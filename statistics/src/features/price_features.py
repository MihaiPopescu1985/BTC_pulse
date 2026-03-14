from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np
import pandas as pd


# -----------------------------
# Helpers
# -----------------------------

def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def _zscore(s: pd.Series, win: int) -> pd.Series:
    mu = s.rolling(win, min_periods=win).mean()
    sd = s.rolling(win, min_periods=win).std(ddof=0)
    return (s - mu) / sd.replace(0, np.nan)


def _rolling_quantile(s: pd.Series, win: int, q: float) -> pd.Series:
    # rolling quantile can be slow, but OK for daily data (~3k rows).
    return s.rolling(win, min_periods=win).quantile(q)


def _clip01(s: pd.Series) -> pd.Series:
    return s.clip(lower=0.0, upper=1.0)


def _compute_range_score(features: pd.DataFrame, cfg: FeatureConfig) -> pd.Series:
    ts_abs = features["TS_50"].abs()
    ts_low = -_zscore(ts_abs, win=cfg.adapt_win)  # high when TS is low
    bw_low = -_zscore(features["band_w"], win=cfg.adapt_win)  # high when band width is low
    sw_hi = _zscore(features["switch_rate_50"], win=cfg.adapt_win)  # high when switches are high

    range_raw = (
        0.9 * ts_low.fillna(0)
        + 0.7 * bw_low.fillna(0)
        + 0.6 * sw_hi.fillna(0)
    )
    return _clip01(pd.Series(_sigmoid(cfg.range_scale * range_raw), index=features.index))

# -----------------------------
# Configuration
# -----------------------------

@dataclass(frozen=True)
class FeatureConfig:
    # Core horizons
    ret_fast: int = 3
    ret_mid: int = 7
    ret_slow: int = 14

    trend_win_short: int = 20
    trend_win_mid: int = 50
    trend_win_long: int = 200

    band_win: int = 100

    # Rolling window for adaptive thresholds (non-stationarity)
    adapt_win: int = 365 * 2  # 2y

    # Probability mapping scales (tunable)
    ts_scale: float = 1.35
    range_scale: float = 1.15
    speed_scale: float = 1.25
    runlen_scale: float = 0.08


# -----------------------------
# Feature computation
# -----------------------------

