"""Load and validate BTC daily OHLCV data from the repository data directory.

The default input file lives at ``../data/daily_price.json`` relative to the
``src`` folder. The expected JSON payload is a non-empty array of objects with
this shape:

    {
        "timestamp": "2017-08-17",
        "open": 4261.48,
        "high": 4485.39,
        "low": 4200.74,
        "close": 4285.08,
        "volume": 795.150377
    }

Each record must contain a ``timestamp`` in ``YYYY-MM-DD`` format. OHLC fields
must be strictly positive. ``volume`` may be zero, but it must remain finite and
non-negative.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.path_config import DEFAULT_PRICE_JSON_PATH

DEFAULT_DAILY_PRICE_PATH = str(DEFAULT_PRICE_JSON_PATH)
TIMESTAMP_FORMAT = "%Y-%m-%d"
OHLC_FIELDS: tuple[str, ...] = ("open", "high", "low", "close")
VOLUME_FIELD = "volume"
PRICE_FIELDS: tuple[str, ...] = (*OHLC_FIELDS, VOLUME_FIELD)
REQUIRED_FIELDS: tuple[str, ...] = ("timestamp", *PRICE_FIELDS)


def load_daily_price_json(path: str = DEFAULT_DAILY_PRICE_PATH) -> pd.DataFrame:
    """Load validated BTC daily OHLCV data into a timestamp-indexed DataFrame.

    Parameters:
        path: Path to the JSON file. Defaults to ``../data/daily_price.json``
            relative to the repository ``statistics/src`` folder.

    Returns:
        A ``pandas.DataFrame`` indexed by ``timestamp`` with numeric ``open``,
        ``high``, ``low``, ``close``, and ``volume`` columns.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON payload does not match the expected schema.
    """
    payload = _read_daily_price_file(path)
    records = _validate_daily_price_payload(payload, path)
    return _build_daily_price_frame(records)


def load_daily_price_timestamps(path: str = DEFAULT_DAILY_PRICE_PATH) -> pd.DatetimeIndex:
    """Return the validated timestamp index from the BTC daily price file."""
    return load_daily_price_json(path).index


def load_daily_price_open(path: str = DEFAULT_DAILY_PRICE_PATH) -> pd.Series:
    """Return the validated ``open`` series from the BTC daily price file."""
    return _load_daily_price_field(path, "open")


def load_daily_price_high(path: str = DEFAULT_DAILY_PRICE_PATH) -> pd.Series:
    """Return the validated ``high`` series from the BTC daily price file."""
    return _load_daily_price_field(path, "high")


def load_daily_price_low(path: str = DEFAULT_DAILY_PRICE_PATH) -> pd.Series:
    """Return the validated ``low`` series from the BTC daily price file."""
    return _load_daily_price_field(path, "low")


def load_daily_price_close(path: str = DEFAULT_DAILY_PRICE_PATH) -> pd.Series:
    """Return the validated ``close`` series from the BTC daily price file."""
    return _load_daily_price_field(path, "close")


def load_daily_price_volume(path: str = DEFAULT_DAILY_PRICE_PATH) -> pd.Series:
    """Return the validated ``volume`` series from the BTC daily price file."""
    return _load_daily_price_field(path, "volume")


def _load_daily_price_field(path: str, field_name: str) -> pd.Series:
    frame = load_daily_price_json(path)
    return frame[field_name]


def _read_daily_price_file(path: str) -> Any:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Daily price file not found: {file_path}")

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {file_path}: {exc.msg} at line {exc.lineno}, column {exc.colno}.") from exc


def _validate_daily_price_payload(payload: Any, path: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError(
            f"Daily price payload in {path} must be a JSON array of objects, got {type(payload).__name__}."
        )
    if not payload:
        raise ValueError(f"Daily price payload in {path} is empty.")

    validated_rows: list[dict[str, Any]] = []
    seen_timestamps: set[str] = set()
    for index, row in enumerate(payload):
        validated_row = _validate_daily_price_row(row, index)
        timestamp = validated_row["timestamp"]
        if timestamp in seen_timestamps:
            raise ValueError(f"Duplicate timestamp '{timestamp}' found at entry {index}.")
        seen_timestamps.add(timestamp)
        validated_rows.append(validated_row)

    return validated_rows


def _validate_daily_price_row(row: Any, index: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"Entry {index} must be a JSON object, got {type(row).__name__}.")

    missing_fields = [field for field in REQUIRED_FIELDS if field not in row]
    if missing_fields:
        raise ValueError(f"Entry {index} is missing required fields: {', '.join(missing_fields)}.")

    validated_row: dict[str, Any] = {
        "timestamp": _validate_timestamp(row["timestamp"], index),
    }
    for field_name in OHLC_FIELDS:
        validated_row[field_name] = _validate_positive_number(row[field_name], field_name, index)
    validated_row[VOLUME_FIELD] = _validate_non_negative_number(row[VOLUME_FIELD], VOLUME_FIELD, index)

    return validated_row


def _validate_timestamp(value: Any, index: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Entry {index} field 'timestamp' must be a string in {TIMESTAMP_FORMAT} format.")

    try:
        parsed = datetime.strptime(value, TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Entry {index} field 'timestamp' must match {TIMESTAMP_FORMAT}; got {value!r}."
        ) from exc

    if parsed.strftime(TIMESTAMP_FORMAT) != value:
        raise ValueError(
            f"Entry {index} field 'timestamp' must be normalized as {TIMESTAMP_FORMAT}; got {value!r}."
        )

    return value


def _validate_positive_number(value: Any, field_name: str, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Entry {index} field '{field_name}' must be a positive number, got {value!r}.")
    if value <= 0:
        raise ValueError(f"Entry {index} field '{field_name}' must be greater than 0, got {value!r}.")
    return float(value)


def _validate_non_negative_number(value: Any, field_name: str, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Entry {index} field '{field_name}' must be a finite non-negative number, got {value!r}.")
    numeric_value = float(value)
    if not pd.notna(numeric_value):
        raise ValueError(f"Entry {index} field '{field_name}' must be finite, got {value!r}.")
    if numeric_value < 0:
        raise ValueError(f"Entry {index} field '{field_name}' must be greater than or equal to 0, got {value!r}.")
    return numeric_value


def _build_daily_price_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(records)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], format=TIMESTAMP_FORMAT)
    frame = frame.sort_values("timestamp")
    frame = frame.set_index("timestamp")
    frame.index.name = "timestamp"
    return frame
