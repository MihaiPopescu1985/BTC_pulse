import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.features.price_features import compute_price_features, to_echarts_json, FeatureConfig

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--price-json", default="data/daily_price.json")
    return ap.parse_args()

def main():
    args = parse_args()
    df = load_daily_price_json(args.price_json)

    cfg = FeatureConfig(
        adapt_win=365 * 2,
        band_win=100,
        trend_win_mid=50,
    )

    feats = compute_price_features(df, cfg=cfg)

    out_dir = Path("out") / args.asset
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = to_echarts_json(feats)
    drop_series = {"E_target_safe", "L_target_safe", "direction_safe", "range_score"}
    for key in drop_series:
        payload.get("series", {}).pop(key, None)
    out_path = out_dir / "features.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # quick sanity print
    print("Wrote:", out_path)
    print("Meta:", payload["meta"])
    required_states = [f"HMM_STATE_{k}" for k in range(4)]
    missing = [c for c in required_states if c not in feats.columns]
    assert not missing, f"Missing HMM state columns in features: {missing}"

    print("Last probs:",
          feats[[
              *required_states,
              "P_CORRECTION_10D", "P_REBOUND_10D"
          ]].dropna().tail(1).round(4).to_string())


if __name__ == "__main__":
    main()
