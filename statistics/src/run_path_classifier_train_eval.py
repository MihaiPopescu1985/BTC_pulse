#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.path_classifier import (
    PATH_CLASSIFIER_FEATURES,
    build_base_estimator,
    build_path_classifier_dataset,
    feature_importance_frame,
    fit_probabilistic_model,
    generate_walk_forward_folds,
    save_model_pack,
)
from src.models.path_probabilities import PATH_LABELS
from src.path_config import (
    DEFAULT_FEATURES_JSON_PATH,
    DEFAULT_ONCHAIN_FEATURES_JSON_PATH,
    DEFAULT_PRICE_JSON_PATH,
    OUT_DIR,
)


DEFAULT_OUT_DIR = OUT_DIR / "path_classifier_eval"
DEFAULT_MODEL_PATH = OUT_DIR / "path_classifier" / "model.joblib"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and walk-forward evaluate a supervised SAFE path classifier.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-json", default=str(DEFAULT_FEATURES_JSON_PATH), help="Default: ../out/features.json")
    parser.add_argument(
        "--days",
        type=int,
        default=10,
        help="Forward horizon in days. Default: 10",
    )
    parser.add_argument("--up-pct", type=float, default=0.02)
    parser.add_argument("--down-pct", type=float, default=0.02)
    parser.add_argument(
        "--ambiguity-mode",
        choices=["pessimistic", "optimistic", "skip_ambiguous", "label_as_both_same_day"],
        default="skip_ambiguous",
    )
    parser.add_argument("--train-start-date", default=None)
    parser.add_argument("--eval-start-date", default=None)
    parser.add_argument("--eval-end-date", default=None)
    parser.add_argument("--min-train-rows", type=int, default=250)
    parser.add_argument("--fold-size-days", type=int, default=30)
    parser.add_argument("--expanding-window", choices=["true", "false"], default="true")
    parser.add_argument("--model-type", choices=["gbt", "rf", "logreg"], default="gbt")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    return parser.parse_args()


def _safe_log_loss(probability: float) -> float:
    clipped = min(max(float(probability), 1e-12), 1.0 - 1e-12)
    return -float(np.log(clipped))


