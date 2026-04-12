from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_BUY_SIDE_HYBRID_SCORES_CSV_PATH,
    DEFAULT_BUY_SIDE_HYBRID_VALIDATION_CSV_PATH,
    DEFAULT_BUY_SIDE_HYBRID_VALIDATION_DETAIL_CSV_PATH,
    DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bottom.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
)
from src.research.v4_iteration.core.swing_bottom.run_swing_extreme_timing import THRESHOLDS, TOP_BUCKETS, clip01


DEFAULT_BUY_SIDE_HYBRID_VALIDATION_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_BUY_SIDE_HYBRID_VALIDATION.md"
)
DISTANCE_COLUMN = "dist_to_current_down_swing_low_pct"
SWING_ID_COLUMN = "current_confirmed_swing_id"
SWING_DIRECTION_COLUMN = "current_confirmed_swing_direction"
DOWN_DIRECTION = "down"
REFERENCE_SCORE = "buy_fixed_extreme_timing_score"
HYBRID_SCORE = "buy_hybrid_weighted_balanced_score"
TWO_STAGE_SCORE = "buy_hybrid_two_stage_score"
ORDINAL_SCORE = "buy_ordinal_ranking_score"
EXHAUSTION_SCORE = "buy_exhaustion_redesign_score"
WEIGHT_VARIANTS: dict[str, tuple[float, float, float]] = {
    "weights_40_30_30": (0.40, 0.30, 0.30),
    "weights_45_25_30": (0.45, 0.25, 0.30),
    "weights_35_35_30": (0.35, 0.35, 0.30),
    "weights_40_25_35": (0.40, 0.25, 0.35),
    "weights_35_30_35": (0.35, 0.30, 0.35),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the buy-side hybrid timing candidate.")
    parser.add_argument(
        "--buy-side-hybrid-scores-csv",
        default=str(DEFAULT_BUY_SIDE_HYBRID_SCORES_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_hybrid_scores.csv",
    )
    parser.add_argument(
        "--reversal-zone-dataset-csv",
        default=str(DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_dataset.csv",
    )
    parser.add_argument(
        "--out-validation-csv",
        default=str(DEFAULT_BUY_SIDE_HYBRID_VALIDATION_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_hybrid_validation.csv",
    )
    parser.add_argument(
        "--out-detail-csv",
        default=str(DEFAULT_BUY_SIDE_HYBRID_VALIDATION_DETAIL_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_hybrid_validation_detail.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_BUY_SIDE_HYBRID_VALIDATION_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_BUY_SIDE_HYBRID_VALIDATION.md",
    )
    return parser.parse_args()


def load_inputs(hybrid_scores_path: str | Path, reversal_dataset_path: str | Path) -> pd.DataFrame:
    scores = pd.read_csv(hybrid_scores_path).sort_values("date").reset_index(drop=True)
    required_scores = [
        "date",
        "close",
        "split",
        SWING_ID_COLUMN,
        SWING_DIRECTION_COLUMN,
        "live_swing_direction",
        REFERENCE_SCORE,
        HYBRID_SCORE,
        TWO_STAGE_SCORE,
        ORDINAL_SCORE,
        EXHAUSTION_SCORE,
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DISTANCE_COLUMN,
    ]
    missing = [column for column in required_scores if column not in scores.columns]
    if missing:
        raise ValueError(f"Hybrid scores file is missing required columns: {missing}")
    if scores["date"].duplicated().any():
        raise ValueError("Hybrid scores contain duplicate dates.")

    regime_columns = [
        "date",
        "atr_pct",
        "ewma_vol",
        "TS_50",
        "TS_200",
        "P_SHOCK_HMM",
        "P_CORE_HMM",
        "HMM_LABEL",
    ]
    dataset = pd.read_csv(reversal_dataset_path, usecols=lambda col: col in regime_columns)
    missing_regime = [column for column in regime_columns if column not in dataset.columns]
    if missing_regime:
        raise ValueError(f"Reversal dataset is missing regime columns: {missing_regime}")
    merged = scores.merge(dataset, on="date", how="left", validate="one_to_one")
    if len(merged) != len(scores):
        raise ValueError("Regime merge changed the number of score rows.")
    return merged


def add_weight_variants(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    fixed = pd.to_numeric(out[REFERENCE_SCORE], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    exhaustion = pd.to_numeric(out[EXHAUSTION_SCORE], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    ordinal = pd.to_numeric(out[ORDINAL_SCORE], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    for name, (fixed_weight, exhaustion_weight, ordinal_weight) in WEIGHT_VARIANTS.items():
        out[f"buy_hybrid_{name}_score"] = clip01(
            fixed_weight * fixed + exhaustion_weight * exhaustion + ordinal_weight * ordinal
        )
    return out


def score_definitions() -> list[dict[str, object]]:
    definitions: list[dict[str, object]] = [
        {
            "approach": "baseline_fixed_weight",
            "family": "reference",
            "score_column": REFERENCE_SCORE,
            "selection_mode": "score",
        },
        {
            "approach": "hybrid_weighted_balanced",
            "family": "candidate",
            "score_column": HYBRID_SCORE,
            "selection_mode": "score",
        },
        {
            "approach": "hybrid_two_stage_shortlist_rerank",
            "family": "diagnostic",
            "score_column": TWO_STAGE_SCORE,
            "selection_mode": "two_stage",
        },
        {
            "approach": "approach_c_ordinal_ranking",
            "family": "reference_optional",
            "score_column": ORDINAL_SCORE,
            "selection_mode": "score",
        },
    ]
    for variant in WEIGHT_VARIANTS:
        definitions.append(
            {
                "approach": variant,
                "family": "weight_sensitivity",
                "score_column": f"buy_hybrid_{variant}_score",
                "selection_mode": "score",
            }
        )
    return definitions


def subset_definitions(frame: pd.DataFrame) -> list[tuple[str, pd.Series]]:
    test = frame["split"].eq("test")
    test_idx = np.flatnonzero(test.to_numpy())
    if test_idx.size < 3:
        raise ValueError("Test split is too small for validation subsets.")
    thirds = np.array_split(test_idx, 3)

    atr = pd.to_numeric(frame["atr_pct"], errors="coerce")
    ts50 = pd.to_numeric(frame["TS_50"], errors="coerce")
    shock = pd.to_numeric(frame["P_SHOCK_HMM"], errors="coerce")
    high_vol_cut = float(atr.loc[test].median())
    shock_cut = float(shock.loc[test].median())

    subsets: list[tuple[str, pd.Series]] = [
        ("full_test", test),
        ("test_early_third", pd.Series(frame.index.isin(thirds[0]), index=frame.index)),
        ("test_middle_third", pd.Series(frame.index.isin(thirds[1]), index=frame.index)),
        ("test_late_third", pd.Series(frame.index.isin(thirds[2]), index=frame.index)),
        ("regime_high_vol", test & atr.ge(high_vol_cut)),
        ("regime_low_vol", test & atr.lt(high_vol_cut)),
        ("regime_ts50_positive", test & ts50.ge(0.0)),
        ("regime_ts50_negative", test & ts50.lt(0.0)),
        ("regime_high_shock", test & shock.ge(shock_cut)),
        ("regime_low_shock", test & shock.lt(shock_cut)),
    ]
    return subsets


def down_rows(frame: pd.DataFrame, subset_mask: pd.Series) -> pd.DataFrame:
    return frame.loc[
        subset_mask
        & frame[SWING_DIRECTION_COLUMN].eq(DOWN_DIRECTION)
        & frame[SWING_ID_COLUMN].notna()
    ].copy()


def choose_best_row(swing_frame: pd.DataFrame, definition: dict[str, object]) -> pd.Series | None:
    score_column = str(definition["score_column"])
    valid = swing_frame.loc[pd.to_numeric(swing_frame[score_column], errors="coerce").notna()].copy()
    if valid.empty:
        return None
    if definition["selection_mode"] == "two_stage":
        ordinal_valid = valid.loc[pd.to_numeric(valid[ORDINAL_SCORE], errors="coerce").notna()].copy()
        if ordinal_valid.empty:
            return None
        shortlist_count = max(1, int(np.ceil(len(ordinal_valid) * 0.40)))
        shortlist = ordinal_valid.sort_values([ORDINAL_SCORE, "date"], ascending=[False, True]).head(shortlist_count)
        return shortlist.sort_values([EXHAUSTION_SCORE, "date"], ascending=[False, True]).iloc[0]
    return valid.sort_values([score_column, "date"], ascending=[False, True]).iloc[0]


def add_detail_row(
    rows: list[dict[str, object]],
    *,
    validation_type: str,
    setting: str,
    approach: str,
    family: str,
    row_type: str,
    bucket: str,
    metric: str,
    value: float,
) -> None:
    rows.append(
        {
            "validation_type": validation_type,
            "setting": setting,
            "approach": approach,
            "family": family,
            "row_type": row_type,
            "bucket": bucket,
            "metric": metric,
            "value": value,
        }
    )


def evaluate_subset(
    frame: pd.DataFrame,
    subset_name: str,
    subset_mask: pd.Series,
    definitions: list[dict[str, object]],
    validation_type: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    subset = frame.loc[subset_mask].copy()
    side_rows = down_rows(frame, subset_mask)
    if subset.empty or side_rows.empty:
        return rows

    total_swings = int(side_rows[SWING_ID_COLUMN].nunique())
    for definition in definitions:
        approach = str(definition["approach"])
        family = str(definition["family"])
        score_column = str(definition["score_column"])
        best_rows: list[pd.Series] = []
        for _swing_id, swing_frame in side_rows.groupby(SWING_ID_COLUMN, sort=True):
            best = choose_best_row(swing_frame, definition)
            if best is not None:
                best_rows.append(best)
        best_frame = pd.DataFrame(best_rows)
        for metric, value in (
            ("swing_count", float(total_swings)),
            ("coverage_rate", float(len(best_frame) / total_swings) if total_swings else np.nan),
            ("avg_best_distance", pd.to_numeric(best_frame[DISTANCE_COLUMN], errors="coerce").mean()),
            ("median_best_distance", pd.to_numeric(best_frame[DISTANCE_COLUMN], errors="coerce").median()),
            ("zone_5_hit_rate", pd.to_numeric(best_frame[DEFAULT_BUY_TARGET], errors="coerce").mean()),
            ("zone_3_hit_rate", pd.to_numeric(best_frame[DEFAULT_BUY_STRICT_TARGET], errors="coerce").mean()),
        ):
            add_detail_row(
                rows,
                validation_type=validation_type,
                setting=subset_name,
                approach=approach,
                family=family,
                row_type="best_per_swing",
                bucket="all_down_swings",
                metric=metric,
                value=float(value) if pd.notna(value) else np.nan,
            )

        ordered = subset.sort_values(score_column, ascending=False).reset_index(drop=True)
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
                add_detail_row(
                    rows,
                    validation_type=validation_type,
                    setting=subset_name,
                    approach=approach,
                    family=family,
                    row_type="top_bucket",
                    bucket=f"top_{int(bucket * 100)}pct",
                    metric=metric,
                    value=float(value) if pd.notna(value) else np.nan,
                )

        side_scores = pd.to_numeric(side_rows[score_column], errors="coerce")
        for threshold in THRESHOLDS:
            selected = side_rows.loc[side_scores >= threshold].copy()
            swings_touched = int(selected[SWING_ID_COLUMN].nunique())
            for metric, value in (
                ("row_count", float(len(selected))),
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
                add_detail_row(
                    rows,
                    validation_type=validation_type,
                    setting=subset_name,
                    approach=approach,
                    family=family,
                    row_type="threshold",
                    bucket=f"threshold_{threshold:.2f}",
                    metric=metric,
                    value=float(value) if pd.notna(value) else np.nan,
                )
    return rows


def metric_value(
    detail: pd.DataFrame,
    *,
    validation_type: str,
    setting: str,
    approach: str,
    row_type: str,
    bucket: str,
    metric: str,
) -> float:
    matched = detail.loc[
        detail["validation_type"].eq(validation_type)
        & detail["setting"].eq(setting)
        & detail["approach"].eq(approach)
        & detail["row_type"].eq(row_type)
        & detail["bucket"].eq(bucket)
        & detail["metric"].eq(metric)
    ]
    if matched.empty:
        return np.nan
    return float(matched.iloc[0]["value"])


def build_validation_summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    candidate = "hybrid_weighted_balanced"
    baseline = "baseline_fixed_weight"
    settings = detail.loc[
        detail["approach"].isin([candidate, baseline])
        & detail["row_type"].eq("best_per_swing")
        & detail["metric"].eq("swing_count")
    ][["validation_type", "setting"]].drop_duplicates()

    for row in settings.itertuples(index=False):
        validation_type = str(row.validation_type)
        setting = str(row.setting)
        swing_count = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=baseline,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric="swing_count",
        )
        if pd.isna(swing_count) or swing_count < 3:
            continue
        baseline_distance = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=baseline,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric="avg_best_distance",
        )
        hybrid_distance = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=candidate,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric="avg_best_distance",
        )
        baseline_zone5 = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=baseline,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric="zone_5_hit_rate",
        )
        hybrid_zone5 = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=candidate,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric="zone_5_hit_rate",
        )
        baseline_zone3 = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=baseline,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric="zone_3_hit_rate",
        )
        hybrid_zone3 = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=candidate,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric="zone_3_hit_rate",
        )
        baseline_top10 = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=baseline,
            row_type="top_bucket",
            bucket="top_10pct",
            metric="zone_5_hit_rate",
        )
        hybrid_top10 = metric_value(
            detail,
            validation_type=validation_type,
            setting=setting,
            approach=candidate,
            row_type="top_bucket",
            bucket="top_10pct",
            metric="zone_5_hit_rate",
        )
        rows.append(
            {
                "validation_type": validation_type,
                "setting": setting,
                "swing_count": swing_count,
                "avg_distance_delta": baseline_distance - hybrid_distance,
                "zone_5_delta": hybrid_zone5 - baseline_zone5,
                "zone_3_delta": hybrid_zone3 - baseline_zone3,
                "top10_zone_5_delta": hybrid_top10 - baseline_top10,
                "distance_winner": "hybrid" if hybrid_distance < baseline_distance else "baseline",
                "zone5_winner": "hybrid" if hybrid_zone5 > baseline_zone5 else ("tie" if hybrid_zone5 == baseline_zone5 else "baseline"),
                "zone3_winner": "hybrid" if hybrid_zone3 > baseline_zone3 else ("tie" if hybrid_zone3 == baseline_zone3 else "baseline"),
                "top10_zone5_winner": "hybrid"
                if hybrid_top10 > baseline_top10
                else ("tie" if hybrid_top10 == baseline_top10 else "baseline"),
            }
        )
    return pd.DataFrame(rows)


def make_decision(summary: pd.DataFrame) -> tuple[str, list[str]]:
    if summary.empty:
        return "Do not promote hybrid", ["No validation settings were available."]
    distance_win_rate = float(summary["distance_winner"].eq("hybrid").mean())
    zone5_non_loss_rate = float(summary["zone5_winner"].isin(["hybrid", "tie"]).mean())
    zone3_non_loss_rate = float(summary["zone3_winner"].isin(["hybrid", "tie"]).mean())
    top10_non_loss_rate = float(summary["top10_zone5_winner"].isin(["hybrid", "tie"]).mean())
    core = summary.loc[summary["validation_type"].isin(["time_split", "regime", "full"])]
    core_distance_win_rate = float(core["distance_winner"].eq("hybrid").mean()) if not core.empty else np.nan
    notes = [
        f"Hybrid distance win rate across validation settings: `{distance_win_rate:.3f}`.",
        f"Hybrid 5% best-pick non-loss rate: `{zone5_non_loss_rate:.3f}`.",
        f"Hybrid 3% best-pick non-loss rate: `{zone3_non_loss_rate:.3f}`.",
        f"Hybrid top-decile 5% non-loss rate: `{top10_non_loss_rate:.3f}`.",
        f"Core full/time/regime distance win rate: `{core_distance_win_rate:.3f}`.",
    ]
    if (
        distance_win_rate >= 0.75
        and zone5_non_loss_rate >= 0.65
        and top10_non_loss_rate >= 0.65
        and core_distance_win_rate >= 0.70
    ):
        return "Promote hybrid", notes
    if distance_win_rate >= 0.55 and (zone5_non_loss_rate >= 0.50 or top10_non_loss_rate >= 0.50):
        return "Keep hybrid as candidate, not reference", notes
    return "Do not promote hybrid", notes


def render_markdown(detail: pd.DataFrame, summary: pd.DataFrame) -> str:
    decision, notes = make_decision(summary)

    def full_metric(approach: str, metric: str) -> str:
        value = metric_value(
            detail,
            validation_type="full",
            setting="full_test",
            approach=approach,
            row_type="best_per_swing",
            bucket="all_down_swings",
            metric=metric,
        )
        return "n/a" if pd.isna(value) else f"{value:.3f}"

    def top10_metric(approach: str, metric: str) -> str:
        value = metric_value(
            detail,
            validation_type="full",
            setting="full_test",
            approach=approach,
            row_type="top_bucket",
            bucket="top_10pct",
            metric=metric,
        )
        return "n/a" if pd.isna(value) else f"{value:.3f}"

    validation_counts = summary.groupby("validation_type").size().to_dict() if not summary.empty else {}
    counts_text = ", ".join(f"`{key}` `{value}`" for key, value in validation_counts.items())
    strongest = summary.sort_values("avg_distance_delta", ascending=False).head(5)
    weakest = summary.sort_values("avg_distance_delta", ascending=True).head(5)

    lines = [
        "# SAFE v4.0 Buy-Side Hybrid Validation",
        "",
        "## Purpose",
        "",
        "- validate whether `hybrid_weighted_balanced` is stable enough to replace `baseline_fixed_weight` as the buy-side reference",
        "- no new ideas, trade rules, execution logic, capital management, or backtesting are introduced",
        "",
        "## Validation Dimensions",
        "",
        "- parameter sensitivity: nearby fixed/exhaustion/ordinal weights around `0.40 / 0.30 / 0.30`",
        "- time-split robustness: early, middle, and late thirds of the held-out test period",
        "- regime robustness: high/low volatility, TS_50 positive/negative, and high/low shock probability subsets",
        "- threshold stability: retained in the detailed CSV for standard score cutoffs",
        f"- validation setting counts: {counts_text}",
        "",
        "## Full-Test Reference",
        "",
        f"- fixed baseline avg / median best distance: `{full_metric('baseline_fixed_weight', 'avg_best_distance')}` / `{full_metric('baseline_fixed_weight', 'median_best_distance')}`",
        f"- hybrid avg / median best distance: `{full_metric('hybrid_weighted_balanced', 'avg_best_distance')}` / `{full_metric('hybrid_weighted_balanced', 'median_best_distance')}`",
        f"- fixed baseline best-pick within 5% / 3%: `{full_metric('baseline_fixed_weight', 'zone_5_hit_rate')}` / `{full_metric('baseline_fixed_weight', 'zone_3_hit_rate')}`",
        f"- hybrid best-pick within 5% / 3%: `{full_metric('hybrid_weighted_balanced', 'zone_5_hit_rate')}` / `{full_metric('hybrid_weighted_balanced', 'zone_3_hit_rate')}`",
        f"- fixed baseline top-decile 5% / 3%: `{top10_metric('baseline_fixed_weight', 'zone_5_hit_rate')}` / `{top10_metric('baseline_fixed_weight', 'zone_3_hit_rate')}`",
        f"- hybrid top-decile 5% / 3%: `{top10_metric('hybrid_weighted_balanced', 'zone_5_hit_rate')}` / `{top10_metric('hybrid_weighted_balanced', 'zone_3_hit_rate')}`",
        "",
        "## Strongest Hybrid Settings",
        "",
        *[
            f"- `{row.validation_type}` / `{row.setting}`: distance delta `{row.avg_distance_delta:.3f}`, 5% delta `{row.zone_5_delta:.3f}`, top10 5% delta `{row.top10_zone_5_delta:.3f}`"
            for row in strongest.itertuples(index=False)
        ],
        "",
        "## Weakest Hybrid Settings",
        "",
        *[
            f"- `{row.validation_type}` / `{row.setting}`: distance delta `{row.avg_distance_delta:.3f}`, 5% delta `{row.zone_5_delta:.3f}`, top10 5% delta `{row.top10_zone_5_delta:.3f}`"
            for row in weakest.itertuples(index=False)
        ],
        "",
        "## Decision",
        "",
        f"- recommendation: **{decision}**",
        *[f"- {note}" for note in notes],
        "",
        "## Interpretation",
        "",
        "- promotion requires the hybrid to beat or tie the fixed baseline across more than the original split-level headline result",
        "- if the hybrid wins distance but loses too often on zone/top-decile quality, it should remain a candidate rather than become the reference",
        "- this is still a research timing-layer validation, not a trading-system proof",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame = load_inputs(args.buy_side_hybrid_scores_csv, args.reversal_zone_dataset_csv)
    frame = add_weight_variants(frame)

    detail_rows: list[dict[str, object]] = []
    definitions = score_definitions()
    for subset_name, mask in subset_definitions(frame):
        validation_type = "full" if subset_name == "full_test" else ("time_split" if subset_name.startswith("test_") else "regime")
        detail_rows.extend(evaluate_subset(frame, subset_name, mask, definitions, validation_type))

    weight_definitions = [definition for definition in definitions if definition["family"] == "weight_sensitivity"]
    full_mask = frame["split"].eq("test")
    detail_rows.extend(evaluate_subset(frame, "weight_sensitivity_full_test", full_mask, weight_definitions, "weight_sensitivity"))

    detail = pd.DataFrame(detail_rows)
    summary = build_validation_summary(detail)

    out_validation = Path(args.out_validation_csv)
    out_validation.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_validation, index=False)

    out_detail = Path(args.out_detail_csv)
    out_detail.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(out_detail, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(detail, summary), encoding="utf-8")

    print(f"Wrote: {out_validation}")
    print(f"Wrote: {out_detail}")
    print(f"Wrote: {out_md}")
    print(f"Validation settings: {len(summary)}")


if __name__ == "__main__":
    main()
