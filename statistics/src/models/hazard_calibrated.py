from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DEFAULT_HAZARD_FEATURE_COLS: tuple[str, ...] = (
    "TS_50",
    "ER_20",
    "atr_pct",
    "ewma_vol",
    "band_pos",
    "band_w",
    "dist_from_mean_vol_units",
    "run_length_up",
    "run_length_down",
    "return_accel",
    "relative_volume_20",
)
# Backward-compatible alias for callers that import FEATURE_COLS.
FEATURE_COLS: tuple[str, ...] = DEFAULT_HAZARD_FEATURE_COLS


@dataclass(frozen=True)
class HazardConfig:
    """Configuration for calibrated horizon-specific correction and rebound models.

    A correction event means the market reaches a sufficiently deep adverse move
    within the next ``horizon_days``. A rebound event means the market reaches a
    sufficiently strong positive move within the same horizon. Event thresholds
    are estimated from training-period forward excursion quantiles only.
    """

    horizon_days: int = 10
    corr_quantile: float = 0.70
    rebound_quantile: float = 0.70
    min_train_rows: int = 800
    min_calibration_rows: int = 200
    min_test_rows: int = 200
    test_fraction: float = 0.20
    calibration_fraction: float = 0.20
    logistic_c: float = 1.0
    clip_probability: float = 1e-6
    feature_cols: tuple[str, ...] | None = None


ModelBundle = dict[str, Any]


def _resolve_feature_cols(cfg: HazardConfig) -> tuple[str, ...]:
    return tuple(cfg.feature_cols) if cfg.feature_cols is not None else DEFAULT_HAZARD_FEATURE_COLS


def _validate_feature_columns(features: pd.DataFrame, feature_cols: tuple[str, ...]) -> None:
    missing_columns = [column for column in feature_cols if column not in features.columns]
    if missing_columns:
        raise ValueError(
            "Hazard model is missing required descriptive inputs: "
            f"{missing_columns}. Expected fixed feature set: {list(feature_cols)}."
        )


def _forward_rolling_extreme(series: pd.Series, horizon: int, mode: str) -> pd.Series:
    """Compute a forward rolling min/max over the next ``horizon`` rows."""
    shifted = series.shift(-1)
    reversed_shifted = shifted.iloc[::-1]
    if mode == "min":
        extreme = reversed_shifted.rolling(horizon, min_periods=horizon).min()
    elif mode == "max":
        extreme = reversed_shifted.rolling(horizon, min_periods=horizon).max()
    else:
        raise ValueError(f"Unsupported forward extreme mode: {mode}")
    return extreme.iloc[::-1]


def _build_forward_excursions(features: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, dict[str, str]]:
    if "close" not in features.columns:
        raise ValueError("Hazard modeling requires a 'close' column.")

    close = pd.to_numeric(features["close"], errors="coerce")
    if close.isna().any():
        raise ValueError("Column 'close' contains invalid values for hazard modeling.")

    downside_source_name = "low" if "low" in features.columns else "close"
    upside_source_name = "high" if "high" in features.columns else "close"
    downside_source = pd.to_numeric(features[downside_source_name], errors="coerce")
    upside_source = pd.to_numeric(features[upside_source_name], errors="coerce")

    if downside_source.isna().any():
        raise ValueError(f"Column '{downside_source_name}' contains invalid values for hazard modeling.")
    if upside_source.isna().any():
        raise ValueError(f"Column '{upside_source_name}' contains invalid values for hazard modeling.")

    future_low = _forward_rolling_extreme(downside_source, horizon, mode="min")
    future_high = _forward_rolling_extreme(upside_source, horizon, mode="max")

    excursions = pd.DataFrame(
        {
            "future_correction_move": (future_low / close) - 1.0,
            "future_rebound_move": (future_high / close) - 1.0,
        },
        index=features.index,
    )
    source_meta = {
        "correction_source": downside_source_name,
        "rebound_source": upside_source_name,
    }
    return excursions, source_meta


def _estimate_event_thresholds(train_excursions: pd.DataFrame, cfg: HazardConfig) -> dict[str, float]:
    corr_moves = train_excursions["future_correction_move"].dropna()
    reb_moves = train_excursions["future_rebound_move"].dropna()
    if corr_moves.empty or reb_moves.empty:
        raise ValueError("Training excursion series is empty; cannot estimate hazard thresholds.")

    x_corr = float(np.quantile((-corr_moves).to_numpy(dtype=float), cfg.corr_quantile))
    y_rebound = float(np.quantile(reb_moves.to_numpy(dtype=float), cfg.rebound_quantile))
    return {
        "X_corr": x_corr,
        "Y_rebound": y_rebound,
    }


