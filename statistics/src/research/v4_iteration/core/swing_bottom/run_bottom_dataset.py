from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv, load_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import (
    DEFAULT_BOTTOM_DATASET_CSV_PATH,
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bridge.run_live_swing_state import build_live_swing_state
from src.research.v4_iteration.core.swing_bridge.swing_bridge_common import (
    SWING_ATR_WINDOW,
    SWING_GRANULARITY_LABEL,
    SWING_REVERSAL_K,
    compute_swing_taxonomy,
    map_dates_to_containing_swings,
    map_dates_to_next_swings,
)
from src.research.v4_iteration.core.swing_detection.run_swing_detection import detect_swings


DEFAULT_BOTTOM_DATASET_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_BOTTOM_DATASET.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a daily causal swing-bottom dataset for later bottom-probability modeling.",
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
        default=str(DEFAULT_BOTTOM_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/bottom_dataset.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_BOTTOM_DATASET_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_BOTTOM_DATASET.md",
    )
    return parser.parse_args()


def _validate_date_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"{name} input is empty.")
    if "date" not in frame.columns:
        raise ValueError(f"{name} input must contain a 'date' column.")
    validated = frame.copy()
    validated["date"] = pd.to_datetime(validated["date"], errors="raise")
    if validated["date"].duplicated().any():
        raise ValueError(f"{name} input has duplicate dates.")
    return validated.sort_values("date").reset_index(drop=True)


