from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import DEFAULT_DECISION_ANALYSIS_CSV_PATH, DEFAULT_DECISION_VALIDATION_CSV_PATH, DEFAULT_TARGETS_CSV_PATH, OUT_DIR


RETURN_TARGETS: tuple[str, ...] = ("ret_3d", "ret_5d", "ret_10d", "ret_20d")
NUMERIC_TARGETS: tuple[str, ...] = ("ret_3d", "ret_5d", "ret_10d", "ret_20d", "max_up_10d", "max_down_10d")
BINARY_TARGETS: tuple[str, ...] = ("touch_up_2pct_10d", "touch_down_2pct_10d")
FIRST_TOUCH_TARGETS: tuple[str, ...] = ("first_touch_2pct_10d",)
TARGET_COLUMNS: tuple[str, ...] = RETURN_TARGETS + ("max_up_10d", "max_down_10d") + BINARY_TARGETS + FIRST_TOUCH_TARGETS

SCORE_COLUMNS: tuple[str, ...] = ("risk_score", "opportunity_score", "asymmetry_score")
BUCKET_COLUMNS: tuple[str, ...] = ("risk_bucket", "opportunity_bucket")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for SAFE decision-layer validation."""
    parser = argparse.ArgumentParser(
        description="Validate SAFE decision scores, buckets, and tilts against realized forward BTC outcomes.",
    )
    parser.add_argument(
        "--decision-analysis-csv",
        default=str(DEFAULT_DECISION_ANALYSIS_CSV_PATH),
        help="Default: ../out/decision_analysis.csv",
    )
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_DECISION_VALIDATION_CSV_PATH),
        help="Default: ../out/decision_validation.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(OUT_DIR / "decision_validation.md"),
        help="Default: ../out/decision_validation.md",
    )
    return parser.parse_args()


def _validate_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a date-first SAFE CSV store before joining."""
    if frame.empty:
        raise ValueError(f"{name} input is empty.")
    if "date" not in frame.columns:
        raise ValueError(f"{name} input must contain a 'date' column.")
    if frame["date"].duplicated().any():
        duplicates = frame.loc[frame["date"].duplicated(), "date"].dt.strftime("%Y-%m-%d").head(5).tolist()
        raise ValueError(f"{name} input has duplicate dates: {duplicates}")
    validated = frame.copy()
    validated["date"] = pd.to_datetime(validated["date"], errors="raise")
    return validated.sort_values("date").reset_index(drop=True)


def load_aligned_inputs(decision_path: str | Path, targets_path: str | Path) -> pd.DataFrame:
    """Load and one-to-one align decision analysis and realized targets by anchor date."""
    decisions = _validate_frame("decision_analysis", load_feature_csv(decision_path))
    targets = _validate_frame("targets", load_feature_csv(targets_path))

    missing_decision_columns = [column for column in (*SCORE_COLUMNS, *BUCKET_COLUMNS, "decision_tilt") if column not in decisions.columns]
    if missing_decision_columns:
        raise ValueError(f"decision_analysis.csv is missing required columns: {missing_decision_columns}")

    missing_target_columns = [column for column in TARGET_COLUMNS if column not in targets.columns]
    if missing_target_columns:
        raise ValueError(f"targets.csv is missing required validation targets: {missing_target_columns}")

    if set(decisions["date"]) != set(targets["date"]):
        raise ValueError("decision_analysis.csv and targets.csv must contain the same anchor-date set.")

    merged = decisions.merge(targets, on="date", how="inner", validate="one_to_one", suffixes=("", "_target"))
    if merged.empty:
        raise ValueError("Joined decision validation dataset is empty.")
    return merged.sort_values("date").reset_index(drop=True)


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _target_series(group: pd.DataFrame, target: str) -> pd.Series:
    if target in FIRST_TOUCH_TARGETS:
        return group[target].astype("string")
    return _safe_numeric(group[target])


def _spearman_corr(left: pd.Series, right: pd.Series) -> float:
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return float("nan")
    return float(left.corr(right, method="spearman"))


def _numeric_summary(values: pd.Series, target: str) -> dict[str, Any]:
    clean = _safe_numeric(values).dropna()
    if clean.empty:
        return {
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "p25": np.nan,
            "p75": np.nan,
            "win_rate": np.nan,
            "event_rate": np.nan,
            "up_rate": np.nan,
            "down_rate": np.nan,
            "both_same_bar_rate": np.nan,
            "none_rate": np.nan,
        }
    return {
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "std": float(clean.std(ddof=0)),
        "p25": float(clean.quantile(0.25)),
        "p75": float(clean.quantile(0.75)),
        "win_rate": float((clean > 0).mean()) if target in RETURN_TARGETS else np.nan,
        "event_rate": float(clean.mean()) if target in BINARY_TARGETS else np.nan,
        "up_rate": np.nan,
        "down_rate": np.nan,
        "both_same_bar_rate": np.nan,
        "none_rate": np.nan,
    }


