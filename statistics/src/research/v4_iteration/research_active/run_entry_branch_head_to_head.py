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
from src.research.v4_iteration.core.interaction_discovery.run_interaction_discovery import build_templates, quantile_cutoffs
from src.research.v4_iteration.research_active.run_entry_logic_low_risk_base import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    compute_thresholds,
    load_base_dataset,
    summarize_variant,
)


DEFAULT_ENTRY_BRANCH_HEAD_TO_HEAD_CSV_PATH = OUT_DIR / "swing_bridge" / "entry_branch_head_to_head.csv"
DEFAULT_ENTRY_BRANCH_HEAD_TO_HEAD_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_ENTRY_BRANCH_HEAD_TO_HEAD.md"
)


@dataclass(frozen=True)
class HeadToHeadVariant:
    variant_name: str
    branch_family: str
    description: str
    builder: callable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a narrow head-to-head execution-quality comparison between the refined low-risk branch and squeeze_release_up.",
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
        default=str(DEFAULT_ENTRY_BRANCH_HEAD_TO_HEAD_CSV_PATH),
        help="Default: ../out/swing_bridge/entry_branch_head_to_head.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_ENTRY_BRANCH_HEAD_TO_HEAD_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_ENTRY_BRANCH_HEAD_TO_HEAD.md",
    )
    return parser.parse_args()


