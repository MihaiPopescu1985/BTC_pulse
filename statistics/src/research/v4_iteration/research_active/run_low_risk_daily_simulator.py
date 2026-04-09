from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.research_active.run_low_risk_event_backtest import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    _equity_curve,
    _safe_mean,
    _safe_median,
    build_policy,
)
from src.research.v4_iteration.research_active.run_low_risk_strategy_sanity import build_entry_mask, build_trade_table
from src.research.v4_iteration.research_active.run_entry_branch_head_to_head import add_reclaim_flags
from src.research.v4_iteration.research_active.run_entry_logic_low_risk_base import load_base_dataset


DEFAULT_LOW_RISK_DAILY_SIMULATOR_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_daily_simulator.csv"
DEFAULT_LOW_RISK_TRADE_LOG_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_trade_log.csv"
DEFAULT_LOW_RISK_YEARLY_SUMMARY_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_yearly_summary.csv"
DEFAULT_LOW_RISK_FRICTION_SUMMARY_CSV_PATH = OUT_DIR / "swing_bridge" / "low_risk_friction_summary.csv"
DEFAULT_LOW_RISK_DAILY_SIMULATOR_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_LOW_RISK_DAILY_SIMULATOR.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a template-specific daily chronological simulator on the frozen low-risk template.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument(
        "--onchain-features-csv",
        default=str(DEFAULT_ONCHAIN_FEATURES_CSV_PATH),
        help="Default: ../out/onchain_features.csv",
    )
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument(
        "--live-swing-state-csv",
        default=str(DEFAULT_LIVE_SWING_STATE_CSV_PATH),
        help="Default: ../out/swing_bridge/live_swing_state.csv",
    )
    parser.add_argument(
        "--swing-taxonomy-csv",
        default=str(DEFAULT_SWING_TAXONOMY_CSV_PATH),
        help="Default: ../out/swing_bridge/swing_taxonomy.csv",
    )
    parser.add_argument(
        "--swing-condition-mapping-csv",
        default=str(DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH),
        help="Default: ../out/swing_bridge/swing_condition_mapping.csv",
    )
    parser.add_argument(
        "--frictions-bps",
        default="0,10,25",
        help="Comma-separated round-trip friction assumptions in bps. Default: 0,10,25",
    )
    parser.add_argument(
        "--out-daily-csv",
        default=str(DEFAULT_LOW_RISK_DAILY_SIMULATOR_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_daily_simulator.csv",
    )
    parser.add_argument(
        "--out-trades-csv",
        default=str(DEFAULT_LOW_RISK_TRADE_LOG_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_trade_log.csv",
    )
    parser.add_argument(
        "--out-yearly-csv",
        default=str(DEFAULT_LOW_RISK_YEARLY_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_yearly_summary.csv",
    )
    parser.add_argument(
        "--out-friction-csv",
        default=str(DEFAULT_LOW_RISK_FRICTION_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bridge/low_risk_friction_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_LOW_RISK_DAILY_SIMULATOR_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_LOW_RISK_DAILY_SIMULATOR.md",
    )
    return parser.parse_args()


def parse_frictions(raw: str) -> list[int]:
    values: list[int] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        value = int(item)
        if value < 0:
            raise ValueError("Friction bps must be non-negative.")
        values.append(value)
    if not values:
        raise ValueError("At least one friction assumption is required.")
    return sorted(set(values))


def build_frame_and_trades(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame, masks = load_base_dataset(args)
    frame = add_reclaim_flags(frame)
    frame["date"] = pd.to_datetime(frame["date"])
    entry_mask = build_entry_mask(frame, masks)
    trades = build_trade_table(frame, entry_mask, build_policy())
    if trades.empty:
        raise ValueError("No trades generated for low-risk daily simulator.")

    trades = trades.copy()
    for column in ("signal_date", "entry_date", "exit_date"):
        trades[column] = pd.to_datetime(trades[column])

    date_to_idx = pd.Series(frame.index.values, index=frame["date"])
    trades["entry_idx"] = trades["entry_date"].map(date_to_idx).astype(int)
    trades["exit_idx"] = trades["exit_date"].map(date_to_idx).astype(int)
    trades["signal_idx"] = trades["signal_date"].map(date_to_idx).astype(int)
    trades["entry_year"] = trades["entry_date"].dt.year.astype(int)
    return frame.reset_index(drop=True), trades.sort_values(["entry_date", "trade_id"]).reset_index(drop=True)


def build_state_arrays(frame: pd.DataFrame, trades: pd.DataFrame) -> dict[str, np.ndarray]:
    size = len(frame)
    signal_flag = np.zeros(size, dtype=int)
    entry_flag = np.zeros(size, dtype=int)
    exit_flag = np.zeros(size, dtype=int)
    position_during_day = np.zeros(size, dtype=int)
    position_state_eod = np.zeros(size, dtype=int)
    active_trade_id = np.full(size, np.nan)
    holding_day_number = np.full(size, np.nan)

    for trade in trades.itertuples(index=False):
        signal_idx = int(trade.signal_idx)
        entry_idx = int(trade.entry_idx)
        exit_idx = int(trade.exit_idx)
        trade_id = int(trade.trade_id)

        signal_flag[signal_idx] = 1
        entry_flag[entry_idx] = 1
        exit_flag[exit_idx] = 1
        if entry_idx < exit_idx:
            position_state_eod[entry_idx:exit_idx] = 1
            active_trade_id[entry_idx:exit_idx + 1] = trade_id
        if entry_idx + 1 <= exit_idx:
            position_during_day[entry_idx + 1 : exit_idx + 1] = 1
            holding_day_number[entry_idx + 1 : exit_idx + 1] = np.arange(1, exit_idx - entry_idx + 1, dtype=float)

    return {
        "signal_flag": signal_flag,
        "entry_flag": entry_flag,
        "exit_flag": exit_flag,
        "position_during_day": position_during_day,
        "position_state_eod": position_state_eod,
        "active_trade_id": active_trade_id,
        "holding_day_number": holding_day_number,
    }


def simulate_daily_path(
    frame: pd.DataFrame,
    trades: pd.DataFrame,
    state: dict[str, np.ndarray],
    round_trip_bps: int,
) -> pd.DataFrame:
    side_cost_rate = round_trip_bps / 20000.0
    close_factor = frame["close"] / frame["close"].shift(1)
    close_factor = close_factor.fillna(1.0).to_numpy(dtype=float)

    gross_factor = np.ones(len(frame), dtype=float)
    gross_factor *= np.where(state["position_during_day"] == 1, close_factor, 1.0)

    net_factor = gross_factor.copy()
    if side_cost_rate > 0:
        net_factor *= np.where(state["entry_flag"] == 1, 1.0 - side_cost_rate, 1.0)
        net_factor *= np.where(state["exit_flag"] == 1, 1.0 - side_cost_rate, 1.0)

    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["date"]),
            "friction_round_trip_bps": int(round_trip_bps),
            "signal_flag": state["signal_flag"].astype(int),
            "entry_flag": state["entry_flag"].astype(int),
            "exit_flag": state["exit_flag"].astype(int),
            "position_during_day": state["position_during_day"].astype(int),
            "position_state_eod": np.where(state["position_state_eod"] == 1, "long", "flat"),
            "active_trade_id": state["active_trade_id"],
            "holding_day_number": state["holding_day_number"],
            "close_to_close_return": close_factor - 1.0,
            "gross_daily_factor": gross_factor,
            "gross_daily_return": gross_factor - 1.0,
            "entry_cost_applied": np.where(state["entry_flag"] == 1, side_cost_rate, 0.0),
            "exit_cost_applied": np.where(state["exit_flag"] == 1, side_cost_rate, 0.0),
            "net_daily_factor": net_factor,
            "net_daily_return": net_factor - 1.0,
        }
    )
    daily["equity"] = daily["net_daily_factor"].cumprod()
    daily["running_peak"] = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] / daily["running_peak"] - 1.0
    daily["calendar_year"] = daily["date"].dt.year.astype(int)
    return daily


def build_trade_log(trades: pd.DataFrame, round_trip_bps: int) -> pd.DataFrame:
    side_cost_rate = round_trip_bps / 20000.0
    trade_log = trades.copy()
    gross_factor = trade_log["exit_price"] / trade_log["entry_price"]
    net_factor = gross_factor * (1.0 - side_cost_rate) * (1.0 - side_cost_rate)
    trade_log["friction_round_trip_bps"] = int(round_trip_bps)
    trade_log["entry_cost_rate"] = side_cost_rate
    trade_log["exit_cost_rate"] = side_cost_rate
    trade_log["gross_return"] = gross_factor - 1.0
    trade_log["net_return"] = net_factor - 1.0
    trade_log["winning_trade_flag"] = (trade_log["net_return"] > 0).astype(int)
    trade_log["calendar_holding_days"] = (trade_log["exit_date"] - trade_log["entry_date"]).dt.days.astype(int)
    return trade_log.loc[
        :,
        [
            "friction_round_trip_bps",
            "trade_id",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "gross_return",
            "net_return",
            "holding_days",
            "calendar_holding_days",
            "mfe_pct",
            "mae_pct",
            "exit_reason",
            "entry_cost_rate",
            "exit_cost_rate",
            "winning_trade_flag",
            "entry_year",
        ],
    ].copy()


def summarize_yearly(daily: pd.DataFrame, trade_log: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    years = sorted(set(trade_log["entry_year"].astype(int).tolist()))
    for year in years:
        daily_year = daily.loc[daily["calendar_year"] == year].copy()
        trades_year = trade_log.loc[trade_log["entry_year"] == year].copy()
        equity, drawdown = _equity_curve(daily_year["net_daily_return"])
        returns = pd.to_numeric(trades_year["net_return"], errors="coerce")
        rows.append(
            {
                "friction_round_trip_bps": int(daily["friction_round_trip_bps"].iloc[0]),
                "calendar_year": int(year),
                "trade_count": int(len(trades_year)),
                "win_rate": float((returns > 0).mean()) if not returns.empty else np.nan,
                "mean_trade_return": _safe_mean(returns),
                "median_trade_return": _safe_median(returns),
                "compounded_return": float(equity.iloc[-1] - 1.0) if not equity.empty else np.nan,
                "max_drawdown": float(drawdown.min()) if not drawdown.empty else np.nan,
                "time_in_market": float(pd.to_numeric(daily_year["position_during_day"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows)


def summarize_friction(daily: pd.DataFrame, trade_log: pd.DataFrame) -> dict[str, object]:
    returns = pd.to_numeric(trade_log["net_return"], errors="coerce")
    equity, drawdown = _equity_curve(daily["net_daily_return"])
    elapsed_days = float((daily["date"].max() - daily["date"].min()).days)
    elapsed_years = elapsed_days / 365.25 if elapsed_days > 0 else np.nan
    compounded_return = float(equity.iloc[-1] - 1.0) if not equity.empty else np.nan
    if pd.notna(compounded_return) and pd.notna(elapsed_years) and elapsed_years > 0 and equity.iloc[-1] > 0:
        annualized_return = float(equity.iloc[-1] ** (1.0 / elapsed_years) - 1.0)
    else:
        annualized_return = np.nan
    return {
        "friction_round_trip_bps": int(daily["friction_round_trip_bps"].iloc[0]),
        "trade_count": int(len(trade_log)),
        "win_rate": float((returns > 0).mean()) if not returns.empty else np.nan,
        "mean_trade_return": _safe_mean(returns),
        "median_trade_return": _safe_median(returns),
        "compounded_return": compounded_return,
        "annualized_return": annualized_return,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else np.nan,
        "average_holding_days": _safe_mean(trade_log["holding_days"]),
        "mean_mfe": _safe_mean(trade_log["mfe_pct"]),
        "mean_mae": _safe_mean(trade_log["mae_pct"]),
        "time_in_market": float(pd.to_numeric(daily["position_during_day"], errors="coerce").mean()),
    }


def render_markdown(
    daily_all: pd.DataFrame,
    trades_all: pd.DataFrame,
    yearly_all: pd.DataFrame,
    friction_summary: pd.DataFrame,
) -> str:
    base_row = friction_summary.sort_values("friction_round_trip_bps").iloc[0]
    yearly_zero = yearly_all.loc[yearly_all["friction_round_trip_bps"] == int(base_row["friction_round_trip_bps"])].copy()
    trades_zero = trades_all.loc[trades_all["friction_round_trip_bps"] == int(base_row["friction_round_trip_bps"])].copy()
    latest_daily = daily_all.loc[daily_all["friction_round_trip_bps"] == int(base_row["friction_round_trip_bps"])].copy()

    best_trade = trades_zero.loc[pd.to_numeric(trades_zero["net_return"], errors="coerce").idxmax()]
    worst_trade = trades_zero.loc[pd.to_numeric(trades_zero["net_return"], errors="coerce").idxmin()]

    lines = [
        "# SAFE v4.0 Low Risk Daily Simulator",
        "",
        "## Section 1 — Why This Pass Is Being Run",
        "",
        "- this is a stricter calendar-time simulator for one frozen research template",
        "- it is not a production backtest, not a portfolio system, and not a final robustness proof",
        "- the purpose is to see whether the template still looks sane once translated into a daily equity path with simple trading friction",
        "",
        "## Section 2 — Frozen Entry / Exit Rules",
        "",
        "- entry: `low_risk_wait2_persist_reclaim`",
        "- exit: `fixed_horizon_5d`",
        "- position handling: one position at a time; overlapping signals are skipped while a position is open",
        "- entry assumption: signal-day close",
        "- exit assumption: close after exactly 5 trading days",
        "",
        "## Section 3 — Daily Simulator Assumptions",
        "",
        "- daily chronology uses close-to-close mark-to-market while the trade is active",
        "- the position becomes active after the entry close and contributes returns from the next close-to-close step through the exit close",
        "- friction assumptions are expressed as round-trip bps and split evenly across entry and exit",
        "- tested round-trip friction assumptions: "
        + ", ".join(f"`{int(value)}` bps" for value in friction_summary["friction_round_trip_bps"].tolist()),
        "",
        "## Section 4 — Full-Sample Results",
        "",
        f"- baseline friction: `{int(base_row['friction_round_trip_bps'])}` bps round-trip",
        f"- trade count: `{int(base_row['trade_count'])}`",
        f"- win rate: `{base_row['win_rate']:.2%}`",
        f"- mean trade return: `{base_row['mean_trade_return']:.2%}`",
        f"- median trade return: `{base_row['median_trade_return']:.2%}`",
        f"- compounded return: `{base_row['compounded_return']:.2%}`",
        f"- annualized return: `{base_row['annualized_return']:.2%}`" if pd.notna(base_row["annualized_return"]) else "- annualized return: `n/a`",
        f"- max drawdown: `{base_row['max_drawdown']:.2%}`",
        f"- average holding time: `{base_row['average_holding_days']:.2f}` trading days",
        f"- time in market: `{base_row['time_in_market']:.2%}`",
        f"- mean MFE / MAE: `{base_row['mean_mfe']:.2%}` / `{base_row['mean_mae']:.2%}`",
        f"- latest daily equity: `{latest_daily['equity'].iloc[-1] - 1.0:.2%}` with running drawdown `{latest_daily['drawdown'].iloc[-1]:.2%}`",
        "",
        f"- best trade: `{pd.to_datetime(best_trade['entry_date']).date()}` -> `{pd.to_datetime(best_trade['exit_date']).date()}`, net return `{best_trade['net_return']:.2%}`",
        f"- worst trade: `{pd.to_datetime(worst_trade['entry_date']).date()}` -> `{pd.to_datetime(worst_trade['exit_date']).date()}`, net return `{worst_trade['net_return']:.2%}`",
        "",
        "## Section 5 — Yearly Breakdown",
        "",
        "| Year | Trades | Win rate | Mean trade return | Compounded return | Max drawdown | Time in market |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in yearly_zero.iterrows():
        lines.append(
            f"| `{int(row['calendar_year'])}` | {int(row['trade_count'])} | {row['win_rate']:.2%} | "
            f"{row['mean_trade_return']:.2%} | {row['compounded_return']:.2%} | {row['max_drawdown']:.2%} | "
            f"{row['time_in_market']:.2%} |"
        )

    lines.extend(["", "## Section 6 — Friction Sensitivity", ""])
    lines.append("| Round-trip friction | Trades | Mean trade return | Compounded return | Max drawdown | Viability read |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for _, row in friction_summary.sort_values("friction_round_trip_bps").iterrows():
        if row["compounded_return"] > 0 and row["max_drawdown"] > -0.15:
            viability = "still sane"
        elif row["compounded_return"] > 0:
            viability = "positive but weaker"
        else:
            viability = "fragile"
        lines.append(
            f"| `{int(row['friction_round_trip_bps'])}` bps | {int(row['trade_count'])} | {row['mean_trade_return']:.2%} | "
            f"{row['compounded_return']:.2%} | {row['max_drawdown']:.2%} | {viability} |"
        )

    lines.extend(
        [
            "",
            "## Section 7 — Clear Conclusion",
            "",
        ]
    )

    best_cost = friction_summary.sort_values("friction_round_trip_bps").iloc[0]
    harsh_cost = friction_summary.sort_values("friction_round_trip_bps").iloc[-1]
    if harsh_cost["compounded_return"] > 0 and harsh_cost["max_drawdown"] > -0.15:
        lines.append("- yes, the template still looks sane once translated into a daily chronological simulator.")
    else:
        lines.append("- the template weakens materially once translated into daily chronology and simple trading friction.")

    if harsh_cost["compounded_return"] > 0:
        lines.append("- modest costs hurt the profile, but they do not erase it in this first calendar-time implementation.")
    else:
        lines.append("- even modestly harsher costs challenge the template enough that confidence should stay restrained.")

    lines.append("- the event count is still small, so this should be read as calendar-time sanity, not final proof of deployable robustness.")
    lines.append("- the template remains strong enough to stay the primary active research template.")
    lines.append("- the next justified step would be a more formal template-specific walk-forward implementation or a stricter out-of-time holdout, not renewed branch hunting.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frictions = parse_frictions(args.frictions_bps)
    frame, trades = build_frame_and_trades(args)
    state = build_state_arrays(frame, trades)

    daily_frames: list[pd.DataFrame] = []
    trade_logs: list[pd.DataFrame] = []
    yearly_rows: list[pd.DataFrame] = []
    friction_rows: list[dict[str, object]] = []

    for round_trip_bps in frictions:
        daily = simulate_daily_path(frame, trades, state, round_trip_bps)
        trade_log = build_trade_log(trades, round_trip_bps)
        yearly = summarize_yearly(daily, trade_log)
        friction_summary_row = summarize_friction(daily, trade_log)

        daily_frames.append(daily)
        trade_logs.append(trade_log)
        yearly_rows.append(yearly)
        friction_rows.append(friction_summary_row)

    daily_all = pd.concat(daily_frames, ignore_index=True)
    trades_all = pd.concat(trade_logs, ignore_index=True)
    yearly_all = pd.concat(yearly_rows, ignore_index=True)
    friction_summary = pd.DataFrame(friction_rows).sort_values("friction_round_trip_bps").reset_index(drop=True)

    out_daily = Path(args.out_daily_csv)
    out_trades = Path(args.out_trades_csv)
    out_yearly = Path(args.out_yearly_csv)
    out_friction = Path(args.out_friction_csv)
    out_md = Path(args.out_md)
    for path in (out_daily, out_trades, out_yearly, out_friction, out_md):
        path.parent.mkdir(parents=True, exist_ok=True)

    daily_all.to_csv(out_daily, index=False)
    trades_all.to_csv(out_trades, index=False)
    yearly_all.to_csv(out_yearly, index=False)
    friction_summary.to_csv(out_friction, index=False)
    out_md.write_text(render_markdown(daily_all, trades_all, yearly_all, friction_summary), encoding="utf-8")

    print("SAFE v4.0 low-risk daily simulator complete.")
    print(f"Trades: {int(friction_summary.loc[0, 'trade_count'])}")
    print(f"Friction assumptions: {', '.join(str(value) for value in frictions)} bps round-trip")
    print(f"Daily output: {out_daily}")
    print(f"Trade log: {out_trades}")
    print(f"Yearly summary: {out_yearly}")
    print(f"Friction summary: {out_friction}")
    print(f"Markdown: {out_md}")


if __name__ == "__main__":
    main()
