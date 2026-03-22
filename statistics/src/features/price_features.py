from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, TypedDict

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FeatureConfig:
    """Configuration for descriptive OHLCV feature engineering."""

    ret_fast: int = 3
    ret_mid: int = 7
    ret_slow: int = 14

    trend_win_short: int = 20
    trend_win_mid: int = 50
    trend_win_long: int = 200

    volatility_win: int = 20
    atr_win: int = 14
    band_win: int = 100
    switch_win: int = 50
    volume_win: int = 20
    equilibrium_win: int = 50
    local_extrema_win: int = 50
    adapt_win: int = 365 * 2
    ewma_span: int = 20

    eps: float = 1e-8


class FeatureSpec(TypedDict):
    group: str
    what_it_describes: str
    why_it_matters: str
    how_computed: str
    inputs: tuple[str, ...]
    notes: str



def _feature_spec(
    group: str,
    what_it_describes: str,
    why_it_matters: str,
    how_computed: str,
    inputs: tuple[str, ...],
    notes: str = "",
) -> FeatureSpec:
    return {
        "group": group,
        "what_it_describes": what_it_describes,
        "why_it_matters": why_it_matters,
        "how_computed": how_computed,
        "inputs": inputs,
        "notes": notes,
    }


EXPORTED_FEATURES: tuple[str, ...] = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "r1",
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
    "true_range",
    "atr",
    "atr_pct",
    "parkinson_vol",
    "garman_klass_vol",
    "ewma_vol",
    "upside_semi_vol",
    "downside_semi_vol",
    "band_hi",
    "band_lo",
    "band_w",
    "band_pos",
    "dist_from_mean_vol_units",
    "candle_body",
    "candle_range",
    "body_to_range_ratio",
    "upper_wick_ratio",
    "lower_wick_ratio",
    "close_in_range",
    "volume_log1p",
    "relative_volume_20",
    "volume_z",
    "switch_rate_50",
    "run_length_up",
    "run_length_down",
    "run_magnitude_up",
    "run_magnitude_down",
    "return_accel",
    "time_since_local_high",
    "time_since_local_low",
)


