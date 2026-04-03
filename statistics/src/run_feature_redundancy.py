from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import DEFAULT_FEATURES_CSV_PATH, OUT_DIR


RAW_EXCLUDED_COLUMNS: frozenset[str] = frozenset({"date", "open", "high", "low", "close", "volume", "HMM_LABEL"})
DEFAULT_CORR_OUT = OUT_DIR / "feature_redundancy_corr.csv"
DEFAULT_SUMMARY_OUT = OUT_DIR / "feature_redundancy_summary.csv"
DEFAULT_MD_OUT = OUT_DIR / "feature_redundancy.md"
DEFAULT_RELIABILITY_CSV = OUT_DIR / "indicator_reliability.csv"
REDUNDANT_CLUSTER_THRESHOLD = 0.90


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the feature redundancy analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze redundancy and orthogonality across SAFE BTC indicators.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument(
        "--indicator-reliability-csv",
        default=str(DEFAULT_RELIABILITY_CSV),
        help="Optional: ../out/indicator_reliability.csv",
    )
    parser.add_argument("--out-corr-csv", default=str(DEFAULT_CORR_OUT), help="Default: ../out/feature_redundancy_corr.csv")
    parser.add_argument("--out-summary-csv", default=str(DEFAULT_SUMMARY_OUT), help="Default: ../out/feature_redundancy_summary.csv")
    parser.add_argument("--out-md", default=str(DEFAULT_MD_OUT), help="Default: ../out/feature_redundancy.md")
    return parser.parse_args()


def load_numeric_feature_frame(features_path: str | Path) -> pd.DataFrame:
    """Load the numeric feature subset used for redundancy analysis."""
    frame = load_feature_csv(features_path)
    numeric_columns = frame.select_dtypes(include=[np.number]).columns.tolist()
    selected_columns = [column for column in numeric_columns if column not in RAW_EXCLUDED_COLUMNS]
    if not selected_columns:
        raise ValueError("No numeric indicator columns were available for redundancy analysis.")
    return frame.loc[:, selected_columns].copy()


