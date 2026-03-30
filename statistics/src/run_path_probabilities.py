#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.models.path_probabilities import build_path_probability_context, estimate_path_probabilities_for_anchor
from src.path_config import DEFAULT_FEATURES_JSON_PATH, DEFAULT_HMM_PACK_PATH, DEFAULT_PRICE_JSON_PATH, OUT_DIR
from src.util.safe_touch_probabilities import load_features


DEFAULT_OUT_JSON_PATH = OUT_DIR / "path_probabilities" / "path_probabilities.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate short-horizon path-type probabilities from SAFE regime-conditioned return simulation.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-json", default=str(DEFAULT_FEATURES_JSON_PATH), help="Default: ../out/features.json")
    parser.add_argument("--date", default=None, help="Anchor date YYYY-MM-DD. Default: latest common date.")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--sims", type=int, default=20000)
    parser.add_argument("--up-pct", type=float, default=0.02, help="Upper barrier as decimal return. Default: 0.02")
    parser.add_argument("--down-pct", type=float, default=0.02, help="Lower barrier as decimal return. Default: 0.02")
    parser.add_argument("--mode", choices=["mixture", "markov"], default="markov")
    parser.add_argument("--hmm-pack", default=str(DEFAULT_HMM_PACK_PATH), help="Default: ../out/models/hmm_pack.joblib")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--winsor-p", type=float, default=0.0025)
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON_PATH))
    return parser.parse_args()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    args = parse_args()

    price_frame = load_daily_price_json(args.price_json)
    features_dates, features_series = load_features(args.features_json)
    context = build_path_probability_context(
        price_frame,
        features_dates,
        features_series,
        winsor_p=args.winsor_p,
        hmm_pack_path=Path(args.hmm_pack) if args.mode == "markov" else None,
    )

    common_dates = sorted(set(context.price_frame.index) & set(context.probability_frame.index))
    if not common_dates:
        raise ValueError("No overlapping dates between price data and SAFE features.")
    anchor_date = args.date or common_dates[-1]

    result = estimate_path_probabilities_for_anchor(
        context,
        anchor_date,
        days=args.days,
        up_pct=args.up_pct,
        down_pct=args.down_pct,
        sims=args.sims,
        seed=args.seed,
        mode=args.mode,
    )

    output_payload = {
        "anchor_date": result["anchor_date"],
        "anchor_close": result["anchor_close"],
        "simulation_mode": result["mode"],
        "days": result["days"],
        "sims": result["sims"],
        "seed": result["seed"],
        "barriers": result["barriers"],
        "regime_probabilities": result["regime_probabilities"],
        "path_probabilities": result["path_probabilities"],
        "path_counts": result["path_counts"],
        "average_forward_return": result["average_forward_return"],
        "median_forward_return": result["median_forward_return"],
        "prob_finishing_positive": result["prob_finishing_positive"],
        "prob_finishing_negative": result["prob_finishing_negative"],
        "average_max_drawdown": result["average_max_drawdown"],
        "average_max_runup": result["average_max_runup"],
        "average_daily_log_return": result["average_daily_log_return"],
        "simulation_details": result["simulation_details"],
    }

    out_json_path = Path(args.out_json)
    _write_json(out_json_path, output_payload)

    print("=== SAFE Path Probabilities ===")
    print(f"Anchor date: {result['anchor_date']} | close={result['anchor_close']:,.2f}")
    print(f"Mode: {result['mode']} | horizon={result['days']}d | sims={result['sims']}")
    print(
        f"Barriers: up={result['barriers']['up_pct'] * 100:.2f}% "
        f"({result['barriers']['upper_price']:,.2f}) | "
        f"down={result['barriers']['down_pct'] * 100:.2f}% "
        f"({result['barriers']['lower_price']:,.2f})"
    )
    print("")
    print("Path probabilities:")
    for label, probability in result["path_probabilities"].items():
        print(f"  {label:16s}: {probability:.4f} ({result['path_counts'][label]} sims)")
    print("")
    print(
        "Forward summary: "
        f"mean={result['average_forward_return'] * 100:+.2f}% | "
        f"median={result['median_forward_return'] * 100:+.2f}% | "
        f"P(final > 0)={result['prob_finishing_positive']:.4f} | "
        f"P(final < 0)={result['prob_finishing_negative']:.4f}"
    )
    print(f"Saved: {out_json_path}")


if __name__ == "__main__":
    main()