def add_reclaim_flags(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["prev_high"] = enriched["high"].shift(1)
    enriched["prev_low"] = enriched["low"].shift(1)
    enriched["close_above_prev_close"] = enriched["close"] > enriched["prev_close"]
    enriched["close_above_prev_high"] = enriched["close"] > enriched["prev_high"]
    enriched["failed_breakdown_recovery"] = (enriched["low"] < enriched["prev_low"]) & (
        enriched["close"] > enriched["prev_close"]
    )
    return enriched


def build_low_risk_baseline(frame: pd.DataFrame, masks: dict[str, pd.Series], thresholds: dict[str, float]) -> pd.Series:
    return (
        masks["low_risk_base"]
        & (frame["atr_pct"] <= thresholds["atr_pct_cap"])
        & (frame["ewma_vol"] <= thresholds["ewma_vol_cap"])
        & (frame["downside_semi_vol"] <= thresholds["downside_semi_vol_cap"])
        & (frame["TS_20"] >= thresholds["ts20_floor"])
    ).fillna(False)


def get_squeeze_release_mask(frame: pd.DataFrame) -> pd.Series:
    templates = {template.name: template for template in build_templates()}
    quantiles = quantile_cutoffs(frame)
    return templates["squeeze_release_up"].builder(frame, quantiles).fillna(False)


def build_variants(frame: pd.DataFrame, masks: dict[str, pd.Series], thresholds: dict[str, float]) -> tuple[HeadToHeadVariant, ...]:
    low_risk_base = build_low_risk_baseline(frame, masks, thresholds)
    squeeze_release = get_squeeze_release_mask(frame)
    return (
        HeadToHeadVariant(
            variant_name="low_risk_base_volatility_sanity_ts20_confirm",
            branch_family="low_risk_base",
            description="Current winning low-risk baseline from the prior pass.",
            builder=lambda df, low=low_risk_base: low,
        ),
        HeadToHeadVariant(
            variant_name="low_risk_reclaim_close",
            branch_family="low_risk_base",
            description="Current low-risk winner plus close above prior close.",
            builder=lambda df, low=low_risk_base: low & df["close_above_prev_close"],
        ),
        HeadToHeadVariant(
            variant_name="low_risk_reclaim_high",
            branch_family="low_risk_base",
            description="Current low-risk winner plus close above prior high.",
            builder=lambda df, low=low_risk_base: low & df["close_above_prev_high"],
        ),
        HeadToHeadVariant(
            variant_name="low_risk_wait1_persist_reclaim",
            branch_family="low_risk_base",
            description="Current low-risk winner persists one day and closes above prior close.",
            builder=lambda df, low=low_risk_base: low.shift(1).fillna(False) & low & df["close_above_prev_close"],
        ),
        HeadToHeadVariant(
            variant_name="squeeze_release_up_raw",
            branch_family="squeeze_release_up",
            description="Raw squeeze_release_up rival branch.",
            builder=lambda df, sq=squeeze_release: sq,
        ),
        HeadToHeadVariant(
            variant_name="squeeze_release_up_confirm_close",
            branch_family="squeeze_release_up",
            description="squeeze_release_up plus close above prior close.",
            builder=lambda df, sq=squeeze_release: sq & df["close_above_prev_close"],
        ),
        HeadToHeadVariant(
            variant_name="squeeze_release_up_reclaim_high",
            branch_family="squeeze_release_up",
            description="squeeze_release_up plus close above prior high.",
            builder=lambda df, sq=squeeze_release: sq & df["close_above_prev_high"],
        ),
        HeadToHeadVariant(
            variant_name="squeeze_release_up_wait1_persist_close",
            branch_family="squeeze_release_up",
            description="squeeze_release_up persists one day and closes above prior close.",
            builder=lambda df, sq=squeeze_release: sq.shift(1).fillna(False) & sq & df["close_above_prev_close"],
        ),
    )


def build_results(frame: pd.DataFrame, masks: dict[str, pd.Series], thresholds: dict[str, float]) -> pd.DataFrame:
    rows = []
    for variant in build_variants(frame, masks, thresholds):
        rows.append(
            {
                "branch_family": variant.branch_family,
                **summarize_variant(
                    frame,
                    variant.builder(frame).fillna(False),
                    variant_name=variant.variant_name,
                    description=variant.description,
                ),
            }
        )

    results = pd.DataFrame(rows)
    baseline = results.loc[results["variant_name"] == "low_risk_base_volatility_sanity_ts20_confirm"].iloc[0]
    for column in (
        "ret_10d_mean",
        "max_up_10d_mean",
        "max_down_10d_mean",
        "touch_up_2pct_10d_rate",
        "touch_down_2pct_10d_rate",
        "hit_neg_1pct_before_up2pct_rate",
        "hit_neg_2pct_before_up2pct_rate",
        "hit_neg_3pct_before_up2pct_rate",
    ):
        results[f"delta_{column}_vs_lowrisk_winner"] = pd.to_numeric(results[column], errors="coerce") - float(baseline[column])

    sample_penalty = pd.to_numeric(results["sample_count"], errors="coerce").fillna(0.0).clip(upper=100.0) / 100.0
    results["execution_quality_score"] = (
        pd.to_numeric(results["delta_ret_10d_mean_vs_lowrisk_winner"], errors="coerce").fillna(0.0) * 0.70
        + pd.to_numeric(results["delta_max_up_10d_mean_vs_lowrisk_winner"], errors="coerce").fillna(0.0) * 0.40
        + pd.to_numeric(results["delta_max_down_10d_mean_vs_lowrisk_winner"], errors="coerce").fillna(0.0) * 1.20
        - pd.to_numeric(results["delta_touch_down_2pct_10d_rate_vs_lowrisk_winner"], errors="coerce").fillna(0.0)
        + pd.to_numeric(results["delta_touch_up_2pct_10d_rate_vs_lowrisk_winner"], errors="coerce").fillna(0.0) * 0.50
        - pd.to_numeric(results["delta_hit_neg_2pct_before_up2pct_rate_vs_lowrisk_winner"], errors="coerce").fillna(0.0) * 1.10
        - pd.to_numeric(results["delta_hit_neg_1pct_before_up2pct_rate_vs_lowrisk_winner"], errors="coerce").fillna(0.0) * 0.40
    ) * sample_penalty
    results.loc[results["variant_name"] == "low_risk_base_volatility_sanity_ts20_confirm", "execution_quality_score"] = 0.0
    return results.sort_values(["execution_quality_score", "sample_count"], ascending=[False, False]).reset_index(drop=True)


def render_markdown(results: pd.DataFrame) -> str:
    baseline = results.loc[results["variant_name"] == "low_risk_base_volatility_sanity_ts20_confirm"].iloc[0]
    low_risk_variants = results.loc[(results["branch_family"] == "low_risk_base") & (results["variant_name"] != "low_risk_base_volatility_sanity_ts20_confirm")].copy()
    squeeze_variants = results.loc[results["branch_family"] == "squeeze_release_up"].copy()
    best = results.sort_values(["execution_quality_score", "sample_count"], ascending=[False, False]).iloc[0]

    lines = [
        "# SAFE v4.0 Entry Branch Head To Head",
        "",
        "## Section 1 — Why This Pass Is Being Run",
        "",
        "- the prior pass produced one active execution-quality candidate: `low_risk_base_volatility_sanity_ts20_confirm`",
        "- this pass checks whether a small reclaim layer improves that winner and whether `squeeze_release_up` can beat it as a rival execution branch",
        "- the comparison is path-quality first, upside retention second, sample viability third",
        "",
        "## Section 2 — Low-Risk Branch Timing Refinements Tested",
        "",
        "- baseline winner: `low_risk_base_volatility_sanity_ts20_confirm`",
        "- `low_risk_reclaim_close`: require close above prior close",
        "- `low_risk_reclaim_high`: require close above prior high",
        "- `low_risk_wait1_persist_reclaim`: require one-day persistence plus close above prior close",
        "",
        "## Section 3 — Squeeze-Release Rival Variants Tested",
        "",
        "- `squeeze_release_up_raw`",
        "- `squeeze_release_up_confirm_close`",
        "- `squeeze_release_up_reclaim_high`",
        "- `squeeze_release_up_wait1_persist_close`",
        "",
        "## Section 4 — Head-To-Head Execution-Quality Comparison",
        "",
        f"- low-risk winner baseline: n=`{int(baseline['sample_count'])}`, ret_10d mean `{baseline['ret_10d_mean']:.2%}`, max_down_10d `{baseline['max_down_10d_mean']:.2%}`, touch_down `{baseline['touch_down_2pct_10d_rate']:.2%}`, `-2% before +2%` `{baseline['hit_neg_2pct_before_up2pct_rate']:.2%}`",
        "",
        "| Variant | Branch | n | ret_10d mean | max_up_10d | max_down_10d | touch_up | touch_down | -2% before +2% |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in results.sort_values(["branch_family", "variant_name"]).iterrows():
        lines.append(
            f"| `{row['variant_name']}` | `{row['branch_family']}` | {int(row['sample_count'])} | "
            f"{row['ret_10d_mean']:.2%} | {row['max_up_10d_mean']:.2%} | {row['max_down_10d_mean']:.2%} | "
            f"{row['touch_up_2pct_10d_rate']:.2%} | {row['touch_down_2pct_10d_rate']:.2%} | {row['hit_neg_2pct_before_up2pct_rate']:.2%} |"
        )

    lines.extend(["", "Low-risk refinements vs current winner:", ""])
    for _, row in low_risk_variants.sort_values(["execution_quality_score", "sample_count"], ascending=[False, False]).iterrows():
        lines.append(
            f"- `{row['variant_name']}`: delta ret_10d `{row['delta_ret_10d_mean_vs_lowrisk_winner']:.2%}`, "
            f"delta max_down `{row['delta_max_down_10d_mean_vs_lowrisk_winner']:.2%}`, "
            f"delta touch_down `{row['delta_touch_down_2pct_10d_rate_vs_lowrisk_winner']:.2%}`, "
            f"delta `-2% before +2%` `{row['delta_hit_neg_2pct_before_up2pct_rate_vs_lowrisk_winner']:.2%}`, "
            f"n=`{int(row['sample_count'])}`"
        )

    lines.extend(["", "Squeeze-release rivals vs current winner:", ""])
    for _, row in squeeze_variants.sort_values(["execution_quality_score", "sample_count"], ascending=[False, False]).iterrows():
        lines.append(
            f"- `{row['variant_name']}`: delta ret_10d `{row['delta_ret_10d_mean_vs_lowrisk_winner']:.2%}`, "
            f"delta max_down `{row['delta_max_down_10d_mean_vs_lowrisk_winner']:.2%}`, "
            f"delta touch_down `{row['delta_touch_down_2pct_10d_rate_vs_lowrisk_winner']:.2%}`, "
            f"delta `-2% before +2%` `{row['delta_hit_neg_2pct_before_up2pct_rate_vs_lowrisk_winner']:.2%}`, "
            f"n=`{int(row['sample_count'])}`"
        )

    lines.extend(["", "## Section 5 — Clear Conclusion", ""])

    if best["variant_name"] == "low_risk_base_volatility_sanity_ts20_confirm":
        lines.append("- the low-risk branch still leads. None of the small refinements or squeeze-release rivals beat the current winner cleanly enough.")
    else:
        lines.append(f"- the current leader is now `{best['variant_name']}` from `{best['branch_family']}`.")

    low_risk_best = results.loc[results["branch_family"] == "low_risk_base"].sort_values(
        ["execution_quality_score", "sample_count"], ascending=[False, False]
    ).iloc[0]
    squeeze_best = results.loc[results["branch_family"] == "squeeze_release_up"].sort_values(
        ["execution_quality_score", "sample_count"], ascending=[False, False]
    ).iloc[0]

    lines.append(
        f"- best low-risk variant: `{low_risk_best['variant_name']}` with ret_10d mean `{low_risk_best['ret_10d_mean']:.2%}`, "
        f"touch_down `{low_risk_best['touch_down_2pct_10d_rate']:.2%}`, `-2% before +2%` `{low_risk_best['hit_neg_2pct_before_up2pct_rate']:.2%}`, n=`{int(low_risk_best['sample_count'])}`"
    )
    lines.append(
        f"- best squeeze-release variant: `{squeeze_best['variant_name']}` with ret_10d mean `{squeeze_best['ret_10d_mean']:.2%}`, "
        f"touch_down `{squeeze_best['touch_down_2pct_10d_rate']:.2%}`, `-2% before +2%` `{squeeze_best['hit_neg_2pct_before_up2pct_rate']:.2%}`, n=`{int(squeeze_best['sample_count'])}`"
    )
    lines.append("- further refinement should continue on one branch only, and that branch should be the current head-to-head winner.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame, masks = load_base_dataset(args)
    frame = add_reclaim_flags(frame)
    thresholds = compute_thresholds(frame, masks["low_risk_base"].fillna(False))
    results = build_results(frame, masks, thresholds)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(results), encoding="utf-8")

    best = results.sort_values(["execution_quality_score", "sample_count"], ascending=[False, False]).iloc[0]
    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(results)}")
    print(f"Current winner: {best['variant_name']}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
