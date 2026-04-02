from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DATE_COLUMN = "date"


def export_feature_csv(
    frame: pd.DataFrame,
    path: str | Path,
    *,
    columns: list[str] | tuple[str, ...] | None = None,
    dropna_on: str | None = None,
) -> pd.DataFrame:
    """Write a date-first CSV feature store.

    The exported contract is:
    - first column: ``date`` formatted as ``YYYY-MM-DD``
    - remaining columns: feature series in column order
    """
    export = frame.copy()
    if columns is not None:
        export = export.loc[:, list(columns)]
    if dropna_on is not None:
        if dropna_on not in export.columns:
            raise ValueError(f"dropna_on column '{dropna_on}' is not present in the export frame.")
        export = export.loc[export[dropna_on].notna()].copy()

    if isinstance(export.index, pd.DatetimeIndex):
        date_values = export.index.strftime("%Y-%m-%d")
    else:
        date_values = pd.to_datetime(export.index, errors="raise").strftime("%Y-%m-%d")

    export.insert(0, DATE_COLUMN, date_values)

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(out_path, index=False, float_format="%.8f")
    return export


def load_feature_csv(path: str | Path) -> pd.DataFrame:
    """Load a SAFE CSV feature store with ``date`` as the first column."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Feature CSV not found: {csv_path}")

    frame = pd.read_csv(csv_path)
    if DATE_COLUMN not in frame.columns:
        raise ValueError(f"{csv_path} must contain a '{DATE_COLUMN}' column.")
    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN], errors="raise")
    frame = frame.sort_values(DATE_COLUMN).reset_index(drop=True)
    return frame


def load_feature_series(path: str | Path) -> tuple[pd.Index, dict[str, list[Any]]]:
    """Load a SAFE CSV store into the legacy dates/series shape for model consumers."""
    frame = load_feature_csv(path)
    dates = pd.Index(frame[DATE_COLUMN].dt.strftime("%Y-%m-%d"), dtype="object")
    series = {column: frame[column].tolist() for column in frame.columns if column != DATE_COLUMN}
    return dates, series
