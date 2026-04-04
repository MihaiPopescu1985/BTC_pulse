from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_PRICE_JSON_PATH, DEFAULT_TARGETS_CSV_PATH


RETURN_HORIZONS: tuple[int, ...] = (1, 3, 5, 10, 20)
EXCURSION_HORIZONS: tuple[int, ...] = (3, 5, 10)
FIRST_TOUCH_HORIZONS: tuple[int, ...] = (3, 5, 10)
TOUCH_SPECS: tuple[tuple[float, int], ...] = (
    (0.02, 3),
    (0.02, 5),
    (0.02, 10),
    (0.05, 10),
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the BTC forward-target runner."""
    parser = argparse.ArgumentParser(
        description="Compute BTC ground-truth forward targets and export them to ../out/targets.csv.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--out-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    return parser.parse_args()


def _validate_target_input(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the OHLC columns required for forward target construction."""
    if frame.empty:
        raise ValueError("Target generation received an empty OHLCV table.")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("Target generation requires a DatetimeIndex.")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("Target generation requires dates sorted in increasing order.")
    if frame.index.has_duplicates:
        raise ValueError("Target generation does not accept duplicate timestamps.")

    required_columns = ("open", "high", "low", "close")
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Target generation is missing OHLC columns: {missing_columns}")

    numeric = frame.loc[:, required_columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        bad_rows = numeric[numeric.isna().any(axis=1)].index[:5].strftime("%Y-%m-%d").tolist()
        raise ValueError(f"OHLC input contains invalid numeric values at: {bad_rows}")
    if (numeric <= 0).any().any():
        bad_rows = numeric[(numeric <= 0).any(axis=1)].index[:5].strftime("%Y-%m-%d").tolist()
        raise ValueError(f"OHLC input contains non-positive values at: {bad_rows}")

    return frame.copy()


def _future_window(values: pd.Series, start: int, horizon_days: int) -> np.ndarray | None:
    end = start + horizon_days
    if end >= len(values):
        return None
    return values.iloc[start + 1 : end + 1].to_numpy(dtype=float)


def compute_forward_return_targets(close: pd.Series, horizons: Iterable[int]) -> pd.DataFrame:
    """Compute forward close-to-close returns.

    Definition:
    ret_Nd[t] = close[t+N] / close[t] - 1
    """
    out = pd.DataFrame(index=close.index)
    for horizon in horizons:
        out[f"ret_{horizon}d"] = close.shift(-horizon) / close - 1.0
    return out


def compute_forward_excursion_targets(high: pd.Series, low: pd.Series, close: pd.Series, horizons: Iterable[int]) -> pd.DataFrame:
    """Compute maximum forward upside and downside excursions over each horizon.

    Definitions:
    - max_up_Nd[t] = max(high[t+1:t+N]) / close[t] - 1
    - max_down_Nd[t] = min(low[t+1:t+N]) / close[t] - 1
    """
    out = pd.DataFrame(index=close.index)
    for horizon in horizons:
        max_up = np.full(len(close), np.nan, dtype=float)
        max_down = np.full(len(close), np.nan, dtype=float)
        for index in range(len(close)):
            future_high = _future_window(high, index, horizon)
            future_low = _future_window(low, index, horizon)
            if future_high is None or future_low is None:
                continue
            anchor_close = float(close.iloc[index])
            max_up[index] = float(np.max(future_high) / anchor_close - 1.0)
            max_down[index] = float(np.min(future_low) / anchor_close - 1.0)
        out[f"max_up_{horizon}d"] = max_up
        out[f"max_down_{horizon}d"] = max_down
    return out


def compute_touch_targets(high: pd.Series, low: pd.Series, close: pd.Series, touch_specs: Iterable[tuple[float, int]]) -> pd.DataFrame:
    """Compute binary touch indicators for future barrier hits.

    Definitions:
    - touch_up_Xpct_Nd[t] = 1 if any future high reaches close[t] * (1 + X)
    - touch_down_Xpct_Nd[t] = 1 if any future low reaches close[t] * (1 - X)
    """
    out = pd.DataFrame(index=close.index)
    for pct, horizon in touch_specs:
        up_hits = np.full(len(close), np.nan, dtype=float)
        down_hits = np.full(len(close), np.nan, dtype=float)
        for index in range(len(close)):
            future_high = _future_window(high, index, horizon)
            future_low = _future_window(low, index, horizon)
            if future_high is None or future_low is None:
                continue
            anchor_close = float(close.iloc[index])
            up_barrier = anchor_close * (1.0 + pct)
            down_barrier = anchor_close * (1.0 - pct)
            up_hits[index] = 1.0 if np.any(future_high >= up_barrier) else 0.0
            down_hits[index] = 1.0 if np.any(future_low <= down_barrier) else 0.0
        pct_label = int(round(pct * 100))
        out[f"touch_up_{pct_label}pct_{horizon}d"] = up_hits
        out[f"touch_down_{pct_label}pct_{horizon}d"] = down_hits
    return out


def _first_touch_label(
    future_high: np.ndarray,
    future_low: np.ndarray,
    anchor_close: float,
    pct: float,
) -> str:
    up_barrier = anchor_close * (1.0 + pct)
    down_barrier = anchor_close * (1.0 - pct)

    for high_value, low_value in zip(future_high, future_low):
        up_hit = high_value >= up_barrier
        down_hit = low_value <= down_barrier
        if up_hit and down_hit:
            return "both_same_bar"
        if up_hit:
            return "up"
        if down_hit:
            return "down"
    return "none"


def compute_first_touch_targets(high: pd.Series, low: pd.Series, close: pd.Series, horizons: Iterable[int], pct: float = 0.02) -> pd.DataFrame:
    """Compute categorical first-touch labels using future daily OHLC.

    Labels:
    - ``up``
    - ``down``
    - ``both_same_bar``
    - ``none``
    """
    out = pd.DataFrame(index=close.index)
    for horizon in horizons:
        labels: list[str | float] = [np.nan] * len(close)
        for index in range(len(close)):
            future_high = _future_window(high, index, horizon)
            future_low = _future_window(low, index, horizon)
            if future_high is None or future_low is None:
                continue
            labels[index] = _first_touch_label(future_high, future_low, float(close.iloc[index]), pct)
        out[f"first_touch_2pct_{horizon}d"] = labels
    return out


def compute_targets(price_frame: pd.DataFrame) -> pd.DataFrame:
    """Compute the full SAFE v4.0 Phase 1 truth-layer target table."""
    validated = _validate_target_input(price_frame)
    close = validated["close"]
    high = validated["high"]
    low = validated["low"]

    target_frame = pd.concat(
        [
            compute_forward_return_targets(close, RETURN_HORIZONS),
            compute_forward_excursion_targets(high, low, close, EXCURSION_HORIZONS),
            compute_touch_targets(high, low, close, TOUCH_SPECS),
            compute_first_touch_targets(high, low, close, FIRST_TOUCH_HORIZONS),
        ],
        axis=1,
    )
    return target_frame


def export_targets(target_frame: pd.DataFrame, out_path: Path) -> None:
    """Export the target table as a date-first CSV artifact."""
    export_frame = export_feature_csv(target_frame, out_path, columns=list(target_frame.columns))
    if export_frame.columns[0] != "date":
        raise ValueError("Target export must use 'date' as the first CSV column.")


def print_summary(target_frame: pd.DataFrame, out_path: Path) -> None:
    """Print a compact CLI summary for the truth-layer export."""
    numeric_target_columns = [column for column in target_frame.columns if not column.startswith("first_touch_")]
    first_touch_columns = [column for column in target_frame.columns if column.startswith("first_touch_")]

    print(f"Wrote: {out_path}")
    print(f"Rows written: {len(target_frame)}")
    print(f"Range: {target_frame.index.min().strftime('%Y-%m-%d')} -> {target_frame.index.max().strftime('%Y-%m-%d')}")
    print(
        "Non-null target counts:",
        f"returns={int(target_frame[[c for c in target_frame.columns if c.startswith('ret_')]].notna().all(axis=1).sum())}",
        f"excursions={int(target_frame[[c for c in target_frame.columns if c.startswith('max_')]].notna().all(axis=1).sum())}",
        f"touches={int(target_frame[[c for c in target_frame.columns if c.startswith('touch_')]].notna().all(axis=1).sum())}",
        f"first_touch={int(target_frame[first_touch_columns].notna().all(axis=1).sum())}",
    )
    print(f"Numeric target columns: {len(numeric_target_columns)} | first-touch columns: {len(first_touch_columns)}")


def main() -> None:
    """Run the BTC ground-truth target pipeline end to end."""
    try:
        args = parse_args()
        price_frame = load_daily_price_json(args.price_json)
        target_frame = compute_targets(price_frame)
        out_path = Path(args.out_csv)
        export_targets(target_frame, out_path)
        print_summary(target_frame, out_path)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Target pipeline failed: {exc}") from exc


if __name__ == "__main__":
    main()
