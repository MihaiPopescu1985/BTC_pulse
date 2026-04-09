from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.path_config import OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.research_active.run_entry_logic_research import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    add_live_flags,
    build_condition_masks,
    build_dataset,
)
from src.research.v4_iteration.research_active.run_entry_logic_bearish_refinement import add_refinement_flags


DEFAULT_ENTRY_LOGIC_BEARISH_CANDLE_TIMING_CSV_PATH = OUT_DIR / "swing_bridge" / "entry_logic_bearish_candle_timing.csv"
DEFAULT_ENTRY_LOGIC_BEARISH_CANDLE_TIMING_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_ENTRY_LOGIC_BEARISH_CANDLE_TIMING.md"
)

SETUP_NAME = "bearish_age0_75_size1_25_with_veto"
UPSIDE_THRESHOLD = 0.02
DRAW_THRESHOLDS: tuple[float, ...] = (0.01, 0.02, 0.03)


@dataclass(frozen=True)
class TriggerSpec:
    name: str
    description: str
    builder: callable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test candle-mechanics timing triggers on the bearish contrarian swing setup zone.",
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
        "--out-csv",
        default=str(DEFAULT_ENTRY_LOGIC_BEARISH_CANDLE_TIMING_CSV_PATH),
        help="Default: ../out/swing_bridge/entry_logic_bearish_candle_timing.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_ENTRY_LOGIC_BEARISH_CANDLE_TIMING_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_ENTRY_LOGIC_BEARISH_CANDLE_TIMING.md",
    )
    return parser.parse_args()


def _validate_date_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"{name} input is empty.")
    if "date" not in frame.columns:
        raise ValueError(f"{name} input must contain a 'date' column.")
    validated = frame.copy()
    validated["date"] = pd.to_datetime(validated["date"], errors="raise")
    if validated["date"].duplicated().any():
        raise ValueError(f"{name} input has duplicate dates.")
    return validated.sort_values("date").reset_index(drop=True)


def load_base_dataset(args: argparse.Namespace) -> pd.DataFrame:
    dataset, condition_mapping = build_dataset(args)
    masks = build_condition_masks(dataset, condition_mapping)
    dataset = add_live_flags(dataset, masks)
    dataset = add_refinement_flags(dataset)

    price = load_daily_price_json(args.price_json).reset_index()
    if "timestamp" in price.columns:
        price = price.rename(columns={"timestamp": "date"})
    price = _validate_date_frame("price", price.loc[:, ["date", "open", "high", "low", "close"]])

    merged = dataset.merge(price, on="date", how="inner", validate="one_to_one", suffixes=("", "_price"))
    if len(merged) != len(dataset):
        raise ValueError("Price merge dropped rows unexpectedly.")

    merged["setup_zone_best"] = (
        masks["bearish_risk_regime"]
        & merged["live_reversal_window"]
        & merged["age_lte_0_75"]
        & merged["size_lte_1_25"]
        & (~merged["warning_active"])
    ).fillna(False)
    merged["raw_bearish_risk_regime"] = masks["bearish_risk_regime"].fillna(False)
    return merged.reset_index(drop=True)


