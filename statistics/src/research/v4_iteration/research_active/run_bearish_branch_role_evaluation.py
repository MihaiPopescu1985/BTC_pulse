from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
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
from src.research.v4_iteration.research_active.run_entry_logic_bearish_candle_timing import (
    DRAW_THRESHOLDS,
    UPSIDE_THRESHOLD,
    build_setup_episodes,
    compute_path_barriers,
)


DEFAULT_BEARISH_BRANCH_ROLE_EVALUATION_CSV_PATH = OUT_DIR / "swing_bridge" / "bearish_branch_role_evaluation.csv"
DEFAULT_BEARISH_BRANCH_ROLE_EVALUATION_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_BEARISH_BRANCH_ROLE_EVALUATION.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the bearish contrarian branch as watchlist state, context filter, and regime layer.",
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
        default=str(DEFAULT_BEARISH_BRANCH_ROLE_EVALUATION_CSV_PATH),
        help="Default: ../out/swing_bridge/bearish_branch_role_evaluation.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_BEARISH_BRANCH_ROLE_EVALUATION_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_BEARISH_BRANCH_ROLE_EVALUATION.md",
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


def load_dataset(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    dataset, condition_mapping = build_dataset(args)
    masks = build_condition_masks(dataset, condition_mapping)
    dataset = add_live_flags(dataset, masks)
    dataset = add_refinement_flags(dataset)

    price = load_daily_price_json(args.price_json).reset_index()
    if "timestamp" in price.columns:
        price = price.rename(columns={"timestamp": "date"})
    price = _validate_date_frame("price", price.loc[:, ["date", "open", "high", "low", "close"]])

    dataset = dataset.merge(price, on="date", how="inner", validate="one_to_one")
    if dataset.empty:
        raise ValueError("Price merge produced an empty dataset.")
    rename_map: dict[str, str] = {}
    for field in ("open", "high", "low", "close"):
        if field not in dataset.columns:
            if f"{field}_y" in dataset.columns:
                rename_map[f"{field}_y"] = field
            elif f"{field}_x" in dataset.columns:
                rename_map[f"{field}_x"] = field
    if rename_map:
        dataset = dataset.rename(columns=rename_map)
    drop_columns = [f"{field}_x" for field in ("open", "high", "low", "close") if f"{field}_x" in dataset.columns]
    drop_columns.extend(f"{field}_y" for field in ("open", "high", "low", "close") if f"{field}_y" in dataset.columns)
    drop_columns = [column for column in drop_columns if column not in {"open", "high", "low", "close"}]
    if drop_columns:
        dataset = dataset.drop(columns=drop_columns)
    missing_ohlc = [field for field in ("open", "high", "low", "close") if field not in dataset.columns]
    if missing_ohlc:
        raise ValueError(f"Price columns missing after merge: {missing_ohlc}")

    dataset["setup_zone_best"] = (
        masks["bearish_risk_regime"]
        & dataset["live_reversal_window"]
        & dataset["age_lte_0_75"]
        & dataset["size_lte_1_25"]
        & (~dataset["warning_active"])
    ).fillna(False)
    dataset["raw_bearish_risk_regime"] = masks["bearish_risk_regime"].fillna(False)
    dataset["onchain_dominance_support"] = masks["onchain_dominance_support"].fillna(False)

    taxonomy = pd.read_csv(args.swing_taxonomy_csv)
    taxonomy["start_date"] = pd.to_datetime(taxonomy["start_date"], errors="raise")
    taxonomy["end_date"] = pd.to_datetime(taxonomy["end_date"], errors="raise")
    return dataset.reset_index(drop=True), taxonomy


def _mean(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else np.nan


def _median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else np.nan


def _rate(series: pd.Series, value: str) -> float:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    return float((clean == value).mean())


def first_future_upswing_days(date: pd.Timestamp, taxonomy: pd.DataFrame) -> float:
    future = taxonomy.loc[(taxonomy["direction"] == "up") & (taxonomy["start_date"] > date)]
    if future.empty:
        return np.nan
    return float((future.iloc[0]["start_date"] - date).days)


def time_to_upside_touch_days(data: pd.DataFrame, row_index: int, horizon: int = 10, threshold: float = UPSIDE_THRESHOLD) -> float:
    entry_close = float(data.iloc[row_index]["close"])
    future = data.iloc[row_index + 1 : row_index + horizon + 1]
    hits = future.index[future["high"] >= entry_close * (1.0 + threshold)].tolist()
    if not hits:
        return np.nan
    return float(hits[0] - row_index)


def enrich_watchlist_rows(frame: pd.DataFrame, taxonomy: pd.DataFrame, indices: list[int]) -> list[dict[str, object]]:
    ohlc = frame.loc[:, ["date", "open", "high", "low", "close"]]
    rows: list[dict[str, object]] = []
    for idx in indices:
        row = frame.iloc[idx]
        rows.append(
            {
                "date": row["date"],
                "next_swing_direction": row["next_swing_direction"],
                "next_swing_abs_amplitude": row["next_swing_abs_amplitude"],
                "next_swing_duration_days": row["next_swing_duration_days"],
                "next_swing_size_class": row["next_swing_size_class"],
                "ret_10d": row["ret_10d"],
                "max_up_3d": row["max_up_3d"],
                "max_up_5d": row["max_up_5d"],
                "max_up_10d": row["max_up_10d"],
                "max_down_10d": row["max_down_10d"],
                "touch_up_2pct_3d": row["touch_up_2pct_3d"],
                "touch_up_2pct_5d": row["touch_up_2pct_5d"],
                "touch_up_2pct_10d": row["touch_up_2pct_10d"],
                "touch_down_2pct_10d": row["touch_down_2pct_10d"],
                "days_to_next_upswing_start": first_future_upswing_days(row["date"], taxonomy),
                "days_to_up2_touch_10d": time_to_upside_touch_days(frame, idx, horizon=10, threshold=0.02),
                **compute_path_barriers(ohlc, idx),
            }
        )
    return rows


def summarize_rows(rows: list[dict[str, object]], *, role_type: str, role_name: str, description: str) -> dict[str, object]:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {
            "role_type": role_type,
            "role_name": role_name,
            "description": description,
            "sample_count": 0,
            "next_up_swing_rate": np.nan,
            "next_down_swing_rate": np.nan,
            "median_next_swing_abs_amplitude": np.nan,
            "median_next_swing_duration_days": np.nan,
            "ret_10d_mean": np.nan,
            "ret_10d_median": np.nan,
            "max_up_3d_mean": np.nan,
            "max_up_5d_mean": np.nan,
            "max_up_10d_mean": np.nan,
            "max_down_10d_mean": np.nan,
            "touch_up_2pct_3d_rate": np.nan,
            "touch_up_2pct_5d_rate": np.nan,
            "touch_up_2pct_10d_rate": np.nan,
            "touch_down_2pct_10d_rate": np.nan,
            "median_days_to_next_upswing_start": np.nan,
            "median_days_to_up2_touch_10d": np.nan,
            "hit_neg_1pct_before_up2pct_rate": np.nan,
            "hit_neg_2pct_before_up2pct_rate": np.nan,
            "hit_neg_3pct_before_up2pct_rate": np.nan,
            "upside_touch_asymmetry_10d": np.nan,
            "excursion_asymmetry_10d": np.nan,
        }

    return {
        "role_type": role_type,
        "role_name": role_name,
        "description": description,
        "sample_count": int(len(frame)),
        "next_up_swing_rate": _rate(frame["next_swing_direction"], "up"),
        "next_down_swing_rate": _rate(frame["next_swing_direction"], "down"),
        "median_next_swing_abs_amplitude": _median(frame["next_swing_abs_amplitude"]),
        "median_next_swing_duration_days": _median(frame["next_swing_duration_days"]),
        "ret_10d_mean": _mean(frame["ret_10d"]),
        "ret_10d_median": _median(frame["ret_10d"]),
        "max_up_3d_mean": _mean(frame["max_up_3d"]),
        "max_up_5d_mean": _mean(frame["max_up_5d"]),
        "max_up_10d_mean": _mean(frame["max_up_10d"]),
        "max_down_10d_mean": _mean(frame["max_down_10d"]),
        "touch_up_2pct_3d_rate": _mean(frame["touch_up_2pct_3d"]),
        "touch_up_2pct_5d_rate": _mean(frame["touch_up_2pct_5d"]),
        "touch_up_2pct_10d_rate": _mean(frame["touch_up_2pct_10d"]),
        "touch_down_2pct_10d_rate": _mean(frame["touch_down_2pct_10d"]),
        "median_days_to_next_upswing_start": _median(frame["days_to_next_upswing_start"]),
        "median_days_to_up2_touch_10d": _median(frame["days_to_up2_touch_10d"]),
        "hit_neg_1pct_before_up2pct_rate": _mean(frame["hit_neg_1pct_before_up2pct"]),
        "hit_neg_2pct_before_up2pct_rate": _mean(frame["hit_neg_2pct_before_up2pct"]),
        "hit_neg_3pct_before_up2pct_rate": _mean(frame["hit_neg_3pct_before_up2pct"]),
        "upside_touch_asymmetry_10d": _mean(frame["touch_up_2pct_10d"]) - _mean(frame["touch_down_2pct_10d"]),
        "excursion_asymmetry_10d": _mean(frame["max_up_10d"]) - abs(_mean(frame["max_down_10d"])),
    }


def build_role_rows(frame: pd.DataFrame, taxonomy: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    setup_episodes = build_setup_episodes(frame["setup_zone_best"])
    setup_episode_starts = [start for start, _ in setup_episodes]
    rows.append(
        summarize_rows(
            enrich_watchlist_rows(frame, taxonomy, setup_episode_starts),
            role_type="watchlist_state",
            role_name="setup_episode_start",
            description="First day of each bearish setup-zone episode, treated as a watchlist alert state.",
        )
    )

    candidate_mask = frame["onchain_dominance_support"].fillna(False)
    candidate_indices = frame.index[candidate_mask].tolist()
    filtered_indices = frame.index[(candidate_mask & frame["setup_zone_best"].fillna(False))].tolist()
    rows.append(
        summarize_rows(
            enrich_watchlist_rows(frame, taxonomy, candidate_indices),
            role_type="context_filter",
            role_name="onchain_dominance_support_alone",
            description="Reference condition alone.",
        )
    )
    rows.append(
        summarize_rows(
            enrich_watchlist_rows(frame, taxonomy, filtered_indices),
            role_type="context_filter",
            role_name="onchain_dominance_support_with_bearish_setup",
            description="Reference condition filtered by the bearish setup zone.",
        )
    )

    regime_indices = frame.index[frame["setup_zone_best"].fillna(False)].tolist()
    outside_indices = frame.index[~frame["setup_zone_best"].fillna(False)].tolist()
    raw_bearish_indices = frame.index[frame["raw_bearish_risk_regime"].fillna(False)].tolist()
    rows.append(
        summarize_rows(
            enrich_watchlist_rows(frame, taxonomy, regime_indices),
            role_type="partial_allocation_regime",
            role_name="setup_zone_active_days",
            description="All daily rows where the bearish setup zone is active.",
        )
    )
    rows.append(
        summarize_rows(
            enrich_watchlist_rows(frame, taxonomy, raw_bearish_indices),
            role_type="partial_allocation_regime",
            role_name="raw_bearish_regime_active_days",
            description="All daily rows with raw bearish_risk_regime active.",
        )
    )
    rows.append(
        summarize_rows(
            enrich_watchlist_rows(frame, taxonomy, outside_indices),
            role_type="partial_allocation_regime",
            role_name="outside_setup_zone_days",
            description="All daily rows outside the setup zone, for regime comparison.",
        )
    )

    return pd.DataFrame(rows)


def render_markdown(summary: pd.DataFrame) -> str:
    watch = summary.loc[summary["role_type"] == "watchlist_state"].iloc[0]
    context = summary.loc[summary["role_type"] == "context_filter"].copy()
    regime = summary.loc[summary["role_type"] == "partial_allocation_regime"].copy()

    base_context = context.loc[context["role_name"] == "onchain_dominance_support_alone"].iloc[0]
    filt_context = context.loc[context["role_name"] == "onchain_dominance_support_with_bearish_setup"].iloc[0]

    setup_regime = regime.loc[regime["role_name"] == "setup_zone_active_days"].iloc[0]
    outside_regime = regime.loc[regime["role_name"] == "outside_setup_zone_days"].iloc[0]

    lines = [
        "# SAFE v4.0 Bearish Branch Role Evaluation",
        "",
        "## Section 1 — Why Direct-Entry Work Is Being Frozen",
        "",
        "- the bearish-contrarian branch is not being treated as a direct-entry candidate in this pass",
        "- prior candle-timing work did not justify promoting it to direct entry logic",
        "- this pass reclassifies the branch by role instead: watchlist state, context filter, or partial-allocation regime",
        "",
        "## Section 2 — Watchlist-State Evaluation",
        "",
        f"- setup-episode alerts analysed: `{int(watch['sample_count'])}`",
        f"- touch +2% within 3d / 5d / 10d: `{watch['touch_up_2pct_3d_rate']:.2%}` / `{watch['touch_up_2pct_5d_rate']:.2%}` / `{watch['touch_up_2pct_10d_rate']:.2%}`",
        f"- median days to next confirmed upswing start: `{watch['median_days_to_next_upswing_start']:.1f}`",
        f"- median days to +2% upside touch within 10d: `{watch['median_days_to_up2_touch_10d']:.1f}`",
        f"- downside before upside: `-1%` `{watch['hit_neg_1pct_before_up2pct_rate']:.2%}` | `-2%` `{watch['hit_neg_2pct_before_up2pct_rate']:.2%}` | `-3%` `{watch['hit_neg_3pct_before_up2pct_rate']:.2%}`",
        "",
        "## Section 3 — Context-Filter Evaluation",
        "",
        "- only one already-known candidate condition had enough honest overlap with this branch to test cleanly: `onchain_dominance_support`",
        f"- `onchain_dominance_support` alone: next up `{base_context['next_up_swing_rate']:.2%}`, ret_10d mean `{base_context['ret_10d_mean']:.2%}`, touch_down_2pct_10d `{base_context['touch_down_2pct_10d_rate']:.2%}`, n=`{int(base_context['sample_count'])}`",
        f"- `onchain_dominance_support` with bearish setup: next up `{filt_context['next_up_swing_rate']:.2%}`, ret_10d mean `{filt_context['ret_10d_mean']:.2%}`, touch_down_2pct_10d `{filt_context['touch_down_2pct_10d_rate']:.2%}`, n=`{int(filt_context['sample_count'])}`",
        "",
        "## Section 4 — Partial-Allocation / Regime Evaluation",
        "",
        f"- setup-zone active days: ret_10d mean `{setup_regime['ret_10d_mean']:.2%}`, upside touch asymmetry `{setup_regime['upside_touch_asymmetry_10d']:.2%}`, excursion asymmetry `{setup_regime['excursion_asymmetry_10d']:.2%}`, n=`{int(setup_regime['sample_count'])}`",
        f"- outside setup zone: ret_10d mean `{outside_regime['ret_10d_mean']:.2%}`, upside touch asymmetry `{outside_regime['upside_touch_asymmetry_10d']:.2%}`, excursion asymmetry `{outside_regime['excursion_asymmetry_10d']:.2%}`, n=`{int(outside_regime['sample_count'])}`",
        "",
        "## Section 5 — Clear Conclusion",
        "",
    ]

    if (
        pd.notna(watch["touch_up_2pct_5d_rate"])
        and watch["touch_up_2pct_5d_rate"] >= 0.50
        and pd.notna(watch["median_days_to_next_upswing_start"])
        and watch["median_days_to_next_upswing_start"] <= 5
    ):
        lines.append("- Watchlist state: yes. The branch is useful as a bullish-reversal watchlist alert state.")
    else:
        lines.append("- Watchlist state: weak. The branch does not bring reversal quickly enough to justify close monitoring on its own.")

    if (
        pd.notna(filt_context["next_up_swing_rate"])
        and pd.notna(base_context["next_up_swing_rate"])
        and filt_context["next_up_swing_rate"] > base_context["next_up_swing_rate"]
        and filt_context["sample_count"] >= 10
    ):
        lines.append("- Context filter: modestly yes. It can improve at least one overlapping candidate condition.")
    else:
        lines.append("- Context filter: limited. Honest overlap with other candidate conditions is sparse, so this is not its main role.")

    if (
        pd.notna(setup_regime["ret_10d_mean"])
        and pd.notna(outside_regime["ret_10d_mean"])
        and setup_regime["ret_10d_mean"] > outside_regime["ret_10d_mean"]
        and pd.notna(setup_regime["upside_touch_asymmetry_10d"])
        and setup_regime["upside_touch_asymmetry_10d"] > outside_regime["upside_touch_asymmetry_10d"]
    ):
        lines.append("- Partial-allocation regime: plausible. The branch looks more useful as a reduced-risk / non-zero-bias regime than as a direct trigger.")
    else:
        lines.append("- Partial-allocation regime: not clearly supported yet. The state still looks too path-painful to promote beyond watchlist use.")

    lines.append("- Operationally, this branch should now be treated primarily as a setup-zone / watchlist state, with only secondary context-filter value.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    dataset, taxonomy = load_dataset(args)
    summary = build_role_rows(dataset, taxonomy)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(summary), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(summary)}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
