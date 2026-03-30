from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.data.loaders import load_daily_price_json
from src.models.path_probabilities import PATH_LABELS, realized_path_outcome_from_ohlc
from src.path_config import DEFAULT_ONCHAIN_FEATURES_JSON_PATH
from src.util.safe_touch_probabilities import load_features


ModelType = Literal["gbt", "rf", "logreg"]
AmbiguityMode = Literal["pessimistic", "optimistic", "skip_ambiguous", "label_as_both_same_day"]

PATH_CLASSIFIER_FEATURES: tuple[str, ...] = (
    "R_3",
    "R_7",
    "R_14",
    "TS_20",
    "TS_50",
    "TS_200",
    "LR_20",
    "LR_50",
    "LR_200",
    "ER_20",
    "ER_50",
    "ER_200",
    "RVR_20",
    "RVR_50",
    "RVR_200",
    "vol_20",
    "atr_pct",
    "parkinson_vol",
    "garman_klass_vol",
    "ewma_vol",
    "upside_semi_vol",
    "downside_semi_vol",
    "band_w",
    "band_pos",
    "dist_from_mean_vol_units",
    "time_since_local_high",
    "time_since_local_low",
    "body_to_range_ratio",
    "upper_wick_ratio",
    "lower_wick_ratio",
    "close_in_range",
    "run_length_up",
    "run_length_down",
    "run_magnitude_up",
    "run_magnitude_down",
    "return_accel",
    "relative_volume_20",
    "volume_z",
    "P_CORE_HMM",
    "P_DRIFT_HMM",
    "P_SHOCK_HMM",
    "P_SURGE_HMM",
    "HMM_CONF",
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
    "direction_safe",
    "E_target_safe",
    "entry_step_safe",
    "conviction_safe",
    "D_score_safe",
    "hard_risk_off_flag_safe",
    "ONCHAIN_VOL_Z",
    "ONCHAIN_DOM_Z",
    "ONCHAIN_WHALE_SHARE_Z",
    "ONCHAIN_AMOUNT_PCT",
    "ONCHAIN_WHALE_TX_PCT",
    "ONCHAIN_DOM_PCT",
)

FEATURE_GROUPS: dict[str, str] = {
    "R_3": "recent_movement",
    "R_7": "recent_movement",
    "R_14": "recent_movement",
    "TS_20": "trend",
    "TS_50": "trend",
    "TS_200": "trend",
    "LR_20": "trend",
    "LR_50": "trend",
    "LR_200": "trend",
    "ER_20": "trend",
    "ER_50": "trend",
    "ER_200": "trend",
    "RVR_20": "trend",
    "RVR_50": "trend",
    "RVR_200": "trend",
    "vol_20": "volatility",
    "atr_pct": "volatility",
    "parkinson_vol": "volatility",
    "garman_klass_vol": "volatility",
    "ewma_vol": "volatility",
    "upside_semi_vol": "volatility",
    "downside_semi_vol": "volatility",
    "band_w": "positioning",
    "band_pos": "positioning",
    "dist_from_mean_vol_units": "positioning",
    "time_since_local_high": "positioning",
    "time_since_local_low": "positioning",
    "body_to_range_ratio": "candles",
    "upper_wick_ratio": "candles",
    "lower_wick_ratio": "candles",
    "close_in_range": "candles",
    "run_length_up": "recent_movement",
    "run_length_down": "recent_movement",
    "run_magnitude_up": "recent_movement",
    "run_magnitude_down": "recent_movement",
    "return_accel": "recent_movement",
    "relative_volume_20": "participation",
    "volume_z": "participation",
    "P_CORE_HMM": "hmm",
    "P_DRIFT_HMM": "hmm",
    "P_SHOCK_HMM": "hmm",
    "P_SURGE_HMM": "hmm",
    "HMM_CONF": "hmm",
    "P_CORRECTION_10D_CAL": "hazard",
    "P_REBOUND_10D_CAL": "hazard",
    "direction_safe": "safe",
    "E_target_safe": "safe",
    "entry_step_safe": "safe",
    "conviction_safe": "safe",
    "D_score_safe": "safe",
    "hard_risk_off_flag_safe": "safe",
    "ONCHAIN_VOL_Z": "onchain",
    "ONCHAIN_DOM_Z": "onchain",
    "ONCHAIN_WHALE_SHARE_Z": "onchain",
    "ONCHAIN_AMOUNT_PCT": "onchain",
    "ONCHAIN_WHALE_TX_PCT": "onchain",
    "ONCHAIN_DOM_PCT": "onchain",
}