def load_inputs(price_json: str | Path, features_csv: str | Path, onchain_features_csv: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    price = load_daily_price_json(str(price_json)).reset_index().rename(columns={"timestamp": "date"})
    price = _validate_date_frame("price", price.loc[:, ["date", "open", "high", "low", "close", "volume"]])

    features = _validate_date_frame("features", load_feature_csv(features_csv))
    onchain = _validate_date_frame("onchain_features", load_feature_csv(onchain_features_csv))

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
    onchain_renamed = onchain.drop(columns=[column for column in ("open", "high", "low", "close", "volume") if column in onchain.columns], errors="ignore")
    merged = features.merge(onchain_renamed, on="date", how="inner", validate="one_to_one")
    if not merged["date"].equals(price["date"]):
        raise ValueError("Merged feature surface is not one-row-per-day aligned to the price series.")
    return merged


def build_next_down_labels(dates: pd.Series, closes: pd.Series, taxonomy: pd.DataFrame) -> pd.DataFrame:
    down_tax = taxonomy.loc[taxonomy["direction"] == "down"].sort_values(["swing_low_date", "start_date"]).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for date, close in zip(pd.to_datetime(dates), pd.to_numeric(closes, errors="coerce"), strict=True):
        candidates = down_tax.loc[(down_tax["swing_low_date"] > date) & (down_tax["swing_low_price"] <= close)]
        if candidates.empty:
            rows.append(
                {
                    "date": date,
                    "next_down_swing_id": np.nan,
                    "next_down_swing_low_date": np.nan,
                    "days_to_next_down_swing_low": np.nan,
                    "dist_to_next_down_swing_low_pct": np.nan,
                }
            )
            continue
        swing = candidates.iloc[0]
        dist_pct = float(swing["swing_low_price"] / float(close) - 1.0)
        rows.append(
            {
                "date": date,
                "next_down_swing_id": int(swing["swing_id"]),
                "next_down_swing_low_date": pd.to_datetime(swing["swing_low_date"]),
                "days_to_next_down_swing_low": float((pd.to_datetime(swing["swing_low_date"]) - date).days),
                "dist_to_next_down_swing_low_pct": dist_pct,
            }
        )
    return pd.DataFrame(rows)


def add_down_swing_labels(frame: pd.DataFrame, taxonomy: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["is_in_confirmed_down_swing"] = enriched["containing_swing_direction"].eq("down").astype(int)
    enriched["is_in_confirmed_up_swing"] = enriched["containing_swing_direction"].eq("up").astype(int)

    progress_time = np.full(len(enriched), np.nan, dtype=float)
    progress_range = np.full(len(enriched), np.nan, dtype=float)
    bottom_zone_time_20 = np.zeros(len(enriched), dtype=int)
    bottom_zone_time_10 = np.zeros(len(enriched), dtype=int)
    bottom_zone_range_20 = np.zeros(len(enriched), dtype=int)
    bottom_zone_range_10 = np.zeros(len(enriched), dtype=int)
    near_current_low_2 = np.zeros(len(enriched), dtype=int)
    near_current_low_3 = np.zeros(len(enriched), dtype=int)

    taxonomy_by_id = taxonomy.set_index("swing_id")
    for idx, row in enriched.iterrows():
        if row["is_in_confirmed_down_swing"] != 1 or pd.isna(row["containing_swing_id"]):
            continue
        swing = taxonomy_by_id.loc[int(row["containing_swing_id"])]
        start_date = pd.to_datetime(swing["start_date"])
        end_date = pd.to_datetime(swing["end_date"])
        start_price = float(swing["start_pivot_price"])
        low_price = float(swing["swing_low_price"])
        current_close = float(row["close"])

        duration_days = max(float((end_date - start_date).days), 1.0)
        time_progress = float(np.clip((pd.to_datetime(row["date"]) - start_date).days / duration_days, 0.0, 1.0))

        range_denominator = start_price - low_price
        if range_denominator <= 0:
            range_progress = np.nan
        else:
            raw_range_progress = (start_price - current_close) / range_denominator
            range_progress = float(np.clip(raw_range_progress, 0.0, 1.0))

        progress_time[idx] = time_progress
        progress_range[idx] = range_progress
        bottom_zone_time_20[idx] = int(time_progress >= 0.80)
        bottom_zone_time_10[idx] = int(time_progress >= 0.90)
        if pd.notna(range_progress):
            bottom_zone_range_20[idx] = int(range_progress >= 0.80)
            bottom_zone_range_10[idx] = int(range_progress >= 0.90)

        if low_price > 0:
            above_low_pct = current_close / low_price - 1.0
            near_current_low_2[idx] = int(0.0 <= above_low_pct <= 0.02)
            near_current_low_3[idx] = int(0.0 <= above_low_pct <= 0.03)

    enriched["down_swing_progress_time"] = progress_time
    enriched["down_swing_progress_range"] = progress_range
    enriched["bottom_zone_time_20pct"] = bottom_zone_time_20
    enriched["bottom_zone_time_10pct"] = bottom_zone_time_10
    enriched["bottom_zone_range_20pct"] = bottom_zone_range_20
    enriched["bottom_zone_range_10pct"] = bottom_zone_range_10
    enriched["near_current_swing_low_2pct"] = near_current_low_2
    enriched["near_current_swing_low_3pct"] = near_current_low_3
    return enriched


def build_bottom_dataset(price: pd.DataFrame, features: pd.DataFrame, onchain: pd.DataFrame) -> pd.DataFrame:
    base = build_base_dataset(price, features, onchain)
    live_state = build_live_swing_state(price.set_index("date"))
    live_state = live_state.reset_index().rename(columns={"index": "date", "timestamp": "date"})
    live_state = _validate_date_frame("live_swing_state", live_state)

    taxonomy = build_enriched_taxonomy(price)
    containing = map_dates_to_containing_swings(base["date"], taxonomy)
    next_swings = map_dates_to_next_swings(base["date"], taxonomy)
    next_down = build_next_down_labels(base["date"], base["close"], taxonomy)

    dataset = (
        base.merge(live_state, on="date", how="left", validate="one_to_one")
        .merge(containing, on="date", how="left", validate="one_to_one")
        .merge(next_swings, on="date", how="left", validate="one_to_one")
        .merge(next_down, on="date", how="left", validate="one_to_one")
        .sort_values("date")
        .reset_index(drop=True)
    )
    dataset = add_down_swing_labels(dataset, taxonomy)
    return dataset


def validate_bottom_dataset(dataset: pd.DataFrame, price: pd.DataFrame) -> None:
    if dataset.empty:
        raise ValueError("Bottom dataset is empty.")
    if dataset["date"].duplicated().any():
        raise ValueError("Bottom dataset contains duplicate dates.")
    if len(dataset) != len(price):
        raise ValueError("Bottom dataset is not one-row-per-day aligned to the price series.")
    if not pd.to_datetime(dataset["date"]).reset_index(drop=True).equals(price["date"].reset_index(drop=True)):
        raise ValueError("Bottom dataset dates do not match the price series exactly.")

    down_mask = dataset["is_in_confirmed_down_swing"] == 1
    for column in (
        "bottom_zone_time_20pct",
        "bottom_zone_time_10pct",
        "bottom_zone_range_20pct",
        "bottom_zone_range_10pct",
        "near_current_swing_low_2pct",
        "near_current_swing_low_3pct",
    ):
        invalid_positive = (pd.to_numeric(dataset[column], errors="coerce").fillna(0) > 0) & (~down_mask)
        if invalid_positive.any():
            raise ValueError(f"{column} is positive outside confirmed down swings.")

    for column in ("down_swing_progress_time", "down_swing_progress_range"):
        values = pd.to_numeric(dataset[column], errors="coerce").dropna()
        if not values.empty and ((values < 0.0) | (values > 1.0)).any():
            raise ValueError(f"{column} must remain within [0,1] when defined.")

    dist = pd.to_numeric(dataset["dist_to_next_down_swing_low_pct"], errors="coerce").dropna()
    if not dist.empty and (dist > 1e-12).any():
        raise ValueError("dist_to_next_down_swing_low_pct must be <= 0 when defined.")


def render_markdown(dataset: pd.DataFrame) -> str:
    labels = [
        "bottom_zone_time_20pct",
        "bottom_zone_time_10pct",
        "bottom_zone_range_20pct",
        "bottom_zone_range_10pct",
        "near_current_swing_low_2pct",
        "near_current_swing_low_3pct",
    ]
    down_rows = int(pd.to_numeric(dataset["is_in_confirmed_down_swing"], errors="coerce").fillna(0).sum())
    days_to_low = pd.to_numeric(dataset["days_to_next_down_swing_low"], errors="coerce").dropna()
    dist_to_low = pd.to_numeric(dataset["dist_to_next_down_swing_low_pct"], errors="coerce").dropna()

    def quantile_line(series: pd.Series, label: str, as_pct: bool = False) -> list[str]:
        if series.empty:
            return [f"- {label}: `n/a`"]
        if as_pct:
            return [
                f"- {label} median: `{series.median():.2%}`",
                f"- {label} q25 / q75: `{series.quantile(0.25):.2%}` / `{series.quantile(0.75):.2%}`",
            ]
        return [
            f"- {label} median: `{series.median():.1f}`",
            f"- {label} q25 / q75: `{series.quantile(0.25):.1f}` / `{series.quantile(0.75):.1f}`",
        ]

    lines = [
        "# SAFE v4.0 Bottom Dataset",
        "",
        "## Swing Granularity",
        "",
        f"- label: `{SWING_GRANULARITY_LABEL}`",
        f"- ATR window: `{SWING_ATR_WINDOW}`",
        f"- reversal multiplier: `{SWING_REVERSAL_K:.2f}`",
        "",
        "## Dataset Summary",
        "",
        f"- daily rows: `{len(dataset)}`",
        f"- date range: `{pd.to_datetime(dataset['date']).min().date()}` -> `{pd.to_datetime(dataset['date']).max().date()}`",
        f"- rows inside confirmed down swings: `{down_rows}`",
        "",
        "## Bottom Label Prevalence",
        "",
    ]
    for column in labels:
        prevalence = float(pd.to_numeric(dataset[column], errors="coerce").fillna(0).mean())
        lines.append(f"- `{column}`: `{prevalence:.2%}`")

    lines.extend(
        [
            "",
            "## Future Bottom Geometry",
            "",
        ]
    )
    lines.extend(quantile_line(days_to_low, "days_to_next_down_swing_low", as_pct=False))
    lines.extend(quantile_line(dist_to_low, "dist_to_next_down_swing_low_pct", as_pct=True))

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- feature columns remain causal daily state descriptors",
            "- swing-bottom labels are future-derived targets for later supervised modeling",
            "- rows outside confirmed down swings keep the binary bottom-zone labels at `0`, while down-swing progress fields stay `NaN`",
            "- `next_down_swing_*` labels are only defined when a future confirmed down-swing low is at or below the current close",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    price, features, onchain = load_inputs(args.price_json, args.features_csv, args.onchain_features_csv)
    dataset = build_bottom_dataset(price, features, onchain)
    validate_bottom_dataset(dataset, price)

    export = dataset.set_index("date")
    out_csv = Path(args.out_csv)
    export_feature_csv(export, out_csv, columns=list(export.columns))

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(dataset), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(dataset)}")
    print(f"Range: {pd.to_datetime(dataset['date']).min().date()} -> {pd.to_datetime(dataset['date']).max().date()}")
    print(f"Down-swing rows: {int(pd.to_numeric(dataset['is_in_confirmed_down_swing'], errors='coerce').fillna(0).sum())}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