def compute_price_features(df: pd.DataFrame, cfg: FeatureConfig = FeatureConfig()) -> pd.DataFrame:
    """
    Input:
      df: index=date (DatetimeIndex), columns: close (float)
    Output:
      DataFrame with features and basic state probabilities.
    """
    if "close" not in df.columns:
        raise ValueError("Expected df with column 'close'.")

    out = pd.DataFrame(index=df.index)
    close = df["close"].astype(float)

    # Log returns
    logp = np.log(close)
    r1 = logp.diff()
    out["r1"] = r1

    # Multi-day log returns (speed proxies)
    out["R_fast"] = logp.diff(cfg.ret_fast)
    out["R_mid"] = logp.diff(cfg.ret_mid)
    out["R_slow"] = logp.diff(cfg.ret_slow)

    # Trend strength: mean/std of returns over windows (signal-to-noise)
    def trend_strength(win: int) -> pd.Series:
        mu = r1.rolling(win, min_periods=win).mean()
        sd = r1.rolling(win, min_periods=win).std(ddof=0)
        return mu / sd.replace(0, np.nan)

    out["TS_20"] = trend_strength(cfg.trend_win_short)
    out["TS_50"] = trend_strength(cfg.trend_win_mid)
    out["TS_200"] = trend_strength(cfg.trend_win_long)

    # Donchian band (close-only approximation is fine here)
    hi = close.rolling(cfg.band_win, min_periods=cfg.band_win).max()
    lo = close.rolling(cfg.band_win, min_periods=cfg.band_win).min()
    out["band_hi"] = hi
    out["band_lo"] = lo
    out["band_w"] = (hi - lo) / close
    out["band_pos"] = (close - lo) / (hi - lo)

    # Switch frequency (proxy for choppiness / range)
    # sign of 1d return
    sign = np.sign(out["r1"]).replace(0.0, np.nan).ffill()
    switch = (sign != sign.shift(1)).astype(float)
    out["switch_rate_50"] = switch.rolling(50, min_periods=50).mean()

    # Run length (streak) on drift direction using r1 sign
    # We compute consecutive positive/negative r1 streaks.
    sgn = np.sign(out["r1"]).fillna(0.0)

    run_pos = np.zeros(len(out), dtype=float)
    run_neg = np.zeros(len(out), dtype=float)
    rp = rn = 0
    for i, v in enumerate(sgn.values):
        if v > 0:
            rp += 1
            rn = 0
        elif v < 0:
            rn += 1
            rp = 0
        else:
            rp = 0
            rn = 0
        run_pos[i] = rp
        run_neg[i] = rn

    out["RL_pos"] = run_pos
    out["RL_neg"] = run_neg

    # Adaptive speed z-score: "fast move" relative to recent history
    # Use mid horizon return normalized.
    out["speed_z"] = _zscore(out["R_mid"], win=cfg.adapt_win)

    # Adaptive volatility proxy
    out["vol_20"] = out["r1"].rolling(20, min_periods=20).std(ddof=0)
    out["vol_z"] = _zscore(out["vol_20"], win=cfg.adapt_win)

    # Simple range proxy for default path (extras can compute full range_score)
    range_proxy = _clip01(out["switch_rate_50"].fillna(0.0))

    # Trend direction probability (up vs down), independent of range
    # Use TS_50 (direction+strength)
    trend_raw = out["TS_50"].fillna(0.0)
    out["p_up_dir"] = _clip01(pd.Series(_sigmoid(cfg.ts_scale * trend_raw), index=out.index))
    out["p_down_dir"] = 1.0 - out["p_up_dir"]

    # Speed probability: "fast" vs "slow" (based on speed_z)
    # fast if speed_z is high magnitude; slow if near 0.
    speed_mag = out["speed_z"].abs().fillna(0.0)
    out["p_fast"] = _clip01(pd.Series(_sigmoid(cfg.speed_scale * (speed_mag - 0.75)), index=out.index))
    out["p_slow"] = 1.0 - out["p_fast"]

    # Duration hazard components:
    # - After long up streak, increase correction propensity
    # - After long down streak, increase rebound propensity
    # Use sigmoid on run lengths (scaled).
    out["p_corr_dur"] = _clip01(pd.Series(_sigmoid(cfg.runlen_scale * (out["RL_pos"] - 10.0)), index=out.index))
    out["p_reb_dur"] = _clip01(pd.Series(_sigmoid(cfg.runlen_scale * (out["RL_neg"] - 10.0)), index=out.index))

    # "State" probabilities (simple compositional model)
    # Prior: range dominates -> range_proxy sets mass.
    # Remaining mass is split between up/down.
    p_range = range_proxy
    p_trend = 1.0 - p_range

    p_up = p_trend * out["p_up_dir"]
    p_down = p_trend * out["p_down_dir"]

    # Speed-derived components (used for hazard overlays).
    p_up_fast = p_up * out["p_fast"]
    p_down_fast = p_down * out["p_fast"]

    # Split range into low/high vol by vol_z
    # high vol if vol_z high
    out["p_range_highvol"] = _clip01(pd.Series(_sigmoid(1.0 * (out["vol_z"].fillna(0.0) - 0.25)), index=out.index))
    range_high = p_range * out["p_range_highvol"]
    range_low = p_range * (1.0 - out["p_range_highvol"])

    # 4 generic regime buckets (temporary index mapping)
    out["HMM_STATE_0"] = p_up
    out["HMM_STATE_1"] = p_down
    out["HMM_STATE_2"] = range_low
    out["HMM_STATE_3"] = range_high

    # Normalize to sum to 1 (numerical safety)
    probs = out[[
        "HMM_STATE_0", "HMM_STATE_1",
        "HMM_STATE_2", "HMM_STATE_3"
    ]].sum(axis=1)
    out.loc[probs > 0, [
        "HMM_STATE_0", "HMM_STATE_1",
        "HMM_STATE_2", "HMM_STATE_3"
    ]] = out.loc[probs > 0, [
        "HMM_STATE_0", "HMM_STATE_1",
        "HMM_STATE_2", "HMM_STATE_3"
    ]].div(probs[probs > 0], axis=0)

    # Attach close for convenience
    out["close"] = close

    # Minimal "risk overlays" (event-like props, heuristic for now)
    # Correction propensity increases with: UP_FAST + duration hazard
    out["P_CORRECTION_10D"] = _clip01(
        0.55 * p_up_fast + 0.35 * out["p_corr_dur"] + 0.10 * p_trend
    )

    # Rebound propensity increases with: DOWN_FAST + duration hazard
    out["P_REBOUND_10D"] = _clip01(
        0.55 * p_down_fast + 0.35 * out["p_reb_dur"] + 0.10 * p_trend
    )

    return out


def compute_extras_features(features: pd.DataFrame, cfg: FeatureConfig = FeatureConfig()) -> pd.DataFrame:
    out = features.copy()
    required = ["TS_50", "band_w", "switch_rate_50"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"compute_extras_features missing columns: {missing}")

    out["range_score"] = _compute_range_score(out, cfg)
    return out


def to_echarts_json(features: pd.DataFrame) -> Dict:
    """
    Prepare minimal JSON structure that ECharts can consume easily.
    """
    hmm_state_cols = [c for c in features.columns if c.startswith("HMM_STATE_")]
    hmm_state_cols = sorted(
        hmm_state_cols,
        key=lambda c: int(c.split("_")[-1]) if c.split("_")[-1].isdigit() else c,
    )

    # Keep only the columns we care about for visualization
    cols = [
        "close",
        "TS_50",
        "band_w",
        "band_pos",
        "range_score",
        "P_CORRECTION_10D",
        "P_REBOUND_10D",
        "P_CORRECTION_10D_CAL",
        "P_REBOUND_10D_CAL",
        "HMM_CONF",
        "HMM_DOM",
        *hmm_state_cols,
        # exposure
        "E_target_safe", "L_target_safe", "direction_safe", "entry_step_safe",
        "conviction_safe",
    ]
    
    existing = [c for c in cols if c in features.columns]
    keep = features[existing].dropna()

    dates = [d.strftime("%Y-%m-%d") for d in keep.index.to_pydatetime()]
    series = {c: keep[c].astype(float).round(8).tolist() for c in existing}

    return {
        "meta": {
            "start": dates[0] if dates else None,
            "end": dates[-1] if dates else None,
            "rows": len(dates),
        },
        "dates": dates,
        "series": series,
    }