def make_event_labels(
    features: pd.DataFrame,
    cfg: HazardConfig,
    thresholds: dict[str, float] | None = None,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    """Create horizon-specific correction and rebound event labels.

    Correction is defined from the forward minimum of ``low`` when available,
    otherwise ``close`` as a documented fallback. Rebound is defined from the
    forward maximum of ``high`` when available, otherwise ``close``.
    """
    excursions, source_meta = _build_forward_excursions(features, cfg.horizon_days)
    if thresholds is None:
        thresholds = _estimate_event_thresholds(excursions, cfg)

    y_corr = pd.Series(np.nan, index=features.index, dtype=float)
    y_reb = pd.Series(np.nan, index=features.index, dtype=float)

    corr_mask = excursions["future_correction_move"].notna()
    reb_mask = excursions["future_rebound_move"].notna()
    y_corr.loc[corr_mask] = (
        excursions.loc[corr_mask, "future_correction_move"] < -thresholds["X_corr"]
    ).astype(int)
    y_reb.loc[reb_mask] = (
        excursions.loc[reb_mask, "future_rebound_move"] > thresholds["Y_rebound"]
    ).astype(int)

    meta = {
        "horizon_days": cfg.horizon_days,
        "corr_quantile": cfg.corr_quantile,
        "rebound_quantile": cfg.rebound_quantile,
        **thresholds,
        **source_meta,
    }
    return y_corr, y_reb, meta


def _make_base_model(cfg: HazardConfig) -> Pipeline:
    """Create the base logistic model used before temporal calibration."""
    return Pipeline(
        [
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    solver="lbfgs",
                    class_weight="balanced",
                    C=cfg.logistic_c,
                ),
            ),
        ]
    )


def _make_calibrator() -> LogisticRegression:
    """Platt-style calibrator fit on a forward-held calibration segment."""
    return LogisticRegression(max_iter=1000, solver="lbfgs")


def _temporal_split_bounds(n_rows: int, cfg: HazardConfig) -> dict[str, int]:
    min_total_rows = cfg.min_train_rows + cfg.min_calibration_rows + cfg.min_test_rows
    if n_rows < min_total_rows:
        raise ValueError(
            "Not enough labeled rows for hazard training. "
            f"Need at least {min_total_rows}, got {n_rows}."
        )

    test_rows = max(int(round(n_rows * cfg.test_fraction)), cfg.min_test_rows)
    test_rows = min(test_rows, n_rows - cfg.min_train_rows - cfg.min_calibration_rows)
    if test_rows < cfg.min_test_rows:
        raise ValueError(
            "Not enough rows to allocate the required hazard test holdout. "
            f"Need at least {cfg.min_test_rows}, got {test_rows}."
        )

    pretest_rows = n_rows - test_rows
    calibration_rows = max(int(round(pretest_rows * cfg.calibration_fraction)), cfg.min_calibration_rows)
    calibration_rows = min(calibration_rows, pretest_rows - cfg.min_train_rows)
    if calibration_rows < cfg.min_calibration_rows:
        raise ValueError(
            "Not enough rows to allocate the required hazard calibration holdout. "
            f"Need at least {cfg.min_calibration_rows}, got {calibration_rows}."
        )

    train_rows = pretest_rows - calibration_rows
    if train_rows < cfg.min_train_rows:
        raise ValueError(
            "Not enough rows to allocate the required hazard training segment. "
            f"Need at least {cfg.min_train_rows}, got {train_rows}."
        )

    return {
        "train_end": train_rows,
        "calibration_end": pretest_rows,
        "test_end": n_rows,
        "train_rows": train_rows,
        "calibration_rows": calibration_rows,
        "test_rows": test_rows,
    }


def _validate_binary_segment(y: pd.Series, segment_name: str) -> None:
    classes = set(y.astype(int).tolist())
    if classes != {0, 1}:
        raise ValueError(
            f"Hazard segment '{segment_name}' must contain both classes; got classes={sorted(classes)}."
        )


def _safe_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    return float(roc_auc_score(y_true, y_prob))


def _safe_pr_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    return float(average_precision_score(y_true, y_prob))


def _reliability_table(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 10) -> list[dict[str, Any]]:
    if len(y_true) == 0:
        return []

    frame = pd.DataFrame({"y_true": y_true, "y_prob": y_prob})
    try:
        frame["bucket"] = pd.qcut(frame["y_prob"], q=min(bins, len(frame)), duplicates="drop")
    except ValueError:
        return []

    reliability: list[dict[str, Any]] = []
    for interval, group in frame.groupby("bucket", observed=True):
        reliability.append(
            {
                "bin": str(interval),
                "count": int(len(group)),
                "mean_pred": float(group["y_prob"].mean()),
                "event_rate": float(group["y_true"].mean()),
            }
        )
    return reliability


