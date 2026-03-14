import argparse
import json
from pathlib import Path
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib

from src.data.loaders import load_daily_price_json
from src.features.price_features import compute_price_features, FeatureConfig
try:
    from src.features.price_features import compute_extras_features
except ImportError:  # optional for older versions
    compute_extras_features = None
from src.models.hazard_calibrated import apply_hazard_models
from src.models.regime_hmm import apply_hmm_pack, load_hmm_pack
from src.strategy.exposure import compute_exposure_series, ExposureConfig


EXTRA_KEYS = [
    "E_target_safe",
    "L_target_safe",
    "direction_safe",
    "range_score",
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
]


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--price-json", default="data/daily_price.json")
    return ap.parse_args()


def _load_production(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing production features.json: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not data.get("dates"):
        raise ValueError("Production features.json missing dates")
    return data


def _align_series(values: pd.Series, base_dt: pd.DatetimeIndex) -> List[Optional[float]]:
    aligned = values.reindex(base_dt)
    out: List[Optional[float]] = []
    for v in aligned.values:
        if v is None:
            out.append(None)
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        if not np.isfinite(f):
            out.append(None)
        else:
            out.append(f)
    return out


def main():
    args = parse_args()
    asset = args.asset.lower()

    prod_path = Path("out") / asset / "features.json"
    prod = _load_production(prod_path)
    base_dates = prod["dates"]
    base_dt = pd.to_datetime(base_dates)

    df = load_daily_price_json(args.price_json)
    cfg = FeatureConfig()
    feats = compute_price_features(df, cfg=cfg)

    if compute_extras_features is not None:
        feats = compute_extras_features(feats, cfg=cfg)

    hmm_pack_path = Path("models") / asset / "hmm_pack.joblib"
    if hmm_pack_path.exists():
        hmm_pack = load_hmm_pack(str(hmm_pack_path))
        feats, _ = apply_hmm_pack(feats, hmm_pack, mode="filter")

    hazard_pack_path = Path("models") / asset / "hazard_pack.joblib"
    if hazard_pack_path.exists():
        try:
            pack = joblib.load(hazard_pack_path)
        except Exception as exc:
            print(f"WARN: Failed to load hazard pack ({hazard_pack_path}): {exc}")
        else:
            cols = pack.get("feature_cols", [])
            if all(c in feats.columns for c in cols):
                feats = apply_hazard_models(feats, pack)
            else:
                missing = [c for c in cols if c not in feats.columns]
                print(f"WARN: Missing hazard feature cols: {missing}")

    exp_cfg = ExposureConfig(E_base_safe=0.35, L_cap=2.0, max_daily_change=0.10)
    feats = compute_exposure_series(feats, mode="safe", cfg=exp_cfg, use_hmm=True)

    series_out: Dict[str, List[Optional[float]]] = {}
    for key in EXTRA_KEYS:
        if key in feats.columns:
            series_out[key] = _align_series(feats[key], base_dt)
        else:
            series_out[key] = [None] * len(base_dates)

    meta_out = dict(prod.get("meta", {}))
    meta_out["extras_version"] = 1
    meta_out["parent_features"] = str(prod_path)

    out = {
        "meta": meta_out,
        "dates": base_dates,
        "series": series_out,
    }

    out_path = Path("out") / asset / "features_extras.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote:", out_path)


if __name__ == "__main__":
    main()