FEATURE_SPECS: dict[str, FeatureSpec] = {
    "open": _feature_spec(
        "candle",
        "Session opening price.",
        "Anchors intraday direction and gap-like candle structure.",
        "Raw open price from the input OHLCV table.",
        ("open",),
    ),
    "high": _feature_spec(
        "candle",
        "Session high price.",
        "Captures intraday upside excursion and range expansion.",
        "Raw high price from the input OHLCV table.",
        ("high",),
    ),
    "low": _feature_spec(
        "candle",
        "Session low price.",
        "Captures intraday downside excursion and range expansion.",
        "Raw low price from the input OHLCV table.",
        ("low",),
    ),
    "close": _feature_spec(
        "candle",
        "Session closing price.",
        "Primary anchor for returns, trend, and most downstream models.",
        "Raw close price from the input OHLCV table.",
        ("close",),
        "Most exported features depend on close directly or indirectly.",
    ),
    "volume": _feature_spec(
        "volume",
        "Observed traded volume for the session.",
        "Provides participation context for price moves.",
        "Raw volume from the input OHLCV table.",
        ("volume",),
        "Allowed to be zero but never negative.",
    ),
    "r1": _feature_spec(
        "returns",
        "One-day log return.",
        "Baseline daily price change used by most trend and volatility measures.",
        "Difference of log(close) over one period.",
        ("close",),
        "Core return feature; overlaps with multi-horizon returns by construction.",
    ),
    "R_3": _feature_spec(
        "returns",
        "Three-day log return.",
        "Captures short-horizon price speed with less noise than a one-day move.",
        "Difference of log(close) over 3 periods.",
        ("close",),
    ),
    "R_7": _feature_spec(
        "returns",
        "Seven-day log return.",
        "Captures weekly-scale directional movement.",
        "Difference of log(close) over 7 periods.",
        ("close",),
    ),
    "R_14": _feature_spec(
        "returns",
        "Fourteen-day log return.",
        "Captures slower short-term swing movement.",
        "Difference of log(close) over 14 periods.",
        ("close",),
    ),
    "TS_20": _feature_spec(
        "trend",
        "20-day return signal-to-noise ratio.",
        "Measures whether returns are directionally persistent relative to their noise level.",
        "Rolling mean of r1 divided by rolling standard deviation over 20 periods.",
        ("close",),
        "Overlaps with LR_20 and RVR_20 but is simpler and more return-centric.",
    ),
    "TS_50": _feature_spec(
        "trend",
        "50-day return signal-to-noise ratio.",
        "Summarizes medium-term directional persistence.",
        "Rolling mean of r1 divided by rolling standard deviation over 50 periods.",
        ("close",),
        "Overlaps with LR_50 and RVR_50.",
    ),
    "TS_200": _feature_spec(
        "trend",
        "200-day return signal-to-noise ratio.",
        "Summarizes long-term directional persistence.",
        "Rolling mean of r1 divided by rolling standard deviation over 200 periods.",
        ("close",),
        "Long-horizon companion to TS_20 and TS_50.",
    ),
    "LR_20": _feature_spec(
        "trend",
        "20-day normalized linear trend slope.",
        "Captures directional slope of log price while adjusting for realized volatility.",
        "Rolling linear-regression slope of log(close) over 20 periods divided by rolling return volatility.",
        ("close",),
        "Overlaps with TS_20 but is more geometry-based than return-average based.",
    ),
    "LR_50": _feature_spec(
        "trend",
        "50-day normalized linear trend slope.",
        "Captures medium-term geometric trend strength.",
        "Rolling linear-regression slope of log(close) over 50 periods divided by rolling return volatility.",
        ("close",),
        "Often redundant with TS_50 and RVR_50 in stable trends.",
    ),
    "LR_200": _feature_spec(
        "trend",
        "200-day normalized linear trend slope.",
        "Captures long-term geometric trend strength.",
        "Rolling linear-regression slope of log(close) over 200 periods divided by rolling return volatility.",
        ("close",),
    ),
    "ER_20": _feature_spec(
        "trend",
        "20-day directional efficiency ratio.",
        "Separates clean directional travel from noisy back-and-forth movement.",
        "Absolute 20-day net log-price change divided by the sum of absolute daily log-price changes over the same window.",
        ("close",),
        "Overlaps with TS_20 and RVR_20, but is more path-sensitive.",
    ),
    "ER_50": _feature_spec(
        "trend",
        "50-day directional efficiency ratio.",
        "Measures whether medium-term movement is trend-like or choppy.",
        "Absolute 50-day net log-price change divided by the sum of absolute daily log-price changes over the same window.",
        ("close",),
    ),
    "ER_200": _feature_spec(
        "trend",
        "200-day directional efficiency ratio.",
        "Measures long-horizon trend cleanliness.",
        "Absolute 200-day net log-price change divided by the sum of absolute daily log-price changes over the same window.",
        ("close",),
    ),
    "RVR_20": _feature_spec(
        "trend",
        "20-day cumulative return normalized by realized volatility.",
        "Compares directional payoff to the volatility required to achieve it.",
        "20-day log return divided by rolling standard deviation of r1 times sqrt(20).",
        ("close",),
        "Overlaps with TS_20 and LR_20 but is cumulative-return based.",
    ),
    "RVR_50": _feature_spec(
        "trend",
        "50-day cumulative return normalized by realized volatility.",
        "Measures medium-term risk-adjusted directional movement.",
        "50-day log return divided by rolling standard deviation of r1 times sqrt(50).",
        ("close",),
    ),
    "RVR_200": _feature_spec(
        "trend",
        "200-day cumulative return normalized by realized volatility.",
        "Measures long-term risk-adjusted directional movement.",
        "200-day log return divided by rolling standard deviation of r1 times sqrt(200).",
        ("close",),
    ),
    "vol_20": _feature_spec(
        "volatility",
        "20-day realized volatility of daily log returns.",
        "Baseline close-to-close volatility descriptor.",
        "Rolling standard deviation of r1 over 20 periods.",
        ("close",),
        "Overlaps with ATR and high-low estimators but only uses close-to-close moves.",
    ),
    "true_range": _feature_spec(
        "volatility",
        "Daily true range including gap effects.",
        "Captures the full one-day trading span relative to the previous close.",
        "Max of high-low, abs(high-prev_close), and abs(low-prev_close).",
        ("high", "low", "close"),
        "Unavailable when high/low are missing.",
    ),
    "atr": _feature_spec(
        "volatility",
        "Average true range over the ATR window.",
        "Smooths daily trading span into a more stable range-volatility measure.",
        "Rolling mean of true_range over the configured ATR window.",
        ("high", "low", "close"),
        "Overlaps with vol_20 and Parkinson volatility, but keeps gap sensitivity.",
    ),
    "atr_pct": _feature_spec(
        "volatility",
        "ATR scaled by close price.",
        "Makes ATR comparable across price levels.",
        "atr divided by close.",
        ("high", "low", "close"),
    ),
    "parkinson_vol": _feature_spec(
        "volatility",
        "High-low volatility estimator.",
        "Uses intraday range information more efficiently than close-only volatility.",
        "Square root of the rolling mean of log(high/low)^2 divided by 4*ln(2).",
        ("high", "low"),
        "Ignores open-close drift and gaps; overlaps with Garman-Klass and ATR.",
    ),
    "garman_klass_vol": _feature_spec(
        "volatility",
        "Open-high-low-close volatility estimator.",
        "Uses more OHLC information than close-to-close volatility alone.",
        "Rolling Garman-Klass estimator built from log(high/low) and log(close/open).",
        ("open", "high", "low", "close"),
        "Unavailable when open/high/low are missing; overlaps with Parkinson and ATR.",
    ),
    "ewma_vol": _feature_spec(
        "volatility",
        "Exponentially weighted volatility estimate.",
        "Responds faster to volatility regime shifts than a fixed rolling window.",
        "Square root of exponentially weighted mean of r1^2 with the configured span.",
        ("close",),
        "Overlaps with vol_20 but reacts more quickly to recent shocks.",
    ),
    "upside_semi_vol": _feature_spec(
        "volatility",
        "Volatility of positive daily returns only.",
        "Separates upside variability from downside stress.",
        "Square root of the rolling mean of clipped positive r1 squared.",
        ("close",),
        "Useful alongside downside_semi_vol when volatility is asymmetric.",
    ),
    "downside_semi_vol": _feature_spec(
        "volatility",
        "Volatility of negative daily returns only.",
        "Highlights downside stress separately from total volatility.",
        "Square root of the rolling mean of clipped negative r1 magnitudes squared.",
        ("close",),
        "Useful alongside upside_semi_vol when volatility is asymmetric.",
    ),
    "band_hi": _feature_spec(
        "structure",
        "Rolling upper price band.",
        "Defines the recent local ceiling used for range width and band position.",
        "Rolling maximum of high when available, otherwise close, over the configured band window.",
        ("close", "high"),
        "Falls back to close-only bands when high is unavailable.",
    ),
    "band_lo": _feature_spec(
        "structure",
        "Rolling lower price band.",
        "Defines the recent local floor used for range width and band position.",
        "Rolling minimum of low when available, otherwise close, over the configured band window.",
        ("close", "low"),
        "Falls back to close-only bands when low is unavailable.",
    ),
    "band_w": _feature_spec(
        "structure",
        "Normalized width of the rolling price band.",
        "Measures how wide the recent trading envelope is relative to current price.",
        "(band_hi - band_lo) divided by close.",
        ("close", "high", "low"),
        "Overlaps with atr_pct and realized-volatility features but is more geometric.",
    ),
    "band_pos": _feature_spec(
        "structure",
        "Close position inside the rolling band.",
        "Shows whether price is near the recent top, middle, or bottom of its envelope.",
        "(close - band_lo) divided by (band_hi - band_lo), clipped to [0, 1].",
        ("close", "high", "low"),
    ),
    "dist_from_mean_vol_units": _feature_spec(
        "structure",
        "Distance from the rolling mean in volatility units.",
        "Measures how stretched price is relative to its recent equilibrium.",
        "Difference between log(close) and its rolling mean divided by rolling return volatility scaled by sqrt(window).",
        ("close",),
        "Conceptually overlaps with band_pos but is mean-reversion oriented rather than envelope oriented.",
    ),
    "candle_body": _feature_spec(
        "candle",
        "Signed open-to-close candle body.",
        "Captures daily directional movement within the session.",
        "close minus open.",
        ("open", "close"),
        "Unavailable when open is missing.",
    ),
    "candle_range": _feature_spec(
        "candle",
        "Full intraday high-low range.",
        "Captures the total session span independent of direction.",
        "high minus low.",
        ("high", "low"),
        "Unavailable when high/low are missing; overlaps with true_range but excludes previous-close gaps.",
    ),
    "body_to_range_ratio": _feature_spec(
        "candle",
        "Body size relative to the full candle range.",
        "Separates directional candles from indecisive candles with long wicks.",
        "candle_body divided by candle_range.",
        ("open", "high", "low", "close"),
    ),
    "upper_wick_ratio": _feature_spec(
        "candle",
        "Upper wick share of the candle range.",
        "Highlights upside rejection inside the session.",
        "(high - max(open, close)) divided by candle_range.",
        ("open", "high", "low", "close"),
    ),
    "lower_wick_ratio": _feature_spec(
        "candle",
        "Lower wick share of the candle range.",
        "Highlights downside rejection inside the session.",
        "(min(open, close) - low) divided by candle_range.",
        ("open", "high", "low", "close"),
    ),
    "close_in_range": _feature_spec(
        "candle",
        "Close location inside the day’s range.",
        "Distinguishes closes near the high from closes near the low.",
        "(close - low) divided by candle_range, clipped to [0, 1].",
        ("high", "low", "close"),
    ),
    "volume_log1p": _feature_spec(
        "volume",
        "Log-scaled volume with zero-safe transform.",
        "Compresses heavy-tailed volume while allowing valid zero-volume rows.",
        "Natural log of (1 + volume).",
        ("volume",),
    ),
    "relative_volume_20": _feature_spec(
        "volume",
        "Volume relative to its recent average.",
        "Shows whether current participation is above or below normal.",
        "volume divided by the rolling mean of volume over the configured volume window.",
        ("volume",),
        "Overlaps with volume_z but keeps a direct multiplicative interpretation.",
    ),
    "volume_z": _feature_spec(
        "volume",
        "Adaptive z-score of log-scaled volume.",
        "Measures whether current participation is unusual relative to its longer-run history.",
        "Rolling z-score of volume_log1p over the adaptive window.",
        ("volume",),
        "Overlaps with relative_volume_20 but uses longer-run normalization.",
    ),
    "switch_rate_50": _feature_spec(
        "path",
        "Frequency of daily direction changes.",
        "Measures how often return signs flip, which helps distinguish trending from choppy paths.",
        "Rolling mean of sign-change events in daily log returns over the switch window.",
        ("close",),
        "Path descriptor that partly overlaps with efficiency ratio.",
    ),
    "run_length_up": _feature_spec(
        "path",
        "Length of the current positive-return streak.",
        "Describes directional persistence in the immediate path.",
        "Count of consecutive days with positive r1 up to the current row.",
        ("close",),
        "Pairs naturally with run_magnitude_up.",
    ),
    "run_length_down": _feature_spec(
        "path",
        "Length of the current negative-return streak.",
        "Describes downside persistence in the immediate path.",
        "Count of consecutive days with negative r1 up to the current row.",
        ("close",),
        "Pairs naturally with run_magnitude_down.",
    ),
    "run_magnitude_up": _feature_spec(
        "path",
        "Cumulative magnitude of the current positive-return streak.",
        "Separates long mild up-streaks from shorter but stronger up-runs.",
        "Running sum of positive r1 values within the current positive streak.",
        ("close",),
        "Overlaps with run_length_up but adds amplitude information.",
    ),
    "run_magnitude_down": _feature_spec(
        "path",
        "Cumulative magnitude of the current negative-return streak.",
        "Separates long mild down-streaks from shorter but stronger selloffs.",
        "Running sum of absolute negative r1 values within the current negative streak.",
        ("close",),
        "Overlaps with run_length_down but adds amplitude information.",
    ),
    "return_accel": _feature_spec(
        "path",
        "Second difference of log price via return acceleration.",
        "Captures whether short-term momentum is increasing or fading.",
        "Difference of r1 from one day to the next.",
        ("close",),
        "Often noisy; complements smoother trend features rather than replacing them.",
    ),
    "time_since_local_high": _feature_spec(
        "path",
        "Elapsed time since the most recent rolling local high.",
        "Describes recency of upside extremes in the current path.",
        "Number of periods since the maximum of high, or close if high is unavailable, within the local-extrema window.",
        ("close", "high"),
        "Window length is controlled by configuration; overlaps with band_pos in a different form.",
    ),
    "time_since_local_low": _feature_spec(
        "path",
        "Elapsed time since the most recent rolling local low.",
        "Describes recency of downside extremes in the current path.",
        "Number of periods since the minimum of low, or close if low is unavailable, within the local-extrema window.",
        ("close", "low"),
        "Window length is controlled by configuration; overlaps with band_pos in a different form.",
    ),
}



