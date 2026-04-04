from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_TARGETS_CSV_PATH, OUT_DIR


DEFAULT_TARGETS: tuple[str, ...] = (
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "touch_up_2pct_3d",
    "touch_down_2pct_3d",
    "touch_up_2pct_10d",
    "touch_down_2pct_10d",
    "max_up_10d",
    "max_down_10d",
)
RAW_EXCLUDED_COLUMNS: frozenset[str] = frozenset({"date", "open", "high", "low", "close", "volume", "HMM_LABEL"})


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the first-pass indicator reliability analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze how informative SAFE indicators are about future BTC targets.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument(
        "--out-csv",
        default=str(OUT_DIR / "indicator_reliability.csv"),
        help="Default: ../out/indicator_reliability.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(OUT_DIR / "indicator_reliability.md"),
        help="Default: ../out/indicator_reliability.md",
    )
    parser.add_argument("--buckets", type=int, default=10, help="Quantile bucket count. Default: 10")
    return parser.parse_args()


def load_aligned_inputs(features_path: str | Path, targets_path: str | Path) -> pd.DataFrame:
    """Load and inner-join features and targets on anchor date."""
    features = load_feature_csv(features_path)
    targets = load_feature_csv(targets_path)
    merged = features.merge(targets, on="date", how="inner", validate="one_to_one", suffixes=("", "_target"))
    if merged.empty:
        raise ValueError("Aligned reliability dataset is empty after joining features and targets by date.")
    return merged.sort_values("date").reset_index(drop=True)


def select_indicator_columns(frame: pd.DataFrame) -> list[str]:
    """Select numeric indicator columns while excluding raw OHLCV and categorical fields."""
    numeric_columns = frame.select_dtypes(include=[np.number]).columns.tolist()
    return [column for column in numeric_columns if column not in RAW_EXCLUDED_COLUMNS and column in frame.columns]


def safe_corr(left: pd.Series, right: pd.Series, method: str) -> float:
    """Return a correlation only when both inputs have usable variation."""
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return float("nan")
    return float(left.corr(right, method=method))


def _is_binary_target(series: pd.Series) -> bool:
    values = pd.to_numeric(series, errors="coerce").dropna().unique().tolist()
    return bool(values) and set(values).issubset({0.0, 1.0})


def _is_return_target(target: str) -> bool:
    return target.startswith("ret_")


def bucketize_indicator(series: pd.Series, bucket_count: int) -> pd.Series:
    """Split an indicator into quantile buckets with duplicate-edge handling."""
    ranked = series.rank(method="first")
    return pd.qcut(ranked, q=bucket_count, labels=False, duplicates="drop")


def monotonicity_score(bucket_means: pd.Series) -> float:
    """Measure ordered bucket monotonicity via rank correlation against bucket index."""
    clean = bucket_means.dropna()
    if len(clean) < 2:
        return float("nan")
    bucket_index = pd.Series(clean.index.to_numpy(dtype=float), index=clean.index)
    return float(bucket_index.corr(clean.astype(float), method="spearman"))


