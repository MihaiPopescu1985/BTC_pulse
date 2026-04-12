from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_CSV_PATH,
    DEFAULT_MINIMAL_STRATEGY_SUMMARY_CSV_PATH,
    DEFAULT_MINIMAL_STRATEGY_TRADES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SIGNAL_LAYER_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_MINIMAL_STRATEGY_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_MINIMAL_STRATEGY_LAYER.md"
)
MAX_HOLD_DAYS = 10
STRICT_ENTRY_COLUMN = "variant_high_closest_to_low"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SAFE minimal long-only strategy layer.")
    parser.add_argument(
        "--signal-layer-csv",
        default=str(DEFAULT_SIGNAL_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_layer.csv",
    )
    parser.add_argument(
        "--conditioning-csv",
        default=str(DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_CSV_PATH),
        help="Default: ../out/swing_bottom/final_long_signal_conditioning.csv",
    )
    parser.add_argument(
        "--price-json",
        default=str(DEFAULT_PRICE_JSON_PATH),
        help="Default: ../data/daily_price.json",
    )
    parser.add_argument(
        "--out-trades-csv",
        default=str(DEFAULT_MINIMAL_STRATEGY_TRADES_CSV_PATH),
        help="Default: ../out/swing_bottom/minimal_strategy_trades.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_MINIMAL_STRATEGY_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/minimal_strategy_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_MINIMAL_STRATEGY_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_MINIMAL_STRATEGY_LAYER.md",
    )
    return parser.parse_args()


def load_price_json(path: str | Path) -> pd.DataFrame:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError("Price JSON must be a list of daily OHLC records.")
    frame = pd.DataFrame(raw).rename(columns={"timestamp": "date"})
    required = ["date", "open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Price JSON is missing required columns: {missing}")
    frame = frame.loc[:, required].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame["date"].duplicated().any():
        raise ValueError("Price JSON contains duplicate dates.")
    if frame[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("Price JSON contains malformed OHLC values.")
    return frame.sort_values("date").reset_index(drop=True)


def load_inputs(signal_path: str | Path, conditioning_path: str | Path, price_path: str | Path) -> pd.DataFrame:
    signals = pd.read_csv(signal_path).sort_values("date").reset_index(drop=True)
    signal_required = [
        "date",
        "close",
        "signal_state",
        "long_signal_event_flag",
        "sell_signal_event_flag",
        "signal_invalidation_event_flag",
        "rule_state",
        "operational_state",
        "playbook_label",
        "promoted_buy_timing_score",
        "promoted_sell_timing_score",
        "timing_score_spread",
        "edge_clarity_score",
        "conflict_score",
    ]
    missing_signal = [column for column in signal_required if column not in signals.columns]
    if missing_signal:
        raise ValueError(f"Signal layer is missing required columns: {missing_signal}")
    if signals["date"].duplicated().any():
        raise ValueError("Signal layer contains duplicate dates.")

    conditioning = pd.read_csv(conditioning_path).sort_values("date").reset_index(drop=True)
    conditioning_required = ["date", STRICT_ENTRY_COLUMN, "long_refinement_bucket", "dist_to_current_down_swing_low_pct"]
    missing_conditioning = [column for column in conditioning_required if column not in conditioning.columns]
    if missing_conditioning:
        raise ValueError(f"Final conditioning file is missing required columns: {missing_conditioning}")
    if conditioning["date"].duplicated().any():
        raise ValueError("Final conditioning file contains duplicate dates.")

    prices = load_price_json(price_path)
    merged = signals.merge(prices, on="date", how="left", suffixes=("", "_price"), validate="one_to_one")
    if merged[["open", "high", "low", "close_price"]].isna().any().any():
        raise ValueError("Signal/price merge left missing OHLC rows.")
    if not np.allclose(merged["close"], merged["close_price"], rtol=0.0, atol=1e-8):
        raise ValueError("Signal close values do not match price JSON close values.")

    entry_context = conditioning.loc[:, ["date", STRICT_ENTRY_COLUMN, "long_refinement_bucket"]].copy()
    merged = merged.merge(entry_context, on="date", how="left", validate="one_to_one")
    merged[STRICT_ENTRY_COLUMN] = pd.to_numeric(merged[STRICT_ENTRY_COLUMN], errors="coerce").fillna(0).astype(int)
    return merged


def first_touch_day(path: pd.DataFrame, entry_price: float, threshold: float, direction: str) -> int | float:
    if path.empty:
        return np.nan
    if direction == "up":
        matches = np.flatnonzero(path["high"].to_numpy(dtype=float) >= entry_price * (1.0 + threshold))
    elif direction == "down":
        matches = np.flatnonzero(path["low"].to_numpy(dtype=float) <= entry_price * (1.0 - threshold))
    else:
        raise ValueError(f"Unknown direction: {direction}")
    return int(matches[0] + 1) if matches.size else np.nan


def build_trade(
    frame: pd.DataFrame,
    strategy_name: str,
    entry_idx: int,
    exit_idx: int,
    exit_reason: str,
    skipped_signals: int,
) -> dict[str, object]:
    entry = frame.iloc[entry_idx]
    exit_row = frame.iloc[exit_idx]
    path = frame.iloc[entry_idx + 1 : exit_idx + 1].copy()
    entry_price = float(entry["close"])
    exit_price = float(exit_row["close"])
    trade_return = exit_price / entry_price - 1.0
    if path.empty:
        max_favorable = 0.0
        max_adverse = 0.0
        up2_day = np.nan
        down2_day = np.nan
    else:
        max_favorable = float(path["high"].max() / entry_price - 1.0)
        max_adverse = float(path["low"].min() / entry_price - 1.0)
        up2_day = first_touch_day(path, entry_price, 0.02, "up")
        down2_day = first_touch_day(path, entry_price, 0.02, "down")

    favorable_first = int(np.isfinite(up2_day) and (not np.isfinite(down2_day) or up2_day < down2_day))
    adverse_first = int(np.isfinite(down2_day) and (not np.isfinite(up2_day) or down2_day < up2_day))
    clean_follow_through = int(favorable_first or (np.isfinite(up2_day) and not np.isfinite(down2_day)))

    return {
        "strategy_name": strategy_name,
        "entry_filter_uses_future_low_label": int(strategy_name == "strict_closest_to_low"),
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_price": entry_price,
        "exit_price": exit_price,
        "return": trade_return,
        "max_favorable_excursion": max_favorable,
        "max_adverse_excursion": max_adverse,
        "duration_days": int(exit_idx - entry_idx),
        "exit_reason": exit_reason,
        "skipped_entry_signals_while_open": skipped_signals,
        "favorable_2pct_before_adverse_2pct": favorable_first,
        "adverse_2pct_before_favorable_2pct": adverse_first,
        "clean_follow_through_flag": clean_follow_through,
        "time_to_favorable_2pct": up2_day,
        "time_to_adverse_2pct": down2_day,
        "entry_buy_score": entry["promoted_buy_timing_score"],
        "entry_sell_score": entry["promoted_sell_timing_score"],
        "entry_timing_spread": entry["timing_score_spread"],
        "entry_edge_clarity": entry["edge_clarity_score"],
        "entry_conflict": entry["conflict_score"],
        "entry_dist_to_current_down_swing_low_pct": entry["dist_to_current_down_swing_low_pct"],
        "entry_long_refinement_bucket": entry["long_refinement_bucket"],
    }


def simulate_strategy(frame: pd.DataFrame, strategy_name: str, entry_mask: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    in_position = False
    entry_idx = -1
    skipped_signals = 0

    for idx, row in frame.iterrows():
        eligible_entry = bool(entry_mask.iloc[idx])
        if in_position:
            if eligible_entry:
                skipped_signals += 1
            held_days = idx - entry_idx
            exit_reason = ""
            if idx > entry_idx and int(row["sell_signal_event_flag"]) == 1:
                exit_reason = "sell_signal_new"
            elif idx > entry_idx and int(row["signal_invalidation_event_flag"]) == 1:
                exit_reason = "signal_invalidated"
            elif held_days >= MAX_HOLD_DAYS:
                exit_reason = "max_hold_10d"
            elif idx == len(frame) - 1:
                exit_reason = "end_of_data"

            if exit_reason:
                rows.append(build_trade(frame, strategy_name, entry_idx, idx, exit_reason, skipped_signals))
                in_position = False
                entry_idx = -1
                skipped_signals = 0
            continue

        if eligible_entry:
            in_position = True
            entry_idx = idx
            skipped_signals = 0

    if in_position and entry_idx >= 0:
        rows.append(build_trade(frame, strategy_name, entry_idx, len(frame) - 1, "end_of_data", skipped_signals))

    return pd.DataFrame(rows)


def run_simulations(frame: pd.DataFrame) -> pd.DataFrame:
    strict_mask = frame[STRICT_ENTRY_COLUMN].eq(1)
    baseline_mask = frame["signal_state"].eq("LONG_SIGNAL_NEW")
    strict = simulate_strategy(frame, "strict_closest_to_low", strict_mask)
    baseline = simulate_strategy(frame, "baseline_all_long_signals", baseline_mask)
    if strict.empty:
        raise ValueError("Strict strategy produced no trades.")
    if baseline.empty:
        raise ValueError("Baseline strategy produced no trades.")
    return pd.concat([strict, baseline], ignore_index=True)


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.median()) if values.notna().any() else np.nan


def build_summary(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for strategy, group in trades.groupby("strategy_name", sort=True):
        metrics = {
            "trade_count": float(len(group)),
            "win_rate": safe_mean(group["return"].gt(0).astype(float)),
            "mean_return": safe_mean(group["return"]),
            "median_return": safe_median(group["return"]),
            "mean_max_favorable_excursion": safe_mean(group["max_favorable_excursion"]),
            "mean_max_adverse_excursion": safe_mean(group["max_adverse_excursion"]),
            "worst_trade_return": float(group["return"].min()),
            "max_drawdown_per_trade": float(group["max_adverse_excursion"].min()),
            "average_duration_days": safe_mean(group["duration_days"]),
            "adverse_first_rate": safe_mean(group["adverse_2pct_before_favorable_2pct"]),
            "clean_follow_through_rate": safe_mean(group["clean_follow_through_flag"]),
            "mean_skipped_signals_while_open": safe_mean(group["skipped_entry_signals_while_open"]),
        }
        for metric, value in metrics.items():
            rows.append({"strategy_name": strategy, "metric": metric, "value": value})
        for reason, count in group["exit_reason"].value_counts().sort_index().items():
            rows.append(
                {
                    "strategy_name": strategy,
                    "metric": f"exit_reason_{reason}_count",
                    "value": float(count),
                }
            )
    return pd.DataFrame(rows)


def pivot_summary(summary: pd.DataFrame) -> pd.DataFrame:
    return summary.pivot_table(index="strategy_name", columns="metric", values="value", aggfunc="first").reset_index()


def pct(value: float, digits: int = 1) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    out = frame.loc[:, columns].copy()
    if out.empty:
        return "_No rows._"
    rendered = out.fillna("n/a").astype(str)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = [
        "| " + " | ".join(str(value).replace("\n", " ") for value in record) + " |"
        for record in rendered.to_numpy()
    ]
    return "\n".join([header, separator, *rows])


def render_markdown(trades: pd.DataFrame, summary: pd.DataFrame) -> str:
    pivot = pivot_summary(summary)
    display = pivot[
        [
            "strategy_name",
            "trade_count",
            "win_rate",
            "mean_return",
            "median_return",
            "mean_max_favorable_excursion",
            "mean_max_adverse_excursion",
            "max_drawdown_per_trade",
            "average_duration_days",
            "adverse_first_rate",
            "clean_follow_through_rate",
        ]
    ].copy()
    for column in display.columns:
        if column == "strategy_name":
            continue
        if column in {"trade_count", "average_duration_days"}:
            display[column] = display[column].map(lambda value: number(float(value)))
        else:
            display[column] = display[column].map(lambda value: pct(float(value)))

    strict = pivot.loc[pivot["strategy_name"].eq("strict_closest_to_low")].iloc[0]
    baseline = pivot.loc[pivot["strategy_name"].eq("baseline_all_long_signals")].iloc[0]
    strict_better = (
        float(strict["mean_return"]) > float(baseline["mean_return"])
        and float(strict["adverse_first_rate"]) < float(baseline["adverse_first_rate"])
        and float(strict["mean_max_adverse_excursion"]) > float(baseline["mean_max_adverse_excursion"])
    )
    if strict_better and float(strict["trade_count"]) >= 5:
        conclusion = "Viable minimal strategy as an oracle feasibility check"
        conclusion_note = (
            "The strict subset improves realized outcomes and path quality versus all long signals, but it uses the "
            "future-derived closest-to-low conditioning label. It is not deployable until that condition is replaced by a causal proxy."
        )
    elif float(strict["mean_return"]) > 0:
        conclusion = "Edge exists but too weak/noisy"
        conclusion_note = "The strict subset has positive behavior, but path quality or sample size is not strong enough for a robust claim."
    else:
        conclusion = "Not usable in current form"
        conclusion_note = "The strict subset does not preserve a positive realized profile under these simple structural exits."

    lines = [
        "# SAFE v4.0 Minimal Strategy Layer",
        "",
        "## Purpose",
        "",
        "This is the first minimal long-only strategy simulation layer. It is intentionally simple and transparent. "
        "It does not add stops, take-profit rules, position sizing, leverage, portfolio logic, or optimization.",
        "",
        "## Rules",
        "",
        "- Position model: binary long or flat, one position at a time.",
        "- Entry: `LONG_SIGNAL_NEW` inside `LONG_QUALITY_HIGH` and `high_closest_to_low` conditioning.",
        "- Exit: first of `SELL_SIGNAL_NEW`, `SIGNAL_INVALIDATED`, max hold of 10 trading days, or end of data.",
        "- Sell signals are used only as exit/risk control, never as standalone short entries.",
        "- Prices use close-to-close accounting for research measurement; this is not an execution model.",
        "",
        "## Causality Caveat",
        "",
        "`strict_closest_to_low` uses the final conditioning subset based on proximity to the eventual confirmed swing low. "
        "That field is future-derived. Therefore this pass is an oracle/feasibility check for whether the cleanest structural subset behaves like a real strategy object, not a deployable causal strategy.",
        "",
        "## Baseline",
        "",
        "`baseline_all_long_signals` uses every `LONG_SIGNAL_NEW` event with the same exits and one-position-at-a-time handling.",
        "",
        "## Summary",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Final Conclusion",
        "",
        f"**{conclusion}.** {conclusion_note}",
        "",
        "This result answers whether the strict structural subset behaves like a plausible strategy object. It is not production-ready and should not be read as deployable.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/minimal_strategy_trades.csv`",
        "- `out/swing_bottom/minimal_strategy_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def validate_trades(trades: pd.DataFrame) -> None:
    if trades.empty:
        raise ValueError("Minimal strategy produced no trades.")
    required = {"strict_closest_to_low", "baseline_all_long_signals"}
    missing = required - set(trades["strategy_name"])
    if missing:
        raise ValueError(f"Trade log missing strategy variants: {sorted(missing)}")
    if (trades["duration_days"] < 0).any():
        raise ValueError("Trade durations must be non-negative.")


def run(args: argparse.Namespace) -> None:
    frame = load_inputs(args.signal_layer_csv, args.conditioning_csv, args.price_json)
    trades = run_simulations(frame)
    validate_trades(trades)
    summary = build_summary(trades)
    markdown = render_markdown(trades, summary)

    out_trades = Path(args.out_trades_csv)
    out_summary = Path(args.out_summary_csv)
    out_md = Path(args.out_md)
    out_trades.parent.mkdir(parents=True, exist_ok=True)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(out_trades, index=False)
    summary.to_csv(out_summary, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_trades}")
    print(f"Wrote {out_summary}")
    print(f"Wrote {out_md}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