def _validate_feature_catalog() -> None:
    missing_specs = [name for name in EXPORTED_FEATURES if name not in FEATURE_SPECS]
    extra_specs = [name for name in FEATURE_SPECS if name not in EXPORTED_FEATURES]
    if missing_specs or extra_specs:
        raise RuntimeError(
            f"Feature catalog mismatch. Missing specs: {missing_specs}; extra specs: {extra_specs}."
        )


_validate_feature_catalog()


# -----------------------------
# Validation helpers
# -----------------------------



def _nan_series(index: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=index, dtype=float)



def _empty_frame(index: pd.Index, columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame({column: _nan_series(index) for column in columns}, index=index)



def _validate_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("compute_price_features expects a DataFrame indexed by pandas.DatetimeIndex.")
    if df.empty:
        raise ValueError("compute_price_features received an empty DataFrame.")
    if "close" not in df.columns:
        raise ValueError("compute_price_features requires at least a 'close' column.")
    if df.index.has_duplicates:
        raise ValueError("compute_price_features does not accept duplicate timestamps in the index.")

    out = df.sort_index().copy()

    for column in ("open", "high", "low", "close"):
        if column in out.columns:
            numeric = pd.to_numeric(out[column], errors="coerce")
            invalid_mask = (~np.isfinite(numeric)) | (numeric <= 0.0)
            if invalid_mask.any():
                bad_index = numeric.index[invalid_mask][0]
                bad_value = out.loc[bad_index, column]
                raise ValueError(
                    f"Column '{column}' contains a non-positive or non-finite value at {bad_index}: {bad_value!r}."
                )
            out[column] = numeric.astype(float)

    if "volume" in out.columns:
        volume = pd.to_numeric(out["volume"], errors="coerce")
        invalid_mask = (~np.isfinite(volume)) | (volume < 0.0)
        if invalid_mask.any():
            bad_index = volume.index[invalid_mask][0]
            bad_value = out.loc[bad_index, "volume"]
            raise ValueError(
                f"Column 'volume' contains a negative or non-finite value at {bad_index}: {bad_value!r}."
            )
        out["volume"] = volume.astype(float)

    if {"high", "low"}.issubset(out.columns):
        invalid_range = out["high"] < out["low"]
        if invalid_range.any():
            bad_index = out.index[invalid_range][0]
            raise ValueError(f"Column 'high' must be greater than or equal to 'low' at {bad_index}.")

    if {"open", "high", "low", "close"}.issubset(out.columns):
        invalid_high = out["high"] < out[["open", "close"]].max(axis=1)
        invalid_low = out["low"] > out[["open", "close"]].min(axis=1)
        if invalid_high.any():
            bad_index = out.index[invalid_high][0]
            raise ValueError(f"Column 'high' must cover open/close at {bad_index}.")
        if invalid_low.any():
            bad_index = out.index[invalid_low][0]
            raise ValueError(f"Column 'low' must cover open/close at {bad_index}.")

    return out


# -----------------------------
# Low-level compute helpers
# -----------------------------



def _clip01(s: pd.Series) -> pd.Series:
    return s.clip(lower=0.0, upper=1.0)



def _rolling_zscore(s: pd.Series, win: int, eps: float) -> pd.Series:
    mean = s.rolling(win, min_periods=win).mean()
    std = s.rolling(win, min_periods=win).std(ddof=0).clip(lower=eps)
    return (s - mean) / std



def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)



