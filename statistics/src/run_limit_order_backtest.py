from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_FEATURES_JSON_PATH, DEFAULT_PRICE_JSON_PATH, OUT_DIR
from src.strategy.limit_order_backtest import (
    LimitOrderBacktestConfig,
    SearchConfig,
    config_to_jsonable,
    load_safe_features_json,
    run_grid_search,
    run_limit_order_backtest,
)


DEFAULT_BACKTEST_OUT_DIR = OUT_DIR / "limit_order_backtest"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the BTC next-day passive limit-order backtest."""
    parser = argparse.ArgumentParser(
        description=(
            "Backtest BTC passive limit buys with a daily-reassessment state machine driven only by information "
            "known at the previous daily close. Outputs are written under ../out/limit_order_backtest by default."
        )
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-json", default=str(DEFAULT_FEATURES_JSON_PATH), help="Default: ../out/features.json")
    parser.add_argument("--out-dir", default=str(DEFAULT_BACKTEST_OUT_DIR), help="Default: ../out/limit_order_backtest")

    parser.add_argument("--entry-offset-pct", type=float, default=0.015)
    parser.add_argument("--target-offset-pct", type=float, default=0.015)
    parser.add_argument("--stop-offset-pct", type=float, default=0.025)
    parser.add_argument("--fill-mode", choices=["pessimistic", "optimistic", "skip_ambiguous", "entry_only_then_daily_range"], default="pessimistic")
    parser.add_argument("--fee-bps", type=float, default=0.0)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--initial-equity", type=float, default=100_000.0)
    parser.add_argument("--position-size-fraction", type=float, default=1.0)
    parser.add_argument("--entry-ttl-days", type=int, default=1)
    parser.add_argument("--force-eod-exit", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--pending-order-update-mode", choices=["replace", "keep"], default="replace")

    parser.add_argument("--require-ts20-positive", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-rebound-gt-correction", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-drift-regime", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-safe-risk-on", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--max-band-pos", type=float)
    parser.add_argument("--min-hmm-conf", type=float)
    parser.add_argument("--no-stop", action="store_true", help="Disable stop-loss placement.")
    parser.add_argument("--reassess-open-on-hard-risk-off", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--reassess-open-on-rebound-lte-correction", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--reassess-open-on-regime-break", action=argparse.BooleanOptionalAction, default=False)

    parser.add_argument("--search", action="store_true", help="Run a simple parameter-grid search.")
    parser.add_argument(
        "--grid-entry-offset-pct",
        default="0.01,0.015,0.02",
        help="Comma-separated entry offset grid used in --search mode.",
    )
    parser.add_argument(
        "--grid-target-offset-pct",
        default="0.01,0.015,0.02",
        help="Comma-separated target offset grid used in --search mode.",
    )
    parser.add_argument(
        "--grid-stop-offset-pct",
        default="0.02,0.025,0.03",
        help="Comma-separated stop offset grid used in --search mode. Ignored with --no-stop.",
    )
    parser.add_argument(
        "--grid-max-band-pos",
        default="",
        help="Optional comma-separated band_pos thresholds for search, for example 0.4,0.5.",
    )
    parser.add_argument(
        "--grid-min-hmm-conf",
        default="",
        help="Optional comma-separated HMM confidence thresholds for search, for example 0.55,0.65.",
    )
    parser.add_argument("--min-trade-count", type=int, default=25)
    parser.add_argument("--max-drawdown-limit", type=float)
    parser.add_argument("--top-n-search-results", type=int, default=20)
    return parser.parse_args()


def build_backtest_config(args: argparse.Namespace) -> LimitOrderBacktestConfig:
    """Build the main backtest configuration from CLI arguments."""
    return LimitOrderBacktestConfig(
        entry_offset_pct=args.entry_offset_pct,
        target_offset_pct=args.target_offset_pct,
        stop_offset_pct=None if args.no_stop else args.stop_offset_pct,
        fill_mode=args.fill_mode,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_equity=args.initial_equity,
        position_size_fraction=args.position_size_fraction,
        entry_ttl_days=args.entry_ttl_days,
        force_eod_exit=args.force_eod_exit,
        pending_order_update_mode=args.pending_order_update_mode,
        require_ts20_positive=args.require_ts20_positive,
        require_rebound_gt_correction=args.require_rebound_gt_correction,
        require_drift_regime=args.require_drift_regime,
        require_safe_risk_on=args.require_safe_risk_on,
        max_band_pos=args.max_band_pos,
        min_hmm_conf=args.min_hmm_conf,
        reassess_open_on_hard_risk_off=args.reassess_open_on_hard_risk_off,
        reassess_open_on_rebound_lte_correction=args.reassess_open_on_rebound_lte_correction,
        reassess_open_on_regime_break=args.reassess_open_on_regime_break,
    )


def _parse_optional_float_grid(raw: str) -> tuple[float | None, ...]:
    if not raw.strip():
        return (None,)
    values: list[float | None] = []
    for token in raw.split(","):
        item = token.strip()
        if not item:
            continue
        if item.lower() in {"none", "null"}:
            values.append(None)
        else:
            values.append(float(item))
    return tuple(values or [None])


def _parse_float_grid(raw: str) -> tuple[float, ...]:
    values = tuple(float(token.strip()) for token in raw.split(",") if token.strip())
    if not values:
        raise ValueError("Grid values must not be empty.")
    return values


def build_search_config(args: argparse.Namespace) -> SearchConfig:
    """Build the optional parameter search configuration from CLI arguments."""
    stop_grid: tuple[float | None, ...]
    if args.no_stop:
        stop_grid = (None,)
    else:
        stop_grid = _parse_optional_float_grid(args.grid_stop_offset_pct)
        if any(value is None for value in stop_grid):
            raise ValueError("Stop grid cannot contain null values unless --no-stop is used.")

    band_grid = _parse_optional_float_grid(args.grid_max_band_pos)
    hmm_conf_grid = _parse_optional_float_grid(args.grid_min_hmm_conf)

    if args.max_band_pos is not None:
        band_grid = tuple(sorted(set((*band_grid, args.max_band_pos)), key=lambda value: (value is None, value)))
    if args.min_hmm_conf is not None:
        hmm_conf_grid = tuple(sorted(set((*hmm_conf_grid, args.min_hmm_conf)), key=lambda value: (value is None, value)))

    return SearchConfig(
        entry_offset_grid=_parse_float_grid(args.grid_entry_offset_pct),
        target_offset_grid=_parse_float_grid(args.grid_target_offset_pct),
        stop_offset_grid=stop_grid,
        max_band_pos_grid=band_grid,
        min_hmm_conf_grid=hmm_conf_grid,
        min_trade_count=args.min_trade_count,
        max_drawdown_limit=args.max_drawdown_limit,
        top_n=args.top_n_search_results,
    )


def load_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load BTC OHLCV candles and the exported SAFE feature table."""
    price_df = load_daily_price_json(args.price_json)
    features_df = load_safe_features_json(args.features_json)
    return price_df, features_df


