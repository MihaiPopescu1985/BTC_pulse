from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

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
    DEFAULT_POLICY_STRESS_WALKFORWARD_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    OUT_DIR,
)
from src.research.v4_iteration.run_policy_backtest import (
    PolicyDefinition,
    build_policy_definitions,
    build_signal_frame,
    simulate_policy_series,
)
from src.walkforward.run_policy_refinement_walkforward import (
    PolicyVariant,
    build_ablation_signal_frame,
    build_ablation_variants,
    build_baseline_variants,
)


BASELINE_COST_BPS = 10.0
TIME_SPLIT_NAMES: tuple[str, ...] = ("early_period", "middle_period", "late_period")
SELECTED_FAMILIES: tuple[str, ...] = ("opportunity_only", "opportunity_asym", "baseline", "risk_only")
BENCHMARK_NAMES: tuple[str, ...] = ("always_long", "always_flat")
MARKET_TYPE_ORDER: tuple[str, ...] = (
    "bullish_major_trend",
    "bearish_major_trend",
    "high_volatility",
    "lower_volatility",
)


@dataclass(frozen=True)
class SelectedPolicy:
    """Stress-test policy metadata pinned to an accepted refinement winner."""

    policy_name: str
    policy_family: str
    variant_label: str
    selection_source: str
    variant: PolicyVariant

    @property
    def policy_def(self) -> PolicyDefinition:
        return self.variant.policy_def


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for walk-forward robustness and stress testing."""
    parser = argparse.ArgumentParser(
        description="Stress-test the strongest SAFE BTC walk-forward policy variants across subperiods and execution assumptions.",
    )
    parser.add_argument(
        "--decision-analysis-walkforward-csv",
        default=str(DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH),
        help="Default: ../out/decision_analysis_walkforward.csv",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument(
        "--policy-refinement-walkforward-csv",
        default=str(DEFAULT_POLICY_REFINEMENT_WALKFORWARD_CSV_PATH),
        help="Default: ../out/policy_refinement_walkforward.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_POLICY_STRESS_WALKFORWARD_CSV_PATH),
        help="Default: ../out/policy_stress_walkforward.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(OUT_DIR / "policy_stress_walkforward.md"),
        help="Default: ../out/policy_stress_walkforward.md",
    )
    parser.add_argument("--start-date", default=None, help="Optional YYYY-MM-DD inclusive start date.")
    parser.add_argument("--end-date", default=None, help="Optional YYYY-MM-DD inclusive end date.")
    return parser.parse_args()


def _validate_date_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a date-first SAFE CSV artifact before joining."""
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


