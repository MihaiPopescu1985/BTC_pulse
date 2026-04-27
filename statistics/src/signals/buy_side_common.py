from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signals.reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    build_feature_columns,
    build_model,
    build_splits,
    drop_constant_features,
    prepare_feature_frames,
    validate_retained_feature_columns,
)
from src.signals.swing_extreme_timing import (
    DEFAULT_ANALOG_FORWARD_DAYS,
    DEFAULT_ANALOG_TOP_K,
    DEFAULT_ANALOG_WINDOW,
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


DISTANCE_COLUMN = "dist_to_current_down_swing_low_pct"
SWING_ID_COLUMN = "current_confirmed_swing_id"
SWING_DIRECTION_COLUMN = "current_confirmed_swing_direction"
DOWN_DIRECTION = "down"


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


def build_retained_buy_source(reversal_zone_dataset_csv: str | Path) -> tuple[pd.DataFrame, list[str]]:
    source = load_dataset(reversal_zone_dataset_csv)
    timing, phase_features = add_baseline_scores(source)
    scored = add_exploration_scores(timing)
    return scored, phase_features
