import argparse
from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import joblib

from src.data.loaders import load_daily_price_json
from src.features.price_features import compute_price_features, compute_extras_features, to_echarts_json, FeatureConfig
from src.models.regime_hmm import (
    HMMConfig, fit_hmm_pack, apply_hmm_pack, save_hmm_pack, load_hmm_pack
)
from src.models.hazard_calibrated import apply_hazard_models


HMM_PACK_PATH = "models/btc/hmm_pack.joblib"


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--price-json", default="data/daily_price.json")
    ap.add_argument("--retrain-hmm", action="store_true")
    ap.add_argument("--hmm-mode", choices=["filter", "smooth"], default="filter")
    ap.add_argument("--hmm-states", type=int, default=4)

    return ap.parse_args()


def main():
    args = parse_args()
    df = load_daily_price_json(args.price_json)
    cfg = FeatureConfig()
    feats = compute_price_features(df, cfg=cfg)
    feats = compute_extras_features(feats, cfg=cfg)

    # Apply HMM regimes
    if args.retrain_hmm or (not os.path.exists(HMM_PACK_PATH)):
        pack = fit_hmm_pack(feats, cfg=HMMConfig(n_states=args.hmm_states, n_iter=80, seed=4))
        save_hmm_pack(pack, HMM_PACK_PATH)
    else:
        pack = load_hmm_pack(HMM_PACK_PATH)

    feats2, hmm_meta = apply_hmm_pack(feats, pack, mode=args.hmm_mode)

    # If hazard model exists, apply calibrated event probs too
    pack_path = Path("models") / args.asset / "hazard_pack.joblib"
    if pack_path.exists():
        try:
            pack = joblib.load(pack_path)
        except Exception as exc:
            print(f"WARN: Failed to load hazard pack ({pack_path}): {exc}")
            hazard_meta = None
            test_meta = None
        else:
            feats2 = apply_hazard_models(feats2.dropna(), pack)
            hazard_meta = pack.get("meta", {})
            test_meta = {
                "test_corr_rate": pack.get("test_corr_rate"),
                "test_reb_rate": pack.get("test_reb_rate"),
            }
    else:
        hazard_meta = None
        test_meta = None

    payload = to_echarts_json(feats2)

    # Add HMM series to payload if present
    # (to_echarts_json currently exports a fixed list; we’ll patch it below)
    payload["meta"]["hmm"] = hmm_meta
    payload["meta"]["hmm_state_labels"] = hmm_meta.get("labels_by_state", [])
    if hazard_meta:
        payload["meta"]["hazard_meta"] = hazard_meta
    if test_meta:
        payload["meta"].update(test_meta)

    out_dir = Path("out") / args.asset
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "features.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Wrote:", out_path)
    train_info = hmm_meta.get("train_info", {})
    loglik = train_info.get("loglik")
    n_iter_ran = train_info.get("n_iter_ran")
    print("HMM loglik:", loglik, "iters:", n_iter_ran)
    if hazard_meta:
        print("Hazard pack found and applied.")
    else:
        print("Hazard pack NOT found; skipping calibrated events.")


if __name__ == "__main__":
    main()