def add_candle_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    total_range = (enriched["high"] - enriched["low"]).astype(float)
    body_size = (enriched["close"] - enriched["open"]).abs().astype(float)
    upper_wick = (enriched["high"] - enriched[["open", "close"]].max(axis=1)).astype(float)
    lower_wick = (enriched[["open", "close"]].min(axis=1) - enriched["low"]).astype(float)
    safe_range = total_range.where(total_range > 0.0, np.nan)

    enriched["total_range"] = total_range
    enriched["body_size"] = body_size
    enriched["upper_wick"] = upper_wick
    enriched["lower_wick"] = lower_wick
    enriched["body_pct_of_range"] = body_size / safe_range
    enriched["lower_wick_pct_of_range"] = lower_wick / safe_range
    enriched["upper_wick_pct_of_range"] = upper_wick / safe_range
    enriched["close_position_in_range"] = (enriched["close"] - enriched["low"]) / safe_range

    prev_high = enriched["high"].shift(1)
    prev_low = enriched["low"].shift(1)
    prev_close = enriched["close"].shift(1)
    prev_open = enriched["open"].shift(1)
    prev_range_high = pd.concat([prev_open, prev_close], axis=1).max(axis=1)
    prev_range_low = pd.concat([prev_open, prev_close], axis=1).min(axis=1)

    enriched["bullish_close"] = enriched["close"] > enriched["open"]
    enriched["close_above_prev_high"] = enriched["close"] > prev_high
    enriched["close_above_prev_close"] = enriched["close"] > prev_close
    enriched["low_below_prev_low_but_close_recovers"] = (enriched["low"] < prev_low) & (enriched["close"] > prev_close)
    enriched["close_back_inside_prev_range"] = (enriched["close"] >= prev_range_low) & (enriched["close"] <= prev_range_high)

    enriched["prior_2d_return"] = enriched["close"].pct_change(2).shift(1)
    enriched["prior_3d_return"] = enriched["close"].pct_change(3).shift(1)
    enriched["current_1d_return"] = enriched["close"].pct_change(1)
    enriched["momentum_shift_2d"] = (enriched["prior_2d_return"] < 0.0) & (enriched["current_1d_return"] > 0.0)
    enriched["momentum_shift_3d"] = (enriched["prior_3d_return"] < 0.0) & (enriched["current_1d_return"] > 0.0)
    return enriched


def build_triggers(frame: pd.DataFrame) -> tuple[TriggerSpec, ...]:
    return (
        TriggerSpec(
            name="lower_wick_rejection",
            description="Large lower-wick rejection with a strong close near the top of the bar.",
            builder=lambda df: (
                (df["lower_wick_pct_of_range"] >= 0.45)
                & (df["close_position_in_range"] >= 0.65)
                & (df["bullish_close"] | (df["current_1d_return"] >= 0.0))
            ),
        ),
        TriggerSpec(
            name="reclaim_trigger",
            description="Close strength above prior close with reclaim of prior bar structure.",
            builder=lambda df: (
                df["close_above_prev_close"]
                & (df["close_above_prev_high"] | df["close_back_inside_prev_range"])
                & (df["close_position_in_range"] >= 0.55)
            ),
        ),
        TriggerSpec(
            name="failed_breakdown_recovery",
            description="Low breaks prior low but the bar closes back with visible recovery.",
            builder=lambda df: (
                df["low_below_prev_low_but_close_recovers"]
                & df["bullish_close"]
                & (df["close_position_in_range"] >= 0.60)
            ),
        ),
        TriggerSpec(
            name="momentum_turn",
            description="Very short-term downside gives way to a positive reversal day.",
            builder=lambda df: (
                (df["prior_3d_return"] <= -0.02)
                & (df["current_1d_return"] >= 0.01)
                & df["bullish_close"]
                & (df["close_position_in_range"] >= 0.55)
            ),
        ),
    )


def build_setup_episodes(setup_mask: pd.Series) -> list[tuple[int, int]]:
    episodes: list[tuple[int, int]] = []
    active_start: int | None = None
    values = setup_mask.fillna(False).to_numpy(dtype=bool)
    for idx, flag in enumerate(values):
        if flag and active_start is None:
            active_start = idx
        elif not flag and active_start is not None:
            episodes.append((active_start, idx - 1))
            active_start = None
    if active_start is not None:
        episodes.append((active_start, len(values) - 1))
    return episodes


def first_trigger_in_window(trigger_mask: pd.Series, start_idx: int, wait_days: int, immediate_only: bool) -> int | None:
    if immediate_only:
        return start_idx if bool(trigger_mask.iloc[start_idx]) else None
    left = start_idx + 1
    right = min(start_idx + wait_days, len(trigger_mask) - 1)
    if left > right:
        return None
    window = trigger_mask.iloc[left : right + 1]
    hits = np.flatnonzero(window.to_numpy(dtype=bool))
    if len(hits) == 0:
        return None
    return left + int(hits[0])


