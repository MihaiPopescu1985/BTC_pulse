from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.data.feature_store import export_feature_csv
from src.features.price_features import EXPORTED_FEATURES, FeatureConfig, compute_price_features
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_PRICE_JSON_PATH


SUMMARY_FEATURES: tuple[str, ...] = (
    "close",
    "r1",
    "TS_50",
    "atr_pct",
    "band_pos",
    "relative_volume_20",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the BTC descriptive feature pipeline."""
    parser = argparse.ArgumentParser(
        description="Compute descriptive BTC OHLCV features and export them to ../out/features.csv by default.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--out-csv", "--out-json", dest="out_csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--ret-fast", type=int, default=3)
    parser.add_argument("--ret-mid", type=int, default=7)
    parser.add_argument("--ret-slow", type=int, default=14)
    parser.add_argument("--trend-win-short", type=int, default=20)
    parser.add_argument("--trend-win-mid", type=int, default=50)
    parser.add_argument("--trend-win-long", type=int, default=200)
    parser.add_argument("--volatility-win", type=int, default=20)
    parser.add_argument("--atr-win", type=int, default=14)
    parser.add_argument("--band-win", type=int, default=100)
    parser.add_argument("--switch-win", type=int, default=50)
    parser.add_argument("--volume-win", type=int, default=20)
    parser.add_argument("--equilibrium-win", type=int, default=50)
    parser.add_argument("--local-extrema-win", type=int, default=50)
    parser.add_argument("--adapt-win", type=int, default=365 * 2)
    parser.add_argument("--ewma-span", type=int, default=20)
    parser.add_argument("--eps", type=float, default=1e-8)
    return parser.parse_args()


def build_feature_config(args: argparse.Namespace) -> FeatureConfig:
    """Build the descriptive feature configuration from parsed CLI arguments."""
    return FeatureConfig(
        ret_fast=args.ret_fast,
        ret_mid=args.ret_mid,
        ret_slow=args.ret_slow,
        trend_win_short=args.trend_win_short,
        trend_win_mid=args.trend_win_mid,
        trend_win_long=args.trend_win_long,
        volatility_win=args.volatility_win,
        atr_win=args.atr_win,
        band_win=args.band_win,
        switch_win=args.switch_win,
        volume_win=args.volume_win,
        equilibrium_win=args.equilibrium_win,
        local_extrema_win=args.local_extrema_win,
        adapt_win=args.adapt_win,
        ewma_span=args.ewma_span,
        eps=args.eps,
    )


def _validate_features(features: pd.DataFrame) -> None:
    if features.empty:
        raise ValueError("Feature computation returned an empty DataFrame.")
    if not isinstance(features.index, pd.DatetimeIndex):
        raise ValueError("Feature output must use a DatetimeIndex.")
    if not features.index.is_monotonic_increasing:
        raise ValueError("Feature output index must be sorted in increasing timestamp order.")
    if features.index.has_duplicates:
        raise ValueError("Feature output contains duplicate timestamps.")

    missing_columns = sorted({"close", "r1"}.difference(features.columns))
    if missing_columns:
        raise ValueError(f"Feature output is missing essential columns: {missing_columns}")

    actual_columns = list(features.columns)
    expected_columns = list(EXPORTED_FEATURES)
    if actual_columns != expected_columns:
        raise ValueError(
            "Feature output columns do not match EXPORTED_FEATURES. "
            f"Expected {len(expected_columns)} columns, got {len(actual_columns)}."
        )


def run_feature_pipeline(args: argparse.Namespace) -> pd.DataFrame:
    """Load BTC OHLCV input and compute the descriptive feature table."""
    raw_df = load_daily_price_json(args.price_json)
    features = compute_price_features(raw_df, cfg=build_feature_config(args))
    _validate_features(features)
    return features


def export_features(features: pd.DataFrame, out_path: Path) -> None:
    """Export descriptive features to the canonical BTC CSV feature store."""
    export_frame = export_feature_csv(features, out_path, columns=list(EXPORTED_FEATURES), dropna_on="close")
    actual_columns = list(export_frame.columns)
    expected_columns = ["date", *list(EXPORTED_FEATURES)]
    if actual_columns != expected_columns:
        raise ValueError(
            "Export CSV columns do not match the expected feature store contract. "
            f"Expected {expected_columns[:5]}..., got {actual_columns[:5]}..."
        )


def print_feature_summary(features: pd.DataFrame) -> None:
    """Print a compact summary of the latest descriptive BTC feature values."""
    last_timestamp = features.index[-1]
    last_row = features.iloc[-1]

    print(f"Rows: {len(features)}")
    print(f"Range: {features.index.min().strftime('%Y-%m-%d')} -> {features.index.max().strftime('%Y-%m-%d')}")
    print(f"Last timestamp: {last_timestamp.strftime('%Y-%m-%d')}")
    print("Last descriptive snapshot:")
    for feature in SUMMARY_FEATURES:
        value = last_row.get(feature, pd.NA)
        rendered = "na" if pd.isna(value) else f"{float(value):.6f}"
        print(f"  {feature}: {rendered}")


def main() -> None:
    """Run the descriptive BTC feature pipeline end to end."""
    try:
        args = parse_args()
        features = run_feature_pipeline(args)
        out_path = Path(args.out_csv)
        export_features(features, out_path)
        print(f"Wrote: {out_path}")
        print_feature_summary(features)
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Feature pipeline failed: {exc}") from exc


if __name__ == "__main__":
    main()
