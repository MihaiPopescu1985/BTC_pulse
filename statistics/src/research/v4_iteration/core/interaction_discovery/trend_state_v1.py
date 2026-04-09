from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv, load_feature_csv
from src.path_config import DEFAULT_FEATURES_CSV_PATH, OUT_DIR


REQUIRED_COLUMNS: tuple[str, ...] = (
    "TS_20",
    "TS_50",
    "TS_200",
    "ER_20",
    "ER_50",
    "R_14",
    "R_7",
    "LR_20",
)

OUTPUT_COLUMNS: tuple[str, ...] = (
    "trend_state_v1",
    "trend_context_v1",
    "supportive_structure_flag",
    "weak_backdrop_flag",
    "clean_trend_flag",
    "noisy_trend_flag",
    "pullback_flag",
    "rebound_attempt_flag",
    "extended_move_flag",
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the research-stage trend-state layer."""
    parser = argparse.ArgumentParser(
        description="Build the SAFE v4.0 research trend-state v1 layer from ../out/features.csv.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--out-csv", default=str(OUT_DIR / "trend_state_v1.csv"), help="Default: ../out/trend_state_v1.csv")
    return parser.parse_args()


def _require_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and coerce the columns required by the trend-state rules."""
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"features.csv is missing required trend-state columns: {missing}")

    validated = frame.copy()
    for column in REQUIRED_COLUMNS:
        validated[column] = pd.to_numeric(validated[column], errors="coerce")
    return validated


def percentile_rank(series: pd.Series) -> pd.Series:
    """Return percentile ranks in [0, 1] while preserving NaNs."""
    return series.rank(method="average", pct=True)


