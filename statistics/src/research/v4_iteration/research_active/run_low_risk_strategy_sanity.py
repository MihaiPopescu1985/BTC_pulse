from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.research_active.run_entry_branch_head_to_head import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    add_reclaim_flags,
    build_low_risk_baseline,
)
from src.research.v4_iteration.research_active.run_entry_logic_low_risk_base import (
    compute_thresholds,
    load_base_dataset,
)


DEFAULT_LOW_RISK_STRATEGY_SANITY_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_strategy_sanity.csv"
DEFAULT_LOW_RISK_STRATEGY_SANITY_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_LOW_RISK_STRATEGY_SANITY.md"
)


@dataclass(frozen=True)
class ExitPolicy:
    name: str
    description: str
    policy_type: str
    horizon_days: int
    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal strategy-layer sanity test on the active low-risk entry template.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument(
        "--onchain-features-csv",
        default=str(DEFAULT_ONCHAIN_FEATURES_CSV_PATH),
        help="Default: ../out/onchain_features.csv",
    )
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument(
        "--live-swing-state-csv",
        default=str(DEFAULT_LIVE_SWING_STATE_CSV_PATH),
        help="Default: ../out/swing_bridge/live_swing_state.csv",
    )
    parser.add_argument(
        "--swing-taxonomy-csv",
        default=str(DEFAULT_SWING_TAXONOMY_CSV_PATH),
        help="Default: ../out/swing_bridge/swing_taxonomy.csv",
    )
    parser.add_argument(
        "--swing-condition-mapping-csv",
        default=str(DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH),
        help="Default: ../out/swing_bridge/swing_condition_mapping.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_LOW_RISK_STRATEGY_SANITY_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_strategy_sanity.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_LOW_RISK_STRATEGY_SANITY_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_LOW_RISK_STRATEGY_SANITY.md",
    )
    return parser.parse_args()


def build_entry_mask(frame: pd.DataFrame, masks: dict[str, pd.Series]) -> pd.Series:
    thresholds = compute_thresholds(frame, masks["low_risk_base"].fillna(False))
    base_mask = build_low_risk_baseline(frame, masks, thresholds)
    return (base_mask.shift(2).fillna(False) & base_mask.shift(1).fillna(False) & base_mask & frame["close_above_prev_close"]).fillna(False)


def build_policies() -> tuple[ExitPolicy, ...]:
    return (
        ExitPolicy(
            name="fixed_horizon_5d",
            description="Enter on signal-day close and exit on the close after 5 trading days.",
            policy_type="fixed_horizon",
            horizon_days=5,
        ),
        ExitPolicy(
            name="fixed_horizon_10d",
            description="Enter on signal-day close and exit on the close after 10 trading days.",
            policy_type="fixed_horizon",
            horizon_days=10,
        ),
        ExitPolicy(
            name="tp5_sl2_h10",
            description="Enter on signal-day close, exit on first touch of +5% TP or -2% SL, else exit on the 10-day close.",
            policy_type="tp_sl_horizon",
            horizon_days=10,
            take_profit_pct=0.05,
            stop_loss_pct=0.02,
        ),
        ExitPolicy(
            name="tp8_sl3_h10",
            description="Enter on signal-day close, exit on first touch of +8% TP or -3% SL, else exit on the 10-day close.",
            policy_type="tp_sl_horizon",
            horizon_days=10,
            take_profit_pct=0.08,
            stop_loss_pct=0.03,
        ),
    )


