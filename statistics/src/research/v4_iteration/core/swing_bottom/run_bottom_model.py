from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import (
    DEFAULT_BOTTOM_DATASET_CSV_PATH,
    DEFAULT_BOTTOM_MODEL_METRICS_CSV_PATH,
    DEFAULT_BOTTOM_MODEL_PREDICTIONS_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_BOTTOM_MODEL_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_BOTTOM_MODEL_BASELINE.md"
DEFAULT_TARGET_COLUMN = "bottom_zone_time_20pct"
MODEL_NAME = "logistic_regression_balanced"
VARIANT_NAME = "all_rows"

FORBIDDEN_PREFIXES: tuple[str, ...] = ("next_", "containing_")
FORBIDDEN_EXACT_COLUMNS: tuple[str, ...] = (
    "date",
    "bottom_zone_time_20pct",
    "bottom_zone_time_10pct",
    "bottom_zone_range_20pct",
    "bottom_zone_range_10pct",
    "near_current_swing_low_2pct",
    "near_current_swing_low_3pct",
    "down_swing_progress_time",
    "down_swing_progress_range",
    "is_in_confirmed_down_swing",
    "is_in_confirmed_up_swing",
)
ADDITIONAL_EXCLUDED_COLUMNS: tuple[str, ...] = (
    "last_confirmed_pivot_date",
    "current_leg_start_date",
    "swing_granularity",
)
EVAL_LABEL_COLUMNS: tuple[str, ...] = (
    "near_current_swing_low_2pct",
    "near_current_swing_low_3pct",
    "dist_to_next_down_swing_low_pct",
    "days_to_next_down_swing_low",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the first leakage-safe swing-bottom baseline model.",
    )
    parser.add_argument(
        "--bottom-dataset-csv",
        default=str(DEFAULT_BOTTOM_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/bottom_dataset.csv",
    )
    parser.add_argument(
        "--target-column",
        default=DEFAULT_TARGET_COLUMN,
        help="Default: bottom_zone_time_20pct",
    )
    parser.add_argument(
        "--out-predictions-csv",
        default=str(DEFAULT_BOTTOM_MODEL_PREDICTIONS_CSV_PATH),
        help="Default: ../out/swing_bottom/bottom_model_predictions.csv",
    )
    parser.add_argument(
        "--out-metrics-csv",
        default=str(DEFAULT_BOTTOM_MODEL_METRICS_CSV_PATH),
        help="Default: ../out/swing_bottom/bottom_model_metrics.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_BOTTOM_MODEL_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_BOTTOM_MODEL_BASELINE.md",
    )
    return parser.parse_args()


def build_feature_columns(columns: list[str], target_column: str) -> list[str]:
    excluded = set(FORBIDDEN_EXACT_COLUMNS) | set(ADDITIONAL_EXCLUDED_COLUMNS) | {target_column}
    selected: list[str] = []
    for column in columns:
        if column in excluded:
            continue
        if any(column.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            continue
        selected.append(column)

    forbidden_entered = [
        column
        for column in selected
        if column in excluded or any(column.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
    ]
    if forbidden_entered:
        raise ValueError(f"Leakage columns entered the feature set: {forbidden_entered}")
    if not selected:
        raise ValueError("Feature selection produced an empty feature set.")
    return selected


def build_dataset(path: str | Path, target_column: str) -> tuple[pd.DataFrame, list[str], list[str]]:
    frame = load_feature_csv(path)
    if target_column not in frame.columns:
        raise ValueError(f"Target column '{target_column}' is missing from the bottom dataset.")
    frame = frame.sort_values("date").reset_index(drop=True)
    raw_columns = frame.columns.tolist()

    feature_columns = build_feature_columns(frame.columns.tolist(), target_column)
    working = frame.loc[frame[target_column].notna()].copy()
    if working.empty:
        raise ValueError("No rows remain after filtering to defined target values.")

    feature_non_missing = working.loc[:, feature_columns].notna().any(axis=1)
    working = working.loc[feature_non_missing].reset_index(drop=True)
    if working.empty:
        raise ValueError("No rows remain after filtering to rows with available feature inputs.")
    return working, feature_columns, raw_columns


def build_splits(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n_rows = len(frame)
    train_end = int(n_rows * 0.70)
    validation_end = int(n_rows * 0.85)
    if train_end <= 0 or validation_end <= train_end or validation_end >= n_rows:
        raise ValueError("Chronological split boundaries are invalid.")

    train = frame.iloc[:train_end].copy()
    validation = frame.iloc[train_end:validation_end].copy()
    test = frame.iloc[validation_end:].copy()

    if train["date"].max() >= validation["date"].min():
        raise ValueError("Train and validation splits overlap.")
    if validation["date"].max() >= test["date"].min():
        raise ValueError("Validation and test splits overlap.")
    return train, validation, test


def drop_constant_features(train: pd.DataFrame, feature_columns: list[str]) -> list[str]:
    kept: list[str] = []
    for column in feature_columns:
        non_null = train[column].dropna()
        if non_null.empty:
            continue
        if pd.api.types.is_bool_dtype(non_null):
            unique_count = int(non_null.astype(int).nunique())
        else:
            unique_count = int(non_null.nunique())
        if unique_count > 1:
            kept.append(column)
    if not kept:
        raise ValueError("All candidate features were constant or empty in the training split.")
    return kept


def prepare_feature_frames(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    train_x = train.loc[:, feature_columns].copy()
    validation_x = validation.loc[:, feature_columns].copy()
    test_x = test.loc[:, feature_columns].copy()

    bool_columns = [column for column in feature_columns if pd.api.types.is_bool_dtype(train_x[column])]
    for frame in (train_x, validation_x, test_x):
        for column in bool_columns:
            frame[column] = frame[column].astype(float)

    numeric_columns: list[str] = []
    categorical_columns: list[str] = []
    for column in feature_columns:
        if pd.api.types.is_numeric_dtype(train_x[column]):
            numeric_columns.append(column)
        else:
            categorical_columns.append(column)
    if not numeric_columns and not categorical_columns:
        raise ValueError("Prepared feature matrix has no usable columns.")
    return train_x, validation_x, test_x, numeric_columns, categorical_columns


def build_model(numeric_columns: list[str], categorical_columns: list[str]) -> Pipeline:
    transformers: list[tuple[str, object, list[str]]] = []
    if numeric_columns:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            )
        )
    if categorical_columns:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            )
        )

    return Pipeline(
        steps=[
            ("preprocessor", ColumnTransformer(transformers=transformers)),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=0,
                ),
            ),
        ]
    )