def _calibrated_probabilities(
    base_model: Pipeline,
    calibrator: LogisticRegression,
    X: np.ndarray,
    clip_probability: float,
) -> np.ndarray:
    raw_score = base_model.decision_function(X).reshape(-1, 1)
    prob = calibrator.predict_proba(raw_score)[:, 1]
    return np.clip(prob, clip_probability, 1.0 - clip_probability)


def _fit_single_hazard_model(
    labeled: pd.DataFrame,
    target_col: str,
    feature_cols: tuple[str, ...],
    cfg: HazardConfig,
    split_bounds: dict[str, int],
    event_label: str,
) -> tuple[Pipeline, LogisticRegression, dict[str, Any]]:
    required_columns = list(feature_cols) + [target_col]
    task_frame = labeled.dropna(subset=required_columns).copy()
    if task_frame.empty:
        raise ValueError(f"No usable rows remain for hazard model '{event_label}'.")

    train_cutoff = labeled.index[split_bounds["train_end"] - 1]
    calibration_cutoff = labeled.index[split_bounds["calibration_end"] - 1]

    model_train = task_frame.loc[task_frame.index <= train_cutoff]
    calibration = task_frame.loc[(task_frame.index > train_cutoff) & (task_frame.index <= calibration_cutoff)]
    test = task_frame.loc[task_frame.index > calibration_cutoff]
    pretest = task_frame.loc[task_frame.index <= calibration_cutoff]

    if len(model_train) < cfg.min_train_rows:
        raise ValueError(
            f"Hazard model '{event_label}' has too few training rows after input filtering: "
            f"{len(model_train)} < {cfg.min_train_rows}."
        )
    if len(calibration) < cfg.min_calibration_rows:
        raise ValueError(
            f"Hazard model '{event_label}' has too few calibration rows after input filtering: "
            f"{len(calibration)} < {cfg.min_calibration_rows}."
        )
    if len(test) < cfg.min_test_rows:
        raise ValueError(
            f"Hazard model '{event_label}' has too few test rows after input filtering: "
            f"{len(test)} < {cfg.min_test_rows}."
        )

    _validate_binary_segment(model_train[target_col], f"{event_label}_train")
    _validate_binary_segment(calibration[target_col], f"{event_label}_calibration")

    X_model_train = model_train.loc[:, feature_cols].to_numpy(dtype=float)
    y_model_train = model_train[target_col].to_numpy(dtype=int)
    X_calibration = calibration.loc[:, feature_cols].to_numpy(dtype=float)
    y_calibration = calibration[target_col].to_numpy(dtype=int)
    X_pretest = pretest.loc[:, feature_cols].to_numpy(dtype=float)
    y_pretest = pretest[target_col].to_numpy(dtype=int)
    X_test = test.loc[:, feature_cols].to_numpy(dtype=float)
    y_test = test[target_col].to_numpy(dtype=int)

    base_model = _make_base_model(cfg)
    base_model.fit(X_model_train, y_model_train)

    calibrator = _make_calibrator()
    calibration_scores = base_model.decision_function(X_calibration).reshape(-1, 1)
    calibrator.fit(calibration_scores, y_calibration)

    p_train = _calibrated_probabilities(base_model, calibrator, X_pretest, cfg.clip_probability)
    p_test = _calibrated_probabilities(base_model, calibrator, X_test, cfg.clip_probability)

    diagnostics = {
        "feature_cols": list(feature_cols),
        "usable_rows": int(len(task_frame)),
        "dropped_rows_missing_inputs": int(len(labeled) - len(task_frame)),
        "train_size": int(len(pretest)),
        "base_train_size": int(len(model_train)),
        "calibration_size": int(len(calibration)),
        "test_size": int(len(test)),
        "positive_rate_train": float(y_pretest.mean()),
        "positive_rate_test": float(y_test.mean()),
        "pred_mean_train": float(np.mean(p_train)),
        "pred_mean_test": float(np.mean(p_test)),
        "brier_test": float(brier_score_loss(y_test, p_test)),
        "log_loss_test": float(log_loss(y_test, p_test, labels=[0, 1])),
        "roc_auc_test": _safe_auc(y_test, p_test),
        "pr_auc_test": _safe_pr_auc(y_test, p_test),
        "calibration_test": _reliability_table(y_test, p_test),
        "train_start": pretest.index.min().strftime("%Y-%m-%d"),
        "train_end": pretest.index.max().strftime("%Y-%m-%d"),
        "test_start": test.index.min().strftime("%Y-%m-%d"),
        "test_end": test.index.max().strftime("%Y-%m-%d"),
    }
    return base_model, calibrator, diagnostics