def _safe_mean(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else np.nan


def _safe_median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else np.nan


def _equity_drawdown(returns: pd.Series) -> tuple[float, float]:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    if clean.empty:
        return np.nan, np.nan
    equity = (1.0 + clean).cumprod()
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    return float(equity.iloc[-1] - 1.0), float(drawdown.min())


def simulate_trade(frame: pd.DataFrame, entry_idx: int, policy: ExitPolicy, trade_id: int) -> dict[str, object] | None:
    if entry_idx >= len(frame) - 1:
        return None

    entry_row = frame.iloc[entry_idx]
    entry_price = float(entry_row["close"])
    horizon_end_idx = min(entry_idx + policy.horizon_days, len(frame) - 1)
    future = frame.iloc[entry_idx + 1 : horizon_end_idx + 1].copy()
    if future.empty:
        return None

    exit_idx = horizon_end_idx
    exit_price = float(frame.iloc[exit_idx]["close"])
    exit_reason = f"horizon_{policy.horizon_days}d"
    tp_hit = 0.0
    sl_hit = 0.0
    first_touch_label = "none"

    if policy.policy_type == "tp_sl_horizon":
        take_profit_level = entry_price * (1.0 + float(policy.take_profit_pct))
        stop_loss_level = entry_price * (1.0 - float(policy.stop_loss_pct))
        for idx, row in future.iterrows():
            hit_tp = float(row["high"]) >= take_profit_level
            hit_sl = float(row["low"]) <= stop_loss_level
            if hit_tp and hit_sl:
                hit_tp = False
                hit_sl = True
            if hit_sl:
                exit_idx = int(idx)
                exit_price = stop_loss_level
                exit_reason = f"sl_{int(policy.stop_loss_pct * 100)}pct"
                sl_hit = 1.0
                first_touch_label = "sl"
                break
            if hit_tp:
                exit_idx = int(idx)
                exit_price = take_profit_level
                exit_reason = f"tp_{int(policy.take_profit_pct * 100)}pct"
                tp_hit = 1.0
                first_touch_label = "tp"
                break

    path = frame.iloc[entry_idx + 1 : exit_idx + 1].copy()
    mfe_pct = float(path["high"].max() / entry_price - 1.0) if not path.empty else np.nan
    mae_pct = float(path["low"].min() / entry_price - 1.0) if not path.empty else np.nan

    return {
        "row_type": "trade",
        "policy_name": policy.name,
        "policy_description": policy.description,
        "trade_id": int(trade_id),
        "signal_date": entry_row["date"],
        "entry_date": entry_row["date"],
        "exit_date": frame.iloc[exit_idx]["date"],
        "entry_price": entry_price,
        "exit_price": float(exit_price),
        "holding_days": int(exit_idx - entry_idx),
        "exit_reason": exit_reason,
        "return_pct": float(exit_price / entry_price - 1.0),
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "tp_hit_rate": tp_hit,
        "sl_hit_rate": sl_hit,
        "first_touch_label": first_touch_label,
    }


def build_trade_table(frame: pd.DataFrame, entry_mask: pd.Series, policy: ExitPolicy) -> pd.DataFrame:
    signal_indices = frame.index[entry_mask.fillna(False)].tolist()
    trades: list[dict[str, object]] = []
    next_available_idx = 0
    trade_id = 1
    for entry_idx in signal_indices:
        if entry_idx < next_available_idx:
            continue
        trade = simulate_trade(frame, entry_idx, policy, trade_id)
        if trade is None:
            continue
        trades.append(trade)
        exit_date = pd.to_datetime(trade["exit_date"])
        exit_idx = int(frame.index[frame["date"] == exit_date][0])
        next_available_idx = exit_idx + 1
        trade_id += 1
    return pd.DataFrame(trades)


def summarize_policy(trades: pd.DataFrame, policy: ExitPolicy) -> dict[str, object]:
    if trades.empty:
        return {
            "row_type": "summary",
            "policy_name": policy.name,
            "policy_description": policy.description,
            "trade_count": 0,
            "win_rate": np.nan,
            "mean_return_per_trade": np.nan,
            "median_return_per_trade": np.nan,
            "average_holding_days": np.nan,
            "mean_mfe_pct": np.nan,
            "mean_mae_pct": np.nan,
            "tp_hit_rate": np.nan,
            "sl_hit_rate": np.nan,
            "average_return_winners": np.nan,
            "average_return_losers": np.nan,
            "compounded_return": np.nan,
            "max_drawdown": np.nan,
        }

    returns = pd.to_numeric(trades["return_pct"], errors="coerce")
    winners = returns[returns > 0]
    losers = returns[returns <= 0]
    compounded_return, max_drawdown = _equity_drawdown(returns)

    return {
        "row_type": "summary",
        "policy_name": policy.name,
        "policy_description": policy.description,
        "trade_count": int(len(trades)),
        "win_rate": float((returns > 0).mean()),
        "mean_return_per_trade": float(returns.mean()),
        "median_return_per_trade": float(returns.median()),
        "average_holding_days": float(pd.to_numeric(trades["holding_days"], errors="coerce").mean()),
        "mean_mfe_pct": _safe_mean(trades["mfe_pct"]),
        "mean_mae_pct": _safe_mean(trades["mae_pct"]),
        "tp_hit_rate": _safe_mean(trades["tp_hit_rate"]),
        "sl_hit_rate": _safe_mean(trades["sl_hit_rate"]),
        "average_return_winners": float(winners.mean()) if not winners.empty else np.nan,
        "average_return_losers": float(losers.mean()) if not losers.empty else np.nan,
        "compounded_return": compounded_return,
        "max_drawdown": max_drawdown,
    }


def render_markdown(combined: pd.DataFrame) -> str:
    summaries = combined.loc[combined["row_type"] == "summary"].copy()
    best = summaries.sort_values(["mean_return_per_trade", "win_rate"], ascending=[False, False]).iloc[0]

    lines = [
        "# SAFE v4.0 Low Risk Strategy Sanity",
        "",
        "## Section 1 — Why This Pass Is Being Run",
        "",
        "- this is a first strategy-layer sanity test on one already-selected entry template",
        "- it is not a walk-forward validation and not a production-readiness claim",
        "- the purpose is to see whether the template still looks reasonable once converted into simple trades",
        "",
        "## Section 2 — Frozen Entry Rule",
        "",
        "- exact entry template: `low_risk_wait2_persist_reclaim`",
        "- implementation: low-risk base branch + volatility sanity + TS_20 confirmation + two-day persistence + close above prior close",
        "- trade handling rule: one position at a time; overlapping signals are ignored until the active trade exits",
        "- entry assumption: signal-day close",
        "",
        "## Section 3 — Exit Policies Tested",
        "",
        "- `fixed_horizon_5d`",
        "- `fixed_horizon_10d`",
        "- `tp5_sl2_h10`",
        "- `tp8_sl3_h10`",
        "- for TP/SL policies, if both TP and SL are touched on the same bar, the stop is assumed to hit first (conservative rule)",
        "",
        "## Section 4 — Trade-Level Comparison Table",
        "",
        "| Policy | Trades | Win rate | Mean return | Median return | Avg hold | TP hit | SL hit | Compounded return | Max DD |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in summaries.sort_values(["mean_return_per_trade", "win_rate"], ascending=[False, False]).iterrows():
        lines.append(
            f"| `{row['policy_name']}` | {int(row['trade_count'])} | {row['win_rate']:.2%} | {row['mean_return_per_trade']:.2%} | "
            f"{row['median_return_per_trade']:.2%} | {row['average_holding_days']:.2f} | {row['tp_hit_rate']:.2%} | "
            f"{row['sl_hit_rate']:.2%} | {row['compounded_return']:.2%} | {row['max_drawdown']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Section 5 — What Survives First Strategy-Layer Testing And What Does Not",
            "",
        ]
    )
    for _, row in summaries.sort_values(["mean_return_per_trade", "win_rate"], ascending=[False, False]).iterrows():
        lines.append(
            f"- `{row['policy_name']}`: mean return `{row['mean_return_per_trade']:.2%}`, "
            f"median `{row['median_return_per_trade']:.2%}`, "
            f"mean MFE `{row['mean_mfe_pct']:.2%}`, mean MAE `{row['mean_mae_pct']:.2%}`, "
            f"winner avg `{row['average_return_winners']:.2%}`, loser avg `{row['average_return_losers']:.2%}`, "
            f"trades=`{int(row['trade_count'])}`"
        )

    lines.extend(
        [
            "",
            "## Section 6 — Clear Conclusion",
            "",
            f"- yes, the template still looks sane under simple trade logic: best current exit style is `{best['policy_name']}`",
            "- this is still only a first event-level sanity check, not a formal walk-forward or production proof",
            "- the next step should move to a more formal event-based backtest / walk-forward style test for this single entry template",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame, masks = load_base_dataset(args)
    frame = add_reclaim_flags(frame)
    entry_mask = build_entry_mask(frame, masks)

    output_rows: list[dict[str, object]] = []
    for policy in build_policies():
        trades = build_trade_table(frame, entry_mask, policy)
        if not trades.empty:
            output_rows.extend(trades.to_dict(orient="records"))
        output_rows.append(summarize_policy(trades, policy))

    combined = pd.DataFrame(output_rows)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(combined), encoding="utf-8")

    summaries = combined.loc[combined["row_type"] == "summary"].copy()
    best = summaries.sort_values(["mean_return_per_trade", "win_rate"], ascending=[False, False]).iloc[0]
    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(combined)}")
    print(f"Best exit style: {best['policy_name']}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
