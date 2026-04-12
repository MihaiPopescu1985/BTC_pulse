from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_BUY_SIDE_EXPLORATION_SCORES_CSV_PATH,
    DEFAULT_BUY_SIDE_HYBRID_COMPARISON_CSV_PATH,
    DEFAULT_BUY_SIDE_HYBRID_SCORES_CSV_PATH,
    DEFAULT_BUY_SIDE_HYBRID_SWING_SUMMARY_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bottom.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
)
from src.research.v4_iteration.core.swing_bottom.run_swing_extreme_timing import THRESHOLDS, TOP_BUCKETS, clip01


DEFAULT_BUY_SIDE_HYBRID_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_BUY_SIDE_HYBRID.md"
DISTANCE_COLUMN = "dist_to_current_down_swing_low_pct"
SWING_ID_COLUMN = "current_confirmed_swing_id"
SWING_DIRECTION_COLUMN = "current_confirmed_swing_direction"
DOWN_DIRECTION = "down"
HYBRID_FEATURES = [
    "buy_fixed_extreme_timing_score",
    "buy_exhaustion_redesign_score",
    "buy_ordinal_ranking_score",
]
TWO_STAGE_SHORTLIST_FRACTION = 0.40


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the narrow buy-side fixed/exhaustion/ordinal hybrid pass.",
    )
    parser.add_argument(
        "--buy-side-exploration-scores-csv",
        default=str(DEFAULT_BUY_SIDE_EXPLORATION_SCORES_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_exploration_scores.csv",
    )
    parser.add_argument(
        "--out-scores-csv",
        default=str(DEFAULT_BUY_SIDE_HYBRID_SCORES_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_hybrid_scores.csv",
    )
    parser.add_argument(
        "--out-comparison-csv",
        default=str(DEFAULT_BUY_SIDE_HYBRID_COMPARISON_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_hybrid_comparison.csv",
    )
    parser.add_argument(
        "--out-swing-summary-csv",
        default=str(DEFAULT_BUY_SIDE_HYBRID_SWING_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_hybrid_swing_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_BUY_SIDE_HYBRID_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_BUY_SIDE_HYBRID.md",
    )
    return parser.parse_args()


def load_scores(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = [
        "date",
        "close",
        "split",
        SWING_ID_COLUMN,
        SWING_DIRECTION_COLUMN,
        "live_swing_direction",
        "buy_phase_prob",
        "buy_fixed_extreme_timing_score",
        "buy_extreme_timing_score",
        "buy_exhaustion_redesign_score",
        "buy_ordinal_ranking_score",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DISTANCE_COLUMN,
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Buy-side exploration score file is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Buy-side exploration score file contains duplicate dates.")
    frame = frame.sort_values("date").reset_index(drop=True)
    for column in HYBRID_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def build_learned_combo(frame: pd.DataFrame) -> tuple[np.ndarray, dict[str, float]]:
    fit_mask = frame["split"].isin(["train", "validation"])
    fit_frame = frame.loc[fit_mask].copy()
    y = pd.to_numeric(fit_frame[DEFAULT_BUY_TARGET], errors="coerce").astype(int)
    if sorted(y.unique().tolist()) != [0, 1]:
        raise ValueError("Hybrid learned combiner fit target must contain both classes.")

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(class_weight="balanced", max_iter=2000, random_state=0),
            ),
        ]
    )
    model.fit(fit_frame.loc[:, HYBRID_FEATURES], y)
    probabilities = model.predict_proba(frame.loc[:, HYBRID_FEATURES])[:, 1]
    classifier: LogisticRegression = model.named_steps["model"]
    coefficients = {
        feature: float(coef)
        for feature, coef in zip(HYBRID_FEATURES, classifier.coef_.reshape(-1), strict=True)
    }
    return probabilities, coefficients


def add_hybrid_scores(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    scored = frame.copy()
    fixed = pd.to_numeric(scored["buy_fixed_extreme_timing_score"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    exhaustion = pd.to_numeric(scored["buy_exhaustion_redesign_score"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    ordinal = pd.to_numeric(scored["buy_ordinal_ranking_score"], errors="coerce").fillna(0.0).to_numpy(dtype=float)

    scored["buy_hybrid_weighted_balanced_score"] = clip01(0.40 * fixed + 0.30 * exhaustion + 0.30 * ordinal)
    scored["buy_hybrid_rank_local_score"] = clip01(0.25 * fixed + 0.35 * exhaustion + 0.40 * ordinal)
    scored["buy_hybrid_two_stage_score"] = clip01(ordinal * (0.35 + 0.65 * exhaustion))
    scored["buy_hybrid_learned_combo_score"], coefficients = build_learned_combo(scored)
    return scored, coefficients


def score_definitions() -> list[dict[str, object]]:
    return [
        {
            "approach": "baseline_fixed_weight",
            "family": "reference",
            "score_column": "buy_fixed_extreme_timing_score",
            "selection_mode": "score",
        },
        {
            "approach": "approach_b_exhaustion_redesign",
            "family": "reference",
            "score_column": "buy_exhaustion_redesign_score",
            "selection_mode": "score",
        },
        {
            "approach": "approach_c_ordinal_ranking",
            "family": "reference",
            "score_column": "buy_ordinal_ranking_score",
            "selection_mode": "score",
        },
        {
            "approach": "hybrid_weighted_balanced",
            "family": "hybrid",
            "score_column": "buy_hybrid_weighted_balanced_score",
            "selection_mode": "score",
        },
        {
            "approach": "hybrid_rank_local_weighted",
            "family": "hybrid",
            "score_column": "buy_hybrid_rank_local_score",
            "selection_mode": "score",
        },
        {
            "approach": "hybrid_learned_three_score",
            "family": "hybrid",
            "score_column": "buy_hybrid_learned_combo_score",
            "selection_mode": "score",
        },
        {
            "approach": "hybrid_two_stage_shortlist_rerank",
            "family": "hybrid",
            "score_column": "buy_hybrid_two_stage_score",
            "selection_mode": "two_stage",
        },
    ]


def test_down_swing_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[
        frame["split"].eq("test")
        & frame[SWING_DIRECTION_COLUMN].eq(DOWN_DIRECTION)
        & frame[SWING_ID_COLUMN].notna()
    ].copy()


def choose_best_row(swing_frame: pd.DataFrame, definition: dict[str, object]) -> pd.Series | None:
    score_column = str(definition["score_column"])
    selection_mode = str(definition["selection_mode"])
    valid = swing_frame.loc[pd.to_numeric(swing_frame[score_column], errors="coerce").notna()].copy()
    if valid.empty:
        return None
    if selection_mode == "two_stage":
        ordinal_valid = valid.loc[pd.to_numeric(valid["buy_ordinal_ranking_score"], errors="coerce").notna()].copy()
        if ordinal_valid.empty:
            return None
        shortlist_count = max(1, int(np.ceil(len(ordinal_valid) * TWO_STAGE_SHORTLIST_FRACTION)))
        shortlist = ordinal_valid.sort_values(["buy_ordinal_ranking_score", "date"], ascending=[False, True]).head(
            shortlist_count
        )
        return shortlist.sort_values(["buy_exhaustion_redesign_score", "date"], ascending=[False, True]).iloc[0]
    return valid.sort_values([score_column, "date"], ascending=[False, True]).iloc[0]


def build_per_swing_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    down_rows = test_down_swing_rows(frame)
    if down_rows.empty:
        raise ValueError("No confirmed down swings are present in the test split.")

    for definition in score_definitions():
        for swing_id, swing_frame in down_rows.groupby(SWING_ID_COLUMN, sort=True):
            best = choose_best_row(swing_frame, definition)
            if best is None:
                rows.append(
                    {
                        "approach": definition["approach"],
                        "family": definition["family"],
                        "selection_mode": definition["selection_mode"],
                        "current_confirmed_swing_id": swing_id,
                        "valid_signal": 0,
                        "best_date": None,
                        "best_score": np.nan,
                        "best_distance": np.nan,
                        "best_within_5pct": np.nan,
                        "best_within_3pct": np.nan,
                        "swing_row_count": len(swing_frame),
                    }
                )
                continue
            rows.append(
                {
                    "approach": definition["approach"],
                    "family": definition["family"],
                    "selection_mode": definition["selection_mode"],
                    "current_confirmed_swing_id": swing_id,
                    "valid_signal": 1,
                    "best_date": pd.to_datetime(best["date"]).strftime("%Y-%m-%d"),
                    "best_score": float(best[str(definition["score_column"])]),
                    "best_distance": float(best[DISTANCE_COLUMN]),
                    "best_within_5pct": int(best[DEFAULT_BUY_TARGET]),
                    "best_within_3pct": int(best[DEFAULT_BUY_STRICT_TARGET]),
                    "swing_row_count": len(swing_frame),
                }
            )
    return pd.DataFrame(rows)


def add_comparison_row(
    rows: list[dict[str, object]],
    *,
    row_type: str,
    approach: str,
    family: str,
    bucket: str,
    metric: str,
    value: float,
) -> None:
    rows.append(
        {
            "row_type": row_type,
            "approach": approach,
            "family": family,
            "split": "test",
            "bucket": bucket,
            "metric": metric,
            "value": value,
        }
    )


def build_comparison_table(frame: pd.DataFrame, per_swing: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    test = frame.loc[frame["split"].eq("test")].copy()
    down_rows = test_down_swing_rows(frame)
    total_swings = int(down_rows[SWING_ID_COLUMN].nunique())

    for definition in score_definitions():
        approach = str(definition["approach"])
        family = str(definition["family"])
        score_column = str(definition["score_column"])
        swing_group = per_swing.loc[per_swing["approach"].eq(approach)].copy()
        valid = swing_group.loc[swing_group["valid_signal"].eq(1)].copy()
        for metric, value in (
            ("swing_count", float(len(swing_group))),
            ("coverage_rate", float(len(valid) / len(swing_group)) if len(swing_group) else np.nan),
            ("avg_best_distance", pd.to_numeric(valid["best_distance"], errors="coerce").mean()),
            ("median_best_distance", pd.to_numeric(valid["best_distance"], errors="coerce").median()),
            ("zone_5_hit_rate", pd.to_numeric(valid["best_within_5pct"], errors="coerce").mean()),
            ("zone_3_hit_rate", pd.to_numeric(valid["best_within_3pct"], errors="coerce").mean()),
        ):
            add_comparison_row(
                rows,
                row_type="best_per_swing",
                approach=approach,
                family=family,
                bucket="all_test_down_swings",
                metric=metric,
                value=float(value) if pd.notna(value) else np.nan,
            )

        ordered = test.sort_values(score_column, ascending=False).reset_index(drop=True)
        for bucket in TOP_BUCKETS:
            selected = ordered.iloc[: max(1, int(np.ceil(len(ordered) * bucket)))].copy()
            swing_mask = selected[SWING_DIRECTION_COLUMN].eq(DOWN_DIRECTION) & selected[SWING_ID_COLUMN].notna()
            for metric, value in (
                ("row_count", float(len(selected))),
                ("zone_5_hit_rate", pd.to_numeric(selected[DEFAULT_BUY_TARGET], errors="coerce").fillna(0).mean()),
                ("zone_3_hit_rate", pd.to_numeric(selected[DEFAULT_BUY_STRICT_TARGET], errors="coerce").fillna(0).mean()),
                ("avg_distance", pd.to_numeric(selected[DISTANCE_COLUMN], errors="coerce").dropna().mean()),
                ("unique_swings_touched", float(selected.loc[swing_mask, SWING_ID_COLUMN].nunique())),
            ):
                add_comparison_row(
                    rows,
                    row_type="top_bucket",
                    approach=approach,
                    family=family,
                    bucket=f"top_{int(bucket * 100)}pct",
                    metric=metric,
                    value=float(value) if pd.notna(value) else np.nan,
                )

        side_scores = pd.to_numeric(down_rows[score_column], errors="coerce")
        for threshold in THRESHOLDS:
            selected = down_rows.loc[side_scores >= threshold].copy()
            swings_touched = int(selected[SWING_ID_COLUMN].nunique())
            for metric, value in (
                ("row_count", float(len(selected))),
                ("swing_count", float(total_swings)),
                ("swings_touched", float(swings_touched)),
                ("coverage_rate", float(swings_touched / total_swings) if total_swings else np.nan),
                (
                    "zone_5_hit_rate",
                    pd.to_numeric(selected[DEFAULT_BUY_TARGET], errors="coerce").fillna(0).mean()
                    if not selected.empty
                    else np.nan,
                ),
                (
                    "zone_3_hit_rate",
                    pd.to_numeric(selected[DEFAULT_BUY_STRICT_TARGET], errors="coerce").fillna(0).mean()
                    if not selected.empty
                    else np.nan,
                ),
                (
                    "avg_distance",
                    pd.to_numeric(selected[DISTANCE_COLUMN], errors="coerce").dropna().mean()
                    if not selected.empty
                    else np.nan,
                ),
            ):
                add_comparison_row(
                    rows,
                    row_type="threshold",
                    approach=approach,
                    family=family,
                    bucket=f"threshold_{threshold:.2f}",
                    metric=metric,
                    value=float(value) if pd.notna(value) else np.nan,
                )
    return pd.DataFrame(rows)


def metric_lookup(comparison: pd.DataFrame, approach: str, row_type: str, bucket: str, metric: str) -> float:
    matched = comparison.loc[
        comparison["approach"].eq(approach)
        & comparison["row_type"].eq(row_type)
        & comparison["bucket"].eq(bucket)
        & comparison["metric"].eq(metric)
    ]
    if matched.empty:
        return np.nan
    return float(matched.iloc[0]["value"])


def best_hybrid(comparison: pd.DataFrame) -> str:
    rows = comparison.loc[
        comparison["row_type"].eq("best_per_swing")
        & comparison["bucket"].eq("all_test_down_swings")
        & comparison["metric"].eq("avg_best_distance")
        & comparison["family"].eq("hybrid")
    ].copy()
    if rows.empty:
        return ""
    return str(rows.sort_values("value", ascending=True).iloc[0]["approach"])


def make_recommendation(comparison: pd.DataFrame) -> tuple[str, list[str]]:
    candidate = best_hybrid(comparison)
    if not candidate:
        return "Pause / likely dead end", ["No hybrid candidate was available for evaluation."]

    fixed_distance = metric_lookup(
        comparison,
        "baseline_fixed_weight",
        "best_per_swing",
        "all_test_down_swings",
        "avg_best_distance",
    )
    fixed_zone5 = metric_lookup(
        comparison,
        "baseline_fixed_weight",
        "best_per_swing",
        "all_test_down_swings",
        "zone_5_hit_rate",
    )
    fixed_zone3 = metric_lookup(
        comparison,
        "baseline_fixed_weight",
        "best_per_swing",
        "all_test_down_swings",
        "zone_3_hit_rate",
    )
    fixed_top10_zone5 = metric_lookup(comparison, "baseline_fixed_weight", "top_bucket", "top_10pct", "zone_5_hit_rate")
    fixed_top10_distance = metric_lookup(comparison, "baseline_fixed_weight", "top_bucket", "top_10pct", "avg_distance")

    candidate_distance = metric_lookup(
        comparison,
        candidate,
        "best_per_swing",
        "all_test_down_swings",
        "avg_best_distance",
    )
    candidate_zone5 = metric_lookup(
        comparison,
        candidate,
        "best_per_swing",
        "all_test_down_swings",
        "zone_5_hit_rate",
    )
    candidate_zone3 = metric_lookup(
        comparison,
        candidate,
        "best_per_swing",
        "all_test_down_swings",
        "zone_3_hit_rate",
    )
    candidate_top10_zone5 = metric_lookup(comparison, candidate, "top_bucket", "top_10pct", "zone_5_hit_rate")
    candidate_top10_distance = metric_lookup(comparison, candidate, "top_bucket", "top_10pct", "avg_distance")

    distance_gain = fixed_distance - candidate_distance
    zone5_gain = candidate_zone5 - fixed_zone5
    zone3_gain = candidate_zone3 - fixed_zone3
    top10_zone5_gain = candidate_top10_zone5 - fixed_top10_zone5
    top10_distance_gain = fixed_top10_distance - candidate_top10_distance

    notes = [
        f"Best hybrid: `{candidate}`.",
        f"Best-pick avg distance `{candidate_distance:.3f}` vs fixed baseline `{fixed_distance:.3f}` "
        f"({distance_gain:+.3f} improvement).",
        f"Best-pick 5% / 3% changes vs fixed baseline: `{zone5_gain:+.3f}` / `{zone3_gain:+.3f}`.",
        f"Top-decile 5% hit change vs fixed baseline: `{top10_zone5_gain:+.3f}`.",
        f"Top-decile avg distance change vs fixed baseline: `{top10_distance_gain:+.3f}`.",
    ]

    if distance_gain >= 0.008 and zone5_gain >= 0.03 and zone3_gain >= 0.03 and top10_zone5_gain >= 0.03:
        return "Continue", notes
    if distance_gain > 0.0 or zone5_gain > 0.0 or zone3_gain > 0.0 or top10_zone5_gain > 0.0:
        return "Continue cautiously", notes
    return "Pause / likely dead end", notes


def render_markdown(frame: pd.DataFrame, comparison: pd.DataFrame, coefficients: dict[str, float]) -> str:
    decision, notes = make_recommendation(comparison)
    test = frame.loc[frame["split"].eq("test")].copy()
    down_swing_count = int(
        test.loc[test[SWING_DIRECTION_COLUMN].eq(DOWN_DIRECTION) & test[SWING_ID_COLUMN].notna(), SWING_ID_COLUMN].nunique()
    )

    def best_line(approach: str) -> str:
        avg_distance = metric_lookup(comparison, approach, "best_per_swing", "all_test_down_swings", "avg_best_distance")
        median_distance = metric_lookup(
            comparison, approach, "best_per_swing", "all_test_down_swings", "median_best_distance"
        )
        zone5 = metric_lookup(comparison, approach, "best_per_swing", "all_test_down_swings", "zone_5_hit_rate")
        zone3 = metric_lookup(comparison, approach, "best_per_swing", "all_test_down_swings", "zone_3_hit_rate")
        return (
            f"- `{approach}`: avg / median distance `{avg_distance:.3f}` / `{median_distance:.3f}`, "
            f"within 5% / 3% `{zone5:.3f}` / `{zone3:.3f}`"
        )

    def top10_line(approach: str) -> str:
        zone5 = metric_lookup(comparison, approach, "top_bucket", "top_10pct", "zone_5_hit_rate")
        zone3 = metric_lookup(comparison, approach, "top_bucket", "top_10pct", "zone_3_hit_rate")
        avg_distance = metric_lookup(comparison, approach, "top_bucket", "top_10pct", "avg_distance")
        swings = metric_lookup(comparison, approach, "top_bucket", "top_10pct", "unique_swings_touched")
        return (
            f"- `{approach}`: hit 5% / 3% `{zone5:.3f}` / `{zone3:.3f}`, "
            f"avg distance `{avg_distance:.3f}`, swings touched `{swings:.0f}`"
        )

    ranked = (
        comparison.loc[
            comparison["row_type"].eq("best_per_swing")
            & comparison["bucket"].eq("all_test_down_swings")
            & comparison["metric"].eq("avg_best_distance")
        ]
        .sort_values("value", ascending=True)
        .loc[:, ["approach", "value"]]
    )
    ranked_lines = [f"- `{row.approach}`: avg best distance `{row.value:.3f}`" for row in ranked.itertuples(index=False)]
    coefficient_text = ", ".join(f"`{feature}` `{value:.3f}`" for feature, value in coefficients.items())

    lines = [
        "# SAFE v4.0 Buy-Side Narrow Hybrid Pass",
        "",
        "## Purpose",
        "",
        "- narrow follow-up pass using only the fixed baseline, redesigned exhaustion, and ordinal ranking scores",
        "- no new indicator families, trade rules, execution logic, capital management, or backtesting are introduced",
        "- objective: decide whether a simple hybrid materially improves buy-side swing-low timing",
        "",
        "## Inputs And Split",
        "",
        "- source score file: `out/swing_bottom/buy_side_exploration_scores.csv`",
        f"- test down swings evaluated: `{down_swing_count}`",
        f"- test date range: `{pd.to_datetime(test['date']).min().date()}` to `{pd.to_datetime(test['date']).max().date()}`",
        "",
        "## References",
        "",
        "- `baseline_fixed_weight`: current fixed phase/analog/exhaustion reference",
        "- `approach_b_exhaustion_redesign`: best local best-pick selector from sprint",
        "- `approach_c_ordinal_ranking`: best global top-decile ranker from sprint",
        "",
        "## Hybrid Candidates",
        "",
        "- `hybrid_weighted_balanced`: `0.40 fixed + 0.30 exhaustion + 0.30 ordinal`",
        "- `hybrid_rank_local_weighted`: `0.25 fixed + 0.35 exhaustion + 0.40 ordinal`",
        "- `hybrid_learned_three_score`: logistic combiner trained on train+validation using only the three reference scores",
        f"- learned-combiner coefficients: {coefficient_text}",
        "- `hybrid_two_stage_shortlist_rerank`: ordinal shortlists the top 40% of rows inside each test down swing, then exhaustion picks the local best row",
        "- two-stage shortlist/rerank is a swing-level diagnostic; the exported date-aligned two-stage score is still causal and does not use confirmed swing membership",
        "",
        "## Primary Swing-Level Best-Pick Results",
        "",
        best_line("baseline_fixed_weight"),
        best_line("approach_b_exhaustion_redesign"),
        best_line("approach_c_ordinal_ranking"),
        best_line("hybrid_weighted_balanced"),
        best_line("hybrid_rank_local_weighted"),
        best_line("hybrid_learned_three_score"),
        best_line("hybrid_two_stage_shortlist_rerank"),
        "",
        "## Ranking By Average Best-Picked Distance",
        "",
        *ranked_lines,
        "",
        "## Top-Decile Quality",
        "",
        top10_line("baseline_fixed_weight"),
        top10_line("approach_b_exhaustion_redesign"),
        top10_line("approach_c_ordinal_ranking"),
        top10_line("hybrid_weighted_balanced"),
        top10_line("hybrid_rank_local_weighted"),
        top10_line("hybrid_learned_three_score"),
        top10_line("hybrid_two_stage_shortlist_rerank"),
        "",
        "## Decision",
        "",
        f"- recommendation: **{decision}**",
        *[f"- {note}" for note in notes],
        "",
        "## Interpretation",
        "",
        "- the hybrid result directly tests whether buy-side timing needs both global ranking and local bottom refinement",
        "- a useful hybrid must beat the fixed baseline on best-pick proximity without giving back top-decile quality",
        "- if this pass failed, the current buy-side framing would be near a practical dead end; if it succeeds, the next step should be validation rather than another broad idea sprint",
    ]
    return "\n".join(lines) + "\n"


def build_export(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "close",
        "split",
        SWING_ID_COLUMN,
        SWING_DIRECTION_COLUMN,
        "live_swing_direction",
        "days_since_last_pivot",
        "distance_from_last_pivot_pct",
        "current_swing_age_pct_of_median",
        "current_swing_size_pct_of_median",
        "buy_fixed_extreme_timing_score",
        "buy_exhaustion_redesign_score",
        "buy_ordinal_ranking_score",
        "buy_hybrid_weighted_balanced_score",
        "buy_hybrid_rank_local_score",
        "buy_hybrid_learned_combo_score",
        "buy_hybrid_two_stage_score",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DISTANCE_COLUMN,
    ]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Cannot export buy-side hybrid scores; missing columns: {missing}")
    return frame.loc[:, columns].copy()


def main() -> None:
    args = parse_args()
    source = load_scores(args.buy_side_exploration_scores_csv)
    scored, coefficients = add_hybrid_scores(source)
    per_swing = build_per_swing_summary(scored)
    comparison = build_comparison_table(scored, per_swing)
    export = build_export(scored)

    out_scores = Path(args.out_scores_csv)
    out_scores.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(out_scores, index=False)

    out_comparison = Path(args.out_comparison_csv)
    out_comparison.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(out_comparison, index=False)

    out_swing = Path(args.out_swing_summary_csv)
    out_swing.parent.mkdir(parents=True, exist_ok=True)
    per_swing.to_csv(out_swing, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(scored, comparison, coefficients), encoding="utf-8")

    print(f"Wrote: {out_scores}")
    print(f"Wrote: {out_comparison}")
    print(f"Wrote: {out_swing}")
    print(f"Wrote: {out_md}")
    print(f"Rows written: {len(export)}")
    print(f"Test rows: {int((export['split'] == 'test').sum())}")


if __name__ == "__main__":
    main()
