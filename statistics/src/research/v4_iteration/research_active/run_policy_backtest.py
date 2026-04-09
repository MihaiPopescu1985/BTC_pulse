from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv, load_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import (
    DEFAULT_DECISION_ANALYSIS_CSV_PATH,
    DEFAULT_DECISION_VALIDATION_CSV_PATH,
    DEFAULT_POLICY_BACKTEST_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    OUT_DIR,
)


POLICY_NAMES: tuple[str, ...] = ("policy_a", "policy_b", "policy_c")
ANNUALIZATION_DAYS = 365.25
TRADING_DAYS = 365.25


@dataclass(frozen=True)
class PolicyDefinition:
    name: str
    label: str
    signal_fn: Callable[[pd.Series], bool]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the first SAFE decision-policy backtest."""
    parser = argparse.ArgumentParser(
        description="Backtest simple long/flat policies driven by SAFE decision_analysis.csv on BTC daily closes.",
    )
    parser.add_argument(
        "--decision-analysis-csv",
        default=str(DEFAULT_DECISION_ANALYSIS_CSV_PATH),
        help="Default: ../out/decision_analysis.csv",
    )
    parser.add_argument(
        "--decision-validation-csv",
        default=str(DEFAULT_DECISION_VALIDATION_CSV_PATH),
        help="Default: ../out/decision_validation.csv",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--out-csv", default=str(DEFAULT_POLICY_BACKTEST_CSV_PATH), help="Default: ../out/policy_backtest.csv")
    parser.add_argument("--out-md", default=str(OUT_DIR / "policy_backtest.md"), help="Default: ../out/policy_backtest.md")
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


def _validate_decision_validation(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the descriptive decision validation artifact used for context in the markdown summary."""
    required_columns = {"object_type", "object_name", "target", "sample_count", "mean", "median", "win_rate", "event_rate", "spearman_corr", "monotonicity_score"}
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"decision_validation.csv is missing required columns: {missing}")
    return frame.copy()