def train_hazard_models(features: pd.DataFrame, cfg: HazardConfig) -> dict[str, Any]:
    """Train calibrated correction and rebound models on descriptive OHLCV features.

    Both targets are horizon-specific event probabilities. Correction is based
    on forward downside excursion to future ``low``. Rebound is based on forward
    upside excursion to future ``high``. Thresholds are estimated only from the
    pre-test training segment to avoid leakage from the held-out test period.
    """
    feature_cols = _resolve_feature_cols(cfg)
    _validate_feature_columns(features, feature_cols)

    excursions, source_meta = _build_forward_excursions(features, cfg.horizon_days)
    labeled = pd.concat([features.loc[:, feature_cols], excursions], axis=1)
    labeled = labeled.dropna(subset=["future_correction_move", "future_rebound_move"])
    if labeled.empty:
        raise ValueError("No labeled rows remain after building forward hazard excursions.")

    split_bounds = _temporal_split_bounds(len(labeled), cfg)
    pretest = labeled.iloc[:split_bounds["calibration_end"]].copy()
    thresholds = _estimate_event_thresholds(pretest, cfg)

    y_corr, y_reb, label_meta = make_event_labels(features, cfg, thresholds=thresholds)
    labeled["y_corr"] = y_corr.loc[labeled.index]
    labeled["y_reb"] = y_reb.loc[labeled.index]

    model_corr, calibrator_corr, corr_diag = _fit_single_hazard_model(
        labeled=labeled,
        target_col="y_corr",
        feature_cols=feature_cols,
        cfg=cfg,
        split_bounds=split_bounds,
        event_label="correction",
    )
    model_reb, calibrator_reb, reb_diag = _fit_single_hazard_model(
        labeled=labeled,
        target_col="y_reb",
        feature_cols=feature_cols,
        cfg=cfg,
        split_bounds=split_bounds,
        event_label="rebound",
    )

    diagnostics = {
        "rows_with_excursions": int(len(labeled)),
        "total_input_rows": int(len(features)),
        "rows_dropped_before_modeling": int(len(features) - len(labeled)),
        "split_bounds": split_bounds,
        "correction": corr_diag,
        "rebound": reb_diag,
    }
    meta = {
        **label_meta,
        "feature_cols": list(feature_cols),
        "test_fraction": cfg.test_fraction,
        "calibration_fraction": cfg.calibration_fraction,
        "clip_probability": cfg.clip_probability,
        "training_policy": "time-ordered split with separate train, calibration, and test segments",
        "calibration_method": "Platt scaling on forward-held calibration segment",
        **source_meta,
    }

    return {
        "meta": meta,
        "feature_cols": list(feature_cols),
        "model_corr": model_corr,
        "calibrator_corr": calibrator_corr,
        "model_reb": model_reb,
        "calibrator_reb": calibrator_reb,
        "diagnostics": diagnostics,
        "test_corr_rate": corr_diag["positive_rate_test"],
        "test_corr_pred_mean": corr_diag["pred_mean_test"],
        "test_reb_rate": reb_diag["positive_rate_test"],
        "test_reb_pred_mean": reb_diag["pred_mean_test"],
    }


def apply_hazard_models(features: pd.DataFrame, model_pack: dict[str, Any]) -> pd.DataFrame:
    """Apply calibrated 10-day hazard probabilities to the feature table.

    Outputs:
    - ``P_CORRECTION_10D_CAL``: calibrated probability of a threshold-sized
      downside move within the configured horizon.
    - ``P_REBOUND_10D_CAL``: calibrated probability of a threshold-sized upside
      move within the configured horizon.
    Rows with missing hazard inputs remain ``NaN``.
    """
    df = features.copy()
    feature_cols = tuple(model_pack["feature_cols"])
    _validate_feature_columns(df, feature_cols)

    valid = df.dropna(subset=list(feature_cols))
    df["P_CORRECTION_10D_CAL"] = np.nan
    df["P_REBOUND_10D_CAL"] = np.nan
    if valid.empty:
        return df

    X = valid.loc[:, feature_cols].to_numpy(dtype=float)
    p_corr = _calibrated_probabilities(
        model_pack["model_corr"],
        model_pack["calibrator_corr"],
        X,
        clip_probability=float(model_pack.get("meta", {}).get("clip_probability", 1e-6)),
    )
    p_reb = _calibrated_probabilities(
        model_pack["model_reb"],
        model_pack["calibrator_reb"],
        X,
        clip_probability=float(model_pack.get("meta", {}).get("clip_probability", 1e-6)),
    )

    df.loc[valid.index, "P_CORRECTION_10D_CAL"] = p_corr
    df.loc[valid.index, "P_REBOUND_10D_CAL"] = p_reb
    return df