def _rolling_linear_regression_slope(log_price: pd.Series, returns: pd.Series, win: int, eps: float) -> pd.Series:
    x = np.arange(win, dtype=float)
    x = x - x.mean()
    denom = float(np.dot(x, x))

    def _slope(values: np.ndarray) -> float:
        centered = values - values.mean()
        return float(np.dot(centered, x) / denom)

    slope = log_price.rolling(win, min_periods=win).apply(_slope, raw=True)
    realized_vol = returns.rolling(win, min_periods=win).std(ddof=0).clip(lower=eps)
    return slope / realized_vol



def _efficiency_ratio(log_price: pd.Series, win: int, eps: float) -> pd.Series:
    net_move = log_price.diff(win).abs()
    gross_move = log_price.diff().abs().rolling(win, min_periods=win).sum().clip(lower=eps)
    return net_move / gross_move



def _return_vol_ratio(log_price: pd.Series, returns: pd.Series, win: int, eps: float) -> pd.Series:
    cumulative_return = log_price.diff(win)
    realized_vol = returns.rolling(win, min_periods=win).std(ddof=0) * np.sqrt(win)
    return cumulative_return / realized_vol.clip(lower=eps)



def _parkinson_volatility(high: pd.Series, low: pd.Series, win: int) -> pd.Series:
    log_hl = np.log(high / low)
    variance = log_hl.pow(2).rolling(win, min_periods=win).mean() / (4.0 * np.log(2.0))
    return np.sqrt(variance.clip(lower=0.0))