def build_pairwise_correlation_table(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compute Pearson/Spearman matrices and export them as a tidy upper-triangle table."""
    pearson = frame.corr(method="pearson")
    spearman = frame.corr(method="spearman")

    rows: list[dict[str, Any]] = []
    columns = list(frame.columns)
    for i, feature_a in enumerate(columns):
        for j in range(i + 1, len(columns)):
            feature_b = columns[j]
            pearson_corr = pearson.loc[feature_a, feature_b]
            spearman_corr = spearman.loc[feature_a, feature_b]
            rows.append(
                {
                    "feature_a": feature_a,
                    "feature_b": feature_b,
                    "pearson_corr": pearson_corr,
                    "spearman_corr": spearman_corr,
                    "abs_pearson_corr": abs(pearson_corr) if pd.notna(pearson_corr) else np.nan,
                    "abs_spearman_corr": abs(spearman_corr) if pd.notna(spearman_corr) else np.nan,
                }
            )
    return pd.DataFrame(rows), pearson, spearman


def build_redundancy_summary(pearson: pd.DataFrame, spearman: pd.DataFrame) -> pd.DataFrame:
    """Summarize how redundant each feature is relative to the rest."""
    features = list(pearson.columns)
    rows: list[dict[str, Any]] = []
    for feature in features:
        pearson_abs = pearson.loc[feature].drop(index=feature).abs()
        spearman_abs = spearman.loc[feature].drop(index=feature).abs()

        pearson_abs = pearson_abs.dropna()
        spearman_abs = spearman_abs.dropna()

        nearest_pearson_feature = pearson_abs.idxmax() if not pearson_abs.empty else None
        nearest_spearman_feature = spearman_abs.idxmax() if not spearman_abs.empty else None

        rows.append(
            {
                "feature": feature,
                "mean_abs_pearson_corr": float(pearson_abs.mean()) if not pearson_abs.empty else np.nan,
                "mean_abs_spearman_corr": float(spearman_abs.mean()) if not spearman_abs.empty else np.nan,
                "max_abs_pearson_corr": float(pearson_abs.max()) if not pearson_abs.empty else np.nan,
                "max_abs_spearman_corr": float(spearman_abs.max()) if not spearman_abs.empty else np.nan,
                "nearest_neighbor_pearson": nearest_pearson_feature,
                "nearest_neighbor_spearman": nearest_spearman_feature,
            }
        )
    return pd.DataFrame(rows).sort_values("mean_abs_spearman_corr", ascending=False).reset_index(drop=True)


def load_reliability_summary(path: str | Path) -> pd.DataFrame | None:
    """Load summary rows from Phase 2 indicator reliability output when available."""
    csv_path = Path(path)
    if not csv_path.exists():
        return None

    frame = pd.read_csv(csv_path)
    if "bucket" not in frame.columns:
        return None
    summary = frame.loc[frame["bucket"].astype(str) == "summary"].copy()
    if summary.empty:
        return None

    summary["abs_spearman_target"] = pd.to_numeric(summary["spearman_corr"], errors="coerce").abs()
    summary["abs_pearson_target"] = pd.to_numeric(summary["pearson_corr"], errors="coerce").abs()
    summary["abs_top_bottom_separation"] = pd.to_numeric(summary["top_bottom_separation"], errors="coerce").abs()

    grouped = (
        summary.sort_values(["indicator", "abs_spearman_target", "abs_top_bottom_separation"], ascending=[True, False, False])
        .groupby("indicator", as_index=False)
        .first()
    )
    return grouped.rename(
        columns={
            "target": "best_target",
            "abs_spearman_target": "best_abs_spearman_to_target",
            "abs_pearson_target": "best_abs_pearson_to_target",
            "abs_top_bottom_separation": "best_abs_top_bottom_separation",
        }
    )


def enrich_summary_with_reliability(summary: pd.DataFrame, reliability_summary: pd.DataFrame | None) -> pd.DataFrame:
    """Add simple reliability-aware heuristics when Phase 2 output is present."""
    if reliability_summary is None:
        return summary

    merged = summary.merge(reliability_summary.loc[:, [
        "indicator",
        "best_target",
        "best_abs_spearman_to_target",
        "best_abs_pearson_to_target",
        "best_abs_top_bottom_separation",
        "usable_rows",
    ]], left_on="feature", right_on="indicator", how="left")
    merged = merged.drop(columns=["indicator"])

    def classify(row: pd.Series) -> str:
        info = row.get("best_abs_spearman_to_target")
        redundancy = row.get("max_abs_spearman_corr")
        mean_redundancy = row.get("mean_abs_spearman_corr")
        if pd.isna(info):
            return "no_reliability_data"
        if info >= 0.08 and redundancy >= 0.90:
            return "informative_but_redundant"
        if info >= 0.08 and redundancy <= 0.75:
            return "informative_and_distinct"
        if info < 0.03 and mean_redundancy >= 0.60:
            return "weak_and_redundant"
        return "mixed"

    merged["reliability_redundancy_label"] = merged.apply(classify, axis=1)
    return merged


def build_redundancy_clusters(corr_table: pd.DataFrame, threshold: float) -> list[list[str]]:
    """Create simple connected components from high-correlation pairs."""
    adjacency: dict[str, set[str]] = defaultdict(set)
    for _, row in corr_table.iterrows():
        if pd.isna(row["abs_spearman_corr"]) and pd.isna(row["abs_pearson_corr"]):
            continue
        if max(row["abs_spearman_corr"], row["abs_pearson_corr"]) < threshold:
            continue
        feature_a = str(row["feature_a"])
        feature_b = str(row["feature_b"])
        adjacency[feature_a].add(feature_b)
        adjacency[feature_b].add(feature_a)

    visited: set[str] = set()
    clusters: list[list[str]] = []
    for feature in sorted(adjacency):
        if feature in visited:
            continue
        stack = [feature]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - visited))
        if len(component) >= 2:
            clusters.append(sorted(component))
    clusters.sort(key=lambda cluster: (-len(cluster), cluster))
    return clusters


def feature_family(feature: str) -> str:
    """Assign features to broad naming families for report grouping."""
    if feature.startswith("TS_"):
        return "TS trend strength"
    if feature.startswith("LR_"):
        return "LR regression slope"
    if feature.startswith("ER_"):
        return "ER efficiency ratio"
    if feature.startswith("RVR_"):
        return "RVR return-vol ratio"
    if feature.startswith("HMM_STATE_"):
        return "HMM raw latent states"
    if feature.startswith("P_") and feature.endswith("_HMM"):
        return "HMM semantic probabilities"
    if feature.startswith("P_") and feature.endswith("_CAL"):
        return "Hazard probabilities"
    if feature.endswith("_safe") or feature in {"direction_safe", "hard_risk_off_flag_safe"}:
        return "SAFE outputs"
    if feature in {"vol_20", "atr", "atr_pct", "parkinson_vol", "garman_klass_vol", "ewma_vol", "upside_semi_vol", "downside_semi_vol", "true_range"}:
        return "Volatility family"
    if feature in {"band_hi", "band_lo", "band_w", "band_pos", "dist_from_mean_vol_units"}:
        return "Structure / band family"
    if feature.startswith("run_") or feature.startswith("time_since_") or feature == "return_accel":
        return "Path / exhaustion family"
    return "Other"


def build_family_notes(corr_table: pd.DataFrame) -> list[str]:
    """Summarize likely same-idea groups from naming families and correlation pairs."""
    family_to_features: dict[str, list[str]] = defaultdict(list)
    for feature in sorted(set(corr_table["feature_a"]).union(set(corr_table["feature_b"]))):
        family_to_features[feature_family(feature)].append(feature)

    notes: list[str] = []
    for family, features in sorted(family_to_features.items()):
        if len(features) < 2:
            continue
        family_pairs = corr_table[
            corr_table["feature_a"].isin(features) & corr_table["feature_b"].isin(features)
        ].copy()
        if family_pairs.empty:
            continue
        best = family_pairs.sort_values("abs_spearman_corr", ascending=False).iloc[0]
        notes.append(
            f"- {family}: {', '.join(features)}. Strongest internal pair `{best['feature_a']}` / `{best['feature_b']}` has abs_spearman={best['abs_spearman_corr']:.4f}."
        )
    return notes


def render_markdown_report(corr_table: pd.DataFrame, summary: pd.DataFrame, reliability_available: bool) -> str:
    """Render a compact redundancy / orthogonality summary."""
    lines = [
        "# Feature Redundancy",
        "",
        "This report is descriptive, not causal. High correlation means two indicators often move together, not that one causes the other.",
        "",
    ]

    clusters = build_redundancy_clusters(corr_table, REDUNDANT_CLUSTER_THRESHOLD)
    lines.append("## Highly redundant clusters")
    if clusters:
        for cluster in clusters[:15]:
            lines.append(f"- {', '.join(cluster)}")
    else:
        lines.append("- none above the redundancy threshold")
    lines.append("")

    top_pairs = corr_table.sort_values(["abs_spearman_corr", "abs_pearson_corr"], ascending=[False, False]).head(15)
    lines.append("## Likely duplicate pairs")
    for _, row in top_pairs.iterrows():
        lines.append(
            f"- `{row['feature_a']}` / `{row['feature_b']}`: abs_spearman={row['abs_spearman_corr']:.4f}, abs_pearson={row['abs_pearson_corr']:.4f}"
        )
    lines.append("")

    unique = summary.dropna(subset=["mean_abs_spearman_corr", "max_abs_spearman_corr"]).copy()
    if reliability_available and "best_abs_spearman_to_target" in unique.columns:
        unique = unique.sort_values(
            ["best_abs_spearman_to_target", "mean_abs_spearman_corr", "max_abs_spearman_corr"],
            ascending=[False, True, True],
        )
        unique = unique.loc[
            (unique["best_abs_spearman_to_target"] >= 0.05) & (unique["max_abs_spearman_corr"] <= 0.80)
        ].head(10)
    else:
        unique = unique.sort_values(["mean_abs_spearman_corr", "max_abs_spearman_corr"], ascending=[True, True]).head(10)

    lines.append("## Potentially unique indicators")
    if not unique.empty:
        for _, row in unique.iterrows():
            extra = ""
            if reliability_available and pd.notna(row.get("best_abs_spearman_to_target", np.nan)):
                extra = f", best_target={row['best_target']}, abs_target_spearman={row['best_abs_spearman_to_target']:.4f}"
            lines.append(
                f"- `{row['feature']}`: mean_abs_spearman={row['mean_abs_spearman_corr']:.4f}, max_abs_spearman={row['max_abs_spearman_corr']:.4f}{extra}"
            )
    else:
        lines.append("- none met the current distinctiveness heuristic")
    lines.append("")

    if reliability_available and "reliability_redundancy_label" in summary.columns:
        lines.append("## Reliability-aware heuristic groups")
        for label in ("informative_but_redundant", "informative_and_distinct", "weak_and_redundant"):
            subset = summary.loc[summary["reliability_redundancy_label"] == label].copy()
            subset = subset.sort_values(
                ["best_abs_spearman_to_target", "max_abs_spearman_corr"],
                ascending=[False, False],
            ).head(10)
            lines.append(f"### {label}")
            if subset.empty:
                lines.append("- none")
            else:
                for _, row in subset.iterrows():
                    lines.append(
                        f"- `{row['feature']}`: best_target={row['best_target']}, abs_target_spearman={row['best_abs_spearman_to_target']:.4f}, max_abs_spearman={row['max_abs_spearman_corr']:.4f}"
                    )
            lines.append("")

    lines.append("## Same idea in different form")
    family_notes = build_family_notes(corr_table)
    if family_notes:
        lines.extend(family_notes)
    else:
        lines.append("- no multi-feature families were detected")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Run the first-pass SAFE feature redundancy analysis."""
    try:
        args = parse_args()
        feature_frame = load_numeric_feature_frame(args.features_csv)
        corr_table, pearson, spearman = build_pairwise_correlation_table(feature_frame)
        summary = build_redundancy_summary(pearson, spearman)

        reliability_summary = load_reliability_summary(args.indicator_reliability_csv)
        summary = enrich_summary_with_reliability(summary, reliability_summary)

        out_corr = Path(args.out_corr_csv)
        out_summary = Path(args.out_summary_csv)
        out_md = Path(args.out_md)
        out_corr.parent.mkdir(parents=True, exist_ok=True)
        out_summary.parent.mkdir(parents=True, exist_ok=True)
        out_md.parent.mkdir(parents=True, exist_ok=True)

        corr_table.to_csv(out_corr, index=False, float_format="%.8f")
        summary.to_csv(out_summary, index=False, float_format="%.8f")
        out_md.write_text(render_markdown_report(corr_table, summary, reliability_summary is not None), encoding="utf-8")

        print(f"Features analyzed: {feature_frame.shape[1]}")
        print(f"Feature pairs analyzed: {len(corr_table)}")
        print(f"Wrote correlation CSV: {out_corr}")
        print(f"Wrote summary CSV: {out_summary}")
        print(f"Wrote Markdown: {out_md}")
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Feature redundancy analysis failed: {exc}") from exc


if __name__ == "__main__":
    main()
