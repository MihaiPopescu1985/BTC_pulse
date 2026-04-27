from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.foundation.swing_common import SWING_ATR_WINDOW, SWING_REVERSAL_K, compute_swing_taxonomy
from src.foundation.swing_detection import detect_swings


def validate_date_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"{name} input is empty.")
    if "date" not in frame.columns:
        raise ValueError(f"{name} input must contain a 'date' column.")
    validated = frame.copy()
    validated["date"] = pd.to_datetime(validated["date"], errors="raise")
    if validated["date"].duplicated().any():
        raise ValueError(f"{name} input has duplicate dates.")
    return validated.sort_values("date").reset_index(drop=True)


def load_inputs(
    price_json: str | Path,
    features_csv: str | Path,
    onchain_features_csv: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from src.data.feature_store import load_feature_csv

    price = load_daily_price_json(str(price_json)).reset_index().rename(columns={"timestamp": "date"})
    price = validate_date_frame("price", price.loc[:, ["date", "open", "high", "low", "close", "volume"]])

    features = validate_date_frame("features", load_feature_csv(features_csv))
    onchain = validate_date_frame("onchain_features", load_feature_csv(onchain_features_csv))

    if len(price) != len(features):
        raise ValueError("price and features must have the same row count.")
    if not price["date"].equals(features["date"]):
        raise ValueError("price and features are not date-aligned.")
    missing_onchain_dates = price.loc[~price["date"].isin(onchain["date"]), "date"]
    if not missing_onchain_dates.empty:
        raise ValueError(
            "on-chain features do not fully cover the price date range; "
            f"first missing date: {missing_onchain_dates.iloc[0].date()}"
        )

    for column in ("open", "high", "low", "close", "volume"):
        if column in features.columns:
            price_values = pd.to_numeric(price[column], errors="coerce").to_numpy(dtype=float)
            feature_values = pd.to_numeric(features[column], errors="coerce").to_numpy(dtype=float)
            if not np.allclose(price_values, feature_values, rtol=1e-10, atol=1e-10):
                raise ValueError(f"Price mismatch between daily_price.json and features.csv for column '{column}'.")
    return price, features, onchain


def build_enriched_taxonomy(price: pd.DataFrame) -> pd.DataFrame:
    price_indexed = price.set_index("date")
    swings, _ = detect_swings(price_indexed, reversal_k=SWING_REVERSAL_K, atr_window=SWING_ATR_WINDOW)
    taxonomy, _ = compute_swing_taxonomy(swings)
    enriched = taxonomy.copy()

    start_dates = pd.to_datetime(enriched["start_date"])
    end_dates = pd.to_datetime(enriched["end_date"])
    start_high = price_indexed.loc[start_dates, "high"].to_numpy(dtype=float)
    start_low = price_indexed.loc[start_dates, "low"].to_numpy(dtype=float)
    end_high = price_indexed.loc[end_dates, "high"].to_numpy(dtype=float)
    end_low = price_indexed.loc[end_dates, "low"].to_numpy(dtype=float)

    enriched["start_pivot_price"] = np.where(enriched["direction"].eq("up"), start_low, start_high)
    enriched["end_pivot_price"] = np.where(enriched["direction"].eq("up"), end_high, end_low)
    enriched["swing_low_date"] = np.where(enriched["direction"].eq("down"), end_dates, start_dates)
    enriched["swing_low_price"] = np.where(enriched["direction"].eq("down"), end_low, start_low)
    enriched["swing_high_date"] = np.where(enriched["direction"].eq("down"), start_dates, end_dates)
    enriched["swing_high_price"] = np.where(enriched["direction"].eq("down"), start_high, end_high)
    return enriched


def build_base_dataset(price: pd.DataFrame, features: pd.DataFrame, onchain: pd.DataFrame) -> pd.DataFrame:
    onchain_renamed = onchain.drop(
        columns=[column for column in ("open", "high", "low", "close", "volume") if column in onchain.columns],
        errors="ignore",
    )
    merged = features.merge(onchain_renamed, on="date", how="inner", validate="one_to_one")
    if not merged["date"].equals(price["date"]):
        raise ValueError("Merged feature surface is not one-row-per-day aligned to the price series.")
    return merged
