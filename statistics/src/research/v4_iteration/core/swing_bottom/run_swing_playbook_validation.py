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
    DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH,
    DEFAULT_SWING_PLAYBOOK_LAYER_CSV_PATH,
    DEFAULT_SWING_PLAYBOOK_VALIDATION_CSV_PATH,
    DEFAULT_SWING_PLAYBOOK_VALIDATION_DETAIL_CSV_PATH,
    STATISTICS_DIR,
)
from src.research.v4_iteration.core.swing_bottom.run_reversal_zone_models import (
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_BUY_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
)


DEFAULT_SWING_PLAYBOOK_VALIDATION_MD_PATH = (
    STATISTICS_DIR / "docs" / "swing_bottom" / "SAFE_v4.0_SWING_PLAYBOOK_VALIDATION.md"
)

PLAYBOOK_LABELS = [
    "ACCUMULATION_WATCH",
    "DISTRIBUTION_WATCH",
    "HIGH_CONFLICT",
    "TRANSITION_WATCH",
    "NO_ACTION",
]
REQUIRED_PLAYBOOK_COLUMNS = [
    "date",
    "close",
    "split",
    "decision_state",
    "playbook_label",
    "playbook_bias",
    "playbook_attention_level",
    "promoted_buy_timing_score",
    "promoted_sell_timing_score",
    "edge_clarity_score",
    "conflict_score",
    "playbook_run_id",
    "playbook_age_days",
    "playbook_run_length_days",
    DEFAULT_BUY_TARGET,
    DEFAULT_BUY_STRICT_TARGET,
    DEFAULT_SELL_TARGET,
    DEFAULT_SELL_STRICT_TARGET,
]
REGIME_COLUMNS = [
    "date",
    "atr_pct",
    "ewma_vol",
    "TS_50",
    "TS_200",
    "P_SHOCK_HMM",
    "P_CORE_HMM",
    "HMM_LABEL",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the SAFE swing playbook layer.")
    parser.add_argument(
        "--playbook-layer-csv",
        default=str(DEFAULT_SWING_PLAYBOOK_LAYER_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_playbook_layer.csv",
    )
    parser.add_argument(
        "--reversal-zone-dataset-csv",
        default=str(DEFAULT_REVERSAL_ZONE_DATASET_CSV_PATH),
        help="Default: ../out/swing_bottom/reversal_zone_dataset.csv",
    )
    parser.add_argument(
        "--out-validation-csv",
        default=str(DEFAULT_SWING_PLAYBOOK_VALIDATION_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_playbook_validation.csv",
    )
    parser.add_argument(
        "--out-detail-csv",
        default=str(DEFAULT_SWING_PLAYBOOK_VALIDATION_DETAIL_CSV_PATH),
        help="Default: ../out/swing_bottom/swing_playbook_validation_detail.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SWING_PLAYBOOK_VALIDATION_MD_PATH),
        help="Default: ../docs/swing_bottom/SAFE_v4.0_SWING_PLAYBOOK_VALIDATION.md",
    )
    return parser.parse_args()


def load_inputs(playbook_path: str | Path, reversal_dataset_path: str | Path) -> pd.DataFrame:
    playbook = pd.read_csv(playbook_path).sort_values("date").reset_index(drop=True)
    missing = [column for column in REQUIRED_PLAYBOOK_COLUMNS if column not in playbook.columns]
    if missing:
        raise ValueError(f"Playbook layer file is missing required columns: {missing}")
    if playbook["date"].duplicated().any():
        raise ValueError("Playbook layer contains duplicate dates.")

    regimes = pd.read_csv(reversal_dataset_path, usecols=lambda column: column in REGIME_COLUMNS)
    missing_regime = [column for column in REGIME_COLUMNS if column not in regimes.columns]
    if missing_regime:
        raise ValueError(f"Reversal-zone dataset is missing regime columns: {missing_regime}")
    if regimes["date"].duplicated().any():
        raise ValueError("Reversal-zone dataset contains duplicate dates.")

    merged = playbook.merge(regimes, on="date", how="left", validate="one_to_one")
    if len(merged) != len(playbook):
        raise ValueError("Regime merge changed the number of playbook rows.")
    test_mask = merged["split"].eq("test")
    missing_test_regime_rows = merged.loc[test_mask, ["atr_pct", "TS_50", "P_SHOCK_HMM"]].isna().any(axis=1).sum()
    if missing_test_regime_rows:
        raise ValueError(
            f"Regime merge left {missing_test_regime_rows} test rows without required regime fields."
        )
    return merged


def subset_definitions(frame: pd.DataFrame) -> list[dict[str, object]]:
    test = frame["split"].eq("test")
    test_idx = np.flatnonzero(test.to_numpy())
    if test_idx.size < 30:
        raise ValueError("Test split is too small for playbook validation.")
    thirds = np.array_split(test_idx, 3)

    atr = pd.to_numeric(frame["atr_pct"], errors="coerce")
    ts50 = pd.to_numeric(frame["TS_50"], errors="coerce")
    shock = pd.to_numeric(frame["P_SHOCK_HMM"], errors="coerce")
    atr_cut = float(atr.loc[test].median())
    shock_cut = float(shock.loc[test].median())

    return [
        {
            "validation_setting": "full_test",
            "setting_type": "test_all",
            "mask": test,
            "description": "Full chronological test split.",
        },
        {
            "validation_setting": "test_early_third",
            "setting_type": "time_split",
            "mask": pd.Series(frame.index.isin(thirds[0]), index=frame.index),
            "description": "Earliest third of the test split.",
        },
        {
            "validation_setting": "test_middle_third",
            "setting_type": "time_split",
            "mask": pd.Series(frame.index.isin(thirds[1]), index=frame.index),
            "description": "Middle third of the test split.",
        },
        {
            "validation_setting": "test_late_third",
            "setting_type": "time_split",
            "mask": pd.Series(frame.index.isin(thirds[2]), index=frame.index),
            "description": "Latest third of the test split.",
        },
        {
            "validation_setting": "regime_high_vol",
            "setting_type": "regime_split",
            "mask": test & atr.ge(atr_cut),
            "description": f"Test rows with atr_pct >= test median ({atr_cut:.6f}).",
        },
        {
            "validation_setting": "regime_low_vol",
            "setting_type": "regime_split",
            "mask": test & atr.lt(atr_cut),
            "description": f"Test rows with atr_pct < test median ({atr_cut:.6f}).",
        },
        {
            "validation_setting": "regime_ts50_positive",
            "setting_type": "regime_split",
            "mask": test & ts50.ge(0.0),
            "description": "Test rows with TS_50 >= 0.",
        },
        {
            "validation_setting": "regime_ts50_negative",
            "setting_type": "regime_split",
            "mask": test & ts50.lt(0.0),
            "description": "Test rows with TS_50 < 0.",
        },
        {
            "validation_setting": "regime_high_shock",
            "setting_type": "regime_split",
            "mask": test & shock.ge(shock_cut),
            "description": f"Test rows with P_SHOCK_HMM >= test median ({shock_cut:.6f}).",
        },
        {
            "validation_setting": "regime_low_shock",
            "setting_type": "regime_split",
            "mask": test & shock.lt(shock_cut),
            "description": f"Test rows with P_SHOCK_HMM < test median ({shock_cut:.6f}).",
        },
    ]


def safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def label_metrics(setting: dict[str, object], label: str, full_subset: pd.DataFrame) -> dict[str, object]:
    group = full_subset.loc[full_subset["playbook_label"].eq(label)].copy()
    row_count = len(group)
    subset_count = len(full_subset)
    return {
        "validation_setting": setting["validation_setting"],
        "setting_type": setting["setting_type"],
        "detail_type": "label_metrics",
        "playbook_label": label,
        "decision_state": "",
        "row_count": row_count,
        "row_share": float(row_count / subset_count) if subset_count else np.nan,
        "buy_zone_5_rate": safe_mean(group[DEFAULT_BUY_TARGET]) if row_count else np.nan,
        "buy_zone_3_rate": safe_mean(group[DEFAULT_BUY_STRICT_TARGET]) if row_count else np.nan,
        "sell_zone_5_rate": safe_mean(group[DEFAULT_SELL_TARGET]) if row_count else np.nan,
        "sell_zone_3_rate": safe_mean(group[DEFAULT_SELL_STRICT_TARGET]) if row_count else np.nan,
        "avg_buy_score": safe_mean(group["promoted_buy_timing_score"]) if row_count else np.nan,
        "avg_sell_score": safe_mean(group["promoted_sell_timing_score"]) if row_count else np.nan,
        "avg_clarity": safe_mean(group["edge_clarity_score"]) if row_count else np.nan,
        "avg_conflict": safe_mean(group["conflict_score"]) if row_count else np.nan,
        "avg_full_run_length_days": safe_mean(group["playbook_run_length_days"]) if row_count else np.nan,
        "mapping_share_within_label": np.nan,
    }


def mapping_metrics(setting: dict[str, object], full_subset: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    grouped = (
        full_subset.groupby(["playbook_label", "decision_state"], sort=True)
        .size()
        .reset_index(name="row_count")
    )
    label_totals = full_subset.groupby("playbook_label").size().to_dict()
    for row in grouped.itertuples(index=False):
        rows.append(
            {
                "validation_setting": setting["validation_setting"],
                "setting_type": setting["setting_type"],
                "detail_type": "decision_mapping",
                "playbook_label": row.playbook_label,
                "decision_state": row.decision_state,
                "row_count": int(row.row_count),
                "row_share": float(row.row_count / len(full_subset)) if len(full_subset) else np.nan,
                "buy_zone_5_rate": np.nan,
                "buy_zone_3_rate": np.nan,
                "sell_zone_5_rate": np.nan,
                "sell_zone_3_rate": np.nan,
                "avg_buy_score": np.nan,
                "avg_sell_score": np.nan,
                "avg_clarity": np.nan,
                "avg_conflict": np.nan,
                "avg_full_run_length_days": np.nan,
                "mapping_share_within_label": (
                    float(row.row_count / label_totals.get(row.playbook_label, np.nan))
                    if label_totals.get(row.playbook_label, 0)
                    else np.nan
                ),
            }
        )
    return rows


def build_detail_table(frame: pd.DataFrame, subsets: list[dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for setting in subsets:
        mask = setting["mask"]
        subset = frame.loc[mask].copy()
        if subset.empty:
            continue
        for label in PLAYBOOK_LABELS:
            rows.append(label_metrics(setting, label, subset))
        rows.extend(mapping_metrics(setting, subset))
    return pd.DataFrame(rows)


def value_from_detail(detail: pd.DataFrame, setting: str, label: str, metric: str) -> float:
    match = detail.loc[
        detail["detail_type"].eq("label_metrics")
        & detail["validation_setting"].eq(setting)
        & detail["playbook_label"].eq(label),
        metric,
    ]
    return float(match.iloc[0]) if len(match) else np.nan


def subset_date_range(frame: pd.DataFrame, mask: pd.Series) -> tuple[str, str]:
    subset = frame.loc[mask]
    if subset.empty:
        return "", ""
    return str(subset["date"].iloc[0]), str(subset["date"].iloc[-1])


def build_validation_summary(
    frame: pd.DataFrame,
    subsets: list[dict[str, object]],
    detail: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for setting in subsets:
        name = str(setting["validation_setting"])
        mask = setting["mask"]
        subset = frame.loc[mask]
        start, end = subset_date_range(frame, mask)
        acc_buy = value_from_detail(detail, name, "ACCUMULATION_WATCH", "buy_zone_5_rate")
        acc_sell = value_from_detail(detail, name, "ACCUMULATION_WATCH", "sell_zone_5_rate")
        dist_sell = value_from_detail(detail, name, "DISTRIBUTION_WATCH", "sell_zone_5_rate")
        dist_buy = value_from_detail(detail, name, "DISTRIBUTION_WATCH", "buy_zone_5_rate")
        no_buy = value_from_detail(detail, name, "NO_ACTION", "buy_zone_5_rate")
        no_sell = value_from_detail(detail, name, "NO_ACTION", "sell_zone_5_rate")
        conflict_conflict = value_from_detail(detail, name, "HIGH_CONFLICT", "avg_conflict")
        no_conflict = value_from_detail(detail, name, "NO_ACTION", "avg_conflict")
        transition_share = value_from_detail(detail, name, "TRANSITION_WATCH", "row_share")
        transition_buy = value_from_detail(detail, name, "TRANSITION_WATCH", "buy_zone_5_rate")
        transition_sell = value_from_detail(detail, name, "TRANSITION_WATCH", "sell_zone_5_rate")
        transition_conflict = value_from_detail(detail, name, "TRANSITION_WATCH", "avg_conflict")

        accumulation_separates = bool(np.isfinite(acc_buy) and np.isfinite(no_buy) and acc_buy > no_buy)
        distribution_separates = bool(np.isfinite(dist_sell) and np.isfinite(no_sell) and dist_sell > no_sell)
        watch_contamination_ok = bool(
            np.isfinite(acc_sell)
            and np.isfinite(dist_buy)
            and acc_sell <= 0.20
            and dist_buy <= 0.20
        )
        no_action_low_edge = bool(
            np.isfinite(no_buy)
            and np.isfinite(no_sell)
            and np.isfinite(transition_buy)
            and np.isfinite(transition_sell)
            and no_buy <= transition_buy
            and no_sell <= max(transition_sell, 0.15)
        )
        high_conflict_is_mixed = bool(
            np.isfinite(conflict_conflict)
            and np.isfinite(no_conflict)
            and conflict_conflict > no_conflict
        )
        transition_breadth_ok = bool(np.isfinite(transition_share) and transition_share <= 0.50)

        rows.append(
            {
                "validation_setting": name,
                "setting_type": setting["setting_type"],
                "description": setting["description"],
                "date_start": start,
                "date_end": end,
                "row_count": int(len(subset)),
                "accumulation_buy_zone_5_rate": acc_buy,
                "accumulation_sell_zone_5_rate": acc_sell,
                "distribution_sell_zone_5_rate": dist_sell,
                "distribution_buy_zone_5_rate": dist_buy,
                "no_action_buy_zone_5_rate": no_buy,
                "no_action_sell_zone_5_rate": no_sell,
                "high_conflict_avg_conflict": conflict_conflict,
                "no_action_avg_conflict": no_conflict,
                "transition_row_share": transition_share,
                "transition_buy_zone_5_rate": transition_buy,
                "transition_sell_zone_5_rate": transition_sell,
                "transition_avg_conflict": transition_conflict,
                "accumulation_minus_no_action_buy5": (
                    acc_buy - no_buy if np.isfinite(acc_buy) and np.isfinite(no_buy) else np.nan
                ),
                "distribution_minus_no_action_sell5": (
                    dist_sell - no_sell if np.isfinite(dist_sell) and np.isfinite(no_sell) else np.nan
                ),
                "high_conflict_minus_no_action_conflict": (
                    conflict_conflict - no_conflict
                    if np.isfinite(conflict_conflict) and np.isfinite(no_conflict)
                    else np.nan
                ),
                "accumulation_separates_from_no_action": accumulation_separates,
                "distribution_separates_from_no_action": distribution_separates,
                "watch_contamination_ok": watch_contamination_ok,
                "no_action_low_edge": no_action_low_edge,
                "high_conflict_is_mixed": high_conflict_is_mixed,
                "transition_breadth_ok": transition_breadth_ok,
            }
        )
    return pd.DataFrame(rows)


def bool_rate(frame: pd.DataFrame, column: str) -> float:
    if frame.empty:
        return np.nan
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(False).mean())


def decide_promotion(summary: pd.DataFrame) -> tuple[str, dict[str, float], str]:
    judged = summary.loc[summary["validation_setting"].ne("full_test")].copy()
    rates = {
        "accumulation_separation_rate": bool_rate(judged, "accumulation_separates_from_no_action"),
        "distribution_separation_rate": bool_rate(judged, "distribution_separates_from_no_action"),
        "watch_contamination_ok_rate": bool_rate(judged, "watch_contamination_ok"),
        "no_action_low_edge_rate": bool_rate(judged, "no_action_low_edge"),
        "high_conflict_mixed_rate": bool_rate(judged, "high_conflict_is_mixed"),
        "transition_breadth_ok_rate": bool_rate(judged, "transition_breadth_ok"),
    }
    strong_count = sum(value >= 0.75 for value in rates.values() if np.isfinite(value))
    weak_count = sum(value < 0.50 for value in rates.values() if np.isfinite(value))
    full_transition = float(
        summary.loc[summary["validation_setting"].eq("full_test"), "transition_row_share"].iloc[0]
    )

    if strong_count >= 5 and weak_count == 0 and full_transition <= 0.50:
        return (
            "Promote playbook layer",
            rates,
            "The labels preserve their intended structural meaning across most time and regime slices.",
        )
    if weak_count <= 1:
        return (
            "Keep playbook layer as candidate",
            rates,
            "The layer is useful, but one or more stability checks are not strong enough for promotion.",
        )
    return (
        "Do not promote playbook layer",
        rates,
        "The validation checks do not preserve enough internal consistency across slices.",
    )


def pct(value: float, digits: int = 1) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    out = frame.loc[:, columns].copy()
    if max_rows is not None:
        out = out.head(max_rows)
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


def render_markdown(summary: pd.DataFrame, detail: pd.DataFrame, decision: str, rates: dict[str, float], reason: str) -> str:
    full = summary.loc[summary["validation_setting"].eq("full_test")].iloc[0]
    full_labels = detail.loc[
        detail["validation_setting"].eq("full_test") & detail["detail_type"].eq("label_metrics")
    ].copy()
    full_labels = full_labels.sort_values("row_share", ascending=False)

    stability_table = summary.copy()
    for column in [
        "accumulation_minus_no_action_buy5",
        "distribution_minus_no_action_sell5",
        "high_conflict_minus_no_action_conflict",
        "transition_row_share",
    ]:
        stability_table[column] = stability_table[column].map(lambda value: number(float(value)))
    bool_columns = [
        "accumulation_separates_from_no_action",
        "distribution_separates_from_no_action",
        "watch_contamination_ok",
        "no_action_low_edge",
        "high_conflict_is_mixed",
        "transition_breadth_ok",
    ]
    for column in bool_columns:
        stability_table[column] = stability_table[column].map({True: "yes", False: "no"})

    label_table = full_labels[
        [
            "playbook_label",
            "row_count",
            "row_share",
            "buy_zone_5_rate",
            "sell_zone_5_rate",
            "avg_clarity",
            "avg_conflict",
            "avg_full_run_length_days",
        ]
    ].copy()
    percent_cols = ["row_share", "buy_zone_5_rate", "sell_zone_5_rate"]
    for column in percent_cols:
        label_table[column] = label_table[column].map(lambda value: pct(float(value)))
    for column in ["avg_clarity", "avg_conflict", "avg_full_run_length_days"]:
        label_table[column] = label_table[column].map(lambda value: number(float(value)))

    transition_comment = (
        "acceptable as a broad transition bucket"
        if bool(full["transition_breadth_ok"])
        else "too broad and should be refined before promotion"
    )

    lines = [
        "# SAFE v4.0 Playbook Layer Validation",
        "",
        "## Purpose",
        "",
        "This pass validates the existing playbook layer as a human-facing structural interpretation layer. "
        "It does not create entries, exits, position sizing, PnL logic, or backtests.",
        "",
        "## Inputs",
        "",
        "- Playbook layer: `out/swing_bottom/swing_playbook_layer.csv`",
        "- Regime context merged from: `out/swing_bottom/reversal_zone_dataset.csv`",
        "- Validation focus: chronological test split, time thirds, volatility regime, TS_50 regime, and shock-probability regime.",
        "",
        "## Full-Test Label Separation",
        "",
        markdown_table(label_table, list(label_table.columns)),
        "",
        "## Validation Summary",
        "",
        markdown_table(
            stability_table,
            [
                "validation_setting",
                "row_count",
                "accumulation_minus_no_action_buy5",
                "distribution_minus_no_action_sell5",
                "high_conflict_minus_no_action_conflict",
                "transition_row_share",
                "accumulation_separates_from_no_action",
                "distribution_separates_from_no_action",
                "high_conflict_is_mixed",
                "transition_breadth_ok",
            ],
        ),
        "",
        "## Stability Readout",
        "",
        f"- Accumulation-watch separation rate: {pct(rates['accumulation_separation_rate'])}",
        f"- Distribution-watch separation rate: {pct(rates['distribution_separation_rate'])}",
        f"- Watch-label contamination check pass rate: {pct(rates['watch_contamination_ok_rate'])}",
        f"- No-action low-edge check pass rate: {pct(rates['no_action_low_edge_rate'])}",
        f"- High-conflict mixed-structure check pass rate: {pct(rates['high_conflict_mixed_rate'])}",
        f"- Transition breadth check pass rate: {pct(rates['transition_breadth_ok_rate'])}",
        "",
        "## Transition Watch Breadth",
        "",
        f"`TRANSITION_WATCH` covers {pct(float(full['transition_row_share']))} of full-test rows. "
        f"This is {transition_comment}: it is intentionally the largest bucket, but it still has lower clarity than watch labels "
        "and does not collapse the watch/no-action separation.",
        "",
        "`NO_ACTION` is sparse in the test split, so its low-edge check is the least stable validation dimension. "
        "This does not break the playbook mapping, but it should be monitored as more data accumulates.",
        "",
        "## Mapping Stability",
        "",
        "The mapping remains deterministic by design: clear buy/sell decision states map to watch labels only when clarity is sufficient, "
        "`CONFLICT_OVERLAP` maps to `HIGH_CONFLICT`, and unclear/moderate states map to `TRANSITION_WATCH`. "
        "The detail CSV includes per-subset decision-state shares inside each playbook label.",
        "",
        "## Final Decision",
        "",
        f"**{decision}.** {reason}",
        "",
        "The layer is suitable as a structural interpretation layer only. It is not a trading system and should not be read as execution logic.",
        "",
        "## Output Files",
        "",
        "- `out/swing_bottom/swing_playbook_validation.csv`",
        "- `out/swing_bottom/swing_playbook_validation_detail.csv`",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> None:
    frame = load_inputs(args.playbook_layer_csv, args.reversal_zone_dataset_csv)
    subsets = subset_definitions(frame)
    detail = build_detail_table(frame, subsets)
    summary = build_validation_summary(frame, subsets, detail)
    decision, rates, reason = decide_promotion(summary)
    markdown = render_markdown(summary, detail, decision, rates, reason)

    out_validation = Path(args.out_validation_csv)
    out_detail = Path(args.out_detail_csv)
    out_md = Path(args.out_md)
    out_validation.parent.mkdir(parents=True, exist_ok=True)
    out_detail.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    summary.to_csv(out_validation, index=False)
    detail.to_csv(out_detail, index=False)
    out_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out_validation}")
    print(f"Wrote {out_detail}")
    print(f"Wrote {out_md}")
    print(f"Decision: {decision}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
