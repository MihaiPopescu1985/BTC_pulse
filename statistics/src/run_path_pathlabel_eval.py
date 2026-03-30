#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.models.path_probabilities import (
    PATH_LABELS,
    build_path_probability_context,
    estimate_path_probabilities_for_anchor,
    realized_path_outcome_from_ohlc,
)
from src.path_config import DEFAULT_FEATURES_JSON_PATH, DEFAULT_HMM_PACK_PATH, DEFAULT_PRICE_JSON_PATH, OUT_DIR
from src.util.safe_touch_probabilities import load_features


DEFAULT_OUT_DIR = OUT_DIR / "path_probabilities_eval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate simulated SAFE path probabilities against realized future OHLC path labels.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-json", default=str(DEFAULT_FEATURES_JSON_PATH), help="Default: ../out/features.json")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--up-pct", type=float, default=0.02)
    parser.add_argument("--down-pct", type=float, default=0.02)
    parser.add_argument("--mode", choices=["mixture", "markov"], default="markov")
    parser.add_argument("--hmm-pack", default=str(DEFAULT_HMM_PACK_PATH), help="Default: ../out/models/hmm_pack.joblib")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--sims", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--winsor-p", type=float, default=0.0025)
    parser.add_argument(
        "--ambiguity-mode",
        choices=["pessimistic", "optimistic", "skip_ambiguous", "label_as_both_same_day"],
        default="skip_ambiguous",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    return parser.parse_args()


def _safe_log_loss(probability: float) -> float:
    clipped = min(max(float(probability), 1e-12), 1.0 - 1e-12)
    return -float(np.log(clipped))


def _per_class_brier(predictions: pd.DataFrame, labels: pd.Series, classes: list[str]) -> dict[str, float]:
    result: dict[str, float] = {}
    for class_name in classes:
        truth = (labels == class_name).astype(float).to_numpy()
        probs = predictions[class_name].to_numpy(dtype=float)
        result[class_name] = float(np.mean((probs - truth) ** 2))
    return result


def _confusion_matrix(labels: pd.Series, predicted: pd.Series, classes: list[str]) -> pd.DataFrame:
    matrix = pd.DataFrame(0, index=classes, columns=classes, dtype=int)
    for actual, pred in zip(labels, predicted):
        matrix.loc[actual, pred] += 1
    matrix.index.name = "realized"
    matrix.columns.name = "predicted"
    return matrix


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_predictions_csv(path: Path, rows: list[dict[str, Any]], classes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        pd.DataFrame(columns=["anchor_date", *classes]).to_csv(path, index=False)
        return
    pd.DataFrame(rows).to_csv(path, index=False)


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
    if args.start_date:
        common_dates = [date for date in common_dates if date >= args.start_date]
    if args.end_date:
        common_dates = [date for date in common_dates if date <= args.end_date]

    rows: list[dict[str, Any]] = []
    skipped_insufficient_future = 0
    skipped_ambiguous = 0

    for anchor_date in common_dates:
        try:
            estimate = estimate_path_probabilities_for_anchor(
                context,
                anchor_date,
                days=args.days,
                up_pct=args.up_pct,
                down_pct=args.down_pct,
                sims=args.sims,
                seed=args.seed,
                mode=args.mode,
            )
            realized = realized_path_outcome_from_ohlc(
                price_frame,
                anchor_date,
                days=args.days,
                up_pct=args.up_pct,
                down_pct=args.down_pct,
                ambiguity_mode=args.ambiguity_mode,
            )
        except ValueError:
            skipped_insufficient_future += 1
            continue

        if realized.label is None:
            skipped_ambiguous += 1
            continue

        probability_columns = estimate["path_probabilities"].copy()
        top1_label = max(probability_columns, key=probability_columns.get)
        top2_labels = sorted(probability_columns, key=probability_columns.get, reverse=True)[:2]

        row: dict[str, Any] = {
            "anchor_date": anchor_date,
            "anchor_close": estimate["anchor_close"],
            "realized_label": realized.label,
            "top1_label": top1_label,
            "top2_labels": "|".join(top2_labels),
            "realized_forward_return": realized.forward_return,
            "ambiguous_realized": int(realized.ambiguous),
            "ambiguity_type": realized.ambiguity_type,
            "first_upper_day": realized.first_upper_day,
            "first_lower_day": realized.first_lower_day,
        }
        row.update(probability_columns)
        rows.append(row)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise ValueError("No evaluation rows available. Check the date range, horizon, or ambiguity mode.")

    predictions = pd.DataFrame(rows)
    extra_classes = sorted(set(predictions["realized_label"]) - set(PATH_LABELS))
    classes = list(PATH_LABELS) + extra_classes
    for class_name in classes:
        if class_name not in predictions.columns:
            predictions[class_name] = 0.0

    labels = predictions["realized_label"]
    predicted_top1 = predictions["top1_label"]

    log_losses = [
        _safe_log_loss(float(predictions.loc[idx, label]))
        for idx, label in zip(predictions.index, labels)
    ]

    top2_coverage = float(
        np.mean(
            [
                label in top2.split("|")
                for label, top2 in zip(labels, predictions["top2_labels"])
            ]
        )
    )

    confusion = _confusion_matrix(labels, predicted_top1, classes)
    confusion.to_csv(out_dir / "confusion_matrix.csv")
    _write_predictions_csv(out_dir / "predictions.csv", rows, classes)

    report = {
        "rows_evaluated": int(len(predictions)),
        "days": int(args.days),
        "up_pct": float(args.up_pct),
        "down_pct": float(args.down_pct),
        "mode": args.mode,
        "sims": int(args.sims),
        "seed": int(args.seed),
        "ambiguity_mode": args.ambiguity_mode,
        "skipped_insufficient_future": int(skipped_insufficient_future),
        "skipped_ambiguous": int(skipped_ambiguous),
        "class_distribution_realized": labels.value_counts(normalize=True).sort_index().to_dict(),
        "class_distribution_predicted_mean": {
            class_name: float(predictions[class_name].mean()) for class_name in classes
        },
        "multiclass_log_loss": float(np.mean(log_losses)),
        "per_class_brier": _per_class_brier(predictions, labels, classes),
        "top1_accuracy": float(np.mean(predicted_top1 == labels)),
        "top2_coverage": top2_coverage,
        "confusion_matrix_summary": {
            actual: {pred: int(value) for pred, value in row.items()}
            for actual, row in confusion.to_dict(orient="index").items()
        },
    }
    _write_json(out_dir / "report.json", report)

    print("=== SAFE Path Probability Evaluation ===")
    print(f"Rows evaluated: {report['rows_evaluated']}")
    print(
        f"Mode: {args.mode} | horizon={args.days}d | "
        f"barriers=+{args.up_pct * 100:.2f}% / -{args.down_pct * 100:.2f}%"
    )
    print(f"Log loss: {report['multiclass_log_loss']:.6f}")
    print(f"Top-1 accuracy: {report['top1_accuracy']:.4f}")
    print(f"Top-2 coverage: {report['top2_coverage']:.4f}")
    print(f"Saved: {out_dir}")


if __name__ == "__main__":
    main()