def _garman_klass_volatility(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    win: int,
) -> pd.Series:
    log_hl = np.log(high / low)
    log_co = np.log(close / open_)
    variance_term = 0.5 * log_hl.pow(2) - (2.0 * np.log(2.0) - 1.0) * log_co.pow(2)
    variance = variance_term.rolling(win, min_periods=win).mean()
    return np.sqrt(variance.clip(lower=0.0))



def _ewma_volatility(returns: pd.Series, span: int) -> pd.Series:
    return returns.pow(2).ewm(span=span, adjust=False, min_periods=span).mean().pow(0.5)



def _semi_volatility(returns: pd.Series, win: int, positive: bool) -> pd.Series:
    if positive:
        component = returns.clip(lower=0.0)
    else:
        component = (-returns.clip(upper=0.0))
    return component.pow(2).rolling(win, min_periods=win).mean().pow(0.5)



def _compute_run_descriptors(returns: pd.Series) -> pd.DataFrame:
    run_length_up = np.zeros(len(returns), dtype=float)
    run_length_down = np.zeros(len(returns), dtype=float)
    run_magnitude_up = np.zeros(len(returns), dtype=float)
    run_magnitude_down = np.zeros(len(returns), dtype=float)

    up_len = 0.0
    down_len = 0.0
    up_mag = 0.0
    down_mag = 0.0

    for i, value in enumerate(returns.fillna(0.0).to_numpy()):
        if value > 0.0:
            up_len += 1.0
            up_mag += float(value)
            down_len = 0.0
            down_mag = 0.0
        elif value < 0.0:
            down_len += 1.0
            down_mag += float(-value)
            up_len = 0.0
            up_mag = 0.0
        else:
            up_len = 0.0
            down_len = 0.0
            up_mag = 0.0
            down_mag = 0.0

        run_length_up[i] = up_len
        run_length_down[i] = down_len
        run_magnitude_up[i] = up_mag
        run_magnitude_down[i] = down_mag

    return pd.DataFrame(
        {
            "run_length_up": run_length_up,
            "run_length_down": run_length_down,
            "run_magnitude_up": run_magnitude_up,
            "run_magnitude_down": run_magnitude_down,
        },
        index=returns.index,
    )



