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
from src.research.v4_iteration.research_active.run_entry_branch_head_to_head import (
    DEFAULT_FEATURES_CSV_PATH,
    DEFAULT_LIVE_SWING_STATE_CSV_PATH,
    DEFAULT_ONCHAIN_FEATURES_CSV_PATH,
    DEFAULT_PRICE_JSON_PATH,
    DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH,
    DEFAULT_SWING_TAXONOMY_CSV_PATH,
    DEFAULT_TARGETS_CSV_PATH,
    add_reclaim_flags,
    build_low_risk_baseline,
)
from src.research.v4_iteration.research_active.run_entry_logic_low_risk_base import (
    compute_thresholds,
    load_base_dataset,
)
from src.research.v4_iteration.research_active.run_entry_logic_bearish_candle_timing import compute_path_barriers


DEFAULT_ENTRY_LOGIC_LOW_RISK_ROBUSTNESS_CSV_PATH = OUT_DIR / "swing_bridge" / "entry_logic_low_risk_robustness.csv"
DEFAULT_ENTRY_LOGIC_LOW_RISK_ROBUSTNESS_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_ENTRY_LOGIC_LOW_RISK_ROBUSTNESS.md"
)


@dataclass(frozen=True)
class RobustnessVariant:
    variant_name: str
    description: str
    builder: callable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a narrow robustness pass around the current best low-risk entry candidate.",
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
        default=str(DEFAULT_ENTRY_LOGIC_LOW_RISK_ROBUSTNESS_CSV_PATH),
        help="Default: ../out/swing_bridge/entry_logic_low_risk_robustness.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_ENTRY_LOGIC_LOW_RISK_ROBUSTNESS_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_ENTRY_LOGIC_LOW_RISK_ROBUSTNESS.md",
    )
    return parser.parse_args()


