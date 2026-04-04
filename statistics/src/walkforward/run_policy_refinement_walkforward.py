from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import (
    DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH,
    DEFAULT_POLICY_REFINEMENT_WALKFORWARD_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    OUT_DIR,
)
from src.research.v4_iteration.run_policy_backtest import (
    PolicyDefinition,
    build_policy_definitions,
    build_signal_frame,
    compute_policy_metrics,
    simulate_policy_series,
)


LOW_THRESHOLDS: tuple[int, ...] = (4, 5, 6)
HIGH_THRESHOLDS: tuple[int, ...] = (7, 8, 9)


@dataclass(frozen=True)
class PolicyVariant:
    policy_name: str
    policy_family: str
    variant_label: str
    threshold_low: float | None
    threshold_high: float | None
    policy_def: PolicyDefinition


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the walk-forward policy refinement / ablation stage."""
    parser = argparse.ArgumentParser(
        description="Run a controlled ablation study on SAFE BTC walk-forward long/flat policies.",
    )
    parser.add_argument(
        "--decision-analysis-walkforward-csv",
        default=str(DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH),
        help="Default: ../out/decision_analysis_walkforward.csv",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_POLICY_REFINEMENT_WALKFORWARD_CSV_PATH),
        help="Default: ../out/policy_refinement_walkforward.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(OUT_DIR / "policy_refinement_walkforward.md"),
        help="Default: ../out/policy_refinement_walkforward.md",
    )
    parser.add_argument("--cost-bps", type=float, default=10.0, help="Fixed basis-point cost per position change. Default: 10")
    parser.add_argument("--start-date", default=None, help="Optional YYYY-MM-DD inclusive start date.")
    parser.add_argument("--end-date", default=None, help="Optional YYYY-MM-DD inclusive end date.")
    return parser.parse_args()


def _validate_date_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a date-first SAFE CSV store before merging."""
    if frame.empty:
        raise ValueError(f"{name} input is empty.")
    if "date" not in frame.columns:
        raise ValueError(f"{name} input must contain a 'date' column.")
    if frame["date"].duplicated().any():
        duplicates = frame.loc[frame["date"].duplicated(), "date"].astype(str).head(5).tolist()
        raise ValueError(f"{name} input has duplicate dates: {duplicates}")
    validated = frame.copy()
    validated["date"] = pd.to_datetime(validated["date"], errors="raise")
    return validated.sort_values("date").reset_index(drop=True)


