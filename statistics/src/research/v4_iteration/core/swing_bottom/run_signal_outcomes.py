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
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SIGNAL_LAYER_CSV_PATH,
    DEFAULT_SIGNAL_OUTCOMES_CSV_PATH,
    DEFAULT_SIGNAL_OUTCOMES_SUMMARY_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_SIGNAL_OUTCOMES_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_SIGNAL_OUTCOMES.md"
)
PRIMARY_SIGNALS = ["LONG_SIGNAL_NEW", "SELL_SIGNAL_NEW"]
RETURN_HORIZONS = [1, 3, 5, 10]
PATH_HORIZONS = [5, 10]
THRESHOLDS = [0.02, 0.05]
MAX_HORIZON = 10

REQUIRED_SIGNAL_COLUMNS = [
    "date",
    "close",
    "signal_state",
    "signal_side",
    "long_signal_event_flag",
    "sell_signal_event_flag",
    "promoted_buy_timing_score",
    "promoted_sell_timing_score",
    "rule_state",
    "operational_state",
    "playbook_label",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate forward outcomes after SAFE signal events.")
    parser.add_argument(
        "--signal-layer-csv",
        default=str(DEFAULT_SIGNAL_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_layer.csv",
    )
    parser.add_argument(
        "--price-json",
        default=str(DEFAULT_PRICE_JSON_PATH),
        help="Default: ../data/daily_price.json",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_SIGNAL_OUTCOMES_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_outcomes.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_SIGNAL_OUTCOMES_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_outcomes_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SIGNAL_OUTCOMES_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_SIGNAL_OUTCOMES.md",
    )
    return parser.parse_args()


def load_price_json(path: str | Path) -> pd.DataFrame:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError("Price JSON must contain a list of daily records.")
    frame = pd.DataFrame(raw)
    rename = {"timestamp": "date"}
    frame = frame.rename(columns=rename)
    required = ["date", "open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Price JSON is missing required fields: {missing}")
    frame = frame.loc[:, required].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame["date"].duplicated().any():
        raise ValueError("Price data contains duplicate dates.")
    if frame[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("Price data contains malformed OHLC values.")
    return frame.sort_values("date").reset_index(drop=True)


def load_signal_layer(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path).sort_values("date").reset_index(drop=True)
    missing = [column for column in REQUIRED_SIGNAL_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Signal layer is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Signal layer contains duplicate dates.")
    return frame


def first_touch_day(path: pd.DataFrame, event_close: float, threshold: float, direction: str) -> int | float:
    if path.empty:
        return np.nan
    if direction == "up":
        target = event_close * (1.0 + threshold)
        matches = np.flatnonzero(path["high"].to_numpy(dtype=float) >= target)
    elif direction == "down":
        target = event_close * (1.0 - threshold)
        matches = np.flatnonzero(path["low"].to_numpy(dtype=float) <= target)
    else:
        raise ValueError(f"Unknown direction: {direction}")
    return int(matches[0] + 1) if matches.size else np.nan


def build_event_outcomes(signals: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    merged = signals.merge(prices, on="date", how="left", suffixes=("", "_price"), validate="one_to_one")
    if merged[["open", "high", "low", "close_price"]].isna().any().any():
        raise ValueError("Signal/price merge left missing OHLC rows.")
    if not np.allclose(merged["close"], merged["close_price"], rtol=0.0, atol=1e-8):
        raise ValueError("Signal close values do not match price JSON close values.")

    events = merged.loc[merged["signal_state"].isin(PRIMARY_SIGNALS)].copy()
    if events.empty:
        raise ValueError("No primary signal events found.")

    rows: list[dict[str, object]] = []
    close = prices["close"].to_numpy(dtype=float)
    high = prices["high"].to_numpy(dtype=float)
    low = prices["low"].to_numpy(dtype=float)
    date_to_index = {date: idx for idx, date in enumerate(prices["date"])}

    for event in events.itertuples(index=False):
        idx = date_to_index[str(event.date)]
        event_close = float(event.close)
        side = str(event.signal_side)
        row: dict[str, object] = {
            "date": event.date,
            "signal_state": event.signal_state,
            "signal_side": side,
            "close": event_close,
            "rule_state": event.rule_state,
            "operational_state": event.operational_state,
            "playbook_label": event.playbook_label,
            "promoted_buy_timing_score": event.promoted_buy_timing_score,
            "promoted_sell_timing_score": event.promoted_sell_timing_score,
            "has_full_10d_path": idx + MAX_HORIZON < len(prices),
        }

        for horizon in RETURN_HORIZONS:
            if idx + horizon < len(prices):
                raw_ret = close[idx + horizon] / event_close - 1.0
                row[f"return_{horizon}d"] = raw_ret if side == "long" else -raw_ret
                row[f"raw_return_{horizon}d"] = raw_ret
            else:
                row[f"return_{horizon}d"] = np.nan
                row[f"raw_return_{horizon}d"] = np.nan

        for horizon in PATH_HORIZONS:
            end = min(idx + horizon + 1, len(prices))
            path_high = high[idx + 1 : end]
            path_low = low[idx + 1 : end]
            if path_high.size:
                up = np.nanmax(path_high / event_close - 1.0)
                down = np.nanmin(path_low / event_close - 1.0)
                if side == "long":
                    row[f"max_up_{horizon}d"] = up
                    row[f"max_down_{horizon}d"] = down
                    row[f"favorable_excursion_{horizon}d"] = up
                    row[f"adverse_excursion_{horizon}d"] = down
                else:
                    row[f"max_up_{horizon}d"] = up
                    row[f"max_down_{horizon}d"] = down
                    row[f"favorable_excursion_{horizon}d"] = -down
                    row[f"adverse_excursion_{horizon}d"] = -up
            else:
                row[f"max_up_{horizon}d"] = np.nan
                row[f"max_down_{horizon}d"] = np.nan
                row[f"favorable_excursion_{horizon}d"] = np.nan
                row[f"adverse_excursion_{horizon}d"] = np.nan

        path10 = prices.iloc[idx + 1 : min(idx + MAX_HORIZON + 1, len(prices))].copy()
        plus2_day = first_touch_day(path10, event_close, 0.02, "up")
        minus2_day = first_touch_day(path10, event_close, 0.02, "down")
        row["time_to_plus_2pct_10d"] = plus2_day
        row["time_to_minus_2pct_10d"] = minus2_day
        row["plus_2pct_before_minus_2pct_10d"] = (
            int(np.isfinite(plus2_day) and (not np.isfinite(minus2_day) or plus2_day < minus2_day))
        )
        row["minus_2pct_before_plus_2pct_10d"] = (
            int(np.isfinite(minus2_day) and (not np.isfinite(plus2_day) or minus2_day < plus2_day))
        )

        for horizon in PATH_HORIZONS:
            path = prices.iloc[idx + 1 : min(idx + horizon + 1, len(prices))]
            for threshold in THRESHOLDS:
                pct_label = f"{int(threshold * 100)}pct"
                up_day = first_touch_day(path, event_close, threshold, "up")
                down_day = first_touch_day(path, event_close, threshold, "down")
                row[f"touch_plus_{pct_label}_{horizon}d"] = int(np.isfinite(up_day))
                row[f"touch_minus_{pct_label}_{horizon}d"] = int(np.isfinite(down_day))
                if side == "long":
                    row[f"touch_favorable_{pct_label}_{horizon}d"] = int(np.isfinite(up_day))
                    row[f"touch_adverse_{pct_label}_{horizon}d"] = int(np.isfinite(down_day))
                else:
                    row[f"touch_favorable_{pct_label}_{horizon}d"] = int(np.isfinite(down_day))
                    row[f"touch_adverse_{pct_label}_{horizon}d"] = int(np.isfinite(up_day))

        if side == "long":
            row["favorable_2pct_before_adverse_2pct_10d"] = row["plus_2pct_before_minus_2pct_10d"]
            row["adverse_2pct_before_favorable_2pct_10d"] = row["minus_2pct_before_plus_2pct_10d"]
            row["time_to_favorable_2pct_10d"] = plus2_day
            row["time_to_adverse_2pct_10d"] = minus2_day
        else:
            row["favorable_2pct_before_adverse_2pct_10d"] = row["minus_2pct_before_plus_2pct_10d"]
            row["adverse_2pct_before_favorable_2pct_10d"] = row["plus_2pct_before_minus_2pct_10d"]
            row["time_to_favorable_2pct_10d"] = minus2_day
            row["time_to_adverse_2pct_10d"] = plus2_day

        rows.append(row)

    return pd.DataFrame(rows)


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.median()) if values.notna().any() else np.nan


def build_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for group_name, group in events.groupby("signal_state", sort=True):
        rows.append({"group": group_name, "metric": "event_count", "value": float(len(group))})
        rows.append({"group": group_name, "metric": "full_10d_path_count", "value": float(group["has_full_10d_path"].sum())})
        for horizon in RETURN_HORIZONS:
            rows.append({"group": group_name, "metric": f"mean_return_{horizon}d", "value": safe_mean(group[f"return_{horizon}d"])})
            rows.append({"group": group_name, "metric": f"median_return_{horizon}d", "value": safe_median(group[f"return_{horizon}d"])})
            rows.append({"group": group_name, "metric": f"win_rate_{horizon}d", "value": safe_mean(group[f"return_{horizon}d"].gt(0).astype(float))})
        for horizon in PATH_HORIZONS:
            rows.append({"group": group_name, "metric": f"mean_favorable_excursion_{horizon}d", "value": safe_mean(group[f"favorable_excursion_{horizon}d"])})
            rows.append({"group": group_name, "metric": f"mean_adverse_excursion_{horizon}d", "value": safe_mean(group[f"adverse_excursion_{horizon}d"])})
            for threshold in THRESHOLDS:
                pct_label = f"{int(threshold * 100)}pct"
                rows.append({"group": group_name, "metric": f"touch_favorable_{pct_label}_{horizon}d_rate", "value": safe_mean(group[f"touch_favorable_{pct_label}_{horizon}d"])})
                rows.append({"group": group_name, "metric": f"touch_adverse_{pct_label}_{horizon}d_rate", "value": safe_mean(group[f"touch_adverse_{pct_label}_{horizon}d"])})
        rows.append({"group": group_name, "metric": "favorable_2pct_before_adverse_2pct_10d_rate", "value": safe_mean(group["favorable_2pct_before_adverse_2pct_10d"])})
        rows.append({"group": group_name, "metric": "adverse_2pct_before_favorable_2pct_10d_rate", "value": safe_mean(group["adverse_2pct_before_favorable_2pct_10d"])})
        rows.append({"group": group_name, "metric": "median_time_to_favorable_2pct_10d", "value": safe_median(group["time_to_favorable_2pct_10d"])})
        rows.append({"group": group_name, "metric": "median_time_to_adverse_2pct_10d", "value": safe_median(group["time_to_adverse_2pct_10d"])})
    return pd.DataFrame(rows)


def pivot_summary(summary: pd.DataFrame) -> pd.DataFrame:
    return summary.pivot_table(index="group", columns="metric", values="value", aggfunc="first").reset_index()


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


def render_markdown(events: pd.DataFrame, summary: pd.DataFrame) -> str:
    pivot = pivot_summary(summary)
    display = pivot[
        [
            "group",
            "event_count",
            "mean_return_5d",
            "median_return_5d",
            "mean_return_10d",
            "median_return_10d",
            "mean_favorable_excursion_10d",
            "mean_adverse_excursion_10d",
            "touch_favorable_2pct_10d_rate",
            "touch_adverse_2pct_10d_rate",
            "favorable_2pct_before_adverse_2pct_10d_rate",
            "adverse_2pct_before_favorable_2pct_10d_rate",
            "median_time_to_favorable_2pct_10d",
        ]
    ].copy()
    for column in [
        "mean_return_5d",
        "median_return_5d",
        "mean_return_10d",
        "median_return_10d",
        "mean_favorable_excursion_10d",
        "mean_adverse_excursion_10d",
        "touch_favorable_2pct_10d_rate",
        "touch_adverse_2pct_10d_rate",
        "favorable_2pct_before_adverse_2pct_10d_rate",
        "adverse_2pct_before_favorable_2pct_10d_rate",
    ]:
        display[column] = display[column].map(lambda value: pct(float(value)))
    for column in ["event_count", "median_time_to_favorable_2pct_10d"]:
        display[column] = display[column].map(lambda value: number(float(value)))

    conclusion_parts: list[str] = []
    for signal in PRIMARY_SIGNALS:
        row = pivot.loc[pivot["group"].eq(signal)]
        if row.empty:
            continue
        mean10 = float(row["mean_return_10d"].iloc[0])
        favorable_first = float(row["favorable_2pct_before_adverse_2pct_10d_rate"].iloc[0])
        adverse_first = float(row["adverse_2pct_before_favorable_2pct_10d_rate"].iloc[0])
        if mean10 > 0 and favorable_first >= adverse_first:
            conclusion_parts.append(f"`{signal}` shows directional edge in forward paths.")
        elif mean10 > 0:
            conclusion_parts.append(f"`{signal}` has positive average outcome but path ordering is mixed.")
        else:
            conclusion_parts.append(f"`{signal}` does not show a clean positive forward-path edge.")
    conclusion = " ".join(conclusion_parts)

    lines = [
        "# SAFE v4.0 Signal Outcome Evaluation",
        "",
        "## Purpose",
        "",
        "This pass measures what happens after discrete structural signal events. It is event-based forward-path analysis only: no execution, entries/exits, stops, position sizing, portfolio logic, PnL, or backtests.",
        "",
        "## Event Selection",
        "",
        "- Primary events: `LONG_SIGNAL_NEW`, `SELL_SIGNAL_NEW`",
        "- Fixed-horizon close-to-close returns: 1d, 3d, 5d, 10d",
        "- Path metrics: 5d and 10d favorable/adverse excursions",
        "- Touch metrics: +/-2% and +/-5%, plus 2% favorable/adverse ordering inside 10d",
        "",
        "## Signal Outcome Summary",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Interpretation Questions",
        "",
        "1. Directional correctness: summarized by side-adjusted mean/median returns.",
        "2. Path cleanliness: summarized by favorable versus adverse excursion and 2% ordering.",
        "3. Adverse movement before favorable movement: summarized by adverse-before-favorable 2% rate.",
        "4. Signal speed: summarized by median time to favorable 2% touch.",
        "5. Long versus sell difference: shown in the side-by-side signal summary.",
        "",
        "## Decision Framing",
        "",
        conclusion if conclusion else "No primary signal events were available for interpretation.",
        "",
        "These results describe forward behavior after structural signals. They do not define a strategy or prove tradability.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/signal_outcomes.csv`",
        "- `out/swing_bottom/signal_outcomes_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def validate_outputs(events: pd.DataFrame) -> None:
    if events.empty:
        raise ValueError("Signal outcome table is empty.")
    unexpected = sorted(set(events["signal_state"].dropna()) - set(PRIMARY_SIGNALS))
    if unexpected:
        raise ValueError(f"Outcome table includes non-primary signals: {unexpected}")
    if events["date"].duplicated().any():
        raise ValueError("Outcome table contains duplicate event dates.")
    if events[["return_1d", "return_3d", "return_5d", "return_10d"]].isna().to_numpy().all():
        raise ValueError("No fixed-horizon returns were computed.")


def run(args: argparse.Namespace) -> None:
    prices = load_price_json(args.price_json)
    signals = load_signal_layer(args.signal_layer_csv)
    events = build_event_outcomes(signals, prices)
    validate_outputs(events)
    summary = build_summary(events)
    markdown = render_markdown(events, summary)

    out_csv = Path(args.out_csv)
    out_summary = Path(args.out_summary_csv)
    out_md = Path(args.out_md)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(out_csv, index=False)
    summary.to_csv(out_summary, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_summary}")
    print(f"Wrote {out_md}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