def export_backtest_outputs(
    result_report: dict[str, Any],
    trades: pd.DataFrame,
    cfg: LimitOrderBacktestConfig,
    out_dir: Path,
    search_results: pd.DataFrame | None = None,
) -> None:
    """Write the backtest report, trades, and configuration to disk."""

    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [_json_safe(item) for item in value]
        if isinstance(value, (np.floating, np.integer)):  # type: ignore[name-defined]
            return value.item()
        if isinstance(value, float) and not math.isfinite(value):  # type: ignore[name-defined]
            return None
        if pd.isna(value):
            return None
        return value

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.json"
    trades_path = out_dir / "trades.csv"
    config_path = out_dir / "config_used.json"

    report_payload = _json_safe(dict(result_report))
    report_payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    trades.to_csv(trades_path, index=False)
    config_path.write_text(json.dumps(config_to_jsonable(cfg), indent=2), encoding="utf-8")

    if search_results is not None:
        search_path = out_dir / "search_results.csv"
        search_results.to_csv(search_path, index=False)


def print_summary(report: dict[str, Any], search_enabled: bool) -> None:
    """Print a compact summary of the backtest outcome."""
    print(f"days_tested={report['total_days_tested']}")
    print(f"orders_placed={report['total_orders_placed']}")
    print(f"entries_filled={report['total_entries_filled']}")
    print(f"final_equity={report['final_equity']:.2f}")
    print(f"cumulative_return={report['cumulative_return']:+.2%}")
    print(f"max_drawdown={report['max_drawdown']:+.2%}")
    print(f"expectancy={report['expectancy']:+.4%}")
    print(f"fill_mode={report['fill_mode']}")
    if search_enabled:
        search_meta = report.get("search", {})
        print(f"search_candidates={search_meta.get('candidates_evaluated', 0)}")


def main() -> None:
    args = parse_args()
    price_df, features_df = load_inputs(args)
    base_cfg = build_backtest_config(args)
    out_dir = Path(args.out_dir)

    if args.search:
        search_cfg = build_search_config(args)
        search_results, best_cfg, best_result = run_grid_search(
            price_df=price_df,
            features_df=features_df,
            base_cfg=base_cfg,
            search_cfg=search_cfg,
            price_path=args.price_json,
            features_path=args.features_json,
        )
        export_backtest_outputs(
            result_report=best_result.report,
            trades=best_result.trades,
            cfg=best_cfg,
            out_dir=out_dir,
            search_results=search_results,
        )
        print_summary(best_result.report, search_enabled=True)
        return

    result = run_limit_order_backtest(
        price_df=price_df,
        features_df=features_df,
        cfg=base_cfg,
        price_path=args.price_json,
        features_path=args.features_json,
    )
    result.report["search"] = {"enabled": False}
    export_backtest_outputs(
        result_report=result.report,
        trades=result.trades,
        cfg=base_cfg,
        out_dir=out_dir,
    )
    print_summary(result.report, search_enabled=False)


if __name__ == "__main__":
    main()
