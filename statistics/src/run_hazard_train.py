import argparse
import json
from pathlib import Path
import joblib
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.features.price_features import compute_price_features, compute_extras_features, to_echarts_json, FeatureConfig
from src.models.hazard_calibrated import train_hazard_models, apply_hazard_models, HazardConfig

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

    pack = train_hazard_models(feats, cfg=HazardConfig(horizon_days=10, corr_quantile=0.70, rebound_quantile=0.70))

    models_dir = Path("models") / args.asset
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pack, models_dir / "hazard_pack.joblib")

    # Apply and export a new JSON with calibrated fields (keep heuristic too for comparison)
    feats2 = apply_hazard_models(feats.dropna(), pack)

    # Patch export: include calibrated series if present
    payload = to_echarts_json(feats2)
    payload["meta"]["hazard_meta"] = pack["meta"]
    payload["meta"]["test_corr_rate"] = pack["test_corr_rate"]
    payload["meta"]["test_reb_rate"] = pack["test_reb_rate"]

    out_dir = Path("out") / args.asset
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "features.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Saved models:", models_dir / "hazard_pack.joblib")
    print("Wrote:", out_path)
    print("Test base rates: corr=", pack["test_corr_rate"], "reb=", pack["test_reb_rate"])
    print("Test predicted means: corr=", pack["test_corr_pred_mean"], "reb=", pack["test_reb_pred_mean"])


if __name__ == "__main__":
    main()
