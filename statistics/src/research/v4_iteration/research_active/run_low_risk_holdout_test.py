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
from src.research.v4_iteration.research_active.run_low_risk_daily_simulator import (
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
    build_frame_and_trades,
    build_state_arrays,
    build_trade_log,
    parse_frictions,
    simulate_daily_path,
)


DEFAULT_LOW_RISK_HOLDOUT_TEST_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_holdout_test.csv"
DEFAULT_LOW_RISK_HOLDOUT_FRICTION_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_holdout_friction.csv"
DEFAULT_LOW_RISK_HOLDOUT_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_LOW_RISK_HOLDOUT_TEST.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a strict out-of-time holdout test on the frozen low-risk template.",
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
        "--frictions-bps",
        default="0,10,25",
        help="Comma-separated round-trip friction assumptions in bps. Default: 0,10,25",
    )
    parser.add_argument(
        "--holdout-fraction",
        type=float,
        default=0.20,
        help="Final holdout fraction of the daily chronology. Default: 0.20",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_LOW_RISK_HOLDOUT_TEST_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_holdout_test.csv",
    )
    parser.add_argument(
        "--out-friction-csv",
        default=str(DEFAULT_LOW_RISK_HOLDOUT_FRICTION_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_holdout_friction.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_LOW_RISK_HOLDOUT_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_LOW_RISK_HOLDOUT_TEST.md",
    )
    return parser.parse_args()


def compute_holdout_boundary(frame: pd.DataFrame, holdout_fraction: float) -> pd.Timestamp:
    if not (0.05 <= holdout_fraction < 0.50):
        raise ValueError("holdout_fraction must be between 0.05 and 0.50.")
    ordered = frame.sort_values("date").reset_index(drop=True)
    boundary_idx = int(len(ordered) * (1.0 - holdout_fraction))
    boundary_idx = min(max(boundary_idx, 1), len(ordered) - 1)
    return pd.to_datetime(ordered.loc[boundary_idx, "date"])


def summarize_segment(
    daily: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    segment_name: str,
    segment_start: pd.Timestamp,
    segment_end: pd.Timestamp,
    segment_trade_mask: pd.Series,
) -> dict[str, object]:
    daily_segment = daily.loc[(daily["date"] >= segment_start) & (daily["date"] <= segment_end)].copy()
    trades_segment = trades.loc[segment_trade_mask].copy()
    returns = pd.to_numeric(trades_segment["net_return"], errors="coerce")

    if daily_segment.empty:
        compounded_return = np.nan
        max_drawdown = np.nan
    else:
        equity, drawdown = _equity_curve(daily_segment["net_daily_return"])
        compounded_return = float(equity.iloc[-1] - 1.0) if not equity.empty else np.nan
        max_drawdown = float(drawdown.min()) if not drawdown.empty else np.nan

    return {
        "friction_round_trip_bps": int(daily["friction_round_trip_bps"].iloc[0]),
        "segment_name": segment_name,
        "segment_start": segment_start,
        "segment_end": segment_end,
        "trade_count": int(len(trades_segment)),
        "win_rate": float((returns > 0).mean()) if not returns.empty else np.nan,
        "mean_trade_return": _safe_mean(returns),
        "median_trade_return": _safe_median(returns),
        "compounded_return": compounded_return,
        "max_drawdown": max_drawdown,
        "average_holding_days": _safe_mean(trades_segment["holding_days"]),
        "mean_mfe": _safe_mean(trades_segment["mfe_pct"]),
        "mean_mae": _safe_mean(trades_segment["mae_pct"]),
        "time_in_market": float(pd.to_numeric(daily_segment["position_during_day"], errors="coerce").mean())
        if not daily_segment.empty
        else np.nan,
    }


def build_segment_summary(
    daily: pd.DataFrame,
    trades: pd.DataFrame,
    holdout_start: pd.Timestamp,
) -> pd.DataFrame:
    segment_end = pd.to_datetime(daily["date"].max())
    pre_end = holdout_start - pd.Timedelta(days=1)

    rows = [
        summarize_segment(
            daily,
            trades,
            segment_name="full_sample",
            segment_start=pd.to_datetime(daily["date"].min()),
            segment_end=segment_end,
            segment_trade_mask=pd.Series(True, index=trades.index),
        ),
        summarize_segment(
            daily,
            trades,
            segment_name="pre_holdout",
            segment_start=pd.to_datetime(daily["date"].min()),
            segment_end=pre_end,
            segment_trade_mask=trades["entry_date"] < holdout_start,
        ),
        summarize_segment(
            daily,
            trades,
            segment_name="holdout",
            segment_start=holdout_start,
            segment_end=segment_end,
            segment_trade_mask=trades["entry_date"] >= holdout_start,
        ),
    ]
    return pd.DataFrame(rows)


def build_holdout_friction(segment_summary: pd.DataFrame) -> pd.DataFrame:
    holdout = segment_summary.loc[segment_summary["segment_name"] == "holdout"].copy()
    pre = (
        segment_summary.loc[segment_summary["segment_name"] == "pre_holdout", ["friction_round_trip_bps", "mean_trade_return", "compounded_return", "max_drawdown"]]
        .rename(
            columns={
                "mean_trade_return": "pre_holdout_mean_trade_return",
                "compounded_return": "pre_holdout_compounded_return",
                "max_drawdown": "pre_holdout_max_drawdown",
            }
        )
    )
    merged = holdout.merge(pre, on="friction_round_trip_bps", how="left")
    merged["delta_mean_trade_return_vs_pre"] = (
        pd.to_numeric(merged["mean_trade_return"], errors="coerce")
        - pd.to_numeric(merged["pre_holdout_mean_trade_return"], errors="coerce")
    )
    merged["delta_compounded_return_vs_pre"] = (
        pd.to_numeric(merged["compounded_return"], errors="coerce")
        - pd.to_numeric(merged["pre_holdout_compounded_return"], errors="coerce")
    )
    merged["delta_max_drawdown_vs_pre"] = (
        pd.to_numeric(merged["max_drawdown"], errors="coerce")
        - pd.to_numeric(merged["pre_holdout_max_drawdown"], errors="coerce")
    )
    return merged.sort_values("friction_round_trip_bps").reset_index(drop=True)


def render_markdown(
    segment_summary: pd.DataFrame,
    holdout_friction: pd.DataFrame,
    *,
    holdout_start: pd.Timestamp,
    holdout_end: pd.Timestamp,
) -> str:
    base_segments = segment_summary.loc[segment_summary["friction_round_trip_bps"] == 0].copy()
    full = base_segments.loc[base_segments["segment_name"] == "full_sample"].iloc[0]
    pre = base_segments.loc[base_segments["segment_name"] == "pre_holdout"].iloc[0]
    holdout = base_segments.loc[base_segments["segment_name"] == "holdout"].iloc[0]
    latest_holdout = holdout_friction.sort_values("friction_round_trip_bps").iloc[-1]

    lines = [
        "# SAFE v4.0 Low Risk Holdout Test",
        "",
        "## Section 1 — Why This Holdout Pass Is Being Run",
        "",
        "- this is a strict frozen-rule out-of-time credibility test on the single active template",
        "- no branch design, threshold fitting, or rule re-optimization is allowed in this pass",
        "- the purpose is to see whether the same rule still behaves reasonably in a recent untouched holdout segment",
        "",
        "## Section 2 — Frozen Rule And Holdout Split",
        "",
        "- entry: `low_risk_wait2_persist_reclaim`",
        "- exit: `fixed_horizon_5d`",
        "- handling: one position at a time, overlapping signals skipped while a trade is open",
        "- execution assumption: signal-day close entry, close exit after 5 trading days",
        "- holdout split rule: final 20% of the daily chronology",
        f"- pre-holdout period: `{pd.to_datetime(pre['segment_start']).date()}` -> `{pd.to_datetime(pre['segment_end']).date()}`",
        f"- holdout period: `{holdout_start.date()}` -> `{holdout_end.date()}`",
        "- the split is deterministic and recent; it was chosen for chronology discipline, not for outcome optimization",
        "",
        "## Section 3 — Pre-Holdout Vs Holdout Comparison",
        "",
        "| Segment | Trade count | Win rate | Mean trade return | Median trade return | Compounded return | Max drawdown | Mean MFE | Mean MAE | Time in market |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in base_segments.iterrows():
        lines.append(
            f"| `{row['segment_name']}` | {int(row['trade_count'])} | {row['win_rate']:.2%} | "
            f"{row['mean_trade_return']:.2%} | {row['median_trade_return']:.2%} | {row['compounded_return']:.2%} | "
            f"{row['max_drawdown']:.2%} | {row['mean_mfe']:.2%} | {row['mean_mae']:.2%} | {row['time_in_market']:.2%} |"
        )

    lines.extend(["", "## Section 4 — Holdout Friction Sensitivity", ""])
    lines.append("| Round-trip friction | Holdout trades | Holdout mean trade return | Holdout compounded return | Holdout max drawdown | Read |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for _, row in holdout_friction.iterrows():
        if int(row["trade_count"]) == 0:
            read = "no holdout trades"
        elif row["compounded_return"] > 0:
            read = "positive but sparse"
        else:
            read = "weak / broken"
        lines.append(
            f"| `{int(row['friction_round_trip_bps'])}` bps | {int(row['trade_count'])} | "
            f"{row['mean_trade_return']:.2%} | {row['compounded_return']:.2%} | {row['max_drawdown']:.2%} | {read} |"
        )

    lines.extend(["", "## Section 5 — Clear Conclusion", ""])
    if int(holdout["trade_count"]) == 0:
        lines.append("- the rule did not fire in the holdout, so this pass cannot say much about recent viability.")
    else:
        lines.append(f"- the rule did fire in holdout, but only `{int(holdout['trade_count'])}` times, so evidence remains sparse.")

    if int(holdout["trade_count"]) > 0 and holdout["compounded_return"] > 0:
        lines.append("- holdout performance is positive rather than broken, which is the main credibility hurdle for this pass.")
    else:
        lines.append("- holdout performance is too weak to keep confidence high.")

    if int(holdout["trade_count"]) > 0:
        if holdout["mean_trade_return"] < pre["mean_trade_return"]:
            lines.append("- holdout is weaker than pre-holdout, but not obviously dead.")
        else:
            lines.append("- holdout is not materially worse than pre-holdout on mean trade return.")

    if latest_holdout["compounded_return"] > 0:
        lines.append("- modest costs do not overturn the holdout read, though the sample is too small for strong claims.")
    else:
        lines.append("- friction worsens the holdout enough that confidence should remain low.")

    lines.append("- this is still not production readiness or full walk-forward proof.")
    if int(holdout["trade_count"]) >= 2 and holdout["compounded_return"] > 0:
        lines.append("- the template survives the holdout well enough to remain the primary active research template.")
        lines.append("- the next justified step is a stricter template-specific implementation in the accepted walk-forward path, not more branch exploration.")
    else:
        lines.append("- the template should remain provisional until more recent out-of-time evidence accumulates.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frictions = parse_frictions(args.frictions_bps)
    frame, trades_base = build_frame_and_trades(args)
    holdout_start = compute_holdout_boundary(frame, args.holdout_fraction)
    holdout_end = pd.to_datetime(frame["date"].max())
    state = build_state_arrays(frame, trades_base)

    segment_frames: list[pd.DataFrame] = []
    holdout_rows: list[pd.DataFrame] = []
    for round_trip_bps in frictions:
        daily = simulate_daily_path(frame, trades_base, state, round_trip_bps)
        trade_log = build_trade_log(trades_base, round_trip_bps)
        segment_summary = build_segment_summary(daily, trade_log, holdout_start)
        holdout_friction = build_holdout_friction(segment_summary)
        segment_frames.append(segment_summary)
        holdout_rows.append(holdout_friction)

    segment_summary_all = pd.concat(segment_frames, ignore_index=True)
    holdout_friction_all = pd.concat(holdout_rows, ignore_index=True)

    out_csv = Path(args.out_csv)
    out_friction_csv = Path(args.out_friction_csv)
    out_md = Path(args.out_md)
    for path in (out_csv, out_friction_csv, out_md):
        path.parent.mkdir(parents=True, exist_ok=True)

    segment_summary_all.to_csv(out_csv, index=False)
    holdout_friction_all.to_csv(out_friction_csv, index=False)
    out_md.write_text(
        render_markdown(
            segment_summary_all,
            holdout_friction_all,
            holdout_start=holdout_start,
            holdout_end=holdout_end,
        ),
        encoding="utf-8",
    )

    print("SAFE v4.0 low-risk holdout test complete.")
    print(f"Holdout start: {holdout_start.date()}")
    print(f"Holdout end: {holdout_end.date()}")
    print(f"Friction assumptions: {', '.join(str(value) for value in frictions)} bps round-trip")
    print(f"Segment summary: {out_csv}")
    print(f"Holdout friction summary: {out_friction_csv}")
    print(f"Markdown: {out_md}")


if __name__ == "__main__":
    main()
