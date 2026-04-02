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
from src.models.hazard_calibrated import FEATURE_COLS as HAZARD_FEATURE_COLS, apply_hazard_models
from src.models.regime_hmm import HMM_FEATURE_COLS, apply_hmm_pack, load_hmm_pack
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_HAZARD_PACK_PATH, DEFAULT_HMM_PACK_PATH, DEFAULT_PRICE_JSON_PATH
from src.strategy.exposure import ExposureConfig, compute_exposure_series


SEMANTIC_HMM_COLUMNS: tuple[str, ...] = (
    "P_CORE_HMM",
    "P_DRIFT_HMM",
    "P_SHOCK_HMM",
    "P_SURGE_HMM",
)
HAZARD_OUTPUT_COLUMNS: tuple[str, ...] = (
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
)
SUMMARY_COLUMNS: tuple[str, ...] = (
    "close",
    "HMM_LABEL",
    "P_SHOCK_HMM",
    "P_CORRECTION_10D_CAL",
    "E_target_safe",
    "hard_risk_off_flag_safe",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the BTC exposure pipeline."""
    parser = argparse.ArgumentParser(
        description="Compute descriptive BTC features, apply HMM and hazard packs, compute exposure, and export ../out/features.csv by default.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--out-csv", "--out-json", dest="out_csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--hmm-pack", default=str(DEFAULT_HMM_PACK_PATH), help="Default: ../out/models/hmm_pack.joblib")
    parser.add_argument("--hazard-pack", default=str(DEFAULT_HAZARD_PACK_PATH), help="Default: ../out/models/hazard_pack.joblib")
    parser.add_argument("--hmm-mode", choices=["filter", "smooth"], default="filter")
    parser.add_argument("--exposure-mode", choices=["safe", "aggr"], default="safe")

    parser.add_argument("--safe-base", type=float, default=0.15)
    parser.add_argument("--alpha-hazard", type=float, default=2.0)
    parser.add_argument("--dom-floor", type=float, default=0.35)
    parser.add_argument("--dom-span", type=float, default=0.35)
    parser.add_argument("--enable-hard-risk-off", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--shock-prob-threshold", type=float, default=0.70)
    parser.add_argument("--correction-prob-threshold", type=float, default=0.65)
    parser.add_argument("--positive-regime-max", type=float, default=0.30)
    parser.add_argument("--hmm-conf-risk-off-threshold", type=float, default=0.60)
    parser.add_argument("--ts50-risk-off-threshold", type=float, default=0.0)
    parser.add_argument("--band-pos-risk-off-threshold", type=float, default=0.35)
    parser.add_argument("--risk-off-max-daily-change", type=float, default=0.50)
    parser.add_argument("--d0", type=float, default=0.10)
    parser.add_argument("--d1", type=float, default=0.20)
    parser.add_argument("--l-cap", type=float, default=2.0)
    parser.add_argument("--l-gain", type=float, default=1.0)
    parser.add_argument("--max-daily-change", type=float, default=0.10)

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
    """Build the descriptive feature configuration from CLI arguments."""
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


def build_exposure_config(args: argparse.Namespace) -> ExposureConfig:
    """Build the exposure configuration from CLI arguments."""
    return ExposureConfig(
        E_base_safe=args.safe_base,
        alpha_hazard=args.alpha_hazard,
        dom_floor=args.dom_floor,
        dom_span=args.dom_span,
        enable_hard_risk_off=args.enable_hard_risk_off,
        shock_prob_threshold=args.shock_prob_threshold,
        correction_prob_threshold=args.correction_prob_threshold,
        positive_regime_max=args.positive_regime_max,
        hmm_conf_risk_off_threshold=args.hmm_conf_risk_off_threshold,
        ts50_risk_off_threshold=args.ts50_risk_off_threshold,
        band_pos_risk_off_threshold=args.band_pos_risk_off_threshold,
        risk_off_max_daily_change=args.risk_off_max_daily_change,
        d0=args.d0,
        d1=args.d1,
        L_cap=args.l_cap,
        L_gain=args.l_gain,
        max_daily_change=args.max_daily_change,
    )


def _expected_hmm_state_columns(n_states: int) -> list[str]:
    return [f"HMM_STATE_{state}" for state in range(n_states)]


def _expected_exposure_columns(mode: str) -> tuple[str, ...]:
    return (
        f"direction_{mode}",
        f"E_target_{mode}",
        f"L_target_{mode}",
        f"entry_step_{mode}",
        f"conviction_{mode}",
        f"D_score_{mode}",
        f"hard_risk_off_flag_{mode}",
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


def _validate_hmm_inputs(features: pd.DataFrame) -> None:
    missing_columns = [column for column in HMM_FEATURE_COLS if column not in features.columns]
    if missing_columns:
        raise ValueError(f"Missing required HMM inputs: {missing_columns}")


def _validate_hmm_outputs(features: pd.DataFrame, n_states: int) -> None:
    expected_columns = [
        *_expected_hmm_state_columns(n_states),
        "HMM_DOM",
        "HMM_CONF",
        "HMM_LABEL",
        *SEMANTIC_HMM_COLUMNS,
    ]
    missing_columns = [column for column in expected_columns if column not in features.columns]
    if missing_columns:
        raise ValueError(f"HMM output is missing required columns: {missing_columns}")


def _validate_hazard_inputs(features: pd.DataFrame) -> None:
    missing_columns = [column for column in HAZARD_FEATURE_COLS if column not in features.columns]
    if missing_columns:
        raise ValueError(f"Missing required hazard inputs: {missing_columns}")


def _validate_hazard_outputs(features: pd.DataFrame) -> None:
    missing_columns = [column for column in HAZARD_OUTPUT_COLUMNS if column not in features.columns]
    if missing_columns:
        raise ValueError(f"Hazard output is missing required columns: {missing_columns}")


def _validate_exposure_outputs(features: pd.DataFrame, mode: str) -> None:
    missing_columns = [column for column in _expected_exposure_columns(mode) if column not in features.columns]
    if missing_columns:
        raise ValueError(f"Exposure output is missing required columns: {missing_columns}")


def load_base_features(args: argparse.Namespace) -> pd.DataFrame:
    """Load BTC OHLCV input and compute the descriptive base feature table."""
    raw_df = load_daily_price_json(args.price_json)
    base_features = compute_price_features(raw_df, cfg=build_feature_config(args))
    _validate_base_features(base_features)
    return base_features


def apply_hmm_stage(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load and apply the fitted HMM pack using the requested inference mode."""
    _validate_hmm_inputs(features)
    hmm_pack_path = Path(args.hmm_pack)
    if not hmm_pack_path.exists():
        raise FileNotFoundError(f"HMM pack not found: {hmm_pack_path}")

    hmm_pack = load_hmm_pack(str(hmm_pack_path))
    if list(hmm_pack.get("feature_cols", [])) != list(HMM_FEATURE_COLS):
        raise ValueError(
            "Loaded HMM pack does not match the canonical HMM feature contract. "
            f"Expected {list(HMM_FEATURE_COLS)}, got {list(hmm_pack.get('feature_cols', []))}."
        )

    hmm_features, hmm_meta = apply_hmm_pack(features, hmm_pack, mode=args.hmm_mode)
    if not hmm_features.index.equals(features.index):
        raise ValueError("HMM stage changed index alignment unexpectedly.")
    _validate_hmm_outputs(hmm_features, int(hmm_pack["cfg"]["n_states"]))
    return hmm_features, hmm_meta


def apply_hazard_stage(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load and apply the calibrated hazard pack to the full BTC feature frame."""
    _validate_hazard_inputs(features)
    hazard_pack_path = Path(args.hazard_pack)
    if not hazard_pack_path.exists():
        raise FileNotFoundError(f"Hazard pack not found: {hazard_pack_path}")

    hazard_pack = joblib.load(hazard_pack_path)
    if list(hazard_pack.get("feature_cols", [])) != list(HAZARD_FEATURE_COLS):
        raise ValueError(
            "Loaded hazard pack does not match the canonical hazard feature contract. "
            f"Expected {list(HAZARD_FEATURE_COLS)}, got {list(hazard_pack.get('feature_cols', []))}."
        )

    hazard_features = apply_hazard_models(features, hazard_pack)
    if not hazard_features.index.equals(features.index):
        raise ValueError("Hazard stage changed index alignment unexpectedly.")
    _validate_hazard_outputs(hazard_features)

    hazard_meta = {
        "feature_cols": list(hazard_pack.get("feature_cols", [])),
        "meta": hazard_pack.get("meta", {}),
        "diagnostics": hazard_pack.get("diagnostics", {}),
        "test_corr_rate": hazard_pack.get("test_corr_rate"),
        "test_corr_pred_mean": hazard_pack.get("test_corr_pred_mean"),
        "test_reb_rate": hazard_pack.get("test_reb_rate"),
        "test_reb_pred_mean": hazard_pack.get("test_reb_pred_mean"),
    }
    return hazard_features, hazard_meta


def apply_exposure_stage(features: pd.DataFrame, exposure_cfg: ExposureConfig, mode: str) -> pd.DataFrame:
    """Compute exposure targets from descriptive, HMM, and hazard features."""
    exposure_features = compute_exposure_series(features, mode=mode, cfg=exposure_cfg, use_hmm=True)
    if not exposure_features.index.equals(features.index):
        raise ValueError("Exposure stage changed index alignment unexpectedly.")
    _validate_exposure_outputs(exposure_features, mode)
    return exposure_features


def export_payload(
    features: pd.DataFrame,
    hmm_meta: dict[str, Any],
    hazard_meta: dict[str, Any],
    exposure_cfg: ExposureConfig,
    out_path: Path,
    exposure_mode: str,
) -> None:
    """Export descriptive, HMM, hazard, and exposure columns into the BTC CSV feature store."""
    export_frame = export_feature_csv(features, out_path, columns=list(features.columns), dropna_on="close")
    if export_frame.columns[0] != "date":
        raise ValueError("Feature export must use 'date' as the first CSV column.")

    required_columns = [
        *_expected_hmm_state_columns(int(hmm_meta["cfg"]["n_states"])),
        "HMM_DOM",
        "HMM_CONF",
        "HMM_LABEL",
        *SEMANTIC_HMM_COLUMNS,
        *HAZARD_OUTPUT_COLUMNS,
        *(_expected_exposure_columns(exposure_mode)),
    ]
    missing_columns = [column for column in required_columns if column not in export_frame.columns]
    if missing_columns:
        raise ValueError(f"Export CSV is missing expected enriched columns: {missing_columns}")


def print_summary(features: pd.DataFrame, hmm_meta: dict[str, Any], hazard_meta: dict[str, Any], exposure_mode: str) -> None:
    """Print a compact summary of the latest BTC exposure snapshot."""
    last_timestamp = features.index[-1]
    last_row = features.iloc[-1]

    print(f"Rows: {len(features)}")
    print(f"Range: {features.index.min().strftime('%Y-%m-%d')} -> {features.index.max().strftime('%Y-%m-%d')}")
    print(f"Last timestamp: {last_timestamp.strftime('%Y-%m-%d')}")
    print("Last exposure snapshot:")
    for column in SUMMARY_COLUMNS:
        value = last_row.get(column, pd.NA)
        if pd.isna(value):
            rendered = "na"
        elif isinstance(value, str):
            rendered = value
        else:
            rendered = f"{float(value):.6f}"
        print(f"  {column}: {rendered}")

    print(
        "Diagnostics:",
        f"hmm_mode={hmm_meta['mode']}",
        f"hmm_usable_rows={hmm_meta.get('diagnostics', {}).get('usable_rows')}",
        f"hazard_horizon={hazard_meta.get('meta', {}).get('horizon_days')}",
        f"exposure_mode={exposure_mode}",
        f"corr_brier={hazard_meta.get('diagnostics', {}).get('correction', {}).get('brier_test')}",
        f"reb_brier={hazard_meta.get('diagnostics', {}).get('rebound', {}).get('brier_test')}",
    )


def main() -> None:
    """Run the descriptive BTC, HMM, hazard, and exposure pipeline end to end."""
    try:
        args = parse_args()
        base_features = load_base_features(args)
        hmm_features, hmm_meta = apply_hmm_stage(base_features, args)
        hazard_features, hazard_meta = apply_hazard_stage(hmm_features, args)
        exposure_cfg = build_exposure_config(args)
        exposure_features = apply_exposure_stage(hazard_features, exposure_cfg, args.exposure_mode)
        out_path = Path(args.out_csv)
        export_payload(exposure_features, hmm_meta, hazard_meta, exposure_cfg, out_path, args.exposure_mode)
        print(f"Wrote: {out_path}")
        print_summary(exposure_features, hmm_meta, hazard_meta, args.exposure_mode)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Exposure pipeline failed: {exc}") from exc


if __name__ == "__main__":
    main()
