from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import pandas as pd

from src.data.loaders import load_daily_price_json
from src.models.path_classifier import (
    FEATURE_GROUPS,
    PATH_CLASSIFIER_FEATURES,
    PathClassifierDataset,
    available_feature_columns,
    build_base_estimator,
    feature_importance_frame,
    fit_probabilistic_model,
    generate_walk_forward_folds,
    load_combined_feature_frame,
    save_model_pack,
    load_model_pack,
)


FirstTouchLabel = Literal["UP_FIRST", "DOWN_FIRST", "NONE"]
FirstTouchAmbiguityMode = Literal["pessimistic", "optimistic", "skip_ambiguous"]
FIRST_TOUCH_LABELS: tuple[FirstTouchLabel, ...] = ("UP_FIRST", "DOWN_FIRST", "NONE")


@dataclass(frozen=True)
class RealizedFirstTouchOutcome:
    label: str | None
    ambiguous: bool
    ambiguity_type: str | None
    first_upper_day: int | None
    first_lower_day: int | None
    upper_barrier: float
    lower_barrier: float
    forward_return: float | None


def realized_first_touch_outcome_from_ohlc(
    price_frame: pd.DataFrame,
    anchor_date: str,
    *,
    days: int = 2,
    up_pct: float = 0.02,
    down_pct: float = 0.02,
    ambiguity_mode: FirstTouchAmbiguityMode = "skip_ambiguous",
) -> RealizedFirstTouchOutcome:
    """Determine whether the upper or lower barrier is touched first over the next H days.

    Features always come from anchor date ``t``. The label is built only from
    future OHLC candles ``t+1 ... t+H``. If the first future candle to touch a
    barrier touches both upper and lower on the same day, daily data cannot
    determine intraday order. The chosen ambiguity mode controls resolution:

    - ``pessimistic`` -> label as ``DOWN_FIRST``
    - ``optimistic`` -> label as ``UP_FIRST``
    - ``skip_ambiguous`` -> return ``label=None``
    """
    if days <= 0:
        raise ValueError("days must be positive.")
    if up_pct <= 0.0 or down_pct <= 0.0:
        raise ValueError("up_pct and down_pct must be strictly positive.")
    if ambiguity_mode not in {"pessimistic", "optimistic", "skip_ambiguous"}:
        raise ValueError(f"Unsupported ambiguity_mode: {ambiguity_mode}")

    frame = price_frame.sort_index().copy()
    anchor_ts = pd.Timestamp(anchor_date)
    if anchor_ts not in frame.index:
        raise KeyError(f"Anchor date {anchor_date} not found in price data.")

    anchor_position = int(frame.index.get_loc(anchor_ts))
    future = frame.iloc[anchor_position + 1 : anchor_position + 1 + days]
    if len(future) < days:
        raise ValueError(
            f"Not enough future rows after {anchor_date} for a {days}-day first-touch label."
        )

    anchor_close = float(frame.loc[anchor_ts, "close"])
    upper_barrier = anchor_close * (1.0 + up_pct)
    lower_barrier = anchor_close * (1.0 - down_pct)

    first_upper_day: int | None = None
    first_lower_day: int | None = None
    ambiguous = False
    ambiguity_type: str | None = None

    for day_offset, row in enumerate(future.itertuples(index=False), start=1):
        up_hit = float(row.high) >= upper_barrier
        down_hit = float(row.low) <= lower_barrier

        if up_hit and down_hit and first_upper_day is None and first_lower_day is None:
            ambiguous = True
            ambiguity_type = "both_barriers_first_touched_same_day"
            if ambiguity_mode == "skip_ambiguous":
                return RealizedFirstTouchOutcome(
                    label=None,
                    ambiguous=True,
                    ambiguity_type=ambiguity_type,
                    first_upper_day=day_offset,
                    first_lower_day=day_offset,
                    upper_barrier=upper_barrier,
                    lower_barrier=lower_barrier,
                    forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
                )
            return RealizedFirstTouchOutcome(
                label="UP_FIRST" if ambiguity_mode == "optimistic" else "DOWN_FIRST",
                ambiguous=True,
                ambiguity_type=ambiguity_type,
                first_upper_day=day_offset,
                first_lower_day=day_offset,
                upper_barrier=upper_barrier,
                lower_barrier=lower_barrier,
                forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
            )

        if up_hit and first_upper_day is None:
            first_upper_day = day_offset
        if down_hit and first_lower_day is None:
            first_lower_day = day_offset

        if first_upper_day is not None or first_lower_day is not None:
            break

    if first_upper_day is None and first_lower_day is None:
        label: str | None = "NONE"
    elif first_upper_day is not None and first_lower_day is None:
        label = "UP_FIRST"
    elif first_upper_day is None and first_lower_day is not None:
        label = "DOWN_FIRST"
    else:
        label = "UP_FIRST" if first_upper_day <= first_lower_day else "DOWN_FIRST"

    return RealizedFirstTouchOutcome(
        label=label,
        ambiguous=ambiguous,
        ambiguity_type=ambiguity_type,
        first_upper_day=first_upper_day,
        first_lower_day=first_lower_day,
        upper_barrier=upper_barrier,
        lower_barrier=lower_barrier,
        forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
    )


