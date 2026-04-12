from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_BUY_SIDE_EXPLORATION_COMPARISON_CSV_PATH,
    DEFAULT_BUY_SIDE_EXPLORATION_SCORES_CSV_PATH,
    DEFAULT_BUY_SIDE_EXPLORATION_SWING_SUMMARY_CSV_PATH,
    DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bottom.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    build_feature_columns,
    build_model,
    build_splits,
    drop_constant_features,
    prepare_feature_frames,
    validate_retained_feature_columns,
)
from src.research.v4_iteration.core.swing_bottom.run_swing_extreme_timing import (
    DEFAULT_ANALOG_FORWARD_DAYS,
    DEFAULT_ANALOG_TOP_K,
    DEFAULT_ANALOG_WINDOW,
    THRESHOLDS,
    TOP_BUCKETS,
    add_combiner_scores,
    build_analog_component,
    build_analog_matrix,
    build_exhaustion_component,
    build_forward_analog_outcomes,
    build_phase_component,
    clip01,
    combine_components,
    load_dataset,
    safe_numeric,
)


DEFAULT_BUY_SIDE_EXPLORATION_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_BUY_SIDE_EXPLORATION.md"
)
DISTANCE_COLUMN = "dist_to_current_down_swing_low_pct"
SWING_ID_COLUMN = "current_confirmed_swing_id"
SWING_DIRECTION_COLUMN = "current_confirmed_swing_direction"
DOWN_DIRECTION = "down"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded buy-side swing-low timing exploration sprint.",
    )
    parser.add_argument(
        "--reversal-zone-dataset-csv",
        default=str(DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_dataset.csv",
    )
    parser.add_argument(
        "--out-scores-csv",
        default=str(DEFAULT_BUY_SIDE_EXPLORATION_SCORES_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_exploration_scores.csv",
    )
    parser.add_argument(
        "--out-comparison-csv",
        default=str(DEFAULT_BUY_SIDE_EXPLORATION_COMPARISON_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_exploration_comparison.csv",
    )
    parser.add_argument(
        "--out-swing-summary-csv",
        default=str(DEFAULT_BUY_SIDE_EXPLORATION_SWING_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/buy_side_exploration_swing_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_BUY_SIDE_EXPLORATION_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_BUY_SIDE_EXPLORATION.md",
    )
    return parser.parse_args()


def weighted_average(values: np.ndarray, weights: np.ndarray) -> float:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    if not valid.any():
        return np.nan
    return float(np.average(values[valid], weights=weights[valid]))


def similarity_weights(similarity: np.ndarray, temperature: float) -> np.ndarray:
    if similarity.size == 0:
        return similarity
    shifted = similarity - np.nanmax(similarity)
    weights = np.exp(shifted / temperature)
    return np.where(np.isfinite(weights), weights, 0.0)


def build_buy_analog_overhaul_score(
    frame: pd.DataFrame,
    *,
    window: int = 7,
    top_k: int = 50,
    horizons: tuple[int, ...] = (3, 5, 7),
    temperature: float = 0.08,
) -> pd.DataFrame:
    matrix, valid = build_analog_matrix(frame, window)
    norms = np.linalg.norm(np.nan_to_num(matrix, nan=0.0), axis=1)
    live_direction = frame["live_swing_direction"].astype("object").fillna("unknown")
    candidate_mask = valid & (norms > 0.0) & live_direction.eq("down").to_numpy()
    outcomes_by_horizon = {
        horizon: build_forward_analog_outcomes(frame, horizon) for horizon in horizons
    }

    score = np.full(len(frame), np.nan, dtype=float)
    match_count = np.zeros(len(frame), dtype=int)
    horizon_weights = {3: 0.25, 5: 0.50, 7: 0.25}

    for idx in range(len(frame)):
        if not valid[idx] or norms[idx] <= 0.0:
            continue
        prior_idx = np.flatnonzero(candidate_mask[:idx])
        if prior_idx.size == 0:
            continue
        current_vector = np.nan_to_num(matrix[idx], nan=0.0)
        prior_vectors = np.nan_to_num(matrix[prior_idx], nan=0.0)
        similarity = prior_vectors @ current_vector
        similarity = similarity / (norms[prior_idx] * norms[idx] + 1e-12)
        order = np.argsort(similarity)[::-1][:top_k]
        analog_idx = prior_idx[order]
        weights = similarity_weights(similarity[order], temperature=temperature)
        horizon_scores: list[tuple[float, float]] = []
        for horizon, outcomes in outcomes_by_horizon.items():
            horizon_scores.append(
                (
                    weighted_average(outcomes["buy_hit_5"][analog_idx], weights),
                    horizon_weights.get(horizon, 1.0),
                )
            )
        valid_scores = [(value, weight) for value, weight in horizon_scores if np.isfinite(value)]
        if valid_scores:
            numerator = sum(value * weight for value, weight in valid_scores)
            denominator = sum(weight for _, weight in valid_scores)
            score[idx] = numerator / denominator
            match_count[idx] = int(analog_idx.size)

    return pd.DataFrame(
        {
            "buy_analog_overhaul_score": clip01(score),
            "buy_analog_overhaul_match_count": match_count,
        }
    )


def build_candle_pattern_matrix(frame: pd.DataFrame, window: int) -> tuple[np.ndarray, np.ndarray]:
    atr = safe_numeric(frame["atr"], fill=np.nan)
    atr_safe = np.where((np.isfinite(atr)) & (atr > 0.0), atr, np.nan)
    base_series = [
        safe_numeric(frame["r1"], fill=np.nan),
        np.divide(safe_numeric(frame["candle_body"], fill=np.nan), atr_safe),
        np.divide(safe_numeric(frame["candle_range"], fill=np.nan), atr_safe),
        safe_numeric(frame["upper_wick_ratio"], fill=np.nan),
        safe_numeric(frame["lower_wick_ratio"], fill=np.nan),
        safe_numeric(frame["close_in_range"], fill=np.nan),
        safe_numeric(frame["body_to_range_ratio"], fill=np.nan),
    ]
    parts: list[np.ndarray] = []
    for lag in range(window):
        for series in base_series:
            shifted = np.roll(series, lag)
            shifted[:lag] = np.nan
            parts.append(shifted)
    matrix = np.column_stack(parts)
    valid = np.isfinite(matrix).all(axis=1)
    return matrix, valid


def build_candle_pattern_memory_score(
    frame: pd.DataFrame,
    *,
    window: int = 5,
    top_k: int = 50,
    forward_days: int = 5,
    temperature: float = 0.07,
) -> pd.DataFrame:
    matrix, valid = build_candle_pattern_matrix(frame, window)
    outcomes = build_forward_analog_outcomes(frame, forward_days)
    norms = np.linalg.norm(np.nan_to_num(matrix, nan=0.0), axis=1)
    candidate_mask = valid & outcomes["candidate_ok"] & (norms > 0.0)
    score = np.full(len(frame), np.nan, dtype=float)
    match_count = np.zeros(len(frame), dtype=int)

    for idx in range(len(frame)):
        if not valid[idx] or norms[idx] <= 0.0:
            continue
        prior_idx = np.flatnonzero(candidate_mask[:idx])
        if prior_idx.size == 0:
            continue
        current_vector = np.nan_to_num(matrix[idx], nan=0.0)
        prior_vectors = np.nan_to_num(matrix[prior_idx], nan=0.0)
        similarity = prior_vectors @ current_vector
        similarity = similarity / (norms[prior_idx] * norms[idx] + 1e-12)
        order = np.argsort(similarity)[::-1][:top_k]
        analog_idx = prior_idx[order]
        weights = similarity_weights(similarity[order], temperature=temperature)
        score[idx] = weighted_average(outcomes["buy_hit_5"][analog_idx], weights)
        match_count[idx] = int(analog_idx.size)

    return pd.DataFrame(
        {
            "buy_candle_pattern_memory_score": clip01(score),
            "buy_candle_pattern_match_count": match_count,
        }
    )


def build_buy_exhaustion_redesign_score(frame: pd.DataFrame) -> pd.DataFrame:
    live_direction = frame["live_swing_direction"].astype("object").fillna("unknown")
    down_context = np.where(live_direction.eq("down"), 1.0, np.where(live_direction.eq("unknown"), 0.35, 0.0))
    age_late = clip01(safe_numeric(frame["current_swing_age_pct_of_median"]) / 1.10)
    size_late = clip01(safe_numeric(frame["current_swing_size_pct_of_median"]) / 1.10)
    band_pos = clip01(safe_numeric(frame["band_pos"]))
    dist_from_mean = safe_numeric(frame["dist_from_mean_vol_units"])
    pivot_distance = safe_numeric(frame["distance_from_last_pivot_pct"])
    price_stretch = clip01(
        0.45 * clip01(-dist_from_mean / 2.5)
        + 0.35 * clip01((0.40 - band_pos) / 0.40)
        + 0.20 * clip01(-pivot_distance / 0.18)
    )

    lower_wick = clip01(safe_numeric(frame["lower_wick_ratio"]))
    close_in_range = clip01(safe_numeric(frame["close_in_range"]))
    bullish_day = (safe_numeric(frame["r1"]) > 0.0).astype(float)
    rejection = clip01(0.45 * lower_wick + 0.40 * close_in_range + 0.15 * bullish_day)

    downside_semi = safe_numeric(frame["downside_semi_vol"])
    ewma_vol = safe_numeric(frame["ewma_vol"])
    washout = clip01(np.divide(downside_semi, ewma_vol + 1e-9) / 1.5)
    stabilization = clip01(0.50 * close_in_range + 0.50 * clip01(safe_numeric(frame["return_accel"]) / 0.08 + 0.50))
    volatility_component = clip01(0.55 * washout + 0.45 * stabilization)

    rebound_pressure = clip01(
        0.55 * safe_numeric(frame["P_REBOUND_10D_CAL"])
        + 0.25 * (1.0 - safe_numeric(frame["P_SHOCK_HMM"]))
        + 0.20 * safe_numeric(frame["P_CORRECTION_10D_CAL"])
    )
    onchain_accumulation = clip01(
        0.45 * clip01(safe_numeric(frame["ONCHAIN_WHALE_SHARE_Z"]) / 3.0 + 0.50)
        + 0.35 * clip01(safe_numeric(frame["ONCHAIN_DOM_Z"]) / 3.0 + 0.50)
        + 0.20 * clip01(safe_numeric(frame["ONCHAIN_VOL_Z"]) / 3.0 + 0.50)
    )

    score = clip01(
        0.16 * down_context
        + 0.14 * age_late
        + 0.14 * size_late
        + 0.18 * price_stretch
        + 0.16 * rejection
        + 0.10 * volatility_component
        + 0.08 * rebound_pressure
        + 0.04 * onchain_accumulation
    )
    return pd.DataFrame({"buy_exhaustion_redesign_score": score})


def build_multiclass_model(numeric_columns: list[str], categorical_columns: list[str]) -> Pipeline:
    transformers: list[tuple[str, object, list[str]]] = []
    if numeric_columns:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            )
        )
    if categorical_columns:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            )
        )
    return Pipeline(
        steps=[
            ("preprocessor", ColumnTransformer(transformers=transformers)),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=0,
                ),
            ),
        ]
    )