def _time_since_extreme(series: pd.Series, win: int, mode: str) -> pd.Series:
    reducer = np.argmax if mode == "max" else np.argmin
    positions = series.rolling(win, min_periods=win).apply(reducer, raw=True)
    return (win - 1) - positions


# -----------------------------
# Family-specific compute helpers
# -----------------------------



def _compute_return_features(close: pd.Series, cfg: FeatureConfig) -> pd.DataFrame:
    log_close = np.log(close)
    return pd.DataFrame(
        {
            "r1": log_close.diff(),
            "R_3": log_close.diff(cfg.ret_fast),
            "R_7": log_close.diff(cfg.ret_mid),
            "R_14": log_close.diff(cfg.ret_slow),
        },
        index=close.index,
    )



def _compute_trend_features(close: pd.Series, returns: pd.Series, cfg: FeatureConfig) -> pd.DataFrame:
    log_close = np.log(close)

    def trend_strength(win: int) -> pd.Series:
        mean_return = returns.rolling(win, min_periods=win).mean()
        std_return = returns.rolling(win, min_periods=win).std(ddof=0).clip(lower=cfg.eps)
        return mean_return / std_return

    return pd.DataFrame(
        {
            "TS_20": trend_strength(cfg.trend_win_short),
            "TS_50": trend_strength(cfg.trend_win_mid),
            "TS_200": trend_strength(cfg.trend_win_long),
            "LR_20": _rolling_linear_regression_slope(log_close, returns, cfg.trend_win_short, cfg.eps),
            "LR_50": _rolling_linear_regression_slope(log_close, returns, cfg.trend_win_mid, cfg.eps),
            "LR_200": _rolling_linear_regression_slope(log_close, returns, cfg.trend_win_long, cfg.eps),
            "ER_20": _efficiency_ratio(log_close, cfg.trend_win_short, cfg.eps),
            "ER_50": _efficiency_ratio(log_close, cfg.trend_win_mid, cfg.eps),
            "ER_200": _efficiency_ratio(log_close, cfg.trend_win_long, cfg.eps),
            "RVR_20": _return_vol_ratio(log_close, returns, cfg.trend_win_short, cfg.eps),
            "RVR_50": _return_vol_ratio(log_close, returns, cfg.trend_win_mid, cfg.eps),
            "RVR_200": _return_vol_ratio(log_close, returns, cfg.trend_win_long, cfg.eps),
        },
        index=close.index,
    )



