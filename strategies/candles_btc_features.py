#!/usr/bin/env python3
"""
Vectorized candlestick features + outcome generator.

Compute OHLC-derived candlestick components (range, net move, upper/lower shadows),
their normalizations, and forward outcomes (log-returns, MFE/MAW) for given horizons.

Design goals:
- One function per formula.
- Each formula function has docstrings with: definition, math, purpose.
- Separate export function (CSV/Parquet/JSON).
- main() orchestrates the pipeline.

Expected input:
A JSON ... TODO: explain the JSON content and adapt the code to use the JSON content

Output:
A table containing original OHLC plus:
- R, M, U, D (raw components)
- r_R, r_M, r_U, r_D (normalized by previous close)
- f_U, f_D, f_B, f_dir (shape fractions, normalized by range)
- u_k, MFE_k, MAE_k for each horizon k
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Candle:
    """Single candlestick (scalar)."""
    open_price: float
    high_price: float
    low_price: float
    close_price: float

@dataclass(frozen=True)
class CandleBatch:
    """
    Batch of candlestick stored as NumPy arrays (vectorized).

    Attributes:
      open_price, high_price, low_price, close_price: np.ndarray shape

    Notes:
      - Vectorized operations on arrays are much faster than Python loops.
      - Iteration is provided for debugging/inspection, not for core computation.
    """
    open_price: np.ndarray
    high_price: np.ndarray
    low_price: np.ndarray
    close_price: np.ndarray

    def __post_init__(self) -> None:
        if not (len(self.open_price) == len(self.high_price) == len(self.low_price) == len(self.close_price)):
            raise ValueError("All OHLC arrays must have the same length.")
        if (
            np.any(self.open_price <= 0)
            or np.any(self.high_price <= 0)
            or np.any(self.low_price <= 0)
            or np.any(self.close_price <= 0)
        ):
            raise ValueError("All OHLC values must be greater than 0.")
        
    def __len__(self) -> int:
        return len(self.open_price)
    
    def __iter__(self) -> Iterator[Candle]:
        for i in range(len(self)):
            yield Candle(
                open_price=float(self.open_price[i]),
                high_price=float(self.high_price[i]),
                low_price=float(self.low_price[i]),
                close_price=float(self.close_price[i]),
            )

    def compute_range_size(self) -> np.ndarray:
        """
        Intraperiod range size.

        Math:
          range_size[t] = high[t] - low[t]

        Purpose:
          Captures the maximum price span explored during the interval.
        """
        return self.high_price - self.low_price

    def compute_net_move(self) -> np.ndarray:
        """
        Signed net move from open to close.

        Math:
          net_move[t] = close[t] - open[t]

        Purpose:
          Net directional result (sign indicates bullish/bearish close vs open)
        """
        return self.close_price - self.open_price
    
    def compute_upper_shadow_size(self) -> np.ndarray:
        """
        Upper shadow (wick) size.

        Math:
          upper_shadow[t] = high[t] - max(open[t], close[t])
        
        Purpose:
          Distance from the upper extreme back to the body top.
        """

        body_top = np.maximum(self.open_price, self.close_price)
        return self.high_price - body_top
    
    def compute_lower_shadow_size(self) -> np.ndarray:
        """
        Lower shadow (wick) size.

        Math:
          lower_shadow[t] = min(open[t], close[t]) - low[t]

        Purpose:
          Distance from the lower extreme up to the body bottom.
        """

        body_bottom = np.minimum(self.open_price, self.close_price)
        return body_bottom - self.low_price

    def check_range_decomposition_identity(
        self,
        atol: float = 1e-10,
    ) -> np.ndarray:
        """
        Sanity check identity:
          range_size[t] == upper_sadow[t] + abs(net_move[t]) + lower_shadow[t]

        Returns:
          Boolean array (True where identity holds within tolerance).

        Purpose:
          Detects inconsistent OHLC rows (or floating-point anomalies).
        """
        left_operand = self.compute_range_size()
        right_operand = self.compute_upper_shadow_size() + np.abs(self.compute_net_move()) + self.compute_lower_shadow_size()
        return np.isclose(left_operand, right_operand, atol=atol)
    
    def compute_previous_close(self) -> np.ndarray:
        """
        Previous close.

        Math:
          prev_close[0] = open[0]
          prev_close[t] = close[t-1] for t>= 1

        Purpose:
          Common scaling denominator to remove dependencies on absolute price level.
        """
        n = len(self.close_price)
        prev_close = np.empty(n, dtype=float)

        prev_close[0] = self.open_price[0]
        prev_close[1:] = self.close_price[:-1]

        return prev_close
    
    def normalize_by_previous_close(self, values: np.ndarray) -> np.ndarray:
        """
        Normalize a value series by previous close.

        Math:
        pct_value[t] = values[t] / prev_close[t]

        Purpose:
        Converts absolute price units into relative units (approx percent scale).
        """
        return values / self.compute_previous_close()
    
    def fraction_of_range(self, values: np.ndarray) -> np.ndarray:
        """
        Normalize a component by the current range (shape fraction).

        Math:
          (for range_size[t] > 0):
            frac_value[t] = values[t] / range_size[t]

        Edge case:
          If range_size[t] == 0 -> 0

        Purpose:
          Describes candle *shape* independent of size.
        """
        r = self.compute_range_size()
        out = np.zeros_like(values, dtype=float)
        mask = r > 0
        out[mask] = values[mask] / r[mask]
        return out

    def compute_body_fraction(self) -> np.ndarray:
        """
        Body fraction.

        Math:
          body_fraction[t] = abs(net_move[t]) / range_size[t]

        Purpose:
          Fraction of range explained by the candle body.
        """
        return self.fraction_of_range(np.abs(self.compute_net_move()))
    
    def compute_direction_sign(self) -> np.ndarray:
        """
        Direction sign.

        Math:
          direction[t] = sign(net_move[t]) in {-1, 0, +1}

        Purpose:
          Discrete direction label for grouping candles.
        """
        return np.sign(self.compute_net_move())
    
    def compute_forward_log_return(self, horizon_days: int) -> np.ndarray:
        """
        Forward log return over k days.

        Math:
          fwd_logret[t, k] = ln( close[t+k] / close[t] )

        Purpose:
          Scale-invariant forward return for horizon k.
        """
        out = np.empty(len(self), dtype=float)
        out[-horizon_days:] = np.nan
        out[:-horizon_days] = np.log(self.close_price[horizon_days:] / self.close_price[:-horizon_days])
        return out

    def compute_max_favorable_excursion(self, horizon_days: int) -> np.ndarray:
        """
        Max Favorable Excursion (MFE) over next k days, relative to entry at close[t].

        Math:
          mfe[t, k] = max_{j=1..k} ( high[t+j] / close[t] -1 )
        
        Purpose:
          Maximum upside observed within the next k days.
        """
        n = len(self)
        if horizon_days <= 0:
            raise ValueError("horizon_days must be positive.")
        out = np.full(n, np.nan, dtype=float)
        for t in range(n - horizon_days):
            future_high = np.max(self.high_price[t+1 : t+horizon_days+1])
            out[t] = future_high / self.close_price[t] - 1.0
        return out
    
    def compute_max_adverse_excursion(self, horizon_days: int) -> np.ndarray:
        """
        Max Adverse Excursion (MAE) over next k days, relative to entry at close[t].

        Math:
          mae[t, k] = min_{j=1..k} ( low[t+j] / close[t] - 1 )

        Purpose:
          Maximum downside observed within the next k days (usually <= 0).
        """
        n = len(self)
        if horizon_days <= 0:
            raise ValueError("horizon_days must be positive.")
        out = np.full(n, np.nan, dtype=float)
        for t in range(n - horizon_days):
            future_low = np.min(self.low_price[t+1 : t+horizon_days+1])
            out[t] = future_low / self.close_price[t] - 1.0
        return out
    
def compute_quantile_bins(values: np.ndarray, num_bins: int, labels: Optional[List[str]] = None) -> pd.Categorical:
    """
    Quantile-based bins (using pandas.qcut).

    Purpose:
      Categorize without hard-coded thresholds.

    Returns:
      pandas Categorical o bin label.
    """
    s = pd.Series(values)
    if labels is None:
        labels = [f"Q{i+1}" for i in range(num_bins)]
    return pd.qcut(s, q=num_bins, labels=labels, duplicates="drop")

def classify_candle_shape(
    frac_upper_shadow: np.ndarray,
    frac_lower_shadow: np.ndarray,
    frac_body: np.ndarray,
    dominant_threshold: float = 0.5,
    doji_body_threshold: float = 0.1,
) -> np.ndarray:
    """
    Shape classification based on range fractions.

    Rules:
      - if frac_body <= doji_body_threshold -> "doji-ish"
      - else if frac_upper_shadow >= dominant_threshold -> "upper-dominant"
      - else if frac_lower_shadow >= dominant_threshold -> "lower-dominant"
      - else if frac_body >= dominant_threshold -> "body-dominant"
      - else -> balanced
    """
    n = len(frac_body)
    out = np.full(n, "balanced", dtype=object)

    out[frac_body <= doji_body_threshold] = "doji-ish"
    mask = frac_body > doji_body_threshold
    out[mask & (frac_upper_shadow >= dominant_threshold)] = "upper-dominant"
    out[mask & (frac_lower_shadow >= dominant_threshold)] = "lower-dominant"
    out[mask & (frac_body >= dominant_threshold)] = "body-dominant"

    return out

def direction_label(direction_sign: np.ndarray) -> np.ndarray:
    """
    Map sign to string label: bull/bear/flat.
    """
    out = np.full(len(direction_sign), "flat", dtype=object)
    out[direction_sign > 0] = "bull"
    out[direction_sign < 0] = "bear"
    return out

@dataclass(frozen=True)
class InputColumns:
    date: Optional[str]
    open: str
    high: str
    low: str
    close: str

def read_input_table(path: Path, fmt: str) -> pd.DataFrame:
    """
    Read input OHLC table.
    """
    fmt = fmt.lower()
    if fmt != "json":
        raise ValueError(f"Unsupported input format: {fmt}")
    return pd.read_json(path, orient="records", convert_dates=False)
    
def build_candle_batch(dataframe: pd.DataFrame, columns: InputColumns) -> CandleBatch:
    """
    Build CandleBatch from DataFrame.

    Purpose:
      Centralizes column extraction, float conversion, and array materialization.
    """
    return CandleBatch(
        open_price=dataframe[columns.open].astype(float).to_numpy(),
        high_price=dataframe[columns.high].astype(float).to_numpy(),
        low_price=dataframe[columns.low].astype(float).to_numpy(),
        close_price=dataframe[columns.close].astype(float).to_numpy()
    )

def export_table(dataframe: pd.DataFrame, out_path: Path, fmt: str) -> None:
    """
    Export the generated table.

    Supported:
    - csv
    - parquet
    - jsonl
    """
    fmt = fmt.lower()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        dataframe.to_csv(out_path, index=False)
    elif fmt == "parquet":
        dataframe.to_parquet(out_path, index=False)
    elif fmt == "jsonl":
        with out_path.open("w", encoding="utf-8") as f:
            for rec in dataframe.to_dict(orient="records"):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        raise ValueError(f"Unsupported export format: {fmt}")
    
def compute_all_features_and_outcomes(
    dataframe: pd.DataFrame,
    columns: InputColumns,
    horizons: Sequence[int],
    add_categories: bool = True,
    vol_quantiles: int = 4,
) -> pd.DataFrame:
    """
    Main comutation pipeline:
    1) Build CandleBatch
    2) Compute rau candle components (range/net/wicks)
    3) Compute normalizations (prev-close and range fractions)
    4) Compute forward outcomes (logret/MFE/MAE)
    5) Optionally compute categories
    """
    out = dataframe.copy()
    candles = build_candle_batch(out, columns)

    # Raw components
    range_size = candles.compute_range_size()
    net_move = candles.compute_net_move()
    upper_shadow = candles.compute_upper_shadow_size()
    lower_shadow = candles.compute_lower_shadow_size()
    identity_ok = candles.check_range_decomposition_identity()

    # Prev-close normalization
    prev_close = candles.compute_previous_close()

    pct_range_size = candles.normalize_by_previous_close(range_size)
    pct_net_move = candles.normalize_by_previous_close(net_move)
    pct_upper_shadow = candles.normalize_by_previous_close(upper_shadow)
    pct_lower_shadow = candles.normalize_by_previous_close(lower_shadow)

    # Shape fractions
    frac_upper_shadow = candles.fraction_of_range(upper_shadow)
    frac_lower_shadow = candles.fraction_of_range(lower_shadow)
    frac_body = candles.compute_body_fraction()
    direction = candles.compute_direction_sign()

    # Save features into DataFrame (suggestive names)
    out["range_size"] = range_size
    out["net_move"] = net_move
    out["upper_shadow_size"] = upper_shadow
    out["lower_shadow_size"] = lower_shadow
    out["range_identity_ok"] = identity_ok

    out["prev_close"] = prev_close
    out["pct_range_size"] = pct_range_size
    out["pct_net_move"] = pct_net_move
    out["pct_upper_shadow_size"] = pct_upper_shadow
    out["pct_lower_shadow_size"] = pct_lower_shadow

    out["frac_upper_shadow"] = frac_upper_shadow
    out["frac_lower_shadow"] = frac_lower_shadow
    out["frac_body"] = frac_body
    out["direction_sign"] = direction

    # Outcomes
    for k in horizons:
        out[f"fwd_logret_{k}"] = candles.compute_forward_log_return(k)
        out[f"mfe_{k}"] = candles.compute_max_favorable_excursion(k)
        out[f"mae_{k}"] = candles.compute_max_adverse_excursion(k)

    # Categories
    if add_categories:
        out["vol_bin"] = compute_quantile_bins(out["pct_range_size"].to_numpy(), num_bins=vol_quantiles)
        out["shape"] = classify_candle_shape(
            frac_upper_shadow=out["frac_upper_shadow"].to_numpy(),
            frac_lower_shadow=out["frac_lower_shadow"].to_numpy(),
            frac_body=out["frac_body"].to_numpy(),
        )
        out["direction"] = direction_label(out["direction_sign"].to_numpy())
        out["candle_class"] = (
            out["vol_bin"].astype(str) + "|" + out["shape"].astype(str) + "|" + out["direction"].astype(str)
        )

    return out

def main() -> None:
    parser = argparse.ArgumentParser(description="Compute BTC candlestick features and forward outcomes.")
    parser.add_argument("--input", required=True, type=Path, help="Input OHLC file (json).")
    parser.add_argument("--input-fmt", default="json", choices=["json"])
    parser.add_argument("--output", required=True, type=Path, help="Output file path.")
    parser.add_argument("--output-fmt", default="csv", choices=["csv", "parquet", "jsonl"])

    parser.add_argument("--horizons", default="1,3,5,7,10", help="Comma-separated horisons.")
    parser.add_argument("--no-categories", action="store_true", help="Disable candle categories.")
    parser.add_argument("--vol-quantiles", type=int, default=4, help="Quantile bins for vol_bin.")

    args = parser.parse_args()

    columns = InputColumns(
        date="timestamp",
        open="open",
        high="high",
        low="low",
        close="close",
    )

    horizons = sorted(set(int(x.strip()) for x in args.horizons.split(",") if x.strip()))
    dataframe = read_input_table(args.input, args.input_fmt)

    # Ensure time ordering
    dataframe = dataframe.sort_values(columns.date).reset_index(drop=True)

    out = compute_all_features_and_outcomes(
        dataframe=dataframe,
        columns=columns,
        horizons=horizons,
        add_categories=(not args.no_categories),
        vol_quantiles=args.vol_quantiles,
    )

    export_table(out, args.output, args.output_fmt)

if __name__ == "__main__":
    main()