def _per_class_brier(predictions: pd.DataFrame, labels: pd.Series, classes: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for class_name in classes:
        truth = (labels == class_name).astype(float).to_numpy()
        probs = predictions[class_name].to_numpy(dtype=float)
        scores[class_name] = float(np.mean((probs - truth) ** 2))
    return scores


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


def main() -> None:
    args = parse_args()
    expanding_window = args.expanding_window == "true"

    onchain_path = DEFAULT_ONCHAIN_FEATURES_JSON_PATH if DEFAULT_ONCHAIN_FEATURES_JSON_PATH.exists() else None
    dataset = build_path_classifier_dataset(
        args.price_json,
        args.features_json,
        onchain_features_json_path=onchain_path,
        days=args.days,
        up_pct=args.up_pct,
        down_pct=args.down_pct,
        ambiguity_mode=args.ambiguity_mode,
    )

    folds = generate_walk_forward_folds(
        dataset,
        train_start_date=args.train_start_date,
        eval_start_date=args.eval_start_date,
        eval_end_date=args.eval_end_date,
        min_train_rows=args.min_train_rows,
        fold_size_days=args.fold_size_days,
        expanding_window=expanding_window,
    )

    prediction_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []

    for fold in folds:
        X_train = dataset.features.iloc[fold.train_idx]
        y_train = dataset.labels.iloc[fold.train_idx]
        X_test = dataset.features.iloc[fold.test_idx]
        y_test = dataset.labels.iloc[fold.test_idx]

        estimator, fit_info = fit_probabilistic_model(
            X_train,
            y_train,
            model_type=args.model_type,
            seed=args.seed + fold.fold_id,
        )
        classes = list(estimator.classes_)
        prob_matrix = estimator.predict_proba(X_test)
        pred_frame = pd.DataFrame(prob_matrix, index=X_test.index, columns=classes)
        pred_top1 = pred_frame.idxmax(axis=1)
        pred_top2 = pred_frame.apply(lambda row: "|".join(row.nlargest(2).index.tolist()), axis=1)

        fold_log_loss = np.mean(
            [_safe_log_loss(float(pred_frame.loc[idx, label])) for idx, label in zip(y_test.index, y_test)]
        )
        fold_rows.append(
            {
                "fold_id": fold.fold_id,
                "train_rows": int(len(X_train)),
                "test_rows": int(len(X_test)),
                "train_start": str(X_train.index.min()),
                "train_end": str(X_train.index.max()),
                "test_start": str(X_test.index.min()),
                "test_end": str(X_test.index.max()),
                "log_loss": float(fold_log_loss),
                "top1_accuracy": float(np.mean(pred_top1 == y_test)),
                "calibration_used": int(fit_info["calibration_used"]),
            }
        )

        for idx in X_test.index:
            row = {
                "anchor_date": idx,
                "realized_label": dataset.labels.loc[idx],
                "top1_label": pred_top1.loc[idx],
                "top2_labels": pred_top2.loc[idx],
                **dataset.meta.loc[idx].to_dict(),
            }
            for class_name in set(PATH_LABELS) | set(classes):
                row[class_name] = float(pred_frame.loc[idx, class_name]) if class_name in pred_frame.columns else 0.0
            prediction_rows.append(row)

    predictions = pd.DataFrame(prediction_rows).sort_values("anchor_date").reset_index(drop=True)
    classes = list(PATH_LABELS) + sorted(set(predictions["realized_label"]) - set(PATH_LABELS))
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
        np.mean([label in top2.split("|") for label, top2 in zip(labels, predictions["top2_labels"])])
    )
    confusion = _confusion_matrix(labels, predicted_top1, classes)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(out_dir / "predictions.csv", index=False)
    confusion.to_csv(out_dir / "confusion_matrix.csv")
    pd.DataFrame(fold_rows).to_csv(out_dir / "fold_summary.csv", index=False)

    full_estimator, full_fit_info = fit_probabilistic_model(
        dataset.features,
        dataset.labels,
        model_type=args.model_type,
        seed=args.seed,
    )
    reference_estimator = build_base_estimator(args.model_type, args.seed).fit(dataset.features, dataset.labels)
    importance = feature_importance_frame(reference_estimator, dataset.feature_cols, args.model_type)
    importance.to_csv(out_dir / "feature_importance.csv", index=False)

    report = {
        "rows_evaluated": int(len(predictions)),
        "feature_count_used": int(len(dataset.feature_cols)),
        "feature_list_candidate_count": int(len(PATH_CLASSIFIER_FEATURES)),
        "class_distribution_realized": labels.value_counts(normalize=True).sort_index().to_dict(),
        "class_distribution_predicted_mean": {
            class_name: float(predictions[class_name].mean()) for class_name in classes
        },
        "multiclass_log_loss": float(np.mean(log_losses)),
        "per_class_brier": _per_class_brier(predictions, labels, classes),
        "top1_accuracy": float(np.mean(predicted_top1 == labels)),
        "top2_coverage": top2_coverage,
        "macro_f1": float(f1_score(labels, predicted_top1, average="macro")),
        "confusion_matrix_summary": {
            actual: {pred: int(value) for pred, value in row.items()}
            for actual, row in confusion.to_dict(orient="index").items()
        },
        "model_type": args.model_type,
        "days": int(args.days),
        "up_pct": float(args.up_pct),
        "down_pct": float(args.down_pct),
        "ambiguity_mode": args.ambiguity_mode,
        "expanding_window": expanding_window,
        "min_train_rows": int(args.min_train_rows),
        "fold_size_days": int(args.fold_size_days),
        "train_start_date": args.train_start_date,
        "eval_start_date": args.eval_start_date,
        "eval_end_date": args.eval_end_date,
        "calibration_used_on_full_refit": bool(full_fit_info["calibration_used"]),
    }
    _write_json(out_dir / "report.json", report)

    if args.save_model:
        save_model_pack(
            Path(args.model_path),
            model=full_estimator,
            feature_cols=dataset.feature_cols,
            feature_groups={feature: importance.set_index("feature").loc[feature, "group"] for feature in dataset.feature_cols},
            model_type=args.model_type,
            days=args.days,
            up_pct=args.up_pct,
            down_pct=args.down_pct,
            ambiguity_mode=args.ambiguity_mode,
            train_rows=len(dataset.features),
        )

    print("=== SAFE Supervised Path Classifier ===")
    print(f"Rows evaluated: {report['rows_evaluated']}")
    print(
        f"Model: {args.model_type} | horizon={args.days}d | "
        f"barriers=+{args.up_pct * 100:.2f}% / -{args.down_pct * 100:.2f}%"
    )
    print(f"Log loss: {report['multiclass_log_loss']:.6f}")
    print(f"Top-1 accuracy: {report['top1_accuracy']:.4f}")
    print(f"Top-2 coverage: {report['top2_coverage']:.4f}")
    print(f"Macro F1: {report['macro_f1']:.4f}")
    print(f"Feature importance: {out_dir / 'feature_importance.csv'}")
    if args.save_model:
        print(f"Saved model: {args.model_path}")
    print(f"Saved eval outputs: {out_dir}")


if __name__ == "__main__":
    main()
