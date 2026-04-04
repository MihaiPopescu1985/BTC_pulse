from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv, load_feature_csv
from src.path_config import (
    DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH,
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_STATES_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    OUT_DIR,
)
from src.research.v4_iteration.run_decision_analysis import classify_decision_tilt


EXPECTED_TARGETS: tuple[str, ...] = (
    "ret_10d",
    "max_up_10d",
    "max_down_10d",
    "touch_up_2pct_10d",
    "touch_down_2pct_10d",
    "touch_up_5pct_10d",
    "touch_down_5pct_10d",
    "first_touch_2pct_10d",
)
FEATURE_HISTORY_COLUMNS: tuple[str, ...] = (
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
    "P_SHOCK_HMM",
    "TS_20",
    "TS_50",
    "TS_200",
)
HORIZON_DAYS = 10
MIN_HYBRID_SAMPLE = 30
MIN_MARKET_REGIME_SAMPLE = 30
MIN_HMM_SAMPLE = 50
DECISION_WALKFORWARD_COLUMNS: tuple[str, ...] = (
    "risk_score",
    "opportunity_score",
    "asymmetry_score",
    "risk_bucket",
    "opportunity_bucket",
    "state_market_regime",
    "state_hmm_label",
    "historical_source",
    "history_sample_count",
    "history_ready_flag",
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


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the strict walk-forward decision layer."""
    parser = argparse.ArgumentParser(
        description="Build leakage-free walk-forward SAFE BTC decision scores using only prior resolved history.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--states-csv", default=str(DEFAULT_STATES_CSV_PATH), help="Default: ../out/states.csv")
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH),
        help="Default: ../out/decision_analysis_walkforward.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(OUT_DIR / "decision_analysis_walkforward.md"),
        help="Default: ../out/decision_analysis_walkforward.md",
    )
    parser.add_argument("--buckets", type=int, default=10, help="Quantile bucket count for walk-forward risk and opportunity scores.")
    return parser.parse_args()


def _validate_date_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
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


def load_inputs(
    features_path: str | Path,
    states_path: str | Path,
    targets_path: str | Path,
) -> pd.DataFrame:
    """Load and align features, states, and targets on anchor date."""
    features = _validate_date_frame("features", load_feature_csv(features_path))
    states = _validate_date_frame("states", load_feature_csv(states_path))
    targets = _validate_date_frame("targets", load_feature_csv(targets_path))

    if set(features["date"]) != set(states["date"]) or set(features["date"]) != set(targets["date"]):
        raise ValueError("features.csv, states.csv, and targets.csv must contain the same anchor-date set.")

    required_feature_columns = ["band_pos", *FEATURE_HISTORY_COLUMNS]
    missing_feature_columns = [column for column in required_feature_columns if column not in features.columns]
    if missing_feature_columns:
        raise ValueError(f"features.csv is missing required walk-forward columns: {missing_feature_columns}")

    required_state_columns = ["state_hmm_label", "state_market_regime"]
    missing_state_columns = [column for column in required_state_columns if column not in states.columns]
    if missing_state_columns:
        raise ValueError(f"states.csv is missing required walk-forward columns: {missing_state_columns}")

    missing_target_columns = [column for column in EXPECTED_TARGETS if column not in targets.columns]
    if missing_target_columns:
        raise ValueError(f"targets.csv is missing required walk-forward target columns: {missing_target_columns}")

    merged = features.merge(states, on="date", how="inner", validate="one_to_one", suffixes=("", "_state"))
    merged = merged.merge(targets.loc[:, ["date", *EXPECTED_TARGETS]], on="date", how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("Walk-forward decision dataset is empty.")
    return merged.sort_values("date").reset_index(drop=True)


def _make_state_store() -> dict[str, list[Any]]:
    return {target: [] for target in EXPECTED_TARGETS}


def _state_key(row: pd.Series, state_key_type: str) -> str | None:
    hmm_label = row.get("state_hmm_label")
    market_regime = row.get("state_market_regime")
    if state_key_type == "hmm_label":
        return str(hmm_label) if pd.notna(hmm_label) else None
    if state_key_type == "market_regime":
        return str(market_regime) if pd.notna(market_regime) else None
    if state_key_type == "hybrid":
        if pd.notna(hmm_label) and pd.notna(market_regime):
            return f"{hmm_label}|{market_regime}"
        return None
    raise ValueError(f"Unsupported state key type: {state_key_type}")


def update_state_histories(state_histories: dict[str, dict[str, dict[str, list[Any]]]], row: pd.Series) -> None:
    """Add one resolved anchor row into the rolling state-outcome histories."""
    for state_key_type in ("hybrid", "market_regime", "hmm_label"):
        key = _state_key(row, state_key_type)
        if key is None:
            continue
        store = state_histories[state_key_type].setdefault(key, _make_state_store())
        for target in EXPECTED_TARGETS:
            value = row[target]
            if pd.isna(value):
                continue
            store[target].append(value)


def summarize_state_store(store: dict[str, list[Any]] | None) -> dict[str, float]:
    """Summarize one rolling state-outcome store into the expected 10d metrics."""
    if not store:
        return {
            "history_sample_count": np.nan,
            "expected_ret_10d": np.nan,
            "expected_ret_10d_win_rate": np.nan,
            "expected_max_up_10d": np.nan,
            "expected_max_down_10d": np.nan,
            "expected_touch_up_2pct_10d": np.nan,
            "expected_touch_down_2pct_10d": np.nan,
            "expected_touch_up_5pct_10d": np.nan,
            "expected_touch_down_5pct_10d": np.nan,
            "expected_first_touch_up_2pct_10d": np.nan,
            "expected_first_touch_down_2pct_10d": np.nan,
        }

    ret = pd.to_numeric(pd.Series(store["ret_10d"]), errors="coerce").dropna()
    if ret.empty:
        return {
            "history_sample_count": 0.0,
            "expected_ret_10d": np.nan,
            "expected_ret_10d_win_rate": np.nan,
            "expected_max_up_10d": np.nan,
            "expected_max_down_10d": np.nan,
            "expected_touch_up_2pct_10d": np.nan,
            "expected_touch_down_2pct_10d": np.nan,
            "expected_touch_up_5pct_10d": np.nan,
            "expected_touch_down_5pct_10d": np.nan,
            "expected_first_touch_up_2pct_10d": np.nan,
            "expected_first_touch_down_2pct_10d": np.nan,
        }

    first_touch = pd.Series(store["first_touch_2pct_10d"]).dropna().astype(str)
    return {
        "history_sample_count": float(len(ret)),
        "expected_ret_10d": float(ret.median()),
        "expected_ret_10d_win_rate": float((ret > 0).mean()),
        "expected_max_up_10d": float(pd.to_numeric(pd.Series(store["max_up_10d"]), errors="coerce").dropna().mean()),
        "expected_max_down_10d": float(pd.to_numeric(pd.Series(store["max_down_10d"]), errors="coerce").dropna().mean()),
        "expected_touch_up_2pct_10d": float(pd.to_numeric(pd.Series(store["touch_up_2pct_10d"]), errors="coerce").dropna().mean()),
        "expected_touch_down_2pct_10d": float(pd.to_numeric(pd.Series(store["touch_down_2pct_10d"]), errors="coerce").dropna().mean()),
        "expected_touch_up_5pct_10d": float(pd.to_numeric(pd.Series(store["touch_up_5pct_10d"]), errors="coerce").dropna().mean()),
        "expected_touch_down_5pct_10d": float(pd.to_numeric(pd.Series(store["touch_down_5pct_10d"]), errors="coerce").dropna().mean()),
        "expected_first_touch_up_2pct_10d": float((first_touch == "up").mean()) if not first_touch.empty else np.nan,
        "expected_first_touch_down_2pct_10d": float((first_touch == "down").mean()) if not first_touch.empty else np.nan,
    }


def choose_historical_expectation(current_row: pd.Series, state_histories: dict[str, dict[str, dict[str, list[Any]]]]) -> tuple[str, dict[str, float]]:
    """Choose the strict walk-forward fallback source for the current state."""
    fallback_specs = (
        ("hybrid", "hybrid", MIN_HYBRID_SAMPLE),
        ("market_regime", "market_regime", MIN_MARKET_REGIME_SAMPLE),
        ("hmm_label", "hmm_label", MIN_HMM_SAMPLE),
    )
    for source_name, state_key_type, min_sample in fallback_specs:
        key = _state_key(current_row, state_key_type)
        if key is None:
            continue
        store = state_histories[state_key_type].get(key)
        summary = summarize_state_store(store)
        if pd.notna(summary["history_sample_count"]) and float(summary["history_sample_count"]) >= min_sample:
            return source_name, summary
    return "none", summarize_state_store(None)


def past_percentile_rank(value: Any, history: list[float]) -> float:
    """Return the empirical percentile rank of the current value versus prior history only."""
    if pd.isna(value) or not history:
        return float("nan")
    arr = np.asarray(history, dtype=float)
    lower = float(np.sum(arr < float(value)))
    equal = float(np.sum(arr == float(value)))
    return (lower + 0.5 * equal) / float(len(arr))


def _clip01(value: Any) -> float:
    if pd.isna(value):
        return float("nan")
    return float(min(1.0, max(0.0, float(value))))


def _safe_div(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def compute_single_row_scores(row: pd.Series, feature_histories: dict[str, list[float]], summary: dict[str, float]) -> tuple[float, float, float]:
    """Compute walk-forward decision scores for one row using past-only ranks and expectations."""
    corr_rank = past_percentile_rank(row["P_CORRECTION_10D_CAL"], feature_histories["P_CORRECTION_10D_CAL"])
    rebound_rank = past_percentile_rank(row["P_REBOUND_10D_CAL"], feature_histories["P_REBOUND_10D_CAL"])
    shock_rank = past_percentile_rank(row["P_SHOCK_HMM"], feature_histories["P_SHOCK_HMM"])
    ts20_rank = past_percentile_rank(row["TS_20"], feature_histories["TS_20"])
    ts50_rank = past_percentile_rank(row["TS_50"], feature_histories["TS_50"])
    ts200_rank = past_percentile_rank(row["TS_200"], feature_histories["TS_200"])

    trend_ranks = [value for value in (ts20_rank, ts50_rank, ts200_rank) if pd.notna(value)]
    trend_signs = [float(row[column] > 0) for column in ("TS_20", "TS_50", "TS_200") if pd.notna(row[column])]
    trend_support = (
        0.5 * float(np.mean(trend_ranks)) + 0.5 * float(np.mean(trend_signs))
        if trend_ranks and trend_signs
        else float("nan")
    )

    band_pos = pd.to_numeric(pd.Series([row["band_pos"]]), errors="coerce").iloc[0]
    position_score = 1.0 - _clip01(band_pos) if pd.notna(band_pos) else float("nan")

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
    regime_parts = [market_regime_map.get(row["state_market_regime"], np.nan), hmm_map.get(row["state_hmm_label"], np.nan)]
    regime_parts = [value for value in regime_parts if pd.notna(value)]
    regime_risk = float(np.mean(regime_parts)) if regime_parts else float("nan")

    expected_max_up = summary["expected_max_up_10d"]
    expected_max_down_abs = abs(summary["expected_max_down_10d"]) if pd.notna(summary["expected_max_down_10d"]) else float("nan")
    drawdown_share = _safe_div(expected_max_down_abs, expected_max_up + expected_max_down_abs) if pd.notna(expected_max_up) and pd.notna(expected_max_down_abs) else float("nan")
    runup_share = _safe_div(expected_max_up, expected_max_up + expected_max_down_abs) if pd.notna(expected_max_up) and pd.notna(expected_max_down_abs) else float("nan")

    historical_downside = (
        0.6 * _clip01(summary["expected_touch_down_2pct_10d"]) + 0.4 * drawdown_share
        if pd.notna(summary["expected_touch_down_2pct_10d"]) and pd.notna(drawdown_share)
        else float("nan")
    )
    historical_upside = (
        0.6 * _clip01(summary["expected_touch_up_2pct_10d"]) + 0.4 * runup_share
        if pd.notna(summary["expected_touch_up_2pct_10d"]) and pd.notna(runup_share)
        else float("nan")
    )

    risk_parts = [0.35 * corr_rank, 0.20 * shock_rank, 0.20 * regime_risk, 0.25 * historical_downside]
    risk_score = 100.0 * float(np.sum([value for value in risk_parts if pd.notna(value)])) if any(pd.notna(value) for value in risk_parts) else float("nan")

    opportunity_parts = [0.30 * rebound_rank, 0.25 * trend_support, 0.20 * position_score, 0.25 * historical_upside]
    opportunity_score = 100.0 * float(np.sum([value for value in opportunity_parts if pd.notna(value)])) if any(pd.notna(value) for value in opportunity_parts) else float("nan")

    signal_edge = rebound_rank - corr_rank if pd.notna(rebound_rank) and pd.notna(corr_rank) else float("nan")
    historical_touch_edge = (
        _clip01(summary["expected_touch_up_2pct_10d"]) - _clip01(summary["expected_touch_down_2pct_10d"])
        if pd.notna(summary["expected_touch_up_2pct_10d"]) and pd.notna(summary["expected_touch_down_2pct_10d"])
        else float("nan")
    )
    historical_excursion_edge = runup_share - drawdown_share if pd.notna(runup_share) and pd.notna(drawdown_share) else float("nan")
    asymmetry_parts = [0.40 * signal_edge, 0.40 * historical_touch_edge, 0.20 * historical_excursion_edge]
    asymmetry_score = 100.0 * float(np.sum([value for value in asymmetry_parts if pd.notna(value)])) if any(pd.notna(value) for value in asymmetry_parts) else float("nan")

    return risk_score, opportunity_score, asymmetry_score


def bucket_from_history(score: float, score_history: list[float], bucket_count: int) -> float:
    """Assign a walk-forward quantile bucket from prior valid score history only."""
    if pd.isna(score) or len(score_history) < bucket_count:
        return float("nan")
    pct_rank = past_percentile_rank(score, score_history)
    if pd.isna(pct_rank):
        return float("nan")
    return float(min(bucket_count, max(1, int(np.floor(pct_rank * bucket_count) + 1))))


def build_decision_table_walkforward(data: pd.DataFrame, bucket_count: int) -> pd.DataFrame:
    """Build the strict leakage-free walk-forward decision table."""
    state_histories: dict[str, dict[str, dict[str, list[Any]]]] = {
        "hybrid": {},
        "market_regime": {},
        "hmm_label": {},
    }
    feature_histories: dict[str, list[float]] = {column: [] for column in FEATURE_HISTORY_COLUMNS}
    score_histories: dict[str, list[float]] = {"risk_score": [], "opportunity_score": []}

    rows: list[dict[str, Any]] = []
    for idx, row in data.iterrows():
        resolved_idx = idx - HORIZON_DAYS
        if resolved_idx >= 0:
            update_state_histories(state_histories, data.iloc[resolved_idx])

        source, summary = choose_historical_expectation(row, state_histories)
        history_ready = source != "none"

        if history_ready:
            risk_score, opportunity_score, asymmetry_score = compute_single_row_scores(row, feature_histories, summary)
        else:
            risk_score = float("nan")
            opportunity_score = float("nan")
            asymmetry_score = float("nan")

        risk_bucket = bucket_from_history(risk_score, score_histories["risk_score"], bucket_count)
        opportunity_bucket = bucket_from_history(opportunity_score, score_histories["opportunity_score"], bucket_count)

        decision_row = {
            "date": row["date"],
            "risk_score": risk_score,
            "opportunity_score": opportunity_score,
            "asymmetry_score": asymmetry_score,
            "risk_bucket": risk_bucket,
            "opportunity_bucket": opportunity_bucket,
            "state_market_regime": row["state_market_regime"],
            "state_hmm_label": row["state_hmm_label"],
            "historical_source": source,
            "history_sample_count": summary["history_sample_count"],
            "history_ready_flag": float(history_ready),
            "expected_ret_10d": summary["expected_ret_10d"],
            "expected_ret_10d_win_rate": summary["expected_ret_10d_win_rate"],
            "expected_max_up_10d": summary["expected_max_up_10d"],
            "expected_max_down_10d": summary["expected_max_down_10d"],
            "expected_touch_up_2pct_10d": summary["expected_touch_up_2pct_10d"],
            "expected_touch_down_2pct_10d": summary["expected_touch_down_2pct_10d"],
            "expected_touch_up_5pct_10d": summary["expected_touch_up_5pct_10d"],
            "expected_touch_down_5pct_10d": summary["expected_touch_down_5pct_10d"],
            "expected_first_touch_up_2pct_10d": summary["expected_first_touch_up_2pct_10d"],
            "expected_first_touch_down_2pct_10d": summary["expected_first_touch_down_2pct_10d"],
            "decision_tilt": np.nan,
        }

        if history_ready and all(pd.notna(decision_row[column]) for column in ("risk_score", "opportunity_score", "asymmetry_score")):
            decision_row["decision_tilt"] = classify_decision_tilt(pd.Series(decision_row))

        rows.append(decision_row)

        for column in FEATURE_HISTORY_COLUMNS:
            value = row[column]
            if pd.notna(value):
                feature_histories[column].append(float(value))
        if pd.notna(risk_score):
            score_histories["risk_score"].append(float(risk_score))
        if pd.notna(opportunity_score):
            score_histories["opportunity_score"].append(float(opportunity_score))

    out = pd.DataFrame(rows)
    return out.loc[:, ["date", *DECISION_WALKFORWARD_COLUMNS]].copy()


def _fmt_pct(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}"


def render_markdown(decisions: pd.DataFrame) -> str:
    """Render a compact markdown summary of the strict walk-forward decision layer."""
    usable = decisions.loc[decisions["history_ready_flag"] >= 0.5].copy()
    source_counts = decisions["historical_source"].fillna("none").value_counts(dropna=False)
    first_usable_date = usable["date"].min() if not usable.empty else pd.NaT
    latest = decisions.iloc[-1]

    lines = [
        "# Walk-Forward Decision Analysis",
        "",
        "This is the first strict leakage-free decision layer. Each date uses only earlier rows, and only rows whose 10d outcomes would already have been realized by that date.",
        "",
        f"- total rows: `{len(decisions)}`",
        f"- usable walk-forward rows: `{int(len(usable))}`",
        f"- first usable date: `{first_usable_date.strftime('%Y-%m-%d') if pd.notna(first_usable_date) else 'n/a'}`",
        "",
        "Fallback source usage:",
    ]
    for key, value in source_counts.items():
        lines.append(f"- `{key}`: {int(value)}")

    lines.extend(
        [
            "",
            "Minimum history rules:",
            f"- `hybrid >= {MIN_HYBRID_SAMPLE}`",
            f"- `market_regime >= {MIN_MARKET_REGIME_SAMPLE}`",
            f"- `hmm_label >= {MIN_HMM_SAMPLE}`",
            "",
            "Rows before those thresholds stay neutral / unavailable rather than borrowing future-informed expectations.",
            "",
            "## Latest Snapshot",
            "",
            f"- date: `{latest['date'].strftime('%Y-%m-%d')}`",
            f"- HMM state: `{latest['state_hmm_label']}`",
            f"- market regime: `{latest['state_market_regime']}`",
            f"- historical source: `{latest['historical_source']}`",
            f"- history sample count: `{int(latest['history_sample_count']) if pd.notna(latest['history_sample_count']) else 'n/a'}`",
            f"- risk score: `{_fmt_num(latest['risk_score'])}` (bucket `{int(latest['risk_bucket']) if pd.notna(latest['risk_bucket']) else 'n/a'}`)",
            f"- opportunity score: `{_fmt_num(latest['opportunity_score'])}` (bucket `{int(latest['opportunity_bucket']) if pd.notna(latest['opportunity_bucket']) else 'n/a'}`)",
            f"- asymmetry score: `{_fmt_num(latest['asymmetry_score'])}`",
            f"- decision tilt: `{latest['decision_tilt']}`",
            f"- expected 10d return: `{_fmt_pct(latest['expected_ret_10d'])}`",
            f"- expected 10d touch up/down 2pct: `{_fmt_pct(latest['expected_touch_up_2pct_10d'])}` / `{_fmt_pct(latest['expected_touch_down_2pct_10d'])}`",
            "",
        ]
    )
    return "\n".join(lines)


def print_summary(decisions: pd.DataFrame, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the walk-forward decision layer."""
    usable_rows = int((decisions["history_ready_flag"] >= 0.5).sum())
    source_counts = decisions["historical_source"].fillna("none").value_counts(dropna=False)
    print(f"Rows written: {len(decisions)}")
    print(f"Usable walk-forward rows: {usable_rows}")
    print("Fallback counts:")
    for key, value in source_counts.items():
        print(f"  {key}: {int(value)}")
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


def main() -> None:
    """Run SAFE strict walk-forward decision analysis."""
    try:
        args = parse_args()
        data = load_inputs(args.features_csv, args.states_csv, args.targets_csv)
        decisions = build_decision_table_walkforward(data, args.buckets)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_feature_csv(decisions.set_index("date"), out_csv, columns=list(DECISION_WALKFORWARD_COLUMNS))
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(decisions), encoding="utf-8")

        print_summary(decisions, out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Walk-forward decision analysis failed: {exc}") from exc


if __name__ == "__main__":
    main()