def _compute_volatility_features(
    open_: pd.Series | None,
    high: pd.Series | None,
    low: pd.Series | None,
    close: pd.Series,
    returns: pd.Series,
    cfg: FeatureConfig,
) -> pd.DataFrame:
    out = pd.DataFrame(index=close.index)
    out["vol_20"] = returns.rolling(cfg.volatility_win, min_periods=cfg.volatility_win).std(ddof=0)
    out["ewma_vol"] = _ewma_volatility(returns, cfg.ewma_span)
    out["upside_semi_vol"] = _semi_volatility(returns, cfg.volatility_win, positive=True)
    out["downside_semi_vol"] = _semi_volatility(returns, cfg.volatility_win, positive=False)

    if high is not None and low is not None:
        out["true_range"] = _true_range(high, low, close)
        out["atr"] = out["true_range"].rolling(cfg.atr_win, min_periods=cfg.atr_win).mean()
        out["atr_pct"] = out["atr"] / close.clip(lower=cfg.eps)
        out["parkinson_vol"] = _parkinson_volatility(high, low, cfg.volatility_win)
    else:
        out = pd.concat(
            [
                out,
                _empty_frame(close.index, ("true_range", "atr", "atr_pct", "parkinson_vol")),
            ],
            axis=1,
        )

    if open_ is not None and high is not None and low is not None:
        out["garman_klass_vol"] = _garman_klass_volatility(open_, high, low, close, cfg.volatility_win)
    else:
        out["garman_klass_vol"] = _nan_series(close.index)

    return out



def _compute_structure_features(
    high: pd.Series | None,
    low: pd.Series | None,
    close: pd.Series,
    returns: pd.Series,
    cfg: FeatureConfig,
) -> pd.DataFrame:
    band_high_source = high if high is not None else close
    band_low_source = low if low is not None else close

    out = pd.DataFrame(index=close.index)
    out["band_hi"] = band_high_source.rolling(cfg.band_win, min_periods=cfg.band_win).max()
    out["band_lo"] = band_low_source.rolling(cfg.band_win, min_periods=cfg.band_win).min()

    band_span = (out["band_hi"] - out["band_lo"]).clip(lower=cfg.eps)
    out["band_w"] = band_span / close.clip(lower=cfg.eps)
    out["band_pos"] = _clip01((close - out["band_lo"]) / band_span)

    log_close = np.log(close)
    mean_log_close = log_close.rolling(cfg.equilibrium_win, min_periods=cfg.equilibrium_win).mean()
    realized_vol = (
        returns.rolling(cfg.equilibrium_win, min_periods=cfg.equilibrium_win).std(ddof=0)
        * np.sqrt(cfg.equilibrium_win)
    ).clip(lower=cfg.eps)
    out["dist_from_mean_vol_units"] = (log_close - mean_log_close) / realized_vol
    return out



def _compute_candle_features(
    open_: pd.Series | None,
    high: pd.Series | None,
    low: pd.Series | None,
    close: pd.Series,
    cfg: FeatureConfig,
) -> pd.DataFrame:
    columns = (
        "candle_body",
        "candle_range",
        "body_to_range_ratio",
        "upper_wick_ratio",
        "lower_wick_ratio",
        "close_in_range",
    )
    if open_ is None or high is None or low is None:
        return _empty_frame(close.index, columns)

    out = pd.DataFrame(index=close.index)
    out["candle_body"] = close - open_
    out["candle_range"] = (high - low).clip(lower=cfg.eps)
    out["body_to_range_ratio"] = out["candle_body"] / out["candle_range"]
    out["upper_wick_ratio"] = (high - np.maximum(open_, close)) / out["candle_range"]
    out["lower_wick_ratio"] = (np.minimum(open_, close) - low) / out["candle_range"]
    out["close_in_range"] = _clip01((close - low) / out["candle_range"])
    return out



def _compute_volume_features(volume: pd.Series | None, cfg: FeatureConfig, index: pd.Index) -> pd.DataFrame:
    columns = ("volume_log1p", "relative_volume_20", "volume_z")
    if volume is None:
        return _empty_frame(index, columns)

    out = pd.DataFrame(index=index)
    out["volume_log1p"] = np.log1p(volume)
    rolling_mean = volume.rolling(cfg.volume_win, min_periods=cfg.volume_win).mean().clip(lower=cfg.eps)
    out["relative_volume_20"] = volume / rolling_mean
    out["volume_z"] = _rolling_zscore(out["volume_log1p"], cfg.adapt_win, cfg.eps)
    return out