def _first_touch_summary(values: pd.Series) -> dict[str, Any]:
    clean = values.dropna().astype(str)
    if clean.empty:
        return {
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "p25": np.nan,
            "p75": np.nan,
            "win_rate": np.nan,
            "event_rate": np.nan,
            "up_rate": np.nan,
            "down_rate": np.nan,
            "both_same_bar_rate": np.nan,
            "none_rate": np.nan,
        }
    counts = clean.value_counts(normalize=True)
    return {
        "mean": np.nan,
        "median": np.nan,
        "std": np.nan,
        "p25": np.nan,
        "p75": np.nan,
        "win_rate": np.nan,
        "event_rate": np.nan,
        "up_rate": float(counts.get("up", 0.0)),
        "down_rate": float(counts.get("down", 0.0)),
        "both_same_bar_rate": float(counts.get("both_same_bar", 0.0)),
        "none_rate": float(counts.get("none", 0.0)),
    }


def _bucket_monotonicity(summary_rows: list[dict[str, Any]], metric: str) -> float:
    frame = pd.DataFrame(summary_rows)
    if frame.empty or metric not in frame.columns:
        return float("nan")
    frame = frame.dropna(subset=["object_name", metric]).copy()
    if frame.empty or frame["object_name"].nunique() < 2:
        return float("nan")
    bucket_index = pd.to_numeric(frame["object_name"], errors="coerce")
    valid = pd.DataFrame({"bucket_index": bucket_index, "metric": pd.to_numeric(frame[metric], errors="coerce")}).dropna()
    if len(valid) < 2:
        return float("nan")
    return float(valid["bucket_index"].corr(valid["metric"], method="spearman"))


def _summarize_group(
    object_type: str,
    object_name: str,
    target: str,
    group: pd.DataFrame,
    *,
    spearman_corr: float = np.nan,
    monotonicity_score: float = np.nan,
) -> dict[str, Any]:
    values = _target_series(group, target)
    base = {
        "object_type": object_type,
        "object_name": object_name,
        "target": target,
        "sample_count": int(values.dropna().shape[0]),
        "mean": np.nan,
        "median": np.nan,
        "std": np.nan,
        "p25": np.nan,
        "p75": np.nan,
        "win_rate": np.nan,
        "event_rate": np.nan,
        "up_rate": np.nan,
        "down_rate": np.nan,
        "both_same_bar_rate": np.nan,
        "none_rate": np.nan,
        "spearman_corr": spearman_corr,
        "monotonicity_score": monotonicity_score,
    }
    if target in FIRST_TOUCH_TARGETS:
        base.update(_first_touch_summary(values))
    else:
        base.update(_numeric_summary(values, target))
    return base


