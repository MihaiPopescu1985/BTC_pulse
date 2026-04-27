from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.data.feature_store import load_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_PRICE_JSON_PATH, OUT_DIR, STATISTICS_DIR
from src.dashboard.view_registry import VIEW_REGISTRY, ViewDefinition


DEFAULT_SWINGS_CSV_PATH = OUT_DIR / "swing_detection" / "swings.csv"


def _json_safe_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def _series_to_json_values(values: pd.Series) -> list[Any]:
    if pd.api.types.is_datetime64_any_dtype(values):
        return [value.strftime("%Y-%m-%d") if not pd.isna(value) else None for value in values]
    return [_json_safe_scalar(value) for value in values.tolist()]


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (STATISTICS_DIR.parent / path).resolve() if str(path).startswith("statistics/") else (STATISTICS_DIR / path).resolve()


def infer_view_groups(columns: list[str]) -> dict[str, list[str]]:
    score_columns = [column for column in columns if column.endswith("_score")]
    component_columns = [
        column
        for column in columns
        if any(token in column for token in ("_prob", "_analog_", "_exhaustion_")) and column not in score_columns
    ]
    label_columns = [
        column
        for column in columns
        if column.startswith(("buy_zone_", "sell_zone_", "bottom_zone_", "near_current_")) or column.endswith("_target")
    ]
    diagnostics = [
        column
        for column in columns
        if column not in score_columns and column not in component_columns and column not in label_columns
        and any(token in column for token in ("swing", "pivot", "dist_", "days_", "state", "label"))
    ]
    return {
        "scores": score_columns,
        "components": component_columns,
        "labels": label_columns,
        "diagnostics": diagnostics,
    }


def build_runtime_registry(custom_dataset: str | None = None) -> tuple[dict[str, dict[str, Any]], str]:
    registry: dict[str, dict[str, Any]] = {name: dict(definition) for name, definition in VIEW_REGISTRY.items()}
    active_view = "swing_extreme_timing"
    if custom_dataset:
        custom_path = resolve_path(custom_dataset)
        if not custom_path.is_file():
            raise FileNotFoundError(f"Custom dataset not found: {custom_path}")
        custom_frame = load_feature_csv(custom_path)
        groups = infer_view_groups([column for column in custom_frame.columns if column != "date"])
        registry["custom_dataset"] = {
            "label": "Custom Dataset",
            "description": f"Ad hoc view for {custom_path.name}",
            "path": str(custom_path),
            "scores": groups["scores"],
            "components": groups["components"],
            "labels": groups["labels"],
            "diagnostics": groups["diagnostics"],
            "default_scores": groups["scores"][:2],
            "default_components": groups["components"][:6],
            "default_labels": groups["labels"][:4],
            "default_threshold": 0.75,
        }
        active_view = "custom_dataset"
    return registry, active_view


def get_view_definition(registry: dict[str, dict[str, Any]], view_name: str) -> dict[str, Any]:
    if view_name not in registry:
        raise KeyError(f"Unknown dashboard view: {view_name}")
    return registry[view_name]


def load_swings(swings_path: Path = DEFAULT_SWINGS_CSV_PATH) -> list[dict[str, Any]] | None:
    if not swings_path.is_file():
        return None
    rows = pd.read_csv(swings_path)
    expected = {"start_date", "end_date", "direction", "amplitude_pct", "duration_days"}
    missing = expected - set(rows.columns)
    if missing:
        raise ValueError(f"Swings CSV is missing required columns: {sorted(missing)}")
    return [{key: _json_safe_scalar(value) for key, value in row.items()} for row in rows.to_dict(orient="records")]


def load_view_payload(
    registry: dict[str, dict[str, Any]],
    view_name: str,
    *,
    price_json_path: str | Path = DEFAULT_PRICE_JSON_PATH,
) -> dict[str, Any]:
    view = get_view_definition(registry, view_name)
    dataset_path = resolve_path(view["path"])
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset for view '{view_name}' not found: {dataset_path}")

    price = load_daily_price_json(str(price_json_path)).reset_index().rename(columns={"timestamp": "date"})
    price["date"] = pd.to_datetime(price["date"], errors="raise")
    dataset = load_feature_csv(dataset_path)
    dataset["date"] = pd.to_datetime(dataset["date"], errors="raise")

    dataset_extra = dataset.drop(columns=["open", "high", "low", "close", "volume"], errors="ignore")
    merged = price.merge(dataset_extra, on="date", how="left", validate="one_to_one").sort_values("date").reset_index(drop=True)

    groups = infer_view_groups([column for column in merged.columns if column not in {"date", "open", "high", "low", "close", "volume"}])
    for key in ("scores", "components", "labels", "diagnostics"):
        explicit = [column for column in view.get(key, []) if column in merged.columns]
        groups[key] = explicit if explicit else groups[key]

    default_scores = [column for column in view.get("default_scores", []) if column in merged.columns]
    default_components = [column for column in view.get("default_components", []) if column in merged.columns]
    default_labels = [column for column in view.get("default_labels", []) if column in merged.columns]

    series: dict[str, list[Any]] = {}
    for column in merged.columns:
        if column == "date":
            continue
        series[column] = _series_to_json_values(merged[column])

    payload = {
        "view": {
            "name": view_name,
            "label": view.get("label", view_name),
            "description": view.get("description", ""),
            "path": str(dataset_path),
            "scores": groups["scores"],
            "components": groups["components"],
            "labels": groups["labels"],
            "diagnostics": groups["diagnostics"],
            "default_scores": default_scores,
            "default_components": default_components,
            "default_labels": default_labels,
            "default_threshold": float(view.get("default_threshold", 0.75)),
        },
        "dates": merged["date"].dt.strftime("%Y-%m-%d").tolist(),
        "price": {
            "open": _series_to_json_values(pd.to_numeric(merged["open"], errors="coerce")),
            "high": _series_to_json_values(pd.to_numeric(merged["high"], errors="coerce")),
            "low": _series_to_json_values(pd.to_numeric(merged["low"], errors="coerce")),
            "close": _series_to_json_values(pd.to_numeric(merged["close"], errors="coerce")),
            "volume": _series_to_json_values(pd.to_numeric(merged["volume"], errors="coerce")),
        },
        "series": series,
        "swings": load_swings(),
    }
    return payload
