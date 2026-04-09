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

from src.data.feature_store import load_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    OUT_DIR,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bridge.run_live_swing_state import build_live_swing_state
from src.research.v4_iteration.core.swing_bridge.swing_bridge_common import (
    SWING_ATR_WINDOW,
    SWING_GRANULARITY_LABEL,
    SWING_REVERSAL_K,
    build_selected_conditions,
    compute_swing_taxonomy,
    load_feature_onchain_dataset,
    map_dates_to_next_swings,
)
from src.research.v4_iteration.core.swing_detection.run_swing_detection import detect_swings


DEFAULT_LIVE_SWING_STATE_CSV_PATH = OUT_DIR / "swing_bridge" / "live_swing_state.csv"
DEFAULT_SWING_TAXONOMY_CSV_PATH = OUT_DIR / "swing_bridge" / "swing_taxonomy.csv"
DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH = OUT_DIR / "swing_bridge" / "swing_condition_mapping.csv"
DEFAULT_ENTRY_LOGIC_RESEARCH_CSV_PATH = OUT_DIR / "swing_bridge" / "entry_logic_research.csv"
DEFAULT_ENTRY_LOGIC_RESEARCH_MD_PATH = STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_ENTRY_LOGIC_RESEARCH.md"

WARNING_CONDITIONS: tuple[str, ...] = (
    "extended_noisy_chase",
    "rebound_skew_low_shock",
    "upside_probability_stack",
)
RAW_UP_PRECURSORS: tuple[str, ...] = (
    "low_risk_pullback",
    "shock_whale_risk",
    "bearish_risk_regime",
)


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    family: str
    description: str
    builder: callable
    comparison_to: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test small research-stage long-entry templates by combining next-swing precursors with live swing state.",
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
        default=str(DEFAULT_ENTRY_LOGIC_RESEARCH_CSV_PATH),
        help="Default: ../out/swing_bridge/entry_logic_research.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_ENTRY_LOGIC_RESEARCH_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_ENTRY_LOGIC_RESEARCH.md",
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


def ensure_supporting_outputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    live_swing_state_csv = Path(args.live_swing_state_csv)
    if live_swing_state_csv.exists():
        live_state = _validate_date_frame("live_swing_state", load_feature_csv(live_swing_state_csv))
    else:
        live_state = build_live_swing_state(load_daily_price_json(args.price_json)).reset_index().rename(columns={"index": "date"})
        live_state = _validate_date_frame("live_swing_state", live_state)

    swing_taxonomy_csv = Path(args.swing_taxonomy_csv)
    if swing_taxonomy_csv.exists():
        taxonomy = pd.read_csv(swing_taxonomy_csv)
    else:
        price = load_daily_price_json(args.price_json)
        swings, _ = detect_swings(price, reversal_k=SWING_REVERSAL_K, atr_window=SWING_ATR_WINDOW)
        taxonomy, _ = compute_swing_taxonomy(swings)
    taxonomy["start_date"] = pd.to_datetime(taxonomy["start_date"], errors="raise")
    taxonomy["end_date"] = pd.to_datetime(taxonomy["end_date"], errors="raise")
    return live_state, taxonomy


