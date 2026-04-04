from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.data.feature_store import export_feature_csv
from src.features.price_features import EXPORTED_FEATURES, FeatureConfig, compute_price_features
from src.models.regime_hmm import (
    HMM_FEATURE_COLS,
    HMMConfig,
    apply_hmm_pack,
    fit_hmm_pack,
    load_hmm_pack,
    save_hmm_pack,
)
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_HAZARD_PACK_PATH, DEFAULT_HMM_PACK_PATH, DEFAULT_PRICE_JSON_PATH


HMM_SEMANTIC_COLUMNS: tuple[str, ...] = (
    "P_CORE_HMM",
    "P_DRIFT_HMM",
    "P_SHOCK_HMM",
    "P_SURGE_HMM",
)
SUMMARY_COLUMNS: tuple[str, ...] = (
    "close",
    "TS_50",
    "atr_pct",
    "HMM_CONF",
    "HMM_LABEL",
    "P_CORE_HMM",
    "P_DRIFT_HMM",
    "P_SHOCK_HMM",
    "P_SURGE_HMM",
)
HAZARD_OUTPUT_COLUMNS: tuple[str, ...] = (
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the BTC HMM regime pipeline."""
    parser = argparse.ArgumentParser(
        description="Compute descriptive BTC features, fit or load the HMM pack, optionally apply hazard outputs, and export ../out/features.csv by default.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--out-csv", "--out-json", dest="out_csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--hmm-pack", default=str(DEFAULT_HMM_PACK_PATH), help="Default: ../out/models/hmm_pack.joblib")
    parser.add_argument("--hazard-pack", default=str(DEFAULT_HAZARD_PACK_PATH), help="Default: ../out/models/hazard_pack.joblib")
    parser.add_argument("--retrain-hmm", action="store_true")
    parser.add_argument("--hmm-mode", choices=["filter", "smooth"], default="filter")
    parser.add_argument("--hmm-states", type=int, default=4)
    parser.add_argument("--hmm-iter", type=int, default=80)
    parser.add_argument("--hmm-seed", type=int, default=42)
    parser.add_argument("--hmm-tol", type=float, default=1e-4)
    parser.add_argument("--hmm-reg-covar", type=float, default=1e-4)
    parser.add_argument("--hmm-min-rows", type=int, default=250)
    parser.add_argument("--hmm-init-kmeans-iter", type=int, default=12)
    parser.add_argument("--hmm-sticky-self-transition", type=float, default=0.85)
    parser.add_argument("--apply-hazard", action="store_true")
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


def build_hmm_config(args: argparse.Namespace) -> HMMConfig:
    """Build the HMM configuration from parsed CLI arguments."""
    return HMMConfig(
        n_states=args.hmm_states,
        n_iter=args.hmm_iter,
        tol=args.hmm_tol,
        seed=args.hmm_seed,
        reg_covar=args.hmm_reg_covar,
        min_rows=args.hmm_min_rows,
        init_kmeans_iter=args.hmm_init_kmeans_iter,
        sticky_self_transition=args.hmm_sticky_self_transition,
    )


def _validate_base_features(features: pd.DataFrame) -> None:
    if features.empty:
        raise ValueError("Base descriptive feature table is empty.")
    if not isinstance(features.index, pd.DatetimeIndex):
        raise ValueError("Base descriptive features must use a DatetimeIndex.")
    if not features.index.is_monotonic_increasing:
        raise ValueError("Base descriptive feature index must be monotonic increasing.")
    if features.index.has_duplicates:
        raise ValueError("Base descriptive features contain duplicate timestamps.")

    missing_columns = sorted({"close", "r1"}.difference(features.columns))
    if missing_columns:
        raise ValueError(f"Base descriptive features are missing required columns: {missing_columns}")

    if list(features.columns) != list(EXPORTED_FEATURES):
        raise ValueError("Base descriptive features do not match EXPORTED_FEATURES.")


def _validate_hmm_inputs(features: pd.DataFrame) -> None:
    missing_columns = [column for column in HMM_FEATURE_COLS if column not in features.columns]
    if missing_columns:
        raise ValueError(f"Base descriptive features are missing required HMM inputs: {missing_columns}.")


def _expected_hmm_state_columns(n_states: int) -> list[str]:
    return [f"HMM_STATE_{state}" for state in range(n_states)]


def _validate_hmm_outputs(features: pd.DataFrame, hmm_pack: dict[str, Any]) -> None:
    expected_columns = [
        *_expected_hmm_state_columns(int(hmm_pack["cfg"]["n_states"])),
        "HMM_DOM",
        "HMM_CONF",
        "HMM_LABEL",
        *HMM_SEMANTIC_COLUMNS,
    ]
    missing_columns = [column for column in expected_columns if column not in features.columns]
    if missing_columns:
        raise ValueError(f"HMM output is missing required columns: {missing_columns}")


def _validate_hazard_outputs(features: pd.DataFrame) -> None:
    missing_columns = [column for column in HAZARD_OUTPUT_COLUMNS if column not in features.columns]
    if missing_columns:
        raise ValueError(f"Hazard output is missing required columns: {missing_columns}")


def load_base_features(args: argparse.Namespace) -> pd.DataFrame:
    """Load BTC OHLCV input and compute the descriptive base feature table."""
    raw_df = load_daily_price_json(args.price_json)
    features = compute_price_features(raw_df, cfg=build_feature_config(args))
    _validate_base_features(features)
    _validate_hmm_inputs(features)
    return features


def fit_or_load_hmm(features: pd.DataFrame, args: argparse.Namespace, cfg: HMMConfig) -> dict[str, Any]:
    """Load an existing HMM pack or fit a new one using the canonical HMM inputs."""
    _validate_hmm_inputs(features)
    hmm_pack_path = Path(args.hmm_pack)

    if args.retrain_hmm or not hmm_pack_path.exists():
        hmm_pack = fit_hmm_pack(features, cfg=cfg)
        save_hmm_pack(hmm_pack, str(hmm_pack_path))
        return hmm_pack

    hmm_pack = load_hmm_pack(str(hmm_pack_path))
    if list(hmm_pack.get("feature_cols", [])) != list(HMM_FEATURE_COLS):
        raise ValueError(
            "Loaded HMM pack does not match the canonical HMM feature contract. "
            f"Expected {list(HMM_FEATURE_COLS)}, got {list(hmm_pack.get('feature_cols', []))}."
        )
    return hmm_pack


def apply_hmm_stage(features: pd.DataFrame, hmm_pack: dict[str, Any], args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply latent-state inference and semantic HMM labels to the descriptive feature table."""
    hmm_features, hmm_meta = apply_hmm_pack(features, hmm_pack, mode=args.hmm_mode)
    if not hmm_features.index.equals(features.index):
        raise ValueError("HMM stage changed index alignment unexpectedly.")
    _validate_hmm_outputs(hmm_features, hmm_pack)
    return hmm_features, hmm_meta


def maybe_apply_hazard_stage(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    """Optionally apply the saved hazard pack after HMM inference."""
    if not args.apply_hazard:
        return features, None

    hazard_pack_path = Path(args.hazard_pack)
    if not hazard_pack_path.exists():
        raise FileNotFoundError(f"Hazard pack not found: {hazard_pack_path}")

    from src.models.hazard_calibrated import apply_hazard_models

    hazard_pack = joblib.load(hazard_pack_path)
    hazard_feature_cols = list(hazard_pack.get("feature_cols", []))
    missing_columns = [column for column in hazard_feature_cols if column not in features.columns]
    if missing_columns:
        raise ValueError(
            "Hazard pack requires columns that are missing from the enriched feature table: "
            f"{missing_columns}."
        )

    hazard_features = apply_hazard_models(features, hazard_pack)
    if not hazard_features.index.equals(features.index):
        raise ValueError("Hazard stage changed index alignment unexpectedly.")
    _validate_hazard_outputs(hazard_features)

    hazard_meta = {
        "pack_path": str(hazard_pack_path),
        "feature_cols": hazard_feature_cols,
        "meta": hazard_pack.get("meta", {}),
        "diagnostics": hazard_pack.get("diagnostics", {}),
        "test_corr_rate": hazard_pack.get("test_corr_rate"),
        "test_corr_pred_mean": hazard_pack.get("test_corr_pred_mean"),
        "test_reb_rate": hazard_pack.get("test_reb_rate"),
        "test_reb_pred_mean": hazard_pack.get("test_reb_pred_mean"),
    }
    return hazard_features, hazard_meta


def export_payload(
    features: pd.DataFrame,
    hmm_meta: dict[str, Any],
    hazard_meta: dict[str, Any] | None,
    out_path: Path,
) -> None:
    """Export descriptive, HMM, and optional hazard columns into the BTC CSV feature store."""
    export_frame = export_feature_csv(features, out_path, columns=list(features.columns), dropna_on="close")
    if export_frame.columns[0] != "date":
        raise ValueError("Feature export must use 'date' as the first CSV column.")

    required_columns = [
        *_expected_hmm_state_columns(int(hmm_meta["cfg"]["n_states"])),
        "HMM_DOM",
        "HMM_CONF",
        "HMM_LABEL",
        *HMM_SEMANTIC_COLUMNS,
    ]
    if hazard_meta is not None:
        required_columns.extend(HAZARD_OUTPUT_COLUMNS)
    missing_columns = [column for column in required_columns if column not in export_frame.columns]
    if missing_columns:
        raise ValueError(f"Export CSV is missing expected enriched columns: {missing_columns}")


def print_summary(features: pd.DataFrame, hmm_meta: dict[str, Any], hazard_meta: dict[str, Any] | None) -> None:
    """Print a compact summary of the latest enriched BTC row and HMM diagnostics."""
    last_timestamp = features.index[-1]
    last_row = features.iloc[-1]

    print(f"Rows: {len(features)}")
    print(f"Range: {features.index.min().strftime('%Y-%m-%d')} -> {features.index.max().strftime('%Y-%m-%d')}")
    print(f"Last timestamp: {last_timestamp.strftime('%Y-%m-%d')}")
    print("Last enriched snapshot:")
    for column in SUMMARY_COLUMNS:
        value = last_row.get(column, pd.NA)
        if pd.isna(value):
            rendered = "na"
        elif isinstance(value, str):
            rendered = value
        else:
            rendered = f"{float(value):.6f}"
        print(f"  {column}: {rendered}")

    diagnostics = hmm_meta.get("diagnostics", {})
    print(
        "HMM diagnostics:",
        f"mode={hmm_meta['mode']}",
        f"usable_rows={diagnostics.get('usable_rows')}",
        f"loglik={diagnostics.get('final_loglik')}",
        f"iters={diagnostics.get('n_iter_ran')}",
        f"converged={diagnostics.get('converged')}",
    )
    print(f"Hazard applied: {'yes' if hazard_meta is not None else 'no'}")


def main() -> None:
    """Run the BTC descriptive feature, HMM, and optional hazard pipeline end to end."""
    try:
        args = parse_args()
        features = load_base_features(args)
        hmm_pack = fit_or_load_hmm(features, args, build_hmm_config(args))
        hmm_features, hmm_meta = apply_hmm_stage(features, hmm_pack, args)
        final_features, hazard_meta = maybe_apply_hazard_stage(hmm_features, args)
        out_path = Path(args.out_csv)
        export_payload(final_features, hmm_meta, hazard_meta, out_path)
        print(f"Wrote: {out_path}")
        print_summary(final_features, hmm_meta, hazard_meta)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Regime HMM pipeline failed: {exc}") from exc


if __name__ == "__main__":
    main()