def build_first_touch_classifier_dataset(
    price_json_path: str | Path,
    features_json_path: str | Path,
    *,
    onchain_features_json_path: str | Path | None = None,
    days: int = 2,
    up_pct: float = 0.02,
    down_pct: float = 0.02,
    ambiguity_mode: FirstTouchAmbiguityMode = "skip_ambiguous",
    min_feature_coverage: float = 0.5,
) -> PathClassifierDataset:
    """Build a supervised dataset with SAFE state at t and first-touch target over t+1..t+H."""
    if not 0.0 < min_feature_coverage <= 1.0:
        raise ValueError("min_feature_coverage must be in (0, 1].")

    price_frame = load_daily_price_json(str(price_json_path))
    feature_frame = load_combined_feature_frame(
        features_json_path,
        onchain_features_json_path=onchain_features_json_path,
    )
    feature_cols = available_feature_columns(feature_frame)
    if not feature_cols:
        raise ValueError("No supported classifier features are available in the feature frame.")

    rows: list[pd.Series] = []
    labels: list[str] = []
    meta_rows: list[dict[str, Any]] = []

    common_dates = sorted(set(feature_frame.index) & set(price_frame.index.strftime("%Y-%m-%d")))
    for anchor_date in common_dates:
        feature_row = feature_frame.loc[anchor_date, feature_cols]
        if float(feature_row.notna().mean()) < min_feature_coverage:
            continue

        try:
            realized = realized_first_touch_outcome_from_ohlc(
                price_frame,
                anchor_date,
                days=days,
                up_pct=up_pct,
                down_pct=down_pct,
                ambiguity_mode=ambiguity_mode,
            )
        except ValueError:
            continue

        if realized.label is None:
            continue

        rows.append(feature_row)
        labels.append(realized.label)
        meta_rows.append(
            {
                "anchor_date": anchor_date,
                "anchor_close": float(price_frame.loc[pd.Timestamp(anchor_date), "close"]),
                "realized_label": realized.label,
                "realized_forward_return": realized.forward_return,
                "ambiguous_realized": int(realized.ambiguous),
                "ambiguity_type": realized.ambiguity_type,
                "first_upper_day": realized.first_upper_day,
                "first_lower_day": realized.first_lower_day,
                "feature_coverage": float(feature_row.notna().mean()),
                "upper_barrier": realized.upper_barrier,
                "lower_barrier": realized.lower_barrier,
            }
        )

    if not rows:
        raise ValueError("No labeled rows available for first-touch classifier training.")

    X = pd.DataFrame(rows, columns=feature_cols)
    X.index = pd.Index([row["anchor_date"] for row in meta_rows], name="anchor_date")
    y = pd.Series(labels, index=X.index, name="first_touch_label")
    meta = pd.DataFrame(meta_rows).set_index("anchor_date")
    return PathClassifierDataset(features=X, labels=y, meta=meta, feature_cols=feature_cols)