def build_buy_ordinal_ranking_score(frame: pd.DataFrame) -> pd.DataFrame:
    feature_columns = build_feature_columns(frame.columns.tolist())
    working = frame.loc[frame.loc[:, feature_columns].notna().any(axis=1)].copy().reset_index(drop=True)
    train, validation, test = build_splits(working)
    fit = pd.concat([train, validation], ignore_index=True)
    retained = drop_constant_features(fit, feature_columns)
    validate_retained_feature_columns(retained)
    fit_x, _validation_x, test_x, numeric_columns, categorical_columns = prepare_feature_frames(fit, validation, test, retained)

    target = np.where(
        pd.to_numeric(fit[DEFAULT_BUY_STRICT_TARGET], errors="coerce").fillna(0).to_numpy(dtype=int) == 1,
        2,
        np.where(pd.to_numeric(fit[DEFAULT_BUY_TARGET], errors="coerce").fillna(0).to_numpy(dtype=int) == 1, 1, 0),
    )
    if sorted(np.unique(target).tolist()) != [0, 1, 2]:
        raise ValueError("Buy ordinal ranking target must contain classes 0, 1, and 2 in train+validation.")

    model = build_multiclass_model(numeric_columns, categorical_columns)
    model.fit(fit_x, target)
    all_x = frame.loc[:, retained].copy()
    bool_columns = [column for column in retained if pd.api.types.is_bool_dtype(all_x[column])]
    for column in bool_columns:
        all_x[column] = all_x[column].astype(float)
    probabilities = model.predict_proba(all_x)
    classes = model.named_steps["model"].classes_
    class_lookup = {int(class_label): idx for idx, class_label in enumerate(classes)}
    p_usable = probabilities[:, class_lookup[1]] if 1 in class_lookup else np.zeros(len(frame), dtype=float)
    p_near = probabilities[:, class_lookup[2]] if 2 in class_lookup else np.zeros(len(frame), dtype=float)
    score = clip01(p_near + 0.55 * p_usable)
    return pd.DataFrame(
        {
            "buy_ordinal_ranking_score": score,
            "buy_ordinal_prob_usable_5pct": p_usable,
            "buy_ordinal_prob_near_3pct": p_near,
        }
    )


