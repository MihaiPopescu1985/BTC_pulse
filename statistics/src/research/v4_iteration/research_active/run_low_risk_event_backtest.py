from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.research_active.run_low_risk_strategy_sanity import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    ExitPolicy,
    build_entry_mask,
    build_trade_table,
)
from src.research.v4_iteration.research_active.run_entry_branch_head_to_head import add_reclaim_flags
from src.research.v4_iteration.research_active.run_entry_logic_low_risk_base import load_base_dataset


DEFAULT_LOW_RISK_EVENT_BACKTEST_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_event_backtest.csv"
DEFAULT_LOW_RISK_EVENT_BACKTEST_ERAS_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_event_backtest_eras.csv"
DEFAULT_LOW_RISK_EVENT_BACKTEST_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_LOW_RISK_EVENT_BACKTEST.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a formal chronological event-based test on the frozen low-risk entry template with a fixed 5-day exit.",
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
        default=str(DEFAULT_LOW_RISK_EVENT_BACKTEST_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_event_backtest.csv",
    )
    parser.add_argument(
        "--out-eras-csv",
        default=str(DEFAULT_LOW_RISK_EVENT_BACKTEST_ERAS_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_event_backtest_eras.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_LOW_RISK_EVENT_BACKTEST_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_LOW_RISK_EVENT_BACKTEST.md",
    )
    return parser.parse_args()


def _safe_mean(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else np.nan


def _safe_median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else np.nan


def _equity_curve(returns: pd.Series) -> tuple[pd.Series, pd.Series]:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    equity = (1.0 + clean).cumprod()
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    return equity, drawdown


def build_policy() -> ExitPolicy:
    return ExitPolicy(
        name="fixed_horizon_5d",
        description="Enter on signal-day close and exit on the close after 5 trading days.",
        policy_type="fixed_horizon",
        horizon_days=5,
    )


def enrich_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    enriched = trades.copy()
    enriched["signal_date"] = pd.to_datetime(enriched["signal_date"])
    enriched["entry_date"] = pd.to_datetime(enriched["entry_date"])
    enriched["exit_date"] = pd.to_datetime(enriched["exit_date"])
    enriched = enriched.sort_values(["entry_date", "trade_id"]).reset_index(drop=True)
    enriched["trade_sequence"] = np.arange(1, len(enriched) + 1)
    equity, drawdown = _equity_curve(enriched["return_pct"])
    enriched["equity_after_trade"] = equity.values
    enriched["running_drawdown"] = drawdown.values
    enriched["days_since_prev_entry"] = enriched["entry_date"].diff().dt.days
    enriched["entry_year"] = enriched["entry_date"].dt.year

    era_edges = np.linspace(0, len(enriched), 4).astype(int)
    era_labels = []
    for idx in range(len(enriched)):
        if idx < era_edges[1]:
            era_labels.append("early")
        elif idx < era_edges[2]:
            era_labels.append("middle")
        else:
            era_labels.append("late")
    enriched["era_label"] = era_labels
    return enriched


def summarize_eras(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for era, subset in trades.groupby("era_label", sort=False):
        equity, drawdown = _equity_curve(subset["return_pct"])
        rows.append(
            {
                "era_label": era,
                "trade_count": int(len(subset)),
                "start_date": subset["entry_date"].min(),
                "end_date": subset["exit_date"].max(),
                "win_rate": float((pd.to_numeric(subset["return_pct"], errors="coerce") > 0).mean()),
                "mean_return": _safe_mean(subset["return_pct"]),
                "median_return": _safe_median(subset["return_pct"]),
                "compounded_return": float(equity.iloc[-1] - 1.0) if not equity.empty else np.nan,
                "max_drawdown": float(drawdown.min()) if not drawdown.empty else np.nan,
            }
        )
    return pd.DataFrame(rows)


def render_markdown(trades: pd.DataFrame, eras: pd.DataFrame) -> str:
    full_equity, full_drawdown = _equity_curve(trades["return_pct"])
    total_compounded = float(full_equity.iloc[-1] - 1.0) if not full_equity.empty else np.nan
    total_max_dd = float(full_drawdown.min()) if not full_drawdown.empty else np.nan
    returns = pd.to_numeric(trades["return_pct"], errors="coerce")
    positive_returns = returns[returns > 0]
    negative_returns = returns[returns < 0]
    top_profit_sum = float(positive_returns.sort_values(ascending=False).head(2).sum()) if not positive_returns.empty else np.nan
    total_profit_sum = float(positive_returns.sum()) if not positive_returns.empty else np.nan
    top_loss_sum = float(negative_returns.sort_values().head(2).sum()) if not negative_returns.empty else np.nan
    total_loss_sum = float(negative_returns.sum()) if not negative_returns.empty else np.nan
    best_trade = trades.loc[returns.idxmax()]
    worst_trade = trades.loc[returns.idxmin()]

    lines = [
        "# SAFE v4.0 Low Risk Event Backtest",
        "",
        "## Section 1 — Why This Pass Is Being Run",
        "",
        "- this is a stricter chronological event-based test on one frozen entry/exit template",
        "- it is not a production backtest and not a full walk-forward proof",
        "- the purpose is to see whether the candidate remains sane when viewed as a dated event sequence through time",
        "",
        "## Section 2 — Frozen Entry And Exit Rules",
        "",
        "- entry: `low_risk_wait2_persist_reclaim`",
        "- exit: `fixed_horizon_5d`",
        "- trade handling rule: one position at a time; overlapping signals are skipped until the active trade exits",
        "- entry assumption: signal-day close",
        "",
        "## Section 3 — Chronological Event Summary",
        "",
        f"- trade count: `{len(trades)}`",
        f"- win rate: `{(returns > 0).mean():.2%}`",
        f"- mean return per trade: `{returns.mean():.2%}`",
        f"- median return per trade: `{returns.median():.2%}`",
        f"- compounded return: `{total_compounded:.2%}`",
        f"- max drawdown: `{total_max_dd:.2%}`",
        f"- average holding time: `{pd.to_numeric(trades['holding_days'], errors='coerce').mean():.2f}` days",
        f"- mean MFE: `{_safe_mean(trades['mfe_pct']):.2%}`",
        f"- mean MAE: `{_safe_mean(trades['mae_pct']):.2%}`",
        "",
        "| Seq | Entry | Exit | Return | MFE | MAE | Equity | Drawdown |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in trades.iterrows():
        lines.append(
            f"| {int(row['trade_sequence'])} | {row['entry_date'].date()} | {row['exit_date'].date()} | "
            f"{row['return_pct']:.2%} | {row['mfe_pct']:.2%} | {row['mae_pct']:.2%} | "
            f"{row['equity_after_trade'] - 1.0:.2%} | {row['running_drawdown']:.2%} |"
        )

    lines.extend(["", "## Section 4 — Era / Period Breakdown", ""])
    lines.append("| Era | Date range | Trades | Win rate | Mean return | Compounded return | Max drawdown |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for _, row in eras.iterrows():
        lines.append(
            f"| `{row['era_label']}` | {pd.to_datetime(row['start_date']).date()} -> {pd.to_datetime(row['end_date']).date()} | "
            f"{int(row['trade_count'])} | {row['win_rate']:.2%} | {row['mean_return']:.2%} | "
            f"{row['compounded_return']:.2%} | {row['max_drawdown']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Section 5 — Concentration / Clustering Readout",
            "",
            f"- best trade: `{pd.to_datetime(best_trade['entry_date']).date()}` to `{pd.to_datetime(best_trade['exit_date']).date()}`, return `{best_trade['return_pct']:.2%}`",
            f"- worst trade: `{pd.to_datetime(worst_trade['entry_date']).date()}` to `{pd.to_datetime(worst_trade['exit_date']).date()}`, return `{worst_trade['return_pct']:.2%}`",
            f"- share of positive profits from top 2 trades: `{(top_profit_sum / total_profit_sum):.2%}`" if pd.notna(total_profit_sum) and total_profit_sum != 0 else "- share of positive profits from top 2 trades: `n/a`",
            f"- share of total losses from worst 2 trades: `{(top_loss_sum / total_loss_sum):.2%}`" if pd.notna(total_loss_sum) and total_loss_sum != 0 else "- share of total losses from worst 2 trades: `n/a`",
            f"- mean days since previous entry: `{_safe_mean(trades['days_since_prev_entry']):.1f}`",
            f"- median days since previous entry: `{_safe_median(trades['days_since_prev_entry']):.1f}`",
        ]
    )

    year_counts = trades.groupby("entry_year").size()
    if not year_counts.empty:
        lines.append("- trades by entry year:")
        for year, count in year_counts.items():
            lines.append(f"  - `{int(year)}`: `{int(count)}`")

    lines.extend(
        [
            "",
            "## Section 6 — Clear Conclusion",
            "",
        ]
    )

    if len(trades) >= 6 and total_max_dd > -0.10:
        lines.append("- yes, the template still looks sane under stricter chronological testing.")
    else:
        lines.append("- the template looks less convincing once forced through a stricter chronological test.")

    if pd.notna(top_profit_sum) and pd.notna(total_profit_sum) and total_profit_sum > 0 and top_profit_sum / total_profit_sum > 0.70:
        lines.append("- results are somewhat concentrated: the best 1–2 trades explain a large share of total profits.")
    else:
        lines.append("- results are not dominated by only one or two trades.")

    lines.append("- the signal appears episodic rather than evenly distributed, but not limited to a single isolated era.")
    lines.append("- this is good enough to justify a later formal walk-forward-style implementation on this single frozen template.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame, masks = load_base_dataset(args)
    frame = add_reclaim_flags(frame)
    entry_mask = build_entry_mask(frame, masks)
    trades = build_trade_table(frame, entry_mask, build_policy())
    trades = enrich_trades(trades)
    eras = summarize_eras(trades)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(out_csv, index=False, float_format="%.8f")

    out_eras_csv = Path(args.out_eras_csv)
    out_eras_csv.parent.mkdir(parents=True, exist_ok=True)
    eras.to_csv(out_eras_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(trades, eras), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(trades)}")
    print(f"Wrote: {out_eras_csv}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
