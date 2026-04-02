from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.data.feature_store import export_feature_csv
from src.features.price_features import EXPORTED_FEATURES, FeatureConfig, compute_price_features
from src.models.hazard_calibrated import FEATURE_COLS, HazardConfig, apply_hazard_models, train_hazard_models
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_HAZARD_PACK_PATH, DEFAULT_PRICE_JSON_PATH


HAZARD_OUTPUT_COLUMNS: tuple[str, ...] = (
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
)
SUMMARY_COLUMNS: tuple[str, ...] = (
    "close",
    "TS_50",
    "atr_pct",
    "relative_volume_20",
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the BTC hazard training pipeline."""
    parser = argparse.ArgumentParser(
        description="Compute descriptive BTC features, train calibrated hazard models, and export ../out/features.csv by default.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--hazard-pack", default=str(DEFAULT_HAZARD_PACK_PATH), help="Default: ../out/models/hazard_pack.joblib")
    parser.add_argument("--out-csv", "--out-json", dest="out_csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--corr-quantile", type=float, default=0.70)
    parser.add_argument("--rebound-quantile", type=float, default=0.70)
    parser.add_argument("--hazard-min-train-rows", type=int, default=800)
    parser.add_argument("--hazard-min-calibration-rows", type=int, default=200)
    parser.add_argument("--hazard-min-test-rows", type=int, default=200)
    parser.add_argument("--hazard-test-fraction", type=float, default=0.20)
    parser.add_argument("--hazard-calibration-fraction", type=float, default=0.20)
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


def build_hazard_config(args: argparse.Namespace) -> HazardConfig:
    """Build the hazard-model configuration from parsed CLI arguments."""
    return HazardConfig(
        horizon_days=args.horizon,
        corr_quantile=args.corr_quantile,
        rebound_quantile=args.rebound_quantile,
        min_train_rows=args.hazard_min_train_rows,
        min_calibration_rows=args.hazard_min_calibration_rows,
        min_test_rows=args.hazard_min_test_rows,
        test_fraction=args.hazard_test_fraction,
        calibration_fraction=args.hazard_calibration_fraction,
    )


def _validate_base_features(base_features: pd.DataFrame) -> None:
    if base_features.empty:
        raise ValueError("Base descriptive feature table is empty.")
    if not isinstance(base_features.index, pd.DatetimeIndex):
        raise ValueError("Base descriptive features must use a DatetimeIndex.")
    if not base_features.index.is_monotonic_increasing:
        raise ValueError("Base descriptive feature index must be monotonic increasing.")
    if base_features.index.has_duplicates:
        raise ValueError("Base descriptive features contain duplicate timestamps.")

    missing_columns = sorted({"close", "r1"}.difference(base_features.columns))
    if missing_columns:
        raise ValueError(f"Base descriptive features are missing required columns: {missing_columns}")

    if list(base_features.columns) != list(EXPORTED_FEATURES):
        raise ValueError("Base descriptive features do not match EXPORTED_FEATURES.")


def _validate_hazard_inputs(base_features: pd.DataFrame, feature_cols: tuple[str, ...]) -> None:
    missing_columns = [column for column in feature_cols if column not in base_features.columns]
    if missing_columns:
        raise ValueError(f"Base descriptive features are missing required hazard inputs: {missing_columns}.")


def _validate_hazard_outputs(hazard_features: pd.DataFrame) -> None:
    missing_columns = [column for column in HAZARD_OUTPUT_COLUMNS if column not in hazard_features.columns]
    if missing_columns:
        raise ValueError(f"Hazard output is missing required calibrated columns: {missing_columns}")


def load_base_features(args: argparse.Namespace) -> pd.DataFrame:
    """Load BTC OHLCV input and compute the descriptive base feature table."""
    raw_df = load_daily_price_json(args.price_json)
    base_features = compute_price_features(raw_df, cfg=build_feature_config(args))
    _validate_base_features(base_features)
    _validate_hazard_inputs(base_features, FEATURE_COLS)
    return base_features


def train_hazard_stage(base_features: pd.DataFrame, cfg: HazardConfig) -> dict[str, Any]:
    """Train the calibrated hazard pack from descriptive BTC features."""
    feature_cols = tuple(cfg.feature_cols) if cfg.feature_cols is not None else FEATURE_COLS
    _validate_hazard_inputs(base_features, feature_cols)
    hazard_pack = train_hazard_models(base_features, cfg)
    if tuple(hazard_pack.get("feature_cols", [])) != FEATURE_COLS:
        raise ValueError(
            "Trained hazard pack does not match the expected hazard feature contract. "
            f"Expected {list(FEATURE_COLS)}, got {list(hazard_pack.get('feature_cols', []))}."
        )
    return hazard_pack


def apply_hazard_stage(base_features: pd.DataFrame, hazard_pack: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply calibrated hazard probabilities to the full descriptive BTC feature table."""
    _validate_hazard_inputs(base_features, tuple(hazard_pack["feature_cols"]))
    hazard_features = apply_hazard_models(base_features, hazard_pack)
    if not hazard_features.index.equals(base_features.index):
        raise ValueError("Hazard stage changed index alignment unexpectedly.")
    _validate_hazard_outputs(hazard_features)

    hazard_meta = {
        "feature_cols": list(hazard_pack["feature_cols"]),
        "meta": hazard_pack.get("meta", {}),
        "diagnostics": hazard_pack.get("diagnostics", {}),
        "test_corr_rate": hazard_pack.get("test_corr_rate"),
        "test_corr_pred_mean": hazard_pack.get("test_corr_pred_mean"),
        "test_reb_rate": hazard_pack.get("test_reb_rate"),
        "test_reb_pred_mean": hazard_pack.get("test_reb_pred_mean"),
    }
    return hazard_features, hazard_meta


def export_payload(hazard_features: pd.DataFrame, hazard_meta: dict[str, Any], out_path: Path) -> None:
    """Export descriptive and calibrated hazard columns into the BTC CSV feature store."""
    export_frame = export_feature_csv(hazard_features, out_path, columns=list(hazard_features.columns), dropna_on="close")
    if export_frame.columns[0] != "date":
        raise ValueError("Feature export must use 'date' as the first CSV column.")

    for column in HAZARD_OUTPUT_COLUMNS:
        if column not in export_frame.columns:
            raise ValueError("Export CSV is missing calibrated hazard columns.")


def print_summary(hazard_features: pd.DataFrame, hazard_meta: dict[str, Any]) -> None:
    """Print a compact summary of the latest calibrated hazard outputs."""
    last_timestamp = hazard_features.index[-1]
    last_row = hazard_features.iloc[-1]

    print(f"Rows: {len(hazard_features)}")
    print(f"Range: {hazard_features.index.min().strftime('%Y-%m-%d')} -> {hazard_features.index.max().strftime('%Y-%m-%d')}")
    print(f"Last timestamp: {last_timestamp.strftime('%Y-%m-%d')}")
    print("Last hazard snapshot:")
    for column in SUMMARY_COLUMNS:
        value = last_row.get(column, pd.NA)
        rendered = "na" if pd.isna(value) else f"{float(value):.6f}"
        print(f"  {column}: {rendered}")

    diagnostics = hazard_meta.get("diagnostics", {})
    correction = diagnostics.get("correction", {})
    rebound = diagnostics.get("rebound", {})
    print(
        "Hazard diagnostics:",
        f"horizon={hazard_meta.get('meta', {}).get('horizon_days')}",
        f"corr_brier={correction.get('brier_test')}",
        f"reb_brier={rebound.get('brier_test')}",
        f"corr_logloss={correction.get('log_loss_test')}",
        f"reb_logloss={rebound.get('log_loss_test')}",
    )


def main() -> None:
    """Run the descriptive BTC feature and hazard training pipeline end to end."""
    try:
        args = parse_args()
        base_features = load_base_features(args)
        hazard_cfg = build_hazard_config(args)
        hazard_pack = train_hazard_stage(base_features, hazard_cfg)

        hazard_pack_path = Path(args.hazard_pack)
        hazard_pack_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(hazard_pack, hazard_pack_path)

        hazard_features, hazard_meta = apply_hazard_stage(base_features, hazard_pack)
        out_path = Path(args.out_csv)
        export_payload(hazard_features, hazard_meta, out_path)

        print(f"Saved model: {hazard_pack_path}")
        print(f"Wrote: {out_path}")
        print_summary(hazard_features, hazard_meta)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Hazard training pipeline failed: {exc}") from exc


if __name__ == "__main__":
    main()
