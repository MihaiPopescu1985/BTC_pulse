from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_RULE_LAYER_CALIBRATION_CSV_PATH,
    DEFAULT_RULE_LAYER_CALIBRATION_DETAIL_CSV_PATH,
    DEFAULT_STRATEGY_TRANSLATION_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bottom.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
)
from src.research.v4_iteration.core.swing_bottom.run_rule_layer import REQUIRED_COLUMNS


DEFAULT_RULE_LAYER_CALIBRATION_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_RULE_LAYER_CALIBRATION.md"
)


@dataclass(frozen=True)
class RuleVariant:
    name: str
    description: str
    buy_age: int
    sell_age: int
    strong_first_day: bool = False
    strong_clarity: float = 0.40
    strong_conflict: float = 0.16
    strong_abs_spread: float = 0.35


VARIANTS = [
    RuleVariant(
        name="current_age2_symmetric",
        description="Current reference: buy and sell eligibility require active context age >= 2.",
        buy_age=2,
        sell_age=2,
    ),
    RuleVariant(
        name="age1_symmetric",
        description="Looser reference: buy and sell eligibility require active context age >= 1.",
        buy_age=1,
        sell_age=1,
    ),
    RuleVariant(
        name="buy_age1_sell_age2",
        description="Asymmetric persistence: buy eligible immediately, sell keeps age >= 2.",
        buy_age=1,
        sell_age=2,
    ),
    RuleVariant(
        name="buy_age1_sell_age2_strong_first_day",
        description="Asymmetric persistence plus strong first-day promotion for either side.",
        buy_age=1,
        sell_age=2,
        strong_first_day=True,
    ),
    RuleVariant(
        name="age2_with_strong_first_day",
        description="Current age-2 reference with strong first-day promotion when clarity/spread dominate and conflict is low.",
        buy_age=2,
        sell_age=2,
        strong_first_day=True,
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a narrow calibration pass for the SAFE rule layer.")
    parser.add_argument(
        "--strategy-translation-csv",
        default=str(DEFAULT_STRATEGY_TRANSLATION_CSV_PATH),
        help="Default: ../out/swing_bottom/strategy_translation_layer.csv",
    )
    parser.add_argument(
        "--out-calibration-csv",
        default=str(DEFAULT_RULE_LAYER_CALIBRATION_CSV_PATH),
        help="Default: ../out/swing_bottom/rule_layer_calibration.csv",
    )
    parser.add_argument(
        "--out-detail-csv",
        default=str(DEFAULT_RULE_LAYER_CALIBRATION_DETAIL_CSV_PATH),
        help="Default: ../out/swing_bottom/rule_layer_calibration_detail.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_RULE_LAYER_CALIBRATION_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_RULE_LAYER_CALIBRATION.md",
    )
    return parser.parse_args()


def load_strategy_translation(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path).sort_values("date").reset_index(drop=True)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Strategy translation layer is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Strategy translation layer contains duplicate dates.")
    return frame


def strong_first_day_pass(row: pd.Series, variant: RuleVariant, side: str) -> bool:
    if not variant.strong_first_day:
        return False
    if int(row["operational_state_age_days"]) != 1:
        return False
    clarity = float(row["edge_clarity_score"])
    conflict = float(row["conflict_score"])
    spread = float(row["timing_score_spread"])
    if clarity < variant.strong_clarity or conflict > variant.strong_conflict:
        return False
    if side == "long":
        return spread >= variant.strong_abs_spread
    return spread <= -variant.strong_abs_spread


def classify_variant(row: pd.Series, variant: RuleVariant) -> str:
    state = str(row["operational_state"])
    bias = str(row["operational_bias"])
    ready = int(row["readiness_flag"])
    caution = int(row["caution_flag"])
    invalidated = int(row["invalidation_flag"])
    stand_aside = int(row["stand_aside_flag"])
    age = int(row["operational_state_age_days"])

    if invalidated or state == "CONTEXT_INVALIDATED":
        return "INVALIDATED"
    if stand_aside or state == "STAND_ASIDE_CONFLICT":
        return "BLOCKED_BY_CONFLICT"
    if state == "STAND_ASIDE_NO_EDGE":
        return "BLOCKED_NO_EDGE"
    if state == "LONG_CONTEXT_ACTIVE" and ready and not caution and bias == "long_side":
        if age >= variant.buy_age or strong_first_day_pass(row, variant, "long"):
            return "LONG_ELIGIBLE"
        return "AWAIT_CONFIRMATION"
    if state == "SELL_CONTEXT_ACTIVE" and ready and not caution and bias == "sell_side":
        if age >= variant.sell_age or strong_first_day_pass(row, variant, "sell"):
            return "SELL_ELIGIBLE"
        return "AWAIT_CONFIRMATION"
    if state == "WAIT_CONFIRMATION":
        return "AWAIT_CONFIRMATION"
    return "AWAIT_CONFIRMATION"


def add_variant_states(frame: pd.DataFrame, variant: RuleVariant) -> pd.DataFrame:
    out = frame.copy()
    out["rule_state"] = out.apply(lambda row: classify_variant(row, variant), axis=1)
    out["long_permission_flag"] = out["rule_state"].eq("LONG_ELIGIBLE").astype(int)
    out["sell_derisk_permission_flag"] = out["rule_state"].eq("SELL_ELIGIBLE").astype(int)
    out["confirmation_needed_flag"] = out["rule_state"].eq("AWAIT_CONFIRMATION").astype(int)
    out["block_action_flag"] = out["rule_state"].isin(
        ["BLOCKED_BY_CONFLICT", "BLOCKED_NO_EDGE", "INVALIDATED"]
    ).astype(int)
    out["invalidation_active_flag"] = out["rule_state"].eq("INVALIDATED").astype(int)
    return out


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def variant_metrics(frame: pd.DataFrame, variant: RuleVariant) -> dict[str, object]:
    total = len(frame)
    long_rows = frame.loc[frame["rule_state"].eq("LONG_ELIGIBLE")]
    sell_rows = frame.loc[frame["rule_state"].eq("SELL_ELIGIBLE")]
    wait_rows = frame.loc[frame["rule_state"].eq("AWAIT_CONFIRMATION")]
    blocked_rows = frame.loc[frame["block_action_flag"].eq(1)]
    invalid_rows = frame.loc[frame["rule_state"].eq("INVALIDATED")]

    return {
        "variant": variant.name,
        "description": variant.description,
        "buy_age": variant.buy_age,
        "sell_age": variant.sell_age,
        "strong_first_day": variant.strong_first_day,
        "row_count": total,
        "long_eligible_count": len(long_rows),
        "long_eligible_share": len(long_rows) / total if total else np.nan,
        "sell_eligible_count": len(sell_rows),
        "sell_eligible_share": len(sell_rows) / total if total else np.nan,
        "await_confirmation_count": len(wait_rows),
        "await_confirmation_share": len(wait_rows) / total if total else np.nan,
        "blocked_share": len(blocked_rows) / total if total else np.nan,
        "invalidated_share": len(invalid_rows) / total if total else np.nan,
        "long_buy_zone_5_rate": safe_mean(long_rows[DEFAULT_BUY_TARGET]),
        "long_buy_zone_3_rate": safe_mean(long_rows[DEFAULT_BUY_STRICT_TARGET]),
        "long_sell_zone_5_contamination": safe_mean(long_rows[DEFAULT_SELL_TARGET]),
        "sell_sell_zone_5_rate": safe_mean(sell_rows[DEFAULT_SELL_TARGET]),
        "sell_sell_zone_3_rate": safe_mean(sell_rows[DEFAULT_SELL_STRICT_TARGET]),
        "sell_buy_zone_5_contamination": safe_mean(sell_rows[DEFAULT_BUY_TARGET]),
        "long_avg_clarity": safe_mean(long_rows["edge_clarity_score"]),
        "long_avg_conflict": safe_mean(long_rows["conflict_score"]),
        "sell_avg_clarity": safe_mean(sell_rows["edge_clarity_score"]),
        "sell_avg_conflict": safe_mean(sell_rows["conflict_score"]),
    }


def detail_rows(frame: pd.DataFrame, variant: RuleVariant) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    total = len(frame)
    for state, group in frame.groupby("rule_state", sort=True):
        rows.append(
            {
                "variant": variant.name,
                "rule_state": state,
                "row_count": len(group),
                "row_share": len(group) / total if total else np.nan,
                "buy_zone_5_rate": safe_mean(group[DEFAULT_BUY_TARGET]),
                "buy_zone_3_rate": safe_mean(group[DEFAULT_BUY_STRICT_TARGET]),
                "sell_zone_5_rate": safe_mean(group[DEFAULT_SELL_TARGET]),
                "sell_zone_3_rate": safe_mean(group[DEFAULT_SELL_STRICT_TARGET]),
                "avg_clarity": safe_mean(group["edge_clarity_score"]),
                "avg_conflict": safe_mean(group["conflict_score"]),
            }
        )
    return rows


def build_outputs(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, object]] = []
    detail: list[dict[str, object]] = []
    for variant in VARIANTS:
        variant_frame = add_variant_states(frame, variant)
        summary_rows.append(variant_metrics(variant_frame, variant))
        detail.extend(detail_rows(variant_frame, variant))
    summary = pd.DataFrame(summary_rows)
    reference = summary.loc[summary["variant"].eq("current_age2_symmetric")].iloc[0]
    summary["long_coverage_delta_vs_current"] = summary["long_eligible_share"] - float(reference["long_eligible_share"])
    summary["sell_coverage_delta_vs_current"] = summary["sell_eligible_share"] - float(reference["sell_eligible_share"])
    summary["await_delta_vs_current"] = summary["await_confirmation_share"] - float(reference["await_confirmation_share"])
    summary["long_quality_delta_vs_current"] = summary["long_buy_zone_5_rate"] - float(reference["long_buy_zone_5_rate"])
    summary["sell_quality_delta_vs_current"] = summary["sell_sell_zone_5_rate"] - float(reference["sell_sell_zone_5_rate"])
    summary["long_contamination_delta_vs_current"] = (
        summary["long_sell_zone_5_contamination"] - float(reference["long_sell_zone_5_contamination"])
    )
    summary["sell_contamination_delta_vs_current"] = (
        summary["sell_buy_zone_5_contamination"] - float(reference["sell_buy_zone_5_contamination"])
    )
    return summary, pd.DataFrame(detail)


def recommend(summary: pd.DataFrame) -> tuple[str, str, str]:
    reference = summary.loc[summary["variant"].eq("current_age2_symmetric")].iloc[0]
    candidates = summary.loc[summary["variant"].ne("current_age2_symmetric")].copy()
    current_long_quality = float(reference["long_buy_zone_5_rate"])
    current_sell_quality = float(reference["sell_sell_zone_5_rate"])
    current_long_contam = float(reference["long_sell_zone_5_contamination"])
    current_sell_contam = float(reference["sell_buy_zone_5_contamination"])

    viable = candidates.loc[
        candidates["long_eligible_share"].ge(float(reference["long_eligible_share"]) * 1.5)
        & candidates["long_buy_zone_5_rate"].ge(current_long_quality - 0.05)
        & candidates["long_sell_zone_5_contamination"].le(current_long_contam + 0.03)
        & candidates["sell_sell_zone_5_rate"].ge(current_sell_quality - 0.03)
        & candidates["sell_buy_zone_5_contamination"].le(current_sell_contam + 0.03)
    ].copy()
    if viable.empty:
        return (
            "Keep current rule layer",
            "current_age2_symmetric",
            "No calibrated variant expands permission enough without weakening cleanliness beyond the tolerance band.",
        )
    viable["score"] = (
        2.0 * viable["long_coverage_delta_vs_current"]
        + viable["sell_coverage_delta_vs_current"]
        - viable["long_contamination_delta_vs_current"].clip(lower=0.0)
        - viable["sell_contamination_delta_vs_current"].clip(lower=0.0)
    )
    best = viable.sort_values("score", ascending=False).iloc[0]
    if best["variant"] == "age1_symmetric":
        decision = "Promote calibrated rule layer"
    else:
        decision = "Keep both reference and loose variant"
    return (
        decision,
        str(best["variant"]),
        "The recommended variant expands permissions while preserving directional cleanliness within the calibration tolerance band.",
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


def render_markdown(summary: pd.DataFrame, detail: pd.DataFrame, decision: str, recommended: str, reason: str) -> str:
    display = summary[
        [
            "variant",
            "long_eligible_share",
            "long_buy_zone_5_rate",
            "long_sell_zone_5_contamination",
            "sell_eligible_share",
            "sell_sell_zone_5_rate",
            "sell_buy_zone_5_contamination",
            "await_confirmation_share",
            "blocked_share",
            "invalidated_share",
        ]
    ].copy()
    for column in display.columns:
        if column != "variant":
            display[column] = display[column].map(lambda value: pct(float(value)))

    delta_display = summary[
        [
            "variant",
            "long_coverage_delta_vs_current",
            "long_quality_delta_vs_current",
            "long_contamination_delta_vs_current",
            "sell_coverage_delta_vs_current",
            "sell_quality_delta_vs_current",
            "sell_contamination_delta_vs_current",
            "await_delta_vs_current",
        ]
    ].copy()
    for column in delta_display.columns:
        if column != "variant":
            delta_display[column] = delta_display[column].map(lambda value: number(float(value)))

    recommended_row = summary.loc[summary["variant"].eq(recommended)].iloc[0]
    lines = [
        "# SAFE v4.0 Rule Layer Calibration",
        "",
        "## Purpose",
        "",
        "This pass calibrates the first explicit rule layer. It only tests compact eligibility-rule variations; it does not add execution, PnL, stops, position sizing, portfolio logic, or backtests.",
        "",
        "## Variants Tested",
        "",
        "- `current_age2_symmetric`: current reference, buy and sell require active context age >= 2.",
        "- `age1_symmetric`: buy and sell eligible immediately when active context is ready.",
        "- `buy_age1_sell_age2`: buy eligible immediately, sell keeps age >= 2.",
        "- `buy_age1_sell_age2_strong_first_day`: asymmetric persistence plus strong first-day promotion.",
        "- `age2_with_strong_first_day`: current age-2 rule plus strong first-day promotion.",
        "",
        "Strong first-day promotion requires clarity >= 0.40, conflict <= 0.16, and absolute score spread >= 0.35.",
        "",
        "## Permission / Contamination Tradeoff",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Delta Versus Current Reference",
        "",
        markdown_table(delta_display, list(delta_display.columns)),
        "",
        "## Recommendation",
        "",
        f"**{decision}: `{recommended}`.** {reason}",
        "",
        f"The recommended variant has long eligible share {pct(float(recommended_row['long_eligible_share']))}, "
        f"long buy-zone 5% rate {pct(float(recommended_row['long_buy_zone_5_rate']))}, "
        f"long sell-zone contamination {pct(float(recommended_row['long_sell_zone_5_contamination']))}, "
        f"sell eligible share {pct(float(recommended_row['sell_eligible_share']))}, and "
        f"sell sell-zone 5% rate {pct(float(recommended_row['sell_sell_zone_5_rate']))}.",
        "",
        "## Interpretation",
        "",
        "The current layer is structurally correct but over-gated. The calibration mainly shows whether first-day active contexts should be permitted instead of held in confirmation. "
        "This remains a structural permission layer only: eligibility means a later strategy may evaluate that side, not that an order should be placed.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/rule_layer_calibration.csv`",
        "- `out/swing_bottom/rule_layer_calibration_detail.csv`",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> None:
    frame = load_strategy_translation(args.strategy_translation_csv)
    summary, detail = build_outputs(frame)
    decision, recommended, reason = recommend(summary)
    markdown = render_markdown(summary, detail, decision, recommended, reason)

    out_summary = Path(args.out_calibration_csv)
    out_detail = Path(args.out_detail_csv)
    out_md = Path(args.out_md)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_detail.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_summary, index=False)
    detail.to_csv(out_detail, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_summary}")
    print(f"Wrote {out_detail}")
    print(f"Wrote {out_md}")
    print(f"Recommendation: {decision} -> {recommended}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