def compute_path_barriers(price: pd.DataFrame, entry_idx: int) -> dict[str, float]:
    entry_close = float(price.iloc[entry_idx]["close"])
    future = price.iloc[entry_idx + 1 : entry_idx + 11].copy()
    result: dict[str, float] = {}
    for draw in DRAW_THRESHOLDS:
        down_level = entry_close * (1.0 - draw)
        up_level = entry_close * (1.0 + UPSIDE_THRESHOLD)
        down_hits = future.index[future["low"] <= down_level].tolist()
        up_hits = future.index[future["high"] >= up_level].tolist()
        first_down = down_hits[0] if down_hits else None
        first_up = up_hits[0] if up_hits else None
        result[f"hit_neg_{int(draw * 100)}pct_before_up2pct"] = float(
            first_down is not None and (first_up is None or first_down <= first_up)
        )
    return result


def build_entry_rows(frame: pd.DataFrame, trigger: TriggerSpec, wait_days: int, immediate_only: bool) -> list[dict[str, object]]:
    trigger_mask = trigger.builder(frame).fillna(False)
    episodes = build_setup_episodes(frame["setup_zone_best"])
    rows: list[dict[str, object]] = []
    for episode_start, episode_end in episodes:
        entry_idx = first_trigger_in_window(trigger_mask, episode_start, wait_days, immediate_only)
        if entry_idx is None:
            continue
        setup_close = float(frame.iloc[episode_start]["close"])
        pre_entry_slice = frame.iloc[episode_start : entry_idx + 1]
        pre_entry_drawdown = float(pre_entry_slice["low"].min() / setup_close - 1.0)
        entry_row = frame.iloc[entry_idx]
        path_metrics = compute_path_barriers(frame.loc[:, ["date", "open", "high", "low", "close"]], entry_idx)
        rows.append(
            {
                "setup_start_date": frame.iloc[episode_start]["date"],
                "setup_end_date": frame.iloc[episode_end]["date"],
                "entry_date": entry_row["date"],
                "trigger_delay_days": int(entry_idx - episode_start),
                "pre_entry_setup_drawdown_pct": pre_entry_drawdown,
                "next_swing_direction": entry_row["next_swing_direction"],
                "next_swing_abs_amplitude": entry_row["next_swing_abs_amplitude"],
                "next_swing_duration_days": entry_row["next_swing_duration_days"],
                "next_swing_size_class": entry_row["next_swing_size_class"],
                "next_swing_duration_class": entry_row["next_swing_duration_class"],
                "ret_10d": entry_row["ret_10d"],
                "max_up_10d": entry_row["max_up_10d"],
                "max_down_10d": entry_row["max_down_10d"],
                "touch_up_2pct_10d": entry_row["touch_up_2pct_10d"],
                "touch_down_2pct_10d": entry_row["touch_down_2pct_10d"],
                **path_metrics,
            }
        )
    return rows


def _rate(series: pd.Series, value: str) -> float:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    return float((clean == value).mean())


