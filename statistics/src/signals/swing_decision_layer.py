from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_BUY_SIDE_HYBRID_SCORES_CSV_PATH,
    DEFAULT_SWING_DECISION_LAYER_CSV_PATH,
    DEFAULT_SWING_DECISION_LAYER_SUMMARY_CSV_PATH,
    DEFAULT_SWING_EXTREME_TIMING_CSV_PATH,
    STATISTICS_DIR,
)
from src.signals.reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
)
from src.signals.swing_extreme_timing import clip01


DEFAULT_SWING_DECISION_LAYER_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_SWING_DECISION_LAYER.md"
)
BUY_SCORE = "promoted_buy_timing_score"
SELL_SCORE = "promoted_sell_timing_score"
SPREAD = "timing_score_spread"
INTENSITY = "timing_score_intensity"
OVERLAP = "timing_score_overlap"
CLARITY = "edge_clarity_score"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first SAFE swing timing decision-layer dataset.")
    parser.add_argument(
        "--buy-side-hybrid-scores-csv",
        default=str(DEFAULT_BUY_SIDE_HYBRID_SCORES_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_hybrid_scores.csv",
    )
    parser.add_argument(
        "--swing-extreme-timing-csv",
        default=str(DEFAULT_SWING_EXTREME_TIMING_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_extreme_timing.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_SWING_DECISION_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_decision_layer.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_SWING_DECISION_LAYER_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_decision_layer_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SWING_DECISION_LAYER_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_SWING_DECISION_LAYER.md",
    )
    return parser.parse_args()


def load_inputs(buy_path: str | Path, sell_path: str | Path) -> pd.DataFrame:
    buy = pd.read_csv(buy_path).sort_values("date").reset_index(drop=True)
    sell = pd.read_csv(sell_path).sort_values("date").reset_index(drop=True)
    required_buy = [
        "date",
        "close",
        "split",
        "current_confirmed_swing_id",
        "current_confirmed_swing_direction",
        "live_swing_direction",
        "days_since_last_pivot",
        "distance_from_last_pivot_pct",
        "current_swing_age_pct_of_median",
        "current_swing_size_pct_of_median",
        "buy_hybrid_weighted_balanced_score",
        "buy_fixed_extreme_timing_score",
        "buy_exhaustion_redesign_score",
        "buy_ordinal_ranking_score",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        "dist_to_current_down_swing_low_pct",
    ]
    required_sell = [
        "date",
        "sell_fixed_extreme_timing_score",
        "sell_extreme_timing_score",
        "sell_phase_prob",
        "sell_exhaustion_score",
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
        "dist_to_current_up_swing_high_pct",
    ]
    missing_buy = [column for column in required_buy if column not in buy.columns]
    missing_sell = [column for column in required_sell if column not in sell.columns]
    if missing_buy:
        raise ValueError(f"Buy-side hybrid file is missing required columns: {missing_buy}")
    if missing_sell:
        raise ValueError(f"Swing extreme timing file is missing required columns: {missing_sell}")
    if buy["date"].duplicated().any() or sell["date"].duplicated().any():
        raise ValueError("Decision-layer inputs must not contain duplicate dates.")

    merged = buy.loc[:, required_buy].merge(
        sell.loc[:, required_sell],
        on="date",
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(buy):
        raise ValueError("Decision-layer merge lost rows; buy/sell timing outputs are not fully date-aligned.")
    if not np.allclose(pd.to_numeric(merged["close"], errors="coerce"), pd.to_numeric(buy["close"], errors="coerce")):
        raise ValueError("Close alignment check failed.")
    return merged


def build_thresholds(frame: pd.DataFrame) -> dict[str, float]:
    fit = frame.loc[frame["split"].isin(["train", "validation"])].copy()
    if fit.empty:
        raise ValueError("No train/validation rows available for decision-layer threshold calibration.")
    buy_score = pd.to_numeric(fit[BUY_SCORE], errors="coerce").dropna()
    sell_score = pd.to_numeric(fit[SELL_SCORE], errors="coerce").dropna()
    if buy_score.empty or sell_score.empty:
        raise ValueError("Cannot calibrate decision-layer thresholds from empty score series.")
    return {
        "buy_high": float(buy_score.quantile(0.80)),
        "buy_moderate": float(buy_score.quantile(0.60)),
        "sell_high": float(sell_score.quantile(0.80)),
        "sell_moderate": float(sell_score.quantile(0.60)),
        "spread_min": 0.10,
    }


def assign_state(row: pd.Series, thresholds: dict[str, float]) -> str:
    buy = float(row[BUY_SCORE])
    sell = float(row[SELL_SCORE])
    spread = float(row[SPREAD])
    buy_high = buy >= thresholds["buy_high"]
    sell_high = sell >= thresholds["sell_high"]
    buy_moderate = buy >= thresholds["buy_moderate"]
    sell_moderate = sell >= thresholds["sell_moderate"]
    clear_buy = spread >= thresholds["spread_min"]
    clear_sell = spread <= -thresholds["spread_min"]

    if buy_high and not sell_moderate and clear_buy:
        return "BUY_SETUP"
    if sell_high and not buy_moderate and clear_sell:
        return "SELL_SETUP"
    if buy_moderate and sell_moderate:
        return "CONFLICT_OVERLAP"
    if not buy_moderate and not sell_moderate:
        return "NEUTRAL_NO_EDGE"
    return "TRANSITION_UNCLEAR"


def add_decision_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    out = frame.copy()
    out[BUY_SCORE] = pd.to_numeric(out["buy_hybrid_weighted_balanced_score"], errors="coerce")
    out[SELL_SCORE] = pd.to_numeric(out["sell_fixed_extreme_timing_score"], errors="coerce")
    if out[[BUY_SCORE, SELL_SCORE]].isna().all(axis=1).any():
        raise ValueError("A row has no buy or sell timing score.")

    buy = out[BUY_SCORE].fillna(0.0).to_numpy(dtype=float)
    sell = out[SELL_SCORE].fillna(0.0).to_numpy(dtype=float)
    out[SPREAD] = buy - sell
    out[INTENSITY] = np.maximum(buy, sell)
    out[OVERLAP] = np.minimum(buy, sell)
    out["buy_dominance_score"] = clip01(buy * (1.0 - sell))
    out["sell_dominance_score"] = clip01(sell * (1.0 - buy))
    out[CLARITY] = clip01(np.abs(buy - sell) * (0.50 + 0.50 * out[INTENSITY].to_numpy(dtype=float)))
    out["conflict_score"] = clip01(out[OVERLAP].to_numpy(dtype=float) * out[INTENSITY].to_numpy(dtype=float))

    thresholds = build_thresholds(out)
    out["decision_state"] = out.apply(assign_state, axis=1, thresholds=thresholds)
    out["buy_score_band"] = np.select(
        [
            out[BUY_SCORE] >= thresholds["buy_high"],
            out[BUY_SCORE] >= thresholds["buy_moderate"],
        ],
        ["high", "moderate"],
        default="low",
    )
    out["sell_score_band"] = np.select(
        [
            out[SELL_SCORE] >= thresholds["sell_high"],
            out[SELL_SCORE] >= thresholds["sell_moderate"],
        ],
        ["high", "moderate"],
        default="low",
    )
    out["score_interaction_bucket"] = np.select(
        [
            (out["buy_score_band"] == "high") & (out["sell_score_band"] == "high"),
            (out["buy_score_band"] == "high") & (out["sell_score_band"] != "high"),
            (out["sell_score_band"] == "high") & (out["buy_score_band"] != "high"),
            (out["buy_score_band"] == "low") & (out["sell_score_band"] == "low"),
        ],
        ["both_high", "buy_high", "sell_high", "both_low"],
        default="mixed_moderate",
    )
    out = add_state_run_columns(out)
    return out, thresholds


def add_state_run_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    state_change = out["decision_state"].ne(out["decision_state"].shift()).fillna(True)
    out["decision_state_run_id"] = state_change.cumsum().astype(int)
    out["decision_state_age_days"] = out.groupby("decision_state_run_id").cumcount() + 1
    run_lengths = out.groupby("decision_state_run_id")["date"].transform("size")
    out["decision_state_run_length_days"] = run_lengths.astype(int)
    return out


def state_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_rows = len(frame)
    run_table = (
        frame.loc[:, ["decision_state", "decision_state_run_id", "decision_state_run_length_days"]]
        .drop_duplicates("decision_state_run_id")
        .copy()
    )
    for state, group in frame.groupby("decision_state", sort=True):
        runs = run_table.loc[run_table["decision_state"].eq(state)]
        rows.extend(
            [
                {
                    "summary_type": "state_prevalence",
                    "group": state,
                    "metric": "row_count",
                    "value": float(len(group)),
                },
                {
                    "summary_type": "state_prevalence",
                    "group": state,
                    "metric": "row_share",
                    "value": float(len(group) / total_rows) if total_rows else np.nan,
                },
                {
                    "summary_type": "state_prevalence",
                    "group": state,
                    "metric": "run_count",
                    "value": float(len(runs)),
                },
                {
                    "summary_type": "state_prevalence",
                    "group": state,
                    "metric": "avg_run_length_days",
                    "value": float(pd.to_numeric(runs["decision_state_run_length_days"], errors="coerce").mean()),
                },
                {
                    "summary_type": "state_quality",
                    "group": state,
                    "metric": "buy_zone_5_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_BUY_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "state_quality",
                    "group": state,
                    "metric": "buy_zone_3_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_BUY_STRICT_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "state_quality",
                    "group": state,
                    "metric": "sell_zone_5_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_SELL_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "state_quality",
                    "group": state,
                    "metric": "sell_zone_3_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_SELL_STRICT_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "state_scores",
                    "group": state,
                    "metric": "avg_buy_score",
                    "value": float(pd.to_numeric(group[BUY_SCORE], errors="coerce").mean()),
                },
                {
                    "summary_type": "state_scores",
                    "group": state,
                    "metric": "avg_sell_score",
                    "value": float(pd.to_numeric(group[SELL_SCORE], errors="coerce").mean()),
                },
                {
                    "summary_type": "state_scores",
                    "group": state,
                    "metric": "avg_clarity",
                    "value": float(pd.to_numeric(group[CLARITY], errors="coerce").mean()),
                },
            ]
        )

    for bucket, group in frame.groupby("score_interaction_bucket", sort=True):
        rows.extend(
            [
                {
                    "summary_type": "interaction_bucket",
                    "group": bucket,
                    "metric": "row_count",
                    "value": float(len(group)),
                },
                {
                    "summary_type": "interaction_bucket",
                    "group": bucket,
                    "metric": "buy_zone_5_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_BUY_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "interaction_bucket",
                    "group": bucket,
                    "metric": "sell_zone_5_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_SELL_TARGET], errors="coerce").fillna(0).mean()),
                },
            ]
        )
    return pd.DataFrame(rows)


def summary_value(summary: pd.DataFrame, summary_type: str, group: str, metric: str) -> float:
    matched = summary.loc[
        summary["summary_type"].eq(summary_type)
        & summary["group"].eq(group)
        & summary["metric"].eq(metric)
    ]
    if matched.empty:
        return np.nan
    return float(matched.iloc[0]["value"])


def render_markdown(frame: pd.DataFrame, summary: pd.DataFrame, thresholds: dict[str, float]) -> str:
    state_order = ["BUY_SETUP", "SELL_SETUP", "CONFLICT_OVERLAP", "TRANSITION_UNCLEAR", "NEUTRAL_NO_EDGE"]

    def state_line(state: str) -> str:
        share = summary_value(summary, "state_prevalence", state, "row_share")
        avg_run = summary_value(summary, "state_prevalence", state, "avg_run_length_days")
        buy5 = summary_value(summary, "state_quality", state, "buy_zone_5_rate")
        sell5 = summary_value(summary, "state_quality", state, "sell_zone_5_rate")
        clarity = summary_value(summary, "state_scores", state, "avg_clarity")
        if pd.isna(share):
            return f"- `{state}`: not observed"
        return (
            f"- `{state}`: share `{share:.3f}`, avg run `{avg_run:.2f}` days, "
            f"buy-zone 5% `{buy5:.3f}`, sell-zone 5% `{sell5:.3f}`, clarity `{clarity:.3f}`"
        )

    conflict = frame.loc[frame["decision_state"].eq("CONFLICT_OVERLAP")].copy()
    conflict_live = (
        conflict["live_swing_direction"].astype("object").fillna("unknown").value_counts(normalize=True).to_dict()
        if not conflict.empty
        else {}
    )
    conflict_live_text = ", ".join(f"`{key}` `{value:.3f}`" for key, value in conflict_live.items()) or "n/a"
    state_lines = [state_line(state) for state in state_order]

    buy_setup_buy5 = summary_value(summary, "state_quality", "BUY_SETUP", "buy_zone_5_rate")
    sell_setup_sell5 = summary_value(summary, "state_quality", "SELL_SETUP", "sell_zone_5_rate")
    neutral_buy5 = summary_value(summary, "state_quality", "NEUTRAL_NO_EDGE", "buy_zone_5_rate")
    neutral_sell5 = summary_value(summary, "state_quality", "NEUTRAL_NO_EDGE", "sell_zone_5_rate")

    lines = [
        "# SAFE v4.0 Swing Decision Layer",
        "",
        "## Purpose",
        "",
        "- first structural decision layer on top of the validated swing timing scores",
        "- outputs categorical market/playbook states plus continuous buy/sell support and clarity scores",
        "- no trade rules, execution logic, position sizing, or backtesting are introduced",
        "",
        "## Score References",
        "",
        "- promoted buy score: `buy_hybrid_weighted_balanced_score` from the validated buy-side hybrid pass",
        "- promoted sell score: `sell_fixed_extreme_timing_score`, retained as the strongest sell-side timing reference",
        "- diagnostic sell score retained: `sell_extreme_timing_score`",
        "",
        "## Threshold Calibration",
        "",
        "- thresholds are calibrated from train+validation rows only",
        f"- buy high / moderate: `{thresholds['buy_high']:.3f}` / `{thresholds['buy_moderate']:.3f}`",
        f"- sell high / moderate: `{thresholds['sell_high']:.3f}` / `{thresholds['sell_moderate']:.3f}`",
        f"- directional spread minimum: `{thresholds['spread_min']:.3f}`",
        "",
        "## State Definitions",
        "",
        "- `BUY_SETUP`: buy timing high, sell timing below moderate, and buy score leads by at least the spread threshold",
        "- `SELL_SETUP`: sell timing high, buy timing below moderate, and sell score leads by at least the spread threshold",
        "- `CONFLICT_OVERLAP`: both buy and sell timing are at least moderate",
        "- `NEUTRAL_NO_EDGE`: neither side is moderate",
        "- `TRANSITION_UNCLEAR`: one side is moderate/high but the separation is not clean enough for setup classification",
        "",
        "## Continuous Support Columns",
        "",
        "- `timing_score_spread = promoted_buy_timing_score - promoted_sell_timing_score`",
        "- `timing_score_intensity = max(buy, sell)`",
        "- `timing_score_overlap = min(buy, sell)`",
        "- `buy_dominance_score = buy * (1 - sell)`",
        "- `sell_dominance_score = sell * (1 - buy)`",
        "- `edge_clarity_score = abs(spread) * (0.5 + 0.5 * intensity)`",
        "- `conflict_score = overlap * intensity`",
        "",
        "## State Prevalence And Quality",
        "",
        *state_lines,
        "",
        "## Separation Readout",
        "",
        f"- `BUY_SETUP` buy-zone 5% rate: `{buy_setup_buy5:.3f}` vs `NEUTRAL_NO_EDGE` `{neutral_buy5:.3f}`",
        f"- `SELL_SETUP` sell-zone 5% rate: `{sell_setup_sell5:.3f}` vs `NEUTRAL_NO_EDGE` `{neutral_sell5:.3f}`",
        "- separation should be read structurally: states are intended to clarify timing context, not prove a tradable rule",
        "",
        "## Conflict Analysis",
        "",
        f"- conflict rows: `{len(conflict)}`",
        f"- conflict live-swing direction mix: {conflict_live_text}",
        f"- conflict avg buy score: `{pd.to_numeric(conflict[BUY_SCORE], errors='coerce').mean() if not conflict.empty else np.nan:.3f}`",
        f"- conflict avg sell score: `{pd.to_numeric(conflict[SELL_SCORE], errors='coerce').mean() if not conflict.empty else np.nan:.3f}`",
        "- conflict/overlap should be treated as a mixed timing state, not as a buy or sell trigger",
        "",
        "## Interpretation",
        "",
        "- the layer turns independent timing scores into a compact structural state taxonomy",
        "- the continuous support columns preserve nuance when a hard state label is too coarse",
        "- the next step should validate whether these decision states help organize later playbook logic; it should not jump directly to trade execution",
    ]
    return "\n".join(lines) + "\n"


def build_export(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "close",
        "split",
        "current_confirmed_swing_id",
        "current_confirmed_swing_direction",
        "live_swing_direction",
        "days_since_last_pivot",
        "distance_from_last_pivot_pct",
        "current_swing_age_pct_of_median",
        "current_swing_size_pct_of_median",
        BUY_SCORE,
        SELL_SCORE,
        "sell_extreme_timing_score",
        "buy_fixed_extreme_timing_score",
        "buy_exhaustion_redesign_score",
        "buy_ordinal_ranking_score",
        SPREAD,
        INTENSITY,
        OVERLAP,
        "buy_dominance_score",
        "sell_dominance_score",
        CLARITY,
        "conflict_score",
        "buy_score_band",
        "sell_score_band",
        "score_interaction_bucket",
        "decision_state",
        "decision_state_run_id",
        "decision_state_age_days",
        "decision_state_run_length_days",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
        "dist_to_current_down_swing_low_pct",
        "dist_to_current_up_swing_high_pct",
    ]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Cannot export decision layer; missing columns: {missing}")
    return frame.loc[:, columns].copy()


def main() -> None:
    args = parse_args()
    inputs = load_inputs(args.buy_side_hybrid_scores_csv, args.swing_extreme_timing_csv)
    decision, thresholds = add_decision_columns(inputs)
    summary = state_summary(decision)
    export = build_export(decision)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(out_csv, index=False)

    out_summary = Path(args.out_summary_csv)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_summary, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(export, summary, thresholds), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_summary}")
    print(f"Wrote: {out_md}")
    print(f"Rows written: {len(export)}")


if __name__ == "__main__":
    main()
