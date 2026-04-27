from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_RULE_LAYER_CSV_PATH,
    DEFAULT_RULE_LAYER_SUMMARY_CSV_PATH,
    DEFAULT_STRATEGY_TRANSLATION_CSV_PATH,
    STATISTICS_DIR,
)
from src.signals.reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
)


DEFAULT_RULE_LAYER_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_RULE_LAYER.md"
MIN_ELIGIBLE_AGE_DAYS = 1

REQUIRED_COLUMNS = [
    "date",
    "close",
    "split",
    "decision_state",
    "playbook_label",
    "playbook_attention_level",
    "operational_state",
    "operational_bias",
    "readiness_flag",
    "caution_flag",
    "invalidation_flag",
    "stand_aside_flag",
    "operational_is_active_context",
    "operational_state_age_days",
    "operational_state_run_length_days",
    "operational_note",
    "promoted_buy_timing_score",
    "promoted_sell_timing_score",
    "timing_score_spread",
    "edge_clarity_score",
    "conflict_score",
    DEFAULT_BUY_TARGET,
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    "dist_to_current_down_swing_low_pct",
    "dist_to_current_up_swing_high_pct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SAFE minimal rule layer from operational states.")
    parser.add_argument(
        "--strategy-translation-csv",
        default=str(DEFAULT_STRATEGY_TRANSLATION_CSV_PATH),
        help="Default: ../out/swing_bottom/strategy_translation_layer.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_RULE_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/rule_layer.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_RULE_LAYER_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/rule_layer_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_RULE_LAYER_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_RULE_LAYER.md",
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


def classify_rule(row: pd.Series) -> tuple[str, int, int, int, int, int, str]:
    state = str(row["operational_state"])
    bias = str(row["operational_bias"])
    ready = int(row["readiness_flag"])
    caution = int(row["caution_flag"])
    invalidated = int(row["invalidation_flag"])
    stand_aside = int(row["stand_aside_flag"])
    age = int(row["operational_state_age_days"])

    if invalidated or state == "CONTEXT_INVALIDATED":
        return (
            "INVALIDATED",
            0,
            0,
            0,
            1,
            1,
            "Previously favorable context is broken; structural action is blocked until a new context forms.",
        )

    if stand_aside or state == "STAND_ASIDE_CONFLICT":
        return (
            "BLOCKED_BY_CONFLICT",
            0,
            0,
            0,
            0,
            1,
            "Directional action is blocked by conflicting buy/sell timing.",
        )

    if state == "STAND_ASIDE_NO_EDGE":
        return (
            "BLOCKED_NO_EDGE",
            0,
            0,
            0,
            0,
            1,
            "No structural edge is present; action remains blocked.",
        )

    if state == "LONG_CONTEXT_ACTIVE" and ready and not caution:
        if bias == "long_side" and age >= MIN_ELIGIBLE_AGE_DAYS:
            return (
                "LONG_ELIGIBLE",
                1,
                0,
                0,
                0,
                0,
                "Long-side consideration is structurally permitted; this is not an entry signal.",
            )
        return (
            "AWAIT_CONFIRMATION",
            0,
            0,
            1,
            0,
            0,
            "Long context is active but needs persistence before eligibility.",
        )

    if state == "SELL_CONTEXT_ACTIVE" and ready and not caution:
        if bias == "sell_side" and age >= MIN_ELIGIBLE_AGE_DAYS:
            return (
                "SELL_ELIGIBLE",
                0,
                1,
                0,
                0,
                0,
                "Sell/de-risk consideration is structurally permitted; this is not an exit rule.",
            )
        return (
            "AWAIT_CONFIRMATION",
            0,
            0,
            1,
            0,
            0,
            "Sell context is active but needs persistence before eligibility.",
        )

    if state == "WAIT_CONFIRMATION":
        return (
            "AWAIT_CONFIRMATION",
            0,
            0,
            1,
            0,
            0,
            "Directional context exists but explicit eligibility rules are not satisfied.",
        )

    return (
        "AWAIT_CONFIRMATION",
        0,
        0,
        1,
        0,
        1 if caution else 0,
        "Unrecognized operational configuration; defer until structure is clearer.",
    )


def add_rule_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    classified = out.apply(classify_rule, axis=1, result_type="expand")
    classified.columns = [
        "rule_state",
        "long_permission_flag",
        "sell_derisk_permission_flag",
        "confirmation_needed_flag",
        "invalidation_active_flag",
        "block_action_flag",
        "rule_note",
    ]
    out = pd.concat([out, classified], axis=1)
    out["rule_is_permission"] = out["rule_state"].isin(["LONG_ELIGIBLE", "SELL_ELIGIBLE"]).astype(int)
    out["rule_is_block"] = out["rule_state"].isin(
        ["BLOCKED_BY_CONFLICT", "BLOCKED_NO_EDGE", "INVALIDATED"]
    ).astype(int)

    state_change = out["rule_state"].ne(out["rule_state"].shift()).fillna(True)
    out["rule_state_run_id"] = state_change.cumsum().astype(int)
    out["rule_state_age_days"] = out.groupby("rule_state_run_id").cumcount() + 1
    out["rule_state_run_length_days"] = out.groupby("rule_state_run_id")["date"].transform("size").astype(int)
    return out


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_rows = len(frame)
    run_table = (
        frame.loc[:, ["rule_state", "rule_state_run_id", "rule_state_run_length_days"]]
        .drop_duplicates("rule_state_run_id")
        .copy()
    )

    for state, group in frame.groupby("rule_state", sort=True):
        runs = run_table.loc[run_table["rule_state"].eq(state)]
        metrics = {
            "row_count": float(len(group)),
            "row_share": float(len(group) / total_rows) if total_rows else np.nan,
            "run_count": float(len(runs)),
            "avg_run_length_days": safe_mean(runs["rule_state_run_length_days"]),
            "buy_zone_5_rate": safe_mean(group[DEFAULT_BUY_TARGET]),
            "buy_zone_3_rate": safe_mean(group[DEFAULT_BUY_STRICT_TARGET]),
            "sell_zone_5_rate": safe_mean(group[DEFAULT_SELL_TARGET]),
            "sell_zone_3_rate": safe_mean(group[DEFAULT_SELL_STRICT_TARGET]),
            "avg_clarity": safe_mean(group["edge_clarity_score"]),
            "avg_conflict": safe_mean(group["conflict_score"]),
            "long_permission_rate": safe_mean(group["long_permission_flag"]),
            "sell_derisk_permission_rate": safe_mean(group["sell_derisk_permission_flag"]),
            "confirmation_needed_rate": safe_mean(group["confirmation_needed_flag"]),
            "invalidation_active_rate": safe_mean(group["invalidation_active_flag"]),
            "block_action_rate": safe_mean(group["block_action_flag"]),
        }
        for metric, value in metrics.items():
            rows.append(
                {
                    "summary_type": "rule_state_metrics",
                    "group": state,
                    "metric": metric,
                    "value": value,
                }
            )

    mapping = (
        frame.groupby(["rule_state", "operational_state"], sort=True)
        .size()
        .reset_index(name="row_count")
    )
    rule_totals = frame.groupby("rule_state").size().to_dict()
    for row in mapping.itertuples(index=False):
        rows.append(
            {
                "summary_type": "operational_mapping",
                "group": f"{row.rule_state}__{row.operational_state}",
                "metric": "row_count",
                "value": float(row.row_count),
            }
        )
        rows.append(
            {
                "summary_type": "operational_mapping",
                "group": f"{row.rule_state}__{row.operational_state}",
                "metric": "share_within_rule_state",
                "value": float(row.row_count / rule_totals[row.rule_state]),
            }
        )

    return pd.DataFrame(rows)


def output_columns(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "close",
        "split",
        "decision_state",
        "playbook_label",
        "playbook_attention_level",
        "operational_state",
        "operational_bias",
        "readiness_flag",
        "caution_flag",
        "invalidation_flag",
        "stand_aside_flag",
        "operational_state_age_days",
        "operational_state_run_length_days",
        "rule_state",
        "long_permission_flag",
        "sell_derisk_permission_flag",
        "confirmation_needed_flag",
        "invalidation_active_flag",
        "block_action_flag",
        "rule_is_permission",
        "rule_is_block",
        "rule_state_run_id",
        "rule_state_age_days",
        "rule_state_run_length_days",
        "rule_note",
        "promoted_buy_timing_score",
        "promoted_sell_timing_score",
        "timing_score_spread",
        "edge_clarity_score",
        "conflict_score",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
        "dist_to_current_down_swing_low_pct",
        "dist_to_current_up_swing_high_pct",
    ]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Rule-layer output is missing required columns: {missing}")
    return frame.loc[:, columns].copy()


def validate_output(frame: pd.DataFrame) -> None:
    if frame["date"].duplicated().any():
        raise ValueError("Rule layer contains duplicate dates.")
    allowed = {
        "LONG_ELIGIBLE",
        "SELL_ELIGIBLE",
        "AWAIT_CONFIRMATION",
        "BLOCKED_BY_CONFLICT",
        "BLOCKED_NO_EDGE",
        "INVALIDATED",
    }
    unexpected = sorted(set(frame["rule_state"].dropna()) - allowed)
    if unexpected:
        raise ValueError(f"Unexpected rule states: {unexpected}")
    flag_columns = [
        "long_permission_flag",
        "sell_derisk_permission_flag",
        "confirmation_needed_flag",
        "invalidation_active_flag",
        "block_action_flag",
        "rule_is_permission",
        "rule_is_block",
    ]
    for column in flag_columns:
        values = set(pd.to_numeric(frame[column], errors="coerce").dropna().astype(int))
        if not values.issubset({0, 1}):
            raise ValueError(f"{column} must be binary, found {sorted(values)}")
    if (frame["long_permission_flag"] & frame["sell_derisk_permission_flag"]).any():
        raise ValueError("A row cannot have both long and sell/de-risk permission.")


def pivot_summary(summary: pd.DataFrame) -> pd.DataFrame:
    return (
        summary.loc[summary["summary_type"].eq("rule_state_metrics")]
        .pivot_table(index="group", columns="metric", values="value", aggfunc="first")
        .reset_index()
        .rename(columns={"group": "rule_state"})
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


def render_markdown(frame: pd.DataFrame, summary: pd.DataFrame) -> str:
    state_table = pivot_summary(summary).sort_values("row_share", ascending=False)
    display = state_table[
        [
            "rule_state",
            "row_count",
            "row_share",
            "avg_run_length_days",
            "buy_zone_5_rate",
            "sell_zone_5_rate",
            "avg_clarity",
            "avg_conflict",
            "block_action_rate",
        ]
    ].copy()
    for column in ["row_share", "buy_zone_5_rate", "sell_zone_5_rate", "block_action_rate"]:
        display[column] = display[column].map(lambda value: pct(float(value)))
    for column in ["row_count", "avg_run_length_days", "avg_clarity", "avg_conflict"]:
        display[column] = display[column].map(lambda value: number(float(value)))

    mapping = (
        frame.groupby(["rule_state", "operational_state"], sort=True)
        .size()
        .reset_index(name="row_count")
    )
    totals = frame.groupby("rule_state").size().to_dict()
    mapping["share_within_rule_state"] = mapping.apply(
        lambda row: row["row_count"] / totals[row["rule_state"]], axis=1
    )
    mapping_display = mapping.copy()
    mapping_display["share_within_rule_state"] = mapping_display["share_within_rule_state"].map(
        lambda value: pct(float(value))
    )

    latest = frame.iloc[-1]
    age_unit = "day" if MIN_ELIGIBLE_AGE_DAYS == 1 else "days"
    lines = [
        "# SAFE v4.0 Minimal Rule Layer",
        "",
        "## Purpose",
        "",
        "This layer translates operational states into explicit structural permissions, waits, blocks, and invalidations. "
        "It does not define order execution, entries/exits, stops, position sizing, portfolio logic, PnL, or backtests.",
        "",
        "## Inputs",
        "",
        "- Source: `out/swing_bottom/strategy_translation_layer.csv`",
        "- Uses: operational state, operational bias, readiness flag, caution flag, invalidation flag, stand-aside flag, and operational-state persistence.",
        "",
        "## Rule Taxonomy",
        "",
        f"- `LONG_ELIGIBLE`: active long context with readiness, no caution, long bias, and operational-state age >= {MIN_ELIGIBLE_AGE_DAYS} {age_unit}.",
        f"- `SELL_ELIGIBLE`: active sell/de-risk context with readiness, no caution, sell bias, and operational-state age >= {MIN_ELIGIBLE_AGE_DAYS} {age_unit}.",
        "- `AWAIT_CONFIRMATION`: context exists but eligibility or persistence requirements are not satisfied.",
        "- `BLOCKED_BY_CONFLICT`: conflict/stand-aside structure blocks directional action.",
        "- `BLOCKED_NO_EDGE`: no structural edge is present.",
        "- `INVALIDATED`: a previously favorable context has broken.",
        "",
        "## Rule-State Summary",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Operational Mapping",
        "",
        markdown_table(mapping_display, ["rule_state", "operational_state", "row_count", "share_within_rule_state"]),
        "",
        "## Transition Logic",
        "",
        "The intended progression is blocked/no-edge -> await confirmation -> eligible. "
        "Eligible contexts can revert to await confirmation or become invalidated when the operational layer detects conflict, no edge, or a broken prior context. "
        "This is a permission/block layer only; it deliberately stops before trade construction.",
        "",
        "## Latest Rule State",
        "",
        f"- Date: `{latest['date']}`",
        f"- Rule state: `{latest['rule_state']}`",
        f"- Long permission: `{int(latest['long_permission_flag'])}`",
        f"- Sell/de-risk permission: `{int(latest['sell_derisk_permission_flag'])}`",
        f"- Block action: `{int(latest['block_action_flag'])}`",
        f"- Note: {latest['rule_note']}",
        "",
        "## Interpretation",
        "",
        "The rule layer is a meaningful bridge toward later strategy design because it separates structural permission from confirmation, block, and invalidation. "
        "It remains non-executable: permission means a later strategy may consider that side, not that the system should place an order.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/rule_layer.csv`",
        "- `out/swing_bottom/rule_layer_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> None:
    operational = load_strategy_translation(args.strategy_translation_csv)
    rules = add_rule_columns(operational)
    output = output_columns(rules)
    validate_output(output)
    summary = build_summary(output)
    markdown = render_markdown(output, summary)

    out_csv = Path(args.out_csv)
    out_summary = Path(args.out_summary_csv)
    out_md = Path(args.out_md)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(out_csv, index=False)
    summary.to_csv(out_summary, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_summary}")
    print(f"Wrote {out_md}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