def _mean(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else np.nan


def _median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else np.nan


def summarize_entry_table(
    entry_rows: list[dict[str, object]],
    *,
    template_name: str,
    template_family: str,
    trigger_name: str,
    wait_window: str,
    description: str,
    baseline_reference: str,
) -> dict[str, object]:
    frame = pd.DataFrame(entry_rows)
    if frame.empty:
        return {
            "template_name": template_name,
            "template_family": template_family,
            "trigger_name": trigger_name,
            "wait_window": wait_window,
            "rule_definition": description,
            "baseline_reference": baseline_reference,
            "sample_count": 0,
            "next_up_swing_rate": np.nan,
            "next_down_swing_rate": np.nan,
            "median_next_swing_abs_amplitude": np.nan,
            "median_next_swing_duration_days": np.nan,
            "next_small_swing_rate": np.nan,
            "next_medium_swing_rate": np.nan,
            "next_large_swing_rate": np.nan,
            "ret_10d_mean": np.nan,
            "ret_10d_median": np.nan,
            "ret_10d_win_rate": np.nan,
            "max_up_10d_mean": np.nan,
            "max_up_10d_median": np.nan,
            "max_down_10d_mean": np.nan,
            "max_down_10d_median": np.nan,
            "touch_up_2pct_10d_rate": np.nan,
            "touch_down_2pct_10d_rate": np.nan,
            "pre_entry_drawdown_mean": np.nan,
            "pre_entry_drawdown_median": np.nan,
            "trigger_delay_mean": np.nan,
            "trigger_delay_median": np.nan,
            "hit_neg_1pct_before_up2pct_rate": np.nan,
            "hit_neg_2pct_before_up2pct_rate": np.nan,
            "hit_neg_3pct_before_up2pct_rate": np.nan,
        }

    ret_10d = pd.to_numeric(frame["ret_10d"], errors="coerce")
    return {
        "template_name": template_name,
        "template_family": template_family,
        "trigger_name": trigger_name,
        "wait_window": wait_window,
        "rule_definition": description,
        "baseline_reference": baseline_reference,
        "sample_count": int(len(frame)),
        "next_up_swing_rate": _rate(frame["next_swing_direction"], "up"),
        "next_down_swing_rate": _rate(frame["next_swing_direction"], "down"),
        "median_next_swing_abs_amplitude": _median(frame["next_swing_abs_amplitude"]),
        "median_next_swing_duration_days": _median(frame["next_swing_duration_days"]),
        "next_small_swing_rate": _rate(frame["next_swing_size_class"], "small"),
        "next_medium_swing_rate": _rate(frame["next_swing_size_class"], "medium"),
        "next_large_swing_rate": _rate(frame["next_swing_size_class"], "large"),
        "ret_10d_mean": _mean(frame["ret_10d"]),
        "ret_10d_median": _median(frame["ret_10d"]),
        "ret_10d_win_rate": float((ret_10d > 0).mean()) if ret_10d.notna().any() else np.nan,
        "max_up_10d_mean": _mean(frame["max_up_10d"]),
        "max_up_10d_median": _median(frame["max_up_10d"]),
        "max_down_10d_mean": _mean(frame["max_down_10d"]),
        "max_down_10d_median": _median(frame["max_down_10d"]),
        "touch_up_2pct_10d_rate": _mean(frame["touch_up_2pct_10d"]),
        "touch_down_2pct_10d_rate": _mean(frame["touch_down_2pct_10d"]),
        "pre_entry_drawdown_mean": _mean(frame["pre_entry_setup_drawdown_pct"]),
        "pre_entry_drawdown_median": _median(frame["pre_entry_setup_drawdown_pct"]),
        "trigger_delay_mean": _mean(frame["trigger_delay_days"]),
        "trigger_delay_median": _median(frame["trigger_delay_days"]),
        "hit_neg_1pct_before_up2pct_rate": _mean(frame["hit_neg_1pct_before_up2pct"]),
        "hit_neg_2pct_before_up2pct_rate": _mean(frame["hit_neg_2pct_before_up2pct"]),
        "hit_neg_3pct_before_up2pct_rate": _mean(frame["hit_neg_3pct_before_up2pct"]),
    }


def build_baselines(frame: pd.DataFrame) -> list[dict[str, object]]:
    raw_rows = [
        {
            "next_swing_direction": row["next_swing_direction"],
            "next_swing_abs_amplitude": row["next_swing_abs_amplitude"],
            "next_swing_duration_days": row["next_swing_duration_days"],
            "next_swing_size_class": row["next_swing_size_class"],
            "next_swing_duration_class": row["next_swing_duration_class"],
            "ret_10d": row["ret_10d"],
            "max_up_10d": row["max_up_10d"],
            "max_down_10d": row["max_down_10d"],
            "touch_up_2pct_10d": row["touch_up_2pct_10d"],
            "touch_down_2pct_10d": row["touch_down_2pct_10d"],
            "pre_entry_setup_drawdown_pct": np.nan,
            "trigger_delay_days": 0,
            **compute_path_barriers(frame.loc[:, ["date", "open", "high", "low", "close"]], idx),
        }
        for idx, row in frame.loc[frame["raw_bearish_risk_regime"]].iterrows()
    ]

    episode_rows = []
    for episode_start, episode_end in build_setup_episodes(frame["setup_zone_best"]):
        row = frame.iloc[episode_start]
        episode_rows.append(
            {
                "next_swing_direction": row["next_swing_direction"],
                "next_swing_abs_amplitude": row["next_swing_abs_amplitude"],
                "next_swing_duration_days": row["next_swing_duration_days"],
                "next_swing_size_class": row["next_swing_size_class"],
                "next_swing_duration_class": row["next_swing_duration_class"],
                "ret_10d": row["ret_10d"],
                "max_up_10d": row["max_up_10d"],
                "max_down_10d": row["max_down_10d"],
                "touch_up_2pct_10d": row["touch_up_2pct_10d"],
                "touch_down_2pct_10d": row["touch_down_2pct_10d"],
                "pre_entry_setup_drawdown_pct": 0.0,
                "trigger_delay_days": 0,
                **compute_path_barriers(frame.loc[:, ["date", "open", "high", "low", "close"]], episode_start),
            }
        )

    return [
        summarize_entry_table(
            raw_rows,
            template_name="raw_bearish_risk_regime",
            template_family="baseline_raw",
            trigger_name="none",
            wait_window="none",
            description="Raw bearish_risk_regime baseline.",
            baseline_reference="raw_bearish_risk_regime",
        ),
        summarize_entry_table(
            episode_rows,
            template_name="setup_zone_immediate_entry",
            template_family="baseline_setup_zone",
            trigger_name="none",
            wait_window="none",
            description="Immediate entry on first day of each bearish setup-zone episode.",
            baseline_reference="setup_zone_immediate_entry",
        ),
    ]


def build_results(frame: pd.DataFrame) -> pd.DataFrame:
    rows = build_baselines(frame)
    for trigger in build_triggers(frame):
        same_day_rows = build_entry_rows(frame, trigger, wait_days=0, immediate_only=True)
        rows.append(
            summarize_entry_table(
                same_day_rows,
                template_name=f"{SETUP_NAME}_{trigger.name}_same_day",
                template_family="timed_entry",
                trigger_name=trigger.name,
                wait_window="same_day",
                description=f"{SETUP_NAME} plus same-day {trigger.description}",
                baseline_reference="setup_zone_immediate_entry",
            )
        )

        wait3_rows = build_entry_rows(frame, trigger, wait_days=3, immediate_only=False)
        rows.append(
            summarize_entry_table(
                wait3_rows,
                template_name=f"{SETUP_NAME}_{trigger.name}_wait3",
                template_family="timed_entry",
                trigger_name=trigger.name,
                wait_window="wait_1_to_3_days",
                description=f"{SETUP_NAME} plus {trigger.description} within the next 3 bars after setup.",
                baseline_reference="setup_zone_immediate_entry",
            )
        )

    results = pd.DataFrame(rows)
    raw = results.loc[results["template_name"] == "raw_bearish_risk_regime"].iloc[0]
    setup = results.loc[results["template_name"] == "setup_zone_immediate_entry"].iloc[0]

    for prefix, baseline in (("raw", raw), ("setup", setup)):
        results[f"delta_vs_{prefix}_next_up"] = pd.to_numeric(results["next_up_swing_rate"], errors="coerce") - float(baseline["next_up_swing_rate"])
        results[f"delta_vs_{prefix}_next_down"] = pd.to_numeric(results["next_down_swing_rate"], errors="coerce") - float(baseline["next_down_swing_rate"])
        results[f"delta_vs_{prefix}_ret_10d_mean"] = pd.to_numeric(results["ret_10d_mean"], errors="coerce") - float(baseline["ret_10d_mean"])
        results[f"delta_vs_{prefix}_max_down_10d_mean"] = pd.to_numeric(results["max_down_10d_mean"], errors="coerce") - float(baseline["max_down_10d_mean"])
        results[f"delta_vs_{prefix}_touch_down_2pct_10d_rate"] = (
            pd.to_numeric(results["touch_down_2pct_10d_rate"], errors="coerce") - float(baseline["touch_down_2pct_10d_rate"])
        )
        results[f"delta_vs_{prefix}_hit_neg_2pct_before_up2pct_rate"] = (
            pd.to_numeric(results["hit_neg_2pct_before_up2pct_rate"], errors="coerce") - float(baseline["hit_neg_2pct_before_up2pct_rate"])
        )

    timed = results.loc[results["template_family"] == "timed_entry"].copy()
    sample_penalty = pd.to_numeric(timed["sample_count"], errors="coerce").fillna(0).clip(upper=40) / 40.0
    timed["timing_rank"] = (
        pd.to_numeric(timed["delta_vs_setup_ret_10d_mean"], errors="coerce").fillna(0.0)
        - pd.to_numeric(timed["delta_vs_setup_max_down_10d_mean"], errors="coerce").fillna(0.0)
        - pd.to_numeric(timed["delta_vs_setup_touch_down_2pct_10d_rate"], errors="coerce").fillna(0.0)
        - pd.to_numeric(timed["delta_vs_setup_hit_neg_2pct_before_up2pct_rate"], errors="coerce").fillna(0.0)
        + 0.50 * pd.to_numeric(timed["delta_vs_setup_next_up"], errors="coerce").fillna(0.0)
    ) * sample_penalty
    results = results.merge(timed.loc[:, ["template_name", "timing_rank"]], on="template_name", how="left")
    return results.sort_values(["template_family", "timing_rank", "sample_count"], ascending=[True, False, False]).reset_index(drop=True)


def render_markdown(results: pd.DataFrame) -> str:
    timed = results.loc[(results["template_family"] == "timed_entry") & (results["sample_count"] >= 5)].copy()
    ranked = timed.sort_values(["timing_rank", "sample_count"], ascending=[False, False]).head(8)
    best = ranked.head(3)

    lines = [
        "# SAFE v4.0 Entry Logic Bearish Candle Timing",
        "",
        "## Section 1 — Candle-Mechanics Features Tested",
        "",
        "- candle geometry:",
        "  - total range",
        "  - body size",
        "  - upper/lower wick size",
        "  - body / wick percentages of range",
        "  - close position in range",
        "- reclaim / recovery mechanics:",
        "  - bullish close",
        "  - close above previous close",
        "  - close above previous high",
        "  - low below previous low but close recovers",
        "  - close back inside previous body range",
        "- very short sequence context:",
        "  - prior 2d return",
        "  - prior 3d return",
        "  - current 1d return",
        "  - 2d / 3d momentum shift flags",
        "",
        "## Section 2 — Trigger Variants Tested",
        "",
        "- triggers:",
        "  - lower_wick_rejection",
        "  - reclaim_trigger",
        "  - failed_breakdown_recovery",
        "  - momentum_turn",
        "- timing modes:",
        "  - same-day trigger on setup start",
        "  - trigger within days 1-3 after setup start",
        "",
    ]
    for _, row in ranked.iterrows():
        lines.append(
            f"- `{row['template_name']}`: timing rank `{row['timing_rank']:.3f}`, "
            f"next up `{row['next_up_swing_rate']:.2%}`, ret_10d mean `{row['ret_10d_mean']:.2%}`, "
            f"max_down_10d mean `{row['max_down_10d_mean']:.2%}`, "
            f"hit -2% before +2% `{row['hit_neg_2pct_before_up2pct_rate']:.2%}`, n=`{int(row['sample_count'])}`"
        )

    lines.extend(["", "## Section 3 — Best Trigger Variants vs Setup-Zone Baseline", ""])
    for _, row in best.iterrows():
        lines.append(
            f"- `{row['template_name']}` vs setup baseline: "
            f"delta next-up `{row['delta_vs_setup_next_up']:+.2%}`, "
            f"delta ret_10d mean `{row['delta_vs_setup_ret_10d_mean']:+.2%}`, "
            f"delta max_down_10d mean `{row['delta_vs_setup_max_down_10d_mean']:+.2%}`, "
            f"delta touch_down `{row['delta_vs_setup_touch_down_2pct_10d_rate']:+.2%}`, "
            f"delta hit -2% before +2% `{row['delta_vs_setup_hit_neg_2pct_before_up2pct_rate']:+.2%}`"
        )

    lines.extend(["", "## Section 4 — Whether Candle Timing Improves Entry Quality", ""])
    helpful = timed.loc[
        (pd.to_numeric(timed["delta_vs_setup_ret_10d_mean"], errors="coerce") > 0)
        & (pd.to_numeric(timed["delta_vs_setup_max_down_10d_mean"], errors="coerce") >= 0)
        & (pd.to_numeric(timed["delta_vs_setup_hit_neg_2pct_before_up2pct_rate"], errors="coerce") < 0)
        & (pd.to_numeric(timed["delta_vs_setup_next_up"], errors="coerce") > -0.15)
        & (pd.to_numeric(timed["delta_vs_setup_touch_down_2pct_10d_rate"], errors="coerce") <= 0)
    ].sort_values("timing_rank", ascending=False)
    if not helpful.empty:
        for _, row in helpful.iterrows():
            lines.append(
                f"- `{row['template_name']}` helps timing: it improved `ret_10d` by `{row['delta_vs_setup_ret_10d_mean']:+.2%}` "
                f"and reduced hit `-2% before +2%` by `{abs(row['delta_vs_setup_hit_neg_2pct_before_up2pct_rate']):.2%}`."
            )
    else:
        lines.append("- No trigger clearly improved both return quality and early-pain metrics versus the setup-zone baseline.")

    weak = timed.loc[
        ~(
            (pd.to_numeric(timed["delta_vs_setup_ret_10d_mean"], errors="coerce") > 0)
            & (pd.to_numeric(timed["delta_vs_setup_max_down_10d_mean"], errors="coerce") >= 0)
            & (pd.to_numeric(timed["delta_vs_setup_hit_neg_2pct_before_up2pct_rate"], errors="coerce") < 0)
            & (pd.to_numeric(timed["delta_vs_setup_next_up"], errors="coerce") > -0.15)
            & (pd.to_numeric(timed["delta_vs_setup_touch_down_2pct_10d_rate"], errors="coerce") <= 0)
        )
    ].sort_values("timing_rank", ascending=False)
    for _, row in weak.head(4).iterrows():
        lines.append(
            f"- `{row['template_name']}` does not justify itself yet: "
            f"delta ret_10d `{row['delta_vs_setup_ret_10d_mean']:+.2%}`, "
            f"delta max_down `{row['delta_vs_setup_max_down_10d_mean']:+.2%}`, "
            f"delta hit -2% before +2% `{row['delta_vs_setup_hit_neg_2pct_before_up2pct_rate']:+.2%}`."
        )

    lines.extend(["", "## Section 5 — Clear Conclusion", ""])
    if best.empty:
        lines.append("- None of the tested candle triggers produced enough entries to justify further work.")
    else:
        top = best.iloc[0]
        lines.append(
            f"- Best current trigger: `{top['template_name']}` with n=`{int(top['sample_count'])}`, "
            f"next up `{top['next_up_swing_rate']:.2%}`, ret_10d mean `{top['ret_10d_mean']:.2%}`, "
            f"max_down_10d mean `{top['max_down_10d_mean']:.2%}`, "
            f"hit -2% before +2% `{top['hit_neg_2pct_before_up2pct_rate']:.2%}`."
        )
        if (
            pd.notna(top["delta_vs_setup_ret_10d_mean"])
            and top["delta_vs_setup_ret_10d_mean"] > 0
            and pd.notna(top["delta_vs_setup_hit_neg_2pct_before_up2pct_rate"])
            and top["delta_vs_setup_hit_neg_2pct_before_up2pct_rate"] < 0
            and pd.notna(top["delta_vs_setup_next_up"])
            and top["delta_vs_setup_next_up"] > -0.15
            and pd.notna(top["delta_vs_setup_touch_down_2pct_10d_rate"])
            and top["delta_vs_setup_touch_down_2pct_10d_rate"] <= 0
        ):
            lines.append("- Candle mechanics do help this branch at least modestly, and the branch is moving from setup-zone only toward a usable entry candidate.")
        else:
            lines.append("- Candle mechanics did not yet cleanly solve the early-pain problem without sacrificing too much next-swing alignment. This remains primarily a setup zone, not a robust entry candidate.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    dataset = load_base_dataset(args)
    dataset = add_candle_features(dataset)
    results = build_results(dataset)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(results), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(results)}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
