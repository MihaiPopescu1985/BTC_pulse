from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv
from src.path_config import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.productive.run_bottom_dataset import (
    build_base_dataset,
    build_enriched_taxonomy,
    load_inputs,
)
from src.research.v4_iteration.core.swing_bridge.run_live_swing_state import build_live_swing_state
from src.research.v4_iteration.core.swing_bridge.swing_bridge_common import (
    SWING_ATR_WINDOW,
    SWING_GRANULARITY_LABEL,
    SWING_REVERSAL_K,
    map_dates_to_containing_swings,
)


DEFAULT_REVERSAL_ZONE_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_REVERSAL_ZONE_DATASET.md"

LOW_ZONE_LABEL_COLUMNS: tuple[str, ...] = (
    "buy_zone_bottom_10pct_of_range",
    "buy_zone_bottom_5pct_of_range",
    "buy_zone_within_5pct_above_low",
    "buy_zone_within_3pct_above_low",
)
HIGH_ZONE_LABEL_COLUMNS: tuple[str, ...] = (
    "sell_zone_top_10pct_of_range",
    "sell_zone_top_5pct_of_range",
    "sell_zone_within_5pct_below_high",
    "sell_zone_within_3pct_below_high",
)
DISTANCE_LABEL_COLUMNS: tuple[str, ...] = (
    "dist_to_current_down_swing_low_pct",
    "dist_to_current_down_swing_low_range_frac",
    "dist_to_current_up_swing_high_pct",
    "dist_to_current_up_swing_high_range_frac",
)
BOOKKEEPING_COLUMNS: tuple[str, ...] = (
    "current_confirmed_swing_id",
    "current_confirmed_swing_direction",
    "row_is_in_confirmed_down_swing",
    "row_is_in_confirmed_up_swing",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a daily reversal-zone dataset with buyable low-zone and sellable high-zone labels.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument(
        "--onchain-features-csv",
        default=str(DEFAULT_ONCHAIN_FEATURES_CSV_PATH),
        help="Default: ../out/onchain_features.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_dataset.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_REVERSAL_ZONE_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_REVERSAL_ZONE_DATASET.md",
    )
    return parser.parse_args()


def build_current_swing_metadata(dates: pd.Series, taxonomy: pd.DataFrame) -> pd.DataFrame:
    containing = map_dates_to_containing_swings(dates, taxonomy)
    containing = containing.rename(
        columns={
            "containing_swing_id": "current_confirmed_swing_id",
            "containing_swing_direction": "current_confirmed_swing_direction",
            "containing_swing_abs_amplitude": "current_confirmed_swing_abs_amplitude",
            "containing_swing_duration_days": "current_confirmed_swing_duration_days",
            "containing_swing_size_class": "current_confirmed_swing_size_class",
            "containing_swing_duration_class": "current_confirmed_swing_duration_class",
            "containing_swing_stage_pct": "current_confirmed_swing_stage_pct",
            "containing_swing_stage_bucket": "current_confirmed_swing_stage_bucket",
        }
    )

    swing_details = taxonomy.loc[
        :,
        [
            "swing_id",
            "start_date",
            "end_date",
            "swing_low_date",
            "swing_low_price",
            "swing_high_date",
            "swing_high_price",
            "start_pivot_price",
            "end_pivot_price",
        ],
    ].copy()
    swing_details = swing_details.rename(
        columns={
            "swing_id": "current_confirmed_swing_id",
            "start_date": "current_confirmed_swing_start_date",
            "end_date": "current_confirmed_swing_end_date",
            "swing_low_date": "current_confirmed_swing_low_date",
            "swing_low_price": "current_confirmed_swing_low_price",
            "swing_high_date": "current_confirmed_swing_high_date",
            "swing_high_price": "current_confirmed_swing_high_price",
            "start_pivot_price": "current_confirmed_swing_start_pivot_price",
            "end_pivot_price": "current_confirmed_swing_end_pivot_price",
        }
    )
    return containing.merge(swing_details, on="current_confirmed_swing_id", how="left", validate="many_to_one")


def build_dataset(price: pd.DataFrame, features: pd.DataFrame, onchain: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = build_base_dataset(price, features, onchain)
    live_state = build_live_swing_state(price.set_index("date")).reset_index().rename(columns={"timestamp": "date", "index": "date"})
    if "atr_pct" in live_state.columns:
        live_state = live_state.drop(columns=["atr_pct"])
    if "swing_granularity" in live_state.columns:
        live_state = live_state.drop(columns=["swing_granularity"])

    taxonomy = build_enriched_taxonomy(price)
    current_swing = build_current_swing_metadata(base["date"], taxonomy)

    dataset = (
        base.merge(live_state, on="date", how="left", validate="one_to_one")
        .merge(current_swing, on="date", how="left", validate="one_to_one")
        .sort_values("date")
        .reset_index(drop=True)
    )
    return dataset, taxonomy


def add_reversal_zone_labels(dataset: pd.DataFrame) -> pd.DataFrame:
    frame = dataset.copy()
    down_mask = frame["current_confirmed_swing_direction"].eq("down")
    up_mask = frame["current_confirmed_swing_direction"].eq("up")

    frame["row_is_in_confirmed_down_swing"] = down_mask.astype(int)
    frame["row_is_in_confirmed_up_swing"] = up_mask.astype(int)

    low_price = pd.to_numeric(frame["current_confirmed_swing_low_price"], errors="coerce")
    high_price = pd.to_numeric(frame["current_confirmed_swing_high_price"], errors="coerce")
    current_close = pd.to_numeric(frame["close"], errors="coerce")
    swing_range = high_price - low_price

    down_pct = pd.Series(np.nan, index=frame.index, dtype=float)
    down_range_frac = pd.Series(np.nan, index=frame.index, dtype=float)
    valid_down = down_mask & low_price.gt(0)
    down_pct.loc[valid_down] = (current_close.loc[valid_down] / low_price.loc[valid_down] - 1.0).clip(lower=0.0)
    valid_down_range = valid_down & swing_range.gt(0)
    down_range_frac.loc[valid_down_range] = (
        (current_close.loc[valid_down_range] - low_price.loc[valid_down_range]) / swing_range.loc[valid_down_range]
    ).clip(lower=0.0, upper=1.0)

    up_pct = pd.Series(np.nan, index=frame.index, dtype=float)
    up_range_frac = pd.Series(np.nan, index=frame.index, dtype=float)
    valid_up = up_mask & current_close.gt(0)
    up_pct.loc[valid_up] = (high_price.loc[valid_up] / current_close.loc[valid_up] - 1.0).clip(lower=0.0)
    valid_up_range = valid_up & swing_range.gt(0)
    up_range_frac.loc[valid_up_range] = (
        (high_price.loc[valid_up_range] - current_close.loc[valid_up_range]) / swing_range.loc[valid_up_range]
    ).clip(lower=0.0, upper=1.0)

    frame["dist_to_current_down_swing_low_pct"] = down_pct
    frame["dist_to_current_down_swing_low_range_frac"] = down_range_frac
    frame["dist_to_current_up_swing_high_pct"] = up_pct
    frame["dist_to_current_up_swing_high_range_frac"] = up_range_frac

    frame["buy_zone_bottom_10pct_of_range"] = (down_mask & down_range_frac.le(0.10)).astype(int)
    frame["buy_zone_bottom_5pct_of_range"] = (down_mask & down_range_frac.le(0.05)).astype(int)
    frame["buy_zone_within_5pct_above_low"] = (down_mask & down_pct.ge(0.0) & down_pct.le(0.05)).astype(int)
    frame["buy_zone_within_3pct_above_low"] = (down_mask & down_pct.ge(0.0) & down_pct.le(0.03)).astype(int)

    frame["sell_zone_top_10pct_of_range"] = (up_mask & up_range_frac.le(0.10)).astype(int)
    frame["sell_zone_top_5pct_of_range"] = (up_mask & up_range_frac.le(0.05)).astype(int)
    frame["sell_zone_within_5pct_below_high"] = (up_mask & up_pct.ge(0.0) & up_pct.le(0.05)).astype(int)
    frame["sell_zone_within_3pct_below_high"] = (up_mask & up_pct.ge(0.0) & up_pct.le(0.03)).astype(int)
    return frame


def validate_dataset(dataset: pd.DataFrame, price: pd.DataFrame) -> None:
    if dataset.empty:
        raise ValueError("Reversal-zone dataset is empty.")
    if dataset["date"].duplicated().any():
        raise ValueError("Reversal-zone dataset contains duplicate dates.")
    if len(dataset) != len(price):
        raise ValueError("Reversal-zone dataset is not one-row-per-day aligned to the price series.")
    if not pd.to_datetime(dataset["date"]).reset_index(drop=True).equals(price["date"].reset_index(drop=True)):
        raise ValueError("Reversal-zone dataset dates do not match the price series exactly.")

    down_mask = dataset["row_is_in_confirmed_down_swing"] == 1
    up_mask = dataset["row_is_in_confirmed_up_swing"] == 1
    for column in LOW_ZONE_LABEL_COLUMNS:
        if ((pd.to_numeric(dataset[column], errors="coerce").fillna(0) > 0) & (~down_mask)).any():
            raise ValueError(f"{column} is positive outside confirmed down swings.")
    for column in HIGH_ZONE_LABEL_COLUMNS:
        if ((pd.to_numeric(dataset[column], errors="coerce").fillna(0) > 0) & (~up_mask)).any():
            raise ValueError(f"{column} is positive outside confirmed up swings.")

    for column in ("dist_to_current_down_swing_low_range_frac", "dist_to_current_up_swing_high_range_frac"):
        values = pd.to_numeric(dataset[column], errors="coerce").dropna()
        if not values.empty and ((values < 0.0) | (values > 1.0)).any():
            raise ValueError(f"{column} must stay within [0,1] when defined.")

    for column in ("dist_to_current_down_swing_low_pct", "dist_to_current_up_swing_high_pct"):
        values = pd.to_numeric(dataset[column], errors="coerce").dropna()
        if not values.empty and (values < -1e-12).any():
            raise ValueError(f"{column} must be non-negative when defined.")

    feature_like_columns = set(dataset.columns) - set(LOW_ZONE_LABEL_COLUMNS) - set(HIGH_ZONE_LABEL_COLUMNS) - set(DISTANCE_LABEL_COLUMNS) - set(BOOKKEEPING_COLUMNS)
    if any(column in feature_like_columns for column in LOW_ZONE_LABEL_COLUMNS + HIGH_ZONE_LABEL_COLUMNS + DISTANCE_LABEL_COLUMNS):
        raise ValueError("Label-only columns leaked into the feature-like column set.")


def render_markdown(dataset: pd.DataFrame, taxonomy: pd.DataFrame) -> str:
    down_swings = taxonomy.loc[taxonomy["direction"] == "down"].copy()
    up_swings = taxonomy.loc[taxonomy["direction"] == "up"].copy()

    lines = [
        "# SAFE v4.0 Reversal Zone Dataset",
        "",
        "## Swing Granularity",
        "",
        f"- label: `{SWING_GRANULARITY_LABEL}`",
        f"- ATR window: `{SWING_ATR_WINDOW}`",
        f"- reversal multiplier: `{SWING_REVERSAL_K:.2f}`",
        "",
        "## Dataset Summary",
        "",
        f"- rows: `{len(dataset)}`",
        f"- date range: `{pd.to_datetime(dataset['date']).min().date()}` -> `{pd.to_datetime(dataset['date']).max().date()}`",
        f"- rows in confirmed down swings: `{int(pd.to_numeric(dataset['row_is_in_confirmed_down_swing'], errors='coerce').fillna(0).sum())}`",
        f"- rows in confirmed up swings: `{int(pd.to_numeric(dataset['row_is_in_confirmed_up_swing'], errors='coerce').fillna(0).sum())}`",
        "",
        "## Label Families",
        "",
        "### Range-Based Labels",
        "",
        "- `buy_zone_bottom_10pct_of_range`: current close is inside the lowest 10% of the confirmed down-swing range",
        "- `buy_zone_bottom_5pct_of_range`: current close is inside the lowest 5% of the confirmed down-swing range",
        "- `sell_zone_top_10pct_of_range`: current close is inside the highest 10% of the confirmed up-swing range",
        "- `sell_zone_top_5pct_of_range`: current close is inside the highest 5% of the confirmed up-swing range",
        "",
        "### Price-Distance Labels",
        "",
        "- `buy_zone_within_5pct_above_low`: current close is within 5% above the confirmed down-swing low",
        "- `buy_zone_within_3pct_above_low`: current close is within 3% above the confirmed down-swing low",
        "- `sell_zone_within_5pct_below_high`: current close is within 5% below the confirmed up-swing high",
        "- `sell_zone_within_3pct_below_high`: current close is within 3% below the confirmed up-swing high",
        "",
        "## Label Prevalence",
        "",
    ]

    lines.append("### Range-Based")
    lines.append("")
    for column in ("buy_zone_bottom_10pct_of_range", "buy_zone_bottom_5pct_of_range", "sell_zone_top_10pct_of_range", "sell_zone_top_5pct_of_range"):
        prevalence = float(pd.to_numeric(dataset[column], errors="coerce").fillna(0).mean())
        lines.append(f"- `{column}`: `{prevalence:.2%}`")

    lines.extend(["", "### Price-Distance", ""])
    for column in ("buy_zone_within_5pct_above_low", "buy_zone_within_3pct_above_low", "sell_zone_within_5pct_below_high", "sell_zone_within_3pct_below_high"):
        prevalence = float(pd.to_numeric(dataset[column], errors="coerce").fillna(0).mean())
        lines.append(f"- `{column}`: `{prevalence:.2%}`")

    lines.extend(
        [
            "",
            "## Swing Coverage Sanity",
            "",
            f"- confirmed down swings: `{len(down_swings)}`",
            f"- confirmed up swings: `{len(up_swings)}`",
            f"- median down-swing duration: `{down_swings['duration_days'].median():.1f}` days" if not down_swings.empty else "- median down-swing duration: `n/a`",
            f"- median up-swing duration: `{up_swings['duration_days'].median():.1f}` days" if not up_swings.empty else "- median up-swing duration: `n/a`",
            f"- median down-swing amplitude: `{down_swings['abs_amplitude_pct'].median():.2%}`" if not down_swings.empty else "- median down-swing amplitude: `n/a`",
            f"- median up-swing amplitude: `{up_swings['abs_amplitude_pct'].median():.2%}`" if not up_swings.empty else "- median up-swing amplitude: `n/a`",
            "",
            "## Zone Width Read",
            "",
            "- range-based and price-distance labels are not directly comparable thresholds",
            "- range-based labels depend on the full confirmed swing amplitude",
            "- price-distance labels depend on absolute distance to the eventual low/high",
            "- use prevalence as the first sanity check for whether a zone family is too sparse or too broad",
            "",
            "## Interpretation",
            "",
            "- this dataset now contains two distinct reversal-zone label families",
            "- range-based labels are stricter structural zone labels tied to the confirmed swing range",
            "- price-distance labels are more directly aligned with good-enough proximity to the eventual low/high",
            "- future modeling can test which family better captures many usable swings without requiring exact pivot prediction",
            "- causal features remain intact; confirmed-swing zone labels are future-derived supervision only",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    price, features, onchain = load_inputs(args.price_json, args.features_csv, args.onchain_features_csv)
    dataset, taxonomy = build_dataset(price, features, onchain)
    dataset = add_reversal_zone_labels(dataset)
    validate_dataset(dataset, price)

    export = dataset.set_index("date")
    out_csv = Path(args.out_csv)
    export_feature_csv(export, out_csv, columns=list(export.columns))

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(dataset, taxonomy), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(dataset)}")
    print(f"Range: {pd.to_datetime(dataset['date']).min().date()} -> {pd.to_datetime(dataset['date']).max().date()}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