def load_inputs(
    decision_path: str | Path,
    decision_validation_path: str | Path,
    price_path: str | Path,
    start_date: str | None,
    end_date: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and align decision analysis, decision validation, and BTC close data."""
    decisions = _validate_date_frame("decision_analysis", load_feature_csv(decision_path))
    validation = _validate_decision_validation(pd.read_csv(decision_validation_path))

    price = load_daily_price_json(str(price_path)).reset_index().rename(columns={"timestamp": "date"})
    price = _validate_date_frame("daily_price", price.loc[:, ["date", "close"]])

    if set(decisions["date"]) != set(price["date"]):
        raise ValueError("decision_analysis.csv and daily_price.json must contain the same anchor-date set.")

    merged = decisions.merge(price, on="date", how="inner", validate="one_to_one")
    if start_date is not None:
        merged = merged.loc[merged["date"] >= pd.to_datetime(start_date, errors="raise")].copy()
    if end_date is not None:
        merged = merged.loc[merged["date"] <= pd.to_datetime(end_date, errors="raise")].copy()
    merged = merged.sort_values("date").reset_index(drop=True)
    if merged.empty:
        raise ValueError("Backtest window is empty after applying date filters.")
    return merged, validation


def _as_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def build_policy_definitions() -> tuple[PolicyDefinition, ...]:
    """Return the three first-pass long/flat policies."""

    def signal_policy_a(row: pd.Series) -> bool:
        return (
            row["decision_tilt"] in {"favor_longs", "selective_longs"}
            and pd.notna(row["risk_bucket"])
            and float(row["risk_bucket"]) <= 5.0
            and pd.notna(row["asymmetry_score"])
            and float(row["asymmetry_score"]) > 0.0
        )

    def signal_policy_b(row: pd.Series) -> bool:
        return (
            pd.notna(row["opportunity_bucket"])
            and float(row["opportunity_bucket"]) >= 8.0
            and pd.notna(row["risk_bucket"])
            and float(row["risk_bucket"]) <= 6.0
        )

    def signal_policy_c(row: pd.Series) -> bool:
        return row["decision_tilt"] == "favor_longs"

    return (
        PolicyDefinition("policy_a", "Conservative", signal_policy_a),
        PolicyDefinition("policy_b", "Opportunity-led", signal_policy_b),
        PolicyDefinition("policy_c", "Defensive trend-following", signal_policy_c),
    )


def _override_exit_conditions(policy_name: str, row: pd.Series, current_signal: bool) -> bool:
    """Apply policy-specific exit overrides on top of the raw long-entry signal."""
    risk_bucket = float(row["risk_bucket"]) if pd.notna(row["risk_bucket"]) else np.nan
    asymmetry = float(row["asymmetry_score"]) if pd.notna(row["asymmetry_score"]) else np.nan
    tilt = row["decision_tilt"]
    opportunity_bucket = float(row["opportunity_bucket"]) if pd.notna(row["opportunity_bucket"]) else np.nan

    if policy_name == "policy_a":
        if tilt in {"reduce_exposure", "avoid_new_longs"}:
            return False
        if pd.notna(risk_bucket) and risk_bucket >= 8.0:
            return False
        return current_signal
    if policy_name == "policy_b":
        if pd.notna(opportunity_bucket) and opportunity_bucket <= 4.0:
            return False
        if pd.notna(risk_bucket) and risk_bucket >= 8.0:
            return False
        return current_signal
    if policy_name == "policy_c":
        if pd.notna(risk_bucket) and risk_bucket >= 7.0:
            return False
        if pd.notna(asymmetry) and asymmetry < 0.0:
            return False
        return current_signal
    return current_signal


def build_signal_frame(data: pd.DataFrame, policies: tuple[PolicyDefinition, ...]) -> pd.DataFrame:
    """Build daily desired-position signals from current-day decision analysis."""
    signal_frame = pd.DataFrame(index=data.index)
    for policy in policies:
        raw_signal = data.apply(policy.signal_fn, axis=1).astype(float)
        signal_frame[policy.name] = data.apply(
            lambda row: float(_override_exit_conditions(policy.name, row, bool(raw_signal.loc[row.name]))),
            axis=1,
        )
    return signal_frame


def simulate_policy_series(data: pd.DataFrame, signal_frame: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """Convert day-t signals into day-(t+1) close-to-close policy returns."""
    cost_rate = cost_bps / 10000.0
    out = data.loc[:, ["date", "close"]].copy()
    out["daily_return"] = out["close"].pct_change()

    for policy_name in signal_frame.columns:
        position_col = f"position_{policy_name}"
        strategy_col = f"strategy_return_{policy_name}"
        equity_col = f"equity_{policy_name}"

        position = signal_frame[policy_name].shift(1).fillna(0.0)
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
    """Extract completed or terminal holding-period returns and lengths from daily policy series."""
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


def compute_policy_metrics(backtest: pd.DataFrame, policies: tuple[PolicyDefinition, ...]) -> pd.DataFrame:
    """Compute first-pass long/flat backtest metrics for each policy."""
    rows: list[dict[str, float | str]] = []
    if len(backtest) < 2:
        raise ValueError("Backtest requires at least two rows of daily data.")

    elapsed_days = max((backtest["date"].iloc[-1] - backtest["date"].iloc[0]).days, 1)
    years = elapsed_days / ANNUALIZATION_DAYS

    for policy in policies:
        position_col = f"position_{policy.name}"
        strategy_col = f"strategy_return_{policy.name}"
        equity_col = f"equity_{policy.name}"

        returns = _as_float(backtest[strategy_col]).fillna(0.0)
        positions = _as_float(backtest[position_col]).fillna(0.0)
        equity = _as_float(backtest[equity_col]).fillna(1.0)

        total_return = float(equity.iloc[-1] - 1.0)
        cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 and equity.iloc[-1] > 0 else float("nan")
        max_drawdown = _max_drawdown(equity)
        std_daily = float(returns.std(ddof=0))
        sharpe = float(np.sqrt(TRADING_DAYS) * returns.mean() / std_daily) if std_daily > 0 else float("nan")
        time_in_market = float(positions.mean())

        entries = ((positions > 0) & (positions.shift(1).fillna(0.0) <= 0)).sum()
        trade_returns, holding_lengths = _extract_trade_returns(returns, positions)
        number_of_trades = int(entries)
        win_rate_holding_periods = float(np.mean(np.array(trade_returns) > 0)) if trade_returns else float("nan")
        average_holding_period = float(np.mean(holding_lengths)) if holding_lengths else float("nan")
        exposure_adjusted_return = float(total_return / time_in_market) if time_in_market > 0 else float("nan")

        rows.append(
            {
                "policy_name": policy.name,
                "policy_label": policy.label,
                "total_return": total_return,
                "cagr": cagr,
                "max_drawdown": max_drawdown,
                "sharpe": sharpe,
                "number_of_trades": number_of_trades,
                "time_in_market": time_in_market,
                "win_rate_holding_periods": win_rate_holding_periods,
                "average_holding_period": average_holding_period,
                "exposure_adjusted_return": exposure_adjusted_return,
                "final_equity": float(equity.iloc[-1]),
            }
        )

    return pd.DataFrame(rows).sort_values("policy_name").reset_index(drop=True)


def _fmt_pct(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def _validation_context(validation: pd.DataFrame) -> dict[str, float]:
    """Extract a few high-signal validation metrics for markdown context."""
    context: dict[str, float] = {}
    lookups = [
        ("opportunity_ret_spearman", "score_corr", "opportunity_score", "ret_10d", "spearman_corr"),
        ("risk_down_spearman", "score_corr", "risk_score", "max_down_10d", "spearman_corr"),
        ("asymmetry_ret_spearman", "score_corr", "asymmetry_score", "ret_10d", "spearman_corr"),
        ("opportunity_bucket_mono", "opportunity_bucket", "1", "ret_10d", "monotonicity_score"),
        ("risk_bucket_mono", "risk_bucket", "1", "max_down_10d", "monotonicity_score"),
    ]
    for key, object_type, object_name, target, metric in lookups:
        subset = validation.loc[
            (validation["object_type"] == object_type)
            & (validation["target"] == target)
            & ((validation["object_name"] == object_name) if object_type == "score_corr" else True),
            metric,
        ].dropna()
        context[key] = float(subset.iloc[0]) if not subset.empty else float("nan")
    return context


def render_markdown(metrics: pd.DataFrame, validation: pd.DataFrame, cost_bps: float, start_date: pd.Timestamp, end_date: pd.Timestamp) -> str:
    """Render a compact human-readable summary of the first-pass policy backtest."""
    context = _validation_context(validation)
    best_total = metrics.sort_values("total_return", ascending=False).iloc[0]
    best_sharpe = metrics.sort_values("sharpe", ascending=False, na_position="last").iloc[0]
    worst_drawdown = metrics.sort_values("max_drawdown", ascending=True).iloc[0]

    lines = [
        "# Policy Backtest",
        "",
        "This is a simple daily-bar long/flat backtest. Positions are formed from day-t signals and applied to day-(t+1) close-to-close returns.",
        "",
        f"Backtest window: `{start_date.strftime('%Y-%m-%d')}` -> `{end_date.strftime('%Y-%m-%d')}`",
        f"Transaction cost assumption: `{cost_bps:.1f}` bps per position change",
        "",
        "## Summary Table",
        "",
        "| Policy | Total Return | CAGR | Max Drawdown | Sharpe | Trades | Time in Market | Win Rate | Avg Hold | Exposure-Adjusted Return |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for _, row in metrics.iterrows():
        lines.append(
            f"| `{row['policy_label']}` | {_fmt_pct(row['total_return'])} | {_fmt_pct(row['cagr'])} | {_fmt_pct(row['max_drawdown'])} | {_fmt_num(row['sharpe'])} | {int(row['number_of_trades'])} | {_fmt_pct(row['time_in_market'])} | {_fmt_pct(row['win_rate_holding_periods'])} | {_fmt_num(row['average_holding_period'])} | {_fmt_pct(row['exposure_adjusted_return'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Best total return: `{best_total['policy_label']}` with {_fmt_pct(best_total['total_return'])} total return and {_fmt_pct(best_total['cagr'])} CAGR.",
            f"- Best Sharpe: `{best_sharpe['policy_label']}` with Sharpe `{_fmt_num(best_sharpe['sharpe'])}`.",
            f"- Worst drawdown profile: `{worst_drawdown['policy_label']}` at {_fmt_pct(worst_drawdown['max_drawdown'])} max drawdown.",
            "",
            "## Decision-Layer Context",
            "",
            f"- opportunity_score vs realized ret_10d Spearman from Phase 8: `{_fmt_num(context.get('opportunity_ret_spearman'))}`",
            f"- risk_score vs realized max_down_10d Spearman from Phase 8: `{_fmt_num(context.get('risk_down_spearman'))}`",
            f"- asymmetry_score vs realized ret_10d Spearman from Phase 8: `{_fmt_num(context.get('asymmetry_ret_spearman'))}`",
            f"- opportunity bucket monotonicity vs realized ret_10d from Phase 8: `{_fmt_num(context.get('opportunity_bucket_mono'))}`",
            f"- risk bucket monotonicity vs realized max_down_10d from Phase 8: `{_fmt_num(context.get('risk_bucket_mono'))}`",
            "",
            "## Practical Readout",
            "",
        ]
    )

    if best_total["total_return"] > 0:
        lines.append("- The decision layer survives translation into a simple tradable rule in at least one first-pass policy, which supports further refinement.")
    else:
        lines.append("- None of the first-pass policies produced a positive compounded result, so the descriptive layer does not yet survive conversion into a basic trading rule.")

    if best_sharpe["sharpe"] > 0:
        lines.append("- At least one policy produced positive risk-adjusted performance, which suggests the ranking layer may contain tradable structure even before optimization.")
    else:
        lines.append("- Risk-adjusted performance is weak across the simple policies, so the decision layer may still be better suited for context than direct execution.")

    lines.append("- This is only a first-pass policy test. The execution is next-day and cost-aware, but the decision layer being tested is still a descriptive full-sample layer rather than a strict walk-forward state mapper.")
    lines.append("- This remains an approximate daily close-to-close backtest. It does not capture intraday execution ordering, slippage variability, or production constraints.")
    lines.append("- No parameter sweep is included here. The purpose is only to test whether the validated ranking layer can support simple long/flat behavior.")
    lines.append("")
    return "\n".join(lines)


def print_summary(metrics: pd.DataFrame, rows_processed: int, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the policy backtest stage."""
    print(f"Rows processed: {rows_processed}")
    for _, row in metrics.iterrows():
        print(
            f"{row['policy_name']}: total_return={float(row['total_return']):.6f} "
            f"cagr={float(row['cagr']):.6f} max_drawdown={float(row['max_drawdown']):.6f} "
            f"sharpe={float(row['sharpe']):.6f} trades={int(row['number_of_trades'])}"
        )
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


def main() -> None:
    """Run SAFE v4.0 Phase 9: simple policy backtest on top of the decision layer."""
    try:
        args = parse_args()
        merged, validation = load_inputs(
            args.decision_analysis_csv,
            args.decision_validation_csv,
            args.price_json,
            args.start_date,
            args.end_date,
        )
        policies = build_policy_definitions()
        signal_frame = build_signal_frame(merged, policies)
        backtest = simulate_policy_series(merged, signal_frame, args.cost_bps)
        metrics = compute_policy_metrics(backtest, policies)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_columns = [
            "close",
            "daily_return",
            "position_policy_a",
            "position_policy_b",
            "position_policy_c",
            "strategy_return_policy_a",
            "strategy_return_policy_b",
            "strategy_return_policy_c",
            "equity_policy_a",
            "equity_policy_b",
            "equity_policy_c",
        ]
        export_feature_csv(backtest.set_index("date"), out_csv, columns=export_columns)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(
            render_markdown(metrics, validation, args.cost_bps, backtest["date"].iloc[0], backtest["date"].iloc[-1]),
            encoding="utf-8",
        )

        print_summary(metrics, len(backtest), out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Policy backtest failed: {exc}") from exc


if __name__ == "__main__":
    main()