def save_first_touch_model_pack(
    path: Path,
    *,
    model: Any,
    feature_cols: list[str],
    model_type: Literal["gbt", "rf", "logreg"],
    days: int,
    up_pct: float,
    down_pct: float,
    ambiguity_mode: FirstTouchAmbiguityMode,
    train_rows: int,
) -> None:
    """Persist a first-touch classifier pack with an explicit 3-class output contract."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_cols": feature_cols,
            "feature_groups": {feature: FEATURE_GROUPS.get(feature, "other") for feature in feature_cols},
            "model_type": model_type,
            "days": days,
            "up_pct": up_pct,
            "down_pct": down_pct,
            "ambiguity_mode": ambiguity_mode,
            "classes": list(FIRST_TOUCH_LABELS),
            "model_classes": [str(label) for label in getattr(model, "classes_", list(FIRST_TOUCH_LABELS))],
            "train_rows": train_rows,
        },
        path,
    )


def predict_first_touch_probabilities_for_date(
    model_pack: dict[str, Any],
    *,
    features_json_path: str | Path,
    price_json_path: str | Path,
    date: str,
    onchain_features_json_path: str | Path | None = None,
) -> dict[str, Any]:
    """Predict short-horizon first-touch class probabilities for one anchor date."""
    feature_frame = load_combined_feature_frame(
        features_json_path,
        onchain_features_json_path=onchain_features_json_path,
    )
    if date not in feature_frame.index:
        raise KeyError(f"Anchor date {date} not found in feature data.")

    feature_cols = list(model_pack["feature_cols"])
    missing = [column for column in feature_cols if column not in feature_frame.columns]
    if missing:
        raise ValueError(f"Feature frame is missing required model columns: {missing}")

    X_row = feature_frame.loc[[date], feature_cols]
    probabilities = model_pack["model"].predict_proba(X_row)[0]
    classes = list(model_pack.get("classes", FIRST_TOUCH_LABELS))
    model_classes = list(model_pack.get("model_classes", classes))
    probability_map = {label: 0.0 for label in classes}
    for label, prob in zip(model_classes, probabilities):
        probability_map[str(label)] = float(prob)

    price_frame = load_daily_price_json(str(price_json_path))
    anchor_close = float(price_frame.loc[pd.Timestamp(date), "close"])
    top1 = max(probability_map, key=probability_map.get)
    top2 = sorted(probability_map, key=probability_map.get, reverse=True)[:2]

    return {
        "anchor_date": date,
        "anchor_close": anchor_close,
        "days": int(model_pack["days"]),
        "barriers": {
            "up_pct": float(model_pack["up_pct"]),
            "down_pct": float(model_pack["down_pct"]),
            "upper_price": anchor_close * (1.0 + float(model_pack["up_pct"])),
            "lower_price": anchor_close * (1.0 - float(model_pack["down_pct"])),
        },
        "probabilities": probability_map,
        "top1_class": top1,
        "top2_classes": top2,
        "feature_snapshot": {
            column: (None if pd.isna(value) else float(value))
            for column, value in X_row.iloc[0].items()
        },
        "model_type": model_pack["model_type"],
    }


__all__ = [
    "FIRST_TOUCH_LABELS",
    "FEATURE_GROUPS",
    "PATH_CLASSIFIER_FEATURES",
    "PathClassifierDataset",
    "available_feature_columns",
    "build_base_estimator",
    "build_first_touch_classifier_dataset",
    "feature_importance_frame",
    "fit_probabilistic_model",
    "generate_walk_forward_folds",
    "load_model_pack",
    "predict_first_touch_probabilities_for_date",
    "realized_first_touch_outcome_from_ohlc",
    "save_first_touch_model_pack",
]