def _validate_refinement(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the accepted refinement summary used to pin stress-test winners."""
    required = {
        "policy_name",
        "policy_family",
        "variant_label",
        "sharpe",
        "total_return",
        "max_drawdown",
    }
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"policy_refinement_walkforward.csv is missing required columns: {missing}")
    return frame.copy()


def load_inputs(
    decision_path: str | Path,
    price_path: str | Path,
    refinement_path: str | Path,
    start_date: str | None,
    end_date: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and align walk-forward decision analysis, price history, and refinement winners."""
    decisions = _validate_date_frame("decision_analysis_walkforward", load_feature_csv(decision_path))
    required_columns = {
        "risk_bucket",
        "opportunity_bucket",
        "asymmetry_score",
        "decision_tilt",
        "history_ready_flag",
        "state_market_regime",
        "state_hmm_label",
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
        raise ValueError("Stress-test window is empty after applying date filters.")

    refinement = _validate_refinement(pd.read_csv(refinement_path))
    return merged, refinement


def _variant_lookup() -> dict[str, PolicyVariant]:
    """Build a lookup of accepted refinement policy variants by name."""
    variants = build_baseline_variants() + build_ablation_variants()
    return {variant.policy_name: variant for variant in variants}


def select_policies(refinement: pd.DataFrame) -> list[SelectedPolicy]:
    """Pin the fixed set of stress-tested policies from the accepted refinement artifact."""
    lookup = _variant_lookup()
    selections: list[SelectedPolicy] = []

    for family in SELECTED_FAMILIES:
        subset = refinement.loc[refinement["policy_family"] == family].dropna(subset=["sharpe"]).copy()
        if subset.empty:
            raise ValueError(f"Refinement summary does not contain a usable '{family}' policy family.")
        winner = subset.sort_values("sharpe", ascending=False).iloc[0]
        policy_name = str(winner["policy_name"])
        if policy_name not in lookup:
            raise ValueError(f"Selected refinement winner '{policy_name}' is not reproducible from current policy builders.")
        selections.append(
            SelectedPolicy(
                policy_name=policy_name,
                policy_family=str(winner["policy_family"]),
                variant_label=str(winner["variant_label"]),
                selection_source=f"best_{family}_by_sharpe",
                variant=lookup[policy_name],
            )
        )

    for benchmark_name in BENCHMARK_NAMES:
        subset = refinement.loc[refinement["policy_name"] == benchmark_name].copy()
        if subset.empty:
            raise ValueError(f"Refinement summary does not contain benchmark '{benchmark_name}'.")
        row = subset.iloc[0]
        selections.append(
            SelectedPolicy(
                policy_name=benchmark_name,
                policy_family=str(row["policy_family"]),
                variant_label=str(row["variant_label"]),
                selection_source=f"benchmark_{benchmark_name}",
                variant=lookup[benchmark_name],
            )
        )

    seen: set[str] = set()
    deduped: list[SelectedPolicy] = []
    for selection in selections:
        if selection.policy_name in seen:
            continue
        seen.add(selection.policy_name)
        deduped.append(selection)
    return deduped


def build_selected_signal_frame(data: pd.DataFrame, selected_policies: list[SelectedPolicy]) -> pd.DataFrame:
    """Rebuild the exact selected policy signals from the accepted walk-forward logic."""
    frames: list[pd.DataFrame] = []
    baseline_defs = tuple(selection.policy_def for selection in selected_policies if selection.policy_family == "baseline")
    ablation_variants = [selection.variant for selection in selected_policies if selection.policy_family != "baseline"]

    if baseline_defs:
        frames.append(build_signal_frame(data, baseline_defs))
    if ablation_variants:
        frames.append(build_ablation_signal_frame(data, ablation_variants))
    if not frames:
        raise ValueError("No selected policies were available to build signal frames.")
    return pd.concat(frames, axis=1)


def simulate_policy_series_with_delay(
    data: pd.DataFrame,
    signal_frame: pd.DataFrame,
    cost_bps: float,
    entry_delay_days: int,
) -> pd.DataFrame:
    """Convert day-t signals into delayed day-(t+1+d) close-to-close returns."""
    if entry_delay_days < 0:
        raise ValueError("entry_delay_days must be non-negative.")
    if entry_delay_days == 0:
        return simulate_policy_series(data, signal_frame, cost_bps)

    cost_rate = cost_bps / 10000.0
    out = data.loc[:, ["date", "close"]].copy()
    out["daily_return"] = out["close"].pct_change()

    shift_days = 1 + entry_delay_days
    for policy_name in signal_frame.columns:
        position_col = f"position_{policy_name}"
        strategy_col = f"strategy_return_{policy_name}"
        equity_col = f"equity_{policy_name}"

        position = signal_frame[policy_name].shift(shift_days).fillna(0.0)
        prev_position = position.shift(1).fillna(0.0)
        turnover = (position - prev_position).abs()
        strategy_return = position * out["daily_return"].fillna(0.0) - turnover * cost_rate
        equity = (1.0 + strategy_return).cumprod()

        out[position_col] = position
        out[strategy_col] = strategy_return
        out[equity_col] = equity

    return out


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    return float(drawdown.min())


def _extract_trade_returns(strategy_returns: pd.Series, positions: pd.Series) -> tuple[list[float], list[int]]:
    """Extract approximate holding-period returns from a daily policy series."""
    returns = strategy_returns.fillna(0.0).to_numpy(dtype=float)
    pos = positions.fillna(0.0).to_numpy(dtype=float)

    trade_returns: list[float] = []
    holding_lengths: list[int] = []
    in_trade = False
    cumulative = 1.0
    length = 0

    for idx in range(len(pos)):
        if pos[idx] > 0 and not in_trade:
            in_trade = True
            cumulative = 1.0
            length = 0

        if in_trade:
            cumulative *= 1.0 + returns[idx]
            if pos[idx] > 0:
                length += 1

            next_pos = pos[idx + 1] if idx + 1 < len(pos) else 0.0
            if next_pos <= 0:
                if idx + 1 < len(pos):
                    cumulative *= 1.0 + returns[idx + 1]
                trade_returns.append(cumulative - 1.0)
                holding_lengths.append(length)
                in_trade = False
                cumulative = 1.0
                length = 0

    return trade_returns, holding_lengths


def compute_metrics_for_slice(
    backtest: pd.DataFrame,
    selected_policies: list[SelectedPolicy],
    *,
    use_observation_annualization: bool,
) -> pd.DataFrame:
    """Compute policy metrics on a backtest slice.

    Observation annualization is used for non-contiguous conditional slices
    such as market-type splits, where calendar-span CAGR is not meaningful.
    """
    rows: list[dict[str, float | str]] = []
    if len(backtest) < 2:
        return pd.DataFrame(rows)

    if use_observation_annualization:
        years = max(len(backtest) - 1, 1) / 365.25
    else:
        elapsed_days = max((backtest["date"].iloc[-1] - backtest["date"].iloc[0]).days, 1)
        years = elapsed_days / 365.25

    for selection in selected_policies:
        position_col = f"position_{selection.policy_name}"
        strategy_col = f"strategy_return_{selection.policy_name}"
        if position_col not in backtest.columns or strategy_col not in backtest.columns:
            raise ValueError(f"Backtest slice is missing expected columns for {selection.policy_name}.")

        returns = pd.to_numeric(backtest[strategy_col], errors="coerce").fillna(0.0)
        positions = pd.to_numeric(backtest[position_col], errors="coerce").fillna(0.0)
        equity = (1.0 + returns).cumprod()

        total_return = float(equity.iloc[-1] - 1.0)
        cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 and equity.iloc[-1] > 0 else float("nan")
        max_drawdown = _max_drawdown(equity)
        std_daily = float(returns.std(ddof=0))
        sharpe = float(np.sqrt(365.25) * returns.mean() / std_daily) if std_daily > 0 else float("nan")
        time_in_market = float(positions.mean())

        entries = int(((positions > 0) & (positions.shift(1).fillna(0.0) <= 0)).sum())
        trade_returns, holding_lengths = _extract_trade_returns(returns, positions)
        win_rate = float(np.mean(np.array(trade_returns) > 0)) if trade_returns else float("nan")
        average_hold = float(np.mean(holding_lengths)) if holding_lengths else float("nan")

        rows.append(
            {
                "policy_name": selection.policy_name,
                "policy_family": selection.policy_family,
                "variant_label": selection.variant_label,
                "selection_source": selection.selection_source,
                "total_return": total_return,
                "cagr": cagr,
                "max_drawdown": max_drawdown,
                "sharpe": sharpe,
                "number_of_trades": entries,
                "time_in_market": time_in_market,
                "win_rate_holding_periods": win_rate,
                "average_holding_period": average_hold,
                "final_equity": float(equity.iloc[-1]),
            }
        )

    return pd.DataFrame(rows).sort_values(["policy_family", "policy_name"]).reset_index(drop=True)


def build_time_subperiods(data: pd.DataFrame) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """Split the available history into deterministic early/middle/late periods."""
    index_blocks = [block for block in np.array_split(np.arange(len(data)), len(TIME_SPLIT_NAMES)) if len(block) > 0]
    periods: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for label, block in zip(TIME_SPLIT_NAMES, index_blocks, strict=False):
        periods.append((label, data.loc[block[0], "date"], data.loc[block[-1], "date"]))
    return periods


def build_market_type_masks(data: pd.DataFrame) -> dict[str, pd.Series]:
    """Build explicit market-type splits from accepted walk-forward state context."""
    regime = data["state_market_regime"].astype("string")
    hmm = data["state_hmm_label"].astype("string")

    masks = {
        "bullish_major_trend": regime.eq("constructive_trend"),
        "bearish_major_trend": regime.isin(["fragile_trend", "downside_risk"]),
        "high_volatility": regime.eq("high_vol_stress") | hmm.eq("SHOCK"),
        "lower_volatility": hmm.isin(["CORE", "DRIFT"]),
    }
    return {name: mask.fillna(False) for name, mask in masks.items()}


def evaluate_scenario(
    backtest: pd.DataFrame,
    selected_policies: list[SelectedPolicy],
    *,
    scenario_type: str,
    scenario_name: str,
    cost_bps: float,
    entry_delay_days: int,
    mask: pd.Series | None = None,
    use_observation_annualization: bool = False,
) -> pd.DataFrame:
    """Evaluate a single stress scenario and attach scenario metadata."""
    scenario_frame = backtest.copy()
    if mask is not None:
        aligned_mask = mask.reindex(scenario_frame.index).fillna(False)
        scenario_frame = scenario_frame.loc[aligned_mask].copy()
    if len(scenario_frame) < 2:
        return pd.DataFrame()

    metrics = compute_metrics_for_slice(
        scenario_frame,
        selected_policies,
        use_observation_annualization=use_observation_annualization,
    )
    if metrics.empty:
        return metrics

    metrics["scenario_type"] = scenario_type
    metrics["scenario_name"] = scenario_name
    metrics["cost_bps"] = float(cost_bps)
    metrics["entry_delay_days"] = int(entry_delay_days)
    metrics["subperiod_start"] = scenario_frame["date"].iloc[0].strftime("%Y-%m-%d")
    metrics["subperiod_end"] = scenario_frame["date"].iloc[-1].strftime("%Y-%m-%d")
    metrics["rows_in_scenario"] = int(len(scenario_frame))
    return metrics.loc[
        :,
        [
            "policy_name",
            "policy_family",
            "variant_label",
            "selection_source",
            "scenario_type",
            "scenario_name",
            "cost_bps",
            "entry_delay_days",
            "subperiod_start",
            "subperiod_end",
            "rows_in_scenario",
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
    ]


def run_stress_test(data: pd.DataFrame, selected_policies: list[SelectedPolicy]) -> pd.DataFrame:
    """Run the fixed stress-test matrix over the accepted walk-forward winners."""
    signal_frame = build_selected_signal_frame(data, selected_policies)
    scenario_rows: list[pd.DataFrame] = []

    base_backtest = simulate_policy_series_with_delay(data, signal_frame, BASELINE_COST_BPS, entry_delay_days=0)
    base_backtest = base_backtest.merge(
        data.loc[:, ["date", "state_market_regime", "state_hmm_label"]],
        on="date",
        how="left",
        validate="one_to_one",
    )

    scenario_rows.append(
        evaluate_scenario(
            base_backtest,
            selected_policies,
            scenario_type="full_sample",
            scenario_name="full_sample",
            cost_bps=BASELINE_COST_BPS,
            entry_delay_days=0,
        )
    )

    for period_name, start_date, end_date in build_time_subperiods(base_backtest):
        mask = (base_backtest["date"] >= start_date) & (base_backtest["date"] <= end_date)
        scenario_rows.append(
            evaluate_scenario(
                base_backtest,
                selected_policies,
                scenario_type="time_subperiod",
                scenario_name=period_name,
                cost_bps=BASELINE_COST_BPS,
                entry_delay_days=0,
                mask=mask,
            )
        )

    for market_name, mask in build_market_type_masks(base_backtest).items():
        scenario_rows.append(
            evaluate_scenario(
                base_backtest,
                selected_policies,
                scenario_type="market_type",
                scenario_name=market_name,
                cost_bps=BASELINE_COST_BPS,
                entry_delay_days=0,
                mask=mask,
                use_observation_annualization=True,
            )
        )

    for cost_bps in (0.0, 10.0, 25.0, 50.0):
        cost_backtest = simulate_policy_series_with_delay(data, signal_frame, cost_bps, entry_delay_days=0)
        scenario_rows.append(
            evaluate_scenario(
                cost_backtest,
                selected_policies,
                scenario_type="cost_sensitivity",
                scenario_name=f"cost_{int(cost_bps)}bps",
                cost_bps=cost_bps,
                entry_delay_days=0,
            )
        )

    for delay_days in (0, 1):
        delayed_backtest = simulate_policy_series_with_delay(data, signal_frame, BASELINE_COST_BPS, entry_delay_days=delay_days)
        scenario_rows.append(
            evaluate_scenario(
                delayed_backtest,
                selected_policies,
                scenario_type="delay_sensitivity",
                scenario_name=f"delay_{delay_days}d",
                cost_bps=BASELINE_COST_BPS,
                entry_delay_days=delay_days,
            )
        )

    result = pd.concat([frame for frame in scenario_rows if not frame.empty], ignore_index=True)
    return result.sort_values(["policy_family", "policy_name", "scenario_type", "scenario_name"]).reset_index(drop=True)


def _fmt_pct(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def summarize_policy_robustness(results: pd.DataFrame) -> pd.DataFrame:
    """Aggregate scenario-level results into a simple robustness table."""
    summary = (
        results.groupby(["policy_name", "policy_family", "variant_label", "selection_source"], dropna=False)
        .agg(
            scenario_count=("scenario_name", "nunique"),
            median_sharpe=("sharpe", "median"),
            median_total_return=("total_return", "median"),
            worst_max_drawdown=("max_drawdown", "min"),
            best_max_drawdown=("max_drawdown", "max"),
            positive_sharpe_count=("sharpe", lambda values: int(pd.Series(values).dropna().gt(0).sum())),
            positive_return_count=("total_return", lambda values: int(pd.Series(values).dropna().gt(0).sum())),
        )
        .reset_index()
    )
    return summary.sort_values(["median_sharpe", "median_total_return"], ascending=[False, False]).reset_index(drop=True)


def _active_robustness(robustness: pd.DataFrame) -> pd.DataFrame:
    """Drop the always-flat benchmark from headline robustness callouts."""
    active = robustness.loc[robustness["policy_name"] != "always_flat"].copy()
    return active if not active.empty else robustness


def _scenario_lookup(results: pd.DataFrame, scenario_type: str, scenario_name: str) -> pd.DataFrame:
    subset = results.loc[(results["scenario_type"] == scenario_type) & (results["scenario_name"] == scenario_name)].copy()
    return subset.sort_values("sharpe", ascending=False, na_position="last")


def _policy_scenario_row(results: pd.DataFrame, policy_name: str, scenario_type: str, scenario_name: str) -> pd.Series | None:
    subset = results.loc[
        (results["policy_name"] == policy_name)
        & (results["scenario_type"] == scenario_type)
        & (results["scenario_name"] == scenario_name)
    ]
    if subset.empty:
        return None
    return subset.iloc[0]


def render_markdown(results: pd.DataFrame, selected_policies: list[SelectedPolicy], data: pd.DataFrame) -> str:
    """Render a compact robustness report for the selected walk-forward policies."""
    robustness = summarize_policy_robustness(results)
    time_periods = build_time_subperiods(data)
    subperiod_labels = ", ".join(
        f"`{name}` = {start.strftime('%Y-%m-%d')} -> {end.strftime('%Y-%m-%d')}" for name, start, end in time_periods
    )

    active_robustness = _active_robustness(robustness)
    best_by_median_sharpe = active_robustness.dropna(subset=["median_sharpe"]).iloc[0]
    best_by_drawdown = active_robustness.sort_values("worst_max_drawdown", ascending=False).iloc[0]

    lines = [
        "# Policy Stress Walk-Forward",
        "",
        "This phase stress-tests the strongest fixed walk-forward variants. No new optimization sweep is performed here.",
        "",
        f"Stress-test universe: `{len(selected_policies)}` selected policies, `{results[['scenario_type', 'scenario_name']].drop_duplicates().shape[0]}` explicit scenarios",
        f"Date range: `{data['date'].iloc[0].strftime('%Y-%m-%d')}` -> `{data['date'].iloc[-1].strftime('%Y-%m-%d')}`",
        "",
        "## Overall Robustness",
        "",
        "| Policy | Family | Median Sharpe | Median Total Return | Worst Max Drawdown | Positive Sharpe Scenarios | Positive Return Scenarios |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for _, row in robustness.iterrows():
        lines.append(
            f"| `{row['variant_label']}` | `{row['policy_family']}` | {_fmt_num(row['median_sharpe'])} | {_fmt_pct(row['median_total_return'])} | {_fmt_pct(row['worst_max_drawdown'])} | {int(row['positive_sharpe_count'])}/{int(row['scenario_count'])} | {int(row['positive_return_count'])}/{int(row['scenario_count'])} |"
        )

    lines.extend(
        [
            "",
            f"- Strongest policy by median Sharpe across scenarios: `{best_by_median_sharpe['variant_label']}` at `{_fmt_num(best_by_median_sharpe['median_sharpe'])}`.",
            f"- Strongest policy by worst-case drawdown resilience: `{best_by_drawdown['variant_label']}` with worst scenario drawdown `{_fmt_pct(best_by_drawdown['worst_max_drawdown'])}`.",
            "",
            "## Time Stability",
            "",
            f"Deterministic subperiod boundaries: {subperiod_labels}.",
        ]
    )

    for selection in selected_policies:
        period_bits: list[str] = []
        for period_name, _, _ in time_periods:
            row = _policy_scenario_row(results, selection.policy_name, "time_subperiod", period_name)
            if row is None:
                continue
            period_bits.append(f"{period_name}: Sharpe {_fmt_num(row['sharpe'])}, total return {_fmt_pct(row['total_return'])}")
        if period_bits:
            lines.append(f"- `{selection.variant_label}`: " + "; ".join(period_bits) + ".")

    lines.extend(
        [
            "",
            "## Market-Type Rules",
            "",
            "- `bullish_major_trend`: `state_market_regime == constructive_trend`.",
            "- `bearish_major_trend`: `state_market_regime in {fragile_trend, downside_risk}`.",
            "- `high_volatility`: `state_market_regime == high_vol_stress` or `state_hmm_label == SHOCK`.",
            "- `lower_volatility`: `state_hmm_label in {CORE, DRIFT}`.",
            "- Market-type scenario metrics are conditional row-slice summaries. They are useful for robustness checks, but they are not standalone contiguous backtests.",
            "",
            "## Cost Sensitivity",
            "",
        ]
    )

    for selection in selected_policies:
        low_cost = _policy_scenario_row(results, selection.policy_name, "cost_sensitivity", "cost_0bps")
        high_cost = _policy_scenario_row(results, selection.policy_name, "cost_sensitivity", "cost_50bps")
        if low_cost is None or high_cost is None:
            continue
        lines.append(
            f"- `{selection.variant_label}`: Sharpe `{_fmt_num(low_cost['sharpe'])}` at 0 bps vs `{_fmt_num(high_cost['sharpe'])}` at 50 bps; total return `{_fmt_pct(low_cost['total_return'])}` vs `{_fmt_pct(high_cost['total_return'])}`."
        )

    lines.extend(["", "## Delay Sensitivity", ""])
    for selection in selected_policies:
        no_delay = _policy_scenario_row(results, selection.policy_name, "delay_sensitivity", "delay_0d")
        delayed = _policy_scenario_row(results, selection.policy_name, "delay_sensitivity", "delay_1d")
        if no_delay is None or delayed is None:
            continue
        lines.append(
            f"- `{selection.variant_label}`: Sharpe `{_fmt_num(no_delay['sharpe'])}` with normal next-day execution vs `{_fmt_num(delayed['sharpe'])}` with a 1-day extra delay; total return `{_fmt_pct(no_delay['total_return'])}` vs `{_fmt_pct(delayed['total_return'])}`."
        )

    best_opp_only = robustness.loc[robustness["policy_family"] == "opportunity_only"].head(1)
    best_baseline = robustness.loc[robustness["policy_family"] == "baseline"].head(1)
    best_risk_only = robustness.loc[robustness["policy_family"] == "risk_only"].head(1)

    lines.extend(["", "## Practical Interpretation", ""])
    if not best_opp_only.empty and not best_baseline.empty:
        opp_row = best_opp_only.iloc[0]
        base_row = best_baseline.iloc[0]
        if float(opp_row["median_sharpe"]) > float(base_row["median_sharpe"]):
            lines.append("- Opportunity-led logic remains the strongest headline performer under this stress grid, but it should still be judged against its drawdown profile and scenario dependence.")
        else:
            lines.append("- The best baseline policy is at least as robust as the best opportunity-only variant, which argues for a simpler and more defensible rule set.")
    if not best_risk_only.empty:
        risk_row = best_risk_only.iloc[0]
        if float(risk_row["median_sharpe"]) < 0.5:
            lines.append("- Risk-only filtering helps, but on its own it does not look like the main carrier of the walk-forward edge.")
        else:
            lines.append("- Risk-only filtering remains materially useful, which suggests part of the edge comes from avoiding obviously poor states.")

    lines.extend(
        [
            "- If the 1-day extra delay materially damages a policy, the signal likely decays quickly and may depend on prompt execution.",
            "- If a policy collapses at 25–50 bps, it is fragile to practical friction even if the raw backtest looks strong.",
            "- If a policy only shines in one subperiod, treat it as regime-dependent rather than robust.",
            "- This remains a daily-bar long/flat study. It is useful as a robustness filter, not a declaration of production readiness.",
            "",
        ]
    )
    return "\n".join(lines)


def export_summary_csv(frame: pd.DataFrame, path: str | Path) -> None:
    """Write the stress-test summary as a plain CSV."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False, float_format="%.8f")


def print_summary(results: pd.DataFrame, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the stress-test stage."""
    scenario_count = int(results[["scenario_type", "scenario_name"]].drop_duplicates().shape[0])
    robustness = summarize_policy_robustness(results)
    active_robustness = _active_robustness(robustness)
    best_by_median_sharpe = active_robustness.dropna(subset=["median_sharpe"]).iloc[0]
    best_by_drawdown = active_robustness.sort_values("worst_max_drawdown", ascending=False).iloc[0]
    print(f"Scenarios tested: {scenario_count}")
    print(
        "Best median Sharpe policy: "
        f"{best_by_median_sharpe['variant_label']} ({best_by_median_sharpe['policy_family']}) -> "
        f"{float(best_by_median_sharpe['median_sharpe']):.6f}"
    )
    print(
        "Best drawdown resilience policy: "
        f"{best_by_drawdown['variant_label']} ({best_by_drawdown['policy_family']}) -> "
        f"{float(best_by_drawdown['worst_max_drawdown']):.6f}"
    )
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


def main() -> None:
    """Run SAFE walk-forward robustness and stress testing on fixed accepted variants."""
    try:
        args = parse_args()
        data, refinement = load_inputs(
            args.decision_analysis_walkforward_csv,
            args.price_json,
            args.policy_refinement_walkforward_csv,
            args.start_date,
            args.end_date,
        )
        selected_policies = select_policies(refinement)
        results = run_stress_test(data, selected_policies)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_summary_csv(results, out_csv)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(results, selected_policies, data), encoding="utf-8")

        print_summary(results, out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Policy stress walk-forward failed: {exc}") from exc


if __name__ == "__main__":
    main()
