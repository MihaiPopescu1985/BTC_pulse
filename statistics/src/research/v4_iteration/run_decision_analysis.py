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

from src.data.feature_store import export_feature_csv, load_feature_csv
from src.path_config import (
    DEFAULT_DECISION_ANALYSIS_CSV_PATH,
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_STATE_OUTCOMES_CSV_PATH,
    DEFAULT_STATES_CSV_PATH,
    OUT_DIR,
)


DECISION_COLUMNS: tuple[str, ...] = (
    "risk_score",
    "opportunity_score",
    "asymmetry_score",
    "risk_bucket",
    "opportunity_bucket",
    "state_market_regime",
    "state_hmm_label",
    "historical_source",
    "expected_ret_10d",
    "expected_ret_10d_win_rate",
    "expected_max_up_10d",
    "expected_max_down_10d",
    "expected_touch_up_2pct_10d",
    "expected_touch_down_2pct_10d",
    "expected_touch_up_5pct_10d",
    "expected_touch_down_5pct_10d",
    "expected_first_touch_up_2pct_10d",
    "expected_first_touch_down_2pct_10d",
    "decision_tilt",
)
MIN_HYBRID_SAMPLE = 30


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the SAFE ranking-based decision analysis layer."""
    parser = argparse.ArgumentParser(
        description="Build ranking-based SAFE BTC decision scores from current state, ranking signals, and historical state outcomes.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--states-csv", default=str(DEFAULT_STATES_CSV_PATH), help="Default: ../out/states.csv")
    parser.add_argument(
        "--state-outcomes-csv",
        default=str(DEFAULT_STATE_OUTCOMES_CSV_PATH),
        help="Default: ../out/state_outcomes.csv",
    )
    parser.add_argument("--out-csv", default=str(DEFAULT_DECISION_ANALYSIS_CSV_PATH), help="Default: ../out/decision_analysis.csv")
    parser.add_argument("--out-md", default=str(OUT_DIR / "decision_analysis.md"), help="Default: ../out/decision_analysis.md")
    parser.add_argument("--buckets", type=int, default=10, help="Quantile bucket count for risk and opportunity scores. Default: 10")
    return parser.parse_args()


def _validate_date_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a date-first SAFE store before joining."""
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


