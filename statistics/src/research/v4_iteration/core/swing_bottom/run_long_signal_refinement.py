from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_LONG_SIGNAL_REFINEMENT_CSV_PATH,
    DEFAULT_LONG_SIGNAL_REFINEMENT_SUMMARY_CSV_PATH,
    DEFAULT_SIGNAL_LAYER_CSV_PATH,
    DEFAULT_SIGNAL_OUTCOMES_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_LONG_SIGNAL_REFINEMENT_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_LONG_SIGNAL_REFINEMENT.md"
)

REQUIRED_SIGNAL_COLUMNS = [
    "date",
    "close",
    "signal_state",
    "signal_side",
    "signal_reactivation_flag",
    "signal_context_run_length_days",
    "rule_state_age_days",
    "rule_state_run_length_days",
    "promoted_buy_timing_score",
    "promoted_sell_timing_score",
    "timing_score_spread",
    "edge_clarity_score",
    "conflict_score",
    "dist_to_current_down_swing_low_pct",
    "buy_zone_within_5pct_above_low",
    "buy_zone_within_3pct_above_low",
    "sell_zone_within_5pct_below_high",
]
REQUIRED_OUTCOME_COLUMNS = [
    "date",
    "return_1d",
    "return_3d",
    "return_5d",
    "return_10d",
    "favorable_excursion_5d",
    "adverse_excursion_5d",
    "favorable_excursion_10d",
    "adverse_excursion_10d",
    "touch_favorable_2pct_5d",
    "touch_adverse_2pct_5d",
    "touch_favorable_2pct_10d",
    "touch_adverse_2pct_10d",
    "touch_favorable_5pct_10d",
    "touch_adverse_5pct_10d",
    "favorable_2pct_before_adverse_2pct_10d",
    "adverse_2pct_before_favorable_2pct_10d",
    "time_to_favorable_2pct_10d",
    "time_to_adverse_2pct_10d",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build long-side intra-signal refinement diagnostics.")
    parser.add_argument(
        "--signal-layer-csv",
        default=str(DEFAULT_SIGNAL_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_layer.csv",
    )
    parser.add_argument(
        "--signal-outcomes-csv",
        default=str(DEFAULT_SIGNAL_OUTCOMES_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_outcomes.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_LONG_SIGNAL_REFINEMENT_CSV_PATH),
        help="Default: ../out/swing_bottom/long_signal_refinement.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_LONG_SIGNAL_REFINEMENT_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/long_signal_refinement_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_LONG_SIGNAL_REFINEMENT_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_LONG_SIGNAL_REFINEMENT.md",
    )
    return parser.parse_args()


def load_inputs(signal_path: str | Path, outcome_path: str | Path) -> pd.DataFrame:
    signals = pd.read_csv(signal_path).sort_values("date").reset_index(drop=True)
    missing_signal = [column for column in REQUIRED_SIGNAL_COLUMNS if column not in signals.columns]
    if missing_signal:
        raise ValueError(f"Signal layer is missing required columns: {missing_signal}")
    outcomes = pd.read_csv(outcome_path).sort_values("date").reset_index(drop=True)
    missing_outcome = [column for column in REQUIRED_OUTCOME_COLUMNS if column not in outcomes.columns]
    if missing_outcome:
        raise ValueError(f"Signal outcome file is missing required columns: {missing_outcome}")
    long_signals = signals.loc[signals["signal_state"].eq("LONG_SIGNAL_NEW"), REQUIRED_SIGNAL_COLUMNS].copy()
    long_outcomes = outcomes.loc[outcomes["signal_state"].eq("LONG_SIGNAL_NEW"), REQUIRED_OUTCOME_COLUMNS].copy()
    merged = long_signals.merge(long_outcomes, on="date", how="inner", validate="one_to_one")
    if len(merged) != len(long_signals):
        raise ValueError("Long signal/outcome merge lost events.")
    if merged["date"].duplicated().any():
        raise ValueError("Long signal refinement dataset contains duplicate dates.")
    return merged


def score_quality(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    high_buy = out["promoted_buy_timing_score"].ge(out["promoted_buy_timing_score"].quantile(0.66))
    high_spread = out["timing_score_spread"].ge(out["timing_score_spread"].quantile(0.66))
    high_clarity = out["edge_clarity_score"].ge(out["edge_clarity_score"].quantile(0.66))
    low_conflict = out["conflict_score"].le(out["conflict_score"].quantile(0.33))
    low_sell = out["promoted_sell_timing_score"].le(out["promoted_sell_timing_score"].quantile(0.33))
    near_low = out["dist_to_current_down_swing_low_pct"].le(out["dist_to_current_down_swing_low_pct"].quantile(0.50))
    far_from_low = out["dist_to_current_down_swing_low_pct"].gt(out["dist_to_current_down_swing_low_pct"].quantile(0.75))
    high_conflict = out["conflict_score"].ge(out["conflict_score"].quantile(0.66))
    weak_spread = out["timing_score_spread"].le(out["timing_score_spread"].quantile(0.33))
    high_sell = out["promoted_sell_timing_score"].ge(out["promoted_sell_timing_score"].quantile(0.66))

    out["quality_component_buy_score_high"] = high_buy.astype(int)
    out["quality_component_spread_high"] = high_spread.astype(int)
    out["quality_component_clarity_high"] = high_clarity.astype(int)
    out["quality_component_conflict_low"] = low_conflict.astype(int)
    out["quality_component_sell_score_low"] = low_sell.astype(int)
    out["quality_component_near_low"] = near_low.astype(int)
    out["quality_component_far_from_low"] = far_from_low.astype(int)
    out["quality_component_conflict_high"] = high_conflict.astype(int)
    out["quality_component_spread_weak"] = weak_spread.astype(int)
    out["quality_component_sell_score_high"] = high_sell.astype(int)
    out["long_refinement_score"] = (
        high_buy.astype(int)
        + high_spread.astype(int)
        + high_clarity.astype(int)
        + low_conflict.astype(int)
        + low_sell.astype(int)
        + near_low.astype(int)
        - far_from_low.astype(int)
        - high_conflict.astype(int)
        - weak_spread.astype(int)
        - high_sell.astype(int)
    )

    conditions = [
        out["long_refinement_score"].ge(3),
        out["long_refinement_score"].le(0),
    ]
    choices = ["LONG_QUALITY_HIGH", "LONG_QUALITY_LOW"]
    out["long_refinement_bucket"] = np.select(conditions, choices, default="LONG_QUALITY_MEDIUM")
    out["long_refinement_note"] = out["long_refinement_bucket"].map(
        {
            "LONG_QUALITY_HIGH": "Stronger buy dominance, clarity, low conflict, and/or closer-to-low structure.",
            "LONG_QUALITY_MEDIUM": "Valid long signal but mixed structural quality.",
            "LONG_QUALITY_LOW": "Long signal is structurally early, conflicted, or weakly separated.",
        }
    )
    return out


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.median()) if values.notna().any() else np.nan


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for bucket, group in frame.groupby("long_refinement_bucket", sort=True):
        metrics = {
            "event_count": float(len(group)),
            "event_share": float(len(group) / len(frame)) if len(frame) else np.nan,
            "mean_return_1d": safe_mean(group["return_1d"]),
            "median_return_1d": safe_median(group["return_1d"]),
            "mean_return_3d": safe_mean(group["return_3d"]),
            "median_return_3d": safe_median(group["return_3d"]),
            "mean_return_5d": safe_mean(group["return_5d"]),
            "median_return_5d": safe_median(group["return_5d"]),
            "mean_return_10d": safe_mean(group["return_10d"]),
            "median_return_10d": safe_median(group["return_10d"]),
            "mean_favorable_excursion_10d": safe_mean(group["favorable_excursion_10d"]),
            "mean_adverse_excursion_10d": safe_mean(group["adverse_excursion_10d"]),
            "touch_favorable_2pct_10d_rate": safe_mean(group["touch_favorable_2pct_10d"]),
            "touch_adverse_2pct_10d_rate": safe_mean(group["touch_adverse_2pct_10d"]),
            "touch_favorable_5pct_10d_rate": safe_mean(group["touch_favorable_5pct_10d"]),
            "touch_adverse_5pct_10d_rate": safe_mean(group["touch_adverse_5pct_10d"]),
            "favorable_2pct_before_adverse_2pct_10d_rate": safe_mean(group["favorable_2pct_before_adverse_2pct_10d"]),
            "adverse_2pct_before_favorable_2pct_10d_rate": safe_mean(group["adverse_2pct_before_favorable_2pct_10d"]),
            "median_time_to_favorable_2pct_10d": safe_median(group["time_to_favorable_2pct_10d"]),
            "mean_buy_score": safe_mean(group["promoted_buy_timing_score"]),
            "mean_sell_score": safe_mean(group["promoted_sell_timing_score"]),
            "mean_spread": safe_mean(group["timing_score_spread"]),
            "mean_clarity": safe_mean(group["edge_clarity_score"]),
            "mean_conflict": safe_mean(group["conflict_score"]),
            "mean_dist_to_low": safe_mean(group["dist_to_current_down_swing_low_pct"]),
        }
        for metric, value in metrics.items():
            rows.append({"bucket": bucket, "metric": metric, "value": value})
    return pd.DataFrame(rows)


def pivot_summary(summary: pd.DataFrame) -> pd.DataFrame:
    return summary.pivot_table(index="bucket", columns="metric", values="value", aggfunc="first").reset_index()


def pct(value: float, digits: int = 1) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    out = frame.loc[:, columns].copy()
    if out.empty:
        return "_No rows._"
    rendered = out.fillna("n/a").astype(str)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = [
        "| " + " | ".join(str(value).replace("\n", " ") for value in record) + " |"
        for record in rendered.to_numpy()
    ]
    return "\n".join([header, separator, *rows])


def render_markdown(frame: pd.DataFrame, summary: pd.DataFrame) -> str:
    pivot = pivot_summary(summary)
    order = {"LONG_QUALITY_HIGH": 0, "LONG_QUALITY_MEDIUM": 1, "LONG_QUALITY_LOW": 2}
    pivot["order"] = pivot["bucket"].map(order)
    pivot = pivot.sort_values("order")
    display = pivot[
        [
            "bucket",
            "event_count",
            "event_share",
            "mean_return_5d",
            "median_return_5d",
            "mean_return_10d",
            "median_return_10d",
            "mean_favorable_excursion_10d",
            "mean_adverse_excursion_10d",
            "touch_favorable_2pct_10d_rate",
            "touch_adverse_2pct_10d_rate",
            "favorable_2pct_before_adverse_2pct_10d_rate",
            "adverse_2pct_before_favorable_2pct_10d_rate",
        ]
    ].copy()
    for column in display.columns:
        if column != "bucket":
            display[column] = display[column].map(lambda value: pct(float(value)) if column != "event_count" else number(float(value)))

    structure = pivot[
        [
            "bucket",
            "mean_buy_score",
            "mean_sell_score",
            "mean_spread",
            "mean_clarity",
            "mean_conflict",
            "mean_dist_to_low",
        ]
    ].copy()
    for column in [c for c in structure.columns if c != "bucket"]:
        structure[column] = structure[column].map(lambda value: number(float(value)))

    high = pivot.loc[pivot["bucket"].eq("LONG_QUALITY_HIGH")]
    low = pivot.loc[pivot["bucket"].eq("LONG_QUALITY_LOW")]
    if not high.empty and not low.empty:
        high_adv = float(high["adverse_2pct_before_favorable_2pct_10d_rate"].iloc[0])
        low_adv = float(low["adverse_2pct_before_favorable_2pct_10d_rate"].iloc[0])
        high_fav_first = float(high["favorable_2pct_before_adverse_2pct_10d_rate"].iloc[0])
        low_fav_first = float(low["favorable_2pct_before_adverse_2pct_10d_rate"].iloc[0])
        high_ret = float(high["mean_return_10d"].iloc[0])
        low_ret = float(low["mean_return_10d"].iloc[0])
        high_adverse_excursion = float(high["mean_adverse_excursion_10d"].iloc[0])
        low_adverse_excursion = float(low["mean_adverse_excursion_10d"].iloc[0])
        materially_better_adverse = high_adverse_excursion > low_adverse_excursion + 0.02
        materially_better_return = high_ret > low_ret + 0.02
        materially_better_ordering = high_fav_first >= low_fav_first + 0.05 and high_adv <= low_adv - 0.05
        if materially_better_ordering and materially_better_adverse and materially_better_return:
            conclusion = "Yes - meaningful refinement exists. The high-quality bucket improves returns, adverse excursion, and path ordering."
        elif materially_better_adverse or materially_better_return or high_adv < low_adv:
            conclusion = "Partially - small improvement only. Refinement helps one dimension, but noise remains material."
        else:
            conclusion = "No - little separation found. Current structural fields do not clearly isolate better long entries."
    else:
        conclusion = "Partially - bucket coverage is insufficient for a strong conclusion."

    lines = [
        "# SAFE v4.0 Long Signal Refinement",
        "",
        "## Purpose",
        "",
        "This pass analyzes only `LONG_SIGNAL_NEW` events to determine whether the current structural stack can separate better and worse long-side entry-quality zones. "
        "It does not define execution, entries, exits, stops, position sizing, portfolio logic, PnL, or backtests.",
        "",
        "## Refinement Logic",
        "",
        "A compact structural score is built from high buy timing, strong timing spread, high clarity, low conflict, low sell timing, and proximity to the current down-swing low. "
        "Penalties are applied for far-from-low structure, high conflict, weak spread, and elevated sell timing.",
        "",
        "- `LONG_QUALITY_HIGH`: refinement score >= 3",
        "- `LONG_QUALITY_MEDIUM`: refinement score between 1 and 2",
        "- `LONG_QUALITY_LOW`: refinement score <= 0",
        "",
        "## Outcome Comparison",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Structural Profile",
        "",
        markdown_table(structure, list(structure.columns)),
        "",
        "## Final Read",
        "",
        conclusion,
        "",
        "The result is diagnostic only. Any later strategy work should treat these buckets as entry-quality context, not as direct order rules.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/long_signal_refinement.csv`",
        "- `out/swing_bottom/long_signal_refinement_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def validate_output(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise ValueError("Long signal refinement output is empty.")
    if frame["date"].duplicated().any():
        raise ValueError("Long signal refinement output contains duplicate event dates.")
    allowed = {"LONG_QUALITY_HIGH", "LONG_QUALITY_MEDIUM", "LONG_QUALITY_LOW"}
    unexpected = sorted(set(frame["long_refinement_bucket"].dropna()) - allowed)
    if unexpected:
        raise ValueError(f"Unexpected refinement buckets: {unexpected}")
    if not frame["signal_state"].eq("LONG_SIGNAL_NEW").all():
        raise ValueError("Refinement output must contain only LONG_SIGNAL_NEW events.")


def run(args: argparse.Namespace) -> None:
    merged = load_inputs(args.signal_layer_csv, args.signal_outcomes_csv)
    refined = score_quality(merged)
    validate_output(refined)
    summary = build_summary(refined)
    markdown = render_markdown(refined, summary)

    out_csv = Path(args.out_csv)
    out_summary = Path(args.out_summary_csv)
    out_md = Path(args.out_md)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    refined.to_csv(out_csv, index=False)
    summary.to_csv(out_summary, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_summary}")
    print(f"Wrote {out_md}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
