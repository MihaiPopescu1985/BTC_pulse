#!/usr/bin/env python3
"""Build descriptive BTC on-chain features from the repository data directory.

Inputs default to the BTC-specific repository layout relative to ``statistics/src``:
- ``../data/daily_amounts.json``
- ``../data/daily_tx_size.json``

Output defaults to:
- ``../out/onchain_features.csv``

The runner stays descriptive only. It does not fit models or emit trading
signals.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv
from src.path_config import DEFAULT_AMOUNTS_JSON_PATH, DEFAULT_ONCHAIN_FEATURES_CSV_PATH, DEFAULT_TX_SIZE_JSON_PATH


def _load_amounts(path: Path) -> Dict[str, float]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path} must be a JSON object mapping date to amount.")
    out: Dict[str, float] = {}
    for key, value in obj.items():
        if value is None:
            continue
        try:
            out[str(key)] = float(value)
        except Exception:
            continue
    return out


def _load_tx_size(path: Path) -> Dict[str, List[float]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(f"{path} must be a JSON array of rows like [date, ...counts].")
    out: Dict[str, List[float]] = {}
    for row in obj:
        if not isinstance(row, list) or len(row) < 2:
            continue
        date = str(row[0])
        values: List[float] = []
        ok = True
        for item in row[1:]:
            try:
                values.append(float(item))
            except Exception:
                ok = False
                break
        if ok:
            out[date] = values
    return out


def _sorted_dates(*dicts: dict[str, object]) -> List[str]:
    keys: set[str] = set()
    for mapping in dicts:
        keys.update(mapping.keys())
    return sorted(keys)


def _rolling_zscore(values: List[Optional[float]], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    buffer: List[float] = []
    for index, value in enumerate(values):
        if value is None or not math.isfinite(value):
            buffer.append(float("nan"))
        else:
            buffer.append(float(value))

        if index + 1 < window:
            continue

        window_values = buffer[index + 1 - window : index + 1]
        window_values = [item for item in window_values if math.isfinite(item)]
        if len(window_values) < max(10, window // 5):
            out[index] = None
            continue

        mean = sum(window_values) / len(window_values)
        variance = sum((item - mean) ** 2 for item in window_values) / max(1, len(window_values) - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std == 0.0:
            out[index] = 0.0
        else:
            out[index] = (float(value) - mean) / std if (value is not None and math.isfinite(value)) else None
    return out


def _pct_change(values: List[Optional[float]]) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    prev: Optional[float] = None
    for index, value in enumerate(values):
        if value is None or not math.isfinite(value):
            out[index] = None
            continue
        if prev is None or prev == 0 or not math.isfinite(prev):
            out[index] = None
        else:
            out[index] = (value / prev) - 1.0
        prev = value
    return out


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for descriptive BTC on-chain features."""
    parser = argparse.ArgumentParser(
        description="Build descriptive BTC on-chain features and export them to ../out/onchain_features.csv by default.",
    )
    parser.add_argument("--amounts-json", type=Path, default=DEFAULT_AMOUNTS_JSON_PATH, help="Default: ../data/daily_amounts.json")
    parser.add_argument("--tx-size-json", type=Path, default=DEFAULT_TX_SIZE_JSON_PATH, help="Default: ../data/daily_tx_size.json")
    parser.add_argument("--out-csv", "--out-json", dest="out_csv", type=Path, default=DEFAULT_ONCHAIN_FEATURES_CSV_PATH, help="Default: ../out/onchain_features.csv")
    parser.add_argument("--zwin", type=int, default=365, help="Rolling window for z-scores in days.")
    parser.add_argument(
        "--whale-mode",
        choices=["last_bucket", "last_two_buckets"],
        default="last_bucket",
        help=(
            "How to define ONCHAIN_TX_WHALE from tx-size buckets. "
            "last_bucket uses the final bucket only; last_two_buckets sums the final two buckets."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Build and export descriptive BTC on-chain features."""
    args = parse_args()
    amounts = _load_amounts(args.amounts_json)
    tx = _load_tx_size(args.tx_size_json)
    dates = _sorted_dates(amounts, tx)

    total_amount: List[Optional[float]] = [amounts.get(date) for date in dates]
    vol_log: List[Optional[float]] = [math.log(max(1e-12, value)) if (value is not None and value > 0) else None for value in total_amount]
    vol_z = _rolling_zscore(vol_log, args.zwin)

    whale_tx: List[Optional[float]] = []
    mid_tx: List[Optional[float]] = []
    small_tx: List[Optional[float]] = []

    for date in dates:
        row = tx.get(date)
        if not row or len(row) < 2:
            whale_tx.append(None)
            mid_tx.append(None)
            small_tx.append(None)
            continue

        last = float(row[-1])
        second_last = float(row[-2]) if len(row) >= 2 else 0.0
        rest = row[:-2] if len(row) >= 2 else []

        if args.whale_mode == "last_two_buckets" and len(row) >= 3:
            whale_value = last + second_last
            mid_value = float(row[-3])
            small_value = float(sum(row[:-3]))
        else:
            whale_value = last
            mid_value = second_last
            small_value = float(sum(rest)) if rest else 0.0

        whale_tx.append(whale_value)
        mid_tx.append(mid_value)
        small_tx.append(small_value)

    whale_share: List[Optional[float]] = []
    dominance: List[Optional[float]] = []
    for whale_value, mid_value, small_value in zip(whale_tx, mid_tx, small_tx):
        if whale_value is None or mid_value is None or small_value is None:
            whale_share.append(None)
            dominance.append(None)
            continue
        denom = whale_value + mid_value + small_value
        whale_share.append((whale_value / denom) if denom > 0 else None)
        dominance.append(((whale_value + mid_value) / small_value) if small_value > 0 else None)

    dom_log: List[Optional[float]] = [math.log(max(1e-12, value)) if (value is not None and value > 0) else None for value in dominance]
    dom_z = _rolling_zscore(dom_log, args.zwin)
    whale_share_z = _rolling_zscore(whale_share, args.zwin)

    frame = pd.DataFrame(
        {
            "ONCHAIN_AMOUNT_TOTAL": total_amount,
            "ONCHAIN_AMOUNT_LOG": vol_log,
            "ONCHAIN_TX_WHALE": whale_tx,
            "ONCHAIN_TX_MID": mid_tx,
            "ONCHAIN_TX_SMALL": small_tx,
            "ONCHAIN_WHALE_SHARE": whale_share,
            "ONCHAIN_DOMINANCE": dominance,
            "ONCHAIN_VOL_Z": vol_z,
            "ONCHAIN_DOM_Z": dom_z,
            "ONCHAIN_WHALE_SHARE_Z": whale_share_z,
            "ONCHAIN_AMOUNT_PCT": _pct_change(total_amount),
            "ONCHAIN_WHALE_TX_PCT": _pct_change(whale_tx),
            "ONCHAIN_DOM_PCT": _pct_change(dominance),
        },
        index=pd.to_datetime(dates),
    )

    export_frame = export_feature_csv(frame, args.out_csv, columns=list(frame.columns))
    if export_frame.columns[0] != "date":
        raise ValueError("On-chain feature export must use 'date' as the first CSV column.")
    print(f"Wrote {args.out_csv} with {len(frame)} rows and {len(frame.columns)} series.")


if __name__ == "__main__":
    main()