def _mean(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else np.nan


def _median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else np.nan


def build_variants(base_mask: pd.Series) -> tuple[RobustnessVariant, ...]:
    return (
        RobustnessVariant(
            variant_name="low_risk_wait1_persist_reclaim",
            description="Exact current winner: base condition persists one day and the bar closes above prior close.",
            builder=lambda df, base=base_mask: base.shift(1).fillna(False) & base & df["close_above_prev_close"],
        ),
        RobustnessVariant(
            variant_name="low_risk_sameday_reclaim_close",
            description="Same-day reclaim after the base condition: close above prior close with no persistence delay.",
            builder=lambda df, base=base_mask: base & df["close_above_prev_close"],
        ),
        RobustnessVariant(
            variant_name="low_risk_wait2_persist_reclaim",
            description="Base condition persists for two days and the entry day closes above prior close.",
            builder=lambda df, base=base_mask: base.shift(2).fillna(False) & base.shift(1).fillna(False) & base & df["close_above_prev_close"],
        ),
        RobustnessVariant(
            variant_name="low_risk_wait1_persist_reclaim_high",
            description="Current winner with stricter reclaim: after one-day persistence, close above prior high.",
            builder=lambda df, base=base_mask: base.shift(1).fillna(False) & base & df["close_above_prev_high"],
        ),
    )


def summarize_variant(frame: pd.DataFrame, mask: pd.Series, variant: RobustnessVariant) -> dict[str, object]:
    subset = frame.loc[mask.fillna(False)].copy()
    indices = subset.index.tolist()
    barrier_frame = pd.DataFrame(
        [compute_path_barriers(frame.loc[:, ["date", "open", "high", "low", "close"]], idx) for idx in indices]
    )

    return {
        "variant_name": variant.variant_name,
        "rule_definition": variant.description,
        "sample_count": int(len(subset)),
        "ret_5d_mean": _mean(subset["ret_5d"]),
        "ret_5d_median": _median(subset["ret_5d"]),
        "ret_5d_win_rate": float((pd.to_numeric(subset["ret_5d"], errors="coerce") > 0).mean()) if not subset.empty else np.nan,
        "max_up_5d_mean": _mean(subset["max_up_5d"]),
        "max_up_5d_median": _median(subset["max_up_5d"]),
        "max_down_5d_mean": _mean(subset["max_down_5d"]),
        "max_down_5d_median": _median(subset["max_down_5d"]),
        "touch_up_2pct_5d_rate": _mean(subset["touch_up_2pct_5d"]),
        "touch_down_2pct_5d_rate": _mean(subset["touch_down_2pct_5d"]),
        "ret_10d_mean": _mean(subset["ret_10d"]),
        "ret_10d_median": _median(subset["ret_10d"]),
        "ret_10d_win_rate": float((pd.to_numeric(subset["ret_10d"], errors="coerce") > 0).mean()) if not subset.empty else np.nan,
        "max_up_10d_mean": _mean(subset["max_up_10d"]),
        "max_up_10d_median": _median(subset["max_up_10d"]),
        "max_down_10d_mean": _mean(subset["max_down_10d"]),
        "max_down_10d_median": _median(subset["max_down_10d"]),
        "touch_up_2pct_10d_rate": _mean(subset["touch_up_2pct_10d"]),
        "touch_down_2pct_10d_rate": _mean(subset["touch_down_2pct_10d"]),
        "hit_neg_1pct_before_up2pct_rate": _mean(barrier_frame["hit_neg_1pct_before_up2pct"]) if not barrier_frame.empty else np.nan,
        "hit_neg_2pct_before_up2pct_rate": _mean(barrier_frame["hit_neg_2pct_before_up2pct"]) if not barrier_frame.empty else np.nan,
        "hit_neg_3pct_before_up2pct_rate": _mean(barrier_frame["hit_neg_3pct_before_up2pct"]) if not barrier_frame.empty else np.nan,
    }


def build_results(frame: pd.DataFrame, base_mask: pd.Series) -> pd.DataFrame:
    rows = [summarize_variant(frame, variant.builder(frame), variant) for variant in build_variants(base_mask)]
    results = pd.DataFrame(rows)
    baseline = results.loc[results["variant_name"] == "low_risk_wait1_persist_reclaim"].iloc[0]

    for column in (
        "ret_5d_mean",
        "max_up_5d_mean",
        "max_down_5d_mean",
        "touch_up_2pct_5d_rate",
        "touch_down_2pct_5d_rate",
        "ret_10d_mean",
        "max_up_10d_mean",
        "max_down_10d_mean",
        "touch_up_2pct_10d_rate",
        "touch_down_2pct_10d_rate",
        "hit_neg_1pct_before_up2pct_rate",
        "hit_neg_2pct_before_up2pct_rate",
        "hit_neg_3pct_before_up2pct_rate",
    ):
        results[f"delta_{column}_vs_baseline"] = pd.to_numeric(results[column], errors="coerce") - float(baseline[column])

    sample_penalty = pd.to_numeric(results["sample_count"], errors="coerce").fillna(0.0).clip(upper=60.0) / 60.0
    results["robustness_score"] = (
        pd.to_numeric(results["delta_ret_10d_mean_vs_baseline"], errors="coerce").fillna(0.0) * 0.70
        + pd.to_numeric(results["delta_max_up_10d_mean_vs_baseline"], errors="coerce").fillna(0.0) * 0.30
        + pd.to_numeric(results["delta_max_down_10d_mean_vs_baseline"], errors="coerce").fillna(0.0) * 1.20
        - pd.to_numeric(results["delta_touch_down_2pct_10d_rate_vs_baseline"], errors="coerce").fillna(0.0)
        - pd.to_numeric(results["delta_hit_neg_2pct_before_up2pct_rate_vs_baseline"], errors="coerce").fillna(0.0) * 1.00
        + pd.to_numeric(results["delta_ret_5d_mean_vs_baseline"], errors="coerce").fillna(0.0) * 0.30
        + pd.to_numeric(results["delta_max_down_5d_mean_vs_baseline"], errors="coerce").fillna(0.0) * 0.50
        - pd.to_numeric(results["delta_touch_down_2pct_5d_rate_vs_baseline"], errors="coerce").fillna(0.0) * 0.60
    ) * sample_penalty
    results.loc[results["variant_name"] == "low_risk_wait1_persist_reclaim", "robustness_score"] = 0.0
    return results.sort_values(["robustness_score", "sample_count"], ascending=[False, False]).reset_index(drop=True)


def render_markdown(results: pd.DataFrame) -> str:
    baseline = results.loc[results["variant_name"] == "low_risk_wait1_persist_reclaim"].iloc[0]
    others = results.loc[results["variant_name"] != "low_risk_wait1_persist_reclaim"].copy()
    best = results.sort_values(["robustness_score", "sample_count"], ascending=[False, False]).iloc[0]

    lines = [
        "# SAFE v4.0 Entry Logic Low Risk Robustness",
        "",
        "## Section 1 — Why This Pass Is Being Run",
        "",
        "- `low_risk_wait1_persist_reclaim` is the current best entry candidate",
        "- this pass tests whether its quality survives small local rule changes",
        "- the purpose is structural stability, not new idea generation",
        "",
        "## Section 2 — Baseline Template",
        "",
        "- exact baseline: low-risk base branch + volatility sanity + TS_20 confirmation + one-day persistence + reclaim via close above prior close",
        "",
        "## Section 3 — Local Perturbations Tested",
        "",
        "- `low_risk_sameday_reclaim_close`",
        "- `low_risk_wait1_persist_reclaim`",
        "- `low_risk_wait2_persist_reclaim`",
        "- `low_risk_wait1_persist_reclaim_high`",
        "",
        "## Section 4 — Robustness Comparison Table",
        "",
        "| Variant | n | ret_5d | ret_10d | max_down_5d | max_down_10d | touch_down_5d | touch_down_10d | -2% before +2% |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in results.sort_values(["variant_name"]).iterrows():
        lines.append(
            f"| `{row['variant_name']}` | {int(row['sample_count'])} | {row['ret_5d_mean']:.2%} | {row['ret_10d_mean']:.2%} | "
            f"{row['max_down_5d_mean']:.2%} | {row['max_down_10d_mean']:.2%} | "
            f"{row['touch_down_2pct_5d_rate']:.2%} | {row['touch_down_2pct_10d_rate']:.2%} | "
            f"{row['hit_neg_2pct_before_up2pct_rate']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Section 5 — Whether The Candidate Is Stable Or Fragile",
            "",
            f"- frozen baseline: n=`{int(baseline['sample_count'])}`, ret_5d `{baseline['ret_5d_mean']:.2%}`, ret_10d `{baseline['ret_10d_mean']:.2%}`, max_down_10d `{baseline['max_down_10d_mean']:.2%}`, touch_down_10d `{baseline['touch_down_2pct_10d_rate']:.2%}`, `-2% before +2%` `{baseline['hit_neg_2pct_before_up2pct_rate']:.2%}`",
            "",
        ]
    )

    for _, row in others.sort_values(["robustness_score", "sample_count"], ascending=[False, False]).iterrows():
        lines.append(
            f"- `{row['variant_name']}`: "
            f"delta ret_5d `{row['delta_ret_5d_mean_vs_baseline']:.2%}`, "
            f"delta ret_10d `{row['delta_ret_10d_mean_vs_baseline']:.2%}`, "
            f"delta max_down_10d `{row['delta_max_down_10d_mean_vs_baseline']:.2%}`, "
            f"delta touch_down_10d `{row['delta_touch_down_2pct_10d_rate_vs_baseline']:.2%}`, "
            f"delta `-2% before +2%` `{row['delta_hit_neg_2pct_before_up2pct_rate_vs_baseline']:.2%}`, "
            f"n=`{int(row['sample_count'])}`"
        )

    stable_neighborhood = int(
        (
            (others["delta_ret_10d_mean_vs_baseline"] >= -0.01)
            & (others["delta_touch_down_2pct_10d_rate_vs_baseline"] <= 0.10)
            & (others["sample_count"] >= 16)
        ).sum()
    )

    lines.extend(["", "## Section 6 — Clear Conclusion", ""])

    if stable_neighborhood >= 2:
        lines.append("- the candidate looks structurally stable rather than narrowly fragile. Small nearby rule changes mostly preserve the improvement direction.")
    else:
        lines.append("- the candidate looks somewhat fragile. Performance concentrates in a very narrow local rule choice.")

    if baseline["ret_5d_mean"] > 0 and baseline["touch_down_2pct_5d_rate"] <= baseline["touch_down_2pct_10d_rate"]:
        lines.append("- this template reads better as a 5d-to-10d execution setup than as a longer-hold idea. The short-horizon profile is cleaner.")
    else:
        lines.append("- the 10d view is at least as important as the 5d view for this template.")

    lines.append(f"- active version after this pass: `{best['variant_name']}`")

    if best["variant_name"] == "low_risk_wait1_persist_reclaim":
        lines.append("- keep the current winner. It survives local stress well enough and remains the most balanced version.")
    else:
        lines.append(f"- promote `{best['variant_name']}` as the new active variant. It improves the frozen baseline without collapsing the sample.")

    lines.append("- the next step can move closer to strategy-layer testing, but only for this single low-risk branch.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame, masks = load_base_dataset(args)
    frame = add_reclaim_flags(frame)
    thresholds = compute_thresholds(frame, masks["low_risk_base"].fillna(False))
    base_mask = build_low_risk_baseline(frame, masks, thresholds)
    results = build_results(frame, base_mask)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(results), encoding="utf-8")

    best = results.sort_values(["robustness_score", "sample_count"], ascending=[False, False]).iloc[0]
    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(results)}")
    print(f"Active version after robustness pass: {best['variant_name']}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
