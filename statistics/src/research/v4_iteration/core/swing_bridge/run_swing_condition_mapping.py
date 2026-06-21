from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    OUT_DIR,
    STATISTICS_DIR,
)
from src.foundation.swing_common import (
    SWING_ATR_WINDOW,
    SWING_GRANULARITY_LABEL,
    SWING_REVERSAL_K,
    build_selected_conditions,
    compute_swing_taxonomy,
    load_feature_onchain_dataset,
    map_dates_to_containing_swings,
    map_dates_to_next_swings,
)
from src.foundation.swing_detection import detect_swings
from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_PRICE_JSON_PATH


DEFAULT_LIVE_SWING_STATE_CSV_PATH = OUT_DIR / "swing_bridge" / "live_swing_state.csv"
DEFAULT_SWING_TAXONOMY_CSV_PATH = OUT_DIR / "swing_bridge" / "swing_taxonomy.csv"
DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH = OUT_DIR / "swing_bridge" / "swing_condition_mapping.csv"
DEFAULT_SWING_CONDITION_MAPPING_MD_PATH = STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_SWING_CONDITION_MAPPING.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map selected SAFE conditions to future market-defined swing outcomes.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument(
        "--onchain-features-csv",
        default=str(DEFAULT_ONCHAIN_FEATURES_CSV_PATH),
        help="Default: ../out/onchain_features.csv",
    )
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
        "--out-csv",
        default=str(DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH),
        help="Default: ../out/swing_bridge/swing_condition_mapping.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SWING_CONDITION_MAPPING_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_SWING_CONDITION_MAPPING.md",
    )
    return parser.parse_args()