@dataclass(frozen=True)
class PathClassifierDataset:
    features: pd.DataFrame
    labels: pd.Series
    meta: pd.DataFrame
    feature_cols: list[str]


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: int
    train_idx: np.ndarray
    test_idx: np.ndarray


def _payload_to_frame(features_json_path: str | Path) -> pd.DataFrame:
    dates, series = load_features(str(features_json_path))
    frame = pd.DataFrame(
        {name: pd.to_numeric(pd.Series(values, index=dates), errors="coerce") for name, values in series.items()}
    )
    frame.index = pd.Index(dates, name="date")
    return frame


def load_combined_feature_frame(
    features_json_path: str | Path,
    *,
    onchain_features_json_path: str | Path | None = None,
) -> pd.DataFrame:
    """Load SAFE features and optionally merge on-chain features by date."""
    frame = _payload_to_frame(features_json_path)

    default_onchain = Path(onchain_features_json_path) if onchain_features_json_path else DEFAULT_ONCHAIN_FEATURES_JSON_PATH
    if default_onchain.exists():
        onchain = _payload_to_frame(default_onchain)
        overlap = [column for column in onchain.columns if column not in frame.columns]
        if overlap:
            frame = frame.join(onchain[overlap], how="left")
    return frame.sort_index()


def available_feature_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in PATH_CLASSIFIER_FEATURES if column in frame.columns]


def build_path_classifier_dataset(
    price_json_path: str | Path,
    features_json_path: str | Path,
    *,
    onchain_features_json_path: str | Path | None = None,
    days: int = 10,
    up_pct: float = 0.02,
    down_pct: float = 0.02,
    ambiguity_mode: AmbiguityMode = "skip_ambiguous",
    min_feature_coverage: float = 0.5,
) -> PathClassifierDataset:
    """Build a supervised dataset with features at ``t`` and path labels over ``t+1..t+H``."""
    if not 0.0 < min_feature_coverage <= 1.0:
        raise ValueError("min_feature_coverage must be in (0, 1].")

    price_frame = load_daily_price_json(str(price_json_path))
    feature_frame = load_combined_feature_frame(
        features_json_path,
        onchain_features_json_path=onchain_features_json_path,
    )
    feature_cols = available_feature_columns(feature_frame)
    if not feature_cols:
        raise ValueError("No supported classifier features are available in the feature frame.")

    rows: list[pd.Series] = []
    labels: list[str] = []
    meta_rows: list[dict[str, Any]] = []

    common_dates = sorted(set(feature_frame.index) & set(price_frame.index.strftime("%Y-%m-%d")))
    for anchor_date in common_dates:
        feature_row = feature_frame.loc[anchor_date, feature_cols]
        if float(feature_row.notna().mean()) < min_feature_coverage:
            continue

        try:
            realized = realized_path_outcome_from_ohlc(
                price_frame,
                anchor_date,
                days=days,
                up_pct=up_pct,
                down_pct=down_pct,
                ambiguity_mode=ambiguity_mode,
            )
        except ValueError:
            continue

        if realized.label is None:
            continue

        rows.append(feature_row)
        labels.append(realized.label)
        meta_rows.append(
            {
                "anchor_date": anchor_date,
                "anchor_close": float(price_frame.loc[pd.Timestamp(anchor_date), "close"]),
                "realized_label": realized.label,
                "realized_forward_return": realized.forward_return,
                "ambiguous_realized": int(realized.ambiguous),
                "ambiguity_type": realized.ambiguity_type,
                "first_upper_day": realized.first_upper_day,
                "first_lower_day": realized.first_lower_day,
                "feature_coverage": float(feature_row.notna().mean()),
            }
        )

    if not rows:
        raise ValueError("No labeled rows available for path classifier training.")

    X = pd.DataFrame(rows, columns=feature_cols)
    X.index = pd.Index([row["anchor_date"] for row in meta_rows], name="anchor_date")
    y = pd.Series(labels, index=X.index, name="path_label")
    meta = pd.DataFrame(meta_rows).set_index("anchor_date")
    return PathClassifierDataset(features=X, labels=y, meta=meta, feature_cols=feature_cols)