def compute_pair_metrics(data: pd.DataFrame, indicator: str, target: str, bucket_count: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compute bucket-level statistics and pair-level summary metrics for one indicator/target pair."""
    pair = data.loc[:, ["date", indicator, target]].copy()
    pair[indicator] = pd.to_numeric(pair[indicator], errors="coerce")
    pair[target] = pd.to_numeric(pair[target], errors="coerce")
    pair = pair.dropna(subset=[indicator, target]).reset_index(drop=True)

    usable_rows = int(len(pair))
    if usable_rows == 0:
        summary = {
            "indicator": indicator,
            "target": target,
            "bucket": "summary",
            "sample_count": 0,
            "indicator_min": np.nan,
            "indicator_max": np.nan,
            "indicator_mean": np.nan,
            "target_mean": np.nan,
            "target_median": np.nan,
            "win_rate": np.nan,
            "event_rate": np.nan,
            "spearman_corr": np.nan,
            "pearson_corr": np.nan,
            "monotonicity_score": np.nan,
            "top_bottom_separation": np.nan,
            "usable_rows": 0,
        }
        return [summary], summary

    pair["bucket_index"] = bucketize_indicator(pair[indicator], bucket_count)
    bucketed = pair.dropna(subset=["bucket_index"]).copy()
    bucketed["bucket_index"] = bucketed["bucket_index"].astype(int)

    spearman_corr = safe_corr(pair[indicator], pair[target], method="spearman")
    pearson_corr = safe_corr(pair[indicator], pair[target], method="pearson")
    is_binary = _is_binary_target(pair[target])
    is_return = _is_return_target(target)

    rows: list[dict[str, Any]] = []
    bucket_target_means: dict[int, float] = {}
    for bucket_index, group in bucketed.groupby("bucket_index", sort=True):
        target_mean = float(group[target].mean()) if not group.empty else np.nan
        target_median = float(group[target].median()) if not group.empty else np.nan
        bucket_target_means[int(bucket_index)] = target_mean
        row = {
            "indicator": indicator,
            "target": target,
            "bucket": int(bucket_index) + 1,
            "sample_count": int(len(group)),
            "indicator_min": float(group[indicator].min()),
            "indicator_max": float(group[indicator].max()),
            "indicator_mean": float(group[indicator].mean()),
            "target_mean": target_mean,
            "target_median": target_median,
            "win_rate": float((group[target] > 0).mean()) if is_return else np.nan,
            "event_rate": float(group[target].mean()) if is_binary else np.nan,
            "spearman_corr": spearman_corr,
            "pearson_corr": pearson_corr,
            "monotonicity_score": np.nan,
            "top_bottom_separation": np.nan,
            "usable_rows": usable_rows,
        }
        rows.append(row)

    bucket_mean_series = pd.Series(bucket_target_means).sort_index()
    mono = monotonicity_score(bucket_mean_series)
    separation = float(bucket_mean_series.iloc[-1] - bucket_mean_series.iloc[0]) if len(bucket_mean_series) >= 2 else float("nan")

    for row in rows:
        row["monotonicity_score"] = mono
        row["top_bottom_separation"] = separation

    summary = {
        "indicator": indicator,
        "target": target,
        "bucket": "summary",
        "sample_count": usable_rows,
        "indicator_min": float(pair[indicator].min()),
        "indicator_max": float(pair[indicator].max()),
        "indicator_mean": float(pair[indicator].mean()),
        "target_mean": float(pair[target].mean()),
        "target_median": float(pair[target].median()),
        "win_rate": float((pair[target] > 0).mean()) if is_return else np.nan,
        "event_rate": float(pair[target].mean()) if is_binary else np.nan,
        "spearman_corr": spearman_corr,
        "pearson_corr": pearson_corr,
        "monotonicity_score": mono,
        "top_bottom_separation": separation,
        "usable_rows": usable_rows,
    }
    rows.append(summary)
    return rows, summary


def build_reliability_table(data: pd.DataFrame, indicators: list[str], targets: tuple[str, ...], bucket_count: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the tidy reliability table and extract summary rows."""
    missing_targets = [target for target in targets if target not in data.columns]
    if missing_targets:
        raise ValueError(f"Targets missing from aligned dataset: {missing_targets}")

    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for indicator in indicators:
        for target in targets:
            pair_rows, summary = compute_pair_metrics(data, indicator, target, bucket_count)
            rows.extend(pair_rows)
            summaries.append(summary)

    reliability = pd.DataFrame(rows)
    summary_frame = pd.DataFrame(summaries)
    return reliability, summary_frame


def _top_rows(summary_frame: pd.DataFrame, target: str, column: str, ascending: bool, limit: int = 5) -> pd.DataFrame:
    subset = summary_frame.loc[summary_frame["target"] == target].copy()
    subset = subset.dropna(subset=[column])
    return subset.sort_values(column, ascending=ascending).head(limit)


def render_markdown_report(summary_frame: pd.DataFrame, targets: tuple[str, ...]) -> str:
    """Render a compact human-readable reliability summary."""
    lines = [
        "# Indicator Reliability",
        "",
        "This report is descriptive, not causal. It shows how current SAFE indicators line up with later BTC outcomes on the same anchor dates.",
        "",
    ]

    for target in targets:
        lines.append(f"## {target}")
        lines.append("")

        strongest_positive = _top_rows(summary_frame, target, "spearman_corr", ascending=False)
        strongest_negative = _top_rows(summary_frame, target, "spearman_corr", ascending=True)
        best_separation = _top_rows(summary_frame, target, "top_bottom_separation", ascending=False)

        stable = summary_frame.loc[summary_frame["target"] == target].copy()
        stable = stable.dropna(subset=["spearman_corr", "monotonicity_score"])
        stable = stable.assign(
            instability=stable["spearman_corr"].abs().fillna(0.0) + stable["monotonicity_score"].abs().fillna(0.0)
        )
        poor_or_unstable = stable.sort_values(["instability", "usable_rows"], ascending=[True, False]).head(5)

        lines.append("### Strongest positive indicators")
        for _, row in strongest_positive.iterrows():
            lines.append(
                f"- `{row['indicator']}`: spearman={row['spearman_corr']:.4f}, separation={row['top_bottom_separation']:.4f}, usable_rows={int(row['usable_rows'])}"
            )
        if strongest_positive.empty:
            lines.append("- none")
        lines.append("")

        lines.append("### Strongest negative indicators")
        for _, row in strongest_negative.iterrows():
            lines.append(
                f"- `{row['indicator']}`: spearman={row['spearman_corr']:.4f}, separation={row['top_bottom_separation']:.4f}, usable_rows={int(row['usable_rows'])}"
            )
        if strongest_negative.empty:
            lines.append("- none")
        lines.append("")

        lines.append("### Best top-vs-bottom separation")
        for _, row in best_separation.iterrows():
            lines.append(
                f"- `{row['indicator']}`: separation={row['top_bottom_separation']:.4f}, spearman={row['spearman_corr']:.4f}, monotonicity={row['monotonicity_score']:.4f}"
            )
        if best_separation.empty:
            lines.append("- none")
        lines.append("")

        lines.append("### Poor or unstable relationships")
        for _, row in poor_or_unstable.iterrows():
            lines.append(
                f"- `{row['indicator']}`: spearman={row['spearman_corr']:.4f}, monotonicity={row['monotonicity_score']:.4f}, usable_rows={int(row['usable_rows'])}"
            )
        if poor_or_unstable.empty:
            lines.append("- none")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Run the first-pass SAFE v4.0 indicator reliability analysis."""
    try:
        args = parse_args()
        if args.buckets < 2:
            raise ValueError("--buckets must be at least 2.")

        aligned = load_aligned_inputs(args.features_csv, args.targets_csv)
        features_only = load_feature_csv(args.features_csv)
        indicators = select_indicator_columns(features_only)
        reliability, summary_frame = build_reliability_table(aligned, indicators, DEFAULT_TARGETS, args.buckets)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        out_md.parent.mkdir(parents=True, exist_ok=True)

        reliability.to_csv(out_csv, index=False, float_format="%.8f")
        out_md.write_text(render_markdown_report(summary_frame, DEFAULT_TARGETS), encoding="utf-8")

        print(f"Indicators analyzed: {len(indicators)}")
        print(f"Targets analyzed: {len(DEFAULT_TARGETS)}")
        print(f"Wrote CSV: {out_csv}")
        print(f"Wrote Markdown: {out_md}")
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Indicator reliability analysis failed: {exc}") from exc


if __name__ == "__main__":
    main()
