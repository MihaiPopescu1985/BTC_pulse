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
    build_condition_masks,
    build_dataset,
)
from src.research.v4_iteration.research_active.run_entry_logic_bearish_candle_timing import compute_path_barriers


DEFAULT_ENTRY_LOGIC_LOW_RISK_BASE_CSV_PATH = OUT_DIR / "swing_bridge" / "entry_logic_low_risk_base.csv"
DEFAULT_ENTRY_LOGIC_LOW_RISK_BASE_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_ENTRY_LOGIC_LOW_RISK_BASE.md"
)


@dataclass(frozen=True)
class VariantSpec:
    variant_name: str
    description: str
    builder: callable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a narrow execution-quality entry pass on the low_risk_base branch.",
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
        default=str(DEFAULT_ENTRY_LOGIC_LOW_RISK_BASE_CSV_PATH),
        help="Default: ../out/swing_bridge/entry_logic_low_risk_base.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_ENTRY_LOGIC_LOW_RISK_BASE_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_ENTRY_LOGIC_LOW_RISK_BASE.md",
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


def load_base_dataset(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    dataset, condition_mapping = build_dataset(args)
    masks = build_condition_masks(dataset, condition_mapping)

    price = load_daily_price_json(args.price_json).reset_index()
    if "timestamp" in price.columns:
        price = price.rename(columns={"timestamp": "date"})
    price = _validate_date_frame("price", price.loc[:, ["date", "open", "high", "low", "close"]])

    merged = dataset.merge(price, on="date", how="inner", validate="one_to_one", suffixes=("", "_price"))
    rename_map: dict[str, str] = {}
    for field in ("open", "high", "low", "close"):
        if field not in merged.columns:
            if f"{field}_price" in merged.columns:
                rename_map[f"{field}_price"] = field
            elif f"{field}_y" in merged.columns:
                rename_map[f"{field}_y"] = field
            elif f"{field}_x" in merged.columns:
                rename_map[f"{field}_x"] = field
    if rename_map:
        merged = merged.rename(columns=rename_map)
    drop_columns = [f"{field}_price" for field in ("open", "high", "low", "close")]
    drop_columns.extend(f"{field}_x" for field in ("open", "high", "low", "close"))
    drop_columns.extend(f"{field}_y" for field in ("open", "high", "low", "close"))
    drop_columns = [column for column in drop_columns if column in merged.columns and column not in {"open", "high", "low", "close"}]
    if drop_columns:
        merged = merged.drop(columns=drop_columns)

    merged["prev_close"] = merged["close"].shift(1)
    merged["current_1d_return"] = merged["close"].pct_change(1)
    return merged.reset_index(drop=True), masks


def compute_thresholds(frame: pd.DataFrame, base_mask: pd.Series) -> dict[str, float]:
    subset = frame.loc[base_mask.fillna(False)].copy()
    if subset.empty:
        raise ValueError("low_risk_base subset is empty; cannot derive thresholds.")
    thresholds = {
        "band_pos_cap": float(pd.to_numeric(subset["band_pos"], errors="coerce").quantile(0.60)),
        "dist_from_mean_cap": float(pd.to_numeric(subset["dist_from_mean_vol_units"], errors="coerce").quantile(0.60)),
        "atr_pct_cap": float(pd.to_numeric(subset["atr_pct"], errors="coerce").quantile(0.75)),
        "ewma_vol_cap": float(pd.to_numeric(subset["ewma_vol"], errors="coerce").quantile(0.75)),
        "downside_semi_vol_cap": float(pd.to_numeric(subset["downside_semi_vol"], errors="coerce").quantile(0.75)),
        "ts20_floor": float(pd.to_numeric(subset["TS_20"], errors="coerce").quantile(0.50)),
    }
    return thresholds


def build_variants(thresholds: dict[str, float]) -> tuple[VariantSpec, ...]:
    return (
        VariantSpec(
            variant_name="raw_low_risk_base",
            description="Raw low_risk_base setup state, used as the execution-quality baseline.",
            builder=lambda df, masks: masks["low_risk_base"].fillna(False),
        ),
        VariantSpec(
            variant_name="low_risk_base_position_favorable",
            description=(
                "low_risk_base plus favorable position: band_pos not above the branch 60th percentile "
                "and dist_from_mean_vol_units not above the branch 60th percentile."
            ),
            builder=lambda df, masks, t=thresholds: (
                masks["low_risk_base"]
                & (df["band_pos"] <= t["band_pos_cap"])
                & (df["dist_from_mean_vol_units"] <= t["dist_from_mean_cap"])
            ).fillna(False),
        ),
        VariantSpec(
            variant_name="low_risk_base_position_favorable_confirm",
            description=(
                "Favorable position plus mild confirmation: close above prior close."
            ),
            builder=lambda df, masks, t=thresholds: (
                masks["low_risk_base"]
                & (df["band_pos"] <= t["band_pos_cap"])
                & (df["dist_from_mean_vol_units"] <= t["dist_from_mean_cap"])
                & (df["close"] > df["prev_close"])
            ).fillna(False),
        ),
        VariantSpec(
            variant_name="low_risk_base_volatility_sanity",
            description=(
                "low_risk_base plus volatility sanity: atr_pct, ewma_vol, and downside_semi_vol "
                "all at or below the branch 75th percentile."
            ),
            builder=lambda df, masks, t=thresholds: (
                masks["low_risk_base"]
                & (df["atr_pct"] <= t["atr_pct_cap"])
                & (df["ewma_vol"] <= t["ewma_vol_cap"])
                & (df["downside_semi_vol"] <= t["downside_semi_vol_cap"])
            ).fillna(False),
        ),
        VariantSpec(
            variant_name="low_risk_base_volatility_sanity_confirm",
            description=(
                "Volatility sanity plus mild confirmation: close above prior close."
            ),
            builder=lambda df, masks, t=thresholds: (
                masks["low_risk_base"]
                & (df["atr_pct"] <= t["atr_pct_cap"])
                & (df["ewma_vol"] <= t["ewma_vol_cap"])
                & (df["downside_semi_vol"] <= t["downside_semi_vol_cap"])
                & (df["close"] > df["prev_close"])
            ).fillna(False),
        ),
        VariantSpec(
            variant_name="low_risk_base_volatility_sanity_ts20_confirm",
            description=(
                "Volatility sanity plus short-trend confirmation: TS_20 at or above the branch median."
            ),
            builder=lambda df, masks, t=thresholds: (
                masks["low_risk_base"]
                & (df["atr_pct"] <= t["atr_pct_cap"])
                & (df["ewma_vol"] <= t["ewma_vol_cap"])
                & (df["downside_semi_vol"] <= t["downside_semi_vol_cap"])
                & (df["TS_20"] >= t["ts20_floor"])
            ).fillna(False),
        ),
    )


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


def summarize_variant(
    frame: pd.DataFrame,
    mask: pd.Series,
    *,
    variant_name: str,
    description: str,
) -> dict[str, object]:
    subset = frame.loc[mask.fillna(False)].copy()
    indices = subset.index.tolist()
    barrier_frame = pd.DataFrame(
        [compute_path_barriers(frame.loc[:, ["date", "open", "high", "low", "close"]], idx) for idx in indices]
    )

    result = {
        "variant_name": variant_name,
        "rule_definition": description,
        "sample_count": int(len(subset)),
        "next_up_swing_rate": _rate(subset["next_swing_direction"], "up"),
        "next_down_swing_rate": _rate(subset["next_swing_direction"], "down"),
        "ret_10d_mean": _mean(subset["ret_10d"]),
        "ret_10d_median": _median(subset["ret_10d"]),
        "ret_10d_win_rate": float((pd.to_numeric(subset["ret_10d"], errors="coerce") > 0).mean()) if not subset.empty else np.nan,
        "max_up_10d_mean": _mean(subset["max_up_10d"]),
        "max_up_10d_median": _median(subset["max_up_10d"]),
        "max_down_10d_mean": _mean(subset["max_down_10d"]),
        "max_down_10d_median": _median(subset["max_down_10d"]),
        "touch_up_2pct_10d_rate": _mean(subset["touch_up_2pct_10d"]),
        "touch_down_2pct_10d_rate": _mean(subset["touch_down_2pct_10d"]),
        "median_next_swing_abs_amplitude": _median(subset["next_swing_abs_amplitude"]),
        "median_next_swing_duration_days": _median(subset["next_swing_duration_days"]),
        "hit_neg_1pct_before_up2pct_rate": _mean(barrier_frame["hit_neg_1pct_before_up2pct"]) if not barrier_frame.empty else np.nan,
        "hit_neg_2pct_before_up2pct_rate": _mean(barrier_frame["hit_neg_2pct_before_up2pct"]) if not barrier_frame.empty else np.nan,
        "hit_neg_3pct_before_up2pct_rate": _mean(barrier_frame["hit_neg_3pct_before_up2pct"]) if not barrier_frame.empty else np.nan,
    }
    return result


def build_results(frame: pd.DataFrame, masks: dict[str, pd.Series], thresholds: dict[str, float]) -> pd.DataFrame:
    rows = []
    for spec in build_variants(thresholds):
        mask = spec.builder(frame, masks)
        rows.append(
            summarize_variant(
                frame,
                mask,
                variant_name=spec.variant_name,
                description=spec.description,
            )
        )

    results = pd.DataFrame(rows)
    baseline = results.loc[results["variant_name"] == "raw_low_risk_base"].iloc[0]
    results["delta_ret_10d_mean_vs_baseline"] = pd.to_numeric(results["ret_10d_mean"], errors="coerce") - float(baseline["ret_10d_mean"])
    results["delta_max_up_10d_mean_vs_baseline"] = pd.to_numeric(results["max_up_10d_mean"], errors="coerce") - float(baseline["max_up_10d_mean"])
    results["delta_max_down_10d_mean_vs_baseline"] = pd.to_numeric(results["max_down_10d_mean"], errors="coerce") - float(baseline["max_down_10d_mean"])
    results["delta_touch_up_2pct_10d_rate_vs_baseline"] = (
        pd.to_numeric(results["touch_up_2pct_10d_rate"], errors="coerce") - float(baseline["touch_up_2pct_10d_rate"])
    )
    results["delta_touch_down_2pct_10d_rate_vs_baseline"] = (
        pd.to_numeric(results["touch_down_2pct_10d_rate"], errors="coerce") - float(baseline["touch_down_2pct_10d_rate"])
    )
    results["delta_hit_neg_2pct_before_up2pct_vs_baseline"] = (
        pd.to_numeric(results["hit_neg_2pct_before_up2pct_rate"], errors="coerce") - float(baseline["hit_neg_2pct_before_up2pct_rate"])
    )

    sample_penalty = pd.to_numeric(results["sample_count"], errors="coerce").fillna(0.0).clip(upper=150.0) / 150.0
    results["execution_quality_score"] = (
        pd.to_numeric(results["delta_max_down_10d_mean_vs_baseline"], errors="coerce").fillna(0.0)
        - pd.to_numeric(results["delta_touch_down_2pct_10d_rate_vs_baseline"], errors="coerce").fillna(0.0)
        - pd.to_numeric(results["delta_hit_neg_2pct_before_up2pct_vs_baseline"], errors="coerce").fillna(0.0)
        + 0.60 * pd.to_numeric(results["delta_ret_10d_mean_vs_baseline"], errors="coerce").fillna(0.0)
        + 0.40 * pd.to_numeric(results["delta_touch_up_2pct_10d_rate_vs_baseline"], errors="coerce").fillna(0.0)
        + 0.30 * pd.to_numeric(results["delta_max_up_10d_mean_vs_baseline"], errors="coerce").fillna(0.0)
    ) * sample_penalty

    raw_score = float(results.loc[results["variant_name"] == "raw_low_risk_base", "execution_quality_score"].iloc[0])
    results.loc[results["variant_name"] == "raw_low_risk_base", "execution_quality_score"] = raw_score
    return results.sort_values(["execution_quality_score", "sample_count"], ascending=[False, False]).reset_index(drop=True)


def render_markdown(results: pd.DataFrame, thresholds: dict[str, float]) -> str:
    baseline = results.loc[results["variant_name"] == "raw_low_risk_base"].iloc[0]
    ranked = results.loc[results["variant_name"] != "raw_low_risk_base"].copy()
    ranked = ranked.sort_values(["execution_quality_score", "sample_count"], ascending=[False, False])
    best = ranked.iloc[0]

    lines = [
        "# SAFE v4.0 Entry Logic Low Risk Base",
        "",
        "## Section 1 — Why This Branch Is Being Treated As An Execution-Quality Candidate",
        "",
        "- `low_risk_base` is not being treated as a next-swing-purity branch in this pass",
        "- the purpose here is execution quality: lower downside pain, acceptable upside participation, and enough sample size to matter",
        "- all variants are compared directly against raw `low_risk_base`",
        "",
        "## Section 2 — Timing / Filter Variants Tested",
        "",
        f"- baseline: `raw_low_risk_base`",
        f"- favorable position thresholds: `band_pos <= {thresholds['band_pos_cap']:.3f}`, `dist_from_mean_vol_units <= {thresholds['dist_from_mean_cap']:.3f}`",
        f"- volatility sanity thresholds: `atr_pct <= {thresholds['atr_pct_cap']:.4f}`, `ewma_vol <= {thresholds['ewma_vol_cap']:.4f}`, `downside_semi_vol <= {thresholds['downside_semi_vol_cap']:.4f}`",
        f"- short-trend confirmation threshold: `TS_20 >= {thresholds['ts20_floor']:.4f}`",
        "- mild confirmation means `close > prior close`",
        "",
        "## Section 3 — Variant Comparison Vs Raw `low_risk_base`",
        "",
        "| Variant | n | ret_10d mean | max_up_10d | max_down_10d | touch_up | touch_down | -2% before +2% |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in results.sort_values(["variant_name"]).iterrows():
        lines.append(
            f"| `{row['variant_name']}` | {int(row['sample_count'])} | {row['ret_10d_mean']:.2%} | "
            f"{row['max_up_10d_mean']:.2%} | {row['max_down_10d_mean']:.2%} | "
            f"{row['touch_up_2pct_10d_rate']:.2%} | {row['touch_down_2pct_10d_rate']:.2%} | "
            f"{row['hit_neg_2pct_before_up2pct_rate']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Section 4 — Which Variants Improve Path Quality And Which Do Not",
            "",
            f"- raw baseline: ret_10d mean `{baseline['ret_10d_mean']:.2%}`, max_down_10d `{baseline['max_down_10d_mean']:.2%}`, touch_down_2pct_10d `{baseline['touch_down_2pct_10d_rate']:.2%}`, `-2% before +2%` `{baseline['hit_neg_2pct_before_up2pct_rate']:.2%}`",
            f"- best current variant: `{best['variant_name']}` with ret_10d mean `{best['ret_10d_mean']:.2%}`, max_down_10d `{best['max_down_10d_mean']:.2%}`, touch_down_2pct_10d `{best['touch_down_2pct_10d_rate']:.2%}`, `-2% before +2%` `{best['hit_neg_2pct_before_up2pct_rate']:.2%}`, n=`{int(best['sample_count'])}`",
            "",
        ]
    )

    for _, row in ranked.iterrows():
        if row["variant_name"] == best["variant_name"]:
            continue
        lines.append(
            f"- `{row['variant_name']}`: "
            f"delta ret_10d `{row['delta_ret_10d_mean_vs_baseline']:.2%}`, "
            f"delta max_down `{row['delta_max_down_10d_mean_vs_baseline']:.2%}`, "
            f"delta touch_down `{row['delta_touch_down_2pct_10d_rate_vs_baseline']:.2%}`, "
            f"delta `-2% before +2%` `{row['delta_hit_neg_2pct_before_up2pct_vs_baseline']:.2%}`, "
            f"n=`{int(row['sample_count'])}`"
        )

    lines.extend(
        [
            "",
            "## Section 5 — Clear Conclusion",
            "",
        ]
    )

    if (
        best["sample_count"] >= 50
        and best["delta_touch_down_2pct_10d_rate_vs_baseline"] < 0
        and best["delta_hit_neg_2pct_before_up2pct_vs_baseline"] < 0
        and best["delta_ret_10d_mean_vs_baseline"] > 0
    ):
        lines.append(
            f"- yes, this branch supports a plausible entry candidate: `{best['variant_name']}` is materially cleaner than raw `low_risk_base` without collapsing the sample."
        )
    else:
        lines.append(
            f"- not yet cleanly enough. `{best['variant_name']}` improves some execution metrics, but the branch still needs another pass before it can be called a usable entry candidate."
        )

    lines.append(
        f"- best variant in this pass: `{best['variant_name']}`"
    )
    lines.append(
        "- operationally, this branch remains worth refining because it starts from a materially safer path profile than the bearish watchlist branch."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame, masks = load_base_dataset(args)
    thresholds = compute_thresholds(frame, masks["low_risk_base"].fillna(False))
    results = build_results(frame, masks, thresholds)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(results, thresholds), encoding="utf-8")

    best = results.loc[results["variant_name"] != "raw_low_risk_base"].sort_values(
        ["execution_quality_score", "sample_count"], ascending=[False, False]
    ).iloc[0]

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(results)}")
    print(f"Best variant: {best['variant_name']}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
