from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from itertools import product
import json
import math
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd


FillMode = Literal["pessimistic", "optimistic", "skip_ambiguous", "entry_only_then_daily_range"]
StateName = Literal["FLAT", "PENDING_ENTRY", "LONG_OPEN"]
PendingOrderUpdateMode = Literal["replace", "keep"]


@dataclass(frozen=True)
class LimitOrderBacktestConfig:
    """Configuration for the BTC next-day passive limit-order state machine.

    The strategy is strict about information timing:
    - day ``D`` decisions use only the SAFE state known by the close of ``D-1``
    - pending entries and open positions are reassessed once per day, before
      simulating the candle for day ``D``
    - no forced same-day exit is applied unless explicitly enabled
    """

    entry_offset_pct: float = 0.015
    target_offset_pct: float = 0.015
    stop_offset_pct: float | None = 0.025
    fill_mode: FillMode = "pessimistic"
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    start_date: str | None = None
    end_date: str | None = None
    initial_equity: float = 100_000.0
    position_size_fraction: float = 1.0
    entry_ttl_days: int = 1
    force_eod_exit: bool = False
    pending_order_update_mode: PendingOrderUpdateMode = "replace"
    require_ts20_positive: bool = True
    require_rebound_gt_correction: bool = True
    require_drift_regime: bool = True
    require_safe_risk_on: bool = False
    max_band_pos: float | None = None
    min_hmm_conf: float | None = None
    reassess_open_on_hard_risk_off: bool = True
    reassess_open_on_rebound_lte_correction: bool = False
    reassess_open_on_regime_break: bool = False


@dataclass(frozen=True)
class SearchConfig:
    """Configuration for transparent parameter-grid search."""

    entry_offset_grid: tuple[float, ...]
    target_offset_grid: tuple[float, ...]
    stop_offset_grid: tuple[float | None, ...]
    max_band_pos_grid: tuple[float | None, ...]
    min_hmm_conf_grid: tuple[float | None, ...]
    min_trade_count: int = 25
    max_drawdown_limit: float | None = None
    top_n: int = 20


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    report: dict[str, Any]


@dataclass
class PendingEntry:
    trade_id: int
    created_idx: int
    created_date: str
    last_signal_date: str
    entry_limit: float
    days_live: int


@dataclass
class OpenPosition:
    trade_id: int
    entry_idx: int
    entry_date: str
    raw_entry_price: float
    effective_entry_price: float
    quantity: float
    capital_allocated: float
    cash_balance: float
    target_price: float
    stop_price: float | None


def load_safe_features_json(path: str | Path) -> pd.DataFrame:
    """Load the repository SAFE features JSON into a date-indexed frame."""
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    dates = payload.get("dates")
    series = payload.get("series")

    if not isinstance(dates, list) or not isinstance(series, dict):
        raise ValueError(f"{file_path} must contain 'dates' and 'series'.")

    frame = pd.DataFrame(series)
    if frame.empty:
        raise ValueError(f"{file_path} does not contain any SAFE series rows.")
    if len(frame) != len(dates):
        raise ValueError(
            f"{file_path} length mismatch: {len(dates)} dates vs {len(frame)} series rows."
        )

    frame.index = pd.to_datetime(dates, errors="raise")
    frame.index.name = "timestamp"
    for column in frame.columns:
        if column == "HMM_LABEL":
            continue
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_index()


