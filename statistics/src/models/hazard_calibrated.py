from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class HazardConfig:
    horizon_days: int = 10
    # event thresholds are adaptive: quantiles of future extremes distribution
    corr_quantile: float = 0.70     # how "common" a correction event is
    rebound_quantile: float = 0.70  # how "common" a rebound event is
    min_train_rows: int = 800


FEATURE_COLS = [
    # core regime/features
    "TS_20", "TS_50", "TS_200",
    "band_w", "band_pos",
    "range_score",
    "speed_z", "vol_z",
    "RL_pos", "RL_neg",
]


def _future_min_max(close: pd.Series, horizon: int) -> tuple[pd.Series, pd.Series]:
    """
    For each t, compute min/max of close in (t+1 ... t+horizon).
    Uses shifting + rolling on reversed direction trick.
    """
    # shift by -1 so future window starts at t+1
    fut = close.shift(-1)

    fut_min = fut.rolling(horizon, min_periods=horizon).min()
    fut_max = fut.rolling(horizon, min_periods=horizon).max()
    return fut_min, fut_max


def make_event_labels(features: pd.DataFrame, cfg: HazardConfig) -> tuple[pd.Series, pd.Series, dict]:
    """
    Returns:
      y_corr: 1 if correction event happens within horizon
      y_reb:  1 if rebound event happens within horizon
      meta: thresholds used (X,Y)
    """
    if "close" not in features.columns:
        raise ValueError("features must contain 'close'.")

    close = features["close"].astype(float)
    fut_min, fut_max = _future_min_max(close, cfg.horizon_days)

    # compute future drawdown and rally magnitudes (fractional)
    dd = (fut_min / close) - 1.0  # negative values
    rr = (fut_max / close) - 1.0  # positive values

    # adaptive thresholds from historical distribution (drop nan)
    dd_clean = dd.dropna()
    rr_clean = rr.dropna()

    # correction threshold X is a positive number; event when dd < -X
    # pick X so that events are neither too rare nor too common
    # Example: corr_quantile=0.70 -> X is at 70th percentile of (-dd)
    X = float(np.quantile((-dd_clean).values, cfg.corr_quantile))
    Y = float(np.quantile((rr_clean).values, cfg.rebound_quantile))

    y_corr = (dd < -X).astype(int)
    y_reb = (rr > Y).astype(int)

    meta = {"horizon_days": cfg.horizon_days, "X_corr": X, "Y_rebound": Y,
            "corr_quantile": cfg.corr_quantile, "rebound_quantile": cfg.rebound_quantile}
    return y_corr, y_reb, meta


def _make_model() -> Pipeline:
    base = LogisticRegression(
        max_iter=2000,
        solver="lbfgs",
        class_weight="balanced",
    )
    # scale improves LR stability
    pipe = Pipeline([
        ("scaler", StandardScaler(with_mean=True, with_std=True)),
        ("clf", base),
    ])
    # isotonic calibration tends to work well for probabilities (needs enough data)
    cal = CalibratedClassifierCV(pipe, method="isotonic", cv=3)
    return cal


def train_hazard_models(features: pd.DataFrame, cfg: HazardConfig) -> dict:
    """
    Trains two calibrated models:
      - correction model
      - rebound model
    Returns dict containing models and metadata.
    """
    # Build labels
    y_corr, y_reb, meta = make_event_labels(features, cfg)

    df = features.copy()
    df["y_corr"] = y_corr
    df["y_reb"] = y_reb

    # Use rows where features + labels are available
    df = df.dropna(subset=FEATURE_COLS + ["y_corr", "y_reb"])

    if len(df) < cfg.min_train_rows:
        raise ValueError(f"Not enough training rows: {len(df)} < {cfg.min_train_rows}")

    # Temporal split: last 20% held out for sanity (still used inside calibration CV, but ok)
    n = len(df)
    split = int(n * 0.80)
    train = df.iloc[:split]
    test = df.iloc[split:]

    X_train = train[FEATURE_COLS].values
    X_test = test[FEATURE_COLS].values

    out = {"meta": meta, "feature_cols": FEATURE_COLS}

    # Correction model
    m_corr = _make_model()
    m_corr.fit(X_train, train["y_corr"].values)
    p_corr_test = m_corr.predict_proba(X_test)[:, 1]
    out["model_corr"] = m_corr
    out["test_corr_rate"] = float(test["y_corr"].mean())
    out["test_corr_pred_mean"] = float(np.mean(p_corr_test))

    # Rebound model
    m_reb = _make_model()
    m_reb.fit(X_train, train["y_reb"].values)
    p_reb_test = m_reb.predict_proba(X_test)[:, 1]
    out["model_reb"] = m_reb
    out["test_reb_rate"] = float(test["y_reb"].mean())
    out["test_reb_pred_mean"] = float(np.mean(p_reb_test))

    return out


def apply_hazard_models(features: pd.DataFrame, model_pack: dict) -> pd.DataFrame:
    """
    Adds calibrated probabilities to features:
      P_CORRECTION_10D_CAL
      P_REBOUND_10D_CAL
    """
    df = features.copy()
    cols = model_pack["feature_cols"]
    valid = df.dropna(subset=cols)
    if valid.empty:
        df["P_CORRECTION_10D_CAL"] = np.nan
        df["P_REBOUND_10D_CAL"] = np.nan
        return df

    X = valid[cols].values

    m_corr = model_pack["model_corr"]
    m_reb = model_pack["model_reb"]

    df["P_CORRECTION_10D_CAL"] = np.nan
    df["P_REBOUND_10D_CAL"] = np.nan
    df.loc[valid.index, "P_CORRECTION_10D_CAL"] = m_corr.predict_proba(X)[:, 1]
    df.loc[valid.index, "P_REBOUND_10D_CAL"] = m_reb.predict_proba(X)[:, 1]
    return df
