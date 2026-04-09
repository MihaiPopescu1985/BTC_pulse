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

from src.path_config import OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.research_active.run_entry_logic_research import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    WARNING_CONDITIONS,
    add_live_flags,
    build_condition_masks,
    build_dataset,
    summarize_template,
)


DEFAULT_ENTRY_LOGIC_BEARISH_REFINEMENT_CSV_PATH = OUT_DIR / "swing_bridge" / "entry_logic_bearish_refinement.csv"
DEFAULT_ENTRY_LOGIC_BEARISH_REFINEMENT_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_ENTRY_LOGIC_BEARISH_REFINEMENT.md"
)

AGE_OPTIONS: tuple[float, ...] = (0.50, 0.75, 1.00)
SIZE_OPTIONS: tuple[float, ...] = (0.75, 1.00, 1.25)


@dataclass(frozen=True)
class VariantSpec:
    variant_name: str
    age_limit: float
    size_limit: float
    use_warning_veto: bool
    confirmation_name: str
    confirmation_description: str
    builder: callable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a narrow refinement pass around the bearish contrarian swing-entry branch.",
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
        default=str(DEFAULT_ENTRY_LOGIC_BEARISH_REFINEMENT_CSV_PATH),
        help="Default: ../out/swing_bridge/entry_logic_bearish_refinement.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_ENTRY_LOGIC_BEARISH_REFINEMENT_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_ENTRY_LOGIC_BEARISH_REFINEMENT.md",
    )
    return parser.parse_args()


