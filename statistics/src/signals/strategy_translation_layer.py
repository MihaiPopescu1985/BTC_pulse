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
    DEFAULT_STRATEGY_TRANSLATION_CSV_PATH,
    DEFAULT_STRATEGY_TRANSLATION_SUMMARY_CSV_PATH,
    DEFAULT_SWING_PLAYBOOK_LAYER_CSV_PATH,
    STATISTICS_DIR,
)
from src.signals.reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
)


DEFAULT_STRATEGY_TRANSLATION_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_STRATEGY_TRANSLATION_LAYER.md"
)

LONG_MIN_CLARITY = 0.30
SELL_MIN_CLARITY = 0.30
LONG_MAX_CONFLICT = 0.22
SELL_MAX_CONFLICT = 0.24
MIN_ABS_SPREAD = 0.15

REQUIRED_PLAYBOOK_COLUMNS = [
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
    "playbook_age_days",
    "playbook_run_length_days",
    DEFAULT_BUY_TARGET,
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    "dist_to_current_down_swing_low_pct",
    "dist_to_current_up_swing_high_pct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SAFE strategy translation layer from playbook states.")
    parser.add_argument(
        "--playbook-layer-csv",
        default=str(DEFAULT_SWING_PLAYBOOK_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_playbook_layer.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_STRATEGY_TRANSLATION_CSV_PATH),
        help="Default: ../out/swing_bottom/strategy_translation_layer.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_STRATEGY_TRANSLATION_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/strategy_translation_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_STRATEGY_TRANSLATION_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_STRATEGY_TRANSLATION_LAYER.md",
    )
    return parser.parse_args()