def validate_bucket_family(data: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    """Validate realized outcomes across risk/opportunity buckets."""
    rows: list[dict[str, Any]] = []
    object_type = bucket_col
    usable = data.dropna(subset=[bucket_col]).copy()
    if usable.empty:
        return pd.DataFrame()

    for target in TARGET_COLUMNS:
        target_frame = usable.dropna(subset=[target]).copy()
        if target_frame.empty:
            continue
        group_rows: list[dict[str, Any]] = []
        for bucket_value, group in target_frame.groupby(bucket_col, sort=True):
            group_rows.append(
                _summarize_group(
                    object_type,
                    str(int(float(bucket_value))),
                    target,
                    group,
                )
            )

        metric = "median" if target in RETURN_TARGETS else "event_rate" if target in BINARY_TARGETS else "up_rate" if target in FIRST_TOUCH_TARGETS else "mean"
        monotonicity = _bucket_monotonicity(group_rows, metric)
        for row in group_rows:
            row["monotonicity_score"] = monotonicity
        rows.extend(group_rows)

    return pd.DataFrame(rows)


def validate_decision_tilt(data: pd.DataFrame) -> pd.DataFrame:
    """Validate realized outcomes across discrete decision_tilt labels."""
    usable = data.dropna(subset=["decision_tilt"]).copy()
    if usable.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for target in TARGET_COLUMNS:
        target_frame = usable.dropna(subset=[target]).copy()
        if target_frame.empty:
            continue
        for tilt_value, group in target_frame.groupby("decision_tilt", sort=True):
            rows.append(_summarize_group("decision_tilt", str(tilt_value), target, group))
    return pd.DataFrame(rows)


def validate_score_correlations(data: pd.DataFrame) -> pd.DataFrame:
    """Validate monotonic relationship between continuous scores and realized targets."""
    rows: list[dict[str, Any]] = []
    for score_col in SCORE_COLUMNS:
        for target in TARGET_COLUMNS:
            pair = data.loc[:, [score_col, target]].copy()
            pair[score_col] = _safe_numeric(pair[score_col])
            if target in FIRST_TOUCH_TARGETS:
                pair = pair.dropna(subset=[score_col, target]).copy()
                if pair.empty:
                    continue
                up_corr = _spearman_corr(pair[score_col], (pair[target].astype(str) == "up").astype(float))
                down_corr = _spearman_corr(pair[score_col], (pair[target].astype(str) == "down").astype(float))
                rows.append(
                    {
                        "object_type": "score_corr",
                        "object_name": score_col,
                        "target": target,
                        "sample_count": int(len(pair)),
                        "mean": np.nan,
                        "median": np.nan,
                        "std": np.nan,
                        "p25": np.nan,
                        "p75": np.nan,
                        "win_rate": np.nan,
                        "event_rate": np.nan,
                        "up_rate": float((pair[target].astype(str) == "up").mean()),
                        "down_rate": float((pair[target].astype(str) == "down").mean()),
                        "both_same_bar_rate": float((pair[target].astype(str) == "both_same_bar").mean()),
                        "none_rate": float((pair[target].astype(str) == "none").mean()),
                        "spearman_corr": up_corr,
                        "monotonicity_score": down_corr,
                    }
                )
                continue

            pair[target] = _safe_numeric(pair[target])
            pair = pair.dropna(subset=[score_col, target]).copy()
            if pair.empty:
                continue
            rows.append(
                {
                    "object_type": "score_corr",
                    "object_name": score_col,
                    "target": target,
                    "sample_count": int(len(pair)),
                    "mean": float(pair[target].mean()) if target not in BINARY_TARGETS else np.nan,
                    "median": float(pair[target].median()) if target in NUMERIC_TARGETS else np.nan,
                    "std": float(pair[target].std(ddof=0)) if target in NUMERIC_TARGETS else np.nan,
                    "p25": float(pair[target].quantile(0.25)) if target in NUMERIC_TARGETS else np.nan,
                    "p75": float(pair[target].quantile(0.75)) if target in NUMERIC_TARGETS else np.nan,
                    "win_rate": float((pair[target] > 0).mean()) if target in RETURN_TARGETS else np.nan,
                    "event_rate": float(pair[target].mean()) if target in BINARY_TARGETS else np.nan,
                    "up_rate": np.nan,
                    "down_rate": np.nan,
                    "both_same_bar_rate": np.nan,
                    "none_rate": np.nan,
                    "spearman_corr": _spearman_corr(pair[score_col], pair[target]),
                    "monotonicity_score": np.nan,
                }
            )
    return pd.DataFrame(rows)


def build_validation_table(data: pd.DataFrame) -> pd.DataFrame:
    """Build the tidy decision validation table."""
    parts = [validate_bucket_family(data, bucket_col) for bucket_col in BUCKET_COLUMNS]
    parts.append(validate_decision_tilt(data))
    parts.append(validate_score_correlations(data))
    parts = [part for part in parts if not part.empty]
    if not parts:
        raise ValueError("Decision validation produced no rows.")
    out = pd.concat(parts, axis=0, ignore_index=True)
    return out.sort_values(["object_type", "object_name", "target"]).reset_index(drop=True)


def export_csv(frame: pd.DataFrame, path: str | Path) -> None:
    """Write the tidy validation artifact as a plain CSV."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False, float_format="%.8f")


def _fmt_pct(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.4f}"


def _best_bucket(validation: pd.DataFrame, object_type: str, target: str, metric: str, ascending: bool) -> pd.DataFrame:
    subset = validation.loc[(validation["object_type"] == object_type) & (validation["target"] == target)].copy()
    subset = subset.dropna(subset=[metric])
    if subset.empty:
        return subset
    return subset.sort_values(metric, ascending=ascending).head(3)


def render_markdown(validation: pd.DataFrame) -> str:
    """Render a compact markdown summary of decision-layer validation."""
    opp_best = _best_bucket(validation, "opportunity_bucket", "ret_10d", "median", ascending=False)
    risk_worst = _best_bucket(validation, "risk_bucket", "max_down_10d", "mean", ascending=True)
    tilt_returns = _best_bucket(validation, "decision_tilt", "ret_10d", "median", ascending=False)
    tilt_downside = _best_bucket(validation, "decision_tilt", "touch_down_2pct_10d", "event_rate", ascending=False)

    opp_ret = validation.loc[(validation["object_type"] == "opportunity_bucket") & (validation["target"] == "ret_10d")].copy()
    opp_touch = validation.loc[(validation["object_type"] == "opportunity_bucket") & (validation["target"] == "touch_up_2pct_10d")].copy()
    risk_ret = validation.loc[(validation["object_type"] == "risk_bucket") & (validation["target"] == "ret_10d")].copy()
    risk_down = validation.loc[(validation["object_type"] == "risk_bucket") & (validation["target"] == "max_down_10d")].copy()
    risk_touch = validation.loc[(validation["object_type"] == "risk_bucket") & (validation["target"] == "touch_down_2pct_10d")].copy()

    score_corrs = validation.loc[validation["object_type"] == "score_corr"].copy()
    score_ret = score_corrs.loc[score_corrs["target"] == "ret_10d"].copy()
    score_down = score_corrs.loc[score_corrs["target"] == "max_down_10d"].copy()
    score_touch_up = score_corrs.loc[score_corrs["target"] == "touch_up_2pct_10d"].copy()
    score_touch_down = score_corrs.loc[score_corrs["target"] == "touch_down_2pct_10d"].copy()

    lines = [
        "# Decision Validation",
        "",
        "This is not a trading backtest. It is a forward outcome validation of the descriptive decision layer against later realized BTC outcomes.",
        "",
        "## Opportunity Buckets",
        "",
    ]

    for _, row in opp_best.iterrows():
        touch_match = opp_touch.loc[opp_touch["object_name"] == row["object_name"], "event_rate"]
        lines.append(
            f"- bucket `{row['object_name']}`: realized 10d median return {_fmt_pct(row['median'])}, "
            f"10d win rate {_fmt_pct(row['win_rate'])}, "
            f"mean 10d upside touch rate {_fmt_pct(touch_match.iloc[0] if not touch_match.empty else np.nan)}, "
            f"sample_count={int(row['sample_count'])}."
        )
    if opp_best.empty:
        lines.append("- none")

    opp_mono_ret = opp_ret["monotonicity_score"].dropna().iloc[0] if not opp_ret["monotonicity_score"].dropna().empty else np.nan
    opp_mono_touch = opp_touch["monotonicity_score"].dropna().iloc[0] if not opp_touch["monotonicity_score"].dropna().empty else np.nan
    lines.append(f"- opportunity bucket monotonicity vs realized 10d median return: `{_fmt_num(opp_mono_ret)}`")
    lines.append(f"- opportunity bucket monotonicity vs realized 10d upside touch rate: `{_fmt_num(opp_mono_touch)}`")

    lines.extend(["", "## Risk Buckets", ""])
    for _, row in risk_worst.iterrows():
        ret_match = risk_ret.loc[risk_ret["object_name"] == row["object_name"], "median"]
        lines.append(
            f"- bucket `{row['object_name']}`: realized mean 10d downside excursion {_fmt_pct(row['mean'])}, "
            f"with ret_10d median {_fmt_pct(ret_match.iloc[0] if not ret_match.empty else np.nan)}, "
            f"sample_count={int(row['sample_count'])}."
        )
    if risk_worst.empty:
        lines.append("- none")

    risk_mono_down = risk_down["monotonicity_score"].dropna().iloc[0] if not risk_down["monotonicity_score"].dropna().empty else np.nan
    risk_mono_touch = risk_touch["monotonicity_score"].dropna().iloc[0] if not risk_touch["monotonicity_score"].dropna().empty else np.nan
    lines.append(f"- risk bucket monotonicity vs realized mean downside excursion: `{_fmt_num(risk_mono_down)}`")
    lines.append(f"- risk bucket monotonicity vs realized downside touch rate: `{_fmt_num(risk_mono_touch)}`")

    lines.extend(["", "## Asymmetry Score", ""])
    asym_ret = score_ret.loc[score_ret["object_name"] == "asymmetry_score", "spearman_corr"]
    asym_touch_up = score_touch_up.loc[score_touch_up["object_name"] == "asymmetry_score", "spearman_corr"]
    asym_touch_down = score_touch_down.loc[score_touch_down["object_name"] == "asymmetry_score", "spearman_corr"]
    lines.append(f"- Spearman vs realized ret_10d: `{_fmt_num(asym_ret.iloc[0] if not asym_ret.empty else np.nan)}`")
    lines.append(f"- Spearman vs realized touch_up_2pct_10d: `{_fmt_num(asym_touch_up.iloc[0] if not asym_touch_up.empty else np.nan)}`")
    lines.append(f"- Spearman vs realized touch_down_2pct_10d: `{_fmt_num(asym_touch_down.iloc[0] if not asym_touch_down.empty else np.nan)}`")

    lines.extend(["", "## Decision Tilt Labels", ""])
    for _, row in tilt_returns.iterrows():
        lines.append(
            f"- `{row['object_name']}`: realized 10d median return {_fmt_pct(row['median'])}, "
            f"10d win rate {_fmt_pct(row['win_rate'])}, sample_count={int(row['sample_count'])}."
        )
    if tilt_returns.empty:
        lines.append("- none")
    for _, row in tilt_downside.iterrows():
        lines.append(
            f"- highest downside-touch tilt: `{row['object_name']}` with realized touch_down_2pct_10d rate {_fmt_pct(row['event_rate'])}."
        )
        break

    lines.extend(["", "## Practical Interpretation", ""])
    opp_corr = score_ret.loc[score_ret["object_name"] == "opportunity_score", "spearman_corr"]
    risk_corr = score_down.loc[score_down["object_name"] == "risk_score", "spearman_corr"]
    asym_corr = score_ret.loc[score_ret["object_name"] == "asymmetry_score", "spearman_corr"]
    lines.append(
        f"- opportunity_score vs realized ret_10d Spearman: `{_fmt_num(opp_corr.iloc[0] if not opp_corr.empty else np.nan)}`. "
        "This shows whether higher opportunity ranking actually lines up with better forward returns."
    )
    lines.append(
        f"- risk_score vs realized max_down_10d Spearman: `{_fmt_num(risk_corr.iloc[0] if not risk_corr.empty else np.nan)}`. "
        "More negative values indicate that higher risk scores line up with worse downside excursions."
    )
    lines.append(
        f"- asymmetry_score vs realized ret_10d Spearman: `{_fmt_num(asym_corr.iloc[0] if not asym_corr.empty else np.nan)}`. "
        "This is a direct check on whether positive asymmetry readings actually translate into better forward direction."
    )
    if pd.notna(opp_mono_ret) and opp_mono_ret >= 0.4 and pd.notna(opp_mono_touch) and opp_mono_touch >= 0.6:
        lines.append("- opportunity buckets look directionally useful: higher buckets tend to align with better forward returns and stronger upside touch behavior.")
    else:
        lines.append("- opportunity buckets do not show clean ordering across all outcomes, so treat them as soft ranking hints rather than stable thresholds.")
    if pd.notna(risk_mono_down) and risk_mono_down <= -0.6 and pd.notna(risk_mono_touch) and risk_mono_touch >= 0.6:
        lines.append("- risk buckets look practically useful for identifying danger: higher risk buckets line up with worse downside excursions and higher downside-touch rates.")
    else:
        lines.append("- risk buckets show only mixed danger ordering, so they should be used with caution rather than as hard stop/go rules.")
    lines.append("- If bucket monotonicity is weak or inconsistent, use the scores as soft ranking hints rather than hard thresholds.")
    lines.append("- If a decision_tilt label has few samples or noisy realized outcomes, it should not be overinterpreted as an execution rule.")
    lines.append("")
    return "\n".join(lines)


def print_summary(validation: pd.DataFrame, joined_rows: int, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the decision validation stage."""
    bucket_rows = validation.loc[validation["object_type"].isin(["risk_bucket", "opportunity_bucket"])]
    validated_buckets = bucket_rows.loc[:, ["object_type", "object_name"]].drop_duplicates().shape[0]
    print(f"Joined rows: {joined_rows}")
    print(f"Validated buckets: {validated_buckets}")
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


def main() -> None:
    """Run SAFE v4.0 Phase 8 walk-forward-style decision validation."""
    try:
        args = parse_args()
        aligned = load_aligned_inputs(args.decision_analysis_csv, args.targets_csv)
        validation = build_validation_table(aligned)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_csv(validation, out_csv)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(validation), encoding="utf-8")

        print_summary(validation, len(aligned), out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Decision validation failed: {exc}") from exc


if __name__ == "__main__":
    main()