def ensure_binary_target(name: str, values: pd.Series) -> None:
    unique_values = sorted(pd.Series(values).dropna().astype(int).unique().tolist())
    if unique_values != [0, 1]:
        raise ValueError(f"{name} must contain both classes 0 and 1; got {unique_values}.")


def compute_split_metrics(y_true: pd.Series, proba: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "brier_score": float(brier_score_loss(y_true, proba)),
        "log_loss": float(log_loss(y_true, np.column_stack([1.0 - proba, proba]), labels=[0, 1])),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
    }


def build_predictions(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    model: Pipeline,
    feature_columns: list[str],
    target_column: str,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for split_name, split_frame in (("train", train), ("validation", validation), ("test", test)):
        split_x = split_frame.loc[:, feature_columns]
        proba = model.predict_proba(split_x)[:, 1]
        pred = (proba >= 0.50).astype(int)
        export = split_frame.loc[:, ["date", "close", target_column, *EVAL_LABEL_COLUMNS]].copy()
        export["split"] = split_name
        export["predicted_probability"] = proba
        export["predicted_class"] = pred
        rows.append(export)
    predictions = pd.concat(rows, ignore_index=True)
    predictions = predictions.rename(columns={target_column: "target"})
    return predictions


def build_top_bucket_rows(predictions: pd.DataFrame) -> list[dict[str, object]]:
    test = predictions.loc[predictions["split"] == "test"].copy()
    test = test.sort_values("predicted_probability", ascending=False).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for fraction in (0.05, 0.10, 0.20):
        bucket_count = max(1, int(np.ceil(len(test) * fraction)))
        bucket = test.head(bucket_count).copy()
        rows.append(
            {
                "row_type": "top_bucket",
                "model_name": MODEL_NAME,
                "variant": VARIANT_NAME,
                "split": "test",
                "metric_name": np.nan,
                "metric_value": np.nan,
                "bucket_fraction": fraction,
                "bucket_count": int(bucket_count),
                "target_hit_rate": float(pd.to_numeric(bucket["target"], errors="coerce").mean()),
                "avg_near_current_swing_low_2pct": float(pd.to_numeric(bucket["near_current_swing_low_2pct"], errors="coerce").mean()),
                "avg_near_current_swing_low_3pct": float(pd.to_numeric(bucket["near_current_swing_low_3pct"], errors="coerce").mean()),
                "avg_dist_to_next_down_swing_low_pct": float(pd.to_numeric(bucket["dist_to_next_down_swing_low_pct"], errors="coerce").mean()),
                "avg_days_to_next_down_swing_low": float(pd.to_numeric(bucket["days_to_next_down_swing_low"], errors="coerce").mean()),
                "feature_name": np.nan,
                "coefficient": np.nan,
                "abs_rank": np.nan,
                "row_count": int(len(bucket)),
                "positive_rate": float(pd.to_numeric(bucket["target"], errors="coerce").mean()),
            }
        )
    return rows


def build_coefficient_rows(model: Pipeline) -> list[dict[str, object]]:
    preprocessor: ColumnTransformer = model.named_steps["preprocessor"]
    classifier: LogisticRegression = model.named_steps["model"]
    feature_names = preprocessor.get_feature_names_out().tolist()
    coefficients = classifier.coef_[0]
    ranking = pd.DataFrame({"feature_name": feature_names, "coefficient": coefficients})
    ranking["abs_rank"] = ranking["coefficient"].abs().rank(method="first", ascending=False).astype(int)
    ranking = ranking.sort_values(["abs_rank", "feature_name"]).reset_index(drop=True)

    rows: list[dict[str, object]] = []
    for row in ranking.itertuples(index=False):
        rows.append(
            {
                "row_type": "coefficient",
                "model_name": MODEL_NAME,
                "variant": VARIANT_NAME,
                "split": "train",
                "metric_name": np.nan,
                "metric_value": np.nan,
                "bucket_fraction": np.nan,
                "bucket_count": np.nan,
                "target_hit_rate": np.nan,
                "avg_near_current_swing_low_2pct": np.nan,
                "avg_near_current_swing_low_3pct": np.nan,
                "avg_dist_to_next_down_swing_low_pct": np.nan,
                "avg_days_to_next_down_swing_low": np.nan,
                "feature_name": row.feature_name,
                "coefficient": float(row.coefficient),
                "abs_rank": int(row.abs_rank),
                "row_count": np.nan,
                "positive_rate": np.nan,
            }
        )
    return rows


def build_metrics_table(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    predictions: pd.DataFrame,
    model: Pipeline,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split_name, split_frame in (("train", train), ("validation", validation), ("test", test)):
        split_predictions = predictions.loc[predictions["split"] == split_name].copy()
        y_true = pd.to_numeric(split_predictions["target"], errors="coerce").astype(int)
        proba = pd.to_numeric(split_predictions["predicted_probability"], errors="coerce").to_numpy(dtype=float)
        pred = pd.to_numeric(split_predictions["predicted_class"], errors="coerce").astype(int).to_numpy(dtype=int)
        if split_name in {"validation", "test"}:
            ensure_binary_target(split_name, y_true)
        metric_values = compute_split_metrics(y_true, proba, pred)
        for metric_name, metric_value in metric_values.items():
            rows.append(
                {
                    "row_type": "split_metric",
                    "model_name": MODEL_NAME,
                    "variant": VARIANT_NAME,
                    "split": split_name,
                    "metric_name": metric_name,
                    "metric_value": float(metric_value),
                    "bucket_fraction": np.nan,
                    "bucket_count": np.nan,
                    "target_hit_rate": np.nan,
                    "avg_near_current_swing_low_2pct": np.nan,
                    "avg_near_current_swing_low_3pct": np.nan,
                    "avg_dist_to_next_down_swing_low_pct": np.nan,
                    "avg_days_to_next_down_swing_low": np.nan,
                    "feature_name": np.nan,
                    "coefficient": np.nan,
                    "abs_rank": np.nan,
                    "row_count": int(len(split_predictions)),
                    "positive_rate": float(y_true.mean()),
                }
            )
    rows.extend(build_top_bucket_rows(predictions))
    rows.extend(build_coefficient_rows(model))
    return pd.DataFrame(rows)


def render_markdown(
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    *,
    feature_columns: list[str],
    candidate_feature_columns: list[str],
    raw_columns: list[str],
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    target_column: str,
) -> str:
    split_metrics = metrics.loc[metrics["row_type"] == "split_metric"].copy()
    top_buckets = metrics.loc[metrics["row_type"] == "top_bucket"].copy()
    coefficients = metrics.loc[metrics["row_type"] == "coefficient"].copy().sort_values("abs_rank").head(12)

    excluded_by_rule = sorted(set(raw_columns) - set(candidate_feature_columns))
    dropped_as_constant = sorted(set(candidate_feature_columns) - set(feature_columns))

    def metric(split: str, metric_name: str) -> float:
        row = split_metrics.loc[(split_metrics["split"] == split) & (split_metrics["metric_name"] == metric_name)]
        return float(row.iloc[0]["metric_value"])

    lines = [
        "# SAFE v4.0 Bottom Model Baseline",
        "",
        "## Target",
        "",
        f"- default target: `{target_column}`",
        "- baseline variant: all eligible rows, strict chronological split, no shuffle",
        "- model: class-balanced logistic regression",
        "",
        "## Feature Set",
        "",
        "- causal price, volatility, participation, regime, hazard, on-chain, and live swing-state fields",
        "- categorical handling: one-hot encoding for non-numeric causal fields such as `live_swing_direction`",
        "- numeric handling: median imputation plus standardization",
        f"- retained feature columns: `{len(feature_columns)}`",
        f"- excluded columns by leakage rule or identifier handling: `{len(excluded_by_rule)}`",
        f"- additional columns dropped as constant / empty in train: `{len(dropped_as_constant)}`",
        "",
        "Leakage exclusion rule:",
        "- drop all `next_*` columns",
        "- drop all `containing_*` columns",
        "- drop all bottom-label / future-bottom target columns",
        "- drop raw date-like helper columns and constant granularity identifiers",
        "",
        "## Row Counts And Splits",
        "",
        f"- total eligible rows: `{len(predictions)}`",
        f"- train: `{len(train)}` rows, `{pd.to_datetime(train['date']).min().date()}` -> `{pd.to_datetime(train['date']).max().date()}`",
        f"- validation: `{len(validation)}` rows, `{pd.to_datetime(validation['date']).min().date()}` -> `{pd.to_datetime(validation['date']).max().date()}`",
        f"- test: `{len(test)}` rows, `{pd.to_datetime(test['date']).min().date()}` -> `{pd.to_datetime(test['date']).max().date()}`",
        "",
        "## Classifier Metrics",
        "",
        "| Split | ROC AUC | PR AUC | Brier | Log loss | Precision | Recall | F1 | Positive rate |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for split in ("validation", "test"):
        positive_rate = float(
            split_metrics.loc[(split_metrics["split"] == split) & (split_metrics["metric_name"] == "roc_auc"), "positive_rate"].iloc[0]
        )
        lines.append(
            f"| `{split}` | {metric(split, 'roc_auc'):.3f} | {metric(split, 'pr_auc'):.3f} | "
            f"{metric(split, 'brier_score'):.4f} | {metric(split, 'log_loss'):.4f} | "
            f"{metric(split, 'precision'):.3f} | {metric(split, 'recall'):.3f} | {metric(split, 'f1'):.3f} | {positive_rate:.2%} |"
        )

    lines.extend(["", "## Top-Bucket Quality On Test", ""])
    lines.append("| Bucket | Rows | Hit rate | Avg near low 2% | Avg near low 3% | Avg dist to next low | Avg days to next low |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for _, row in top_buckets.sort_values("bucket_fraction").iterrows():
        lines.append(
            f"| top `{int(float(row['bucket_fraction']) * 100)}`% | {int(row['bucket_count'])} | {row['target_hit_rate']:.2%} | "
            f"{row['avg_near_current_swing_low_2pct']:.2%} | {row['avg_near_current_swing_low_3pct']:.2%} | "
            f"{row['avg_dist_to_next_down_swing_low_pct']:.2%} | {row['avg_days_to_next_down_swing_low']:.1f} |"
        )

    lines.extend(["", "## Most Important Coefficients", ""])
    lines.append("| Rank | Feature | Coefficient |")
    lines.append("| --- | --- | --- |")
    for _, row in coefficients.iterrows():
        lines.append(f"| {int(row['abs_rank'])} | `{row['feature_name']}` | {float(row['coefficient']):.4f} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    if metric("test", "roc_auc") > 0.60 and metric("test", "pr_auc") > 0.20:
        lines.append("- the first leakage-safe baseline shows usable signal on the held-out test segment.")
    else:
        lines.append("- the first leakage-safe baseline is weak; the target may need a richer feature treatment or a more conditional setup.")

    if metric("test", "recall") > metric("test", "precision"):
        lines.append("- the current 0.5 threshold behaves more like a broad detector than a precise late-stage bottom selector.")
    else:
        lines.append("- the current 0.5 threshold is relatively selective, not just a generic down-move detector.")

    lines.append("- this is still a baseline modeling pass only: no trade rules, exits, or backtests are implied here.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    dataset, candidate_feature_columns, raw_columns = build_dataset(args.bottom_dataset_csv, args.target_column)
    train, validation, test = build_splits(dataset)

    ensure_binary_target("train", train[args.target_column])
    ensure_binary_target("validation", validation[args.target_column])
    ensure_binary_target("test", test[args.target_column])

    feature_columns = drop_constant_features(train, candidate_feature_columns)
    train_x, validation_x, test_x, numeric_columns, categorical_columns = prepare_feature_frames(
        train,
        validation,
        test,
        feature_columns,
    )

    model = build_model(numeric_columns, categorical_columns)
    train_y = pd.to_numeric(train[args.target_column], errors="coerce").astype(int)
    model.fit(train_x, train_y)

    predictions = build_predictions(train, validation, test, model, feature_columns, args.target_column)
    metrics = build_metrics_table(train, validation, test, predictions, model)

    out_predictions = Path(args.out_predictions_csv)
    out_metrics = Path(args.out_metrics_csv)
    out_md = Path(args.out_md)
    for path in (out_predictions, out_metrics, out_md):
        path.parent.mkdir(parents=True, exist_ok=True)

    predictions.to_csv(out_predictions, index=False, float_format="%.8f")
    metrics.to_csv(out_metrics, index=False, float_format="%.8f")
    out_md.write_text(
        render_markdown(
            predictions,
            metrics,
            feature_columns=feature_columns,
            candidate_feature_columns=candidate_feature_columns,
            raw_columns=raw_columns,
            train=train,
            validation=validation,
            test=test,
            target_column=args.target_column,
        ),
        encoding="utf-8",
    )

    test_metrics = metrics.loc[(metrics["row_type"] == "split_metric") & (metrics["split"] == "test")]
    roc_auc = float(test_metrics.loc[test_metrics["metric_name"] == "roc_auc", "metric_value"].iloc[0])
    pr_auc = float(test_metrics.loc[test_metrics["metric_name"] == "pr_auc", "metric_value"].iloc[0])

    print("SAFE v4.0 bottom model baseline complete.")
    print(f"Target: {args.target_column}")
    print(f"Eligible rows: {len(predictions)}")
    print(f"Train/validation/test: {len(train)} / {len(validation)} / {len(test)}")
    print(f"Retained features: {len(feature_columns)}")
    print(f"Test ROC AUC: {roc_auc:.3f}")
    print(f"Test PR AUC: {pr_auc:.3f}")
    print(f"Wrote: {out_predictions}")
    print(f"Wrote: {out_metrics}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