def ensure_supporting_outputs(price_json: str, live_swing_state_csv: Path, swing_taxonomy_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if live_swing_state_csv.exists():
        live_state = load_feature_csv(live_swing_state_csv)
    else:
        from src.foundation.live_swing_state import build_live_swing_state

        live_state = build_live_swing_state(load_daily_price_json(price_json))

    if swing_taxonomy_csv.exists():
        taxonomy = pd.read_csv(swing_taxonomy_csv)
        taxonomy["start_date"] = pd.to_datetime(taxonomy["start_date"])
        taxonomy["end_date"] = pd.to_datetime(taxonomy["end_date"])
    else:
        price = load_daily_price_json(price_json)
        swings, _ = detect_swings(price, reversal_k=SWING_REVERSAL_K, atr_window=SWING_ATR_WINDOW)
        taxonomy, _ = compute_swing_taxonomy(swings)

    return live_state, taxonomy


def build_mapping_dataset(args: argparse.Namespace) -> pd.DataFrame:
    base = load_feature_onchain_dataset(args.features_csv, args.onchain_features_csv)
    live_state, taxonomy = ensure_supporting_outputs(
        args.price_json,
        Path(args.live_swing_state_csv),
        Path(args.swing_taxonomy_csv),
    )
    if "date" not in live_state.columns:
        live_state = live_state.reset_index().rename(columns={live_state.index.name or "index": "date"})
    live_state = live_state.drop(columns=[column for column in ("atr_pct", "swing_granularity") if column in live_state.columns])
    containing_swings = map_dates_to_containing_swings(base["date"], taxonomy)
    if "date" not in containing_swings.columns:
        containing_swings = containing_swings.reset_index().rename(columns={containing_swings.index.name or "index": "date"})
    next_swings = map_dates_to_next_swings(base["date"], taxonomy)
    if "date" not in next_swings.columns:
        next_swings = next_swings.reset_index().rename(columns={next_swings.index.name or "index": "date"})

    merged = (
        base.merge(live_state, on="date", how="left", validate="one_to_one")
        .merge(containing_swings, on="date", how="left", validate="one_to_one")
        .merge(next_swings, on="date", how="left", validate="one_to_one")
        .sort_values("date")
        .reset_index(drop=True)
    )
    return merged


def summarize_condition(
    frame: pd.DataFrame,
    name: str,
    family: str,
    description: str,
    mask: pd.Series,
    mapping_mode: str,
) -> dict[str, object]:
    subset = frame.loc[mask].copy()
    if mapping_mode == "containing":
        prefix = "containing_swing_"
    elif mapping_mode == "next":
        prefix = "next_swing_"
    else:
        raise ValueError(f"Unsupported mapping_mode: {mapping_mode}")

    mapped = subset.dropna(subset=[f"{prefix}direction"]).copy()

    up_subset = mapped.loc[mapped[f"{prefix}direction"] == "up"]
    down_subset = mapped.loc[mapped[f"{prefix}direction"] == "down"]

    def rate(series: pd.Series, value: str) -> float:
        if series.empty:
            return float("nan")
        return float((series == value).mean())

    row: dict[str, object] = {
        "condition_name": name,
        "condition_family": family,
        "rule_definition": description,
        "mapping_mode": mapping_mode,
        "sample_count": int(mask.sum()),
        "mapped_swing_rows": int(len(mapped)),
        "swing_up_rate": rate(mapped[f"{prefix}direction"], "up"),
        "swing_down_rate": rate(mapped[f"{prefix}direction"], "down"),
        "median_swing_abs_amplitude": float(mapped[f"{prefix}abs_amplitude"].median()) if not mapped.empty else np.nan,
        "median_swing_duration_days": float(mapped[f"{prefix}duration_days"].median()) if not mapped.empty else np.nan,
        "small_swing_rate": rate(mapped[f"{prefix}size_class"], "small"),
        "medium_swing_rate": rate(mapped[f"{prefix}size_class"], "medium"),
        "large_swing_rate": rate(mapped[f"{prefix}size_class"], "large"),
        "short_swing_rate": rate(mapped[f"{prefix}duration_class"], "short"),
        "medium_duration_rate": rate(mapped[f"{prefix}duration_class"], "medium"),
        "long_swing_rate": rate(mapped[f"{prefix}duration_class"], "long"),
        "up_early_stage_rate": np.nan,
        "up_mid_stage_rate": np.nan,
        "up_late_stage_rate": np.nan,
        "down_early_stage_rate": np.nan,
        "down_mid_stage_rate": np.nan,
        "down_late_stage_rate": np.nan,
        "live_up_rate": rate(subset["live_swing_direction"], "up"),
        "live_down_rate": rate(subset["live_swing_direction"], "down"),
        "live_unknown_rate": rate(subset["live_swing_direction"], "unknown"),
    }
    if mapping_mode == "containing":
        row.update(
            {
                "up_early_stage_rate": rate(up_subset["containing_swing_stage_bucket"], "early"),
                "up_mid_stage_rate": rate(up_subset["containing_swing_stage_bucket"], "mid"),
                "up_late_stage_rate": rate(up_subset["containing_swing_stage_bucket"], "late"),
                "down_early_stage_rate": rate(down_subset["containing_swing_stage_bucket"], "early"),
                "down_mid_stage_rate": rate(down_subset["containing_swing_stage_bucket"], "mid"),
                "down_late_stage_rate": rate(down_subset["containing_swing_stage_bucket"], "late"),
            }
        )
    return row


def build_mapping_table(frame: pd.DataFrame) -> pd.DataFrame:
    conditions = build_selected_conditions(frame)
    rows = []
    for condition in conditions:
        mask = condition.builder(frame).fillna(False)
        for mapping_mode in ("containing", "next"):
            rows.append(
                summarize_condition(
                    frame,
                    condition.name,
                    condition.family,
                    condition.description,
                    mask,
                    mapping_mode,
                )
            )
    table = pd.DataFrame(rows)
    table = table.sort_values(["mapping_mode", "swing_up_rate", "mapped_swing_rows"], ascending=[True, False, False]).reset_index(drop=True)
    return table


def _top(frame: pd.DataFrame, column: str, minimum_rows: int = 25, ascending: bool = False, limit: int = 5) -> pd.DataFrame:
    usable = frame.loc[frame["mapped_swing_rows"] >= minimum_rows].dropna(subset=[column]).copy()
    return usable.sort_values(column, ascending=ascending).head(limit)


def render_markdown(mapping: pd.DataFrame) -> str:
    containing = mapping.loc[mapping["mapping_mode"] == "containing"].copy()
    next_map = mapping.loc[mapping["mapping_mode"] == "next"].copy()

    strongest_next_up = _top(next_map, "swing_up_rate", ascending=False)
    strongest_next_down = _top(next_map, "swing_down_rate", ascending=False)
    early_up = _top(containing, "up_early_stage_rate", ascending=False)
    mid_up = _top(containing, "up_mid_stage_rate", ascending=False)
    late_up = _top(containing, "up_late_stage_rate", ascending=False)
    large_move = _top(next_map, "large_swing_rate", ascending=False)

    lines = [
        "# SAFE v4.0 Swing Condition Mapping",
        "",
        f"Chosen swing granularity: `{SWING_GRANULARITY_LABEL}`",
        f"- ATR window: `{SWING_ATR_WINDOW}`",
        f"- reversal multiplier: `{SWING_REVERSAL_K:.2f}`",
        "",
        "This report separates two different swing-mapping questions:",
        "",
        "- `containing` mapping: which confirmed swing currently contains the date",
        "- `next` mapping: which confirmed swing starts strictly after the date",
        "",
        "Why the split matters:",
        "- containing-swing analysis is descriptive of current swing maturity",
        "- next-swing analysis is the predictive bridge to what swing comes next",
        "",
        "## Containing-Swing Analysis",
        "",
        "These rows describe where a condition tends to appear inside the swing that currently contains the date.",
        "",
        "### Which Conditions Align With Early Up-Swing Stages?",
        "",
    ]
    for _, row in early_up.iterrows():
        lines.append(
            f"- `{row['condition_name']}`: early-in-up rate `{row['up_early_stage_rate']:.2%}`, "
            f"current up-swing rate `{row['swing_up_rate']:.2%}`, "
            f"n=`{int(row['mapped_swing_rows'])}`"
        )

    lines.extend(["", "### Which Conditions Align With Mid Up-Swing Stages?", ""])
    for _, row in mid_up.iterrows():
        lines.append(
            f"- `{row['condition_name']}`: mid-in-up rate `{row['up_mid_stage_rate']:.2%}`, "
            f"current up-swing rate `{row['swing_up_rate']:.2%}`, n=`{int(row['mapped_swing_rows'])}`"
        )

    lines.extend(["", "### Which Conditions Align With Late Up-Swing Stages?", ""])
    for _, row in late_up.iterrows():
        lines.append(
            f"- `{row['condition_name']}`: late-in-up rate `{row['up_late_stage_rate']:.2%}`, "
            f"current up-swing rate `{row['swing_up_rate']:.2%}`, n=`{int(row['mapped_swing_rows'])}`"
        )

    lines.extend(["", "## Next-Swing Analysis", ""])
    lines.extend(["", "These rows ask what confirmed swing most often starts after a date where the condition is active.", ""])
    lines.extend(["", "### Which Conditions Most Often Precede The Next Upward Swing?", ""])
    for _, row in strongest_next_up.iterrows():
        lines.append(
            f"- `{row['condition_name']}`: next up-swing rate `{row['swing_up_rate']:.2%}`, "
            f"median amplitude `{row['median_swing_abs_amplitude']:.2%}`, "
            f"median duration `{int(row['median_swing_duration_days'])}`d, "
            f"n=`{int(row['mapped_swing_rows'])}`"
        )

    lines.extend(["", "### Which Conditions Most Often Precede The Next Downward Swing?", ""])
    for _, row in strongest_next_down.iterrows():
        lines.append(
            f"- `{row['condition_name']}`: next down-swing rate `{row['swing_down_rate']:.2%}`, "
            f"median amplitude `{row['median_swing_abs_amplitude']:.2%}`, "
            f"median duration `{int(row['median_swing_duration_days'])}`d, "
            f"n=`{int(row['mapped_swing_rows'])}`"
        )

    lines.extend(["", "### Which Conditions Mainly Describe Current Swing Maturity Rather Than Predict The Next Swing?", ""])
    comparison = containing.merge(
        next_map[["condition_name", "mapped_swing_rows", "swing_up_rate", "swing_down_rate", "large_swing_rate"]],
        on="condition_name",
        how="inner",
        suffixes=("_containing", "_next"),
    )
    ambiguous = comparison.loc[
        (comparison["mapped_swing_rows_containing"] >= 25) & (comparison["mapped_swing_rows_next"] >= 25)
    ].copy()
    ambiguous["maturity_gap"] = (
        ambiguous[["up_early_stage_rate", "up_mid_stage_rate", "up_late_stage_rate"]].max(axis=1)
        - (ambiguous["swing_up_rate_next"] - ambiguous["swing_down_rate_next"]).abs()
    )
    ambiguous = ambiguous.sort_values("maturity_gap", ascending=False).head(5)
    for _, row in ambiguous.iterrows():
        dominant_stage = max(
            (
                ("early", row["up_early_stage_rate"]),
                ("mid", row["up_mid_stage_rate"]),
                ("late", row["up_late_stage_rate"]),
            ),
            key=lambda item: (np.nan_to_num(item[1], nan=-1.0), item[0]),
        )[0]
        lines.append(
            f"- `{row['condition_name']}`: strongest containing up-stage signal is `{dominant_stage}`, "
            f"but next-swing direction gap is only "
            f"{abs(row['swing_up_rate_next'] - row['swing_down_rate_next']):.2%}, "
            f"n=`{int(row['mapped_swing_rows_next'])}`"
        )

    lines.extend(["", "### Which Conditions Mostly Describe Movement Without Directional Clarity?", ""])
    ambiguous = next_map.loc[next_map["mapped_swing_rows"] >= 25].copy()
    ambiguous["direction_gap"] = (ambiguous["swing_up_rate"] - ambiguous["swing_down_rate"]).abs()
    ambiguous = ambiguous.sort_values(["direction_gap", "large_swing_rate"], ascending=[True, False]).head(5)
    for _, row in ambiguous.iterrows():
        lines.append(
            f"- `{row['condition_name']}`: next up `{row['swing_up_rate']:.2%}`, next down `{row['swing_down_rate']:.2%}`, "
            f"large swing rate `{row['large_swing_rate']:.2%}`, n=`{int(row['mapped_swing_rows'])}`"
        )

    lines.extend(["", "## Large-Swing Alignment", ""])
    for _, row in large_move.iterrows():
        lines.append(
            f"- `{row['condition_name']}`: next large-swing rate `{row['large_swing_rate']:.2%}`, "
            f"up `{row['swing_up_rate']:.2%}`, down `{row['swing_down_rate']:.2%}`, n=`{int(row['mapped_swing_rows'])}`"
        )

    lines.extend(
        [
            "",
            "## What This Bridge Says",
            "",
            "- containing-swing and next-swing results must be read separately",
            "- some conditions are mainly descriptive of current swing maturity",
            "- some conditions align cleanly with next-swing direction",
            "- others mainly describe movement intensity or fragile regimes without clear next-swing direction",
            "- this is the first bridge layer from indicator conditions to market-defined swings, not a final trading rule set",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    dataset = build_mapping_dataset(args)
    mapping = build_mapping_table(dataset)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(mapping), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(mapping)}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
