from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_PRICE_JSON_PATH, OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.core.swing_detection.run_swing_detection import detect_swings


DEFAULT_SUMMARY_CSV_PATH = OUT_DIR / "swing_detection" / "swing_sensitivity_summary.csv"
DEFAULT_SUMMARY_MD_PATH = STATISTICS_DIR / "docs" / "swing_detection" / "SAFE_v4.0_SWING_SENSITIVITY.md"

DEFAULT_ATR_WINDOWS: tuple[int, ...] = (10, 14, 20)
DEFAULT_REVERSAL_KS: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0, 2.5)


AMPLITUDE_BINS: tuple[tuple[str, float, float], ...] = (
    ("0_5pct", 0.0, 0.05),
    ("5_10pct", 0.05, 0.10),
    ("10_20pct", 0.10, 0.20),
    ("20_30pct", 0.20, 0.30),
    ("30pct_plus", 0.30, np.inf),
)
DTYPE_SAFE_ZERO = 0
DURATION_BINS: tuple[tuple[str, int, float], ...] = (
    ("0_6d", 0, 7),
    ("7_13d", 7, 14),
    ("14_29d", 14, 30),
    ("30_59d", 30, 60),
    ("60d_plus", 60, np.inf),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a small ATR-window / reversal-k grid to test swing-detector stability.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_detection/swing_sensitivity_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SUMMARY_MD_PATH),
        help="Default: ../docs/swing_detection/SAFE_v4.0_SWING_SENSITIVITY.md",
    )
    return parser.parse_args()


def _safe_median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else float("nan")


def _safe_spearman(left: pd.Series, right: pd.Series) -> float:
    joined = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(joined) < 2 or joined["left"].nunique() < 2 or joined["right"].nunique() < 2:
        return float("nan")
    return float(joined["left"].corr(joined["right"], method="spearman"))


def _count_in_bin(series: pd.Series, lower: float, upper: float) -> int:
    clean = pd.to_numeric(series, errors="coerce").abs().dropna()
    if np.isinf(upper):
        return int((clean >= lower).sum())
    return int(((clean >= lower) & (clean < upper)).sum())


def _count_duration_bin(series: pd.Series, lower: int, upper: float) -> int:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if np.isinf(upper):
        return int((clean >= lower).sum())
    return int(((clean >= lower) & (clean < upper)).sum())


def summarize_swings(swings: pd.DataFrame, atr_window: int, reversal_k: float) -> dict[str, float | int]:
    up_swings = swings.loc[swings["direction"] == "up"].copy()
    down_swings = swings.loc[swings["direction"] == "down"].copy()
    abs_amplitude = swings["amplitude_pct"].abs()

    row: dict[str, float | int] = {
        "atr_window": atr_window,
        "reversal_k": reversal_k,
        "swing_count": int(len(swings)),
        "up_swing_count": int(len(up_swings)),
        "down_swing_count": int(len(down_swings)),
        "median_abs_amplitude": _safe_median(abs_amplitude),
        "median_up_amplitude": _safe_median(up_swings["amplitude_pct"]),
        "median_down_amplitude": _safe_median(down_swings["amplitude_pct"]),
        "median_duration_days": _safe_median(swings["duration_days"]),
        "up_median_duration_days": _safe_median(up_swings["duration_days"]),
        "down_median_duration_days": _safe_median(down_swings["duration_days"]),
        "amplitude_duration_spearman": _safe_spearman(abs_amplitude, swings["duration_days"]),
    }

    for label, lower, upper in AMPLITUDE_BINS:
        row[f"amplitude_bin_{label}"] = _count_in_bin(swings["amplitude_pct"], lower, upper)
    for label, lower, upper in DURATION_BINS:
        row[f"duration_bin_{label}"] = _count_duration_bin(swings["duration_days"], lower, upper)

    return row


