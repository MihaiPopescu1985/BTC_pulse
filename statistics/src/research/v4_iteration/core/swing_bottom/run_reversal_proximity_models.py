from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import (
    DEFAULT_REVERSAL_PROXIMITY_METRICS_CSV_PATH,
    DEFAULT_REVERSAL_PROXIMITY_PREDICTIONS_CSV_PATH,
    DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_REVERSAL_PROXIMITY_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_REVERSAL_PROXIMITY_MODELS.md"
DEFAULT_BUY_TARGET = "dist_to_current_down_swing_low_pct"
DEFAULT_SELL_TARGET = "dist_to_current_up_swing_high_pct"
DEFAULT_BUY_ZONE_5 = "buy_zone_within_5pct_above_low"
DEFAULT_BUY_ZONE_3 = "buy_zone_within_3pct_above_low"
DEFAULT_SELL_ZONE_5 = "sell_zone_within_5pct_below_high"
DEFAULT_SELL_ZONE_3 = "sell_zone_within_3pct_below_high"
MODEL_NAME = "ridge_regression"
TOP_BUCKETS: tuple[float, ...] = (0.05, 0.10, 0.20)

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
    "current_leg_start_price",
    "last_confirmed_pivot_price",
)
FORBIDDEN_DATE_COLUMNS: tuple[str, ...] = (
    "last_confirmed_pivot_date",
    "current_leg_start_date",
)
PREDICTION_BASE_COLUMNS: tuple[str, ...] = (
    "date",
    "close",
    "current_confirmed_swing_id",
    "current_confirmed_swing_direction",
    "buy_zone_within_5pct_above_low",
    "buy_zone_within_3pct_above_low",
    "sell_zone_within_5pct_below_high",
    "sell_zone_within_3pct_below_high",
    "dist_to_current_down_swing_low_pct",
    "dist_to_current_up_swing_high_pct",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train leakage-safe continuous reversal proximity models for swing lows and highs.",
    )
    parser.add_argument(
        "--reversal-zone-dataset-csv",
        default=str(DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_dataset.csv",
    )
    parser.add_argument("--buy-target", default=DEFAULT_BUY_TARGET)
    parser.add_argument("--sell-target", default=DEFAULT_SELL_TARGET)
    parser.add_argument(
        "--out-predictions-csv",
        default=str(DEFAULT_REVERSAL_PROXIMITY_PREDICTIONS_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_proximity_predictions.csv",
    )
    parser.add_argument(
        "--out-metrics-csv",
        default=str(DEFAULT_REVERSAL_PROXIMITY_METRICS_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_proximity_metrics.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_REVERSAL_PROXIMITY_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_REVERSAL_PROXIMITY_MODELS.md",
    )
    return parser.parse_args()


def is_forbidden_feature_column(column: str) -> bool:
    if column in FORBIDDEN_EXACT_COLUMNS or column in FORBIDDEN_DATE_COLUMNS:
        return True
    if any(column.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return True
    return False


def build_feature_columns(columns: list[str]) -> list[str]:
    selected = [column for column in columns if not is_forbidden_feature_column(column)]
    if not selected:
        raise ValueError("Feature selection produced an empty causal feature set.")
    return selected


def validate_retained_feature_columns(feature_columns: list[str]) -> None:
    forbidden = [column for column in feature_columns if is_forbidden_feature_column(column)]
    if forbidden:
        raise ValueError(f"Forbidden columns survived feature selection: {forbidden}")


def load_dataset(path: str | Path, buy_target: str, sell_target: str) -> tuple[pd.DataFrame, list[str]]:
    frame = load_feature_csv(path).sort_values("date").reset_index(drop=True)
    required_columns = [
        buy_target,
        sell_target,
        "row_is_in_confirmed_down_swing",
        "row_is_in_confirmed_up_swing",
        "current_confirmed_swing_id",
        "current_confirmed_swing_direction",
        DEFAULT_BUY_ZONE_5,
        DEFAULT_BUY_ZONE_3,
        DEFAULT_SELL_ZONE_5,
        DEFAULT_SELL_ZONE_3,
    ]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Reversal-zone dataset is missing required columns: {missing}")
    feature_columns = build_feature_columns(frame.columns.tolist())
    validate_retained_feature_columns(feature_columns)
    return frame, feature_columns


def filter_side_rows(frame: pd.DataFrame, side: str, target_column: str) -> pd.DataFrame:
    if side == "buy":
        filtered = frame.loc[
            frame["row_is_in_confirmed_down_swing"].eq(1) & pd.to_numeric(frame[target_column], errors="coerce").notna()
        ].copy()
    elif side == "sell":
        filtered = frame.loc[
            frame["row_is_in_confirmed_up_swing"].eq(1) & pd.to_numeric(frame[target_column], errors="coerce").notna()
        ].copy()
    else:
        raise ValueError(f"Unknown side: {side}")
    if filtered.empty:
        raise ValueError(f"No rows available for {side} proximity modeling.")
    return filtered.sort_values("date").reset_index(drop=True)


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
        if int(non_null.nunique()) > 1:
            kept.append(column)
    if not kept:
        raise ValueError("All candidate causal features were constant or empty in training.")
    validate_retained_feature_columns(kept)
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
            ("model", Ridge(alpha=1.0, random_state=0)),
        ]
    )


def compute_regression_metrics(y_true: pd.Series, pred: np.ndarray) -> dict[str, float]:
    true_series = pd.Series(pd.to_numeric(y_true, errors="coerce").to_numpy())
    pred_series = pd.Series(pd.to_numeric(pred, errors="coerce"))
    return {
        "mae": float(mean_absolute_error(true_series, pred_series)),
        "rmse": float(np.sqrt(mean_squared_error(true_series, pred_series))),
        "r2": float(r2_score(true_series, pred_series)),
        "spearman": float(true_series.corr(pred_series, method="spearman")),
        "pearson": float(true_series.corr(pred_series, method="pearson")),
    }


def build_side_predictions(
    split_name: str,
    split_frame: pd.DataFrame,
    model: Pipeline,
    feature_columns: list[str],
    target_column: str,
    side: str,
) -> pd.DataFrame:
    pred = model.predict(split_frame.loc[:, feature_columns])
    export = split_frame.loc[:, list(PREDICTION_BASE_COLUMNS)].copy()
    export[f"{side}_split"] = split_name
    export[f"true_{side}_distance"] = pd.to_numeric(split_frame[target_column], errors="coerce")
    export[f"predicted_{side}_distance"] = pred
    return export


def build_predictions_table(
    frame: pd.DataFrame,
    buy_splits: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    sell_splits: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    buy_model: Pipeline,
    sell_model: Pipeline,
    buy_feature_columns: list[str],
    sell_feature_columns: list[str],
    buy_target: str,
    sell_target: str,
) -> pd.DataFrame:
    export = frame.loc[:, list(PREDICTION_BASE_COLUMNS)].copy()
    export["buy_split"] = pd.Series(pd.NA, index=export.index, dtype="object")
    export["sell_split"] = pd.Series(pd.NA, index=export.index, dtype="object")
    export["true_buy_distance"] = np.nan
    export["predicted_buy_distance"] = np.nan
    export["true_sell_distance"] = np.nan
    export["predicted_sell_distance"] = np.nan

    for split_name, split_frame in zip(("train", "validation", "test"), buy_splits):
        side_export = build_side_predictions(split_name, split_frame, buy_model, buy_feature_columns, buy_target, "buy")
        merged = export.loc[:, ["date"]].merge(
            side_export.loc[:, ["date", "buy_split", "true_buy_distance", "predicted_buy_distance"]],
            on="date",
            how="left",
            validate="one_to_one",
        )
        export["buy_split"] = export["buy_split"].combine_first(merged["buy_split"])
        export["true_buy_distance"] = export["true_buy_distance"].combine_first(merged["true_buy_distance"])
        export["predicted_buy_distance"] = export["predicted_buy_distance"].combine_first(merged["predicted_buy_distance"])

    for split_name, split_frame in zip(("train", "validation", "test"), sell_splits):
        side_export = build_side_predictions(split_name, split_frame, sell_model, sell_feature_columns, sell_target, "sell")
        merged = export.loc[:, ["date"]].merge(
            side_export.loc[:, ["date", "sell_split", "true_sell_distance", "predicted_sell_distance"]],
            on="date",
            how="left",
            validate="one_to_one",
        )
        export["sell_split"] = export["sell_split"].combine_first(merged["sell_split"])
        export["true_sell_distance"] = export["true_sell_distance"].combine_first(merged["true_sell_distance"])
        export["predicted_sell_distance"] = export["predicted_sell_distance"].combine_first(merged["predicted_sell_distance"])

    return export.sort_values("date").reset_index(drop=True)


def build_split_metric_rows(model_label: str, split_name: str, y_true: pd.Series, pred: np.ndarray) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for metric_name, metric_value in compute_regression_metrics(y_true, pred).items():
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
    return rows


def build_top_bucket_rows(
    model_label: str,
    split_name: str,
    split_frame: pd.DataFrame,
    predicted_column: str,
    true_distance_column: str,
    zone_5_column: str,
    zone_3_column: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    ordered = split_frame.sort_values(predicted_column, ascending=True).reset_index(drop=True)
    for bucket in TOP_BUCKETS:
        bucket_count = max(1, int(np.ceil(len(ordered) * bucket)))
        selected = ordered.iloc[:bucket_count].copy()
        bucket_name = f"top_{int(bucket * 100)}pct"
        rows.extend(
            [
                {
                    "row_type": "top_bucket",
                    "model": model_label,
                    "split": split_name,
                    "bucket": bucket_name,
                    "metric": "row_count",
                    "value": float(len(selected)),
                },
                {
                    "row_type": "top_bucket",
                    "model": model_label,
                    "split": split_name,
                    "bucket": bucket_name,
                    "metric": "avg_true_distance",
                    "value": float(pd.to_numeric(selected[true_distance_column], errors="coerce").mean()),
                },
                {
                    "row_type": "top_bucket",
                    "model": model_label,
                    "split": split_name,
                    "bucket": bucket_name,
                    "metric": "median_true_distance",
                    "value": float(pd.to_numeric(selected[true_distance_column], errors="coerce").median()),
                },
                {
                    "row_type": "top_bucket",
                    "model": model_label,
                    "split": split_name,
                    "bucket": bucket_name,
                    "metric": "zone_5_hit_rate",
                    "value": float(pd.to_numeric(selected[zone_5_column], errors="coerce").fillna(0).mean()),
                },
                {
                    "row_type": "top_bucket",
                    "model": model_label,
                    "split": split_name,
                    "bucket": bucket_name,
                    "metric": "zone_3_hit_rate",
                    "value": float(pd.to_numeric(selected[zone_3_column], errors="coerce").fillna(0).mean()),
                },
            ]
        )
    return rows


def build_best_pick_rows(
    model_label: str,
    test_predictions: pd.DataFrame,
    predicted_column: str,
    true_distance_column: str,
    zone_5_column: str,
    zone_3_column: str,
) -> list[dict[str, object]]:
    swing_rows = test_predictions.loc[test_predictions["current_confirmed_swing_id"].notna()].copy()
    if swing_rows.empty:
        raise ValueError(f"No swings available for {model_label} best-pick evaluation.")
    best_per_swing = (
        swing_rows.sort_values([predicted_column, "date"], ascending=[True, True])
        .groupby("current_confirmed_swing_id", as_index=False)
        .first()
    )
    n_swings = int(best_per_swing["current_confirmed_swing_id"].nunique())
    return [
        {
            "row_type": "swing_best_pick",
            "model": model_label,
            "split": "test",
            "bucket": "best_per_swing",
            "metric": "swing_count",
            "value": float(n_swings),
        },
        {
            "row_type": "swing_best_pick",
            "model": model_label,
            "split": "test",
            "bucket": "best_per_swing",
            "metric": "avg_true_distance",
            "value": float(pd.to_numeric(best_per_swing[true_distance_column], errors="coerce").mean()),
        },
        {
            "row_type": "swing_best_pick",
            "model": model_label,
            "split": "test",
            "bucket": "best_per_swing",
            "metric": "median_true_distance",
            "value": float(pd.to_numeric(best_per_swing[true_distance_column], errors="coerce").median()),
        },
        {
            "row_type": "swing_best_pick",
            "model": model_label,
            "split": "test",
            "bucket": "best_per_swing",
            "metric": "zone_5_hit_rate",
            "value": float(pd.to_numeric(best_per_swing[zone_5_column], errors="coerce").fillna(0).mean()),
        },
        {
            "row_type": "swing_best_pick",
            "model": model_label,
            "split": "test",
            "bucket": "best_per_swing",
            "metric": "zone_3_hit_rate",
            "value": float(pd.to_numeric(best_per_swing[zone_3_column], errors="coerce").fillna(0).mean()),
        },
    ]


def build_coefficient_rows(model_label: str, model: Pipeline) -> list[dict[str, object]]:
    preprocessor: ColumnTransformer = model.named_steps["preprocessor"]
    regressor: Ridge = model.named_steps["model"]
    feature_names = preprocessor.get_feature_names_out()
    coefficients = regressor.coef_.reshape(-1)
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


def build_side_metric_rows(
    *,
    model_label: str,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    predictions: pd.DataFrame,
    target_column: str,
    predicted_column: str,
    zone_5_column: str,
    zone_3_column: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for split_name, split_frame in (("validation", validation), ("test", test)):
        split_pred = predictions.loc[predictions[f"{model_label}_split"] == split_name].copy()
        y_true = pd.to_numeric(split_pred[target_column], errors="coerce")
        pred = pd.to_numeric(split_pred[predicted_column], errors="coerce").to_numpy()
        rows.extend(build_split_metric_rows(model_label, split_name, y_true, pred))
        rows.extend(
            build_top_bucket_rows(
                model_label=model_label,
                split_name=split_name,
                split_frame=split_pred,
                predicted_column=predicted_column,
                true_distance_column=target_column,
                zone_5_column=zone_5_column,
                zone_3_column=zone_3_column,
            )
        )

    test_pred = predictions.loc[predictions[f"{model_label}_split"] == "test"].copy()
    rows.extend(
        build_best_pick_rows(
            model_label=model_label,
            test_predictions=test_pred,
            predicted_column=predicted_column,
            true_distance_column=target_column,
            zone_5_column=zone_5_column,
            zone_3_column=zone_3_column,
        )
    )
    return rows


def build_summary_rows(
    *,
    buy_feature_count: int,
    sell_feature_count: int,
    buy_train: pd.DataFrame,
    buy_validation: pd.DataFrame,
    buy_test: pd.DataFrame,
    sell_train: pd.DataFrame,
    sell_validation: pd.DataFrame,
    sell_test: pd.DataFrame,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"row_type": "feature_set", "model": "buy", "split": "train", "bucket": "", "metric": "retained_feature_count", "value": float(buy_feature_count)},
        {"row_type": "feature_set", "model": "sell", "split": "train", "bucket": "", "metric": "retained_feature_count", "value": float(sell_feature_count)},
    ]
    for model_label, splits in (
        ("buy", (buy_train, buy_validation, buy_test)),
        ("sell", (sell_train, sell_validation, sell_test)),
    ):
        for split_name, split_frame in zip(("train", "validation", "test"), splits):
            rows.append(
                {
                    "row_type": "split_count",
                    "model": model_label,
                    "split": split_name,
                    "bucket": "",
                    "metric": "row_count",
                    "value": float(len(split_frame)),
                }
            )
    return rows


def render_markdown(
    *,
    buy_train: pd.DataFrame,
    buy_validation: pd.DataFrame,
    buy_test: pd.DataFrame,
    sell_train: pd.DataFrame,
    sell_validation: pd.DataFrame,
    sell_test: pd.DataFrame,
    buy_features: list[str],
    sell_features: list[str],
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

    def top_coefficients(model: str, top_n: int = 8) -> list[tuple[str, float]]:
        matched = metrics.loc[(metrics["model"] == model) & (metrics["row_type"] == "coefficient")].copy()
        if matched.empty:
            return []
        matched = matched.sort_values("abs_rank").head(top_n)
        return [(str(row["metric"]), float(row["value"])) for _, row in matched.iterrows()]

    lines = [
        "# SAFE v4.0 Reversal Proximity Models",
        "",
        "## Targets",
        "",
        f"- buy target: `{DEFAULT_BUY_TARGET}`",
        f"- sell target: `{DEFAULT_SELL_TARGET}`",
        "",
        "## Leakage Exclusions",
        "",
        "- excluded all columns with prefixes: `next_`, `containing_`, `buy_zone_`, `sell_zone_`, `dist_to_current_`, `current_confirmed_`",
        "- excluded confirmed-pivot helpers: `current_leg_start_price`, `last_confirmed_pivot_price`, `last_confirmed_pivot_date`, `current_leg_start_date`",
        "- retained only causal price, on-chain, regime/hazard, and live swing-state fields",
        "",
        "## Filtered Sample Sizes",
        "",
        f"- buy rows: `{len(buy_train) + len(buy_validation) + len(buy_test)}`",
        f"- buy train: `{len(buy_train)}` rows, `{pd.to_datetime(buy_train['date']).min().date()}` -> `{pd.to_datetime(buy_train['date']).max().date()}`",
        f"- buy validation: `{len(buy_validation)}` rows, `{pd.to_datetime(buy_validation['date']).min().date()}` -> `{pd.to_datetime(buy_validation['date']).max().date()}`",
        f"- buy test: `{len(buy_test)}` rows, `{pd.to_datetime(buy_test['date']).min().date()}` -> `{pd.to_datetime(buy_test['date']).max().date()}`",
        f"- sell rows: `{len(sell_train) + len(sell_validation) + len(sell_test)}`",
        f"- sell train: `{len(sell_train)}` rows, `{pd.to_datetime(sell_train['date']).min().date()}` -> `{pd.to_datetime(sell_train['date']).max().date()}`",
        f"- sell validation: `{len(sell_validation)}` rows, `{pd.to_datetime(sell_validation['date']).min().date()}` -> `{pd.to_datetime(sell_validation['date']).max().date()}`",
        f"- sell test: `{len(sell_test)}` rows, `{pd.to_datetime(sell_test['date']).min().date()}` -> `{pd.to_datetime(sell_test['date']).max().date()}`",
        f"- buy retained causal feature count: `{len(buy_features)}`",
        f"- sell retained causal feature count: `{len(sell_features)}`",
        "",
        "## Regression Metrics",
        "",
        f"- buy validation MAE / RMSE / R² / Spearman / Pearson: `{metric_value('buy', 'validation', 'mae')}` / `{metric_value('buy', 'validation', 'rmse')}` / `{metric_value('buy', 'validation', 'r2')}` / `{metric_value('buy', 'validation', 'spearman')}` / `{metric_value('buy', 'validation', 'pearson')}`",
        f"- buy test MAE / RMSE / R² / Spearman / Pearson: `{metric_value('buy', 'test', 'mae')}` / `{metric_value('buy', 'test', 'rmse')}` / `{metric_value('buy', 'test', 'r2')}` / `{metric_value('buy', 'test', 'spearman')}` / `{metric_value('buy', 'test', 'pearson')}`",
        f"- sell validation MAE / RMSE / R² / Spearman / Pearson: `{metric_value('sell', 'validation', 'mae')}` / `{metric_value('sell', 'validation', 'rmse')}` / `{metric_value('sell', 'validation', 'r2')}` / `{metric_value('sell', 'validation', 'spearman')}` / `{metric_value('sell', 'validation', 'pearson')}`",
        f"- sell test MAE / RMSE / R² / Spearman / Pearson: `{metric_value('sell', 'test', 'mae')}` / `{metric_value('sell', 'test', 'rmse')}` / `{metric_value('sell', 'test', 'r2')}` / `{metric_value('sell', 'test', 'spearman')}` / `{metric_value('sell', 'test', 'pearson')}`",
        "",
        "## Top-Bucket Ranking Quality",
        "",
        f"- buy test top 10% avg / median distance: `{metric_value('buy', 'test', 'avg_true_distance', row_type='top_bucket', bucket='top_10pct')}` / `{metric_value('buy', 'test', 'median_true_distance', row_type='top_bucket', bucket='top_10pct')}`",
        f"- buy test top 10% zone 5% / 3% hit rate: `{metric_value('buy', 'test', 'zone_5_hit_rate', row_type='top_bucket', bucket='top_10pct')}` / `{metric_value('buy', 'test', 'zone_3_hit_rate', row_type='top_bucket', bucket='top_10pct')}`",
        f"- sell test top 10% avg / median distance: `{metric_value('sell', 'test', 'avg_true_distance', row_type='top_bucket', bucket='top_10pct')}` / `{metric_value('sell', 'test', 'median_true_distance', row_type='top_bucket', bucket='top_10pct')}`",
        f"- sell test top 10% zone 5% / 3% hit rate: `{metric_value('sell', 'test', 'zone_5_hit_rate', row_type='top_bucket', bucket='top_10pct')}` / `{metric_value('sell', 'test', 'zone_3_hit_rate', row_type='top_bucket', bucket='top_10pct')}`",
        "",
        "## Per-Swing Best Pick",
        "",
        f"- buy swings in test: `{metric_value('buy', 'test', 'swing_count', row_type='swing_best_pick', bucket='best_per_swing')}`",
        f"- buy best-pick avg / median distance: `{metric_value('buy', 'test', 'avg_true_distance', row_type='swing_best_pick', bucket='best_per_swing')}` / `{metric_value('buy', 'test', 'median_true_distance', row_type='swing_best_pick', bucket='best_per_swing')}`",
        f"- buy best-pick within 5% / 3%: `{metric_value('buy', 'test', 'zone_5_hit_rate', row_type='swing_best_pick', bucket='best_per_swing')}` / `{metric_value('buy', 'test', 'zone_3_hit_rate', row_type='swing_best_pick', bucket='best_per_swing')}`",
        f"- sell swings in test: `{metric_value('sell', 'test', 'swing_count', row_type='swing_best_pick', bucket='best_per_swing')}`",
        f"- sell best-pick avg / median distance: `{metric_value('sell', 'test', 'avg_true_distance', row_type='swing_best_pick', bucket='best_per_swing')}` / `{metric_value('sell', 'test', 'median_true_distance', row_type='swing_best_pick', bucket='best_per_swing')}`",
        f"- sell best-pick within 5% / 3%: `{metric_value('sell', 'test', 'zone_5_hit_rate', row_type='swing_best_pick', bucket='best_per_swing')}` / `{metric_value('sell', 'test', 'zone_3_hit_rate', row_type='swing_best_pick', bucket='best_per_swing')}`",
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
            "- this step asks whether continuous distance targets improve point selection inside already-known swing types",
            "- better top-bucket distance and better best-per-swing picks matter more than broad row coverage here",
            "- if best-per-swing distance improves materially relative to the binary zone baseline, the system is learning intra-swing ranking rather than only broad phase detection",
            "- the next step should depend on whether ranking quality is limited mainly by the objective, the feature surface, or the simple linear model",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame, shared_feature_columns = load_dataset(args.reversal_zone_dataset_csv, args.buy_target, args.sell_target)

    buy_frame = filter_side_rows(frame, "buy", args.buy_target)
    sell_frame = filter_side_rows(frame, "sell", args.sell_target)
    buy_train, buy_validation, buy_test = build_splits(buy_frame)
    sell_train, sell_validation, sell_test = build_splits(sell_frame)

    buy_feature_columns = drop_constant_features(buy_train, shared_feature_columns)
    sell_feature_columns = drop_constant_features(sell_train, shared_feature_columns)

    buy_train_x, buy_validation_x, buy_test_x, buy_numeric, buy_categorical = prepare_feature_frames(
        buy_train, buy_validation, buy_test, buy_feature_columns
    )
    sell_train_x, sell_validation_x, sell_test_x, sell_numeric, sell_categorical = prepare_feature_frames(
        sell_train, sell_validation, sell_test, sell_feature_columns
    )

    buy_model = build_model(buy_numeric, buy_categorical)
    sell_model = build_model(sell_numeric, sell_categorical)
    buy_model.fit(buy_train_x, pd.to_numeric(buy_train[args.buy_target], errors="coerce"))
    sell_model.fit(sell_train_x, pd.to_numeric(sell_train[args.sell_target], errors="coerce"))

    predictions = build_predictions_table(
        frame=frame,
        buy_splits=(buy_train, buy_validation, buy_test),
        sell_splits=(sell_train, sell_validation, sell_test),
        buy_model=buy_model,
        sell_model=sell_model,
        buy_feature_columns=buy_feature_columns,
        sell_feature_columns=sell_feature_columns,
        buy_target=args.buy_target,
        sell_target=args.sell_target,
    )

    metric_rows = build_summary_rows(
        buy_feature_count=len(buy_feature_columns),
        sell_feature_count=len(sell_feature_columns),
        buy_train=buy_train,
        buy_validation=buy_validation,
        buy_test=buy_test,
        sell_train=sell_train,
        sell_validation=sell_validation,
        sell_test=sell_test,
    )
    metric_rows.extend(
        build_side_metric_rows(
            model_label="buy",
            validation=buy_validation,
            test=buy_test,
            predictions=predictions,
            target_column="true_buy_distance",
            predicted_column="predicted_buy_distance",
            zone_5_column=DEFAULT_BUY_ZONE_5,
            zone_3_column=DEFAULT_BUY_ZONE_3,
        )
    )
    metric_rows.extend(build_coefficient_rows("buy", buy_model))
    metric_rows.extend(
        build_side_metric_rows(
            model_label="sell",
            validation=sell_validation,
            test=sell_test,
            predictions=predictions,
            target_column="true_sell_distance",
            predicted_column="predicted_sell_distance",
            zone_5_column=DEFAULT_SELL_ZONE_5,
            zone_3_column=DEFAULT_SELL_ZONE_3,
        )
    )
    metric_rows.extend(build_coefficient_rows("sell", sell_model))
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
            buy_train=buy_train,
            buy_validation=buy_validation,
            buy_test=buy_test,
            sell_train=sell_train,
            sell_validation=sell_validation,
            sell_test=sell_test,
            buy_features=buy_feature_columns,
            sell_features=sell_feature_columns,
            metrics=metrics,
        ),
        encoding="utf-8",
    )

    print(f"Wrote: {out_predictions}")
    print(f"Wrote: {out_metrics}")
    print(f"Wrote: {out_md}")
    print(f"Buy rows by split: train={len(buy_train)}, validation={len(buy_validation)}, test={len(buy_test)}")
    print(f"Sell rows by split: train={len(sell_train)}, validation={len(sell_validation)}, test={len(sell_test)}")
    print(f"Retained causal features: buy={len(buy_feature_columns)}, sell={len(sell_feature_columns)}")


if __name__ == "__main__":
    main()