def build_dataset(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = _validate_date_frame(
        "feature_onchain",
        load_feature_onchain_dataset(args.features_csv, args.onchain_features_csv),
    )
    targets = _validate_date_frame("targets", load_feature_csv(args.targets_csv))
    live_state, taxonomy = ensure_supporting_outputs(args)
    next_swings = map_dates_to_next_swings(base["date"], taxonomy)
    next_swings = _validate_date_frame("next_swings", next_swings)

    if Path(args.swing_condition_mapping_csv).exists():
        condition_mapping = pd.read_csv(args.swing_condition_mapping_csv)
    else:
        condition_mapping = pd.DataFrame()

    live_state = live_state.drop(columns=[column for column in ("atr_pct", "swing_granularity") if column in live_state.columns])
    merged = (
        base.merge(targets, on="date", how="inner", validate="one_to_one")
        .merge(live_state, on="date", how="left", validate="one_to_one")
        .merge(next_swings, on="date", how="left", validate="one_to_one")
        .sort_values("date")
        .reset_index(drop=True)
    )
    return merged, condition_mapping


def build_condition_masks(frame: pd.DataFrame, condition_mapping: pd.DataFrame) -> dict[str, pd.Series]:
    specs = build_selected_conditions(frame)
    masks = {spec.name: spec.builder(frame).fillna(False) for spec in specs}

    required = set(RAW_UP_PRECURSORS) | set(WARNING_CONDITIONS)
    missing = [name for name in sorted(required) if name not in masks]
    if missing:
        raise ValueError(f"Missing required interaction conditions: {missing}")

    if not condition_mapping.empty and "condition_name" in condition_mapping.columns:
        available = set(condition_mapping["condition_name"].dropna().astype(str))
        missing_from_mapping = [name for name in sorted(required) if name not in available]
        if missing_from_mapping:
            raise ValueError(f"Conditions missing from swing_condition_mapping.csv: {missing_from_mapping}")
    return masks


def add_live_flags(frame: pd.DataFrame, masks: dict[str, pd.Series]) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["warning_active"] = pd.Series(False, index=enriched.index)
    for name in WARNING_CONDITIONS:
        enriched["warning_active"] = enriched["warning_active"] | masks[name]

    live_direction = enriched["live_swing_direction"].astype("string")
    age = pd.to_numeric(enriched["current_swing_age_pct_of_median"], errors="coerce")
    size = pd.to_numeric(enriched["current_swing_size_pct_of_median"], errors="coerce")

    enriched["live_reversal_window"] = live_direction.isin(["down", "unknown"])
    enriched["live_early"] = age <= 0.50
    enriched["live_early_mid"] = age <= 0.75
    enriched["live_not_late"] = age <= 1.00
    enriched["live_small"] = size <= 0.75
    enriched["live_not_extended"] = size <= 1.00
    return enriched


def build_templates() -> tuple[TemplateSpec, ...]:
    return (
        TemplateSpec(
            name="entry_pullback_reversal_window",
            family="filtered_entry",
            description=(
                "low_risk_pullback active, live leg in reversal window (down/unknown), "
                "age <= 0.50 median swing, size <= 0.75 median swing, no strong next-down warning."
            ),
            builder=lambda df, masks: masks["low_risk_pullback"]
            & df["live_reversal_window"]
            & df["live_early"]
            & df["live_small"]
            & (~df["warning_active"]),
            comparison_to="low_risk_pullback",
        ),
        TemplateSpec(
            name="entry_stress_rebound_reversal_window",
            family="filtered_entry",
            description=(
                "shock_whale_risk active, live leg in reversal window (down/unknown), "
                "age <= 0.75 median swing, size <= 1.00 median swing, no strong next-down warning."
            ),
            builder=lambda df, masks: masks["shock_whale_risk"]
            & df["live_reversal_window"]
            & df["live_early_mid"]
            & df["live_not_extended"]
            & (~df["warning_active"]),
            comparison_to="shock_whale_risk",
        ),
        TemplateSpec(
            name="entry_bearish_contrarian_not_late",
            family="filtered_entry",
            description=(
                "bearish_risk_regime active, live leg in reversal window (down/unknown), "
                "age <= 1.00 median swing, size <= 1.00 median swing, no strong next-down warning."
            ),
            builder=lambda df, masks: masks["bearish_risk_regime"]
            & df["live_reversal_window"]
            & df["live_not_late"]
            & df["live_not_extended"]
            & (~df["warning_active"]),
            comparison_to="bearish_risk_regime",
        ),
        TemplateSpec(
            name="low_risk_pullback",
            family="raw_reference",
            description="Raw precursor reference.",
            builder=lambda df, masks: masks["low_risk_pullback"],
        ),
        TemplateSpec(
            name="shock_whale_risk",
            family="raw_reference",
            description="Raw precursor reference.",
            builder=lambda df, masks: masks["shock_whale_risk"],
        ),
        TemplateSpec(
            name="bearish_risk_regime",
            family="raw_reference",
            description="Raw precursor reference.",
            builder=lambda df, masks: masks["bearish_risk_regime"],
        ),
        TemplateSpec(
            name="extended_noisy_chase",
            family="warning_reference",
            description="Raw warning reference.",
            builder=lambda df, masks: masks["extended_noisy_chase"],
        ),
        TemplateSpec(
            name="rebound_skew_low_shock",
            family="warning_reference",
            description="Raw warning reference.",
            builder=lambda df, masks: masks["rebound_skew_low_shock"],
        ),
        TemplateSpec(
            name="upside_probability_stack",
            family="warning_reference",
            description="Raw warning reference.",
            builder=lambda df, masks: masks["upside_probability_stack"],
        ),
    )


def _rate(series: pd.Series, value: str) -> float:
    if series.empty:
        return float("nan")
    return float((series == value).mean())


def _mean(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else np.nan


def _median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else np.nan


def summarize_template(
    frame: pd.DataFrame,
    name: str,
    family: str,
    description: str,
    mask: pd.Series,
    comparison_to: str | None,
) -> dict[str, object]:
    subset = frame.loc[mask].copy()
    next_swing = subset.dropna(subset=["next_swing_direction"]).copy()

    row: dict[str, object] = {
        "template_name": name,
        "template_family": family,
        "rule_definition": description,
        "comparison_to": comparison_to,
        "sample_count": int(mask.sum()),
        "next_swing_rows": int(len(next_swing)),
        "next_up_swing_rate": _rate(next_swing["next_swing_direction"], "up"),
        "next_down_swing_rate": _rate(next_swing["next_swing_direction"], "down"),
        "median_next_swing_abs_amplitude": _median(next_swing["next_swing_abs_amplitude"]),
        "median_next_swing_duration_days": _median(next_swing["next_swing_duration_days"]),
        "next_small_swing_rate": _rate(next_swing["next_swing_size_class"], "small"),
        "next_medium_swing_rate": _rate(next_swing["next_swing_size_class"], "medium"),
        "next_large_swing_rate": _rate(next_swing["next_swing_size_class"], "large"),
        "next_short_swing_rate": _rate(next_swing["next_swing_duration_class"], "short"),
        "next_medium_duration_rate": _rate(next_swing["next_swing_duration_class"], "medium"),
        "next_long_swing_rate": _rate(next_swing["next_swing_duration_class"], "long"),
        "ret_10d_mean": _mean(subset["ret_10d"]),
        "ret_10d_median": _median(subset["ret_10d"]),
        "ret_10d_win_rate": float((pd.to_numeric(subset["ret_10d"], errors="coerce") > 0).mean()) if subset["ret_10d"].notna().any() else np.nan,
        "max_up_10d_mean": _mean(subset["max_up_10d"]),
        "max_up_10d_median": _median(subset["max_up_10d"]),
        "max_down_10d_mean": _mean(subset["max_down_10d"]),
        "max_down_10d_median": _median(subset["max_down_10d"]),
        "touch_up_2pct_10d_rate": _mean(subset["touch_up_2pct_10d"]),
        "touch_down_2pct_10d_rate": _mean(subset["touch_down_2pct_10d"]),
        "live_up_rate": _rate(subset["live_swing_direction"].astype("string"), "up"),
        "live_down_rate": _rate(subset["live_swing_direction"].astype("string"), "down"),
        "live_unknown_rate": _rate(subset["live_swing_direction"].astype("string"), "unknown"),
        "median_live_age_pct_of_median": _median(subset["current_swing_age_pct_of_median"]),
        "median_live_size_pct_of_median": _median(subset["current_swing_size_pct_of_median"]),
    }
    return row


def build_results(frame: pd.DataFrame, masks: dict[str, pd.Series]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for template in build_templates():
        mask = template.builder(frame, masks).fillna(False)
        rows.append(
            summarize_template(
                frame,
                template.name,
                template.family,
                template.description,
                mask,
                template.comparison_to,
            )
        )
    return pd.DataFrame(rows).sort_values(["template_family", "next_up_swing_rate"], ascending=[True, False]).reset_index(drop=True)


def _best(rows: pd.DataFrame, family: str, column: str, ascending: bool = False, limit: int = 3) -> pd.DataFrame:
    subset = rows.loc[(rows["template_family"] == family) & (rows["next_swing_rows"] >= 20)].dropna(subset=[column]).copy()
    return subset.sort_values(column, ascending=ascending).head(limit)


def build_comparison_table(results: pd.DataFrame) -> pd.DataFrame:
    raw = results.loc[results["template_family"] == "raw_reference"].set_index("template_name")
    filtered = results.loc[results["template_family"] == "filtered_entry"].copy()
    rows: list[dict[str, object]] = []
    for _, row in filtered.iterrows():
        raw_name = row["comparison_to"]
        if raw_name not in raw.index:
            continue
        raw_row = raw.loc[raw_name]
        rows.append(
            {
                "template_name": row["template_name"],
                "raw_reference": raw_name,
                "delta_next_up_swing_rate": float(row["next_up_swing_rate"] - raw_row["next_up_swing_rate"]),
                "delta_next_down_swing_rate": float(row["next_down_swing_rate"] - raw_row["next_down_swing_rate"]),
                "delta_ret_10d_mean": float(row["ret_10d_mean"] - raw_row["ret_10d_mean"]),
                "delta_touch_up_2pct_10d_rate": float(row["touch_up_2pct_10d_rate"] - raw_row["touch_up_2pct_10d_rate"]),
                "delta_touch_down_2pct_10d_rate": float(row["touch_down_2pct_10d_rate"] - raw_row["touch_down_2pct_10d_rate"]),
                "sample_count_filtered": int(row["sample_count"]),
                "sample_count_raw": int(raw_row["sample_count"]),
            }
        )
    return pd.DataFrame(rows)


def render_markdown(results: pd.DataFrame, comparisons: pd.DataFrame) -> str:
    filtered_best = _best(results, "filtered_entry", "next_up_swing_rate")
    warning_worst = _best(results, "warning_reference", "next_down_swing_rate")
    filtered = results.loc[results["template_family"] == "filtered_entry"].copy()
    lines = [
        "# SAFE v4.0 Entry Logic Research",
        "",
        f"Chosen swing granularity: `{SWING_GRANULARITY_LABEL}`",
        f"- ATR window: `{SWING_ATR_WINDOW}`",
        f"- reversal multiplier: `{SWING_REVERSAL_K:.2f}`",
        "",
        "This is a small research-stage entry pass. It does not define a full strategy or any exits.",
        "",
        "Important alignment rule:",
        "- this pass uses strict `next swing` semantics",
        "- because of that, long-entry templates are filtered toward live legs that are still in a reversal window (`down` or `unknown`), not already-established upswings",
        "",
        "## Section 1 — Tested Entry Templates",
        "",
    ]
    for _, row in results.iterrows():
        lines.append(
            f"- `{row['template_name']}` ({row['template_family']}): "
            f"next up `{row['next_up_swing_rate']:.2%}` | next down `{row['next_down_swing_rate']:.2%}` | "
            f"ret_10d mean `{row['ret_10d_mean']:.2%}` | n=`{int(row['sample_count'])}`"
        )

    lines.extend(["", "## Section 2 — Raw Precursor vs Filtered Entry-Template Comparison", ""])
    if comparisons.empty:
        lines.append("- No filtered-vs-raw comparisons were available.")
    else:
        for _, row in comparisons.iterrows():
            lines.append(
                f"- `{row['template_name']}` vs `{row['raw_reference']}`: "
                f"delta next-up `{row['delta_next_up_swing_rate']:+.2%}`, "
                f"delta next-down `{row['delta_next_down_swing_rate']:+.2%}`, "
                f"delta ret_10d mean `{row['delta_ret_10d_mean']:+.2%}`, "
                f"delta touch_up_2pct_10d `{row['delta_touch_up_2pct_10d_rate']:+.2%}`, "
                f"delta touch_down_2pct_10d `{row['delta_touch_down_2pct_10d_rate']:+.2%}`"
            )

    lines.extend(["", "## Section 3 — Best Long-Entry Research Candidates", ""])
    for _, row in filtered_best.iterrows():
        lines.append(
            f"- `{row['template_name']}`: next up `{row['next_up_swing_rate']:.2%}`, "
            f"next down `{row['next_down_swing_rate']:.2%}`, "
            f"median next swing amplitude `{row['median_next_swing_abs_amplitude']:.2%}`, "
            f"ret_10d mean `{row['ret_10d_mean']:.2%}`, n=`{int(row['sample_count'])}`"
        )

    lines.extend(["", "## Section 4 — Which Warning States Should Veto Long Entries", ""])
    for _, row in warning_worst.iterrows():
        lines.append(
            f"- `{row['template_name']}`: next down `{row['next_down_swing_rate']:.2%}`, "
            f"touch_down_2pct_10d `{row['touch_down_2pct_10d_rate']:.2%}`, "
            f"ret_10d mean `{row['ret_10d_mean']:.2%}`, n=`{int(row['sample_count'])}`"
        )
    lines.extend(
        [
            "",
            "Interpretation note:",
            "- a strong `next down` warning can still show positive `ret_10d` if the current live leg keeps rising before the next confirmed downswing begins",
            "- that is why next-swing direction and fixed-horizon return should be read together, not treated as interchangeable",
        ]
    )

    lines.extend(
        [
            "",
            "## Section 5 — Clear Conclusion",
            "",
            "- the relevant question is not whether a precursor is good alone, but whether it improves after live swing phase filtering",
        ]
    )
    if not comparisons.empty:
        for _, row in comparisons.iterrows():
            if row["sample_count_filtered"] == 0:
                lines.append(
                    f"- `{row['template_name']}` should be discarded in its current form: the filter stack produced no usable rows."
                )
                continue
            if row["sample_count_filtered"] < 10:
                lines.append(
                    f"- `{row['template_name']}` is too sparse to trust yet: it improved next-up alignment by "
                    f"`{row['delta_next_up_swing_rate']:+.2%}` but only on `{int(row['sample_count_filtered'])}` rows."
                )
                continue
            if row["delta_next_up_swing_rate"] > 0 and row["delta_next_down_swing_rate"] < 0:
                lines.append(
                    f"- `{row['template_name']}` deserves next-step refinement: it improved next-up alignment by "
                    f"`{row['delta_next_up_swing_rate']:+.2%}` while reducing next-down leakage by "
                    f"`{abs(row['delta_next_down_swing_rate']):.2%}`."
                )
            else:
                lines.append(
                    f"- `{row['template_name']}` should be challenged before reuse: live swing filtering did not produce a clearly better next-swing profile."
                )
    lines.extend(
        [
            "- warning states remain useful as long-entry vetoes when they preserve high next-down alignment after the live-state split",
            "- this pass supports further refinement of a small entry layer, not a full strategy or execution rule set",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    dataset, condition_mapping = build_dataset(args)
    masks = build_condition_masks(dataset, condition_mapping)
    dataset = add_live_flags(dataset, masks)
    results = build_results(dataset, masks)
    comparisons = build_comparison_table(results)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(results, comparisons), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(results)}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
