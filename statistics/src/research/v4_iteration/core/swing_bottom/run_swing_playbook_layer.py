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
    DEFAULT_SWING_DECISION_LAYER_CSV_PATH,
    DEFAULT_SWING_PLAYBOOK_LAYER_CSV_PATH,
    DEFAULT_SWING_PLAYBOOK_LAYER_SUMMARY_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bottom.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
)


DEFAULT_SWING_PLAYBOOK_LAYER_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_SWING_PLAYBOOK_LAYER.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SAFE swing playbook layer from decision states.")
    parser.add_argument(
        "--decision-layer-csv",
        default=str(DEFAULT_SWING_DECISION_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_decision_layer.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_SWING_PLAYBOOK_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_playbook_layer.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_SWING_PLAYBOOK_LAYER_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_playbook_layer_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SWING_PLAYBOOK_LAYER_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_SWING_PLAYBOOK_LAYER.md",
    )
    return parser.parse_args()


def load_decision_layer(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path).sort_values("date").reset_index(drop=True)
    required = [
        "date",
        "close",
        "decision_state",
        "promoted_buy_timing_score",
        "promoted_sell_timing_score",
        "timing_score_spread",
        "timing_score_intensity",
        "timing_score_overlap",
        "buy_dominance_score",
        "sell_dominance_score",
        "edge_clarity_score",
        "conflict_score",
        "decision_state_age_days",
        "decision_state_run_length_days",
        "live_swing_direction",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Decision-layer input is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Decision-layer input contains duplicate dates.")
    return frame


def attention_level(label: str, clarity: float, conflict: float, age: int) -> str:
    if label in {"ACCUMULATION_WATCH", "DISTRIBUTION_WATCH"}:
        if clarity >= 0.30 and conflict < 0.25:
            return "high"
        return "medium"
    if label == "HIGH_CONFLICT":
        return "high" if conflict >= 0.25 else "medium"
    if label == "TRANSITION_WATCH":
        return "medium"
    if label == "NO_ACTION":
        return "low" if age < 5 else "very_low"
    return "medium"


def maturity_label(age: int, run_length: int) -> str:
    if age <= 1:
        return "early"
    if run_length >= 4 and age >= max(3, int(np.ceil(run_length * 0.65))):
        return "mature"
    return "developing"


def classify_playbook(row: pd.Series) -> tuple[str, str, str, str]:
    decision_state = str(row["decision_state"])
    clarity = float(row["edge_clarity_score"])
    conflict = float(row["conflict_score"])
    buy = float(row["promoted_buy_timing_score"])
    sell = float(row["promoted_sell_timing_score"])
    spread = float(row["timing_score_spread"])
    age = int(row["decision_state_age_days"])
    run_length = int(row["decision_state_run_length_days"])
    maturity = maturity_label(age, run_length)

    if decision_state == "BUY_SETUP":
        if clarity >= 0.25 and conflict < 0.22:
            label = "ACCUMULATION_WATCH"
            bias = "buy_side"
            note = f"Buy-side timing favored; {maturity} accumulation watch, not an entry trigger."
        else:
            label = "TRANSITION_WATCH"
            bias = "buy_lean"
            note = f"Buy setup present but clarity is modest or conflict is elevated; monitor for cleaner structure."
    elif decision_state == "SELL_SETUP":
        if clarity >= 0.25 and conflict < 0.24:
            label = "DISTRIBUTION_WATCH"
            bias = "sell_side"
            note = f"Sell-side timing favored; {maturity} distribution watch, not an exit rule."
        else:
            label = "TRANSITION_WATCH"
            bias = "sell_lean"
            note = "Sell setup present but clarity is modest or conflict is elevated; treat as caution context."
    elif decision_state == "CONFLICT_OVERLAP":
        label = "HIGH_CONFLICT"
        bias = "mixed"
        note = "Buy and sell timing are both elevated; mixed structure, avoid single-sided interpretation."
    elif decision_state == "TRANSITION_UNCLEAR":
        label = "TRANSITION_WATCH"
        bias = "mixed" if abs(spread) < 0.10 else ("buy_lean" if buy > sell else "sell_lean")
        note = "Timing is forming but not cleanly separated; watch for state resolution."
    elif decision_state == "NEUTRAL_NO_EDGE":
        label = "NO_ACTION"
        bias = "neutral"
        note = "No clear swing-timing edge; remain structurally inactive."
    else:
        label = "TRANSITION_WATCH"
        bias = "mixed"
        note = "Unrecognized decision state; treat as unclear."

    attention = attention_level(label, clarity, conflict, age)
    return label, bias, attention, note


def add_playbook_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    classified = out.apply(classify_playbook, axis=1, result_type="expand")
    classified.columns = ["playbook_label", "playbook_bias", "playbook_attention_level", "playbook_note"]
    out = pd.concat([out, classified], axis=1)
    playbook_change = out["playbook_label"].ne(out["playbook_label"].shift()).fillna(True)
    out["playbook_run_id"] = playbook_change.cumsum().astype(int)
    out["playbook_age_days"] = out.groupby("playbook_run_id").cumcount() + 1
    out["playbook_run_length_days"] = out.groupby("playbook_run_id")["date"].transform("size").astype(int)
    out["playbook_is_clear"] = out["playbook_label"].isin(["ACCUMULATION_WATCH", "DISTRIBUTION_WATCH"]).astype(int)
    out["playbook_is_caution"] = out["playbook_label"].isin(["HIGH_CONFLICT", "TRANSITION_WATCH"]).astype(int)
    return out


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_rows = len(frame)
    run_table = (
        frame.loc[:, ["playbook_label", "playbook_run_id", "playbook_run_length_days"]]
        .drop_duplicates("playbook_run_id")
        .copy()
    )

    for label, group in frame.groupby("playbook_label", sort=True):
        runs = run_table.loc[run_table["playbook_label"].eq(label)]
        rows.extend(
            [
                {
                    "summary_type": "playbook_prevalence",
                    "group": label,
                    "metric": "row_count",
                    "value": float(len(group)),
                },
                {
                    "summary_type": "playbook_prevalence",
                    "group": label,
                    "metric": "row_share",
                    "value": float(len(group) / total_rows) if total_rows else np.nan,
                },
                {
                    "summary_type": "playbook_prevalence",
                    "group": label,
                    "metric": "run_count",
                    "value": float(len(runs)),
                },
                {
                    "summary_type": "playbook_prevalence",
                    "group": label,
                    "metric": "avg_run_length_days",
                    "value": float(pd.to_numeric(runs["playbook_run_length_days"], errors="coerce").mean()),
                },
                {
                    "summary_type": "playbook_quality",
                    "group": label,
                    "metric": "buy_zone_5_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_BUY_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "playbook_quality",
                    "group": label,
                    "metric": "buy_zone_3_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_BUY_STRICT_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "playbook_quality",
                    "group": label,
                    "metric": "sell_zone_5_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_SELL_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "playbook_quality",
                    "group": label,
                    "metric": "sell_zone_3_rate",
                    "value": float(pd.to_numeric(group[DEFAULT_SELL_STRICT_TARGET], errors="coerce").fillna(0).mean()),
                },
                {
                    "summary_type": "playbook_scores",
                    "group": label,
                    "metric": "avg_clarity",
                    "value": float(pd.to_numeric(group["edge_clarity_score"], errors="coerce").mean()),
                },
                {
                    "summary_type": "playbook_scores",
                    "group": label,
                    "metric": "avg_conflict",
                    "value": float(pd.to_numeric(group["conflict_score"], errors="coerce").mean()),
                },
            ]
        )

    mapping = (
        frame.groupby(["playbook_label", "decision_state"], sort=True)
        .size()
        .reset_index(name="row_count")
    )
    for row in mapping.itertuples(index=False):
        rows.append(
            {
                "summary_type": "decision_mapping",
                "group": f"{row.playbook_label}__{row.decision_state}",
                "metric": "row_count",
                "value": float(row.row_count),
            }
        )
    return pd.DataFrame(rows)


def summary_value(summary: pd.DataFrame, summary_type: str, group: str, metric: str) -> float:
    matched = summary.loc[
        summary["summary_type"].eq(summary_type)
        & summary["group"].eq(group)
        & summary["metric"].eq(metric)
    ]
    if matched.empty:
        return np.nan
    return float(matched.iloc[0]["value"])


def render_markdown(frame: pd.DataFrame, summary: pd.DataFrame) -> str:
    label_order = ["ACCUMULATION_WATCH", "DISTRIBUTION_WATCH", "HIGH_CONFLICT", "TRANSITION_WATCH", "NO_ACTION"]

    def label_line(label: str) -> str:
        share = summary_value(summary, "playbook_prevalence", label, "row_share")
        avg_run = summary_value(summary, "playbook_prevalence", label, "avg_run_length_days")
        buy5 = summary_value(summary, "playbook_quality", label, "buy_zone_5_rate")
        sell5 = summary_value(summary, "playbook_quality", label, "sell_zone_5_rate")
        clarity = summary_value(summary, "playbook_scores", label, "avg_clarity")
        conflict = summary_value(summary, "playbook_scores", label, "avg_conflict")
        if pd.isna(share):
            return f"- `{label}`: not observed"
        return (
            f"- `{label}`: share `{share:.3f}`, avg run `{avg_run:.2f}` days, "
            f"buy-zone 5% `{buy5:.3f}`, sell-zone 5% `{sell5:.3f}`, "
            f"clarity `{clarity:.3f}`, conflict `{conflict:.3f}`"
        )

    mapping = (
        frame.groupby(["playbook_label", "decision_state"], sort=True)
        .size()
        .reset_index(name="row_count")
        .sort_values(["playbook_label", "row_count"], ascending=[True, False])
    )
    mapping_lines = [
        f"- `{row.playbook_label}` <- `{row.decision_state}`: `{int(row.row_count)}` rows"
        for row in mapping.itertuples(index=False)
    ]

    current = frame.iloc[-1]
    lines = [
        "# SAFE v4.0 Swing Playbook Layer",
        "",
        "## Purpose",
        "",
        "- maps decision states into human-readable operational playbook interpretations",
        "- remains structural: no orders, entries, exits, position sizing, or PnL logic",
        "- designed for dashboard and daily-report interpretation",
        "",
        "## Playbook Labels",
        "",
        "- `ACCUMULATION_WATCH`: buy-side swing-low opportunity is structurally favored; monitor, not a trade trigger",
        "- `DISTRIBUTION_WATCH`: sell-side swing-high opportunity is structurally favored; monitor, not an exit rule",
        "- `HIGH_CONFLICT`: buy and sell timing overlap; mixed structure requires caution",
        "- `TRANSITION_WATCH`: timing is forming or resolving, but clarity is not sufficient",
        "- `NO_ACTION`: no clear swing-timing edge",
        "",
        "## Mapping Logic",
        "",
        "- uses `decision_state`, promoted buy/sell timing scores, `edge_clarity_score`, `conflict_score`, and state persistence",
        "- clear buy/sell decision states map to watch labels only when clarity is sufficient and conflict is controlled",
        "- conflict and unclear decision states become explicit caution labels",
        "- neutral states become inactivity labels, with persistent neutral periods marked as very-low attention",
        "",
        "## Playbook Prevalence And Quality",
        "",
        *[label_line(label) for label in label_order],
        "",
        "## Decision-State Mapping",
        "",
        *mapping_lines,
        "",
        "## Current Row",
        "",
        f"- date: `{current['date']}`",
        f"- close: `{float(current['close']):.2f}`",
        f"- decision state: `{current['decision_state']}`",
        f"- playbook label: `{current['playbook_label']}`",
        f"- attention: `{current['playbook_attention_level']}`",
        f"- note: {current['playbook_note']}",
        "",
        "## Interpretive Usefulness",
        "",
        "- the playbook layer adds stable human-readable bias, attention level, and note fields on top of raw decision states",
        "- it separates watch states from caution states and inactivity states without creating trade mechanics",
        "- this layer is suitable for dashboard review and daily structural interpretation; later strategy work must validate any operational use separately",
    ]
    return "\n".join(lines) + "\n"


def build_export(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "close",
        "split",
        "decision_state",
        "playbook_label",
        "playbook_bias",
        "playbook_attention_level",
        "playbook_note",
        "promoted_buy_timing_score",
        "promoted_sell_timing_score",
        "timing_score_spread",
        "timing_score_intensity",
        "timing_score_overlap",
        "buy_dominance_score",
        "sell_dominance_score",
        "edge_clarity_score",
        "conflict_score",
        "score_interaction_bucket",
        "live_swing_direction",
        "current_confirmed_swing_id",
        "current_confirmed_swing_direction",
        "decision_state_age_days",
        "decision_state_run_length_days",
        "playbook_run_id",
        "playbook_age_days",
        "playbook_run_length_days",
        "playbook_is_clear",
        "playbook_is_caution",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
        "dist_to_current_down_swing_low_pct",
        "dist_to_current_up_swing_high_pct",
    ]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Cannot export playbook layer; missing columns: {missing}")
    return frame.loc[:, columns].copy()


def main() -> None:
    args = parse_args()
    decision = load_decision_layer(args.decision_layer_csv)
    playbook = add_playbook_columns(decision)
    summary = build_summary(playbook)
    export = build_export(playbook)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(out_csv, index=False)

    out_summary = Path(args.out_summary_csv)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_summary, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(export, summary), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_summary}")
    print(f"Wrote: {out_md}")
    print(f"Rows written: {len(export)}")


if __name__ == "__main__":
    main()