def build_base_estimator(model_type: ModelType, seed: int) -> Pipeline:
    """Return a native-probability multiclass model with simple numeric preprocessing."""
    if model_type == "gbt":
        model = GradientBoostingClassifier(
            random_state=seed,
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
        )
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("model", model),
            ]
        )
    if model_type == "rf":
        model = RandomForestClassifier(
            n_estimators=400,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        )
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("model", model),
            ]
        )
    if model_type == "logreg":
        model = LogisticRegression(
            multi_class="multinomial",
            max_iter=2000,
            C=0.5,
            class_weight="balanced",
            random_state=seed,
        )
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", model),
            ]
        )
    raise ValueError(f"Unsupported model_type: {model_type}")


def fit_probabilistic_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    model_type: ModelType,
    seed: int,
    calibration_fraction: float = 0.2,
    calibration_min_rows: int = 80,
) -> tuple[Any, dict[str, Any]]:
    """Fit a multiclass classifier with a simple time-ordered calibration split.

    The calibrator is trained only on the latest slice of the training window.
    If the calibration slice is too small or does not contain enough class
    variety, the function falls back to the base classifier's native
    ``predict_proba`` outputs.
    """
    if len(X_train) != len(y_train):
        raise ValueError("X_train and y_train must have the same length.")
    if len(y_train.unique()) < 2:
        raise ValueError("Need at least two classes in the training data.")

    estimator = build_base_estimator(model_type, seed)
    calibration_rows = max(int(len(X_train) * calibration_fraction), calibration_min_rows)
    calibration_rows = min(calibration_rows, max(0, len(X_train) - 20))

    calibration_used = False
    if calibration_rows >= calibration_min_rows and len(X_train) - calibration_rows >= 50:
        X_fit = X_train.iloc[:-calibration_rows]
        y_fit = y_train.iloc[:-calibration_rows]
        X_cal = X_train.iloc[-calibration_rows:]
        y_cal = y_train.iloc[-calibration_rows:]
        if len(y_fit.unique()) >= 2 and len(y_cal.unique()) >= 2:
            fitted_base = clone(estimator).fit(X_fit, y_fit)
            try:
                calibrator = CalibratedClassifierCV(estimator=fitted_base, method="sigmoid", cv="prefit")
            except TypeError:
                calibrator = CalibratedClassifierCV(base_estimator=fitted_base, method="sigmoid", cv="prefit")
            try:
                calibrator.fit(X_cal, y_cal)
            except Exception:
                calibrator = None
            if calibrator is not None:
                calibration_used = True
                return calibrator, {
                    "model_type": model_type,
                    "calibration_used": calibration_used,
                    "fit_rows": int(len(X_fit)),
                    "calibration_rows": int(len(X_cal)),
                }

    fitted = estimator.fit(X_train, y_train)
    return fitted, {
        "model_type": model_type,
        "calibration_used": calibration_used,
        "fit_rows": int(len(X_train)),
        "calibration_rows": 0,
    }


def generate_walk_forward_folds(
    dataset: PathClassifierDataset,
    *,
    train_start_date: str | None,
    eval_start_date: str | None,
    eval_end_date: str | None,
    min_train_rows: int,
    fold_size_days: int,
    expanding_window: bool,
) -> list[WalkForwardFold]:
    """Generate time-ordered expanding or rolling evaluation folds."""
    dates = list(dataset.features.index)
    eval_positions = [
        idx
        for idx, date in enumerate(dates)
        if (eval_start_date is None or date >= eval_start_date)
        and (eval_end_date is None or date <= eval_end_date)
    ]
    if not eval_positions:
        raise ValueError("No evaluation dates fall inside the requested range.")

    if train_start_date is None:
        train_start_position = 0
    else:
        train_start_position = next((idx for idx, date in enumerate(dates) if date >= train_start_date), len(dates))
        if train_start_position >= len(dates):
            raise ValueError("train_start_date is after the available dataset.")

    folds: list[WalkForwardFold] = []
    fold_id = 0
    start = 0
    while start < len(eval_positions):
        test_idx = np.array(eval_positions[start:start + fold_size_days], dtype=int)
        if test_idx.size == 0:
            break
        test_start = int(test_idx[0])
        if expanding_window:
            train_start = train_start_position
        else:
            train_start = max(train_start_position, test_start - min_train_rows)
        train_idx = np.arange(train_start, test_start, dtype=int)
        if train_idx.size >= min_train_rows:
            folds.append(WalkForwardFold(fold_id=fold_id, train_idx=train_idx, test_idx=test_idx))
            fold_id += 1
        start += fold_size_days

    if not folds:
        raise ValueError("No folds satisfy the minimum training-row requirement.")
    return folds


