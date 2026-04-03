from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv, load_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import (
    DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH,
    DEFAULT_POLICY_BACKTEST_CSV_PATH,
    DEFAULT_POLICY_BACKTEST_WALKFORWARD_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    OUT_DIR,
)
from src.run_policy_backtest import build_policy_definitions, build_signal_frame, compute_policy_metrics, simulate_policy_series


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the strict walk-forward policy backtest."""
    parser = argparse.ArgumentParser(
        description="Backtest SAFE BTC long/flat policies on the strict walk-forward decision layer.",
    )
    parser.add_argument(
        "--decision-analysis-walkforward-csv",
        default=str(DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH),
        help="Default: ../out/decision_analysis_walkforward.csv",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument(
        "--prototype-policy-csv",
        default=str(DEFAULT_POLICY_BACKTEST_CSV_PATH),
        help="Optional descriptive prototype baseline: ../out/policy_backtest.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_POLICY_BACKTEST_WALKFORWARD_CSV_PATH),
        help="Default: ../out/policy_backtest_walkforward.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(OUT_DIR / "policy_backtest_walkforward.md"),
        help="Default: ../out/policy_backtest_walkforward.md",
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
    required_columns = {"risk_score", "opportunity_score", "asymmetry_score", "risk_bucket", "opportunity_bucket", "decision_tilt"}
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
        raise ValueError("Walk-forward backtest window is empty after applying date filters.")
    return merged


def load_prototype_metrics(path: str | Path) -> pd.DataFrame | None:
    """Load the earlier descriptive prototype backtest if it exists."""
    csv_path = Path(path)
    if not csv_path.exists():
        return None
    prototype = _validate_date_frame("prototype_policy_backtest", load_feature_csv(csv_path))
    policies = build_policy_definitions()
    return compute_policy_metrics(prototype, policies)


def _fmt_pct(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: float | int | str | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def render_markdown(
    metrics: pd.DataFrame,
    prototype_metrics: pd.DataFrame | None,
    cost_bps: float,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    usable_rows: int,
    total_rows: int,
) -> str:
    """Render a compact human-readable summary of the leakage-free walk-forward policy backtest."""
    best_total = metrics.sort_values("total_return", ascending=False).iloc[0]
    best_sharpe = metrics.sort_values("sharpe", ascending=False, na_position="last").iloc[0]

    lines = [
        "# Walk-Forward Policy Backtest",
        "",
        "This is the first leakage-free policy result. Signals are computed from the walk-forward decision layer, which itself uses only prior resolved history.",
        "",
        f"Backtest window: `{start_date.strftime('%Y-%m-%d')}` -> `{end_date.strftime('%Y-%m-%d')}`",
        f"Transaction cost assumption: `{cost_bps:.1f}` bps per position change",
        f"Rows with usable walk-forward decision history: `{usable_rows}` / `{total_rows}`",
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
            "## Walk-Forward Interpretation",
            "",
            f"- Best total return: `{best_total['policy_label']}` with {_fmt_pct(best_total['total_return'])} total return and {_fmt_pct(best_total['cagr'])} CAGR.",
            f"- Best Sharpe: `{best_sharpe['policy_label']}` with Sharpe `{_fmt_num(best_sharpe['sharpe'])}`.",
        ]
    )

    if prototype_metrics is not None:
        lines.extend(["", "## Comparison To Descriptive Prototype", ""])
        prototype_map = prototype_metrics.set_index("policy_name")
        for _, row in metrics.iterrows():
            if row["policy_name"] not in prototype_map.index:
                continue
            baseline = prototype_map.loc[row["policy_name"]]
            delta_return = float(row["total_return"] - baseline["total_return"])
            delta_sharpe = float(row["sharpe"] - baseline["sharpe"]) if pd.notna(row["sharpe"]) and pd.notna(baseline["sharpe"]) else float("nan")
            delta_drawdown = float(row["max_drawdown"] - baseline["max_drawdown"])
            lines.append(
                f"- `{row['policy_label']}`: total return delta {_fmt_pct(delta_return)}, Sharpe delta {_fmt_num(delta_sharpe)}, max drawdown delta {_fmt_pct(delta_drawdown)}."
            )
        lines.append("- Any degradation here is expected and informative: this is the first version that removes the descriptive full-sample state mapping from the policy signal path.")
    else:
        lines.extend(
            [
                "",
                "## Comparison To Descriptive Prototype",
                "",
                "- Prototype comparison unavailable because `../out/policy_backtest.csv` was not found.",
            ]
        )

    lines.extend(
        [
            "",
            "## Practical Readout",
            "",
            "- This is the first credible walk-forward policy proof because every daily signal is built only from information that would have been available then.",
            "- Sparse early history naturally suppresses signals; no future-informed fill-ins are used.",
            "- This remains a daily close-to-close approximation. It is useful as proof-of-validity, not as a production execution model.",
            "- Thresholds are intentionally unchanged from the prototype. No optimization sweep is performed here.",
            "",
        ]
    )
    return "\n".join(lines)


def print_summary(metrics: pd.DataFrame, rows_processed: int, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the walk-forward policy backtest."""
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
    """Run SAFE strict walk-forward policy backtest."""
    try:
        args = parse_args()
        merged = load_inputs(args.decision_analysis_walkforward_csv, args.price_json, args.start_date, args.end_date)
        prototype_metrics = load_prototype_metrics(args.prototype_policy_csv)

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
            render_markdown(
                metrics,
                prototype_metrics,
                args.cost_bps,
                backtest["date"].iloc[0],
                backtest["date"].iloc[-1],
                int(merged["history_ready_flag"].fillna(0).ge(0.5).sum()) if "history_ready_flag" in merged.columns else 0,
                len(backtest),
            ),
            encoding="utf-8",
        )

        print_summary(metrics, len(backtest), out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Walk-forward policy backtest failed: {exc}") from exc


if __name__ == "__main__":
    main()
