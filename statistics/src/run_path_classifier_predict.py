#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.path_classifier import load_model_pack, predict_probabilities_for_date
from src.path_config import (
    DEFAULT_FEATURES_JSON_PATH,
    DEFAULT_ONCHAIN_FEATURES_JSON_PATH,
    DEFAULT_PRICE_JSON_PATH,
    OUT_DIR,
)


DEFAULT_MODEL_PATH = OUT_DIR / "path_classifier" / "model.joblib"
DEFAULT_OUT_JSON_PATH = OUT_DIR / "path_classifier" / "prediction.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict short-horizon SAFE path-class probabilities from the full SAFE state.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-json", default=str(DEFAULT_FEATURES_JSON_PATH), help="Default: ../out/features.json")
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH), help="Default: ../out/path_classifier/model.joblib")
    parser.add_argument("--date", required=True, help="Anchor date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=None, help="Optional override display only. Default: model horizon.")
    parser.add_argument("--up-pct", type=float, default=None, help="Optional override display only. Default: model barrier.")
    parser.add_argument("--down-pct", type=float, default=None, help="Optional override display only. Default: model barrier.")
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_pack = load_model_pack(args.model_path)
    prediction = predict_probabilities_for_date(
        model_pack,
        features_json_path=args.features_json,
        price_json_path=args.price_json,
        date=args.date,
        onchain_features_json_path=DEFAULT_ONCHAIN_FEATURES_JSON_PATH if DEFAULT_ONCHAIN_FEATURES_JSON_PATH.exists() else None,
    )

    if args.days is not None:
        prediction["days"] = args.days
    if args.up_pct is not None:
        prediction["barriers"]["up_pct"] = args.up_pct
        prediction["barriers"]["upper_price"] = prediction["anchor_close"] * (1.0 + args.up_pct)
    if args.down_pct is not None:
        prediction["barriers"]["down_pct"] = args.down_pct
        prediction["barriers"]["lower_price"] = prediction["anchor_close"] * (1.0 - args.down_pct)

    out_json_path = Path(args.out_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(prediction, indent=2, sort_keys=True), encoding="utf-8")

    print("=== SAFE Supervised Path Classifier ===")
    print(f"Anchor date: {prediction['anchor_date']} | close={prediction['anchor_close']:,.2f}")
    print(
        f"Barriers: up={prediction['barriers']['up_pct'] * 100:.2f}% "
        f"({prediction['barriers']['upper_price']:,.2f}) | "
        f"down={prediction['barriers']['down_pct'] * 100:.2f}% "
        f"({prediction['barriers']['lower_price']:,.2f})"
    )
    print("Path probabilities:")
    for label, probability in prediction["path_probabilities"].items():
        print(f"  {label:16s}: {probability:.4f}")
    print(f"Top-1: {prediction['top1_class']}")
    print(f"Top-2: {', '.join(prediction['top2_classes'])}")
    print(f"Saved: {out_json_path}")


if __name__ == "__main__":
    main()
