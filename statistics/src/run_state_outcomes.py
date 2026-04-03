from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_STATE_OUTCOMES_CSV_PATH,
    DEFAULT_STATES_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    OUT_DIR,
)


RETURN_TARGETS: tuple[str, ...] = ("ret_3d", "ret_5d", "ret_10d", "ret_20d")
EXCURSION_TARGETS: tuple[str, ...] = ("max_up_3d", "max_down_3d", "max_up_10d", "max_down_10d")
TOUCH_TARGETS: tuple[str, ...] = (
    "touch_up_2pct_3d",
    "touch_down_2pct_3d",
    "touch_up_2pct_10d",
    "touch_down_2pct_10d",
    "touch_up_5pct_10d",
    "touch_down_5pct_10d",
)
FIRST_TOUCH_TARGETS: tuple[str, ...] = ("first_touch_2pct_3d", "first_touch_2pct_10d")
TARGET_COLUMNS: tuple[str, ...] = RETURN_TARGETS + EXCURSION_TARGETS + TOUCH_TARGETS + FIRST_TOUCH_TARGETS

STATE_TYPE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("hmm_label", "state_hmm_label"),
    ("rule_compact", "state_rule_compact"),
    ("market_regime", "state_market_regime"),
)
MIN_MARKDOWN_SAMPLE = 30
MIN_HYBRID_SAMPLE = 30


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the state-to-outcome mapping stage."""
    parser = argparse.ArgumentParser(
        description="Map SAFE BTC market states to forward outcome summaries using features.csv, targets.csv, and states.csv.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument("--states-csv", default=str(DEFAULT_STATES_CSV_PATH), help="Default: ../out/states.csv")
    parser.add_argument("--out-csv", default=str(DEFAULT_STATE_OUTCOMES_CSV_PATH), help="Default: ../out/state_outcomes.csv")
    parser.add_argument("--out-md", default=str(OUT_DIR / "state_outcomes.md"), help="Default: ../out/state_outcomes.md")
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
    validated = validated.sort_values("date").reset_index(drop=True)
    return validated


def load_joined_inputs(
    features_path: str | Path,
    targets_path: str | Path,
    states_path: str | Path,
) -> pd.DataFrame:
    """Load and join features, targets, and states with one-to-one date validation."""
    features = _validate_frame("features", load_feature_csv(features_path))
    targets = _validate_frame("targets", load_feature_csv(targets_path))
    states = _validate_frame("states", load_feature_csv(states_path))

    required_state_columns = [column for _, column in STATE_TYPE_COLUMNS] + ["state_hmm_conf", "state_hmm_dom"]
    missing_state_columns = [column for column in required_state_columns if column not in states.columns]
    if missing_state_columns:
        raise ValueError(f"states.csv is missing required columns: {missing_state_columns}")

    missing_target_columns = [column for column in TARGET_COLUMNS if column not in targets.columns]
    if missing_target_columns:
        raise ValueError(f"targets.csv is missing required columns: {missing_target_columns}")

    feature_dates = set(features["date"])
    target_dates = set(targets["date"])
    state_dates = set(states["date"])
    if feature_dates != target_dates or feature_dates != state_dates:
        raise ValueError(
            "features.csv, targets.csv, and states.csv must contain the same anchor-date set for state-outcome mapping."
        )

    merged = features.merge(targets, on="date", how="inner", validate="one_to_one", suffixes=("", "_target"))
    merged = merged.merge(states, on="date", how="inner", validate="one_to_one", suffixes=("", "_state"))
    if merged.empty:
        raise ValueError("Joined state-outcome dataset is empty.")
    return merged.sort_values("date").reset_index(drop=True)


def build_state_key_frames(joined: pd.DataFrame) -> dict[str, pd.Series]:
    """Build the explicit state key series used for outcome aggregation."""
    state_keys = {
        state_key_type: joined[column].copy()
        for state_key_type, column in STATE_TYPE_COLUMNS
    }

    hybrid = joined["state_hmm_label"].astype("string") + "|" + joined["state_market_regime"].astype("string")
    valid_hybrid = joined["state_hmm_label"].notna() & joined["state_market_regime"].notna()
    hybrid = hybrid.where(valid_hybrid, np.nan)

    counts = hybrid.dropna().value_counts()
    keepable_hybrid = counts[counts >= MIN_HYBRID_SAMPLE].index
    if len(keepable_hybrid) > 0:
        state_keys["hybrid"] = hybrid.where(hybrid.isin(keepable_hybrid), np.nan)
    return state_keys


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _summarize_numeric_target(group: pd.DataFrame, target: str, is_return: bool) -> dict[str, Any]:
    values = _safe_numeric(group[target]).dropna()
    if values.empty:
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
        "mean": float(values.mean()),
        "median": float(values.median()),
        "std": float(values.std(ddof=0)),
        "p25": float(values.quantile(0.25)),
        "p75": float(values.quantile(0.75)),
        "win_rate": float((values > 0).mean()) if is_return else np.nan,
        "event_rate": np.nan,
        "up_rate": np.nan,
        "down_rate": np.nan,
        "both_same_bar_rate": np.nan,
        "none_rate": np.nan,
    }


def _summarize_binary_target(group: pd.DataFrame, target: str) -> dict[str, Any]:
    values = _safe_numeric(group[target]).dropna()
    if values.empty:
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
        "mean": np.nan,
        "median": np.nan,
        "std": np.nan,
        "p25": np.nan,
        "p75": np.nan,
        "win_rate": np.nan,
        "event_rate": float(values.mean()),
        "up_rate": np.nan,
        "down_rate": np.nan,
        "both_same_bar_rate": np.nan,
        "none_rate": np.nan,
    }


def _summarize_first_touch_target(group: pd.DataFrame, target: str) -> dict[str, Any]:
    values = group[target].dropna().astype(str)
    if values.empty:
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

    counts = values.value_counts(normalize=True)
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


def summarize_state_target(group: pd.DataFrame, state_key_type: str, state_key: str, target: str) -> dict[str, Any]:
    """Summarize one target distribution inside one explicit state bucket."""
    row: dict[str, Any] = {
        "state_key_type": state_key_type,
        "state_key": state_key,
        "target": target,
        "sample_count": int(len(group)),
        "first_date": group["date"].min().strftime("%Y-%m-%d"),
        "last_date": group["date"].max().strftime("%Y-%m-%d"),
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

    if target in RETURN_TARGETS:
        row.update(_summarize_numeric_target(group, target, is_return=True))
    elif target in EXCURSION_TARGETS:
        row.update(_summarize_numeric_target(group, target, is_return=False))
    elif target in TOUCH_TARGETS:
        row.update(_summarize_binary_target(group, target))
    elif target in FIRST_TOUCH_TARGETS:
        row.update(_summarize_first_touch_target(group, target))
    else:
        raise ValueError(f"Unsupported target: {target}")
    return row


def compute_state_outcomes(joined: pd.DataFrame) -> pd.DataFrame:
    """Compute tidy state-to-outcome summaries for each requested state system."""
    rows: list[dict[str, Any]] = []
    state_key_frames = build_state_key_frames(joined)

    for state_key_type, state_series in state_key_frames.items():
        working = joined.loc[:, ["date", *TARGET_COLUMNS]].copy()
        working["state_key"] = state_series
        working = working.dropna(subset=["state_key"]).copy()
        if working.empty:
            continue

        for state_key, group in working.groupby("state_key", sort=True):
            group = group.sort_values("date")
            for target in TARGET_COLUMNS:
                target_rows = group.loc[group[target].notna()].copy()
                if target_rows.empty:
                    rows.append(
                        {
                            "state_key_type": state_key_type,
                            "state_key": str(state_key),
                            "target": target,
                            "sample_count": 0,
                            "first_date": "",
                            "last_date": "",
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
                    )
                    continue
                rows.append(summarize_state_target(target_rows, state_key_type, str(state_key), target))

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("State outcome mapping produced no rows.")
    return out.sort_values(["state_key_type", "state_key", "target"]).reset_index(drop=True)


def export_summary_csv(summary: pd.DataFrame, out_path: Path) -> None:
    """Write the tidy state-outcome table as a plain CSV artifact.

    This output is not a date-indexed feature store. Each row summarizes one
    (state_key_type, state_key, target) combination.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_path, index=False, float_format="%.8f")