def feature_importance_frame(estimator: Any, feature_cols: list[str], model_type: ModelType) -> pd.DataFrame:
    """Return a global feature-importance table for the fitted model."""
    model = estimator
    if hasattr(estimator, "calibrated_classifiers_"):
        calibrated = estimator.calibrated_classifiers_[0]
        if hasattr(calibrated, "estimator"):
            model = calibrated.estimator
        elif hasattr(calibrated, "base_estimator"):
            model = calibrated.base_estimator
        elif hasattr(estimator, "estimator"):
            model = estimator.estimator

    if isinstance(model, Pipeline):
        final_model = model.named_steps["model"]
    else:
        final_model = model

    if hasattr(final_model, "feature_importances_"):
        importance = np.asarray(final_model.feature_importances_, dtype=float)
    elif hasattr(final_model, "coef_"):
        importance = np.mean(np.abs(np.asarray(final_model.coef_, dtype=float)), axis=0)
    else:
        importance = np.zeros(len(feature_cols), dtype=float)

    frame = pd.DataFrame(
        {
            "feature": feature_cols,
            "importance": importance,
            "group": [FEATURE_GROUPS.get(feature, "other") for feature in feature_cols],
        }
    )
    frame = frame.sort_values("importance", ascending=False).reset_index(drop=True)
    return frame


def save_model_pack(
    path: Path,
    *,
    model: Any,
    feature_cols: list[str],
    feature_groups: dict[str, str],
    model_type: ModelType,
    days: int,
    up_pct: float,
    down_pct: float,
    ambiguity_mode: AmbiguityMode,
    train_rows: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_cols": feature_cols,
            "feature_groups": feature_groups,
            "model_type": model_type,
            "days": days,
            "up_pct": up_pct,
            "down_pct": down_pct,
            "ambiguity_mode": ambiguity_mode,
            "classes": list(PATH_LABELS),
            "model_classes": [str(label) for label in getattr(model, "classes_", list(PATH_LABELS))],
            "train_rows": train_rows,
        },
        path,
    )


def load_model_pack(path: str | Path) -> dict[str, Any]:
    return joblib.load(Path(path))


def predict_probabilities_for_date(
    model_pack: dict[str, Any],
    *,
    features_json_path: str | Path,
    price_json_path: str | Path,
    date: str,
    onchain_features_json_path: str | Path | None = None,
) -> dict[str, Any]:
    """Predict path-class probabilities for one anchor date using a saved model pack."""
    feature_frame = load_combined_feature_frame(
        features_json_path,
        onchain_features_json_path=onchain_features_json_path,
    )
    if date not in feature_frame.index:
        raise KeyError(f"Anchor date {date} not found in feature data.")

    feature_cols = list(model_pack["feature_cols"])
    missing = [column for column in feature_cols if column not in feature_frame.columns]
    if missing:
        raise ValueError(f"Feature frame is missing required model columns: {missing}")

    X_row = feature_frame.loc[[date], feature_cols]
    probabilities = model_pack["model"].predict_proba(X_row)[0]
    classes = list(model_pack.get("classes", PATH_LABELS))
    model_classes = list(model_pack.get("model_classes", classes))
    probability_map = {label: 0.0 for label in classes}
    for label, prob in zip(model_classes, probabilities):
        probability_map[str(label)] = float(prob)

    price_frame = load_daily_price_json(str(price_json_path))
    anchor_close = float(price_frame.loc[pd.Timestamp(date), "close"])
    top1 = max(probability_map, key=probability_map.get)
    top2 = sorted(probability_map, key=probability_map.get, reverse=True)[:2]

    return {
        "anchor_date": date,
        "anchor_close": anchor_close,
        "days": int(model_pack["days"]),
        "barriers": {
            "up_pct": float(model_pack["up_pct"]),
            "down_pct": float(model_pack["down_pct"]),
            "upper_price": anchor_close * (1.0 + float(model_pack["up_pct"])),
            "lower_price": anchor_close * (1.0 - float(model_pack["down_pct"])),
        },
        "path_probabilities": probability_map,
        "top1_class": top1,
        "top2_classes": top2,
        "feature_snapshot": {
            column: (None if pd.isna(value) else float(value))
            for column, value in X_row.iloc[0].items()
        },
        "model_type": model_pack["model_type"],
    }
