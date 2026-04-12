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
    DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_CSV_PATH,
    DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_SUMMARY_CSV_PATH,
    DEFAULT_LONG_SIGNAL_REFINEMENT_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_FINAL_LONG_SIGNAL_CONDITIONING.md"
)

REQUIRED_COLUMNS = [
    "date",
    "close",
    "long_refinement_bucket",
    "long_refinement_score",
    "promoted_buy_timing_score",
    "promoted_sell_timing_score",
    "timing_score_spread",
    "edge_clarity_score",
    "conflict_score",
    "dist_to_current_down_swing_low_pct",
    "return_1d",
    "return_3d",
    "return_5d",
    "return_10d",
    "favorable_excursion_10d",
    "adverse_excursion_10d",
    "touch_favorable_2pct_10d",
    "touch_adverse_2pct_10d",
    "touch_favorable_5pct_10d",
    "touch_adverse_5pct_10d",
    "favorable_2pct_before_adverse_2pct_10d",
    "adverse_2pct_before_favorable_2pct_10d",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run final narrow conditioning on high-quality long signal events.")
    parser.add_argument(
        "--long-signal-refinement-csv",
        default=str(DEFAULT_LONG_SIGNAL_REFINEMENT_CSV_PATH),
        help="Default: ../out/swing_bottom/long_signal_refinement.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_CSV_PATH),
        help="Default: ../out/swing_bottom/final_long_signal_conditioning.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/final_long_signal_conditioning_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_FINAL_LONG_SIGNAL_CONDITIONING.md",
    )
    return parser.parse_args()


def load_refinement(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path).sort_values("date").reset_index(drop=True)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Long signal refinement file is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Long signal refinement file contains duplicate dates.")
    return frame


def variant_masks(frame: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    high = frame["long_refinement_bucket"].eq("LONG_QUALITY_HIGH")
    high_frame = frame.loc[high]
    if high_frame.empty:
        raise ValueError("No LONG_QUALITY_HIGH events available for final conditioning.")

    spread_cut = float(high_frame["timing_score_spread"].quantile(0.66))
    conflict_cut = float(high_frame["conflict_score"].quantile(0.33))
    dist_cut = float(high_frame["dist_to_current_down_swing_low_pct"].quantile(0.33))
    clarity_cut = float(high_frame["edge_clarity_score"].quantile(0.66))

    return [
        ("all_long_signal_new", "All LONG_SIGNAL_NEW events.", pd.Series(True, index=frame.index)),
        ("long_quality_high", "Existing best bucket from prior refinement.", high),
        (
            "high_strongest_spread",
            f"LONG_QUALITY_HIGH with timing_score_spread >= {spread_cut:.3f}.",
            high & frame["timing_score_spread"].ge(spread_cut),
        ),
        (
            "high_lowest_conflict",
            f"LONG_QUALITY_HIGH with conflict_score <= {conflict_cut:.3f}.",
            high & frame["conflict_score"].le(conflict_cut),
        ),
        (
            "high_closest_to_low",
            f"LONG_QUALITY_HIGH with dist_to_current_down_swing_low_pct <= {dist_cut:.3f}.",
            high & frame["dist_to_current_down_swing_low_pct"].le(dist_cut),
        ),
        (
            "high_clean_near_combo",
            f"LONG_QUALITY_HIGH with conflict <= {conflict_cut:.3f}, spread >= {spread_cut:.3f}, and clarity >= {clarity_cut:.3f}.",
            high
            & frame["conflict_score"].le(conflict_cut)
            & frame["timing_score_spread"].ge(spread_cut)
            & frame["edge_clarity_score"].ge(clarity_cut),
        ),
    ]


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.median()) if values.notna().any() else np.nan


def summarize_variant(name: str, description: str, group: pd.DataFrame, total_count: int) -> dict[str, object]:
    return {
        "variant": name,
        "description": description,
        "event_count": len(group),
        "share_of_all_long_signal_new": len(group) / total_count if total_count else np.nan,
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
        "mean_spread": safe_mean(group["timing_score_spread"]),
        "mean_clarity": safe_mean(group["edge_clarity_score"]),
        "mean_conflict": safe_mean(group["conflict_score"]),
        "mean_dist_to_low": safe_mean(group["dist_to_current_down_swing_low_pct"]),
    }


def build_conditioning(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    membership_columns = [
        "date",
        "close",
        "long_refinement_bucket",
        "long_refinement_score",
        "promoted_buy_timing_score",
        "promoted_sell_timing_score",
        "timing_score_spread",
        "edge_clarity_score",
        "conflict_score",
        "dist_to_current_down_swing_low_pct",
        "return_1d",
        "return_3d",
        "return_5d",
        "return_10d",
        "favorable_excursion_10d",
        "adverse_excursion_10d",
        "touch_favorable_2pct_10d",
        "touch_adverse_2pct_10d",
        "favorable_2pct_before_adverse_2pct_10d",
        "adverse_2pct_before_favorable_2pct_10d",
    ]
    membership = frame.loc[:, membership_columns].copy()
    for name, description, mask in variant_masks(frame):
        group = frame.loc[mask].copy()
        rows.append(summarize_variant(name, description, group, len(frame)))
        membership[f"variant_{name}"] = mask.astype(int)
    summary = pd.DataFrame(rows)
    reference = summary.loc[summary["variant"].eq("long_quality_high")].iloc[0]
    summary["event_delta_vs_high"] = summary["event_count"] - float(reference["event_count"])
    summary["return_10d_delta_vs_high"] = summary["mean_return_10d"] - float(reference["mean_return_10d"])
    summary["adverse_excursion_delta_vs_high"] = (
        summary["mean_adverse_excursion_10d"] - float(reference["mean_adverse_excursion_10d"])
    )
    summary["favorable_first_delta_vs_high"] = (
        summary["favorable_2pct_before_adverse_2pct_10d_rate"]
        - float(reference["favorable_2pct_before_adverse_2pct_10d_rate"])
    )
    summary["adverse_first_delta_vs_high"] = (
        summary["adverse_2pct_before_favorable_2pct_10d_rate"]
        - float(reference["adverse_2pct_before_favorable_2pct_10d_rate"])
    )
    return membership, summary


def recommend(summary: pd.DataFrame) -> tuple[str, str]:
    high = summary.loc[summary["variant"].eq("long_quality_high")].iloc[0]
    candidates = summary.loc[~summary["variant"].isin(["all_long_signal_new", "long_quality_high"])].copy()
    candidates = candidates.loc[candidates["event_count"].ge(15)].copy()
    if candidates.empty:
        return (
            "Good enough as structural interpreter, not as clean trigger engine",
            "No conditioned subset kept enough events for a meaningful final improvement test.",
        )
    viable = candidates.loc[
        candidates["mean_return_10d"].ge(float(high["mean_return_10d"]) + 0.02)
        & candidates["mean_adverse_excursion_10d"].ge(float(high["mean_adverse_excursion_10d"]) + 0.015)
        & candidates["favorable_2pct_before_adverse_2pct_10d_rate"].ge(
            float(high["favorable_2pct_before_adverse_2pct_10d_rate"]) + 0.05
        )
    ]
    if not viable.empty:
        best = viable.sort_values(
            ["favorable_2pct_before_adverse_2pct_10d_rate", "mean_return_10d"],
            ascending=False,
        ).iloc[0]
        return (
            "Continue worth it",
            f"`{best['variant']}` materially improves return, adverse excursion, and favorable-first ordering with {int(best['event_count'])} events.",
        )
    partial = candidates.loc[
        candidates["mean_return_10d"].ge(float(high["mean_return_10d"]) + 0.015)
        | candidates["mean_adverse_excursion_10d"].ge(float(high["mean_adverse_excursion_10d"]) + 0.015)
        | candidates["favorable_2pct_before_adverse_2pct_10d_rate"].ge(
            float(high["favorable_2pct_before_adverse_2pct_10d_rate"]) + 0.05
        )
    ]
    if not partial.empty:
        return (
            "Good enough as structural interpreter, not as clean trigger engine",
            "One or more stricter subsets improve a dimension, but not enough dimensions at once to justify another refinement branch.",
        )
    return (
        "Likely intrinsic noise / stop here",
        "Stricter conditioning does not improve path quality enough beyond `LONG_QUALITY_HIGH`.",
    )


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


def render_markdown(summary: pd.DataFrame, decision: str, reason: str) -> str:
    display = summary[
        [
            "variant",
            "event_count",
            "share_of_all_long_signal_new",
            "mean_return_5d",
            "mean_return_10d",
            "mean_favorable_excursion_10d",
            "mean_adverse_excursion_10d",
            "touch_favorable_2pct_10d_rate",
            "touch_adverse_2pct_10d_rate",
            "favorable_2pct_before_adverse_2pct_10d_rate",
            "adverse_2pct_before_favorable_2pct_10d_rate",
        ]
    ].copy()
    for column in display.columns:
        if column == "variant":
            continue
        if column == "event_count":
            display[column] = display[column].map(lambda value: number(float(value)))
        else:
            display[column] = display[column].map(lambda value: pct(float(value)))

    deltas = summary[
        [
            "variant",
            "event_delta_vs_high",
            "return_10d_delta_vs_high",
            "adverse_excursion_delta_vs_high",
            "favorable_first_delta_vs_high",
            "adverse_first_delta_vs_high",
        ]
    ].copy()
    for column in deltas.columns:
        if column == "variant":
            continue
        deltas[column] = deltas[column].map(lambda value: number(float(value)))

    lines = [
        "# SAFE v4.0 Final Long Signal Conditioning",
        "",
        "## Purpose",
        "",
        "This final narrow pass tests whether stricter conditioning of the already-best long subset can materially clean up forward paths. "
        "It does not define execution, entries, exits, stops, position sizing, portfolio logic, PnL, or backtests.",
        "",
        "## Variants",
        "",
        "- `all_long_signal_new`: all long signal events.",
        "- `long_quality_high`: prior best long-quality bucket.",
        "- `high_strongest_spread`: high-quality events with strongest timing spread.",
        "- `high_lowest_conflict`: high-quality events with lowest conflict.",
        "- `high_closest_to_low`: high-quality events closest to the current down-swing low.",
        "- `high_clean_near_combo`: compact combined clean/strong subset.",
        "",
        "## Conditioning Results",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Delta Versus `LONG_QUALITY_HIGH`",
        "",
        markdown_table(deltas, list(deltas.columns)),
        "",
        "## Final Conclusion",
        "",
        f"**{decision}.** {reason}",
        "",
        "The strongest subset is small, so this does not justify execution logic. It only justifies one future validation-oriented step if the project continues: confirm whether closest-to-low conditioning remains stable outside this sample.",
        "",
        "## Cleanup Readiness Note",
        "",
        "Current keeper chain for arrangement: swing detection, reversal-zone dataset/models as label foundation, swing extreme timing, buy-side hybrid validation, decision layer, playbook layer, strategy translation layer, calibrated rule layer, signal layer, signal outcomes, long signal refinement, and this final conditioning report.",
        "",
        "Exploratory-only candidates for later cleanup: broad buy-side exploration variants, intermediate low-risk/bearish branch artifacts, early uncalibrated rule outputs, and any report whose only purpose was branch selection rather than retained structural interpretation.",
        "",
        "No files are deleted in this pass.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/final_long_signal_conditioning.csv`",
        "- `out/swing_bottom/final_long_signal_conditioning_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def validate_outputs(membership: pd.DataFrame, summary: pd.DataFrame) -> None:
    if membership.empty or summary.empty:
        raise ValueError("Final long signal conditioning outputs cannot be empty.")
    if membership["date"].duplicated().any():
        raise ValueError("Conditioning membership output contains duplicate event dates.")
    required = {"all_long_signal_new", "long_quality_high"}
    missing = required - set(summary["variant"])
    if missing:
        raise ValueError(f"Conditioning summary missing required variants: {sorted(missing)}")


def run(args: argparse.Namespace) -> None:
    frame = load_refinement(args.long_signal_refinement_csv)
    membership, summary = build_conditioning(frame)
    validate_outputs(membership, summary)
    decision, reason = recommend(summary)
    markdown = render_markdown(summary, decision, reason)

    out_csv = Path(args.out_csv)
    out_summary = Path(args.out_summary_csv)
    out_md = Path(args.out_md)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    membership.to_csv(out_csv, index=False)
    summary.to_csv(out_summary, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_summary}")
    print(f"Wrote {out_md}")
    print(f"Decision: {decision}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