def build_threshold_context(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Build percentile-rank helpers used by the deterministic state rules."""
    return {
        "ts20_pct": percentile_rank(frame["TS_20"]),
        "ts50_pct": percentile_rank(frame["TS_50"]),
        "ts200_pct": percentile_rank(frame["TS_200"]),
        "er20_pct": percentile_rank(frame["ER_20"]),
        "er50_pct": percentile_rank(frame["ER_50"]),
        "r14_pct": percentile_rank(frame["R_14"]),
        "r7_pct": percentile_rank(frame["R_7"]),
        "lr20_pct": percentile_rank(frame["LR_20"]),
    }


def _bool_to_float(value: bool) -> float:
    return float(value)


def classify_state(row: pd.Series) -> tuple[str | float, str | float, dict[str, float]]:
    """Classify one row into a compact trend state and a move-context label.

    State logic intentionally separates:
    - structure: TS_50, TS_200, TS_20
    - cleanliness: ER_20, ER_50
    - pullback / extension: R_7, R_14
    - shape confirmation: LR_20
    """
    needed = [
        "TS_20",
        "TS_50",
        "TS_200",
        "ER_20",
        "ER_50",
        "R_14",
        "R_7",
        "LR_20",
        "ts20_pct",
        "ts50_pct",
        "ts200_pct",
        "er20_pct",
        "er50_pct",
        "r14_pct",
        "r7_pct",
        "lr20_pct",
    ]
    if any(pd.isna(row[column]) for column in needed):
        flags = {name: np.nan for name in OUTPUT_COLUMNS[2:]}
        return np.nan, np.nan, flags

    supportive_structure = bool(
        row["TS_50"] > 0
        and row["TS_200"] > 0
        and (
            row["TS_20"] > 0
            or (row["TS_20"] > -0.08 and row["LR_20"] > 0)
        )
    )
    strong_structure = bool(
        supportive_structure
        and row["ts50_pct"] >= 0.60
        and row["ts200_pct"] >= 0.55
    )
    weak_backdrop = bool(
        row["TS_50"] <= 0
        and row["TS_200"] <= 0
    )
    clean_trend = bool(
        row["er20_pct"] >= 0.60
        and row["er50_pct"] >= 0.67
    )
    noisy_trend = bool(
        row["er20_pct"] <= 0.33
        and row["er50_pct"] <= 0.40
    )
    recent_pullback = bool(
        supportive_structure
        and row["R_7"] < 0
        and row["R_14"] <= 0.03
    )
    rebound_attempt = bool(
        row["TS_20"] > 0
        and row["LR_20"] > 0
        and row["R_14"] <= 0
    )
    extended_move = bool(
        row["r7_pct"] >= 0.80
        or row["r14_pct"] >= 0.80
    )
    very_extended = bool(
        extended_move
        and row["TS_20"] > 0
        and row["ts20_pct"] >= 0.67
    )

    if strong_structure and clean_trend and not recent_pullback and not very_extended:
        trend_state = "STRONG_CLEAN_UPTREND"
    elif supportive_structure and recent_pullback and row["ER_50"] > 0.10:
        trend_state = "PULLBACK_IN_UPTREND"
    elif supportive_structure and clean_trend:
        trend_state = "WEAK_UPTREND"
    elif supportive_structure and not clean_trend:
        trend_state = "NOISY_UPTREND"
    elif weak_backdrop and rebound_attempt and row["ER_20"] >= 0.18:
        trend_state = "CLEAN_REBOUND_ATTEMPT"
    elif weak_backdrop:
        trend_state = "BEARISH_PRESSURE"
    elif row["ER_20"] <= 0.14 and row["ER_50"] <= 0.10:
        trend_state = "CHOPPY_NEUTRAL"
    else:
        trend_state = "FAILED_BOUNCE_OR_WEAK_STRUCTURE"

    if recent_pullback:
        trend_context = "PULLBACK"
    elif weak_backdrop and rebound_attempt:
        trend_context = "REBOUND_ATTEMPT"
    elif very_extended:
        trend_context = "EXTENDED"
    elif clean_trend and row["R_7"] > 0 and row["R_14"] > 0:
        trend_context = "EARLY_MOVE"
    else:
        trend_context = "CHOP"

    flags = {
        "supportive_structure_flag": _bool_to_float(supportive_structure),
        "weak_backdrop_flag": _bool_to_float(weak_backdrop),
        "clean_trend_flag": _bool_to_float(clean_trend),
        "noisy_trend_flag": _bool_to_float(noisy_trend),
        "pullback_flag": _bool_to_float(recent_pullback),
        "rebound_attempt_flag": _bool_to_float(rebound_attempt),
        "extended_move_flag": _bool_to_float(extended_move),
    }
    return trend_state, trend_context, flags


def compute_trend_state_table(features: pd.DataFrame) -> pd.DataFrame:
    """Compute the date-aligned trend-state v1 table."""
    validated = _require_columns(features)
    context = build_threshold_context(validated)

    enriched = validated.copy()
    for column, series in context.items():
        enriched[column] = series

    rows: list[dict[str, Any]] = []
    for _, row in enriched.iterrows():
        trend_state, trend_context, flags = classify_state(row)
        rows.append(
            {
                "trend_state_v1": trend_state,
                "trend_context_v1": trend_context,
                **flags,
            }
        )

    return pd.DataFrame(rows, index=validated.index)


def print_summary(table: pd.DataFrame) -> None:
    """Print a compact CLI summary for the latest trend-state snapshot."""
    state_counts = table["trend_state_v1"].value_counts(dropna=False)
    context_counts = table["trend_context_v1"].value_counts(dropna=False)

    print(f"Rows written: {len(table)}")
    print(f"Distinct trend_state_v1 labels: {table['trend_state_v1'].nunique(dropna=True)}")
    print(f"Distinct trend_context_v1 labels: {table['trend_context_v1'].nunique(dropna=True)}")
    print("Top trend_state_v1 counts:")
    for label, count in state_counts.head(8).items():
        print(f"  {label}: {int(count)}")
    print("Top trend_context_v1 counts:")
    for label, count in context_counts.head(8).items():
        print(f"  {label}: {int(count)}")

    latest = table.iloc[-1]
    print("Latest snapshot:")
    print(f"  trend_state_v1: {latest['trend_state_v1']}")
    print(f"  trend_context_v1: {latest['trend_context_v1']}")


def main() -> None:
    """Build and export the first research-stage trend-state layer."""
    try:
        args = parse_args()
        features = load_feature_csv(args.features_csv)
        if features.empty:
            raise ValueError("features.csv is empty.")

        result = compute_trend_state_table(features)
        result.index = pd.to_datetime(features["date"], errors="raise")

        export_feature_csv(result, args.out_csv, columns=list(OUTPUT_COLUMNS))
        print_summary(result)
        print(f"Wrote CSV: {Path(args.out_csv)}")
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"trend_state_v1 failed: {exc}") from exc


if __name__ == "__main__":
    main()
