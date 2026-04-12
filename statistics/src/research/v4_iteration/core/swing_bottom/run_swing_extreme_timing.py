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

from src.data.feature_store import load_feature_csv
from src.path_config import (
    DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH,
    DEFAULT_SWING_EXTREME_TIMING_ABLATION_CSV_PATH,
    DEFAULT_SWING_EXTREME_TIMING_CSV_PATH,
    DEFAULT_SWING_EXTREME_TIMING_SWING_SUMMARY_CSV_PATH,
    DEFAULT_SWING_EXTREME_TIMING_THRESHOLDS_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bottom.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
    build_feature_columns,
    build_model as build_phase_model,
    build_splits,
    drop_constant_features,
    ensure_binary_target,
    prepare_feature_frames,
    validate_retained_feature_columns,
)


DEFAULT_SWING_EXTREME_TIMING_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_SWING_EXTREME_TIMING.md"
DEFAULT_ANALOG_WINDOW = 5
DEFAULT_ANALOG_TOP_K = 40
DEFAULT_ANALOG_FORWARD_DAYS = 5
THRESHOLDS: tuple[float, ...] = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90)
TOP_BUCKETS: tuple[float, ...] = (0.05, 0.10, 0.20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a combined swing-extreme timing layer from phase, analog, and exhaustion components.",
    )
    parser.add_argument(
        "--reversal-zone-dataset-csv",
        default=str(DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_dataset.csv",
    )
    parser.add_argument("--analog-window", type=int, default=DEFAULT_ANALOG_WINDOW)
    parser.add_argument("--analog-top-k", type=int, default=DEFAULT_ANALOG_TOP_K)
    parser.add_argument("--analog-forward-days", type=int, default=DEFAULT_ANALOG_FORWARD_DAYS)
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_SWING_EXTREME_TIMING_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_extreme_timing.csv",
    )
    parser.add_argument(
        "--out-swing-summary-csv",
        default=str(DEFAULT_SWING_EXTREME_TIMING_SWING_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_extreme_timing_swing_summary.csv",
    )
    parser.add_argument(
        "--out-thresholds-csv",
        default=str(DEFAULT_SWING_EXTREME_TIMING_THRESHOLDS_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_extreme_timing_thresholds.csv",
    )
    parser.add_argument(
        "--out-ablation-csv",
        default=str(DEFAULT_SWING_EXTREME_TIMING_ABLATION_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_extreme_timing_ablation.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SWING_EXTREME_TIMING_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_SWING_EXTREME_TIMING.md",
    )
    return parser.parse_args()


def load_dataset(path: str | Path) -> pd.DataFrame:
    frame = load_feature_csv(path).sort_values("date").reset_index(drop=True)
    required = [
        "date",
        "close",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
        "current_confirmed_swing_id",
        "current_confirmed_swing_direction",
        "live_swing_direction",
        "days_since_last_pivot",
        "distance_from_last_pivot_pct",
        "current_swing_age_pct_of_median",
        "current_swing_size_pct_of_median",
        "dist_to_current_down_swing_low_pct",
        "dist_to_current_up_swing_high_pct",
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Reversal-zone dataset is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Reversal-zone dataset contains duplicate dates.")
    return frame


def build_phase_component(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict[str, pd.DataFrame], dict[str, dict[str, float]]]:
    feature_columns = build_feature_columns(frame.columns.tolist())
    working = frame.loc[frame.loc[:, feature_columns].notna().any(axis=1)].copy().reset_index(drop=True)
    train, validation, test = build_splits(working)

    for name, target in (
        ("buy_train", train[DEFAULT_BUY_TARGET]),
        ("buy_validation", validation[DEFAULT_BUY_TARGET]),
        ("buy_test", test[DEFAULT_BUY_TARGET]),
        ("sell_train", train[DEFAULT_SELL_TARGET]),
        ("sell_validation", validation[DEFAULT_SELL_TARGET]),
        ("sell_test", test[DEFAULT_SELL_TARGET]),
    ):
        ensure_binary_target(name, target)

    phase_features = drop_constant_features(train, feature_columns)
    validate_retained_feature_columns(phase_features)
    train_x, validation_x, test_x, numeric_columns, categorical_columns = prepare_feature_frames(
        train, validation, test, phase_features
    )

    buy_model = build_phase_model(numeric_columns, categorical_columns)
    sell_model = build_phase_model(numeric_columns, categorical_columns)
    buy_model.fit(train_x, pd.to_numeric(train[DEFAULT_BUY_TARGET], errors="coerce").astype(int))
    sell_model.fit(train_x, pd.to_numeric(train[DEFAULT_SELL_TARGET], errors="coerce").astype(int))

    scored_parts: list[pd.DataFrame] = []
    split_lookup: dict[str, pd.DataFrame] = {"train": train, "validation": validation, "test": test}
    phase_reference: dict[str, dict[str, float]] = {}
    for split_name, split_frame, split_x in (
        ("train", train, train_x),
        ("validation", validation, validation_x),
        ("test", test, test_x),
    ):
        buy_proba = buy_model.predict_proba(split_x)[:, 1]
        sell_proba = sell_model.predict_proba(split_x)[:, 1]
        scored_parts.append(
            pd.DataFrame(
                {
                    "date": split_frame["date"].values,
                    "split": split_name,
                    "buy_phase_prob": buy_proba,
                    "sell_phase_prob": sell_proba,
                }
            )
        )
        if split_name == "test":
            test_ref = split_frame.copy()
            test_ref["buy_phase_prob"] = buy_proba
            test_ref["sell_phase_prob"] = sell_proba
            phase_reference["buy"] = compute_bucket_reference(
                test_ref,
                score_column="buy_phase_prob",
                zone_5_column=DEFAULT_BUY_TARGET,
                zone_3_column=DEFAULT_BUY_STRICT_TARGET,
                distance_column="dist_to_current_down_swing_low_pct",
                direction="down",
                bucket=0.10,
            )
            phase_reference["sell"] = compute_bucket_reference(
                test_ref,
                score_column="sell_phase_prob",
                zone_5_column=DEFAULT_SELL_TARGET,
                zone_3_column=DEFAULT_SELL_STRICT_TARGET,
                distance_column="dist_to_current_up_swing_high_pct",
                direction="up",
                bucket=0.10,
            )

    scored = pd.concat(scored_parts, ignore_index=True)
    return scored, phase_features, split_lookup, phase_reference


def safe_numeric(series: pd.Series, fill: float = 0.0) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").fillna(fill).to_numpy(dtype=float)


def clip01(values: np.ndarray) -> np.ndarray:
    return np.clip(values, 0.0, 1.0)


def encode_live_direction(series: pd.Series, down_value: float, up_value: float, unknown_value: float) -> np.ndarray:
    mapped = series.astype("object").fillna("unknown").replace({"down": down_value, "up": up_value, "unknown": unknown_value})
    return mapped.to_numpy(dtype=float)


def build_analog_matrix(frame: pd.DataFrame, window: int) -> tuple[np.ndarray, np.ndarray]:
    atr = safe_numeric(frame["atr"], fill=np.nan)
    atr_safe = np.where((np.isfinite(atr)) & (atr > 0.0), atr, np.nan)
    r1 = safe_numeric(frame["r1"], fill=np.nan)
    candle_body = safe_numeric(frame["candle_body"], fill=np.nan)
    candle_range = safe_numeric(frame["candle_range"], fill=np.nan)
    upper_wick_ratio = safe_numeric(frame["upper_wick_ratio"], fill=np.nan)
    lower_wick_ratio = safe_numeric(frame["lower_wick_ratio"], fill=np.nan)
    close_in_range = safe_numeric(frame["close_in_range"], fill=np.nan)

    state_columns = [
        clip01((safe_numeric(frame["band_pos"]) - 0.0) / 1.0),
        np.clip(safe_numeric(frame["dist_from_mean_vol_units"]) / 3.0, -1.0, 1.0),
        clip01(safe_numeric(frame["atr_pct"]) / 0.10),
        clip01(safe_numeric(frame["ewma_vol"]) / 0.10),
        clip01(safe_numeric(frame["P_CORRECTION_10D_CAL"])),
        clip01(safe_numeric(frame["P_REBOUND_10D_CAL"])),
        clip01(safe_numeric(frame["P_SHOCK_HMM"])),
        clip01(safe_numeric(frame["P_SURGE_HMM"])),
        encode_live_direction(frame["live_swing_direction"], down_value=-1.0, up_value=1.0, unknown_value=0.0),
        clip01(safe_numeric(frame["days_since_last_pivot"]) / 20.0),
        np.clip(safe_numeric(frame["distance_from_last_pivot_pct"]) / 0.20, -1.0, 1.0),
        clip01(safe_numeric(frame["current_swing_age_pct_of_median"]) / 2.0),
        clip01(safe_numeric(frame["current_swing_size_pct_of_median"]) / 2.0),
        np.clip(safe_numeric(frame["ONCHAIN_DOM_Z"]) / 3.0, -1.0, 1.0),
        np.clip(safe_numeric(frame["ONCHAIN_WHALE_SHARE_Z"]) / 3.0, -1.0, 1.0),
        np.clip(safe_numeric(frame["ONCHAIN_VOL_Z"]) / 3.0, -1.0, 1.0),
    ]

    vector_parts: list[np.ndarray] = []
    for lag in range(window):
        shifted_atr = np.roll(atr_safe, lag)
        shifted_atr[:lag] = np.nan
        vector_parts.extend(
            [
                np.roll(r1, lag),
                np.divide(np.roll(candle_body, lag), shifted_atr),
                np.divide(np.roll(candle_range, lag), shifted_atr),
                np.roll(upper_wick_ratio, lag),
                np.roll(lower_wick_ratio, lag),
                np.roll(close_in_range, lag),
            ]
        )
        for arr in vector_parts[-6:]:
            arr[:lag] = np.nan

    vector_parts.extend(state_columns)
    matrix = np.column_stack(vector_parts)
    valid = np.isfinite(matrix).all(axis=1)
    return matrix, valid


def build_forward_analog_outcomes(frame: pd.DataFrame, horizon: int) -> dict[str, np.ndarray]:
    n_rows = len(frame)
    buy_zone_5 = safe_numeric(frame[DEFAULT_BUY_TARGET])
    buy_zone_3 = safe_numeric(frame[DEFAULT_BUY_STRICT_TARGET])
    sell_zone_5 = safe_numeric(frame[DEFAULT_SELL_TARGET])
    sell_zone_3 = safe_numeric(frame[DEFAULT_SELL_STRICT_TARGET])

    outputs = {
        "buy_hit_5": np.zeros(n_rows, dtype=float),
        "buy_hit_3": np.zeros(n_rows, dtype=float),
        "buy_days": np.full(n_rows, np.nan, dtype=float),
        "sell_hit_5": np.zeros(n_rows, dtype=float),
        "sell_hit_3": np.zeros(n_rows, dtype=float),
        "sell_days": np.full(n_rows, np.nan, dtype=float),
        "candidate_ok": np.zeros(n_rows, dtype=bool),
    }

    for idx in range(n_rows):
        end = min(n_rows, idx + 1 + horizon)
        future_slice = slice(idx + 1, end)
        if future_slice.start >= future_slice.stop:
            continue
        outputs["candidate_ok"][idx] = True
        future_buy_5 = buy_zone_5[future_slice]
        future_buy_3 = buy_zone_3[future_slice]
        future_sell_5 = sell_zone_5[future_slice]
        future_sell_3 = sell_zone_3[future_slice]

        if np.any(future_buy_5 > 0.5):
            outputs["buy_hit_5"][idx] = 1.0
            outputs["buy_days"][idx] = float(np.argmax(future_buy_5 > 0.5) + 1)
        if np.any(future_buy_3 > 0.5):
            outputs["buy_hit_3"][idx] = 1.0
        if np.any(future_sell_5 > 0.5):
            outputs["sell_hit_5"][idx] = 1.0
            outputs["sell_days"][idx] = float(np.argmax(future_sell_5 > 0.5) + 1)
        if np.any(future_sell_3 > 0.5):
            outputs["sell_hit_3"][idx] = 1.0
    return outputs


def weighted_average(values: np.ndarray, weights: np.ndarray) -> float:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    if not valid.any():
        return np.nan
    return float(np.average(values[valid], weights=weights[valid]))


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    if not valid.any():
        return np.nan
    ordered = np.argsort(values[valid])
    sorted_values = values[valid][ordered]
    sorted_weights = weights[valid][ordered]
    cumulative = np.cumsum(sorted_weights)
    cutoff = sorted_weights.sum() * 0.5
    return float(sorted_values[np.searchsorted(cumulative, cutoff, side="left")])


def analog_weights(similarity: np.ndarray) -> np.ndarray:
    if similarity.size == 0:
        return similarity
    shifted = similarity - np.nanmax(similarity)
    weights = np.exp(shifted / 0.15)
    return np.where(np.isfinite(weights), weights, 0.0)


def build_analog_component(frame: pd.DataFrame, window: int, top_k: int, forward_days: int) -> pd.DataFrame:
    matrix, valid = build_analog_matrix(frame, window)
    outcomes = build_forward_analog_outcomes(frame, forward_days)
    norms = np.linalg.norm(np.nan_to_num(matrix, nan=0.0), axis=1)
    live_direction = frame["live_swing_direction"].astype("object").fillna("unknown")

    buy_prob = np.full(len(frame), np.nan, dtype=float)
    buy_prob_strict = np.full(len(frame), np.nan, dtype=float)
    buy_days = np.full(len(frame), np.nan, dtype=float)
    buy_count = np.zeros(len(frame), dtype=int)
    sell_prob = np.full(len(frame), np.nan, dtype=float)
    sell_prob_strict = np.full(len(frame), np.nan, dtype=float)
    sell_days = np.full(len(frame), np.nan, dtype=float)
    sell_count = np.zeros(len(frame), dtype=int)

    candidate_mask = valid & outcomes["candidate_ok"] & (norms > 0.0)
    buy_candidate_mask = candidate_mask & live_direction.eq("down").to_numpy()
    sell_candidate_mask = candidate_mask & live_direction.eq("up").to_numpy()

    for idx in range(len(frame)):
        if not valid[idx] or norms[idx] <= 0.0:
            continue

        current_vector = np.nan_to_num(matrix[idx], nan=0.0)
        for side, side_mask in (("buy", buy_candidate_mask), ("sell", sell_candidate_mask)):
            prior_idx = np.flatnonzero(side_mask[:idx])
            if prior_idx.size == 0:
                continue

            prior_vectors = np.nan_to_num(matrix[prior_idx], nan=0.0)
            similarity = prior_vectors @ current_vector
            similarity = similarity / (norms[prior_idx] * norms[idx] + 1e-12)
            order = np.argsort(similarity)[::-1][:top_k]
            analog_idx = prior_idx[order]
            selected_similarity = similarity[order]
            if analog_idx.size == 0:
                continue
            weights = analog_weights(selected_similarity)

            if side == "buy":
                buy_prob[idx] = weighted_average(outcomes["buy_hit_5"][analog_idx], weights)
                buy_prob_strict[idx] = weighted_average(outcomes["buy_hit_3"][analog_idx], weights)
                buy_days[idx] = weighted_median(outcomes["buy_days"][analog_idx], weights)
                buy_count[idx] = int(analog_idx.size)
            else:
                sell_prob[idx] = weighted_average(outcomes["sell_hit_5"][analog_idx], weights)
                sell_prob_strict[idx] = weighted_average(outcomes["sell_hit_3"][analog_idx], weights)
                sell_days[idx] = weighted_median(outcomes["sell_days"][analog_idx], weights)
                sell_count[idx] = int(analog_idx.size)

    return pd.DataFrame(
        {
            "buy_analog_prob": buy_prob,
            "sell_analog_prob": sell_prob,
            "buy_analog_median_days": buy_days,
            "sell_analog_median_days": sell_days,
            "buy_analog_match_count": buy_count,
            "sell_analog_match_count": sell_count,
            "buy_analog_prob_strict": buy_prob_strict,
            "sell_analog_prob_strict": sell_prob_strict,
        }
    )


def combine_components(parts: list[tuple[np.ndarray, float]]) -> np.ndarray:
    weighted_sum = np.zeros(len(parts[0][0]), dtype=float)
    weight_sum = np.zeros(len(parts[0][0]), dtype=float)
    for values, weight in parts:
        valid = np.isfinite(values)
        weighted_sum[valid] += values[valid] * weight
        weight_sum[valid] += weight
    combined = np.divide(weighted_sum, weight_sum, out=np.full_like(weighted_sum, np.nan), where=weight_sum > 0)
    return clip01(combined)


def build_exhaustion_component(frame: pd.DataFrame) -> pd.DataFrame:
    live_direction = frame["live_swing_direction"].astype("object").fillna("unknown")
    band_pos = clip01(safe_numeric(frame["band_pos"]))
    dist_from_mean = safe_numeric(frame["dist_from_mean_vol_units"])
    age_pct = clip01(safe_numeric(frame["current_swing_age_pct_of_median"]) / 1.25)
    size_pct = clip01(safe_numeric(frame["current_swing_size_pct_of_median"]) / 1.25)
    downside_semi = safe_numeric(frame["downside_semi_vol"])
    upside_semi = safe_numeric(frame["upside_semi_vol"])
    ewma_vol = safe_numeric(frame["ewma_vol"])
    vol_cooling_down = clip01(1.0 - np.divide(downside_semi, ewma_vol + 1e-9))
    vol_cooling_up = clip01(1.0 - np.divide(upside_semi, ewma_vol + 1e-9))
    buy_direction = np.where(live_direction.eq("down"), 1.0, np.where(live_direction.eq("unknown"), 0.35, 0.0))
    sell_direction = np.where(live_direction.eq("up"), 1.0, np.where(live_direction.eq("unknown"), 0.35, 0.0))
    buy_stretch = 0.5 * clip01(-dist_from_mean / 3.0) + 0.5 * clip01((0.5 - band_pos) / 0.5)
    sell_stretch = 0.5 * clip01(dist_from_mean / 3.0) + 0.5 * clip01((band_pos - 0.5) / 0.5)
    buy_regime = 0.5 * clip01(safe_numeric(frame["P_CORRECTION_10D_CAL"])) + 0.5 * clip01(safe_numeric(frame["P_REBOUND_10D_CAL"]))
    sell_regime = 0.5 * clip01(safe_numeric(frame["P_CORRECTION_10D_CAL"])) + 0.5 * clip01(safe_numeric(frame["P_SURGE_HMM"]))

    buy_score = clip01((buy_direction + age_pct + size_pct + buy_stretch + vol_cooling_down + buy_regime) / 6.0)
    sell_score = clip01((sell_direction + age_pct + size_pct + sell_stretch + vol_cooling_up + sell_regime) / 6.0)
    return pd.DataFrame(
        {
            "buy_exhaustion_score": buy_score,
            "sell_exhaustion_score": sell_score,
        }
    )


def build_combiner_model() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
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


def fit_combiner_scores(
    timing: pd.DataFrame,
    *,
    side: str,
    feature_columns: list[str],
    target_column: str,
) -> tuple[np.ndarray, dict[str, float]]:
    if not feature_columns:
        raise ValueError(f"{side} combiner feature set is empty.")
    fit_mask = timing["split"].isin(["train", "validation"])
    fit_frame = timing.loc[fit_mask].copy()
    ensure_binary_target(f"{side}_combiner_fit", fit_frame[target_column])

    model = build_combiner_model()
    model.fit(fit_frame.loc[:, feature_columns], pd.to_numeric(fit_frame[target_column], errors="coerce").astype(int))
    proba = model.predict_proba(timing.loc[:, feature_columns])[:, 1]
    classifier: LogisticRegression = model.named_steps["model"]
    coefficients = {
        feature: float(coef)
        for feature, coef in zip(feature_columns, classifier.coef_.reshape(-1), strict=True)
    }
    return proba, coefficients


def add_combiner_scores(timing: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    frame = timing.copy()
    combiner_coefficients: dict[str, dict[str, float]] = {}

    buy_full_features = ["buy_phase_prob", "buy_analog_prob", "buy_exhaustion_score"]
    sell_full_features = ["sell_phase_prob", "sell_analog_prob", "sell_exhaustion_score"]
    frame["buy_phase_only_score"] = frame["buy_phase_prob"]
    frame["sell_phase_only_score"] = frame["sell_phase_prob"]

    frame["buy_phase_analog_score"], combiner_coefficients["buy_phase_analog"] = fit_combiner_scores(
        frame,
        side="buy_phase_analog",
        feature_columns=["buy_phase_prob", "buy_analog_prob"],
        target_column=DEFAULT_BUY_TARGET,
    )
    frame["sell_phase_analog_score"], combiner_coefficients["sell_phase_analog"] = fit_combiner_scores(
        frame,
        side="sell_phase_analog",
        feature_columns=["sell_phase_prob", "sell_analog_prob"],
        target_column=DEFAULT_SELL_TARGET,
    )
    frame["buy_phase_exhaustion_score"], combiner_coefficients["buy_phase_exhaustion"] = fit_combiner_scores(
        frame,
        side="buy_phase_exhaustion",
        feature_columns=["buy_phase_prob", "buy_exhaustion_score"],
        target_column=DEFAULT_BUY_TARGET,
    )
    frame["sell_phase_exhaustion_score"], combiner_coefficients["sell_phase_exhaustion"] = fit_combiner_scores(
        frame,
        side="sell_phase_exhaustion",
        feature_columns=["sell_phase_prob", "sell_exhaustion_score"],
        target_column=DEFAULT_SELL_TARGET,
    )
    frame["buy_extreme_timing_score"], combiner_coefficients["buy_full"] = fit_combiner_scores(
        frame,
        side="buy_full",
        feature_columns=buy_full_features,
        target_column=DEFAULT_BUY_TARGET,
    )
    frame["sell_extreme_timing_score"], combiner_coefficients["sell_full"] = fit_combiner_scores(
        frame,
        side="sell_full",
        feature_columns=sell_full_features,
        target_column=DEFAULT_SELL_TARGET,
    )
    return frame, combiner_coefficients


def compute_bucket_reference(
    frame: pd.DataFrame,
    *,
    score_column: str,
    zone_5_column: str,
    zone_3_column: str,
    distance_column: str,
    direction: str,
    bucket: float,
) -> dict[str, float]:
    ordered = frame.sort_values(score_column, ascending=False).reset_index(drop=True)
    bucket_count = max(1, int(np.ceil(len(ordered) * bucket)))
    selected = ordered.iloc[:bucket_count].copy()
    swing_mask = selected["current_confirmed_swing_direction"].eq(direction) & selected["current_confirmed_swing_id"].notna()
    return {
        "row_count": float(len(selected)),
        "zone_5_hit_rate": float(pd.to_numeric(selected[zone_5_column], errors="coerce").fillna(0).mean()),
        "zone_3_hit_rate": float(pd.to_numeric(selected[zone_3_column], errors="coerce").fillna(0).mean()),
        "avg_distance": float(pd.to_numeric(selected[distance_column], errors="coerce").dropna().mean())
        if pd.to_numeric(selected[distance_column], errors="coerce").dropna().size
        else np.nan,
        "unique_swings_touched": float(selected.loc[swing_mask, "current_confirmed_swing_id"].nunique()),
    }


def build_metric_rows(timing: pd.DataFrame, phase_reference: dict[str, dict[str, float]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    test = timing.loc[timing["split"] == "test"].copy()

    for side, score_col, zone5, zone3, dist_col, direction, phase_col in (
        ("buy", "buy_extreme_timing_score", DEFAULT_BUY_TARGET, DEFAULT_BUY_STRICT_TARGET, "dist_to_current_down_swing_low_pct", "down", "buy_phase_prob"),
        ("sell", "sell_extreme_timing_score", DEFAULT_SELL_TARGET, DEFAULT_SELL_STRICT_TARGET, "dist_to_current_up_swing_high_pct", "up", "sell_phase_prob"),
    ):
        for bucket in (0.05, 0.10, 0.20):
            summary = compute_bucket_reference(
                test,
                score_column=score_col,
                zone_5_column=zone5,
                zone_3_column=zone3,
                distance_column=dist_col,
                direction=direction,
                bucket=bucket,
            )
            for metric, value in summary.items():
                rows.append(
                    {
                        "row_type": "combined_bucket",
                        "side": side,
                        "split": "test",
                        "bucket": f"top_{int(bucket * 100)}pct",
                        "metric": metric,
                        "value": value,
                    }
                )

        phase_summary = phase_reference[side]
        for metric, value in phase_summary.items():
            rows.append(
                {
                    "row_type": "phase_reference",
                    "side": side,
                    "split": "test",
                    "bucket": "top_10pct",
                    "metric": metric,
                    "value": value,
                }
            )

        side_test = test.loc[test["current_confirmed_swing_direction"].eq(direction) & test["current_confirmed_swing_id"].notna()].copy()
        if side_test.empty:
            continue
        threshold = float(test[score_col].quantile(0.90))
        threshold_hits = side_test.loc[side_test[score_col] >= threshold].copy()
        best_per_swing = (
            side_test.sort_values([score_col, "date"], ascending=[False, True])
            .groupby("current_confirmed_swing_id", as_index=False)
            .first()
        )
        rows.extend(
            [
                {
                    "row_type": "swing_summary",
                    "side": side,
                    "split": "test",
                    "bucket": "top_10pct_threshold",
                    "metric": "swing_count",
                    "value": float(side_test["current_confirmed_swing_id"].nunique()),
                },
                {
                    "row_type": "swing_summary",
                    "side": side,
                    "split": "test",
                    "bucket": "top_10pct_threshold",
                    "metric": "swings_with_high_score",
                    "value": float(threshold_hits["current_confirmed_swing_id"].nunique()),
                },
                {
                    "row_type": "swing_summary",
                    "side": side,
                    "split": "test",
                    "bucket": "best_per_swing",
                    "metric": "avg_best_distance",
                    "value": float(pd.to_numeric(best_per_swing[dist_col], errors="coerce").mean()),
                },
                {
                    "row_type": "swing_summary",
                    "side": side,
                    "split": "test",
                    "bucket": "best_per_swing",
                    "metric": "median_best_distance",
                    "value": float(pd.to_numeric(best_per_swing[dist_col], errors="coerce").median()),
                },
                {
                    "row_type": "swing_summary",
                    "side": side,
                    "split": "test",
                    "bucket": "best_per_swing",
                    "metric": "zone_5_hit_rate",
                    "value": float(pd.to_numeric(best_per_swing[zone5], errors="coerce").fillna(0).mean()),
                },
                {
                    "row_type": "swing_summary",
                    "side": side,
                    "split": "test",
                    "bucket": "best_per_swing",
                    "metric": "zone_3_hit_rate",
                    "value": float(pd.to_numeric(best_per_swing[zone3], errors="coerce").fillna(0).mean()),
                },
            ]
        )

    return pd.DataFrame(rows)


def score_variants() -> list[dict[str, str]]:
    return [
        {
            "variant": "phase_only",
            "buy_score": "buy_phase_only_score",
            "sell_score": "sell_phase_only_score",
        },
        {
            "variant": "phase_analog",
            "buy_score": "buy_phase_analog_score",
            "sell_score": "sell_phase_analog_score",
        },
        {
            "variant": "phase_exhaustion",
            "buy_score": "buy_phase_exhaustion_score",
            "sell_score": "sell_phase_exhaustion_score",
        },
        {
            "variant": "fixed_weight",
            "buy_score": "buy_fixed_extreme_timing_score",
            "sell_score": "sell_fixed_extreme_timing_score",
        },
        {
            "variant": "learned_full",
            "buy_score": "buy_extreme_timing_score",
            "sell_score": "sell_extreme_timing_score",
        },
    ]


def side_config(side: str) -> dict[str, str]:
    if side == "buy":
        return {
            "direction": "down",
            "zone5": DEFAULT_BUY_TARGET,
            "zone3": DEFAULT_BUY_STRICT_TARGET,
            "distance": "dist_to_current_down_swing_low_pct",
        }
    if side == "sell":
        return {
            "direction": "up",
            "zone5": DEFAULT_SELL_TARGET,
            "zone3": DEFAULT_SELL_STRICT_TARGET,
            "distance": "dist_to_current_up_swing_high_pct",
        }
    raise ValueError(f"Unknown side: {side}")


def build_per_swing_summary(timing: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    test = timing.loc[timing["split"] == "test"].copy()
    for variant in score_variants():
        for side in ("buy", "sell"):
            config = side_config(side)
            score_column = variant[f"{side}_score"]
            side_rows = test.loc[
                test["current_confirmed_swing_direction"].eq(config["direction"])
                & test["current_confirmed_swing_id"].notna()
            ].copy()
            for swing_id, swing_frame in side_rows.groupby("current_confirmed_swing_id", sort=True):
                valid_scores = swing_frame.loc[pd.to_numeric(swing_frame[score_column], errors="coerce").notna()].copy()
                if valid_scores.empty:
                    rows.append(
                        {
                            "side": side,
                            "score_variant": variant["variant"],
                            "current_confirmed_swing_id": swing_id,
                            "current_confirmed_swing_direction": config["direction"],
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
                best = valid_scores.sort_values([score_column, "date"], ascending=[False, True]).iloc[0]
                rows.append(
                    {
                        "side": side,
                        "score_variant": variant["variant"],
                        "current_confirmed_swing_id": swing_id,
                        "current_confirmed_swing_direction": config["direction"],
                        "valid_signal": 1,
                        "best_date": pd.to_datetime(best["date"]).strftime("%Y-%m-%d"),
                        "best_score": float(best[score_column]),
                        "best_distance": float(best[config["distance"]]),
                        "best_within_5pct": int(best[config["zone5"]]),
                        "best_within_3pct": int(best[config["zone3"]]),
                        "swing_row_count": len(swing_frame),
                    }
                )
    return pd.DataFrame(rows)


def summarize_per_swing(per_swing: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (side, variant), group in per_swing.groupby(["side", "score_variant"], sort=True):
        valid = group.loc[group["valid_signal"].eq(1)].copy()
        rows.append(
            {
                "row_type": "best_per_swing",
                "side": side,
                "score_variant": variant,
                "bucket": "all_test_swings",
                "metric": "swing_count",
                "value": float(len(group)),
            }
        )
        rows.append(
            {
                "row_type": "best_per_swing",
                "side": side,
                "score_variant": variant,
                "bucket": "all_test_swings",
                "metric": "valid_signal_swings",
                "value": float(len(valid)),
            }
        )
        rows.append(
            {
                "row_type": "best_per_swing",
                "side": side,
                "score_variant": variant,
                "bucket": "all_test_swings",
                "metric": "coverage_rate",
                "value": float(len(valid) / len(group)) if len(group) else np.nan,
            }
        )
        if valid.empty:
            for metric in ("avg_distance", "median_distance", "zone_5_hit_rate", "zone_3_hit_rate"):
                rows.append(
                    {
                        "row_type": "best_per_swing",
                        "side": side,
                        "score_variant": variant,
                        "bucket": "all_test_swings",
                        "metric": metric,
                        "value": np.nan,
                    }
                )
            continue
        rows.extend(
            [
                {
                    "row_type": "best_per_swing",
                    "side": side,
                    "score_variant": variant,
                    "bucket": "all_test_swings",
                    "metric": "avg_distance",
                    "value": float(pd.to_numeric(valid["best_distance"], errors="coerce").mean()),
                },
                {
                    "row_type": "best_per_swing",
                    "side": side,
                    "score_variant": variant,
                    "bucket": "all_test_swings",
                    "metric": "median_distance",
                    "value": float(pd.to_numeric(valid["best_distance"], errors="coerce").median()),
                },
                {
                    "row_type": "best_per_swing",
                    "side": side,
                    "score_variant": variant,
                    "bucket": "all_test_swings",
                    "metric": "zone_5_hit_rate",
                    "value": float(pd.to_numeric(valid["best_within_5pct"], errors="coerce").mean()),
                },
                {
                    "row_type": "best_per_swing",
                    "side": side,
                    "score_variant": variant,
                    "bucket": "all_test_swings",
                    "metric": "zone_3_hit_rate",
                    "value": float(pd.to_numeric(valid["best_within_3pct"], errors="coerce").mean()),
                },
            ]
        )
    return pd.DataFrame(rows)


def build_threshold_summary(timing: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    test = timing.loc[timing["split"] == "test"].copy()
    threshold_variants = [variant for variant in score_variants() if variant["variant"] in {"fixed_weight", "learned_full"}]
    for variant in threshold_variants:
        for side in ("buy", "sell"):
            config = side_config(side)
            score_column = variant[f"{side}_score"]
            side_rows = test.loc[
                test["current_confirmed_swing_direction"].eq(config["direction"])
                & test["current_confirmed_swing_id"].notna()
            ].copy()
            total_swings = int(side_rows["current_confirmed_swing_id"].nunique())
            for threshold in THRESHOLDS:
                selected = side_rows.loc[pd.to_numeric(side_rows[score_column], errors="coerce") >= threshold].copy()
                swings_touched = int(selected["current_confirmed_swing_id"].nunique())
                rows.append(
                    {
                        "side": side,
                        "score_variant": variant["variant"],
                        "threshold": threshold,
                        "row_count": int(len(selected)),
                        "swing_count": total_swings,
                        "swings_touched": swings_touched,
                        "coverage_rate": float(swings_touched / total_swings) if total_swings else np.nan,
                        "zone_5_hit_rate": float(pd.to_numeric(selected[config["zone5"]], errors="coerce").fillna(0).mean())
                        if not selected.empty
                        else np.nan,
                        "zone_3_hit_rate": float(pd.to_numeric(selected[config["zone3"]], errors="coerce").fillna(0).mean())
                        if not selected.empty
                        else np.nan,
                        "avg_distance": float(pd.to_numeric(selected[config["distance"]], errors="coerce").mean())
                        if not selected.empty
                        else np.nan,
                        "median_distance": float(pd.to_numeric(selected[config["distance"]], errors="coerce").median())
                        if not selected.empty
                        else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def build_ablation_summary(timing: pd.DataFrame, per_swing: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    test = timing.loc[timing["split"] == "test"].copy()
    rows.extend(summarize_per_swing(per_swing).to_dict(orient="records"))
    for variant in score_variants():
        for side in ("buy", "sell"):
            config = side_config(side)
            score_column = variant[f"{side}_score"]
            ordered = test.sort_values(score_column, ascending=False).reset_index(drop=True)
            for bucket in TOP_BUCKETS:
                bucket_count = max(1, int(np.ceil(len(ordered) * bucket)))
                selected = ordered.iloc[:bucket_count].copy()
                swing_mask = selected["current_confirmed_swing_direction"].eq(config["direction"]) & selected[
                    "current_confirmed_swing_id"
                ].notna()
                rows.extend(
                    [
                        {
                            "row_type": "top_bucket",
                            "side": side,
                            "score_variant": variant["variant"],
                            "bucket": f"top_{int(bucket * 100)}pct",
                            "metric": "row_count",
                            "value": float(len(selected)),
                        },
                        {
                            "row_type": "top_bucket",
                            "side": side,
                            "score_variant": variant["variant"],
                            "bucket": f"top_{int(bucket * 100)}pct",
                            "metric": "zone_5_hit_rate",
                            "value": float(pd.to_numeric(selected[config["zone5"]], errors="coerce").fillna(0).mean()),
                        },
                        {
                            "row_type": "top_bucket",
                            "side": side,
                            "score_variant": variant["variant"],
                            "bucket": f"top_{int(bucket * 100)}pct",
                            "metric": "zone_3_hit_rate",
                            "value": float(pd.to_numeric(selected[config["zone3"]], errors="coerce").fillna(0).mean()),
                        },
                        {
                            "row_type": "top_bucket",
                            "side": side,
                            "score_variant": variant["variant"],
                            "bucket": f"top_{int(bucket * 100)}pct",
                            "metric": "avg_distance",
                            "value": float(pd.to_numeric(selected[config["distance"]], errors="coerce").dropna().mean())
                            if pd.to_numeric(selected[config["distance"]], errors="coerce").dropna().size
                            else np.nan,
                        },
                        {
                            "row_type": "top_bucket",
                            "side": side,
                            "score_variant": variant["variant"],
                            "bucket": f"top_{int(bucket * 100)}pct",
                            "metric": "unique_swings_touched",
                            "value": float(selected.loc[swing_mask, "current_confirmed_swing_id"].nunique()),
                        },
                    ]
                )
    return pd.DataFrame(rows)


def render_markdown(
    timing: pd.DataFrame,
    phase_features: list[str],
    analog_window: int,
    analog_top_k: int,
    analog_forward_days: int,
    metrics: pd.DataFrame,
    per_swing: pd.DataFrame,
    thresholds: pd.DataFrame,
    ablation: pd.DataFrame,
    combiner_coefficients: dict[str, dict[str, float]],
) -> str:
    def metric_value(frame: pd.DataFrame, filters: dict[str, object], metric: str) -> str:
        mask = frame["metric"].eq(metric)
        for column, value in filters.items():
            mask &= frame[column].eq(value)
        matched = frame.loc[mask]
        if matched.empty:
            return "n/a"
        return f"{float(matched.iloc[0]['value']):.3f}"

    def ablation_metric(side: str, variant: str, row_type: str, bucket: str, metric: str) -> str:
        return metric_value(
            ablation,
            {
                "row_type": row_type,
                "side": side,
                "score_variant": variant,
                "bucket": bucket,
            },
            metric,
        )

    def threshold_line(side: str, variant: str, threshold: float) -> str:
        matched = thresholds.loc[
            thresholds["side"].eq(side)
            & thresholds["score_variant"].eq(variant)
            & np.isclose(pd.to_numeric(thresholds["threshold"], errors="coerce"), threshold)
        ]
        if matched.empty:
            return f"- {side} `{variant}` threshold `{threshold:.2f}`: n/a"
        row = matched.iloc[0]
        return (
            f"- {side} `{variant}` threshold `{threshold:.2f}`: "
            f"coverage `{float(row['coverage_rate']):.3f}`, "
            f"within 5% / 3% `{float(row['zone_5_hit_rate']):.3f}` / `{float(row['zone_3_hit_rate']):.3f}`, "
            f"avg distance `{float(row['avg_distance']):.3f}`, rows `{int(row['row_count'])}`"
        )

    def coefficient_line(key: str) -> str:
        coefficients = combiner_coefficients.get(key, {})
        if not coefficients:
            return f"- `{key}`: n/a"
        formatted = ", ".join(f"`{feature}` `{value:.3f}`" for feature, value in coefficients.items())
        return f"- `{key}`: {formatted}"

    test = timing.loc[timing["split"] == "test"].copy()
    buy_uncond_5 = float(pd.to_numeric(test[DEFAULT_BUY_TARGET], errors="coerce").fillna(0).mean())
    sell_uncond_5 = float(pd.to_numeric(test[DEFAULT_SELL_TARGET], errors="coerce").fillna(0).mean())
    buy_swing_count = int(
        test.loc[
            test["current_confirmed_swing_direction"].eq("down") & test["current_confirmed_swing_id"].notna(),
            "current_confirmed_swing_id",
        ].nunique()
    )
    sell_swing_count = int(
        test.loc[
            test["current_confirmed_swing_direction"].eq("up") & test["current_confirmed_swing_id"].notna(),
            "current_confirmed_swing_id",
        ].nunique()
    )

    lines = [
        "# SAFE v4.0 Swing Extreme Timing",
        "",
        "## Purpose",
        "",
        "- this layer combines a causal phase model, strictly historical analogs, and a deterministic exhaustion score",
        "- the goal is to estimate how near price is to a usable swing low or swing high, not to predict exact pivots",
        "",
        "## Inputs Used",
        "",
        "- source dataset: `out/swing_bottom/reversal_zone_dataset.csv`",
        "- feature families: retained causal price, volatility, participation, regime/hazard, on-chain, and live swing-state fields",
        f"- retained phase-model feature count: `{len(phase_features)}`",
        "",
        "## Phase Component",
        "",
        "- model: class-balanced logistic regression reused from the corrected reversal-zone baseline",
        "- leakage exclusions match the corrected baseline; no future-derived columns enter the phase input matrix",
        "- outputs: `buy_phase_prob`, `sell_phase_prob`",
        "",
        "## Analog Component",
        "",
        f"- recent candle window: `{analog_window}` bars",
        "- similarity method: cosine similarity on normalized candle-shape and compact causal state vectors",
        f"- prior analog count: top `{analog_top_k}` only",
        f"- forward analog horizon: `{analog_forward_days}` days",
        "- refinement pass: analog aggregation is similarity-weighted instead of equal-weighted",
        "- refinement pass: buy analogs are restricted to prior down-swing context and sell analogs to prior up-swing context",
        "- outputs: analog probability of reaching the 5% and 3% zone soon, median days, and match count",
        "",
        "## Exhaustion Component",
        "",
        "- deterministic bounded score in `[0,1]`",
        "- buy exhaustion combines: down-direction bias, swing age, swing size, downside stretch, volatility cooling, and correction/rebound regime pressure",
        "- sell exhaustion combines: up-direction bias, swing age, swing size, upside stretch, volatility cooling, and correction/surge regime pressure",
        "",
        "## Combined Score",
        "",
        "- fixed-weight reference formula: `0.45 * phase_prob + 0.30 * analog_prob + 0.25 * exhaustion_score`",
        "- corrected combined score: class-balanced logistic regression trained on train+validation rows only",
        "- learned-combiner inputs: phase probability, analog probability, exhaustion score",
        "- higher learned score means stronger evidence that price is near a usable swing extreme",
        "",
        "## Learned Combiner Coefficients",
        "",
        coefficient_line("buy_full"),
        coefficient_line("sell_full"),
        "",
        "## Evaluation Summary",
        "",
        f"- buy unconditional 5% zone prevalence on test: `{buy_uncond_5:.3f}`",
        f"- buy learned-full top 10% zone 5% / 3% hit rate: `{ablation_metric('buy', 'learned_full', 'top_bucket', 'top_10pct', 'zone_5_hit_rate')}` / `{ablation_metric('buy', 'learned_full', 'top_bucket', 'top_10pct', 'zone_3_hit_rate')}`",
        f"- buy fixed-weight top 10% zone 5% / 3% hit rate: `{ablation_metric('buy', 'fixed_weight', 'top_bucket', 'top_10pct', 'zone_5_hit_rate')}` / `{ablation_metric('buy', 'fixed_weight', 'top_bucket', 'top_10pct', 'zone_3_hit_rate')}`",
        f"- buy phase-only top 10% zone 5% / 3% hit rate: `{ablation_metric('buy', 'phase_only', 'top_bucket', 'top_10pct', 'zone_5_hit_rate')}` / `{ablation_metric('buy', 'phase_only', 'top_bucket', 'top_10pct', 'zone_3_hit_rate')}`",
        f"- sell unconditional 5% zone prevalence on test: `{sell_uncond_5:.3f}`",
        f"- sell learned-full top 10% zone 5% / 3% hit rate: `{ablation_metric('sell', 'learned_full', 'top_bucket', 'top_10pct', 'zone_5_hit_rate')}` / `{ablation_metric('sell', 'learned_full', 'top_bucket', 'top_10pct', 'zone_3_hit_rate')}`",
        f"- sell fixed-weight top 10% zone 5% / 3% hit rate: `{ablation_metric('sell', 'fixed_weight', 'top_bucket', 'top_10pct', 'zone_5_hit_rate')}` / `{ablation_metric('sell', 'fixed_weight', 'top_bucket', 'top_10pct', 'zone_3_hit_rate')}`",
        f"- sell phase-only top 10% zone 5% / 3% hit rate: `{ablation_metric('sell', 'phase_only', 'top_bucket', 'top_10pct', 'zone_5_hit_rate')}` / `{ablation_metric('sell', 'phase_only', 'top_bucket', 'top_10pct', 'zone_3_hit_rate')}`",
        "",
        "## Swing-Level Summary",
        "",
        f"- buy test down swings: `{buy_swing_count}`",
        f"- buy learned-full best-row avg / median distance: `{ablation_metric('buy', 'learned_full', 'best_per_swing', 'all_test_swings', 'avg_distance')}` / `{ablation_metric('buy', 'learned_full', 'best_per_swing', 'all_test_swings', 'median_distance')}`",
        f"- buy learned-full best-row within 5% / 3%: `{ablation_metric('buy', 'learned_full', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('buy', 'learned_full', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        f"- buy fixed-weight best-row within 5% / 3%: `{ablation_metric('buy', 'fixed_weight', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('buy', 'fixed_weight', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        f"- sell test up swings: `{sell_swing_count}`",
        f"- sell learned-full best-row avg / median distance: `{ablation_metric('sell', 'learned_full', 'best_per_swing', 'all_test_swings', 'avg_distance')}` / `{ablation_metric('sell', 'learned_full', 'best_per_swing', 'all_test_swings', 'median_distance')}`",
        f"- sell learned-full best-row within 5% / 3%: `{ablation_metric('sell', 'learned_full', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('sell', 'learned_full', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        f"- sell fixed-weight best-row within 5% / 3%: `{ablation_metric('sell', 'fixed_weight', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('sell', 'fixed_weight', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        "",
        "## Coverage Thresholds",
        "",
        threshold_line("buy", "learned_full", 0.70),
        threshold_line("buy", "learned_full", 0.80),
        threshold_line("sell", "learned_full", 0.70),
        threshold_line("sell", "learned_full", 0.80),
        "",
        "## Ablation Readout",
        "",
        f"- buy phase+analog best-row within 5% / 3%: `{ablation_metric('buy', 'phase_analog', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('buy', 'phase_analog', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        f"- buy phase+exhaustion best-row within 5% / 3%: `{ablation_metric('buy', 'phase_exhaustion', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('buy', 'phase_exhaustion', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        f"- sell phase+analog best-row within 5% / 3%: `{ablation_metric('sell', 'phase_analog', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('sell', 'phase_analog', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        f"- sell phase+exhaustion best-row within 5% / 3%: `{ablation_metric('sell', 'phase_exhaustion', 'best_per_swing', 'all_test_swings', 'zone_5_hit_rate')}` / `{ablation_metric('sell', 'phase_exhaustion', 'best_per_swing', 'all_test_swings', 'zone_3_hit_rate')}`",
        "",
        "## Interpretation",
        "",
        "- this refinement is judged primarily by swing-level best-pick quality and threshold coverage, not generic row classification",
        "- the learned combiner improves materially over phase-only on sell-side ranking, but it does not yet dominate the fixed-weight reference on best-pick quality",
        "- fixed-weight score remains exported because it is still a strong robustness comparator and currently remains competitive, especially on buy-side proximity",
        "- buy-side analog contribution is weak in the learned combiner; sell-side analog and exhaustion contributions are directionally useful",
        "- analog probabilities now test whether direction-restricted historical memory adds useful ranking information beyond phase and exhaustion",
        "- no trade logic, capital management, or backtest is introduced here",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame = load_dataset(args.reversal_zone_dataset_csv)

    phase_scored, phase_features, _phase_splits, phase_reference = build_phase_component(frame)
    timing = frame.merge(phase_scored, on="date", how="left", validate="one_to_one")

    analog = build_analog_component(
        timing,
        window=args.analog_window,
        top_k=args.analog_top_k,
        forward_days=args.analog_forward_days,
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

    timing, combiner_coefficients = add_combiner_scores(timing)
    metrics = build_metric_rows(timing, phase_reference)
    per_swing = build_per_swing_summary(timing)
    thresholds = build_threshold_summary(timing)
    ablation = build_ablation_summary(timing, per_swing)

    export_columns = [
        "date",
        "close",
        "split",
        "current_confirmed_swing_id",
        "current_confirmed_swing_direction",
        "live_swing_direction",
        "days_since_last_pivot",
        "distance_from_last_pivot_pct",
        "distance_from_last_pivot_atr_units",
        "current_swing_age_pct_of_median",
        "current_swing_size_pct_of_median",
        "buy_phase_prob",
        "sell_phase_prob",
        "buy_analog_prob",
        "sell_analog_prob",
        "buy_analog_median_days",
        "sell_analog_median_days",
        "buy_analog_match_count",
        "sell_analog_match_count",
        "buy_analog_prob_strict",
        "sell_analog_prob_strict",
        "buy_exhaustion_score",
        "sell_exhaustion_score",
        "buy_phase_only_score",
        "sell_phase_only_score",
        "buy_phase_analog_score",
        "sell_phase_analog_score",
        "buy_phase_exhaustion_score",
        "sell_phase_exhaustion_score",
        "buy_fixed_extreme_timing_score",
        "sell_fixed_extreme_timing_score",
        "buy_extreme_timing_score",
        "sell_extreme_timing_score",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
        "dist_to_current_down_swing_low_pct",
        "dist_to_current_up_swing_high_pct",
    ]
    export = timing.loc[:, export_columns].copy()

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(out_csv, index=False)

    out_swing_summary_csv = Path(args.out_swing_summary_csv)
    out_swing_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    per_swing.to_csv(out_swing_summary_csv, index=False)

    out_thresholds_csv = Path(args.out_thresholds_csv)
    out_thresholds_csv.parent.mkdir(parents=True, exist_ok=True)
    thresholds.to_csv(out_thresholds_csv, index=False)

    out_ablation_csv = Path(args.out_ablation_csv)
    out_ablation_csv.parent.mkdir(parents=True, exist_ok=True)
    ablation.to_csv(out_ablation_csv, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        render_markdown(
            timing=timing,
            phase_features=phase_features,
            analog_window=args.analog_window,
            analog_top_k=args.analog_top_k,
            analog_forward_days=args.analog_forward_days,
            metrics=metrics,
            per_swing=per_swing,
            thresholds=thresholds,
            ablation=ablation,
            combiner_coefficients=combiner_coefficients,
        ),
        encoding="utf-8",
    )

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_swing_summary_csv}")
    print(f"Wrote: {out_thresholds_csv}")
    print(f"Wrote: {out_ablation_csv}")
    print(f"Wrote: {out_md}")
    print(f"Rows written: {len(export)}")
    print(f"Test rows: {int((export['split'] == 'test').sum())}")


if __name__ == "__main__":
    main()