def align_price_and_features(price_df: pd.DataFrame, features_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Align daily OHLCV candles and SAFE features on a shared date index."""
    if not isinstance(price_df.index, pd.DatetimeIndex):
        raise ValueError("price_df must use a DatetimeIndex.")
    if not isinstance(features_df.index, pd.DatetimeIndex):
        raise ValueError("features_df must use a DatetimeIndex.")

    shared_index = price_df.index.intersection(features_df.index).sort_values()
    if len(shared_index) < 2:
        raise ValueError("Price and feature tables do not share enough dates for a next-day backtest.")

    return price_df.loc[shared_index].sort_index(), features_df.loc[shared_index].sort_index()


def required_feature_columns(cfg: LimitOrderBacktestConfig) -> tuple[str, ...]:
    """Return SAFE columns required by entry filters and reassessment rules."""
    required: list[str] = []
    if cfg.require_drift_regime or cfg.reassess_open_on_regime_break:
        required.append("HMM_LABEL")
    if cfg.require_ts20_positive:
        required.append("TS_20")
    if cfg.require_rebound_gt_correction or cfg.reassess_open_on_rebound_lte_correction:
        required.extend(["P_REBOUND_10D_CAL", "P_CORRECTION_10D_CAL"])
    if cfg.max_band_pos is not None:
        required.append("band_pos")
    if cfg.min_hmm_conf is not None:
        required.append("HMM_CONF")
    if cfg.require_safe_risk_on or cfg.reassess_open_on_hard_risk_off:
        required.append("hard_risk_off_flag_safe")
    return tuple(dict.fromkeys(required))


def validate_backtest_inputs(price_df: pd.DataFrame, features_df: pd.DataFrame, cfg: LimitOrderBacktestConfig) -> None:
    """Validate data availability and configuration before running the state machine."""
    if price_df.empty:
        raise ValueError("Price table is empty.")
    if features_df.empty:
        raise ValueError("SAFE feature table is empty.")
    if not {"open", "high", "low", "close", "volume"}.issubset(price_df.columns):
        raise ValueError("Price table must contain open, high, low, close, and volume.")

    missing_columns = [column for column in required_feature_columns(cfg) if column not in features_df.columns]
    if missing_columns:
        raise ValueError(f"SAFE feature table is missing required filter/reassessment columns: {missing_columns}")

    if cfg.entry_offset_pct <= 0.0:
        raise ValueError("entry_offset_pct must be strictly positive.")
    if cfg.target_offset_pct <= 0.0:
        raise ValueError("target_offset_pct must be strictly positive.")
    if cfg.stop_offset_pct is not None and cfg.stop_offset_pct <= 0.0:
        raise ValueError("stop_offset_pct must be strictly positive when provided.")
    if cfg.position_size_fraction <= 0.0:
        raise ValueError("position_size_fraction must be strictly positive.")
    if cfg.initial_equity <= 0.0:
        raise ValueError("initial_equity must be strictly positive.")
    if cfg.entry_ttl_days <= 0:
        raise ValueError("entry_ttl_days must be strictly positive.")
    if cfg.pending_order_update_mode not in {"replace", "keep"}:
        raise ValueError(f"Unsupported pending_order_update_mode: {cfg.pending_order_update_mode}")
    if cfg.fill_mode not in {"pessimistic", "optimistic", "skip_ambiguous", "entry_only_then_daily_range"}:
        raise ValueError(f"Unsupported fill_mode: {cfg.fill_mode}")


def _filter_trade_date(index: pd.DatetimeIndex, start_date: str | None, end_date: str | None) -> np.ndarray:
    mask = np.ones(len(index), dtype=bool)
    if start_date is not None:
        mask &= index >= pd.Timestamp(start_date)
    if end_date is not None:
        mask &= index <= pd.Timestamp(end_date)
    return mask


def _finite_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _entry_cost_multiplier(cfg: LimitOrderBacktestConfig) -> float:
    return 1.0 + ((cfg.fee_bps + cfg.slippage_bps) / 10_000.0)


def _exit_cost_multiplier(cfg: LimitOrderBacktestConfig) -> float:
    return 1.0 - ((cfg.fee_bps + cfg.slippage_bps) / 10_000.0)


def _active_fill_mode(fill_mode: FillMode) -> FillMode:
    # Legacy alias kept for backward compatibility.
    return "pessimistic" if fill_mode == "entry_only_then_daily_range" else fill_mode


def _passes_entry_filters(signal_row: pd.Series, cfg: LimitOrderBacktestConfig) -> tuple[bool, list[str]]:
    failures: list[str] = []

    if cfg.require_drift_regime:
        if str(signal_row.get("HMM_LABEL", "")).upper() != "DRIFT":
            failures.append("require_drift_regime")

    if cfg.require_ts20_positive:
        ts20 = _finite_or_none(signal_row.get("TS_20"))
        if ts20 is None or ts20 <= 0.0:
            failures.append("require_ts20_positive")

    if cfg.require_rebound_gt_correction:
        rebound = _finite_or_none(signal_row.get("P_REBOUND_10D_CAL"))
        correction = _finite_or_none(signal_row.get("P_CORRECTION_10D_CAL"))
        if rebound is None or correction is None or rebound <= correction:
            failures.append("require_rebound_gt_correction")

    if cfg.max_band_pos is not None:
        band_pos = _finite_or_none(signal_row.get("band_pos"))
        if band_pos is None or band_pos > cfg.max_band_pos:
            failures.append("max_band_pos")

    if cfg.min_hmm_conf is not None:
        hmm_conf = _finite_or_none(signal_row.get("HMM_CONF"))
        if hmm_conf is None or hmm_conf < cfg.min_hmm_conf:
            failures.append("min_hmm_conf")

    if cfg.require_safe_risk_on:
        risk_off_flag = _finite_or_none(signal_row.get("hard_risk_off_flag_safe"))
        if risk_off_flag is None or risk_off_flag != 0.0:
            failures.append("require_safe_risk_on")

    return len(failures) == 0, failures


def _reassessment_exit_reasons(signal_row: pd.Series, cfg: LimitOrderBacktestConfig) -> list[str]:
    reasons: list[str] = []

    if cfg.reassess_open_on_hard_risk_off:
        hard_risk_off = _finite_or_none(signal_row.get("hard_risk_off_flag_safe"))
        if hard_risk_off == 1.0:
            reasons.append("hard_risk_off")

    if cfg.reassess_open_on_rebound_lte_correction:
        rebound = _finite_or_none(signal_row.get("P_REBOUND_10D_CAL"))
        correction = _finite_or_none(signal_row.get("P_CORRECTION_10D_CAL"))
        if rebound is not None and correction is not None and rebound <= correction:
            reasons.append("rebound_lte_correction")

    if cfg.reassess_open_on_regime_break:
        label = str(signal_row.get("HMM_LABEL", "")).upper()
        if cfg.require_drift_regime and label != "DRIFT":
            reasons.append("regime_break")

    return reasons


def _create_pending_order(
    trade_id: int,
    signal_idx: int,
    signal_date: str,
    prev_close: float,
    cfg: LimitOrderBacktestConfig,
) -> PendingEntry:
    return PendingEntry(
        trade_id=trade_id,
        created_idx=signal_idx,
        created_date=signal_date,
        last_signal_date=signal_date,
        entry_limit=prev_close * (1.0 - cfg.entry_offset_pct),
        days_live=0,
    )


def _build_open_position(
    trade_id: int,
    entry_idx: int,
    entry_date: str,
    raw_entry_price: float,
    cash_balance_before_entry: float,
    cfg: LimitOrderBacktestConfig,
) -> OpenPosition:
    effective_entry = raw_entry_price * _entry_cost_multiplier(cfg)
    capital_allocated = cash_balance_before_entry * cfg.position_size_fraction
    quantity = capital_allocated / effective_entry
    cash_after_entry = cash_balance_before_entry - capital_allocated
    return OpenPosition(
        trade_id=trade_id,
        entry_idx=entry_idx,
        entry_date=entry_date,
        raw_entry_price=raw_entry_price,
        effective_entry_price=effective_entry,
        quantity=quantity,
        capital_allocated=capital_allocated,
        cash_balance=cash_after_entry,
        target_price=raw_entry_price * (1.0 + cfg.target_offset_pct),
        stop_price=None if cfg.stop_offset_pct is None else raw_entry_price * (1.0 - cfg.stop_offset_pct),
    )


def _close_position(
    position: OpenPosition,
    raw_exit_price: float,
    exit_reason: str,
    exit_idx: int,
    exit_date: str,
    cfg: LimitOrderBacktestConfig,
    *,
    ambiguous_entry_exit_same_day: bool = False,
    ambiguous_stop_target_same_day: bool = False,
) -> tuple[float, dict[str, Any]]:
    effective_exit = raw_exit_price * _exit_cost_multiplier(cfg)
    proceeds = position.quantity * effective_exit
    cash_after_exit = position.cash_balance + proceeds
    pnl_amount = proceeds - position.capital_allocated
    return_pct = (effective_exit / position.effective_entry_price) - 1.0
    closed_trade = {
        "trade_id": position.trade_id,
        "entry_date": position.entry_date,
        "exit_date": exit_date,
        "entry_idx": position.entry_idx,
        "exit_idx": exit_idx,
        "entry_price": position.raw_entry_price,
        "exit_price": raw_exit_price,
        "effective_entry_price": position.effective_entry_price,
        "effective_exit_price": effective_exit,
        "exit_reason": exit_reason,
        "holding_days": int(exit_idx - position.entry_idx + 1),
        "return_pct": float(return_pct),
        "pnl_amount": float(pnl_amount),
        "ambiguous_entry_exit_same_day": bool(ambiguous_entry_exit_same_day),
        "ambiguous_stop_target_same_day": bool(ambiguous_stop_target_same_day),
    }
    return float(cash_after_exit), closed_trade


def _resolve_from_open_stop_target(
    position: OpenPosition,
    fill_mode: FillMode,
) -> tuple[str, float]:
    active_mode = _active_fill_mode(fill_mode)
    if active_mode == "optimistic":
        return "exit_target", position.target_price
    return "exit_stop", position.stop_price if position.stop_price is not None else position.target_price


def _simulate_long_open_day(
    position: OpenPosition,
    day_row: pd.Series,
    idx: int,
    trade_date: str,
    cfg: LimitOrderBacktestConfig,
) -> tuple[OpenPosition | None, float | None, dict[str, int], dict[str, Any] | None]:
    counts = {
        "exit_target": 0,
        "exit_stop": 0,
        "exit_forced_eod": 0,
        "ambiguous_stop_target_same_day": 0,
        "ambiguous_entry_exit_same_day": 0,
    }

    day_high = float(day_row["high"])
    day_low = float(day_row["low"])
    day_close = float(day_row["close"])

    target_reached = day_high >= position.target_price
    stop_reached = position.stop_price is not None and day_low <= position.stop_price

    if target_reached and stop_reached:
        counts["ambiguous_stop_target_same_day"] = 1
        exit_reason, raw_exit = _resolve_from_open_stop_target(position, cfg.fill_mode)
        cash_after_exit, closed_trade = _close_position(
            position,
            raw_exit,
            exit_reason,
            idx,
            trade_date,
            cfg,
            ambiguous_stop_target_same_day=True,
        )
        counts["exit_target" if exit_reason == "exit_target" else "exit_stop"] = 1
        return None, cash_after_exit, counts, closed_trade

    if target_reached:
        cash_after_exit, closed_trade = _close_position(position, position.target_price, "exit_target", idx, trade_date, cfg)
        counts["exit_target"] = 1
        return None, cash_after_exit, counts, closed_trade

    if stop_reached:
        cash_after_exit, closed_trade = _close_position(
            position,
            position.stop_price if position.stop_price is not None else day_close,
            "exit_stop",
            idx,
            trade_date,
            cfg,
        )
        counts["exit_stop"] = 1
        return None, cash_after_exit, counts, closed_trade

    if cfg.force_eod_exit:
        cash_after_exit, closed_trade = _close_position(position, day_close, "exit_forced_eod", idx, trade_date, cfg)
        counts["exit_forced_eod"] = 1
        return None, cash_after_exit, counts, closed_trade

    return position, None, counts, None


def _simulate_pending_entry_day(
    pending: PendingEntry,
    cash_balance_before_entry: float,
    day_row: pd.Series,
    idx: int,
    trade_date: str,
    cfg: LimitOrderBacktestConfig,
) -> tuple[PendingEntry | None, OpenPosition | None, float | None, dict[str, int], dict[str, Any] | None, dict[str, Any]]:
    """Simulate one candle for a pending long entry.

    Distinction:
    - if `open <= entry_limit`, the position is active from the session start,
      so same-day target/stop checks are acceptable against the daily range
    - if `open > entry_limit` and the daily low later reaches the limit, the
      entry is intraday and same-day target recognition becomes ambiguous
      whenever the target is also reachable inside that same candle
    """
    counts = {
        "entry_filled": 0,
        "exit_target": 0,
        "exit_stop": 0,
        "exit_forced_eod": 0,
        "ambiguous_entry_exit_same_day": 0,
        "ambiguous_stop_target_same_day": 0,
    }

    detail = {
        "entry_source": "not_filled",
        "entry_limit": pending.entry_limit,
        "target_price": np.nan,
        "stop_price": np.nan,
        "raw_entry_price": np.nan,
        "raw_exit_price": np.nan,
        "exit_reason": "no_fill",
    }

    day_open = float(day_row["open"])
    day_high = float(day_row["high"])
    day_low = float(day_row["low"])
    day_close = float(day_row["close"])

    raw_entry_price: float | None = None
    active_from_open = False
    if day_open <= pending.entry_limit:
        raw_entry_price = day_open
        active_from_open = True
        detail["entry_source"] = "open_below_limit"
    elif day_low <= pending.entry_limit:
        raw_entry_price = pending.entry_limit
        detail["entry_source"] = "intraday_limit_touch"

    if raw_entry_price is None:
        detail["exit_reason"] = "no_fill"
        return pending, None, None, counts, None, detail

    counts["entry_filled"] = 1
    detail["raw_entry_price"] = raw_entry_price
    position = _build_open_position(
        trade_id=pending.trade_id,
        entry_idx=idx,
        entry_date=trade_date,
        raw_entry_price=raw_entry_price,
        cash_balance_before_entry=cash_balance_before_entry,
        cfg=cfg,
    )
    detail["target_price"] = position.target_price
    detail["stop_price"] = position.stop_price if position.stop_price is not None else np.nan

    target_reached = day_high >= position.target_price
    stop_reached = position.stop_price is not None and day_low <= position.stop_price

    if active_from_open:
        carry_or_exit, cash_after_exit, extra_counts, closed_trade = _simulate_long_open_day(
            position,
            day_row,
            idx,
            trade_date,
            cfg,
        )
        counts.update({key: counts.get(key, 0) + value for key, value in extra_counts.items()})
        if closed_trade is not None:
            detail["raw_exit_price"] = closed_trade["exit_price"]
            detail["exit_reason"] = closed_trade["exit_reason"]
            return None, None, cash_after_exit, counts, closed_trade, detail
        detail["exit_reason"] = "carry_open"
        return None, carry_or_exit, None, counts, None, detail

    # Entry happens intraday after the open. Stop can still be definite because
    # the price must pass through the entry level before reaching a lower stop.
    if stop_reached:
        cash_after_exit, closed_trade = _close_position(
            position,
            position.stop_price if position.stop_price is not None else day_close,
            "exit_stop",
            idx,
            trade_date,
            cfg,
        )
        counts["exit_stop"] = 1
        detail["raw_exit_price"] = closed_trade["exit_price"]
        detail["exit_reason"] = closed_trade["exit_reason"]
        return None, None, cash_after_exit, counts, closed_trade, detail

    if target_reached:
        counts["ambiguous_entry_exit_same_day"] = 1
        active_mode = _active_fill_mode(cfg.fill_mode)
        if active_mode == "optimistic":
            cash_after_exit, closed_trade = _close_position(
                position,
                position.target_price,
                "exit_target",
                idx,
                trade_date,
                cfg,
                ambiguous_entry_exit_same_day=True,
            )
            counts["exit_target"] = 1
            detail["raw_exit_price"] = closed_trade["exit_price"]
            detail["exit_reason"] = closed_trade["exit_reason"]
            return None, None, cash_after_exit, counts, closed_trade, detail
        if cfg.force_eod_exit:
            cash_after_exit, closed_trade = _close_position(
                position,
                day_close,
                "exit_forced_eod",
                idx,
                trade_date,
                cfg,
                ambiguous_entry_exit_same_day=True,
            )
            counts["exit_forced_eod"] = 1
            detail["raw_exit_price"] = closed_trade["exit_price"]
            detail["exit_reason"] = closed_trade["exit_reason"]
            return None, None, cash_after_exit, counts, closed_trade, detail
        detail["exit_reason"] = "carry_open"
        return None, position, None, counts, None, detail

    if cfg.force_eod_exit:
        cash_after_exit, closed_trade = _close_position(position, day_close, "exit_forced_eod", idx, trade_date, cfg)
        counts["exit_forced_eod"] = 1
        detail["raw_exit_price"] = closed_trade["exit_price"]
        detail["exit_reason"] = closed_trade["exit_reason"]
        return None, None, cash_after_exit, counts, closed_trade, detail

    detail["exit_reason"] = "carry_open"
    return None, position, None, counts, None, detail


def _mark_to_market_equity(cash_balance: float, position: OpenPosition | None, mark_price: float) -> float:
    if position is None:
        return float(cash_balance)
    return float(position.cash_balance + (position.quantity * mark_price))


def _build_report(
    daily_log: pd.DataFrame,
    closed_trades: pd.DataFrame,
    cfg: LimitOrderBacktestConfig,
    price_path: str | None,
    features_path: str | None,
) -> dict[str, Any]:
    total_days_tested = int(len(daily_log))
    orders_placed = int(daily_log["pending_created"].sum() + daily_log["pending_replaced"].sum())
    total_entries_filled = int(daily_log["entry_filled"].sum())

    returns = closed_trades["return_pct"].dropna() if not closed_trades.empty else pd.Series(dtype=float)
    gross_pnl = closed_trades["pnl_amount"].dropna() if not closed_trades.empty else pd.Series(dtype=float)
    wins = returns[returns > 0.0]
    losses = returns[returns < 0.0]

    final_equity = float(daily_log["equity_after"].iloc[-1]) if not daily_log.empty else float(cfg.initial_equity)
    running_peak = daily_log["equity_after"].cummax() if not daily_log.empty else pd.Series(dtype=float)
    drawdown = (daily_log["equity_after"] / running_peak) - 1.0 if not daily_log.empty else pd.Series(dtype=float)
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    avg_return = float(returns.mean()) if not returns.empty else 0.0
    median_return = float(returns.median()) if not returns.empty else 0.0
    win_rate = float((returns > 0.0).mean()) if not returns.empty else 0.0
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0
    expectancy = float((win_rate * avg_win) + ((1.0 - win_rate) * avg_loss)) if not returns.empty else 0.0
    gross_profit = float(gross_pnl[gross_pnl > 0.0].sum()) if not gross_pnl.empty else 0.0
    gross_loss = float(abs(gross_pnl[gross_pnl < 0.0].sum())) if not gross_pnl.empty else 0.0
    if gross_loss > 0.0:
        profit_factor: float | None = float(gross_profit / gross_loss)
    elif gross_profit > 0.0:
        profit_factor = None
    else:
        profit_factor = 0.0

    sharpe_like = 0.0
    if len(returns) >= 2 and float(returns.std(ddof=0)) > 0.0:
        sharpe_like = float(returns.mean() / returns.std(ddof=0) * np.sqrt(len(returns)))

    report = {
        "strategy": "daily_reassessment_passive_limit_long",
        "state_machine": ["FLAT", "PENDING_ENTRY", "LONG_OPEN"],
        "no_lookahead_rule": "Day D decisions use only the SAFE state observed at the close of day D-1.",
        "fill_mode": cfg.fill_mode,
        "daily_candle_execution_note": (
            "If a long position is already active from the start of a session, target and stop are evaluated against "
            "that full daily range. If a pending entry is below the open and both the entry and target lie inside the "
            "same daily range, same-day target recognition is ambiguous because the target may have happened before the entry."
        ),
        "price_json": price_path,
        "features_json": features_path,
        "total_days_tested": total_days_tested,
        "orders_placed": orders_placed,
        "total_orders_placed": orders_placed,
        "entries_filled": total_entries_filled,
        "total_entries_filled": total_entries_filled,
        "fill_rate": float(total_entries_filled / orders_placed) if orders_placed > 0 else 0.0,
        "target_hit_rate_given_fill": float((daily_log["exit_target"].sum()) / len(closed_trades)) if len(closed_trades) > 0 else 0.0,
        "stop_hit_rate_given_fill": float((daily_log["exit_stop"].sum()) / len(closed_trades)) if len(closed_trades) > 0 else 0.0,
        "pending_created": int(daily_log["pending_created"].sum()),
        "pending_replaced": int(daily_log["pending_replaced"].sum()),
        "pending_canceled": int(daily_log["pending_canceled"].sum()),
        "pending_expired": int(daily_log["pending_expired"].sum()),
        "entry_filled": int(daily_log["entry_filled"].sum()),
        "exit_target": int(daily_log["exit_target"].sum()),
        "exit_stop": int(daily_log["exit_stop"].sum()),
        "exit_reassessment_open": int(daily_log["exit_reassessment_open"].sum()),
        "exit_forced_eod": int(daily_log["exit_forced_eod"].sum()),
        "ambiguous_entry_exit_same_day": int(daily_log["ambiguous_entry_exit_same_day"].sum()),
        "ambiguous_stop_target_same_day": int(daily_log["ambiguous_stop_target_same_day"].sum()),
        "ambiguous_rate": float(
            (daily_log["ambiguous_entry_exit_same_day"].sum() + daily_log["ambiguous_stop_target_same_day"].sum()) / max(orders_placed, 1)
        ),
        "canceled_rate": float((daily_log["pending_canceled"].sum() + daily_log["pending_expired"].sum()) / max(orders_placed, 1)),
        "average_return_per_trade": avg_return,
        "median_return_per_trade": median_return,
        "cumulative_return": float((final_equity / cfg.initial_equity) - 1.0),
        "final_equity": final_equity,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "expectancy": expectancy,
        "average_holding_days": float(closed_trades["holding_days"].mean()) if not closed_trades.empty else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "sharpe_like": sharpe_like,
        "open_position_at_end": bool(daily_log["state_after"].iloc[-1] == "LONG_OPEN") if not daily_log.empty else False,
        "pending_order_at_end": bool(daily_log["state_after"].iloc[-1] == "PENDING_ENTRY") if not daily_log.empty else False,
        "config": asdict(cfg),
    }
    if not daily_log.empty:
        report["start_trade_date"] = str(daily_log["trade_date"].iloc[0])
        report["end_trade_date"] = str(daily_log["trade_date"].iloc[-1])
        report["max_drawdown_trade_date"] = str(daily_log.loc[drawdown.idxmin(), "trade_date"]) if not drawdown.empty else None
    return report


def run_limit_order_backtest(
    price_df: pd.DataFrame,
    features_df: pd.DataFrame,
    cfg: LimitOrderBacktestConfig,
    price_path: str | None = None,
    features_path: str | None = None,
) -> BacktestResult:
    """Run the explicit daily-reassessment limit-order state machine."""
    validate_backtest_inputs(price_df, features_df, cfg)
    price_df, features_df = align_price_and_features(price_df, features_df)

    date_mask = _filter_trade_date(price_df.index, cfg.start_date, cfg.end_date)
    records: list[dict[str, Any]] = []
    closed_trades: list[dict[str, Any]] = []

    cash_balance = float(cfg.initial_equity)
    state: StateName = "FLAT"
    pending: PendingEntry | None = None
    position: OpenPosition | None = None
    next_trade_id = 1

    for idx in range(1, len(price_df)):
        trade_date_ts = price_df.index[idx]
        if not date_mask[idx]:
            continue

        signal_date_ts = price_df.index[idx - 1]
        signal_row = features_df.iloc[idx - 1]
        prev_price_row = price_df.iloc[idx - 1]
        day_row = price_df.iloc[idx]

        trade_date = trade_date_ts.strftime("%Y-%m-%d")
        signal_date = signal_date_ts.strftime("%Y-%m-%d")
        prev_close = float(prev_price_row["close"])
        day_open = float(day_row["open"])
        day_close = float(day_row["close"])
        equity_before = _mark_to_market_equity(cash_balance, position, prev_close)

        state_before: StateName = state
        state_after: StateName = state
        blocked_new_entry_today = False
        active_order_today = False
        active_position_today = position is not None
        filter_failures = ""
        reassessment_exit_reason = ""

        counts = {
            "pending_created": 0,
            "pending_replaced": 0,
            "pending_canceled": 0,
            "pending_expired": 0,
            "entry_filled": 0,
            "exit_target": 0,
            "exit_stop": 0,
            "exit_reassessment_open": 0,
            "exit_forced_eod": 0,
            "ambiguous_entry_exit_same_day": 0,
            "ambiguous_stop_target_same_day": 0,
        }

        entry_source = "none"
        active_entry_limit = np.nan
        active_target_price = np.nan
        active_stop_price = np.nan
        raw_entry_price = np.nan
        raw_exit_price = np.nan
        lifecycle_event = "none"
        trade_id = pending.trade_id if pending is not None else (position.trade_id if position is not None else np.nan)

        if state == "LONG_OPEN" and position is not None:
            exit_reasons = _reassessment_exit_reasons(signal_row, cfg)
            if exit_reasons:
                cash_balance, closed_trade = _close_position(
                    position,
                    day_open,
                    "exit_reassessment_open",
                    idx,
                    trade_date,
                    cfg,
                )
                closed_trade["reassessment_reason"] = ",".join(exit_reasons)
                closed_trades.append(closed_trade)
                counts["exit_reassessment_open"] = 1
                raw_exit_price = closed_trade["exit_price"]
                reassessment_exit_reason = closed_trade["reassessment_reason"]
                lifecycle_event = "exit_reassessment_open"
                position = None
                state = "FLAT"
                blocked_new_entry_today = True
                active_position_today = False

        if state == "PENDING_ENTRY" and pending is not None:
            passes_filters, failures = _passes_entry_filters(signal_row, cfg)
            filter_failures = ",".join(failures)

            if cfg.pending_order_update_mode == "keep" and pending.days_live >= cfg.entry_ttl_days:
                counts["pending_expired"] = 1
                lifecycle_event = "pending_expired"
                pending = None
                state = "FLAT"
                blocked_new_entry_today = True
            elif not passes_filters:
                counts["pending_canceled"] = 1
                lifecycle_event = "pending_canceled"
                pending = None
                state = "FLAT"
                blocked_new_entry_today = True
            elif cfg.pending_order_update_mode == "replace":
                pending = _create_pending_order(pending.trade_id, idx - 1, signal_date, prev_close, cfg)
                counts["pending_replaced"] = 1
                lifecycle_event = "pending_replaced"

        if state == "FLAT" and not blocked_new_entry_today:
            passes_filters, failures = _passes_entry_filters(signal_row, cfg)
            filter_failures = ",".join(failures)
            if passes_filters:
                pending = _create_pending_order(next_trade_id, idx - 1, signal_date, prev_close, cfg)
                next_trade_id += 1
                counts["pending_created"] = 1
                lifecycle_event = "pending_created"
                state = "PENDING_ENTRY"
                trade_id = pending.trade_id
            else:
                lifecycle_event = "flat_no_signal"

        if state == "PENDING_ENTRY" and pending is not None:
            active_order_today = True
            trade_id = pending.trade_id
            active_entry_limit = pending.entry_limit

            pending_after, position_after, cash_after_exit, pending_counts, closed_trade, pending_detail = _simulate_pending_entry_day(
                pending,
                cash_balance,
                day_row,
                idx,
                trade_date,
                cfg,
            )
            for key, value in pending_counts.items():
                counts[key] += value

            entry_source = str(pending_detail["entry_source"])
            raw_entry_price = pending_detail["raw_entry_price"]
            raw_exit_price = pending_detail["raw_exit_price"]
            active_target_price = pending_detail["target_price"]
            active_stop_price = pending_detail["stop_price"]
            if pending_detail["exit_reason"] != "no_fill":
                lifecycle_event = pending_detail["exit_reason"]

            if pending_after is not None:
                pending_after.days_live += 1
                pending = pending_after
                state = "PENDING_ENTRY"
            else:
                pending = None

            if closed_trade is not None:
                closed_trades.append(closed_trade)
                cash_balance = cash_after_exit if cash_after_exit is not None else cash_balance
                position = None
                state = "FLAT"
            elif position_after is not None:
                position = position_after
                cash_balance = position.cash_balance
                state = "LONG_OPEN"
                active_position_today = True
            else:
                position = None

        elif state == "LONG_OPEN" and position is not None:
            trade_id = position.trade_id
            active_position_today = True
            active_target_price = position.target_price
            active_stop_price = position.stop_price if position.stop_price is not None else np.nan
            raw_entry_price = position.raw_entry_price

            position_after, cash_after_exit, long_counts, closed_trade = _simulate_long_open_day(
                position,
                day_row,
                idx,
                trade_date,
                cfg,
            )
            for key, value in long_counts.items():
                counts[key] += value

            if closed_trade is not None:
                closed_trades.append(closed_trade)
                raw_exit_price = closed_trade["exit_price"]
                cash_balance = cash_after_exit if cash_after_exit is not None else cash_balance
                position = None
                state = "FLAT"
                lifecycle_event = closed_trade["exit_reason"]
            else:
                position = position_after
                state = "LONG_OPEN"

        state_after = state
        equity_after = _mark_to_market_equity(cash_balance, position, day_close)

        records.append(
            {
                "trade_id": trade_id,
                "signal_date": signal_date,
                "trade_date": trade_date,
                "state_before": state_before,
                "state_after": state_after,
                "prev_close": prev_close,
                "day_open": day_open,
                "day_high": float(day_row["high"]),
                "day_low": float(day_row["low"]),
                "day_close": day_close,
                "order_active_today": bool(active_order_today),
                "position_active_at_open": bool(active_position_today),
                "filter_failures": filter_failures,
                "reassessment_exit_reason": reassessment_exit_reason,
                "signal_hmm_label": signal_row.get("HMM_LABEL"),
                "signal_ts20": _finite_or_none(signal_row.get("TS_20")),
                "signal_band_pos": _finite_or_none(signal_row.get("band_pos")),
                "signal_hmm_conf": _finite_or_none(signal_row.get("HMM_CONF")),
                "signal_rebound_prob": _finite_or_none(signal_row.get("P_REBOUND_10D_CAL")),
                "signal_correction_prob": _finite_or_none(signal_row.get("P_CORRECTION_10D_CAL")),
                "signal_hard_risk_off": _finite_or_none(signal_row.get("hard_risk_off_flag_safe")),
                "entry_limit": active_entry_limit,
                "target_price": active_target_price,
                "stop_price": active_stop_price,
                "raw_entry_price": raw_entry_price,
                "raw_exit_price": raw_exit_price,
                "entry_source": entry_source,
                "lifecycle_event": lifecycle_event,
                "equity_before": equity_before,
                "equity_after": equity_after,
                **counts,
            }
        )

    daily_log = pd.DataFrame.from_records(records)
    if daily_log.empty:
        raise ValueError("No trade dates remain after date filtering.")

    closed_trades_df = pd.DataFrame.from_records(closed_trades)
    report = _build_report(daily_log, closed_trades_df, cfg, price_path=price_path, features_path=features_path)
    return BacktestResult(trades=daily_log, report=report)


def run_grid_search(
    price_df: pd.DataFrame,
    features_df: pd.DataFrame,
    base_cfg: LimitOrderBacktestConfig,
    search_cfg: SearchConfig,
    price_path: str | None = None,
    features_path: str | None = None,
) -> tuple[pd.DataFrame, LimitOrderBacktestConfig, BacktestResult]:
    """Evaluate a transparent parameter grid and return the best surviving run."""
    rows: list[dict[str, Any]] = []

    for entry_offset, target_offset, stop_offset, max_band_pos, min_hmm_conf in product(
        search_cfg.entry_offset_grid,
        search_cfg.target_offset_grid,
        search_cfg.stop_offset_grid,
        search_cfg.max_band_pos_grid,
        search_cfg.min_hmm_conf_grid,
    ):
        cfg = replace(
            base_cfg,
            entry_offset_pct=entry_offset,
            target_offset_pct=target_offset,
            stop_offset_pct=stop_offset,
            max_band_pos=max_band_pos,
            min_hmm_conf=min_hmm_conf,
        )
        result = run_limit_order_backtest(
            price_df=price_df,
            features_df=features_df,
            cfg=cfg,
            price_path=price_path,
            features_path=features_path,
        )
        report = result.report
        rows.append(
            {
                "entry_offset_pct": entry_offset,
                "target_offset_pct": target_offset,
                "stop_offset_pct": stop_offset,
                "max_band_pos": max_band_pos,
                "min_hmm_conf": min_hmm_conf,
                "final_equity": report["final_equity"],
                "cumulative_return": report["cumulative_return"],
                "expectancy": report["expectancy"],
                "max_drawdown": report["max_drawdown"],
                "sharpe_like": report["sharpe_like"],
                "profit_factor": report["profit_factor"],
                "fill_rate": report["fill_rate"],
                "win_rate": report["win_rate"],
                "orders_placed": report["orders_placed"],
                "entries_filled": report["entries_filled"],
            }
        )

    results_df = pd.DataFrame(rows)
    if results_df.empty:
        raise ValueError("Search grid produced no candidate rows.")

    constrained = results_df.loc[results_df["entries_filled"] >= search_cfg.min_trade_count].copy()
    if search_cfg.max_drawdown_limit is not None:
        constrained = constrained.loc[constrained["max_drawdown"] >= -abs(search_cfg.max_drawdown_limit)].copy()
    if constrained.empty:
        constrained = results_df.copy()

    constrained = constrained.sort_values(
        by=["expectancy", "final_equity", "sharpe_like", "max_drawdown"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    best_row = constrained.iloc[0]
    best_cfg = replace(
        base_cfg,
        entry_offset_pct=float(best_row["entry_offset_pct"]),
        target_offset_pct=float(best_row["target_offset_pct"]),
        stop_offset_pct=None if pd.isna(best_row["stop_offset_pct"]) else float(best_row["stop_offset_pct"]),
        max_band_pos=None if pd.isna(best_row["max_band_pos"]) else float(best_row["max_band_pos"]),
        min_hmm_conf=None if pd.isna(best_row["min_hmm_conf"]) else float(best_row["min_hmm_conf"]),
    )
    best_result = run_limit_order_backtest(
        price_df=price_df,
        features_df=features_df,
        cfg=best_cfg,
        price_path=price_path,
        features_path=features_path,
    )
    best_result.report["search"] = {
        "enabled": True,
        "candidates_evaluated": int(len(results_df)),
        "min_trade_count": search_cfg.min_trade_count,
        "max_drawdown_limit": search_cfg.max_drawdown_limit,
        "top_results": constrained.head(search_cfg.top_n).to_dict(orient="records"),
    }
    return constrained, best_cfg, best_result


def config_to_jsonable(cfg: LimitOrderBacktestConfig) -> dict[str, Any]:
    """Convert config dataclass values to a JSON-safe dictionary."""
    return asdict(cfg)