def build_state_snapshot(summary: pd.DataFrame, state_key_type: str) -> pd.DataFrame:
    """Pivot a small set of target summaries into one row per state for ranking and interpretation."""
    subset = summary.loc[summary["state_key_type"] == state_key_type].copy()
    if subset.empty:
        return pd.DataFrame()

    metrics_of_interest = {
        "ret_10d": ["sample_count", "mean", "median", "win_rate"],
        "max_up_10d": ["mean"],
        "max_down_10d": ["mean"],
        "touch_up_2pct_10d": ["event_rate"],
        "touch_down_2pct_10d": ["event_rate"],
        "first_touch_2pct_10d": ["up_rate", "down_rate", "both_same_bar_rate", "none_rate"],
    }

    rows: list[dict[str, Any]] = []
    for state_key, group in subset.groupby("state_key", sort=True):
        row: dict[str, Any] = {"state_key": state_key}
        for target, metrics in metrics_of_interest.items():
            target_rows = group.loc[group["target"] == target]
            if target_rows.empty:
                continue
            target_row = target_rows.iloc[0]
            for metric in metrics:
                row[f"{target}__{metric}"] = target_row[metric]
        rows.append(row)
    return pd.DataFrame(rows)


def add_derived_asymmetry(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Add simple asymmetric outcome diagnostics used in the markdown narrative."""
    if snapshot.empty:
        return snapshot
    derived = snapshot.copy()
    derived["touch_asymmetry_2pct_10d"] = derived.get("touch_up_2pct_10d__event_rate", np.nan) - derived.get(
        "touch_down_2pct_10d__event_rate",
        np.nan,
    )
    derived["excursion_asymmetry_10d"] = derived.get("max_up_10d__mean", np.nan) - derived.get("max_down_10d__mean", np.nan).abs()
    return derived


def _format_pct(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _format_num(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.4f}"


def _top_states(snapshot: pd.DataFrame, metric: str, ascending: bool, limit: int = 5) -> pd.DataFrame:
    usable = snapshot.dropna(subset=[metric]).copy()
    usable = usable.loc[usable["ret_10d__sample_count"].fillna(0) >= MIN_MARKDOWN_SAMPLE].copy()
    if usable.empty:
        return usable
    return usable.sort_values(metric, ascending=ascending).head(limit)


def _state_line(row: pd.Series) -> str:
    sample_count = int(row.get("ret_10d__sample_count", 0) or 0)
    stability = "stable" if sample_count >= MIN_MARKDOWN_SAMPLE else "low_sample"
    return (
        f"- `{row['state_key']}` ({stability}, n={sample_count}): "
        f"10d median return={_format_pct(row.get('ret_10d__median'))}, "
        f"10d win rate={_format_pct(row.get('ret_10d__win_rate'))}, "
        f"touch asymmetry={_format_pct(row.get('touch_asymmetry_2pct_10d'))}, "
        f"excursion asymmetry={_format_pct(row.get('excursion_asymmetry_10d'))}"
    )


def render_markdown_report(summary: pd.DataFrame) -> str:
    """Render a compact state-to-outcome report with honest sample-size handling."""
    hmm_snapshot = add_derived_asymmetry(build_state_snapshot(summary, "hmm_label"))
    rule_snapshot = add_derived_asymmetry(build_state_snapshot(summary, "rule_compact"))
    regime_snapshot = add_derived_asymmetry(build_state_snapshot(summary, "market_regime"))
    hybrid_snapshot = add_derived_asymmetry(build_state_snapshot(summary, "hybrid"))

    latest_rule_states = summary.loc[summary["state_key_type"] == "market_regime", "state_key"].dropna().nunique()

    lines = [
        "# State Outcomes",
        "",
        "This report is descriptive, not predictive. It summarizes what historically happened next after each explicit SAFE state on the same anchor date.",
        "",
        f"Low-sample states are flagged as unstable below n={MIN_MARKDOWN_SAMPLE}.",
        "",
        "## HMM States",
        "",
        "### Forward return tendencies by HMM state",
    ]

    for _, row in _top_states(hmm_snapshot, "ret_10d__median", ascending=False).iterrows():
        lines.append(_state_line(row))
    if _top_states(hmm_snapshot, "ret_10d__median", ascending=False).empty:
        lines.append("- none")

    lines.extend(["", "### Downside / upside asymmetry by HMM state"])
    for _, row in _top_states(hmm_snapshot, "touch_asymmetry_2pct_10d", ascending=False).iterrows():
        lines.append(_state_line(row))
    if _top_states(hmm_snapshot, "touch_asymmetry_2pct_10d", ascending=False).empty:
        lines.append("- none")

    lines.extend(["", "## Rule-Based Market States", "", "### Top bullish-looking states"])
    for _, row in _top_states(rule_snapshot, "ret_10d__median", ascending=False).iterrows():
        lines.append(_state_line(row))
    if _top_states(rule_snapshot, "ret_10d__median", ascending=False).empty:
        lines.append("- none")

    lines.extend(["", "### Top downside-risk states"])
    for _, row in _top_states(rule_snapshot, "touch_asymmetry_2pct_10d", ascending=True).iterrows():
        lines.append(_state_line(row))
    if _top_states(rule_snapshot, "touch_asymmetry_2pct_10d", ascending=True).empty:
        lines.append("- none")

    lines.extend(["", "### Best rebound setups"])
    rebound_candidates = rule_snapshot.dropna(subset=["first_touch_2pct_10d__down_rate", "first_touch_2pct_10d__up_rate"]).copy()
    rebound_candidates = rebound_candidates.loc[rebound_candidates["ret_10d__sample_count"].fillna(0) >= MIN_MARKDOWN_SAMPLE]
    if not rebound_candidates.empty:
        rebound_candidates["rebound_profile"] = (
            rebound_candidates["first_touch_2pct_10d__down_rate"] - rebound_candidates["first_touch_2pct_10d__up_rate"]
        ) + rebound_candidates["touch_asymmetry_2pct_10d"].fillna(0.0)
        for _, row in rebound_candidates.sort_values("rebound_profile", ascending=True).head(5).iterrows():
            lines.append(_state_line(row))
    else:
        lines.append("- none")

    lines.extend(["", "### States with weak / noisy evidence"])
    noisy = rule_snapshot.loc[rule_snapshot["ret_10d__sample_count"].fillna(0) < MIN_MARKDOWN_SAMPLE].copy()
    if not noisy.empty:
        for _, row in noisy.head(10).iterrows():
            lines.append(
                f"- `{row['state_key']}`: low confidence due to small sample (n={int(row.get('ret_10d__sample_count', 0) or 0)})."
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Practical Interpretation",
            "",
        ]
    )

    if not regime_snapshot.empty:
        constructive = _top_states(regime_snapshot, "ret_10d__median", ascending=False, limit=1)
        stressed = _top_states(regime_snapshot, "touch_asymmetry_2pct_10d", ascending=True, limit=1)
        noisy_regime = regime_snapshot.loc[regime_snapshot["ret_10d__sample_count"].fillna(0) < MIN_MARKDOWN_SAMPLE].copy()
        noisy_regime = noisy_regime.sort_values("ret_10d__sample_count", ascending=True).head(1)

        if not constructive.empty:
            row = constructive.iloc[0]
            lines.append(
                f"- `{row['state_key']}` tends to carry the strongest 10d return profile among market-regime states, with median return {_format_pct(row.get('ret_10d__median'))} and upside touch asymmetry {_format_pct(row.get('touch_asymmetry_2pct_10d'))}."
            )
        if not stressed.empty:
            row = stressed.iloc[0]
            lines.append(
                f"- `{row['state_key']}` shows the weakest 10d touch balance, with downside dominating upside by {_format_pct(abs(row.get('touch_asymmetry_2pct_10d')))} and excursion asymmetry {_format_pct(row.get('excursion_asymmetry_10d'))}."
            )
        if not noisy_regime.empty:
            row = noisy_regime.iloc[0]
            lines.append(
                f"- `{row['state_key']}` remains noisy and should not be overinterpreted when only {int(row.get('ret_10d__sample_count', 0) or 0)} historical examples are available."
            )
        else:
            lines.append("- All market-regime synthesis states currently exceed the low-sample cutoff, so the main caution is dispersion rather than sample scarcity.")

    if not hybrid_snapshot.empty:
        stable_hybrid = int(hybrid_snapshot["ret_10d__sample_count"].fillna(0).ge(MIN_MARKDOWN_SAMPLE).sum())
        lines.append(f"- Hybrid HMM+rule states were included where sample size stayed usable; {stable_hybrid} hybrid states currently meet the stable-sample cutoff.")
    else:
        lines.append("- Hybrid HMM+rule states were omitted because sample sizes were too sparse to stay usable.")

    lines.append("")
    return "\n".join(lines)


def print_summary(summary: pd.DataFrame, joined_rows: int, out_csv: Path) -> None:
    """Print a compact CLI summary for the state-outcome mapping stage."""
    state_counts = (
        summary.loc[:, ["state_key_type", "state_key"]]
        .drop_duplicates()
        .groupby("state_key_type")
        .size()
        .sort_index()
    )
    print(f"Wrote: {out_csv}")
    print(f"Joined rows: {joined_rows}")
    print("Distinct states:")
    for state_key_type, count in state_counts.items():
        print(f"  {state_key_type}: {int(count)}")


def main() -> None:
    """Run the SAFE v4.0 Phase 5 state-to-outcome mapping stage."""
    try:
        args = parse_args()
        joined = load_joined_inputs(args.features_csv, args.targets_csv, args.states_csv)
        summary = compute_state_outcomes(joined)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_summary_csv(summary, out_csv)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown_report(summary), encoding="utf-8")

        print_summary(summary, len(joined), out_csv)
        print(f"Markdown: {out_md}")
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"State outcome mapping failed: {exc}") from exc


if __name__ == "__main__":
    main()