def load_inputs(
    decision_path: str | Path,
    price_path: str | Path,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    """Load and align walk-forward decision analysis with BTC close data."""
    decisions = _validate_date_frame("decision_analysis_walkforward", load_feature_csv(decision_path))
    required_columns = {
        "risk_bucket",
        "opportunity_bucket",
        "asymmetry_score",
        "decision_tilt",
        "history_ready_flag",
    }
    missing_columns = [column for column in required_columns if column not in decisions.columns]
    if missing_columns:
        raise ValueError(f"decision_analysis_walkforward.csv is missing required columns: {missing_columns}")

    price = load_daily_price_json(str(price_path)).reset_index().rename(columns={"timestamp": "date"})
    price = _validate_date_frame("daily_price", price.loc[:, ["date", "close"]])

    if set(decisions["date"]) != set(price["date"]):
        raise ValueError("decision_analysis_walkforward.csv and daily_price.json must contain the same anchor-date set.")

    merged = decisions.merge(price, on="date", how="inner", validate="one_to_one")
    if start_date is not None:
        merged = merged.loc[merged["date"] >= pd.to_datetime(start_date, errors="raise")].copy()
    if end_date is not None:
        merged = merged.loc[merged["date"] <= pd.to_datetime(end_date, errors="raise")].copy()
    merged = merged.sort_values("date").reset_index(drop=True)
    if merged.empty:
        raise ValueError("Refinement backtest window is empty after applying date filters.")
    return merged


def _bucket_value(row: pd.Series, column: str) -> float:
    value = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
    return float(value) if pd.notna(value) else float("nan")


def _history_ready(row: pd.Series) -> bool:
    value = pd.to_numeric(pd.Series([row.get("history_ready_flag", np.nan)]), errors="coerce").iloc[0]
    return bool(pd.notna(value) and float(value) >= 0.5)


def stateful_signal_series(
    data: pd.DataFrame,
    enter_fn: Callable[[pd.Series], bool],
    exit_fn: Callable[[pd.Series], bool],
    *,
    initial_state: float = 0.0,
    ignore_history_ready: bool = False,
) -> pd.Series:
    """Build a persistent desired-position signal from explicit entry/exit rules."""
    state = float(initial_state)
    signals: list[float] = []
    for _, row in data.iterrows():
        if not ignore_history_ready and not _history_ready(row):
            state = 0.0
            signals.append(state)
            continue

        should_exit = bool(exit_fn(row))
        should_enter = bool(enter_fn(row))
        if state > 0.0:
            if should_exit:
                state = 0.0
        else:
            if should_enter:
                state = 1.0
        signals.append(state)
    return pd.Series(signals, index=data.index, dtype=float)


def build_ablation_variants() -> list[PolicyVariant]:
    """Create the controlled ablation variant set."""
    variants: list[PolicyVariant] = []

    for low in LOW_THRESHOLDS:
        for high in HIGH_THRESHOLDS:
            risk_name = f"risk_only_lb{low}_ub{high}"
            risk_def = PolicyDefinition(risk_name, risk_name, lambda row: False)
            variants.append(PolicyVariant(risk_name, "risk_only", risk_name, float(low), float(high), risk_def))

            opp_name = f"opp_only_lb{low}_ub{high}"
            opp_def = PolicyDefinition(opp_name, opp_name, lambda row: False)
            variants.append(PolicyVariant(opp_name, "opportunity_only", opp_name, float(low), float(high), opp_def))

            risk_tilt_name = f"risk_tilt_lb{low}_ub{high}"
            risk_tilt_def = PolicyDefinition(risk_tilt_name, risk_tilt_name, lambda row: False)
            variants.append(PolicyVariant(risk_tilt_name, "risk_tilt", risk_tilt_name, float(low), float(high), risk_tilt_def))

            opp_asym_name = f"opp_asym_lb{low}_ub{high}"
            opp_asym_def = PolicyDefinition(opp_asym_name, opp_asym_name, lambda row: False)
            variants.append(PolicyVariant(opp_asym_name, "opportunity_asym", opp_asym_name, float(low), float(high), opp_asym_def))

    tilt_only_name = "tilt_only"
    tilt_only_def = PolicyDefinition(tilt_only_name, tilt_only_name, lambda row: False)
    variants.append(PolicyVariant(tilt_only_name, "tilt_only", tilt_only_name, np.nan, np.nan, tilt_only_def))

    always_long_name = "always_long"
    always_long_def = PolicyDefinition(always_long_name, always_long_name, lambda row: True)
    variants.append(PolicyVariant(always_long_name, "benchmark", always_long_name, np.nan, np.nan, always_long_def))

    always_flat_name = "always_flat"
    always_flat_def = PolicyDefinition(always_flat_name, always_flat_name, lambda row: False)
    variants.append(PolicyVariant(always_flat_name, "benchmark", always_flat_name, np.nan, np.nan, always_flat_def))
    return variants


def build_ablation_signal_frame(data: pd.DataFrame, variants: list[PolicyVariant]) -> pd.DataFrame:
    """Build the persistent desired-position signals for the ablation variants."""
    frame = pd.DataFrame(index=data.index)
    for variant in variants:
        low = variant.threshold_low
        high = variant.threshold_high
        name = variant.policy_name

        if variant.policy_family == "risk_only":
            frame[name] = stateful_signal_series(
                data,
                enter_fn=lambda row, low=low: pd.notna(_bucket_value(row, "risk_bucket")) and _bucket_value(row, "risk_bucket") <= float(low),
                exit_fn=lambda row, high=high: pd.notna(_bucket_value(row, "risk_bucket")) and _bucket_value(row, "risk_bucket") >= float(high),
            )
        elif variant.policy_family == "opportunity_only":
            frame[name] = stateful_signal_series(
                data,
                enter_fn=lambda row, high=high: pd.notna(_bucket_value(row, "opportunity_bucket")) and _bucket_value(row, "opportunity_bucket") >= float(high),
                exit_fn=lambda row, low=low: pd.notna(_bucket_value(row, "opportunity_bucket")) and _bucket_value(row, "opportunity_bucket") <= float(low),
            )
        elif variant.policy_family == "risk_tilt":
            frame[name] = stateful_signal_series(
                data,
                enter_fn=lambda row, low=low: (
                    row["decision_tilt"] in {"favor_longs", "selective_longs"}
                    and pd.notna(_bucket_value(row, "risk_bucket"))
                    and _bucket_value(row, "risk_bucket") <= float(low)
                ),
                exit_fn=lambda row, high=high: (
                    (pd.notna(_bucket_value(row, "risk_bucket")) and _bucket_value(row, "risk_bucket") >= float(high))
                    or row["decision_tilt"] in {"reduce_exposure", "avoid_new_longs"}
                ),
            )
        elif variant.policy_family == "opportunity_asym":
            frame[name] = stateful_signal_series(
                data,
                enter_fn=lambda row, high=high: (
                    pd.notna(_bucket_value(row, "opportunity_bucket"))
                    and _bucket_value(row, "opportunity_bucket") >= float(high)
                    and pd.notna(pd.to_numeric(pd.Series([row["asymmetry_score"]]), errors="coerce").iloc[0])
                    and float(row["asymmetry_score"]) > 0.0
                ),
                exit_fn=lambda row, low=low: (
                    (pd.notna(_bucket_value(row, "opportunity_bucket")) and _bucket_value(row, "opportunity_bucket") <= float(low))
                    or (pd.notna(pd.to_numeric(pd.Series([row["asymmetry_score"]]), errors="coerce").iloc[0]) and float(row["asymmetry_score"]) < 0.0)
                ),
            )
        elif variant.policy_family == "tilt_only":
            frame[name] = stateful_signal_series(
                data,
                enter_fn=lambda row: row["decision_tilt"] == "favor_longs",
                exit_fn=lambda row: row["decision_tilt"] in {"reduce_exposure", "avoid_new_longs"},
            )
        elif variant.policy_family == "benchmark" and variant.policy_name == "always_long":
            frame[name] = stateful_signal_series(
                data,
                enter_fn=lambda row: True,
                exit_fn=lambda row: False,
                ignore_history_ready=True,
            )
        elif variant.policy_family == "benchmark" and variant.policy_name == "always_flat":
            frame[name] = pd.Series(0.0, index=data.index, dtype=float)
        else:
            raise ValueError(f"Unsupported ablation variant family: {variant.policy_family}")
    return frame


def build_baseline_variants() -> list[PolicyVariant]:
    """Wrap the accepted walk-forward baseline policies in the refinement metadata format."""
    baseline_defs = build_policy_definitions()
    family_labels = {
        "policy_a": ("baseline", "conservative_baseline"),
        "policy_b": ("baseline", "opportunity_led_baseline"),
        "policy_c": ("baseline", "defensive_trend_following_baseline"),
    }
    variants: list[PolicyVariant] = []
    for policy_def in baseline_defs:
        family, label = family_labels[policy_def.name]
        variants.append(
            PolicyVariant(
                policy_name=policy_def.name,
                policy_family=family,
                variant_label=label,
                threshold_low=np.nan,
                threshold_high=np.nan,
                policy_def=policy_def,
            )
        )
    return variants


def run_refinement_backtest(data: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """Run the controlled refinement and ablation study and return summary metrics."""
    baseline_variants = build_baseline_variants()
    baseline_defs = tuple(variant.policy_def for variant in baseline_variants)
    baseline_signal_frame = build_signal_frame(data, baseline_defs)

    ablation_variants = build_ablation_variants()
    ablation_signal_frame = build_ablation_signal_frame(data, ablation_variants)

    combined_signal_frame = pd.concat([baseline_signal_frame, ablation_signal_frame], axis=1)
    all_variants = baseline_variants + ablation_variants
    all_defs = tuple(variant.policy_def for variant in all_variants)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pd.errors.PerformanceWarning)
        backtest = simulate_policy_series(data, combined_signal_frame, cost_bps)
    metrics = compute_policy_metrics(backtest, all_defs)

    variant_meta = pd.DataFrame(
        [
            {
                "policy_name": variant.policy_name,
                "policy_family": variant.policy_family,
                "variant_label": variant.variant_label,
                "threshold_low": variant.threshold_low,
                "threshold_high": variant.threshold_high,
            }
            for variant in all_variants
        ]
    )
    merged_metrics = metrics.merge(variant_meta, on="policy_name", how="left", validate="one_to_one")
    return merged_metrics.loc[
        :,
        [
            "policy_name",
            "policy_family",
            "variant_label",
            "threshold_low",
            "threshold_high",
            "total_return",
            "cagr",
            "max_drawdown",
            "sharpe",
            "number_of_trades",
            "time_in_market",
            "win_rate_holding_periods",
            "average_holding_period",
            "final_equity",
        ],
    ].sort_values(["policy_family", "policy_name"]).reset_index(drop=True)


def export_summary_csv(frame: pd.DataFrame, path: str | Path) -> None:
    """Write the tidy refinement summary as a plain CSV."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False, float_format="%.8f")


def _fmt_pct(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def _best_by_metric(frame: pd.DataFrame, metric: str, ascending: bool, limit: int = 5) -> pd.DataFrame:
    usable = frame.dropna(subset=[metric]).copy()
    if usable.empty:
        return usable
    return usable.sort_values(metric, ascending=ascending).head(limit)


def _family_best(frame: pd.DataFrame, family: str, metric: str = "sharpe", ascending: bool = False) -> pd.Series | None:
    subset = frame.loc[frame["policy_family"] == family].dropna(subset=[metric]).copy()
    if subset.empty:
        return None
    return subset.sort_values(metric, ascending=ascending).iloc[0]


def render_markdown(results: pd.DataFrame, cost_bps: float, start_date: pd.Timestamp, end_date: pd.Timestamp) -> str:
    """Render a compact markdown summary of the walk-forward refinement / ablation study."""
    best_sharpe = _best_by_metric(results, "sharpe", ascending=False)
    best_return = _best_by_metric(results, "total_return", ascending=False)
    best_drawdown = _best_by_metric(results, "max_drawdown", ascending=False)

    baseline_best = _family_best(results, "baseline", metric="sharpe", ascending=False)
    risk_only_best = _family_best(results, "risk_only", metric="sharpe", ascending=False)
    opp_only_best = _family_best(results, "opportunity_only", metric="sharpe", ascending=False)
    tilt_only_best = _family_best(results, "tilt_only", metric="sharpe", ascending=False)
    risk_tilt_best = _family_best(results, "risk_tilt", metric="sharpe", ascending=False)
    opp_asym_best = _family_best(results, "opportunity_asym", metric="sharpe", ascending=False)
    always_long = _family_best(results, "benchmark", metric="total_return", ascending=False)

    lines = [
        "# Policy Refinement Walk-Forward",
        "",
        "This report is a controlled ablation study on the strict leakage-free walk-forward decision layer.",
        "",
        f"Backtest window: `{start_date.strftime('%Y-%m-%d')}` -> `{end_date.strftime('%Y-%m-%d')}`",
        f"Transaction cost assumption: `{cost_bps:.1f}` bps per position change",
        f"Policy variants tested: `{len(results)}`",
        "",
        "## Best Overall Variants By Sharpe",
        "",
    ]

    for _, row in best_sharpe.iterrows():
        lines.append(
            f"- `{row['variant_label']}` ({row['policy_family']}): Sharpe `{_fmt_num(row['sharpe'])}`, "
            f"total return `{_fmt_pct(row['total_return'])}`, max drawdown `{_fmt_pct(row['max_drawdown'])}`."
        )
    if best_sharpe.empty:
        lines.append("- none")

    lines.extend(["", "## Best Overall Variants By Total Return", ""])
    for _, row in best_return.iterrows():
        lines.append(
            f"- `{row['variant_label']}` ({row['policy_family']}): total return `{_fmt_pct(row['total_return'])}`, "
            f"CAGR `{_fmt_pct(row['cagr'])}`, Sharpe `{_fmt_num(row['sharpe'])}`."
        )
    if best_return.empty:
        lines.append("- none")

    lines.extend(["", "## Best Drawdown Control", ""])
    for _, row in best_drawdown.iterrows():
        lines.append(
            f"- `{row['variant_label']}` ({row['policy_family']}): max drawdown `{_fmt_pct(row['max_drawdown'])}`, "
            f"Sharpe `{_fmt_num(row['sharpe'])}`, time in market `{_fmt_pct(row['time_in_market'])}`."
        )
    if best_drawdown.empty:
        lines.append("- none")

    lines.extend(["", "## Ablation Conclusions", ""])
    if baseline_best is not None and risk_only_best is not None:
        lines.append(
            f"- risk-only best `{risk_only_best['variant_label']}` vs baseline best `{baseline_best['variant_label']}`: "
            f"Sharpe `{_fmt_num(risk_only_best['sharpe'])}` vs `{_fmt_num(baseline_best['sharpe'])}`, "
            f"total return `{_fmt_pct(risk_only_best['total_return'])}` vs `{_fmt_pct(baseline_best['total_return'])}`."
        )
    if risk_only_best is not None and opp_only_best is not None:
        lines.append(
            f"- risk-only vs opportunity-only: `{risk_only_best['variant_label']}` reaches Sharpe `{_fmt_num(risk_only_best['sharpe'])}`, "
            f"while `{opp_only_best['variant_label']}` reaches `{_fmt_num(opp_only_best['sharpe'])}`."
        )
    if opp_asym_best is not None and opp_only_best is not None:
        lines.append(
            f"- asymmetry add-on test: `{opp_asym_best['variant_label']}` vs `{opp_only_best['variant_label']}` gives "
            f"Sharpe `{_fmt_num(opp_asym_best['sharpe'])}` vs `{_fmt_num(opp_only_best['sharpe'])}`."
        )
    if tilt_only_best is not None and risk_tilt_best is not None:
        lines.append(
            f"- tilt-only vs risk+tilt: `{tilt_only_best['variant_label']}` Sharpe `{_fmt_num(tilt_only_best['sharpe'])}` "
            f"vs `{risk_tilt_best['variant_label']}` Sharpe `{_fmt_num(risk_tilt_best['sharpe'])}`."
        )
    if always_long is not None:
        lines.append(
            f"- benchmark context: `{always_long['variant_label']}` ends with total return `{_fmt_pct(always_long['total_return'])}` "
            f"and max drawdown `{_fmt_pct(always_long['max_drawdown'])}`."
        )

    lines.extend(["", "## Practical Interpretation", ""])
    if risk_only_best is not None and baseline_best is not None:
        if risk_only_best["sharpe"] >= baseline_best["sharpe"] * 0.9:
            lines.append("- Most of the walk-forward value appears to come from avoiding high-risk states. Risk filtering alone retains most of the baseline Sharpe.")
        else:
            lines.append("- Risk filtering matters, but it does not fully explain the baseline performance on its own.")
    if opp_only_best is not None and risk_only_best is not None:
        sharpe_gap = float(opp_only_best["sharpe"] - risk_only_best["sharpe"])
        return_gap = float(opp_only_best["total_return"] - risk_only_best["total_return"])
        if sharpe_gap > 0.20 and return_gap > 1.0:
            lines.append("- Opportunity-only variants clearly outperform risk-only ones here, which suggests the walk-forward edge is being driven more by opportunity ranking than by simple risk avoidance.")
        elif opp_only_best["sharpe"] < risk_only_best["sharpe"]:
            lines.append("- Opportunity-only variants are weaker than risk-only ones here, which suggests upside ranking works best when paired with risk control.")
        else:
            lines.append("- Opportunity-only variants hold up comparably to risk-only ones, which suggests upside ranking itself is carrying meaningful edge.")
    if opp_asym_best is not None and opp_only_best is not None:
        if opp_asym_best["sharpe"] <= opp_only_best["sharpe"]:
            lines.append("- Asymmetry adds little or even slightly hurts once opportunity ranking is already present.")
        else:
            lines.append("- Asymmetry improves the opportunity-led variants, which suggests it is adding directional information beyond raw opportunity buckets.")
    if tilt_only_best is not None:
        lines.append("- Tilt labels remain useful as a compact execution layer, but their value should be judged relative to the simpler bucket-only filters above.")

    lines.extend(
        [
            "- This is still a daily-bar long/flat evaluation, not a production execution model.",
            "- Threshold testing is controlled and modest here, but repeated reuse of the same history can still overfit if pushed too far.",
            "- The purpose of this phase is to identify what is carrying the walk-forward edge, not to declare any variant production-ready.",
            "",
        ]
    )
    return "\n".join(lines)


def print_summary(results: pd.DataFrame, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the refinement stage."""
    best_sharpe = results.dropna(subset=["sharpe"]).sort_values("sharpe", ascending=False).iloc[0]
    best_return = results.dropna(subset=["total_return"]).sort_values("total_return", ascending=False).iloc[0]
    print(f"Policy variants tested: {len(results)}")
    print(f"Best Sharpe: {best_sharpe['variant_label']} ({best_sharpe['policy_family']}) -> {float(best_sharpe['sharpe']):.6f}")
    print(f"Best Total Return: {best_return['variant_label']} ({best_return['policy_family']}) -> {float(best_return['total_return']):.6f}")
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


def main() -> None:
    """Run the controlled walk-forward policy refinement / ablation stage."""
    try:
        args = parse_args()
        data = load_inputs(args.decision_analysis_walkforward_csv, args.price_json, args.start_date, args.end_date)
        results = run_refinement_backtest(data, args.cost_bps)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_summary_csv(results, out_csv)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(results, args.cost_bps, data["date"].iloc[0], data["date"].iloc[-1]), encoding="utf-8")

        print_summary(results, out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Policy refinement walk-forward failed: {exc}") from exc


if __name__ == "__main__":
    main()
