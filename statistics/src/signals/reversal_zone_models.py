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

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import (
    DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH,
    DEFAULT_REVERSAL_ZONE_METRICS_CSV_PATH,
    DEFAULT_REVERSAL_ZONE_PREDICTIONS_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_REVERSAL_ZONE_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_REVERSAL_ZONE_MODELS.md"
DEFAULT_BUY_TARGET = "buy_zone_within_5pct_above_low"
DEFAULT_BUY_STRICT_TARGET = "buy_zone_within_3pct_above_low"
DEFAULT_SELL_TARGET = "sell_zone_within_5pct_below_high"
DEFAULT_SELL_STRICT_TARGET = "sell_zone_within_3pct_below_high"
MODEL_NAME = "logistic_regression_balanced"

FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "next_",
    "containing_",
    "buy_zone_",
    "sell_zone_",
    "dist_to_current_",
    "current_confirmed_",
)
FORBIDDEN_EXACT_COLUMNS: tuple[str, ...] = (
    "date",
    "row_is_in_confirmed_down_swing",
    "row_is_in_confirmed_up_swing",
)
FORBIDDEN_CONFIRMED_SWING_PRICE_COLUMNS: tuple[str, ...] = (
    "current_leg_start_price",
    "last_confirmed_pivot_price",
)
FORBIDDEN_DATE_COLUMNS: tuple[str, ...] = (
    "last_confirmed_pivot_date",
    "current_leg_start_date",
)
PREDICTION_EXPORT_COLUMNS: tuple[str, ...] = (
    "date",
    "close",
    "current_confirmed_swing_id",
    "current_confirmed_swing_direction",
    "row_is_in_confirmed_down_swing",
    "row_is_in_confirmed_up_swing",
    "dist_to_current_down_swing_low_pct",
    "dist_to_current_down_swing_low_range_frac",
    "dist_to_current_up_swing_high_pct",
    "dist_to_current_up_swing_high_range_frac",
)
TOP_BUCKETS: tuple[float, ...] = (0.05, 0.10, 0.20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the first leakage-safe buy-zone and sell-zone reversal models.",
    )
    parser.add_argument(
        "--reversal-zone-dataset-csv",
        default=str(DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_dataset.csv",
    )
    parser.add_argument("--buy-target", default=DEFAULT_BUY_TARGET)
    parser.add_argument("--buy-strict-target", default=DEFAULT_BUY_STRICT_TARGET)
    parser.add_argument("--sell-target", default=DEFAULT_SELL_TARGET)
    parser.add_argument("--sell-strict-target", default=DEFAULT_SELL_STRICT_TARGET)
    parser.add_argument(
        "--out-predictions-csv",
        default=str(DEFAULT_REVERSAL_ZONE_PREDICTIONS_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_predictions.csv",
    )
    parser.add_argument(
        "--out-metrics-csv",
        default=str(DEFAULT_REVERSAL_ZONE_METRICS_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_metrics.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_REVERSAL_ZONE_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_REVERSAL_ZONE_MODELS.md",
    )
    return parser.parse_args()


def is_forbidden_feature_column(column: str) -> bool:
    if (
        column in FORBIDDEN_EXACT_COLUMNS
        or column in FORBIDDEN_CONFIRMED_SWING_PRICE_COLUMNS
        or column in FORBIDDEN_DATE_COLUMNS
    ):
        return True
    if any(column.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return True
    return False


def build_feature_columns(columns: list[str]) -> list[str]:
    selected = [column for column in columns if not is_forbidden_feature_column(column)]
    forbidden_entered = [column for column in selected if is_forbidden_feature_column(column)]
    if forbidden_entered:
        raise ValueError(f"Leakage columns entered the feature matrix: {forbidden_entered}")
    if not selected:
        raise ValueError("Feature selection produced an empty causal feature set.")
    return selected


def validate_retained_feature_columns(feature_columns: list[str]) -> None:
    forbidden = [column for column in feature_columns if is_forbidden_feature_column(column)]
    if forbidden:
        raise ValueError(f"Forbidden columns survived feature selection: {forbidden}")


def ensure_binary_target(name: str, values: pd.Series) -> None:
    unique_values = sorted(pd.Series(values).dropna().astype(int).unique().tolist())
    if unique_values != [0, 1]:
        raise ValueError(f"{name} must contain both classes 0 and 1; got {unique_values}.")


def load_dataset(
    path: str | Path,
    buy_target: str,
    buy_strict_target: str,
    sell_target: str,
    sell_strict_target: str,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    frame = load_feature_csv(path).sort_values("date").reset_index(drop=True)
    required_columns = [
        buy_target,
        buy_strict_target,
        sell_target,
        sell_strict_target,
        "current_confirmed_swing_id",
        "current_confirmed_swing_direction",
        "dist_to_current_down_swing_low_pct",
        "dist_to_current_up_swing_high_pct",
    ]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Reversal-zone dataset is missing required columns: {missing}")

    feature_columns = build_feature_columns(frame.columns.tolist())
    working = frame.copy()
    if working.empty:
        raise ValueError("Reversal-zone dataset is empty after load.")

    has_any_feature = working.loc[:, feature_columns].notna().any(axis=1)
    working = working.loc[has_any_feature].reset_index(drop=True)
    if working.empty:
        raise ValueError("No rows remain after filtering to rows with available causal features.")
    return working, feature_columns, frame.columns.tolist()


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
        unique_count = int(non_null.nunique())
        if unique_count > 1:
            kept.append(column)
    if not kept:
        raise ValueError("All candidate causal features were constant or empty in training.")
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


def build_single_model_predictions(
    split_name: str,
    split_frame: pd.DataFrame,
    model: Pipeline,
    feature_columns: list[str],
    primary_target: str,
    strict_target: str,
    prefix: str,
) -> pd.DataFrame:
    proba = model.predict_proba(split_frame.loc[:, feature_columns])[:, 1]
    pred = (proba >= 0.50).astype(int)
    export = split_frame.loc[:, list(PREDICTION_EXPORT_COLUMNS)].copy()
    export["split"] = split_name
    export[f"{prefix}_primary_target"] = pd.to_numeric(split_frame[primary_target], errors="coerce").astype(int)
    export[f"{prefix}_strict_target"] = pd.to_numeric(split_frame[strict_target], errors="coerce").astype(int)
    export[f"{prefix}_predicted_probability"] = proba
    export[f"{prefix}_predicted_class"] = pred
    return export


def build_predictions_table(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    buy_model: Pipeline,
    sell_model: Pipeline,
    feature_columns: list[str],
    buy_target: str,
    buy_strict_target: str,
    sell_target: str,
    sell_strict_target: str,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for split_name, split_frame in (("train", train), ("validation", validation), ("test", test)):
        buy_export = build_single_model_predictions(
            split_name=split_name,
            split_frame=split_frame,
            model=buy_model,
            feature_columns=feature_columns,
            primary_target=buy_target,
            strict_target=buy_strict_target,
            prefix="buy",
        )
        sell_export = build_single_model_predictions(
            split_name=split_name,
            split_frame=split_frame,
            model=sell_model,
            feature_columns=feature_columns,
            primary_target=sell_target,
            strict_target=sell_strict_target,
            prefix="sell",
        )
        combined = buy_export.merge(
            sell_export.loc[
                :,
                [
                    "date",
                    "sell_primary_target",
                    "sell_strict_target",
                    "sell_predicted_probability",
                    "sell_predicted_class",
                ],
            ],
            on="date",
            how="inner",
            validate="one_to_one",
        )
        rows.append(combined)
    return pd.concat(rows, ignore_index=True)


def build_top_bucket_rows(
    model_label: str,
    split_name: str,
    split_frame: pd.DataFrame,
    probability_column: str,
    primary_target: str,
    strict_target: str,
    distance_column: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    ordered = split_frame.sort_values(probability_column, ascending=False).reset_index(drop=True)
    for bucket in TOP_BUCKETS:
        bucket_count = max(1, int(np.ceil(len(ordered) * bucket)))
        selected = ordered.iloc[:bucket_count].copy()
        rows.append(
            {
                "row_type": "top_bucket",
                "model": model_label,
                "split": split_name,
                "bucket": f"top_{int(bucket * 100)}pct",
                "metric": "row_count",
                "value": float(len(selected)),
            }
        )
        rows.append(
            {
                "row_type": "top_bucket",
                "model": model_label,
                "split": split_name,
                "bucket": f"top_{int(bucket * 100)}pct",
                "metric": "primary_hit_rate",
                "value": float(pd.to_numeric(selected[primary_target], errors="coerce").fillna(0).mean()),
            }
        )
        rows.append(
            {
                "row_type": "top_bucket",
                "model": model_label,
                "split": split_name,
                "bucket": f"top_{int(bucket * 100)}pct",
                "metric": "strict_hit_rate",
                "value": float(pd.to_numeric(selected[strict_target], errors="coerce").fillna(0).mean()),
            }
        )
        rows.append(
            {
                "row_type": "top_bucket",
                "model": model_label,
                "split": split_name,
                "bucket": f"top_{int(bucket * 100)}pct",
                "metric": f"avg_{distance_column}",
                "value": float(pd.to_numeric(selected[distance_column], errors="coerce").dropna().mean())
                if pd.to_numeric(selected[distance_column], errors="coerce").dropna().size
                else np.nan,
            }
        )
    return rows


def build_coefficient_rows(model_label: str, model: Pipeline) -> list[dict[str, object]]:
    preprocessor: ColumnTransformer = model.named_steps["preprocessor"]
    classifier: LogisticRegression = model.named_steps["model"]
    feature_names = preprocessor.get_feature_names_out()
    coefficients = classifier.coef_.reshape(-1)
    ranking = np.argsort(np.abs(coefficients))[::-1]

    rows: list[dict[str, object]] = []
    for rank, index in enumerate(ranking, start=1):
        rows.append(
            {
                "row_type": "coefficient",
                "model": model_label,
                "split": "train",
                "bucket": "",
                "metric": feature_names[index],
                "value": float(coefficients[index]),
                "abs_rank": rank,
            }
        )
    return rows


def build_swing_capture_rows(
    model_label: str,
    test_predictions: pd.DataFrame,
    swing_direction: str,
    probability_column: str,
    predicted_class_column: str,
    distance_column: str,
) -> list[dict[str, object]]:
    direction_frame = test_predictions.loc[
        test_predictions["current_confirmed_swing_direction"].eq(swing_direction)
        & test_predictions["current_confirmed_swing_id"].notna()
    ].copy()
    if direction_frame.empty:
        raise ValueError(f"No {swing_direction} swings are present in the test set for capture evaluation.")

    n_swings = int(direction_frame["current_confirmed_swing_id"].nunique())
    top_decile_threshold = float(direction_frame[probability_column].quantile(0.90))

    threshold_rows = direction_frame.loc[direction_frame[predicted_class_column] == 1].copy()
    top_decile_rows = direction_frame.loc[direction_frame[probability_column] >= top_decile_threshold].copy()

    threshold_swings = int(threshold_rows["current_confirmed_swing_id"].nunique())
    top_decile_swings = int(top_decile_rows["current_confirmed_swing_id"].nunique())

    first_threshold = (
        threshold_rows.sort_values("date")
        .groupby("current_confirmed_swing_id", as_index=False)
        .first()
    )
    first_top_decile = (
        top_decile_rows.sort_values("date")
        .groupby("current_confirmed_swing_id", as_index=False)
        .first()
    )

    rows = [
        {
            "row_type": "swing_capture",
            "model": model_label,
            "split": "test",
            "bucket": "threshold_0.50",
            "metric": "swing_count",
            "value": float(n_swings),
        },
        {
            "row_type": "swing_capture",
            "model": model_label,
            "split": "test",
            "bucket": "threshold_0.50",
            "metric": "captured_swings",
            "value": float(threshold_swings),
        },
        {
            "row_type": "swing_capture",
            "model": model_label,
            "split": "test",
            "bucket": "threshold_0.50",
            "metric": "swing_capture_rate",
            "value": float(threshold_swings / n_swings),
        },
        {
            "row_type": "swing_capture",
            "model": model_label,
            "split": "test",
            "bucket": "threshold_0.50",
            "metric": f"avg_first_signal_{distance_column}",
            "value": float(pd.to_numeric(first_threshold[distance_column], errors="coerce").dropna().mean())
            if not first_threshold.empty
            else np.nan,
        },
        {
            "row_type": "swing_capture",
            "model": model_label,
            "split": "test",
            "bucket": "top_10pct_score",
            "metric": "captured_swings",
            "value": float(top_decile_swings),
        },
        {
            "row_type": "swing_capture",
            "model": model_label,
            "split": "test",
            "bucket": "top_10pct_score",
            "metric": "swing_capture_rate",
            "value": float(top_decile_swings / n_swings),
        },
        {
            "row_type": "swing_capture",
            "model": model_label,
            "split": "test",
            "bucket": "top_10pct_score",
            "metric": f"avg_first_signal_{distance_column}",
            "value": float(pd.to_numeric(first_top_decile[distance_column], errors="coerce").dropna().mean())
            if not first_top_decile.empty
            else np.nan,
        },
    ]
    return rows


def build_metric_rows(
    model_label: str,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    predictions: pd.DataFrame,
    primary_target: str,
    strict_target: str,
    probability_column: str,
    predicted_class_column: str,
    distance_column: str,
    swing_direction: str,
    model: Pipeline,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for split_name, _split_frame in (("validation", validation), ("test", test)):
        split_pred = predictions.loc[predictions["split"] == split_name].copy()
        y_true = pd.to_numeric(split_pred[primary_target], errors="coerce").astype(int)
        ensure_binary_target(f"{model_label}_{split_name}", y_true)
        proba = pd.to_numeric(split_pred[probability_column], errors="coerce").to_numpy()
        pred = pd.to_numeric(split_pred[predicted_class_column], errors="coerce").astype(int).to_numpy()
        for metric_name, metric_value in compute_split_metrics(y_true, proba, pred).items():
            rows.append(
                {
                    "row_type": "split_metric",
                    "model": model_label,
                    "split": split_name,
                    "bucket": "",
                    "metric": metric_name,
                    "value": metric_value,
                }
            )
        rows.extend(
            build_top_bucket_rows(
                model_label=model_label,
                split_name=split_name,
                split_frame=split_pred,
                probability_column=probability_column,
                primary_target=primary_target,
                strict_target=strict_target,
                distance_column=distance_column,
            )
        )

    test_predictions = predictions.loc[predictions["split"] == "test"].copy()
    rows.extend(
        build_swing_capture_rows(
            model_label=model_label,
            test_predictions=test_predictions,
            swing_direction=swing_direction,
            probability_column=probability_column,
            predicted_class_column=predicted_class_column,
            distance_column=distance_column,
        )
    )
    rows.extend(build_coefficient_rows(model_label=model_label, model=model))
    return rows


def build_summary_rows(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    retained_feature_count: int,
    raw_feature_count: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "row_type": "feature_set",
            "model": "shared",
            "split": "train",
            "bucket": "",
            "metric": "raw_causal_feature_count",
            "value": float(raw_feature_count),
        },
        {
            "row_type": "feature_set",
            "model": "shared",
            "split": "train",
            "bucket": "",
            "metric": "retained_feature_count",
            "value": float(retained_feature_count),
        },
    ]
    for split_name, split_frame in (("train", train), ("validation", validation), ("test", test)):
        rows.append(
            {
                "row_type": "split_count",
                "model": "shared",
                "split": split_name,
                "bucket": "",
                "metric": "row_count",
                "value": float(len(split_frame)),
            }
        )
    return rows


def render_markdown(
    *,
    buy_target: str,
    buy_strict_target: str,
    sell_target: str,
    sell_strict_target: str,
    feature_columns: list[str],
    raw_feature_columns: list[str],
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    metrics: pd.DataFrame,
) -> str:
    def metric_value(model: str, split: str, metric: str, row_type: str = "split_metric", bucket: str = "") -> str:
        matched = metrics.loc[
            (metrics["model"] == model)
            & (metrics["split"] == split)
            & (metrics["row_type"] == row_type)
            & (metrics["metric"] == metric)
            & (metrics["bucket"].fillna("") == bucket)
        ]
        if matched.empty:
            return "n/a"
        return f"{float(matched.iloc[0]['value']):.3f}"

    def bucket_value(model: str, split: str, bucket: str, metric: str) -> str:
        return metric_value(model, split, metric, row_type="top_bucket", bucket=bucket)

    def capture_value(model: str, bucket: str, metric: str) -> str:
        return metric_value(model, "test", metric, row_type="swing_capture", bucket=bucket)

    def top_coefficients(model: str, top_n: int = 8) -> list[tuple[str, float]]:
        matched = metrics.loc[(metrics["model"] == model) & (metrics["row_type"] == "coefficient")].copy()
        if matched.empty:
            return []
        matched = matched.sort_values("abs_rank").head(top_n)
        return [(str(row["metric"]), float(row["value"])) for _, row in matched.iterrows()]

    lines = [
        "# SAFE v4.0 Reversal Zone Models",
        "",
        "## Targets",
        "",
        f"- buy primary target: `{buy_target}`",
        f"- buy stricter target: `{buy_strict_target}`",
        f"- sell primary target: `{sell_target}`",
        f"- sell stricter target: `{sell_strict_target}`",
        "",
        "## Leakage Exclusions",
        "",
        "- excluded all columns with prefixes: `next_`, `containing_`, `buy_zone_`, `sell_zone_`, `dist_to_current_`, `current_confirmed_`",
        "- excluded exact label/bookkeeping columns: `date`, `row_is_in_confirmed_down_swing`, `row_is_in_confirmed_up_swing`",
        "- excluded raw date helpers: `last_confirmed_pivot_date`, `current_leg_start_date`",
        "- excluded confirmed-pivot price helpers: `current_leg_start_price`, `last_confirmed_pivot_price`",
        f"- retained causal feature count: `{len(feature_columns)}`",
        f"- raw causal candidate count before train-constant filtering: `{len(raw_feature_columns)}`",
        "",
        "## Leakage Fix Pass",
        "",
        "- removed `current_leg_start_price` and `last_confirmed_pivot_price` from the model inputs",
        "- these fields are too close to confirmed-swing bookkeeping and make the baseline less trustworthy as a causal reversal detector",
        "- the results below should be treated as the corrected baseline for the current reversal-zone pipeline",
        "",
        "## Chronological Split",
        "",
        f"- train: `{len(train)}` rows, `{pd.to_datetime(train['date']).min().date()}` -> `{pd.to_datetime(train['date']).max().date()}`",
        f"- validation: `{len(validation)}` rows, `{pd.to_datetime(validation['date']).min().date()}` -> `{pd.to_datetime(validation['date']).max().date()}`",
        f"- test: `{len(test)}` rows, `{pd.to_datetime(test['date']).min().date()}` -> `{pd.to_datetime(test['date']).max().date()}`",
        "",
        "## Buy Model Row Metrics",
        "",
        f"- validation ROC AUC: `{metric_value('buy', 'validation', 'roc_auc')}`",
        f"- validation PR AUC: `{metric_value('buy', 'validation', 'pr_auc')}`",
        f"- validation Brier: `{metric_value('buy', 'validation', 'brier_score')}`",
        f"- validation Log loss: `{metric_value('buy', 'validation', 'log_loss')}`",
        f"- validation Precision / Recall / F1: `{metric_value('buy', 'validation', 'precision')}` / `{metric_value('buy', 'validation', 'recall')}` / `{metric_value('buy', 'validation', 'f1')}`",
        f"- test ROC AUC: `{metric_value('buy', 'test', 'roc_auc')}`",
        f"- test PR AUC: `{metric_value('buy', 'test', 'pr_auc')}`",
        f"- test Brier: `{metric_value('buy', 'test', 'brier_score')}`",
        f"- test Log loss: `{metric_value('buy', 'test', 'log_loss')}`",
        f"- test Precision / Recall / F1: `{metric_value('buy', 'test', 'precision')}` / `{metric_value('buy', 'test', 'recall')}` / `{metric_value('buy', 'test', 'f1')}`",
        "",
        "## Sell Model Row Metrics",
        "",
        f"- validation ROC AUC: `{metric_value('sell', 'validation', 'roc_auc')}`",
        f"- validation PR AUC: `{metric_value('sell', 'validation', 'pr_auc')}`",
        f"- validation Brier: `{metric_value('sell', 'validation', 'brier_score')}`",
        f"- validation Log loss: `{metric_value('sell', 'validation', 'log_loss')}`",
        f"- validation Precision / Recall / F1: `{metric_value('sell', 'validation', 'precision')}` / `{metric_value('sell', 'validation', 'recall')}` / `{metric_value('sell', 'validation', 'f1')}`",
        f"- test ROC AUC: `{metric_value('sell', 'test', 'roc_auc')}`",
        f"- test PR AUC: `{metric_value('sell', 'test', 'pr_auc')}`",
        f"- test Brier: `{metric_value('sell', 'test', 'brier_score')}`",
        f"- test Log loss: `{metric_value('sell', 'test', 'log_loss')}`",
        f"- test Precision / Recall / F1: `{metric_value('sell', 'test', 'precision')}` / `{metric_value('sell', 'test', 'recall')}` / `{metric_value('sell', 'test', 'f1')}`",
        "",
        "## Top-Bucket Quality",
        "",
        f"- buy test top 10% primary / strict hit rate: `{bucket_value('buy', 'test', 'top_10pct', 'primary_hit_rate')}` / `{bucket_value('buy', 'test', 'top_10pct', 'strict_hit_rate')}`",
        f"- buy test top 10% avg distance to low: `{bucket_value('buy', 'test', 'top_10pct', 'avg_dist_to_current_down_swing_low_pct')}`",
        f"- sell test top 10% primary / strict hit rate: `{bucket_value('sell', 'test', 'top_10pct', 'primary_hit_rate')}` / `{bucket_value('sell', 'test', 'top_10pct', 'strict_hit_rate')}`",
        f"- sell test top 10% avg distance to high: `{bucket_value('sell', 'test', 'top_10pct', 'avg_dist_to_current_up_swing_high_pct')}`",
        "",
        "## Swing-Level Capture",
        "",
        f"- buy threshold swing count / captured / rate: `{capture_value('buy', 'threshold_0.50', 'swing_count')}` / `{capture_value('buy', 'threshold_0.50', 'captured_swings')}` / `{capture_value('buy', 'threshold_0.50', 'swing_capture_rate')}`",
        f"- buy top-decile captured / rate: `{capture_value('buy', 'top_10pct_score', 'captured_swings')}` / `{capture_value('buy', 'top_10pct_score', 'swing_capture_rate')}`",
        f"- buy avg first-signal distance to low: `{capture_value('buy', 'threshold_0.50', 'avg_first_signal_dist_to_current_down_swing_low_pct')}`",
        f"- sell threshold swing count / captured / rate: `{capture_value('sell', 'threshold_0.50', 'swing_count')}` / `{capture_value('sell', 'threshold_0.50', 'captured_swings')}` / `{capture_value('sell', 'threshold_0.50', 'swing_capture_rate')}`",
        f"- sell top-decile captured / rate: `{capture_value('sell', 'top_10pct_score', 'captured_swings')}` / `{capture_value('sell', 'top_10pct_score', 'swing_capture_rate')}`",
        f"- sell avg first-signal distance to high: `{capture_value('sell', 'threshold_0.50', 'avg_first_signal_dist_to_current_up_swing_high_pct')}`",
        "",
        "## Most Important Coefficients",
        "",
    ]

    for model_label in ("buy", "sell"):
        lines.append(f"### {model_label.title()}")
        lines.append("")
        for name, coefficient in top_coefficients(model_label):
            lines.append(f"- `{name}`: `{coefficient:.4f}`")
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "- the baseline asks whether the retained causal feature surface can score good-enough reversal zones rather than exact pivots",
            "- buy and sell should be read separately because late-down-swing and late-up-swing structure are not symmetric in BTC",
            "- the 5% primary targets are the operational training targets; the 3% labels are stricter alignment checks on the same scored rows",
            "- swing capture rate matters more than row-level classification alone because later use will care about capturing many swings, not every row inside a zone",
            "- this corrected baseline should be judged more on whether swing capture and top-bucket quality remain useful after the leakage fix than on matching the earlier raw scores",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame, raw_feature_columns, _raw_columns = load_dataset(
        path=args.reversal_zone_dataset_csv,
        buy_target=args.buy_target,
        buy_strict_target=args.buy_strict_target,
        sell_target=args.sell_target,
        sell_strict_target=args.sell_strict_target,
    )
    train, validation, test = build_splits(frame)

    ensure_binary_target("buy_train", train[args.buy_target])
    ensure_binary_target("buy_validation", validation[args.buy_target])
    ensure_binary_target("buy_test", test[args.buy_target])
    ensure_binary_target("sell_train", train[args.sell_target])
    ensure_binary_target("sell_validation", validation[args.sell_target])
    ensure_binary_target("sell_test", test[args.sell_target])

    feature_columns = drop_constant_features(train, raw_feature_columns)
    validate_retained_feature_columns(feature_columns)
    train_x, validation_x, test_x, numeric_columns, categorical_columns = prepare_feature_frames(
        train=train,
        validation=validation,
        test=test,
        feature_columns=feature_columns,
    )

    buy_model = build_model(numeric_columns=numeric_columns, categorical_columns=categorical_columns)
    sell_model = build_model(numeric_columns=numeric_columns, categorical_columns=categorical_columns)
    buy_model.fit(train_x, pd.to_numeric(train[args.buy_target], errors="coerce").astype(int))
    sell_model.fit(train_x, pd.to_numeric(train[args.sell_target], errors="coerce").astype(int))

    predictions = build_predictions_table(
        train=train,
        validation=validation,
        test=test,
        buy_model=buy_model,
        sell_model=sell_model,
        feature_columns=feature_columns,
        buy_target=args.buy_target,
        buy_strict_target=args.buy_strict_target,
        sell_target=args.sell_target,
        sell_strict_target=args.sell_strict_target,
    )

    metric_rows = build_summary_rows(
        train=train,
        validation=validation,
        test=test,
        retained_feature_count=len(feature_columns),
        raw_feature_count=len(raw_feature_columns),
    )
    metric_rows.extend(
        build_metric_rows(
            model_label="buy",
            validation=validation,
            test=test,
            predictions=predictions,
            primary_target="buy_primary_target",
            strict_target="buy_strict_target",
            probability_column="buy_predicted_probability",
            predicted_class_column="buy_predicted_class",
            distance_column="dist_to_current_down_swing_low_pct",
            swing_direction="down",
            model=buy_model,
        )
    )
    metric_rows.extend(
        build_metric_rows(
            model_label="sell",
            validation=validation,
            test=test,
            predictions=predictions,
            primary_target="sell_primary_target",
            strict_target="sell_strict_target",
            probability_column="sell_predicted_probability",
            predicted_class_column="sell_predicted_class",
            distance_column="dist_to_current_up_swing_high_pct",
            swing_direction="up",
            model=sell_model,
        )
    )
    metrics = pd.DataFrame(metric_rows)

    out_predictions = Path(args.out_predictions_csv)
    out_predictions.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(out_predictions, index=False)

    out_metrics = Path(args.out_metrics_csv)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out_metrics, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        render_markdown(
            buy_target=args.buy_target,
            buy_strict_target=args.buy_strict_target,
            sell_target=args.sell_target,
            sell_strict_target=args.sell_strict_target,
            feature_columns=feature_columns,
            raw_feature_columns=raw_feature_columns,
            train=train,
            validation=validation,
            test=test,
            metrics=metrics,
        ),
        encoding="utf-8",
    )

    print(f"Wrote: {out_predictions}")
    print(f"Wrote: {out_metrics}")
    print(f"Wrote: {out_md}")
    print(f"Retained causal features: {len(feature_columns)}")
    print(f"Rows by split: train={len(train)}, validation={len(validation)}, test={len(test)}")


if __name__ == "__main__":
    main()