def load_playbook(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path).sort_values("date").reset_index(drop=True)
    missing = [column for column in REQUIRED_PLAYBOOK_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Playbook layer is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Playbook layer contains duplicate dates.")
    return frame


def is_long_ready(row: pd.Series) -> bool:
    return bool(
        row["playbook_label"] == "ACCUMULATION_WATCH"
        and row["playbook_attention_level"] == "high"
        and float(row["edge_clarity_score"]) >= LONG_MIN_CLARITY
        and float(row["conflict_score"]) <= LONG_MAX_CONFLICT
        and float(row["timing_score_spread"]) >= MIN_ABS_SPREAD
    )


def is_sell_ready(row: pd.Series) -> bool:
    return bool(
        row["playbook_label"] == "DISTRIBUTION_WATCH"
        and row["playbook_attention_level"] == "high"
        and float(row["edge_clarity_score"]) >= SELL_MIN_CLARITY
        and float(row["conflict_score"]) <= SELL_MAX_CONFLICT
        and float(row["timing_score_spread"]) <= -MIN_ABS_SPREAD
    )


def raw_translation(row: pd.Series) -> tuple[str, str, int, int, int, str]:
    label = str(row["playbook_label"])
    clarity = float(row["edge_clarity_score"])
    conflict = float(row["conflict_score"])
    spread = float(row["timing_score_spread"])
    attention = str(row["playbook_attention_level"])
    age = int(row["playbook_age_days"])

    if is_long_ready(row):
        return (
            "LONG_CONTEXT_ACTIVE",
            "long_side",
            1,
            0,
            0,
            "Long-side context is operationally allowed for later setup evaluation; no entry rule is implied.",
        )
    if is_sell_ready(row):
        return (
            "SELL_CONTEXT_ACTIVE",
            "sell_side",
            1,
            0,
            0,
            "Sell/de-risk context is operationally active for later evaluation; no exit rule is implied.",
        )
    if label == "ACCUMULATION_WATCH":
        note = "Accumulation watch is forming, but clarity, conflict, or score spread is not strong enough for active context."
        return ("WAIT_CONFIRMATION", "long_lean", 0, 0, 0, note)
    if label == "DISTRIBUTION_WATCH":
        note = "Distribution watch is forming, but clarity, conflict, or score spread is not strong enough for active context."
        return ("WAIT_CONFIRMATION", "sell_lean", 0, 0, 0, note)
    if label == "TRANSITION_WATCH":
        if spread >= MIN_ABS_SPREAD and clarity >= 0.20 and conflict < 0.30:
            bias = "long_lean"
        elif spread <= -MIN_ABS_SPREAD and clarity >= 0.20 and conflict < 0.30:
            bias = "sell_lean"
        else:
            bias = "mixed"
        return (
            "WAIT_CONFIRMATION",
            bias,
            0,
            0,
            0,
            "Structure is forming but not confirmed; defer directional interpretation.",
        )
    if label == "HIGH_CONFLICT":
        caution = 1
        note = "Buy and sell timing conflict; stand aside from directional interpretation."
        return ("STAND_ASIDE_CONFLICT", "mixed", 0, caution, 1, note)
    if label == "NO_ACTION":
        note = "No structural swing edge; stand aside."
        return ("STAND_ASIDE_NO_EDGE", "neutral", 0, 0, 0, note)

    note = f"Unrecognized playbook label with attention={attention}, clarity={clarity:.3f}, conflict={conflict:.3f}, age={age}."
    return ("WAIT_CONFIRMATION", "mixed", 0, 1, 0, note)


def add_strategy_translation(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    translated = out.apply(raw_translation, axis=1, result_type="expand")
    translated.columns = [
        "raw_operational_state",
        "raw_operational_bias",
        "raw_readiness_flag",
        "raw_caution_flag",
        "raw_stand_aside_flag",
        "raw_operational_note",
    ]
    out = pd.concat([out, translated], axis=1)

    states: list[str] = []
    biases: list[str] = []
    readiness: list[int] = []
    caution: list[int] = []
    invalidation: list[int] = []
    stand_aside: list[int] = []
    notes: list[str] = []
    previous_favorable_bias = "neutral"

    for row in out.itertuples(index=False):
        raw_state = str(row.raw_operational_state)
        raw_bias = str(row.raw_operational_bias)
        raw_note = str(row.raw_operational_note)
        invalidated = 0
        state = raw_state
        bias = raw_bias
        note = raw_note
        current_caution = int(row.raw_caution_flag)
        current_stand_aside = int(row.raw_stand_aside_flag)
        current_ready = int(row.raw_readiness_flag)

        if previous_favorable_bias in {"long_side", "sell_side", "long_lean", "sell_lean"}:
            conflict_break = raw_state == "STAND_ASIDE_CONFLICT"
            no_edge_break = raw_state == "STAND_ASIDE_NO_EDGE"
            opposite_active = (
                previous_favorable_bias.startswith("long")
                and raw_state == "SELL_CONTEXT_ACTIVE"
            ) or (
                previous_favorable_bias.startswith("sell")
                and raw_state == "LONG_CONTEXT_ACTIVE"
            )
            if conflict_break or no_edge_break or opposite_active:
                invalidated = 1
                current_caution = 1
                current_stand_aside = 1 if raw_state.startswith("STAND_ASIDE") else current_stand_aside
                if conflict_break:
                    state = "CONTEXT_INVALIDATED"
                    bias = "mixed"
                    note = "Previously favorable context is invalidated by high conflict."
                elif no_edge_break:
                    state = "CONTEXT_INVALIDATED"
                    bias = "neutral"
                    note = "Previously favorable context faded into no-edge structure."
                else:
                    note = "Previously favorable context flipped to the opposite side; treat the old context as invalidated."

        states.append(state)
        biases.append(bias)
        readiness.append(current_ready)
        caution.append(current_caution)
        invalidation.append(invalidated)
        stand_aside.append(current_stand_aside)
        notes.append(note)

        if state in {"LONG_CONTEXT_ACTIVE", "SELL_CONTEXT_ACTIVE", "WAIT_CONFIRMATION"}:
            previous_favorable_bias = bias
        elif state in {"STAND_ASIDE_CONFLICT", "STAND_ASIDE_NO_EDGE", "CONTEXT_INVALIDATED"}:
            previous_favorable_bias = "neutral"

    out["operational_state"] = states
    out["operational_bias"] = biases
    out["readiness_flag"] = readiness
    out["caution_flag"] = caution
    out["invalidation_flag"] = invalidation
    out["stand_aside_flag"] = stand_aside
    out["operational_note"] = notes
    out["operational_is_active_context"] = out["operational_state"].isin(
        ["LONG_CONTEXT_ACTIVE", "SELL_CONTEXT_ACTIVE"]
    ).astype(int)

    state_change = out["operational_state"].ne(out["operational_state"].shift()).fillna(True)
    out["operational_state_run_id"] = state_change.cumsum().astype(int)
    out["operational_state_age_days"] = out.groupby("operational_state_run_id").cumcount() + 1
    out["operational_state_run_length_days"] = (
        out.groupby("operational_state_run_id")["date"].transform("size").astype(int)
    )
    return out


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_rows = len(frame)
    run_table = (
        frame.loc[:, ["operational_state", "operational_state_run_id", "operational_state_run_length_days"]]
        .drop_duplicates("operational_state_run_id")
        .copy()
    )

    for state, group in frame.groupby("operational_state", sort=True):
        runs = run_table.loc[run_table["operational_state"].eq(state)]
        rows.extend(
            [
                {
                    "summary_type": "operational_prevalence",
                    "group": state,
                    "metric": "row_count",
                    "value": float(len(group)),
                },
                {
                    "summary_type": "operational_prevalence",
                    "group": state,
                    "metric": "row_share",
                    "value": float(len(group) / total_rows) if total_rows else np.nan,
                },
                {
                    "summary_type": "operational_prevalence",
                    "group": state,
                    "metric": "run_count",
                    "value": float(len(runs)),
                },
                {
                    "summary_type": "operational_prevalence",
                    "group": state,
                    "metric": "avg_run_length_days",
                    "value": safe_mean(runs["operational_state_run_length_days"]),
                },
                {
                    "summary_type": "operational_quality",
                    "group": state,
                    "metric": "buy_zone_5_rate",
                    "value": safe_mean(group[DEFAULT_BUY_TARGET]),
                },
                {
                    "summary_type": "operational_quality",
                    "group": state,
                    "metric": "buy_zone_3_rate",
                    "value": safe_mean(group[DEFAULT_BUY_STRICT_TARGET]),
                },
                {
                    "summary_type": "operational_quality",
                    "group": state,
                    "metric": "sell_zone_5_rate",
                    "value": safe_mean(group[DEFAULT_SELL_TARGET]),
                },
                {
                    "summary_type": "operational_quality",
                    "group": state,
                    "metric": "sell_zone_3_rate",
                    "value": safe_mean(group[DEFAULT_SELL_STRICT_TARGET]),
                },
                {
                    "summary_type": "operational_scores",
                    "group": state,
                    "metric": "avg_clarity",
                    "value": safe_mean(group["edge_clarity_score"]),
                },
                {
                    "summary_type": "operational_scores",
                    "group": state,
                    "metric": "avg_conflict",
                    "value": safe_mean(group["conflict_score"]),
                },
                {
                    "summary_type": "operational_flags",
                    "group": state,
                    "metric": "readiness_rate",
                    "value": safe_mean(group["readiness_flag"]),
                },
                {
                    "summary_type": "operational_flags",
                    "group": state,
                    "metric": "caution_rate",
                    "value": safe_mean(group["caution_flag"]),
                },
                {
                    "summary_type": "operational_flags",
                    "group": state,
                    "metric": "invalidation_rate",
                    "value": safe_mean(group["invalidation_flag"]),
                },
            ]
        )

    mapping = (
        frame.groupby(["operational_state", "playbook_label"], sort=True)
        .size()
        .reset_index(name="row_count")
    )
    state_totals = frame.groupby("operational_state").size().to_dict()
    for row in mapping.itertuples(index=False):
        rows.append(
            {
                "summary_type": "playbook_mapping",
                "group": f"{row.operational_state}__{row.playbook_label}",
                "metric": "row_count",
                "value": float(row.row_count),
            }
        )
        rows.append(
            {
                "summary_type": "playbook_mapping",
                "group": f"{row.operational_state}__{row.playbook_label}",
                "metric": "share_within_operational_state",
                "value": float(row.row_count / state_totals[row.operational_state]),
            }
        )

    return pd.DataFrame(rows)


def pivot_summary(summary: pd.DataFrame) -> pd.DataFrame:
    return (
        summary.loc[summary["summary_type"].isin(["operational_prevalence", "operational_quality", "operational_scores"])]
        .pivot_table(index="group", columns="metric", values="value", aggfunc="first")
        .reset_index()
        .rename(columns={"group": "operational_state"})
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
    state_table = pivot_summary(summary)
    state_table = state_table.sort_values("row_share", ascending=False)
    display = state_table[
        [
            "operational_state",
            "row_count",
            "row_share",
            "avg_run_length_days",
            "buy_zone_5_rate",
            "sell_zone_5_rate",
            "avg_clarity",
            "avg_conflict",
        ]
    ].copy()
    for column in ["row_share", "buy_zone_5_rate", "sell_zone_5_rate"]:
        display[column] = display[column].map(lambda value: pct(float(value)))
    for column in ["row_count", "avg_run_length_days", "avg_clarity", "avg_conflict"]:
        display[column] = display[column].map(lambda value: number(float(value)))

    mapping = (
        frame.groupby(["operational_state", "playbook_label"], sort=True)
        .size()
        .reset_index(name="row_count")
    )
    totals = frame.groupby("operational_state").size().to_dict()
    mapping["share_within_state"] = mapping.apply(
        lambda row: row["row_count"] / totals[row["operational_state"]], axis=1
    )
    mapping_display = mapping.copy()
    mapping_display["share_within_state"] = mapping_display["share_within_state"].map(lambda value: pct(float(value)))

    latest = frame.iloc[-1]
    lines = [
        "# SAFE v4.0 Strategy Translation Layer",
        "",
        "## Purpose",
        "",
        "This layer translates the promoted playbook into operational structural states: active context, waiting, conflict, no edge, and invalidation. "
        "It does not define orders, entries, exits, stops, position sizing, portfolio rules, PnL, or backtests.",
        "",
        "## Inputs",
        "",
        "- Source: `out/swing_bottom/swing_playbook_layer.csv`",
        "- Uses: playbook label, attention level, edge clarity, conflict score, buy/sell timing spread, and playbook persistence fields.",
        "",
        "## Operational Taxonomy",
        "",
        f"- `LONG_CONTEXT_ACTIVE`: `ACCUMULATION_WATCH` with high attention, clarity >= {LONG_MIN_CLARITY:.2f}, conflict <= {LONG_MAX_CONFLICT:.2f}, and buy-dominant spread >= {MIN_ABS_SPREAD:.2f}.",
        f"- `SELL_CONTEXT_ACTIVE`: `DISTRIBUTION_WATCH` with high attention, clarity >= {SELL_MIN_CLARITY:.2f}, conflict <= {SELL_MAX_CONFLICT:.2f}, and sell-dominant spread <= -{MIN_ABS_SPREAD:.2f}.",
        "- `WAIT_CONFIRMATION`: directional or transition context exists, but active-context requirements are not met.",
        "- `STAND_ASIDE_CONFLICT`: high conflict/overlap invalidates directional interpretation.",
        "- `STAND_ASIDE_NO_EDGE`: no structural edge is present.",
        "- `CONTEXT_INVALIDATED`: a previously favorable context breaks into conflict/no-edge or flips to the opposite side.",
        "",
        "## Operational-State Summary",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Playbook Mapping",
        "",
        markdown_table(mapping_display, ["operational_state", "playbook_label", "row_count", "share_within_state"]),
        "",
        "## Transition Logic",
        "",
        "The layer is intentionally state-machine-like. Favorable playbook states move into `WAIT_CONFIRMATION` first unless clarity and spread are strong enough for an active context. "
        "Active contexts can fall back to wait, stand aside, or `CONTEXT_INVALIDATED` when conflict rises, the edge disappears, or the opposite side becomes dominant. "
        "This captures forming, active, conflicted, and absent context without turning the layer into execution logic.",
        "",
        "## Latest State",
        "",
        f"- Date: `{latest['date']}`",
        f"- Operational state: `{latest['operational_state']}`",
        f"- Operational bias: `{latest['operational_bias']}`",
        f"- Note: {latest['operational_note']}",
        "",
        "## Interpretation",
        "",
        "This layer is a useful bridge from human-readable playbook labels toward later strategy design because it separates permission, deferral, caution, and invalidation. "
        "It should be treated as a structural translation layer only. Later strategy work can consume these states, but this report makes no claim about tradability or execution performance.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/strategy_translation_layer.csv`",
        "- `out/swing_bottom/strategy_translation_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def output_columns(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "close",
        "split",
        "decision_state",
        "playbook_label",
        "playbook_bias",
        "playbook_attention_level",
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
        "playbook_age_days",
        "playbook_run_length_days",
        "operational_state",
        "operational_bias",
        "readiness_flag",
        "caution_flag",
        "invalidation_flag",
        "stand_aside_flag",
        "operational_is_active_context",
        "operational_state_run_id",
        "operational_state_age_days",
        "operational_state_run_length_days",
        "operational_note",
        DEFAULT_BUY_TARGET,
        DEFAULT_BUY_STRICT_TARGET,
        DEFAULT_SELL_TARGET,
        DEFAULT_SELL_STRICT_TARGET,
        "dist_to_current_down_swing_low_pct",
        "dist_to_current_up_swing_high_pct",
    ]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Strategy translation output is missing required columns: {missing}")
    return frame.loc[:, columns].copy()


def validate_output(frame: pd.DataFrame) -> None:
    if frame["date"].duplicated().any():
        raise ValueError("Strategy translation output contains duplicate dates.")
    allowed_states = {
        "LONG_CONTEXT_ACTIVE",
        "SELL_CONTEXT_ACTIVE",
        "WAIT_CONFIRMATION",
        "STAND_ASIDE_CONFLICT",
        "STAND_ASIDE_NO_EDGE",
        "CONTEXT_INVALIDATED",
    }
    unexpected = sorted(set(frame["operational_state"].dropna()) - allowed_states)
    if unexpected:
        raise ValueError(f"Unexpected operational states: {unexpected}")
    flag_columns = ["readiness_flag", "caution_flag", "invalidation_flag", "stand_aside_flag"]
    for column in flag_columns:
        values = set(pd.to_numeric(frame[column], errors="coerce").dropna().astype(int))
        if not values.issubset({0, 1}):
            raise ValueError(f"{column} must be binary, found {sorted(values)}")


def run(args: argparse.Namespace) -> None:
    playbook = load_playbook(args.playbook_layer_csv)
    translated = add_strategy_translation(playbook)
    output = output_columns(translated)
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