def _compute_path_features(
    high: pd.Series | None,
    low: pd.Series | None,
    close: pd.Series,
    returns: pd.Series,
    cfg: FeatureConfig,
) -> pd.DataFrame:
    direction = np.sign(returns)
    persistent_direction = direction.replace(0.0, np.nan).ffill().fillna(0.0)
    switch = (
        persistent_direction.ne(0.0)
        & persistent_direction.shift(1).ne(0.0)
        & persistent_direction.ne(persistent_direction.shift(1))
    ).astype(float)

    out = pd.DataFrame(index=close.index)
    out["switch_rate_50"] = switch.rolling(cfg.switch_win, min_periods=cfg.switch_win).mean()
    out = pd.concat([out, _compute_run_descriptors(returns)], axis=1)
    out["return_accel"] = returns.diff()

    high_source = high if high is not None else close
    low_source = low if low is not None else close
    out["time_since_local_high"] = _time_since_extreme(high_source, cfg.local_extrema_win, "max")
    out["time_since_local_low"] = _time_since_extreme(low_source, cfg.local_extrema_win, "min")
    return out


# -----------------------------
# Public API
# -----------------------------



def compute_price_features(df: pd.DataFrame, cfg: FeatureConfig | None = None) -> pd.DataFrame:
    """Compute descriptive OHLCV features only.

    The returned DataFrame is intentionally limited to interpretable market
    descriptors. It does not include regime inference, pseudo-probabilities, or
    heuristic event scores.
    """
    if cfg is None:
        cfg = FeatureConfig()

    prices = _validate_price_frame(df)
    close = prices["close"]
    open_ = prices["open"] if "open" in prices.columns else None
    high = prices["high"] if "high" in prices.columns else None
    low = prices["low"] if "low" in prices.columns else None
    volume = prices["volume"] if "volume" in prices.columns else None

    base = pd.DataFrame(index=prices.index)
    for column in ("open", "high", "low", "close", "volume"):
        base[column] = prices[column] if column in prices.columns else _nan_series(prices.index)

    return_features = _compute_return_features(close, cfg)
    trend_features = _compute_trend_features(close, return_features["r1"], cfg)
    volatility_features = _compute_volatility_features(open_, high, low, close, return_features["r1"], cfg)
    structure_features = _compute_structure_features(high, low, close, return_features["r1"], cfg)
    candle_features = _compute_candle_features(open_, high, low, close, cfg)
    volume_features = _compute_volume_features(volume, cfg, prices.index)
    path_features = _compute_path_features(high, low, close, return_features["r1"], cfg)

    features = pd.concat(
        [
            base,
            return_features,
            trend_features,
            volatility_features,
            structure_features,
            candle_features,
            volume_features,
            path_features,
        ],
        axis=1,
    )
    features = features.replace([np.inf, -np.inf], np.nan)
    return features.reindex(columns=EXPORTED_FEATURES)



def compute_extras_features(features: pd.DataFrame, cfg: FeatureConfig | None = None) -> pd.DataFrame:
    """Retained for compatibility; no extra non-descriptive features are added.

    The function simply returns the explicit descriptive feature set in export
    order.
    """
    if cfg is None:
        cfg = FeatureConfig()

    _ = cfg
    _validate_feature_catalog()
    return features.reindex(columns=EXPORTED_FEATURES).copy()



def to_echarts_json(features: pd.DataFrame) -> Dict[str, Any]:
    """Export only the explicit descriptive feature set for chart consumption."""
    _validate_feature_catalog()

    keep = features.reindex(columns=EXPORTED_FEATURES).copy()
    if "close" not in keep.columns:
        raise ValueError("to_echarts_json requires a 'close' column.")

    keep = keep.loc[keep["close"].notna()]
    if isinstance(keep.index, pd.DatetimeIndex):
        dates = keep.index.strftime("%Y-%m-%d").tolist()
    else:
        dates = pd.to_datetime(keep.index).strftime("%Y-%m-%d").tolist()

    series = {column: [None if pd.isna(value) else round(float(value), 8) for value in keep[column].tolist()] for column in EXPORTED_FEATURES}

    return {
        "meta": {
            "start": dates[0] if dates else None,
            "end": dates[-1] if dates else None,
            "rows": len(dates),
            "exported_features": list(EXPORTED_FEATURES),
        },
        "dates": dates,
        "series": series,
    }