def add_baseline_scores(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    phase_scored, phase_features, _phase_splits, _phase_reference = build_phase_component(frame)
    timing = frame.merge(phase_scored, on="date", how="left", validate="one_to_one")
    analog = build_analog_component(
        timing,
        window=DEFAULT_ANALOG_WINDOW,
        top_k=DEFAULT_ANALOG_TOP_K,
        forward_days=DEFAULT_ANALOG_FORWARD_DAYS,
    )
    exhaustion = build_exhaustion_component(timing)
    timing = pd.concat([timing, analog, exhaustion], axis=1)
    timing["buy_fixed_extreme_timing_score"] = combine_components(
        [
            (pd.to_numeric(timing["buy_phase_prob"], errors="coerce").to_numpy(dtype=float), 0.45),
            (pd.to_numeric(timing["buy_analog_prob"], errors="coerce").to_numpy(dtype=float), 0.30),
            (pd.to_numeric(timing["buy_exhaustion_score"], errors="coerce").to_numpy(dtype=float), 0.25),
        ]
    )
    timing["sell_fixed_extreme_timing_score"] = combine_components(
        [
            (pd.to_numeric(timing["sell_phase_prob"], errors="coerce").to_numpy(dtype=float), 0.45),
            (pd.to_numeric(timing["sell_analog_prob"], errors="coerce").to_numpy(dtype=float), 0.30),
            (pd.to_numeric(timing["sell_exhaustion_score"], errors="coerce").to_numpy(dtype=float), 0.25),
        ]
    )
    timing, _coefficients = add_combiner_scores(timing)
    return timing, phase_features


def add_exploration_scores(timing: pd.DataFrame) -> pd.DataFrame:
    analog_overhaul = build_buy_analog_overhaul_score(timing)
    exhaustion_redesign = build_buy_exhaustion_redesign_score(timing)
    candle_memory = build_candle_pattern_memory_score(timing)
    ordinal = build_buy_ordinal_ranking_score(timing)
    scored = pd.concat([timing, analog_overhaul, exhaustion_redesign, candle_memory, ordinal], axis=1)
    scored["buy_consensus_phase_any_score"] = clip01(
        pd.to_numeric(scored["buy_phase_prob"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        * np.nanmax(
            np.column_stack(
                [
                    pd.to_numeric(scored["buy_analog_overhaul_score"], errors="coerce").fillna(0.0).to_numpy(dtype=float),
                    pd.to_numeric(scored["buy_exhaustion_redesign_score"], errors="coerce").fillna(0.0).to_numpy(dtype=float),
                    pd.to_numeric(scored["buy_candle_pattern_memory_score"], errors="coerce").fillna(0.0).to_numpy(dtype=float),
                ]
            ),
            axis=1,
        )
    )
    return scored


def score_definitions() -> list[dict[str, str]]:
    return [
        {"approach": "baseline_phase_only", "score_column": "buy_phase_prob", "family": "baseline"},
        {
            "approach": "baseline_fixed_weight",
            "score_column": "buy_fixed_extreme_timing_score",
            "family": "baseline",
        },
        {
            "approach": "baseline_learned_combiner",
            "score_column": "buy_extreme_timing_score",
            "family": "baseline",
        },
        {
            "approach": "approach_a_analog_overhaul",
            "score_column": "buy_analog_overhaul_score",
            "family": "in_family_analog",
        },
        {
            "approach": "approach_b_exhaustion_redesign",
            "score_column": "buy_exhaustion_redesign_score",
            "family": "in_family_exhaustion",
        },
        {
            "approach": "approach_c_ordinal_ranking",
            "score_column": "buy_ordinal_ranking_score",
            "family": "ranking_objective",
        },
        {
            "approach": "approach_d_candle_pattern_memory",
            "score_column": "buy_candle_pattern_memory_score",
            "family": "outside_the_box",
        },
        {
            "approach": "approach_e_consensus_phase_any",
            "score_column": "buy_consensus_phase_any_score",
            "family": "ensemble_veto",
        },
    ]


def test_down_swing_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[
        frame["split"].eq("test")
        & frame[SWING_DIRECTION_COLUMN].eq(DOWN_DIRECTION)
        & frame[SWING_ID_COLUMN].notna()
    ].copy()


def build_per_swing_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    down_rows = test_down_swing_rows(frame)
    if down_rows.empty:
        raise ValueError("No confirmed down swings are present in the test split.")

    for definition in score_definitions():
        score_column = definition["score_column"]
        for swing_id, swing_frame in down_rows.groupby(SWING_ID_COLUMN, sort=True):
            valid = swing_frame.loc[pd.to_numeric(swing_frame[score_column], errors="coerce").notna()].copy()
            if valid.empty:
                rows.append(
                    {
                        "approach": definition["approach"],
                        "family": definition["family"],
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
            best = valid.sort_values([score_column, "date"], ascending=[False, True]).iloc[0]
            rows.append(
                {
                    "approach": definition["approach"],
                    "family": definition["family"],
                    "current_confirmed_swing_id": swing_id,
                    "valid_signal": 1,
                    "best_date": pd.to_datetime(best["date"]).strftime("%Y-%m-%d"),
                    "best_score": float(best[score_column]),
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
        approach = definition["approach"]
        family = definition["family"]
        score_column = definition["score_column"]

        swing_group = per_swing.loc[per_swing["approach"].eq(approach)].copy()
        valid = swing_group.loc[swing_group["valid_signal"].eq(1)].copy()
        add_comparison_row(
            rows,
            row_type="best_per_swing",
            approach=approach,
            family=family,
            bucket="all_test_down_swings",
            metric="swing_count",
            value=float(len(swing_group)),
        )
        add_comparison_row(
            rows,
            row_type="best_per_swing",
            approach=approach,
            family=family,
            bucket="all_test_down_swings",
            metric="coverage_rate",
            value=float(len(valid) / len(swing_group)) if len(swing_group) else np.nan,
        )
        for metric, value in (
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
            bucket_count = max(1, int(np.ceil(len(ordered) * bucket)))
            selected = ordered.iloc[:bucket_count].copy()
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


def best_approach_by_distance(comparison: pd.DataFrame) -> str:
    best_rows = comparison.loc[
        comparison["row_type"].eq("best_per_swing")
        & comparison["bucket"].eq("all_test_down_swings")
        & comparison["metric"].eq("avg_best_distance")
    ].copy()
    candidates = best_rows.loc[~best_rows["approach"].str.startswith("baseline_")].copy()
    if candidates.empty:
        return ""
    return str(candidates.sort_values("value", ascending=True).iloc[0]["approach"])


def make_recommendation(comparison: pd.DataFrame) -> tuple[str, list[str]]:
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
    best_candidate = best_approach_by_distance(comparison)
    candidate_distance = metric_lookup(
        comparison,
        best_candidate,
        "best_per_swing",
        "all_test_down_swings",
        "avg_best_distance",
    )
    candidate_zone5 = metric_lookup(
        comparison,
        best_candidate,
        "best_per_swing",
        "all_test_down_swings",
        "zone_5_hit_rate",
    )
    candidate_zone3 = metric_lookup(
        comparison,
        best_candidate,
        "best_per_swing",
        "all_test_down_swings",
        "zone_3_hit_rate",
    )
    fixed_top10_zone5 = metric_lookup(comparison, "baseline_fixed_weight", "top_bucket", "top_10pct", "zone_5_hit_rate")
    fixed_top10_distance = metric_lookup(comparison, "baseline_fixed_weight", "top_bucket", "top_10pct", "avg_distance")
    candidate_top10_zone5 = metric_lookup(comparison, best_candidate, "top_bucket", "top_10pct", "zone_5_hit_rate")
    candidate_top10_distance = metric_lookup(comparison, best_candidate, "top_bucket", "top_10pct", "avg_distance")

    notes: list[str] = []
    if not best_candidate:
        return "Pause / likely dead end", ["No non-baseline candidate could be evaluated."]

    distance_gain = fixed_distance - candidate_distance
    zone5_gain = candidate_zone5 - fixed_zone5
    zone3_gain = candidate_zone3 - fixed_zone3
    notes.append(
        f"Best non-baseline by average distance: `{best_candidate}` "
        f"distance `{candidate_distance:.3f}` vs fixed baseline `{fixed_distance:.3f}`."
    )
    notes.append(
        f"Zone hit changes vs fixed baseline: 5% `{zone5_gain:+.3f}`, 3% `{zone3_gain:+.3f}`."
    )
    if pd.notna(candidate_top10_zone5) and pd.notna(fixed_top10_zone5):
        notes.append(
            f"Top-decile 5% hit rate for `{best_candidate}` is `{candidate_top10_zone5:.3f}` "
            f"vs fixed baseline `{fixed_top10_zone5:.3f}`."
        )
    if pd.notna(candidate_top10_distance) and pd.notna(fixed_top10_distance):
        notes.append(
            f"Top-decile average distance for `{best_candidate}` is `{candidate_top10_distance:.3f}` "
            f"vs fixed baseline `{fixed_top10_distance:.3f}`."
        )

    top_decile_degraded = (
        pd.notna(candidate_top10_zone5)
        and pd.notna(fixed_top10_zone5)
        and pd.notna(candidate_top10_distance)
        and pd.notna(fixed_top10_distance)
        and (candidate_top10_zone5 < fixed_top10_zone5 - 0.05 or candidate_top10_distance > fixed_top10_distance + 0.02)
    )

    if distance_gain >= 0.005 and (zone5_gain >= -0.02 or zone3_gain >= -0.02) and not top_decile_degraded:
        return "Continue", notes
    if distance_gain > 0.0 or zone5_gain > 0.0 or zone3_gain > 0.0:
        return "Continue cautiously", notes
    return "Pause / likely dead end", notes


def render_markdown(
    frame: pd.DataFrame,
    comparison: pd.DataFrame,
    phase_feature_count: int,
) -> str:
    decision, decision_notes = make_recommendation(comparison)
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

    lines = [
        "# SAFE v4.0 Buy-Side Exploration Sprint",
        "",
        "## Purpose",
        "",
        "- bounded sprint focused only on buy-side swing-low timing",
        "- no trade rules, execution logic, capital management, or backtest logic are introduced",
        "- all approaches are compared on the same chronological held-out test split",
        "",
        "## Inputs And Split",
        "",
        "- source dataset: `out/swing_bottom/reversal_zone_dataset.csv`",
        f"- retained phase-model causal feature count: `{phase_feature_count}`",
        f"- test down swings evaluated: `{down_swing_count}`",
        f"- test date range: `{pd.to_datetime(test['date']).min().date()}` to `{pd.to_datetime(test['date']).max().date()}`",
        "",
        "## Approaches Tested",
        "",
        "- `baseline_phase_only`: corrected buy-zone phase model probability",
        "- `baseline_fixed_weight`: current fixed phase/analog/exhaustion reference",
        "- `baseline_learned_combiner`: current learned buy combiner",
        "- `approach_a_analog_overhaul`: 7-candle, 50-neighbor, direction-restricted, similarity-weighted, multi-horizon analog memory",
        "- `approach_b_exhaustion_redesign`: deterministic late-down-swing washout, rejection, stretch, regime, and on-chain accumulation score",
        "- `approach_c_ordinal_ranking`: simple 0/1/2 logistic ranking proxy for rest / 5% zone / 3% zone",
        "- `approach_d_candle_pattern_memory`: outside-the-box candle-geometry-only historical memory",
        "- `approach_e_consensus_phase_any`: phase support multiplied by best agreement from analog, exhaustion, or candle memory",
        "",
        "## Primary Swing-Level Best-Pick Results",
        "",
        best_line("baseline_phase_only"),
        best_line("baseline_fixed_weight"),
        best_line("baseline_learned_combiner"),
        best_line("approach_a_analog_overhaul"),
        best_line("approach_b_exhaustion_redesign"),
        best_line("approach_c_ordinal_ranking"),
        best_line("approach_d_candle_pattern_memory"),
        best_line("approach_e_consensus_phase_any"),
        "",
        "## Ranking By Average Best-Picked Distance",
        "",
        *ranked_lines,
        "",
        "## Top-Decile Quality",
        "",
        top10_line("baseline_phase_only"),
        top10_line("baseline_fixed_weight"),
        top10_line("baseline_learned_combiner"),
        top10_line("approach_a_analog_overhaul"),
        top10_line("approach_b_exhaustion_redesign"),
        top10_line("approach_c_ordinal_ranking"),
        top10_line("approach_d_candle_pattern_memory"),
        top10_line("approach_e_consensus_phase_any"),
        "",
        "## Decision",
        "",
        f"- recommendation: **{decision}**",
        *[f"- {note}" for note in decision_notes],
        "",
        "## Interpretation",
        "",
        "- the fixed-weight baseline remains the buy-side reference unless a new approach improves proximity without materially weakening 5% / 3% hit rates",
        "- if the best experimental approach improves only one dimension, the next pass should be tightly scoped rather than open-ended",
        "- if no approach beats the fixed-weight baseline, the current buy-side framing is likely near diminishing returns with the present feature surface",
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
        "buy_phase_prob",
        "buy_fixed_extreme_timing_score",
        "buy_extreme_timing_score",
        "buy_analog_overhaul_score",
        "buy_exhaustion_redesign_score",
        "buy_ordinal_ranking_score",
        "buy_candle_pattern_memory_score",
        "buy_consensus_phase_any_score",
        "buy_analog_overhaul_match_count",
        "buy_candle_pattern_match_count",
        "buy_ordinal_prob_usable_5pct",
        "buy_ordinal_prob_near_3pct",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DISTANCE_COLUMN,
    ]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Cannot export buy-side exploration scores; missing columns: {missing}")
    return frame.loc[:, columns].copy()


def main() -> None:
    args = parse_args()
    source = load_dataset(args.reversal_zone_dataset_csv)
    timing, phase_features = add_baseline_scores(source)
    scored = add_exploration_scores(timing)
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
    out_md.write_text(render_markdown(scored, comparison, len(phase_features)), encoding="utf-8")

    print(f"Wrote: {out_scores}")
    print(f"Wrote: {out_comparison}")
    print(f"Wrote: {out_swing}")
    print(f"Wrote: {out_md}")
    print(f"Rows written: {len(export)}")
    print(f"Test rows: {int((export['split'] == 'test').sum())}")


if __name__ == "__main__":
    main()
