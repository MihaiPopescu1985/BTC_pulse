import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import joblib

from src.data.loaders import load_daily_price_json
from src.features.price_features import compute_price_features, compute_extras_features, to_echarts_json, FeatureConfig
from src.models.regime_hmm import apply_hmm_pack, load_hmm_pack
from src.models.hazard_calibrated import apply_hazard_models
from src.strategy.exposure import compute_exposure_series, ExposureConfig

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--price-json", default="data/daily_price.json")
    return ap.parse_args()

def main():
    args = parse_args()
    df = load_daily_price_json(args.price_json)
    cfg = FeatureConfig()
    feats = compute_price_features(df, cfg=cfg)
    feats = compute_extras_features(feats, cfg=cfg)

    # HMM (frozen pack, production / no-repaint)
    hmm_pack_path = Path("models") / args.asset / "hmm_pack.joblib"
    if hmm_pack_path.exists():
        hmm_pack = load_hmm_pack(str(hmm_pack_path))
        feats, hmm_meta = apply_hmm_pack(feats, hmm_pack, mode="filter")
    else:
        hmm_meta = None

    # Hazard
    pack_path = Path("models") / args.asset / "hazard_pack.joblib"
    if pack_path.exists():
        pack = joblib.load(pack_path)
        feats = apply_hazard_models(feats.dropna(), pack)
        hazard_meta = pack.get("meta", {})
    else:
        hazard_meta = None

    # Exposure (SAFE)
    cfg = ExposureConfig(E_base_safe=0.35, L_cap=2.0, max_daily_change=0.10)
    feats = compute_exposure_series(feats, mode="safe", cfg=cfg, use_hmm=True)

    payload = to_echarts_json(feats)
    if hmm_meta:
        payload["meta"]["hmm"] = hmm_meta
    if hazard_meta:
        payload["meta"]["hazard_meta"] = hazard_meta
    payload["meta"]["exposure_cfg"] = cfg.__dict__

    out_dir = Path("out") / args.asset
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "features.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Wrote:", out_path)

if __name__ == "__main__":
    main()