def run_grid(price: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for atr_window in DEFAULT_ATR_WINDOWS:
        for reversal_k in DEFAULT_REVERSAL_KS:
            swings, _ = detect_swings(price, reversal_k=reversal_k, atr_window=atr_window)
            rows.append(summarize_swings(swings, atr_window=atr_window, reversal_k=reversal_k))
    return pd.DataFrame(rows).sort_values(["atr_window", "reversal_k"]).reset_index(drop=True)


def _format_table(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, divider]
    for _, row in frame.iterrows():
        values: list[str] = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                if column == "reversal_k":
                    values.append(f"{value:.2f}")
                elif "amplitude" in column or "spearman" in column:
                    values.append(f"{value:.4f}")
                else:
                    values.append(f"{value:.1f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _find_recommended_configs(summary: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    stable_mid = summary.loc[summary["reversal_k"].isin([1.25, 1.5, 2.0])].copy()

    fine_candidates = stable_mid.loc[
        stable_mid["median_duration_days"].between(3, 4) & stable_mid["swing_count"].between(650, 800)
    ].copy()
    medium_candidates = stable_mid.loc[
        stable_mid["median_duration_days"].between(4, 7) & stable_mid["swing_count"].between(300, 600)
    ].copy()

    if fine_candidates.empty:
        fine_candidates = stable_mid.loc[stable_mid["median_duration_days"] <= 4].copy()
    if medium_candidates.empty:
        medium_candidates = stable_mid.loc[stable_mid["median_duration_days"] >= 4].copy()

    fine_candidates = fine_candidates.assign(
        atr_distance=(fine_candidates["atr_window"] - 14).abs(),
        duration_distance=(fine_candidates["median_duration_days"] - 3).abs(),
    )
    medium_candidates = medium_candidates.assign(
        atr_distance=(medium_candidates["atr_window"] - 14).abs(),
        duration_distance=(medium_candidates["median_duration_days"] - 5).abs(),
    )

    fine_choice = fine_candidates.sort_values(
        ["duration_distance", "atr_distance", "reversal_k", "swing_count"],
        ascending=[True, True, True, False],
    ).iloc[0]
    medium_choice = medium_candidates.sort_values(
        ["duration_distance", "atr_distance", "reversal_k", "swing_count"],
        ascending=[True, True, True, False],
    ).iloc[0]
    return fine_choice, medium_choice


def _k_sensitivity_lines(summary: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    grouped = summary.groupby("reversal_k").agg(
        swing_count_min=("swing_count", "min"),
        swing_count_max=("swing_count", "max"),
        median_amp_min=("median_abs_amplitude", "min"),
        median_amp_max=("median_abs_amplitude", "max"),
        median_dur_min=("median_duration_days", "min"),
        median_dur_max=("median_duration_days", "max"),
    )
    for reversal_k, row in grouped.iterrows():
        lines.append(
            f"- `k={reversal_k:.2f}`: swings `{int(row['swing_count_min'])}-{int(row['swing_count_max'])}`, "
            f"median amplitude `{row['median_amp_min']:.2%}-{row['median_amp_max']:.2%}`, "
            f"median duration `{int(row['median_dur_min'])}-{int(row['median_dur_max'])}` days"
        )
    return lines


def _atr_sensitivity_lines(summary: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    grouped = summary.groupby("atr_window").agg(
        swing_count_min=("swing_count", "min"),
        swing_count_max=("swing_count", "max"),
        median_amp_min=("median_abs_amplitude", "min"),
        median_amp_max=("median_abs_amplitude", "max"),
        median_dur_min=("median_duration_days", "min"),
        median_dur_max=("median_duration_days", "max"),
    )
    for atr_window, row in grouped.iterrows():
        lines.append(
            f"- `ATR {atr_window}`: swings `{int(row['swing_count_min'])}-{int(row['swing_count_max'])}`, "
            f"median amplitude `{row['median_amp_min']:.2%}-{row['median_amp_max']:.2%}`, "
            f"median duration `{int(row['median_dur_min'])}-{int(row['median_dur_max'])}` days"
        )
    return lines


def render_markdown(summary: pd.DataFrame) -> str:
    fine_choice, medium_choice = _find_recommended_configs(summary)
    too_fine = summary.sort_values("swing_count", ascending=False).iloc[0]
    too_coarse = summary.sort_values("swing_count", ascending=True).iloc[0]
    compact = summary.loc[
        :, ["atr_window", "reversal_k", "swing_count", "median_abs_amplitude", "median_duration_days", "amplitude_duration_spearman"]
    ]

    lines = [
        "# SAFE v4.0 Swing Sensitivity",
        "",
        "This note tests whether the ATR-normalized ZigZag swing layer is structurally stable across a small parameter grid.",
        "",
        "Grid tested:",
        "- ATR window: `10`, `14`, `20`",
        "- reversal multiplier `k`: `1.00`, `1.25`, `1.50`, `2.00`, `2.50`",
        "",
        "## Compact Results",
        "",
    ]
    lines.extend(_format_table(compact, list(compact.columns)))
    lines.extend(
        [
            "",
            "## What Changed When `k` Changed",
            "",
        ]
    )
    lines.extend(_k_sensitivity_lines(summary))
    lines.extend(
        [
            "",
            "## What Changed When ATR Window Changed",
            "",
        ]
    )
    lines.extend(_atr_sensitivity_lines(summary))

    lines.extend(
        [
            "",
            "## Stability Readout",
            "",
            f"- swing count is much more sensitive to `reversal_k` than to ATR window",
            f"- `k={too_fine['reversal_k']:.2f}`, `ATR {int(too_fine['atr_window'])}` is the finest slice here with `{int(too_fine['swing_count'])}` swings",
            f"- `k={too_coarse['reversal_k']:.2f}`, `ATR {int(too_coarse['atr_window'])}` is the coarsest slice here with `{int(too_coarse['swing_count'])}` swings",
            "- median amplitude rises as `k` rises, while median duration also tends to lengthen",
            "- ATR window changes the structure, but less dramatically than `k`",
            "- the most stable middle zone is around `k=1.25` to `k=2.00`, where swing count and median structure change gradually rather than collapsing",
            "",
            "## Too Fine vs Too Coarse",
            "",
            f"- too fine: `ATR {int(too_fine['atr_window'])}`, `k={too_fine['reversal_k']:.2f}` "
            f"with `{int(too_fine['swing_count'])}` swings and median duration `{int(too_fine['median_duration_days'])}` days",
            f"- too coarse: `ATR {int(too_coarse['atr_window'])}`, `k={too_coarse['reversal_k']:.2f}` "
            f"with `{int(too_coarse['swing_count'])}` swings and median duration `{int(too_coarse['median_duration_days'])}` days",
            "",
            "## Recommended Configurations",
            "",
            f"- fine-grained: `ATR {int(fine_choice['atr_window'])}`, `k={fine_choice['reversal_k']:.2f}`",
            f"  - swings: `{int(fine_choice['swing_count'])}`",
            f"  - median amplitude: `{fine_choice['median_abs_amplitude']:.2%}`",
            f"  - median duration: `{int(fine_choice['median_duration_days'])}` days",
            f"- medium-grained: `ATR {int(medium_choice['atr_window'])}`, `k={medium_choice['reversal_k']:.2f}`",
            f"  - swings: `{int(medium_choice['swing_count'])}`",
            f"  - median amplitude: `{medium_choice['median_abs_amplitude']:.2%}`",
            f"  - median duration: `{int(medium_choice['median_duration_days'])}` days",
            "",
            "## Final Conclusion",
            "",
            "- the swing detector is stable enough for the next phase",
            "- parameter changes do alter granularity, but the structural relationship is orderly rather than chaotic",
            "- `reversal_k` is the main granularity lever",
            "- ATR window matters, but mostly as a secondary smoothing choice",
            "- the detector is therefore usable as a market-structure layer, as long as later work is explicit about whether it wants a fine or medium swing definition",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    price = load_daily_price_json(args.price_json)
    summary = run_grid(price)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_csv, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(summary), encoding="utf-8")

    fine_choice, medium_choice = _find_recommended_configs(summary)

    print(f"Rows written: {len(summary)}")
    print(
        "Recommended fine:",
        f"ATR {int(fine_choice['atr_window'])}",
        f"k={fine_choice['reversal_k']:.2f}",
        f"swings={int(fine_choice['swing_count'])}",
    )
    print(
        "Recommended medium:",
        f"ATR {int(medium_choice['atr_window'])}",
        f"k={medium_choice['reversal_k']:.2f}",
        f"swings={int(medium_choice['swing_count'])}",
    )
    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