def add_refinement_flags(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    age = pd.to_numeric(enriched["current_swing_age_pct_of_median"], errors="coerce")
    size = pd.to_numeric(enriched["current_swing_size_pct_of_median"], errors="coerce")

    for age_limit in AGE_OPTIONS:
        enriched[f"age_lte_{str(age_limit).replace('.', '_')}"] = age <= age_limit
    for size_limit in SIZE_OPTIONS:
        enriched[f"size_lte_{str(size_limit).replace('.', '_')}"] = size <= size_limit

    onchain_dom = pd.to_numeric(enriched["ONCHAIN_DOM_Z"], errors="coerce")
    rebound = pd.to_numeric(enriched["P_REBOUND_10D_CAL"], errors="coerce")
    ts20 = pd.to_numeric(enriched["TS_20"], errors="coerce")
    er50 = pd.to_numeric(enriched["ER_50"], errors="coerce")

    enriched["confirm_none"] = True
    enriched["confirm_onchain_dom_supportive"] = onchain_dom >= onchain_dom.median()
    enriched["confirm_rebound_upper_half"] = rebound >= rebound.median()
    enriched["confirm_ts20_not_strongly_negative"] = ts20 >= ts20.quantile(0.25)
    enriched["confirm_er50_not_weak"] = er50 >= er50.median()
    return enriched


def build_variant_specs() -> list[VariantSpec]:
    variants: list[VariantSpec] = []

    for age_limit in AGE_OPTIONS:
        for size_limit in SIZE_OPTIONS:
            age_key = str(age_limit).replace(".", "_")
            size_key = str(size_limit).replace(".", "_")
            for use_warning_veto in (True, False):
                veto_label = "with_veto" if use_warning_veto else "no_veto"
                variants.append(
                    VariantSpec(
                        variant_name=f"bearish_age{age_key}_size{size_key}_{veto_label}",
                        age_limit=age_limit,
                        size_limit=size_limit,
                        use_warning_veto=use_warning_veto,
                        confirmation_name="none",
                        confirmation_description="No extra confirmation.",
                        builder=lambda df, masks, age_key=age_key, size_key=size_key, use_warning_veto=use_warning_veto: (
                            masks["bearish_risk_regime"]
                            & df["live_reversal_window"]
                            & df[f"age_lte_{age_key}"]
                            & df[f"size_lte_{size_key}"]
                            & ((~df["warning_active"]) if use_warning_veto else True)
                        ),
                    )
                )

    confirmation_specs = (
        ("onchain_dom_supportive", "ONCHAIN_DOM_Z at or above its median."),
        ("rebound_upper_half", "P_REBOUND_10D_CAL at or above its median."),
        ("ts20_not_strongly_negative", "TS_20 not below its 25th percentile."),
        ("er50_not_weak", "ER_50 at or above its median."),
    )
    for confirmation_name, description in confirmation_specs:
        variants.append(
            VariantSpec(
                variant_name=f"bearish_baseline_with_veto_{confirmation_name}",
                age_limit=1.00,
                size_limit=1.00,
                use_warning_veto=True,
                confirmation_name=confirmation_name,
                confirmation_description=description,
                builder=lambda df, masks, confirmation_name=confirmation_name: (
                    masks["bearish_risk_regime"]
                    & df["live_reversal_window"]
                    & df["age_lte_1_0"]
                    & df["size_lte_1_0"]
                    & (~df["warning_active"])
                    & df[f"confirm_{confirmation_name}"]
                ),
            )
        )
    return variants


def build_results(frame: pd.DataFrame, masks: dict[str, pd.Series]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    raw_mask = masks["bearish_risk_regime"].fillna(False)
    raw_row = summarize_template(
        frame,
        "raw_bearish_risk_regime",
        "baseline_raw",
        "Raw bearish_risk_regime precursor.",
        raw_mask,
        comparison_to=None,
    )
    raw_row.update(
        {
            "age_limit": np.nan,
            "size_limit": np.nan,
            "use_warning_veto": np.nan,
            "confirmation_name": "none",
            "confirmation_description": "Raw precursor.",
            "rank_score": np.nan,
            "delta_vs_raw_next_up": 0.0,
            "delta_vs_raw_next_down": 0.0,
            "delta_vs_raw_ret_10d_mean": 0.0,
            "delta_vs_current_filtered_next_up": np.nan,
            "delta_vs_current_filtered_next_down": np.nan,
            "delta_vs_current_filtered_ret_10d_mean": np.nan,
        }
    )
    rows.append(raw_row)

    current_mask = (
        masks["bearish_risk_regime"]
        & frame["live_reversal_window"]
        & frame["age_lte_1_0"]
        & frame["size_lte_1_0"]
        & (~frame["warning_active"])
    ).fillna(False)
    current_row = summarize_template(
        frame,
        "current_entry_bearish_contrarian_not_late",
        "baseline_filtered",
        "Current filtered bearish contrarian entry baseline.",
        current_mask,
        comparison_to="raw_bearish_risk_regime",
    )
    current_row.update(
        {
            "age_limit": 1.00,
            "size_limit": 1.00,
            "use_warning_veto": True,
            "confirmation_name": "none",
            "confirmation_description": "No extra confirmation.",
        }
    )
    rows.append(current_row)

    for variant in build_variant_specs():
        mask = variant.builder(frame, masks).fillna(False)
        row = summarize_template(
            frame,
            variant.variant_name,
            "refined_variant",
            (
                f"bearish_risk_regime + reversal_window + age<={variant.age_limit:.2f} + "
                f"size<={variant.size_limit:.2f} + "
                f"{'warning veto' if variant.use_warning_veto else 'no warning veto'} + "
                f"{variant.confirmation_description}"
            ),
            mask,
            comparison_to="raw_bearish_risk_regime",
        )
        row.update(
            {
                "age_limit": variant.age_limit,
                "size_limit": variant.size_limit,
                "use_warning_veto": variant.use_warning_veto,
                "confirmation_name": variant.confirmation_name,
                "confirmation_description": variant.confirmation_description,
            }
        )
        rows.append(row)

    results = pd.DataFrame(rows)
    raw_next_up = float(results.loc[results["template_name"] == "raw_bearish_risk_regime", "next_up_swing_rate"].iloc[0])
    raw_next_down = float(results.loc[results["template_name"] == "raw_bearish_risk_regime", "next_down_swing_rate"].iloc[0])
    raw_ret = float(results.loc[results["template_name"] == "raw_bearish_risk_regime", "ret_10d_mean"].iloc[0])

    current_next_up = float(results.loc[results["template_name"] == "current_entry_bearish_contrarian_not_late", "next_up_swing_rate"].iloc[0])
    current_next_down = float(results.loc[results["template_name"] == "current_entry_bearish_contrarian_not_late", "next_down_swing_rate"].iloc[0])
    current_ret = float(results.loc[results["template_name"] == "current_entry_bearish_contrarian_not_late", "ret_10d_mean"].iloc[0])

    results["delta_vs_raw_next_up"] = pd.to_numeric(results["next_up_swing_rate"], errors="coerce") - raw_next_up
    results["delta_vs_raw_next_down"] = pd.to_numeric(results["next_down_swing_rate"], errors="coerce") - raw_next_down
    results["delta_vs_raw_ret_10d_mean"] = pd.to_numeric(results["ret_10d_mean"], errors="coerce") - raw_ret
    results["delta_vs_current_filtered_next_up"] = pd.to_numeric(results["next_up_swing_rate"], errors="coerce") - current_next_up
    results["delta_vs_current_filtered_next_down"] = pd.to_numeric(results["next_down_swing_rate"], errors="coerce") - current_next_down
    results["delta_vs_current_filtered_ret_10d_mean"] = pd.to_numeric(results["ret_10d_mean"], errors="coerce") - current_ret

    sample_penalty = pd.to_numeric(results["sample_count"], errors="coerce").fillna(0).clip(upper=80) / 80.0
    results["rank_score"] = (
        pd.to_numeric(results["next_up_swing_rate"], errors="coerce").fillna(0.0)
        - pd.to_numeric(results["next_down_swing_rate"], errors="coerce").fillna(0.0)
        + 0.50 * pd.to_numeric(results["ret_10d_mean"], errors="coerce").fillna(0.0)
        + 0.25 * pd.to_numeric(results["touch_up_2pct_10d_rate"], errors="coerce").fillna(0.0)
        - 0.25 * pd.to_numeric(results["touch_down_2pct_10d_rate"], errors="coerce").fillna(0.0)
    ) * sample_penalty

    return results.sort_values(["template_family", "rank_score", "sample_count"], ascending=[True, False, False]).reset_index(drop=True)


def render_markdown(results: pd.DataFrame) -> str:
    refined = results.loc[results["template_family"] == "refined_variant"].copy()
    ranked = refined.loc[refined["sample_count"] >= 10].sort_values(["rank_score", "sample_count"], ascending=[False, False]).head(8)
    best = ranked.head(3)

    lines = [
        "# SAFE v4.0 Entry Logic Bearish Refinement",
        "",
        "## Section 1 — Refinement Grid Tested",
        "",
        "- base branch: `bearish_risk_regime` in a live reversal window",
        "- age filters: `<= 0.50`, `<= 0.75`, `<= 1.00` of median swing age",
        "- size filters: `<= 0.75`, `<= 1.00`, `<= 1.25` of median swing size",
        "- warning veto comparison: on/off for the no-confirmation grid",
        "- one-at-a-time confirmations on the current baseline shape:",
        "  - `ONCHAIN_DOM_Z` supportive",
        "  - `P_REBOUND_10D_CAL` upper-half",
        "  - `TS_20` not strongly negative",
        "  - `ER_50` not weak",
        "",
        "## Section 2 — Variant Ranking Table",
        "",
    ]
    for _, row in ranked.iterrows():
        lines.append(
            f"- `{row['template_name']}`: rank `{row['rank_score']:.3f}`, "
            f"next up `{row['next_up_swing_rate']:.2%}`, next down `{row['next_down_swing_rate']:.2%}`, "
            f"ret_10d mean `{row['ret_10d_mean']:.2%}`, "
            f"touch_up `{row['touch_up_2pct_10d_rate']:.2%}`, touch_down `{row['touch_down_2pct_10d_rate']:.2%}`, "
            f"n=`{int(row['sample_count'])}`"
        )

    lines.extend(["", "## Section 3 — Best Variants vs Baseline", ""])
    for _, row in best.iterrows():
        lines.append(
            f"- `{row['template_name']}` vs raw: "
            f"delta next-up `{row['delta_vs_raw_next_up']:+.2%}`, "
            f"delta next-down `{row['delta_vs_raw_next_down']:+.2%}`, "
            f"delta ret_10d mean `{row['delta_vs_raw_ret_10d_mean']:+.2%}`"
        )
        lines.append(
            f"- `{row['template_name']}` vs current filtered: "
            f"delta next-up `{row['delta_vs_current_filtered_next_up']:+.2%}`, "
            f"delta next-down `{row['delta_vs_current_filtered_next_down']:+.2%}`, "
            f"delta ret_10d mean `{row['delta_vs_current_filtered_ret_10d_mean']:+.2%}`"
        )

    lines.extend(["", "## Section 4 — Which Refinements Help, Which Do Not", ""])
    no_rows = refined.loc[refined["sample_count"] == 0]
    if not no_rows.empty:
        for _, row in no_rows.iterrows():
            lines.append(f"- `{row['template_name']}` produced no usable rows and does not help in its current form.")

    sparse = refined.loc[(refined["sample_count"] > 0) & (refined["sample_count"] < 10)].sort_values("sample_count")
    if not sparse.empty:
        for _, row in sparse.iterrows():
            lines.append(
                f"- `{row['template_name']}` is too sparse to trust: n=`{int(row['sample_count'])}`, "
                f"next up `{row['next_up_swing_rate']:.2%}`."
            )

    helpful = refined.loc[
        (refined["sample_count"] >= 10)
        & (refined["delta_vs_current_filtered_next_up"] > 0)
        & (refined["delta_vs_current_filtered_next_down"] < 0)
    ].sort_values("rank_score", ascending=False)
    if not helpful.empty:
        for _, row in helpful.head(5).iterrows():
            lines.append(
                f"- `{row['template_name']}` helps: it improved next-up purity by `{row['delta_vs_current_filtered_next_up']:+.2%}` "
                f"and reduced next-down leakage by `{abs(row['delta_vs_current_filtered_next_down']):.2%}`."
            )

    not_helpful = refined.loc[
        (refined["sample_count"] >= 10)
        & ~(
            (refined["delta_vs_current_filtered_next_up"] > 0)
            & (refined["delta_vs_current_filtered_next_down"] < 0)
        )
    ].sort_values("rank_score", ascending=False)
    if not not_helpful.empty:
        for _, row in not_helpful.head(5).iterrows():
            lines.append(
                f"- `{row['template_name']}` does not clearly help: "
                f"delta next-up `{row['delta_vs_current_filtered_next_up']:+.2%}`, "
                f"delta next-down `{row['delta_vs_current_filtered_next_down']:+.2%}`."
            )

    lines.extend(["", "## Section 5 — Clear Conclusion", ""])
    if best.empty:
        lines.append("- No refined variant produced enough usable rows to justify another step for this branch.")
    else:
        top = best.iloc[0]
        lines.append(
            f"- Best current candidate: `{top['template_name']}` with next up `{top['next_up_swing_rate']:.2%}`, "
            f"next down `{top['next_down_swing_rate']:.2%}`, ret_10d mean `{top['ret_10d_mean']:.2%}`, "
            f"n=`{int(top['sample_count'])}`."
        )
        if (
            top["sample_count"] >= 20
            and top["delta_vs_current_filtered_next_up"] > 0
            and top["delta_vs_current_filtered_next_down"] < 0
        ):
            lines.append("- This bearish-contrarian branch should remain alive for one more focused research step.")
        else:
            lines.append("- This bearish-contrarian branch is still weak and should be kept only as a tentative research candidate.")
        lines.append("- Variants that improve purity only by collapsing sample size should not be promoted.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    dataset, condition_mapping = build_dataset(args)
    masks = build_condition_masks(dataset, condition_mapping)
    dataset = add_live_flags(dataset, masks)
    dataset = add_refinement_flags(dataset)
    results = build_results(dataset, masks)

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
