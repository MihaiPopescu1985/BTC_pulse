from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_CAUSAL_BOTTOM_PROXY_COMPARISON_CSV_PATH,
    DEFAULT_CAUSAL_BOTTOM_PROXY_MEMBERSHIP_CSV_PATH,
    DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_CSV_PATH,
    DEFAULT_LONG_SIGNAL_REFINEMENT_CSV_PATH,
    STATISTICS_DIR,
)


DEFAULT_CAUSAL_BOTTOM_PROXY_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_CAUSAL_BOTTOM_PROXY.md"
)
ORACLE_COLUMN = "variant_high_closest_to_low"

REQUIRED_REFINEMENT_COLUMNS = [
    "date",
    "close",
    "promoted_buy_timing_score",
    "promoted_sell_timing_score",
    "timing_score_spread",
    "edge_clarity_score",
    "conflict_score",
    "long_refinement_bucket",
    "return_5d",
    "return_10d",
    "favorable_excursion_10d",
    "adverse_excursion_10d",
    "touch_favorable_2pct_10d",
    "touch_adverse_2pct_10d",
    "favorable_2pct_before_adverse_2pct_10d",
    "adverse_2pct_before_favorable_2pct_10d",
    "dist_to_current_down_swing_low_pct",
]
REQUIRED_CONDITIONING_COLUMNS = ["date", ORACLE_COLUMN, "variant_long_quality_high"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare causal bottom-proximity proxies against the oracle low-proximity subset.")
    parser.add_argument(
        "--long-signal-refinement-csv",
        default=str(DEFAULT_LONG_SIGNAL_REFINEMENT_CSV_PATH),
        help="Default: ../out/swing_bottom/long_signal_refinement.csv",
    )
    parser.add_argument(
        "--final-conditioning-csv",
        default=str(DEFAULT_FINAL_LONG_SIGNAL_CONDITIONING_CSV_PATH),
        help="Default: ../out/swing_bottom/final_long_signal_conditioning.csv",
    )
    parser.add_argument(
        "--out-comparison-csv",
        default=str(DEFAULT_CAUSAL_BOTTOM_PROXY_COMPARISON_CSV_PATH),
        help="Default: ../out/swing_bottom/causal_bottom_proxy_comparison.csv",
    )
    parser.add_argument(
        "--out-membership-csv",
        default=str(DEFAULT_CAUSAL_BOTTOM_PROXY_MEMBERSHIP_CSV_PATH),
        help="Default: ../out/swing_bottom/causal_bottom_proxy_membership.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_CAUSAL_BOTTOM_PROXY_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_CAUSAL_BOTTOM_PROXY.md",
    )
    return parser.parse_args()


def load_inputs(refinement_path: str | Path, conditioning_path: str | Path) -> pd.DataFrame:
    refinement = pd.read_csv(refinement_path).sort_values("date").reset_index(drop=True)
    missing_refinement = [column for column in REQUIRED_REFINEMENT_COLUMNS if column not in refinement.columns]
    if missing_refinement:
        raise ValueError(f"Long signal refinement file is missing columns: {missing_refinement}")
    conditioning = pd.read_csv(conditioning_path).sort_values("date").reset_index(drop=True)
    missing_conditioning = [column for column in REQUIRED_CONDITIONING_COLUMNS if column not in conditioning.columns]
    if missing_conditioning:
        raise ValueError(f"Final conditioning file is missing columns: {missing_conditioning}")
    merged = refinement.merge(conditioning.loc[:, REQUIRED_CONDITIONING_COLUMNS], on="date", how="left", validate="one_to_one")
    if len(merged) != len(refinement):
        raise ValueError("Refinement/conditioning merge changed row count.")
    if merged["date"].duplicated().any():
        raise ValueError("Causal proxy input contains duplicate dates.")
    for column in [ORACLE_COLUMN, "variant_long_quality_high"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype(int)
    return merged


def add_causal_components(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    q = {
        "buy66": out["promoted_buy_timing_score"].quantile(0.66),
        "buy75": out["promoted_buy_timing_score"].quantile(0.75),
        "sell33": out["promoted_sell_timing_score"].quantile(0.33),
        "sell50": out["promoted_sell_timing_score"].quantile(0.50),
        "sell66": out["promoted_sell_timing_score"].quantile(0.66),
        "spread66": out["timing_score_spread"].quantile(0.66),
        "spread75": out["timing_score_spread"].quantile(0.75),
        "spread33": out["timing_score_spread"].quantile(0.33),
        "clarity66": out["edge_clarity_score"].quantile(0.66),
        "clarity75": out["edge_clarity_score"].quantile(0.75),
        "conflict33": out["conflict_score"].quantile(0.33),
        "conflict50": out["conflict_score"].quantile(0.50),
        "conflict66": out["conflict_score"].quantile(0.66),
    }

    out["causal_component_buy_high"] = out["promoted_buy_timing_score"].ge(q["buy66"]).astype(int)
    out["causal_component_buy_extreme"] = out["promoted_buy_timing_score"].ge(q["buy75"]).astype(int)
    out["causal_component_sell_low"] = out["promoted_sell_timing_score"].le(q["sell33"]).astype(int)
    out["causal_component_sell_high"] = out["promoted_sell_timing_score"].ge(q["sell66"]).astype(int)
    out["causal_component_spread_high"] = out["timing_score_spread"].ge(q["spread66"]).astype(int)
    out["causal_component_spread_extreme"] = out["timing_score_spread"].ge(q["spread75"]).astype(int)
    out["causal_component_spread_weak"] = out["timing_score_spread"].le(q["spread33"]).astype(int)
    out["causal_component_clarity_high"] = out["edge_clarity_score"].ge(q["clarity66"]).astype(int)
    out["causal_component_clarity_extreme"] = out["edge_clarity_score"].ge(q["clarity75"]).astype(int)
    out["causal_component_conflict_low"] = out["conflict_score"].le(q["conflict33"]).astype(int)
    out["causal_component_conflict_high"] = out["conflict_score"].ge(q["conflict66"]).astype(int)
    out["causal_refinement_score"] = (
        out["causal_component_buy_high"]
        + out["causal_component_sell_low"]
        + out["causal_component_spread_high"]
        + out["causal_component_clarity_high"]
        + out["causal_component_conflict_low"]
        - out["causal_component_sell_high"]
        - out["causal_component_spread_weak"]
        - out["causal_component_conflict_high"]
    )

    out["proxy_all_long_signal_new"] = 1
    out["proxy_mixed_long_quality_high_reference"] = out["variant_long_quality_high"]
    out["proxy_oracle_high_closest_to_low"] = out[ORACLE_COLUMN]
    out["proxy_causal_score_ge3"] = out["causal_refinement_score"].ge(3).astype(int)
    out["proxy_causal_score_ge4"] = out["causal_refinement_score"].ge(4).astype(int)
    out["proxy_strong_spread_clarity"] = (
        out["timing_score_spread"].ge(q["spread66"]) & out["edge_clarity_score"].ge(q["clarity66"])
    ).astype(int)
    out["proxy_buy_extreme_sell_suppressed"] = (
        out["promoted_buy_timing_score"].ge(q["buy75"]) & out["promoted_sell_timing_score"].le(q["sell50"])
    ).astype(int)
    out["proxy_low_conflict_sell_suppressed"] = (
        out["conflict_score"].le(q["conflict33"]) & out["promoted_sell_timing_score"].le(q["sell33"])
    ).astype(int)
    out["proxy_compact_causal_confluence"] = (
        out["timing_score_spread"].ge(q["spread66"])
        & out["edge_clarity_score"].ge(q["clarity66"])
        & out["conflict_score"].le(q["conflict50"])
        & out["promoted_sell_timing_score"].le(q["sell50"])
    ).astype(int)
    return out


def proxy_definitions() -> list[tuple[str, str, bool]]:
    return [
        ("proxy_all_long_signal_new", "Baseline: all LONG_SIGNAL_NEW events.", False),
        ("proxy_mixed_long_quality_high_reference", "Reference: prior LONG_QUALITY_HIGH bucket; includes future-proximity components.", True),
        ("proxy_oracle_high_closest_to_low", "Oracle benchmark: high-quality events closest to eventual swing low.", True),
        ("proxy_causal_score_ge3", "Causal score >= 3 using buy/sell/spread/clarity/conflict only.", False),
        ("proxy_causal_score_ge4", "Causal score >= 4 using buy/sell/spread/clarity/conflict only.", False),
        ("proxy_strong_spread_clarity", "Timing spread and clarity both in upper causal tercile.", False),
        ("proxy_buy_extreme_sell_suppressed", "Buy timing top quartile with sell timing no higher than median.", False),
        ("proxy_low_conflict_sell_suppressed", "Conflict and sell timing both in lower causal tercile.", False),
        ("proxy_compact_causal_confluence", "Strong spread/clarity with low conflict and suppressed sell timing.", False),
    ]


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.median()) if values.notna().any() else np.nan


def summarize_proxy(frame: pd.DataFrame, proxy_column: str, description: str, is_oracle: bool) -> dict[str, object]:
    group = frame.loc[frame[proxy_column].eq(1)].copy()
    total = len(frame)
    oracle_count = int(frame[ORACLE_COLUMN].sum())
    selected_count = len(group)
    selected_oracle_count = int(group[ORACLE_COLUMN].sum()) if selected_count else 0
    return {
        "proxy": proxy_column,
        "description": description,
        "uses_future_low_label": is_oracle,
        "event_count": selected_count,
        "share_of_all_long_signal_new": selected_count / total if total else np.nan,
        "oracle_capture_count": selected_oracle_count,
        "oracle_precision": selected_oracle_count / selected_count if selected_count else np.nan,
        "oracle_coverage": selected_oracle_count / oracle_count if oracle_count else np.nan,
        "mean_return_5d": safe_mean(group["return_5d"]),
        "mean_return_10d": safe_mean(group["return_10d"]),
        "median_return_10d": safe_median(group["return_10d"]),
        "mean_favorable_excursion_10d": safe_mean(group["favorable_excursion_10d"]),
        "mean_adverse_excursion_10d": safe_mean(group["adverse_excursion_10d"]),
        "touch_favorable_2pct_10d_rate": safe_mean(group["touch_favorable_2pct_10d"]),
        "touch_adverse_2pct_10d_rate": safe_mean(group["touch_adverse_2pct_10d"]),
        "favorable_2pct_before_adverse_2pct_10d_rate": safe_mean(group["favorable_2pct_before_adverse_2pct_10d"]),
        "adverse_2pct_before_favorable_2pct_10d_rate": safe_mean(group["adverse_2pct_before_favorable_2pct_10d"]),
        "mean_dist_to_low_eval_only": safe_mean(group["dist_to_current_down_swing_low_pct"]),
        "mean_causal_score": safe_mean(group["causal_refinement_score"]),
    }


def build_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    rows = [summarize_proxy(frame, column, description, is_oracle) for column, description, is_oracle in proxy_definitions()]
    comparison = pd.DataFrame(rows)
    oracle = comparison.loc[comparison["proxy"].eq("proxy_oracle_high_closest_to_low")].iloc[0]
    quality = comparison.loc[comparison["proxy"].eq("proxy_mixed_long_quality_high_reference")].iloc[0]
    comparison["return_10d_gap_to_oracle"] = comparison["mean_return_10d"] - float(oracle["mean_return_10d"])
    comparison["adverse_excursion_gap_to_oracle"] = (
        comparison["mean_adverse_excursion_10d"] - float(oracle["mean_adverse_excursion_10d"])
    )
    comparison["favorable_first_gap_to_oracle"] = (
        comparison["favorable_2pct_before_adverse_2pct_10d_rate"]
        - float(oracle["favorable_2pct_before_adverse_2pct_10d_rate"])
    )
    comparison["return_10d_delta_vs_quality_high"] = comparison["mean_return_10d"] - float(quality["mean_return_10d"])
    comparison["adverse_excursion_delta_vs_quality_high"] = (
        comparison["mean_adverse_excursion_10d"] - float(quality["mean_adverse_excursion_10d"])
    )
    comparison["favorable_first_delta_vs_quality_high"] = (
        comparison["favorable_2pct_before_adverse_2pct_10d_rate"]
        - float(quality["favorable_2pct_before_adverse_2pct_10d_rate"])
    )
    return comparison


def recommend(comparison: pd.DataFrame) -> tuple[str, str]:
    oracle = comparison.loc[comparison["proxy"].eq("proxy_oracle_high_closest_to_low")].iloc[0]
    quality = comparison.loc[comparison["proxy"].eq("proxy_mixed_long_quality_high_reference")].iloc[0]
    candidates = comparison.loc[
        ~comparison["proxy"].isin(
            ["proxy_all_long_signal_new", "proxy_mixed_long_quality_high_reference", "proxy_oracle_high_closest_to_low"]
        )
    ].copy()
    candidates = candidates.loc[candidates["event_count"].ge(10)].copy()
    if candidates.empty:
        return "No useful causal proxy found", "No causal candidate kept enough events for a meaningful comparison."

    oracle_return = float(oracle["mean_return_10d"])
    quality_return = float(quality["mean_return_10d"])
    oracle_adverse = float(oracle["mean_adverse_excursion_10d"])
    quality_adverse = float(quality["mean_adverse_excursion_10d"])
    oracle_first = float(oracle["favorable_2pct_before_adverse_2pct_10d_rate"])
    quality_first = float(quality["favorable_2pct_before_adverse_2pct_10d_rate"])

    candidates["closes_return_gap"] = candidates["mean_return_10d"].ge(quality_return + 0.5 * (oracle_return - quality_return))
    candidates["closes_adverse_gap"] = candidates["mean_adverse_excursion_10d"].ge(
        quality_adverse + 0.5 * (oracle_adverse - quality_adverse)
    )
    candidates["closes_ordering_gap"] = candidates["favorable_2pct_before_adverse_2pct_10d_rate"].ge(
        quality_first + 0.5 * (oracle_first - quality_first)
    )
    candidates["dimension_count"] = candidates[
        ["closes_return_gap", "closes_adverse_gap", "closes_ordering_gap"]
    ].sum(axis=1)
    best = candidates.sort_values(
        ["dimension_count", "mean_return_10d", "mean_adverse_excursion_10d"],
        ascending=False,
    ).iloc[0]

    if int(best["dimension_count"]) >= 3 and float(best["oracle_precision"]) >= 0.40:
        return (
            "Causal proxy found",
            f"`{best['proxy']}` closes most of the gap to the oracle while remaining causal.",
        )
    if int(best["dimension_count"]) >= 1 or float(best["oracle_precision"]) > float(candidates["oracle_precision"].median()):
        return (
            "Partial proxy only",
            f"`{best['proxy']}` improves at least one dimension, but remains materially weaker than the oracle subset.",
        )
    return (
        "No useful causal proxy found",
        "None of the compact causal candidates meaningfully approaches the oracle subset.",
    )


def pct(value: float, digits: int = 1) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    out = frame.loc[:, columns].copy()
    if out.empty:
        return "_No rows._"
    rendered = out.fillna("n/a").astype(str)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = [
        "| " + " | ".join(str(value).replace("\n", " ") for value in record) + " |"
        for record in rendered.to_numpy()
    ]
    return "\n".join([header, separator, *rows])


def render_markdown(comparison: pd.DataFrame, decision: str, reason: str) -> str:
    display = comparison[
        [
            "proxy",
            "uses_future_low_label",
            "event_count",
            "share_of_all_long_signal_new",
            "oracle_precision",
            "oracle_coverage",
            "mean_return_10d",
            "mean_adverse_excursion_10d",
            "favorable_2pct_before_adverse_2pct_10d_rate",
            "adverse_2pct_before_favorable_2pct_10d_rate",
        ]
    ].copy()
    for column in display.columns:
        if column == "proxy":
            continue
        if column in {"uses_future_low_label", "event_count"}:
            display[column] = display[column].map(lambda value: str(int(value)) if np.isfinite(float(value)) else "n/a")
        else:
            display[column] = display[column].map(lambda value: pct(float(value)))

    gap_display = comparison[
        [
            "proxy",
            "return_10d_delta_vs_quality_high",
            "adverse_excursion_delta_vs_quality_high",
            "favorable_first_delta_vs_quality_high",
            "return_10d_gap_to_oracle",
            "adverse_excursion_gap_to_oracle",
            "favorable_first_gap_to_oracle",
        ]
    ].copy()
    for column in [column for column in gap_display.columns if column != "proxy"]:
        gap_display[column] = gap_display[column].map(lambda value: number(float(value)))

    lines = [
        "# SAFE v4.0 Causal Bottom-Proximity Proxy",
        "",
        "## Purpose",
        "",
        "This pass tests whether the oracle `high_closest_to_low` condition can be approximated using only signal-time causal fields. "
        "It does not add execution logic, stops, position sizing, portfolio logic, broad model search, or production backtesting.",
        "",
        "## Leakage Rule",
        "",
        "Proxy definitions use only promoted buy timing, promoted sell timing, timing spread, edge clarity, and conflict score. "
        "`dist_to_current_down_swing_low_pct` and `high_closest_to_low` are used only for evaluation and oracle comparison.",
        "",
        "## Proxy Comparison",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Gap Versus Causal Reference And Oracle",
        "",
        markdown_table(gap_display, list(gap_display.columns)),
        "",
        "## Final Conclusion",
        "",
        f"**{decision}.** {reason}",
        "",
        "## Next-Step Note",
        "",
        (
            "If the project continues, the next step should validate the best causal proxy inside the minimal strategy feasibility frame."
            if decision == "Causal proxy found"
            else "The system should remain primarily a structural/oracle interpreter until a stronger causal bottom-proximity approximation is found."
        ),
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/causal_bottom_proxy_comparison.csv`",
        "- `out/swing_bottom/causal_bottom_proxy_membership.csv`",
    ]
    return "\n".join(lines) + "\n"


def output_membership(frame: pd.DataFrame) -> pd.DataFrame:
    proxy_columns = [column for column, _, _ in proxy_definitions()]
    columns = [
        "date",
        "close",
        "promoted_buy_timing_score",
        "promoted_sell_timing_score",
        "timing_score_spread",
        "edge_clarity_score",
        "conflict_score",
        "causal_refinement_score",
        "long_refinement_bucket",
        "dist_to_current_down_swing_low_pct",
        "return_5d",
        "return_10d",
        "favorable_excursion_10d",
        "adverse_excursion_10d",
        "favorable_2pct_before_adverse_2pct_10d",
        "adverse_2pct_before_favorable_2pct_10d",
        *proxy_columns,
    ]
    return frame.loc[:, columns].copy()


def validate_outputs(frame: pd.DataFrame, comparison: pd.DataFrame) -> None:
    if frame.empty or comparison.empty:
        raise ValueError("Causal proxy outputs cannot be empty.")
    if frame["date"].duplicated().any():
        raise ValueError("Causal proxy membership contains duplicate dates.")
    proxy_columns = [column for column, _, _ in proxy_definitions()]
    for column in proxy_columns:
        values = set(pd.to_numeric(frame[column], errors="coerce").dropna().astype(int))
        if not values.issubset({0, 1}):
            raise ValueError(f"{column} must be binary, found {sorted(values)}")
    causal_proxy_rows = comparison.loc[comparison["uses_future_low_label"].eq(False)]
    if causal_proxy_rows["event_count"].isna().any():
        raise ValueError("Causal proxy comparison contains malformed event counts.")


def run(args: argparse.Namespace) -> None:
    frame = load_inputs(args.long_signal_refinement_csv, args.final_conditioning_csv)
    scored = add_causal_components(frame)
    comparison = build_comparison(scored)
    membership = output_membership(scored)
    validate_outputs(membership, comparison)
    decision, reason = recommend(comparison)
    markdown = render_markdown(comparison, decision, reason)

    out_comparison = Path(args.out_comparison_csv)
    out_membership = Path(args.out_membership_csv)
    out_md = Path(args.out_md)
    out_comparison.parent.mkdir(parents=True, exist_ok=True)
    out_membership.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(out_comparison, index=False)
    membership.to_csv(out_membership, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_comparison}")
    print(f"Wrote {out_membership}")
    print(f"Wrote {out_md}")
    print(f"Decision: {decision}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
