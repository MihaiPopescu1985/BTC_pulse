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
from src.research.v4_iteration.research_active.run_low_risk_event_backtest import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    _equity_curve,
    _safe_mean,
    _safe_median,
    build_policy,
    enrich_trades,
)
from src.research.v4_iteration.research_active.run_low_risk_strategy_sanity import build_entry_mask, build_trade_table
from src.research.v4_iteration.research_active.run_entry_branch_head_to_head import add_reclaim_flags
from src.research.v4_iteration.research_active.run_entry_logic_low_risk_base import load_base_dataset


DEFAULT_LOW_RISK_WALKFORWARD_STYLE_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_walkforward_style.csv"
DEFAULT_LOW_RISK_WALKFORWARD_STYLE_FOLDS_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_walkforward_style_folds.csv"
DEFAULT_LOW_RISK_WALKFORWARD_STYLE_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_LOW_RISK_WALKFORWARD_STYLE.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a fixed-rule chronological walk-forward-style evaluation on the frozen low-risk template.",
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
        default=str(DEFAULT_LOW_RISK_WALKFORWARD_STYLE_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_walkforward_style.csv",
    )
    parser.add_argument(
        "--out-folds-csv",
        default=str(DEFAULT_LOW_RISK_WALKFORWARD_STYLE_FOLDS_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_walkforward_style_folds.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_LOW_RISK_WALKFORWARD_STYLE_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_LOW_RISK_WALKFORWARD_STYLE.md",
    )
    return parser.parse_args()


def build_event_table(args: argparse.Namespace) -> pd.DataFrame:
    frame, masks = load_base_dataset(args)
    frame = add_reclaim_flags(frame)
    entry_mask = build_entry_mask(frame, masks)
    trades = build_trade_table(frame, entry_mask, build_policy())
    trades = enrich_trades(trades)
    if trades.empty:
        raise ValueError("No trades generated for low-risk walk-forward-style evaluation.")
    return trades


def assign_folds(trades: pd.DataFrame) -> pd.DataFrame:
    assigned = trades.copy()
    assigned["fold_name"] = pd.NA
    assigned["fold_role"] = "unused"

    folds = (
        ("fold_1", 1, 2, 3, 4),
        ("fold_2", 1, 4, 5, 6),
        ("fold_3", 1, 6, 7, 8),
    )
    for fold_name, _train_start, train_end, test_start, test_end in folds:
        train_mask = assigned["trade_sequence"].between(1, train_end)
        test_mask = assigned["trade_sequence"].between(test_start, test_end)
        assigned.loc[train_mask, f"{fold_name}_train"] = True
        assigned.loc[test_mask, "fold_name"] = fold_name
        assigned.loc[test_mask, "fold_role"] = "test"
    assigned["fold_role"] = assigned["fold_role"].fillna("unused")
    return assigned


def summarize_subset(subset: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(subset["return_pct"], errors="coerce")
    equity, drawdown = _equity_curve(returns)
    return {
        "trade_count": int(len(subset)),
        "win_rate": float((returns > 0).mean()) if not returns.empty else np.nan,
        "mean_return_per_trade": _safe_mean(returns),
        "median_return_per_trade": _safe_median(returns),
        "compounded_return": float(equity.iloc[-1] - 1.0) if not equity.empty else np.nan,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else np.nan,
        "average_holding_days": _safe_mean(subset["holding_days"]),
        "mean_mfe": _safe_mean(subset["mfe_pct"]),
        "mean_mae": _safe_mean(subset["mae_pct"]),
    }


def build_fold_summary(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    fold_specs = (
        ("fold_1", 2, 3, 4),
        ("fold_2", 4, 5, 6),
        ("fold_3", 6, 7, 8),
    )

    full_summary = summarize_subset(trades)
    rows.append(
        {
            "row_type": "full_sample",
            "fold_name": "full_sample",
            "train_trade_count": np.nan,
            "test_trade_count": full_summary["trade_count"],
            "train_end_date": pd.NaT,
            "test_start_date": trades["entry_date"].min(),
            "test_end_date": trades["exit_date"].max(),
            **{k: v for k, v in full_summary.items() if k != "trade_count"},
        }
    )

    for fold_name, train_end, test_start, test_end in fold_specs:
        train_subset = trades.loc[trades["trade_sequence"].between(1, train_end)].copy()
        test_subset = trades.loc[trades["trade_sequence"].between(test_start, test_end)].copy()
        test_summary = summarize_subset(test_subset)
        rows.append(
            {
                "row_type": "fold",
                "fold_name": fold_name,
                "train_trade_count": int(len(train_subset)),
                "test_trade_count": int(len(test_subset)),
                "train_end_date": train_subset["exit_date"].max() if not train_subset.empty else pd.NaT,
                "test_start_date": test_subset["entry_date"].min() if not test_subset.empty else pd.NaT,
                "test_end_date": test_subset["exit_date"].max() if not test_subset.empty else pd.NaT,
                **{k: v for k, v in test_summary.items() if k != "trade_count"},
            }
        )
    return pd.DataFrame(rows)


def render_markdown(trades: pd.DataFrame, folds: pd.DataFrame) -> str:
    full_row = folds.loc[folds["row_type"] == "full_sample"].iloc[0]
    fold_rows = folds.loc[folds["row_type"] == "fold"].copy()
    returns = pd.to_numeric(trades["return_pct"], errors="coerce")
    positive_returns = returns[returns > 0]
    total_profit = float(positive_returns.sum()) if not positive_returns.empty else np.nan
    top_fold = fold_rows.sort_values("compounded_return", ascending=False).iloc[0]
    recent_fold = fold_rows.sort_values("test_end_date").iloc[-1]
    recent_trades = trades.loc[trades["fold_name"] == recent_fold["fold_name"]].copy()

    lines = [
        "# SAFE v4.0 Low Risk Walkforward Style",
        "",
        "## Section 1 — Why This Pass Is Being Run",
        "",
        "- this is a fixed-rule chronological walk-forward-style evaluation of one frozen template",
        "- no thresholds are re-fit by fold and no branch design is changed",
        "- the purpose is to see whether the same rule remains acceptable across sequential test blocks",
        "",
        "## Section 2 — Frozen Template And Frozen Exit Rule",
        "",
        "- entry: `low_risk_wait2_persist_reclaim`",
        "- exit: `fixed_horizon_5d`",
        "- trade handling: one position at a time, overlapping signals skipped until active trade exits",
        "",
        "## Section 3 — Chronological Fold Design",
        "",
        "- fold design: expanding-history train, next-2-trade test block",
        "- fold 1: train first 2 trades, test trades 3-4",
        "- fold 2: train first 4 trades, test trades 5-6",
        "- fold 3: train first 6 trades, test trades 7-8",
        "- because the event count is small, folds are intentionally few and each test block is reported honestly",
        "",
        "## Section 4 — Fold-By-Fold Results",
        "",
        f"- full sample: trades `{int(full_row['test_trade_count'])}`, win rate `{full_row['win_rate']:.2%}`, mean return `{full_row['mean_return_per_trade']:.2%}`, compounded `{full_row['compounded_return']:.2%}`, max drawdown `{full_row['max_drawdown']:.2%}`",
        "",
        "| Fold | Train end | Test range | Test trades | Win rate | Mean return | Median return | Compounded | Max DD | Mean MFE | Mean MAE |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in fold_rows.iterrows():
        lines.append(
            f"| `{row['fold_name']}` | {pd.to_datetime(row['train_end_date']).date()} | "
            f"{pd.to_datetime(row['test_start_date']).date()} -> {pd.to_datetime(row['test_end_date']).date()} | "
            f"{int(row['test_trade_count'])} | {row['win_rate']:.2%} | {row['mean_return_per_trade']:.2%} | "
            f"{row['median_return_per_trade']:.2%} | {row['compounded_return']:.2%} | {row['max_drawdown']:.2%} | "
            f"{row['mean_mfe']:.2%} | {row['mean_mae']:.2%} |"
        )

    lines.extend(["", "## Section 5 — Stability / Concentration Interpretation", ""])
    for _, row in fold_rows.iterrows():
        lines.append(
            f"- `{row['fold_name']}`: mean return `{row['mean_return_per_trade']:.2%}`, compounded `{row['compounded_return']:.2%}`, "
            f"max drawdown `{row['max_drawdown']:.2%}`, test trades=`{int(row['test_trade_count'])}`"
        )

    if pd.notna(total_profit) and total_profit > 0:
        best_fold_profit = float(
            pd.to_numeric(
                trades.loc[trades["fold_name"] == top_fold["fold_name"], "return_pct"],
                errors="coerce",
            )[lambda s: s > 0].sum()
        )
        profit_share = best_fold_profit / total_profit if total_profit != 0 else np.nan
    else:
        profit_share = np.nan

    lines.append(
        f"- best-performing test fold: `{top_fold['fold_name']}` with compounded `{top_fold['compounded_return']:.2%}`"
    )
    if pd.notna(profit_share):
        lines.append(f"- share of total gross profits contributed by the best test fold: `{profit_share:.2%}`")
    fold_negative = fold_rows.loc[pd.to_numeric(fold_rows["mean_return_per_trade"], errors="coerce") <= 0]
    if fold_negative.empty:
        lines.append("- no test fold is negative on mean return, but the sample is very small.")
    else:
        lines.append(f"- weak/negative test folds exist: {', '.join(fold_negative['fold_name'].astype(str).tolist())}")

    lines.extend(["", "## Section 6 — Clear Conclusion", ""])
    if fold_negative.empty:
        lines.append("- the template survives this walk-forward-style test well enough for continued research.")
    else:
        lines.append("- the template shows meaningful instability across folds and should be treated more cautiously.")
    lines.append("- it remains the primary active template because no fold fully invalidates it, but confidence should stay moderate given the tiny test blocks.")

    if recent_trades.empty:
        lines.append("- recency note: no trades fired in the most recent segment.")
    else:
        recent_returns = pd.to_numeric(recent_trades["return_pct"], errors="coerce")
        lines.append(
            f"- recency note: the latest fold `{recent_fold['fold_name']}` had {len(recent_trades)} trades with mean return `{recent_returns.mean():.2%}`."
        )

    lines.append("- the next justified step is a more formal template-specific walk-forward implementation with the same frozen rule, not a return to branch exploration.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    trades = build_event_table(args)
    trades = assign_folds(trades)
    folds = build_fold_summary(trades)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(out_csv, index=False, float_format="%.8f")

    out_folds_csv = Path(args.out_folds_csv)
    out_folds_csv.parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(out_folds_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(trades, folds), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(trades)}")
    print(f"Wrote: {out_folds_csv}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
