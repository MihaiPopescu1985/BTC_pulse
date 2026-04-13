from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import (
    DEFAULT_RULE_LAYER_CSV_PATH,
    DEFAULT_SIGNAL_LAYER_CSV_PATH,
    DEFAULT_SIGNAL_LAYER_SUMMARY_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.productive.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
)


DEFAULT_SIGNAL_LAYER_MD_PATH = STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_SIGNAL_LAYER.md"

REQUIRED_COLUMNS = [
    "date",
    "close",
    "split",
    "decision_state",
    "playbook_label",
    "operational_state",
    "operational_bias",
    "rule_state",
    "long_permission_flag",
    "sell_derisk_permission_flag",
    "confirmation_needed_flag",
    "invalidation_active_flag",
    "block_action_flag",
    "rule_is_permission",
    "rule_is_block",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SAFE signal realization layer from calibrated rule states.")
    parser.add_argument(
        "--rule-layer-csv",
        default=str(DEFAULT_RULE_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/rule_layer.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_SIGNAL_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_layer.csv",
    )
    parser.add_argument(
        "--out-summary-csv",
        default=str(DEFAULT_SIGNAL_LAYER_SUMMARY_CSV_PATH),
        help="Default: ../out/swing_bottom/signal_layer_summary.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SIGNAL_LAYER_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_SIGNAL_LAYER.md",
    )
    return parser.parse_args()


def load_rule_layer(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path).sort_values("date").reset_index(drop=True)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Rule layer is missing required columns: {missing}")
    if frame["date"].duplicated().any():
        raise ValueError("Rule layer contains duplicate dates.")
    return frame


def add_signal_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    states: list[str] = []
    sides: list[str] = []
    long_events: list[int] = []
    sell_events: list[int] = []
    continuation: list[int] = []
    reactivation: list[int] = []
    invalidation_events: list[int] = []
    active_flags: list[int] = []
    notes: list[str] = []

    active_side: str | None = None
    last_completed_side: str | None = None
    seen_side: set[str] = set()

    for row in out.itertuples(index=False):
        rule_state = str(row.rule_state)
        invalidation_active = int(row.invalidation_active_flag)
        long_permission = int(row.long_permission_flag)
        sell_permission = int(row.sell_derisk_permission_flag)

        signal_state = "NO_SIGNAL"
        signal_side = "none"
        long_event = 0
        sell_event = 0
        continuation_flag = 0
        reactivation_flag = 0
        invalidation_event = 0
        active_flag = 0
        note = "No discrete signal event."

        if invalidation_active and active_side is not None:
            signal_state = "SIGNAL_INVALIDATED"
            signal_side = active_side
            invalidation_event = 1
            note = f"Previously active {active_side} signal context is invalidated."
            last_completed_side = active_side
            active_side = None
        elif long_permission:
            signal_side = "long"
            active_flag = 1
            if active_side == "long":
                signal_state = "LONG_SIGNAL_ACTIVE"
                continuation_flag = 1
                note = "Long-side signal context remains active; no repeated new signal."
            else:
                signal_state = "LONG_SIGNAL_NEW"
                long_event = 1
                reactivation_flag = int("long" in seen_side or last_completed_side == "long")
                note = "New long-side structural signal event realized from eligible rule context."
                active_side = "long"
                seen_side.add("long")
        elif sell_permission:
            signal_side = "sell"
            active_flag = 1
            if active_side == "sell":
                signal_state = "SELL_SIGNAL_ACTIVE"
                continuation_flag = 1
                note = "Sell/de-risk signal context remains active; no repeated new signal."
            else:
                signal_state = "SELL_SIGNAL_NEW"
                sell_event = 1
                reactivation_flag = int("sell" in seen_side or last_completed_side == "sell")
                note = "New sell/de-risk structural signal event realized from eligible rule context."
                active_side = "sell"
                seen_side.add("sell")
        else:
            if active_side is not None:
                last_completed_side = active_side
            active_side = None
            if rule_state == "AWAIT_CONFIRMATION":
                note = "Rule layer is awaiting confirmation; no signal is realized."
            elif rule_state in {"BLOCKED_BY_CONFLICT", "BLOCKED_NO_EDGE", "INVALIDATED"}:
                note = "Rule layer blocks signal realization."

        states.append(signal_state)
        sides.append(signal_side)
        long_events.append(long_event)
        sell_events.append(sell_event)
        continuation.append(continuation_flag)
        reactivation.append(reactivation_flag)
        invalidation_events.append(invalidation_event)
        active_flags.append(active_flag)
        notes.append(note)

    out["signal_state"] = states
    out["signal_side"] = sides
    out["long_signal_event_flag"] = long_events
    out["sell_signal_event_flag"] = sell_events
    out["signal_continuation_flag"] = continuation
    out["signal_reactivation_flag"] = reactivation
    out["signal_invalidation_event_flag"] = invalidation_events
    out["signal_active_flag"] = active_flags
    out["signal_note"] = notes

    signal_context_key = out["signal_side"].where(out["signal_active_flag"].eq(1), "inactive")
    context_change = signal_context_key.ne(signal_context_key.shift()).fillna(True)
    out["signal_context_run_id"] = context_change.cumsum().astype(int)
    out["signal_context_age_days"] = out.groupby("signal_context_run_id").cumcount() + 1
    out["signal_context_run_length_days"] = out.groupby("signal_context_run_id")["date"].transform("size").astype(int)
    out.loc[signal_context_key.eq("inactive"), ["signal_context_age_days", "signal_context_run_length_days"]] = 0

    event_change = out["signal_state"].ne(out["signal_state"].shift()).fillna(True)
    out["signal_state_run_id"] = event_change.cumsum().astype(int)
    out["signal_state_age_days"] = out.groupby("signal_state_run_id").cumcount() + 1
    out["signal_state_run_length_days"] = out.groupby("signal_state_run_id")["date"].transform("size").astype(int)
    return out


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total = len(frame)
    run_table = (
        frame.loc[:, ["signal_state", "signal_state_run_id", "signal_state_run_length_days"]]
        .drop_duplicates("signal_state_run_id")
        .copy()
    )
    context_runs = (
        frame.loc[
            frame["signal_active_flag"].eq(1),
            ["signal_side", "signal_context_run_id", "signal_context_run_length_days"],
        ]
        .drop_duplicates("signal_context_run_id")
        .copy()
    )

    for state, group in frame.groupby("signal_state", sort=True):
        runs = run_table.loc[run_table["signal_state"].eq(state)]
        metrics = {
            "row_count": float(len(group)),
            "row_share": len(group) / total if total else np.nan,
            "run_count": float(len(runs)),
            "avg_run_length_days": safe_mean(runs["signal_state_run_length_days"]),
            "buy_zone_5_rate": safe_mean(group[DEFAULT_BUY_TARGET]),
            "buy_zone_3_rate": safe_mean(group[DEFAULT_BUY_STRICT_TARGET]),
            "sell_zone_5_rate": safe_mean(group[DEFAULT_SELL_TARGET]),
            "sell_zone_3_rate": safe_mean(group[DEFAULT_SELL_STRICT_TARGET]),
            "avg_clarity": safe_mean(group["edge_clarity_score"]),
            "avg_conflict": safe_mean(group["conflict_score"]),
            "long_signal_event_rate": safe_mean(group["long_signal_event_flag"]),
            "sell_signal_event_rate": safe_mean(group["sell_signal_event_flag"]),
            "continuation_rate": safe_mean(group["signal_continuation_flag"]),
            "reactivation_rate": safe_mean(group["signal_reactivation_flag"]),
            "invalidation_event_rate": safe_mean(group["signal_invalidation_event_flag"]),
        }
        for metric, value in metrics.items():
            rows.append({"summary_type": "signal_state_metrics", "group": state, "metric": metric, "value": value})

    for side, group in context_runs.groupby("signal_side", sort=True):
        rows.append(
            {
                "summary_type": "signal_context_runs",
                "group": side,
                "metric": "context_run_count",
                "value": float(len(group)),
            }
        )
        rows.append(
            {
                "summary_type": "signal_context_runs",
                "group": side,
                "metric": "avg_context_run_length_days",
                "value": safe_mean(group["signal_context_run_length_days"]),
            }
        )

    mapping = frame.groupby(["signal_state", "rule_state"], sort=True).size().reset_index(name="row_count")
    state_totals = frame.groupby("signal_state").size().to_dict()
    for row in mapping.itertuples(index=False):
        rows.append(
            {
                "summary_type": "rule_mapping",
                "group": f"{row.signal_state}__{row.rule_state}",
                "metric": "row_count",
                "value": float(row.row_count),
            }
        )
        rows.append(
            {
                "summary_type": "rule_mapping",
                "group": f"{row.signal_state}__{row.rule_state}",
                "metric": "share_within_signal_state",
                "value": float(row.row_count / state_totals[row.signal_state]),
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
        "operational_state",
        "rule_state",
        "long_permission_flag",
        "sell_derisk_permission_flag",
        "confirmation_needed_flag",
        "invalidation_active_flag",
        "block_action_flag",
        "rule_state_age_days",
        "rule_state_run_length_days",
        "signal_state",
        "signal_side",
        "long_signal_event_flag",
        "sell_signal_event_flag",
        "signal_continuation_flag",
        "signal_reactivation_flag",
        "signal_invalidation_event_flag",
        "signal_active_flag",
        "signal_context_run_id",
        "signal_context_age_days",
        "signal_context_run_length_days",
        "signal_state_run_id",
        "signal_state_age_days",
        "signal_state_run_length_days",
        "signal_note",
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
        raise ValueError(f"Signal-layer output is missing columns: {missing}")
    return frame.loc[:, columns].copy()


def validate_output(frame: pd.DataFrame) -> None:
    if frame["date"].duplicated().any():
        raise ValueError("Signal layer contains duplicate dates.")
    allowed = {
        "LONG_SIGNAL_NEW",
        "SELL_SIGNAL_NEW",
        "LONG_SIGNAL_ACTIVE",
        "SELL_SIGNAL_ACTIVE",
        "SIGNAL_INVALIDATED",
        "NO_SIGNAL",
    }
    unexpected = sorted(set(frame["signal_state"].dropna()) - allowed)
    if unexpected:
        raise ValueError(f"Unexpected signal states: {unexpected}")
    flags = [
        "long_signal_event_flag",
        "sell_signal_event_flag",
        "signal_continuation_flag",
        "signal_reactivation_flag",
        "signal_invalidation_event_flag",
        "signal_active_flag",
    ]
    for column in flags:
        values = set(pd.to_numeric(frame[column], errors="coerce").dropna().astype(int))
        if not values.issubset({0, 1}):
            raise ValueError(f"{column} must be binary, found {sorted(values)}")
    if (frame["long_signal_event_flag"] & frame["sell_signal_event_flag"]).any():
        raise ValueError("A row cannot have both long and sell signal event flags.")
    repeated_new = frame["signal_state"].isin(["LONG_SIGNAL_NEW", "SELL_SIGNAL_NEW"]) & frame["signal_state"].eq(
        frame["signal_state"].shift()
    )
    if repeated_new.any():
        raise ValueError("Repeated NEW signal states found on consecutive rows.")


def pivot_summary(summary: pd.DataFrame) -> pd.DataFrame:
    return (
        summary.loc[summary["summary_type"].eq("signal_state_metrics")]
        .pivot_table(index="group", columns="metric", values="value", aggfunc="first")
        .reset_index()
        .rename(columns={"group": "signal_state"})
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
            "signal_state",
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

    mapping = frame.groupby(["signal_state", "rule_state"], sort=True).size().reset_index(name="row_count")
    totals = frame.groupby("signal_state").size().to_dict()
    mapping["share_within_signal_state"] = mapping.apply(
        lambda row: row["row_count"] / totals[row["signal_state"]], axis=1
    )
    mapping_display = mapping.copy()
    mapping_display["share_within_signal_state"] = mapping_display["share_within_signal_state"].map(
        lambda value: pct(float(value))
    )

    context = (
        summary.loc[summary["summary_type"].eq("signal_context_runs")]
        .pivot_table(index="group", columns="metric", values="value", aggfunc="first")
        .reset_index()
        .rename(columns={"group": "signal_side"})
    )
    context_display = context.copy()
    for column in [column for column in context_display.columns if column != "signal_side"]:
        context_display[column] = context_display[column].map(lambda value: number(float(value)))

    latest = frame.iloc[-1]
    lines = [
        "# SAFE v4.0 Signal Realization Layer",
        "",
        "## Purpose",
        "",
        "This layer converts calibrated rule permissions into discrete structural signal events. "
        "It does not define execution, entries/exits, stops, position sizing, portfolio logic, PnL, or backtests.",
        "",
        "## Inputs",
        "",
        "- Source: `out/swing_bottom/rule_layer.csv`",
        "- Uses: rule state, permission flags, confirmation flag, invalidation flag, block flag, and prior signal context.",
        "",
        "## Signal Taxonomy",
        "",
        "- `LONG_SIGNAL_NEW`: first day of a realized long-side signal context.",
        "- `LONG_SIGNAL_ACTIVE`: continuation of an already-realized long-side signal context.",
        "- `SELL_SIGNAL_NEW`: first day of a realized sell/de-risk signal context.",
        "- `SELL_SIGNAL_ACTIVE`: continuation of an already-realized sell/de-risk signal context.",
        "- `SIGNAL_INVALIDATED`: a previously active signal context is explicitly invalidated.",
        "- `NO_SIGNAL`: no discrete signal event is active.",
        "",
        "## Signal-State Summary",
        "",
        markdown_table(display, list(display.columns)),
        "",
        "## Signal Context Runs",
        "",
        markdown_table(context_display, list(context_display.columns)) if not context_display.empty else "_No active signal runs._",
        "",
        "## Rule-State Mapping",
        "",
        markdown_table(mapping_display, ["signal_state", "rule_state", "row_count", "share_within_signal_state"]),
        "",
        "## Event Logic",
        "",
        "The state machine emits `*_SIGNAL_NEW` only when an eligible context starts. Consecutive eligible days on the same side become `*_SIGNAL_ACTIVE`, not repeated new events. "
        "`SIGNAL_INVALIDATED` is emitted only when a previously active signal context is followed by explicit invalidation. Awaiting, blocked, or no-edge rows otherwise become `NO_SIGNAL`.",
        "",
        "## Latest Signal State",
        "",
        f"- Date: `{latest['date']}`",
        f"- Signal state: `{latest['signal_state']}`",
        f"- Signal side: `{latest['signal_side']}`",
        f"- Long event: `{int(latest['long_signal_event_flag'])}`",
        f"- Sell event: `{int(latest['sell_signal_event_flag'])}`",
        f"- Invalidation event: `{int(latest['signal_invalidation_event_flag'])}`",
        f"- Note: {latest['signal_note']}",
        "",
        "## Interpretation",
        "",
        "This is the first bridge from structural permission into discrete signal events. It is useful for later strategy construction because it separates onset, continuation, invalidation, and absence of signal. "
        "It remains non-executable: signal events are structural markers, not orders.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/signal_layer.csv`",
        "- `out/swing_bottom/signal_layer_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> None:
    rules = load_rule_layer(args.rule_layer_csv)
    signals = add_signal_columns(rules)
    output = output_columns(signals)
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