def load_inputs(
    features_path: str | Path,
    states_path: str | Path,
    state_outcomes_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and validate features/states plus the state-outcome summary table."""
    features = _validate_date_frame("features", load_feature_csv(features_path))
    states = _validate_date_frame("states", load_feature_csv(states_path))
    if set(features["date"]) != set(states["date"]):
        raise ValueError("features.csv and states.csv must contain the same anchor-date set.")

    required_feature_columns = [
        "TS_20",
        "TS_50",
        "TS_200",
        "band_pos",
        "P_CORRECTION_10D_CAL",
        "P_REBOUND_10D_CAL",
        "P_SHOCK_HMM",
    ]
    missing_feature_columns = [column for column in required_feature_columns if column not in features.columns]
    if missing_feature_columns:
        raise ValueError(f"features.csv is missing required decision columns: {missing_feature_columns}")

    required_state_columns = ["state_hmm_label", "state_market_regime", "trend_state", "risk_state"]
    missing_state_columns = [column for column in required_state_columns if column not in states.columns]
    if missing_state_columns:
        raise ValueError(f"states.csv is missing required decision columns: {missing_state_columns}")

    merged = features.merge(states, on="date", how="inner", validate="one_to_one", suffixes=("", "_state"))

    state_outcomes = pd.read_csv(state_outcomes_path)
    expected_outcome_columns = {
        "state_key_type",
        "state_key",
        "target",
        "sample_count",
        "mean",
        "median",
        "win_rate",
        "event_rate",
        "up_rate",
        "down_rate",
    }
    missing_outcome_columns = [column for column in expected_outcome_columns if column not in state_outcomes.columns]
    if missing_outcome_columns:
        raise ValueError(f"state_outcomes.csv is missing required columns: {missing_outcome_columns}")

    return merged.sort_values("date").reset_index(drop=True), state_outcomes


def percentile_rank(series: pd.Series) -> pd.Series:
    """Return percentile ranks in [0, 1] while preserving NaN rows."""
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(method="average", pct=True)


def _build_state_lookup(state_outcomes: pd.DataFrame, state_key_type: str, prefix: str) -> pd.DataFrame:
    """Pivot the tidy state-outcome summary into a compact lookup table for one state type."""
    subset = state_outcomes.loc[state_outcomes["state_key_type"] == state_key_type].copy()
    if subset.empty:
        return pd.DataFrame(columns=[prefix])

    metrics = {
        "ret_10d": ["sample_count", "median", "win_rate"],
        "max_up_10d": ["mean"],
        "max_down_10d": ["mean"],
        "touch_up_2pct_10d": ["event_rate"],
        "touch_down_2pct_10d": ["event_rate"],
        "touch_up_5pct_10d": ["event_rate"],
        "touch_down_5pct_10d": ["event_rate"],
        "first_touch_2pct_10d": ["up_rate", "down_rate"],
    }

    rows: list[dict[str, Any]] = []
    for state_key, group in subset.groupby("state_key", sort=True):
        row: dict[str, Any] = {prefix: state_key}
        for target, target_metrics in metrics.items():
            target_rows = group.loc[group["target"] == target]
            if target_rows.empty:
                continue
            target_row = target_rows.iloc[0]
            for metric in target_metrics:
                row[f"{prefix}_{target}_{metric}"] = target_row[metric]
        rows.append(row)
    return pd.DataFrame(rows)


def add_historical_expectations(merged: pd.DataFrame, state_outcomes: pd.DataFrame) -> pd.DataFrame:
    """Attach state-conditioned historical outcome expectations to each daily row."""
    market_lookup = _build_state_lookup(state_outcomes, "market_regime", "state_market_regime")
    hmm_lookup = _build_state_lookup(state_outcomes, "hmm_label", "state_hmm_label")
    hybrid_lookup = _build_state_lookup(state_outcomes, "hybrid", "hybrid_state_key")

    enriched = merged.copy()
    enriched["hybrid_state_key"] = np.where(
        enriched["state_hmm_label"].notna() & enriched["state_market_regime"].notna(),
        enriched["state_hmm_label"].astype(str) + "|" + enriched["state_market_regime"].astype(str),
        np.nan,
    )

    enriched = enriched.merge(market_lookup, on="state_market_regime", how="left")
    enriched = enriched.merge(hmm_lookup, on="state_hmm_label", how="left")
    if not hybrid_lookup.empty:
        enriched = enriched.merge(hybrid_lookup, on="hybrid_state_key", how="left")

    def choose_metric(row: pd.Series, metric_name: str) -> float:
        hybrid_sample = row.get("hybrid_state_key_ret_10d_sample_count", np.nan)
        hybrid_value = row.get(f"hybrid_state_key_{metric_name}", np.nan)
        market_value = row.get(f"state_market_regime_{metric_name}", np.nan)
        hmm_value = row.get(f"state_hmm_label_{metric_name}", np.nan)

        if pd.notna(hybrid_sample) and float(hybrid_sample) >= MIN_HYBRID_SAMPLE and pd.notna(hybrid_value):
            return float(hybrid_value)
        if pd.notna(market_value):
            return float(market_value)
        if pd.notna(hmm_value):
            return float(hmm_value)
        return float("nan")

    enriched["historical_source"] = np.where(
        pd.to_numeric(enriched.get("hybrid_state_key_ret_10d_sample_count"), errors="coerce").fillna(0) >= MIN_HYBRID_SAMPLE,
        "hybrid",
        np.where(
            enriched.get("state_market_regime_ret_10d_sample_count").notna(),
            "market_regime",
            "hmm_label",
        ),
    )

    metric_map = {
        "expected_ret_10d": "ret_10d_median",
        "expected_ret_10d_win_rate": "ret_10d_win_rate",
        "expected_max_up_10d": "max_up_10d_mean",
        "expected_max_down_10d": "max_down_10d_mean",
        "expected_touch_up_2pct_10d": "touch_up_2pct_10d_event_rate",
        "expected_touch_down_2pct_10d": "touch_down_2pct_10d_event_rate",
        "expected_touch_up_5pct_10d": "touch_up_5pct_10d_event_rate",
        "expected_touch_down_5pct_10d": "touch_down_5pct_10d_event_rate",
        "expected_first_touch_up_2pct_10d": "first_touch_2pct_10d_up_rate",
        "expected_first_touch_down_2pct_10d": "first_touch_2pct_10d_down_rate",
    }
    for output_col, metric_name in metric_map.items():
        enriched[output_col] = enriched.apply(choose_metric, axis=1, metric_name=metric_name)

    return enriched


def _weighted_average(pairs: list[tuple[float, float]]) -> float:
    usable = [(weight, value) for weight, value in pairs if pd.notna(value)]
    if not usable:
        return float("nan")
    weight_sum = sum(weight for weight, _ in usable)
    if weight_sum <= 0:
        return float("nan")
    return float(sum(weight * float(value) for weight, value in usable) / weight_sum)


def _clip01(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(lower=0.0, upper=1.0)


def _trend_support_score(frame: pd.DataFrame) -> pd.Series:
    ts20_rank = percentile_rank(frame["TS_20"])
    ts50_rank = percentile_rank(frame["TS_50"])
    ts200_rank = percentile_rank(frame["TS_200"])
    sign_ratio = pd.concat(
        [
            (pd.to_numeric(frame["TS_20"], errors="coerce") > 0).astype(float),
            (pd.to_numeric(frame["TS_50"], errors="coerce") > 0).astype(float),
            (pd.to_numeric(frame["TS_200"], errors="coerce") > 0).astype(float),
        ],
        axis=1,
    ).mean(axis=1)
    return 0.5 * pd.concat([ts20_rank, ts50_rank, ts200_rank], axis=1).mean(axis=1) + 0.5 * sign_ratio


def _regime_risk_component(frame: pd.DataFrame) -> pd.Series:
    market_regime_map = {
        "high_vol_stress": 1.00,
        "downside_risk": 0.90,
        "transitional_mix": 0.65,
        "fragile_trend": 0.55,
        "rebound_setup": 0.45,
        "compressed_balance": 0.35,
        "neutral_balance": 0.40,
        "constructive_trend": 0.25,
    }
    hmm_map = {"SHOCK": 1.00, "CORE": 0.55, "DRIFT": 0.35, "SURGE": 0.20}
    market_component = frame["state_market_regime"].map(market_regime_map)
    hmm_component = frame["state_hmm_label"].map(hmm_map)
    return pd.concat([market_component, hmm_component], axis=1).mean(axis=1)


def _drawdown_share(frame: pd.DataFrame) -> pd.Series:
    max_up = pd.to_numeric(frame["expected_max_up_10d"], errors="coerce")
    max_down = pd.to_numeric(frame["expected_max_down_10d"], errors="coerce").abs()
    denom = (max_up + max_down).replace(0.0, np.nan)
    return max_down / denom


def _runup_share(frame: pd.DataFrame) -> pd.Series:
    max_up = pd.to_numeric(frame["expected_max_up_10d"], errors="coerce")
    max_down = pd.to_numeric(frame["expected_max_down_10d"], errors="coerce").abs()
    denom = (max_up + max_down).replace(0.0, np.nan)
    return max_up / denom


def compute_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute explicit ranking-based decision scores from current signals plus historical state outcomes."""
    out = frame.copy()

    corr_rank = percentile_rank(out["P_CORRECTION_10D_CAL"])
    rebound_rank = percentile_rank(out["P_REBOUND_10D_CAL"])
    shock_rank = percentile_rank(out["P_SHOCK_HMM"])
    trend_support = _trend_support_score(out)
    position_score = 1.0 - _clip01(out["band_pos"])
    regime_risk = _regime_risk_component(out)
    historical_downside = 0.6 * _clip01(out["expected_touch_down_2pct_10d"]) + 0.4 * _clip01(_drawdown_share(out))
    historical_upside = 0.6 * _clip01(out["expected_touch_up_2pct_10d"]) + 0.4 * _clip01(_runup_share(out))

    risk_component_frame = pd.concat(
        [
            0.35 * corr_rank.rename("corr_rank"),
            0.20 * shock_rank.rename("shock_rank"),
            0.20 * regime_risk.rename("regime_risk"),
            0.25 * historical_downside.rename("historical_downside"),
        ],
        axis=1,
    )
    opportunity_component_frame = pd.concat(
        [
            0.30 * rebound_rank.rename("rebound_rank"),
            0.25 * trend_support.rename("trend_support"),
            0.20 * position_score.rename("position_score"),
            0.25 * historical_upside.rename("historical_upside"),
        ],
        axis=1,
    )

    out["risk_score"] = 100.0 * risk_component_frame.sum(axis=1, min_count=1)
    out["opportunity_score"] = 100.0 * opportunity_component_frame.sum(axis=1, min_count=1)

    signal_edge = rebound_rank - corr_rank
    historical_touch_edge = _clip01(out["expected_touch_up_2pct_10d"]) - _clip01(out["expected_touch_down_2pct_10d"])
    historical_excursion_edge = _runup_share(out) - _drawdown_share(out)
    asymmetry_components = pd.concat(
        [
            0.40 * signal_edge.rename("signal_edge"),
            0.40 * historical_touch_edge.rename("historical_touch_edge"),
            0.20 * historical_excursion_edge.rename("historical_excursion_edge"),
        ],
        axis=1,
    )
    out["asymmetry_score"] = 100.0 * asymmetry_components.sum(axis=1, min_count=1)

    return out


def quantile_bucket(series: pd.Series, bucket_count: int) -> pd.Series:
    """Assign 1..N quantile buckets with duplicate-edge handling."""
    numeric = pd.to_numeric(series, errors="coerce")
    ranked = numeric.rank(method="first")
    bucket = pd.qcut(ranked, q=bucket_count, labels=False, duplicates="drop")
    return bucket.astype("float").add(1)


def classify_decision_tilt(row: pd.Series) -> str | float:
    """Map score combinations into an interpretable ranking-based action bias."""
    risk = row["risk_score"]
    opportunity = row["opportunity_score"]
    asymmetry = row["asymmetry_score"]
    if any(pd.isna(value) for value in (risk, opportunity, asymmetry)):
        return np.nan
    if risk >= 75 and opportunity <= 45:
        return "avoid_new_longs"
    if risk >= 75:
        return "reduce_exposure"
    if opportunity >= 70 and asymmetry >= 5:
        return "favor_longs"
    if opportunity >= 55 and asymmetry >= 0:
        return "selective_longs"
    if asymmetry <= -5:
        return "defensive"
    return "neutral_wait"


def build_decision_table(features_states: pd.DataFrame, state_outcomes: pd.DataFrame, bucket_count: int) -> pd.DataFrame:
    """Build the per-day decision analysis table."""
    enriched = add_historical_expectations(features_states, state_outcomes)
    scored = compute_scores(enriched)
    scored["risk_bucket"] = quantile_bucket(scored["risk_score"], bucket_count)
    scored["opportunity_bucket"] = quantile_bucket(scored["opportunity_score"], bucket_count)
    scored["decision_tilt"] = scored.apply(classify_decision_tilt, axis=1)
    return scored.loc[:, ["date", *DECISION_COLUMNS]].copy()


def _bucket_summary(frame: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    grouped = frame.dropna(subset=[bucket_col]).groupby(bucket_col, sort=True)
    rows: list[dict[str, Any]] = []
    for bucket_value, group in grouped:
        rows.append(
            {
                "bucket": int(bucket_value),
                "sample_count": int(len(group)),
                "mean_expected_ret_10d": float(pd.to_numeric(group["expected_ret_10d"], errors="coerce").mean()),
                "median_expected_ret_10d": float(pd.to_numeric(group["expected_ret_10d"], errors="coerce").median()),
                "mean_expected_max_down_10d": float(pd.to_numeric(group["expected_max_down_10d"], errors="coerce").mean()),
                "mean_expected_max_up_10d": float(pd.to_numeric(group["expected_max_up_10d"], errors="coerce").mean()),
                "mean_expected_touch_up_2pct_10d": float(pd.to_numeric(group["expected_touch_up_2pct_10d"], errors="coerce").mean()),
                "mean_expected_touch_down_2pct_10d": float(pd.to_numeric(group["expected_touch_down_2pct_10d"], errors="coerce").mean()),
                "mean_asymmetry_score": float(pd.to_numeric(group["asymmetry_score"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows)


def _fmt_pct(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}"


def render_markdown(decisions: pd.DataFrame) -> str:
    """Render a compact markdown summary of the ranking-based decision layer."""
    risk_summary = _bucket_summary(decisions, "risk_bucket")
    opportunity_summary = _bucket_summary(decisions, "opportunity_bucket")
    latest = decisions.iloc[-1]

    best_opportunity = opportunity_summary.sort_values("mean_expected_ret_10d", ascending=False).head(3)
    highest_risk = risk_summary.sort_values("mean_expected_max_down_10d", ascending=True).head(3)

    asymmetry_by_regime = (
        decisions.groupby("state_market_regime", dropna=False)
        .agg(
            sample_count=("date", "size"),
            mean_asymmetry_score=("asymmetry_score", "mean"),
            mean_expected_ret_10d=("expected_ret_10d", "mean"),
            mean_expected_touch_up_2pct_10d=("expected_touch_up_2pct_10d", "mean"),
            mean_expected_touch_down_2pct_10d=("expected_touch_down_2pct_10d", "mean"),
        )
        .reset_index()
        .sort_values("mean_asymmetry_score", ascending=False)
    )

    lines = [
        "# Decision Analysis",
        "",
        "This layer is descriptive and ranking-based. It does not treat SAFE probabilities as literal calibrated probabilities.",
        "",
        "Scores combine:",
        "- current ranking signals from `P_CORRECTION_10D_CAL`, `P_REBOUND_10D_CAL`, and `P_SHOCK_HMM`",
        "- current structural context from trend and position",
        "- historical state-conditioned outcomes from `state_outcomes.csv`",
        "",
        "Bucket summaries below describe expected historical outcomes implied by similar states, not out-of-sample realized performance.",
        "",
        "## Best Opportunity Buckets",
        "",
    ]

    for _, row in best_opportunity.iterrows():
        lines.append(
            f"- opportunity bucket `{int(row['bucket'])}`: expected 10d median return {_fmt_pct(row['median_expected_ret_10d'])}, "
            f"expected max up {_fmt_pct(row['mean_expected_max_up_10d'])}, "
            f"expected max down {_fmt_pct(row['mean_expected_max_down_10d'])}, "
            f"touch asymmetry {_fmt_pct(row['mean_expected_touch_up_2pct_10d'] - row['mean_expected_touch_down_2pct_10d'])}."
        )
    if best_opportunity.empty:
        lines.append("- none")

    lines.extend(["", "## Highest Risk Buckets", ""])
    for _, row in highest_risk.iterrows():
        lines.append(
            f"- risk bucket `{int(row['bucket'])}`: expected 10d median return {_fmt_pct(row['median_expected_ret_10d'])}, "
            f"expected drawdown {_fmt_pct(row['mean_expected_max_down_10d'])}, "
            f"expected upside {_fmt_pct(row['mean_expected_max_up_10d'])}, "
            f"touch asymmetry {_fmt_pct(row['mean_expected_touch_up_2pct_10d'] - row['mean_expected_touch_down_2pct_10d'])}."
        )
    if highest_risk.empty:
        lines.append("- none")

    lines.extend(["", "## Favorable / Unfavorable Regimes", ""])
    if not asymmetry_by_regime.empty:
        best_regime = asymmetry_by_regime.iloc[0]
        worst_regime = asymmetry_by_regime.iloc[-1]
        lines.append(
            f"- Most favorable asymmetry: `{best_regime['state_market_regime']}` "
            f"(n={int(best_regime['sample_count'])}, asymmetry score {_fmt_num(best_regime['mean_asymmetry_score'])}, "
            f"expected 10d return {_fmt_pct(best_regime['mean_expected_ret_10d'])})."
        )
        lines.append(
            f"- Least favorable asymmetry: `{worst_regime['state_market_regime']}` "
            f"(n={int(worst_regime['sample_count'])}, asymmetry score {_fmt_num(worst_regime['mean_asymmetry_score'])}, "
            f"expected 10d return {_fmt_pct(worst_regime['mean_expected_ret_10d'])})."
        )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Practical Interpretation",
            "",
            "- Favor longs when opportunity score is in the upper buckets, risk score stays in the lower half, and asymmetry remains positive.",
            "- Reduce exposure when risk score is in the top buckets, especially if the market regime is `downside_risk` or `high_vol_stress`.",
            "- Avoid new trades when risk is high and opportunity is low; the state-conditioned history is then tilted toward worse drawdowns than upside follow-through.",
            "- Treat neutral or conflicting score combinations as wait/selectivity zones rather than strong action signals.",
            "",
            "## Latest Snapshot",
            "",
            f"- date: `{latest['date'].strftime('%Y-%m-%d')}`",
            f"- HMM state: `{latest['state_hmm_label']}`",
            f"- market regime: `{latest['state_market_regime']}`",
            f"- risk score: `{_fmt_num(latest['risk_score'])}` (bucket `{int(latest['risk_bucket']) if pd.notna(latest['risk_bucket']) else 'n/a'}`)",
            f"- opportunity score: `{_fmt_num(latest['opportunity_score'])}` (bucket `{int(latest['opportunity_bucket']) if pd.notna(latest['opportunity_bucket']) else 'n/a'}`)",
            f"- asymmetry score: `{_fmt_num(latest['asymmetry_score'])}`",
            f"- historical source: `{latest['historical_source']}`",
            f"- decision tilt: `{latest['decision_tilt']}`",
            f"- expected 10d return: `{_fmt_pct(latest['expected_ret_10d'])}`",
            f"- expected 10d touch up/down 2pct: `{_fmt_pct(latest['expected_touch_up_2pct_10d'])}` / `{_fmt_pct(latest['expected_touch_down_2pct_10d'])}`",
            "",
        ]
    )

    return "\n".join(lines)


def print_summary(decisions: pd.DataFrame, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the decision analysis stage."""
    print(f"Rows written: {len(decisions)}")
    print(f"Risk buckets: {int(decisions['risk_bucket'].dropna().nunique())}")
    print(f"Opportunity buckets: {int(decisions['opportunity_bucket'].dropna().nunique())}")
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


def main() -> None:
    """Run SAFE v4.0 Phase 7 ranking-based decision analysis."""
    try:
        args = parse_args()
        features_states, state_outcomes = load_inputs(args.features_csv, args.states_csv, args.state_outcomes_csv)
        decisions = build_decision_table(features_states, state_outcomes, args.buckets)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_feature_csv(decisions.set_index("date"), out_csv, columns=list(DECISION_COLUMNS))
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(decisions), encoding="utf-8")

        print_summary(decisions, out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Decision analysis failed: {exc}") from exc


if __name__ == "__main__":
    main()
