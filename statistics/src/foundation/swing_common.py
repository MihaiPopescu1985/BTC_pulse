from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_ONCHAIN_FEATURES_CSV_PATH
from src.research.v4_iteration.core.interaction_discovery.run_interaction_discovery import (
    build_additional_cutoffs,
    build_templates,
    finalize_templates,
    quantile_cutoffs,
)


SWING_ATR_WINDOW = 10
SWING_REVERSAL_K = 1.5
SWING_GRANULARITY_LABEL = "medium_atr10_k1.5"


@dataclass(frozen=True)
class ConditionSpec:
    name: str
    family: str
    description: str
    builder: Callable


def load_feature_onchain_dataset(
    features_csv: str | Path = DEFAULT_FEATURES_CSV_PATH,
    onchain_features_csv: str | Path = DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
) -> pd.DataFrame:
    features = load_feature_csv(features_csv)
    onchain = load_feature_csv(onchain_features_csv)
    return features.merge(onchain, on="date", how="inner", validate="one_to_one").sort_values("date").reset_index(drop=True)


def compute_swing_taxonomy(swings: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    if swings.empty:
        raise ValueError("Swing taxonomy requires a non-empty swing table.")

    taxonomy = swings.copy()
    taxonomy["swing_id"] = np.arange(1, len(taxonomy) + 1, dtype=int)
    taxonomy["abs_amplitude_pct"] = taxonomy["amplitude_pct"].abs()
    taxonomy["start_date"] = pd.to_datetime(taxonomy["start_date"])
    taxonomy["end_date"] = pd.to_datetime(taxonomy["end_date"])

    size_q33 = float(taxonomy["abs_amplitude_pct"].quantile(1.0 / 3.0))
    size_q67 = float(taxonomy["abs_amplitude_pct"].quantile(2.0 / 3.0))
    duration_q33 = float(taxonomy["duration_days"].quantile(1.0 / 3.0))
    duration_q67 = float(taxonomy["duration_days"].quantile(2.0 / 3.0))

    def classify_size(value: float) -> str:
        if value <= size_q33:
            return "small"
        if value <= size_q67:
            return "medium"
        return "large"

    def classify_duration(value: float) -> str:
        if value <= duration_q33:
            return "short"
        if value <= duration_q67:
            return "medium"
        return "long"

    taxonomy["size_class"] = taxonomy["abs_amplitude_pct"].apply(classify_size)
    taxonomy["duration_class"] = taxonomy["duration_days"].apply(classify_duration)
    taxonomy["atr_window"] = SWING_ATR_WINDOW
    taxonomy["reversal_k"] = SWING_REVERSAL_K
    taxonomy["swing_granularity"] = SWING_GRANULARITY_LABEL

    thresholds = {
        "size_q33": size_q33,
        "size_q67": size_q67,
        "duration_q33": duration_q33,
        "duration_q67": duration_q67,
    }
    return taxonomy, thresholds


def build_selected_conditions(frame: pd.DataFrame) -> list[ConditionSpec]:
    quantiles = build_additional_cutoffs(frame, quantile_cutoffs(frame))
    interaction_templates = {
        template.name: template
        for template in finalize_templates(build_templates())
        if template.name
        in {
            "structural_onchain_tailwind",
            "upside_probability_stack",
            "expansion_with_participation",
            "low_risk_base",
            "constructive_pullback",
            "low_risk_pullback",
            "extended_noisy_chase",
            "shock_whale_risk",
            "weak_mixed_high_noise",
        }
    }

    manual_conditions = [
        ConditionSpec(
            name="trend_backdrop_constructive",
            family="reference",
            description="TS_50 > 0, TS_200 > 0, ER_50 at least median.",
            builder=lambda df: (df["TS_50"] > 0) & (df["TS_200"] > 0) & (df["ER_50"] >= quantiles["ER_50_q50"]),
        ),
        ConditionSpec(
            name="rebound_skew_low_shock",
            family="reference",
            description="P_REBOUND_10D_CAL high and P_SHOCK_HMM at or below median.",
            builder=lambda df: (df["P_REBOUND_10D_CAL"] >= quantiles["P_REBOUND_10D_CAL_q75"])
            & (df["P_SHOCK_HMM"] <= quantiles["P_SHOCK_HMM_q50"]),
        ),
        ConditionSpec(
            name="onchain_dominance_support",
            family="reference",
            description="ONCHAIN_DOM_Z high with ONCHAIN_VOL_Z at least median.",
            builder=lambda df: (df["ONCHAIN_DOM_Z"] >= quantiles["ONCHAIN_DOM_Z_q75"])
            & (df["ONCHAIN_VOL_Z"] >= quantiles["ONCHAIN_VOL_Z_q50"]),
        ),
        ConditionSpec(
            name="bearish_risk_regime",
            family="reference",
            description="TS_50 < 0 and correction risk high.",
            builder=lambda df: (df["TS_50"] < 0) & (df["P_CORRECTION_10D_CAL"] >= quantiles["P_CORRECTION_10D_CAL_q75"]),
        ),
    ]

    selected = [
        ConditionSpec(
            name=template.name,
            family=template.family,
            description=template.description,
            builder=lambda df, builder=template.builder: builder(df, quantiles),
        )
        for template in interaction_templates.values()
    ]
    selected.extend(manual_conditions)
    return selected


def map_dates_to_containing_swings(dates: pd.Series, taxonomy: pd.DataFrame) -> pd.DataFrame:
    sorted_tax = taxonomy.sort_values(["start_date", "end_date"]).reset_index(drop=True)

    rows: list[dict[str, object]] = []
    for date in pd.to_datetime(dates):
        candidates = sorted_tax.loc[(sorted_tax["start_date"] <= date) & (sorted_tax["end_date"] >= date)]
        if candidates.empty:
            rows.append(
                {
                    "date": date,
                    "containing_swing_id": np.nan,
                    "containing_swing_direction": np.nan,
                    "containing_swing_abs_amplitude": np.nan,
                    "containing_swing_duration_days": np.nan,
                    "containing_swing_size_class": np.nan,
                    "containing_swing_duration_class": np.nan,
                    "containing_swing_stage_pct": np.nan,
                    "containing_swing_stage_bucket": np.nan,
                }
            )
            continue
        swing = candidates.iloc[0]
        duration_days = max(int(swing["duration_days"]), 1)
        stage_pct = float((date - swing["start_date"]).days / duration_days)
        if stage_pct <= 1.0 / 3.0:
            stage_bucket = "early"
        elif stage_pct <= 2.0 / 3.0:
            stage_bucket = "mid"
        else:
            stage_bucket = "late"

        rows.append(
            {
                "date": date,
                "containing_swing_id": int(swing["swing_id"]),
                "containing_swing_direction": swing["direction"],
                "containing_swing_abs_amplitude": float(swing["abs_amplitude_pct"]),
                "containing_swing_duration_days": float(swing["duration_days"]),
                "containing_swing_size_class": swing["size_class"],
                "containing_swing_duration_class": swing["duration_class"],
                "containing_swing_stage_pct": stage_pct,
                "containing_swing_stage_bucket": stage_bucket,
            }
        )

    return pd.DataFrame(rows)


def map_dates_to_next_swings(dates: pd.Series, taxonomy: pd.DataFrame) -> pd.DataFrame:
    sorted_tax = taxonomy.sort_values(["start_date", "end_date"]).reset_index(drop=True)
    starts = sorted_tax["start_date"].tolist()

    rows: list[dict[str, object]] = []
    swing_index = 0
    for date in pd.to_datetime(dates):
        while swing_index < len(sorted_tax) and starts[swing_index] <= date:
            swing_index += 1

        if swing_index >= len(sorted_tax):
            rows.append(
                {
                    "date": date,
                    "next_swing_id": np.nan,
                    "next_swing_direction": np.nan,
                    "next_swing_abs_amplitude": np.nan,
                    "next_swing_duration_days": np.nan,
                    "next_swing_size_class": np.nan,
                    "next_swing_duration_class": np.nan,
                }
            )
            continue

        swing = sorted_tax.iloc[swing_index]
        rows.append(
            {
                "date": date,
                "next_swing_id": int(swing["swing_id"]),
                "next_swing_direction": swing["direction"],
                "next_swing_abs_amplitude": float(swing["abs_amplitude_pct"]),
                "next_swing_duration_days": float(swing["duration_days"]),
                "next_swing_size_class": swing["size_class"],
                "next_swing_duration_class": swing["duration_class"],
            }
        )

    return pd.DataFrame(rows)

