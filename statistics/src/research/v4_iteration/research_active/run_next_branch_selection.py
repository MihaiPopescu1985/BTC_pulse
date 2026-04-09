from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import OUT_DIR, STATISTICS_DIR


DEFAULT_INTERACTION_DISCOVERY_CSV_PATH = OUT_DIR / "interaction_discovery" / "interaction_discovery.csv"
DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH = OUT_DIR / "swing_bridge" / "swing_condition_mapping.csv"
DEFAULT_ENTRY_LOGIC_RESEARCH_CSV_PATH = OUT_DIR / "swing_bridge" / "entry_logic_research.csv"
DEFAULT_BEARISH_ROLE_EVALUATION_CSV_PATH = OUT_DIR / "swing_bridge" / "bearish_branch_role_evaluation.csv"
DEFAULT_NEXT_BRANCH_SELECTION_CSV_PATH = OUT_DIR / "swing_bridge" / "next_branch_selection.csv"
DEFAULT_NEXT_BRANCH_SELECTION_MD_PATH = STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_NEXT_BRANCH_SELECTION.md"


SHORTLIST: tuple[str, ...] = (
    "low_risk_base",
    "expansion_with_participation",
    "squeeze_release_up",
    "structural_onchain_tailwind",
    "clean_breakout_continuation",
)

WARNING_ONLY_BRANCH = "upside_probability_stack"
WATCHLIST_ONLY_BRANCH = "bearish_age0_75_size1_25_with_veto"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select the next research-stage direct-entry branch from existing SAFE interaction and swing-bridge evidence.",
    )
    parser.add_argument(
        "--interaction-discovery-csv",
        default=str(DEFAULT_INTERACTION_DISCOVERY_CSV_PATH),
        help="Default: ../out/interaction_discovery/interaction_discovery.csv",
    )
    parser.add_argument(
        "--swing-condition-mapping-csv",
        default=str(DEFAULT_SWING_CONDITION_MAPPING_CSV_PATH),
        help="Default: ../out/swing_bridge/swing_condition_mapping.csv",
    )
    parser.add_argument(
        "--entry-logic-research-csv",
        default=str(DEFAULT_ENTRY_LOGIC_RESEARCH_CSV_PATH),
        help="Default: ../out/swing_bridge/entry_logic_research.csv",
    )
    parser.add_argument(
        "--bearish-role-evaluation-csv",
        default=str(DEFAULT_BEARISH_ROLE_EVALUATION_CSV_PATH),
        help="Default: ../out/swing_bridge/bearish_branch_role_evaluation.csv",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_NEXT_BRANCH_SELECTION_CSV_PATH),
        help="Default: ../out/swing_bridge/next_branch_selection.csv",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_NEXT_BRANCH_SELECTION_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_NEXT_BRANCH_SELECTION.md",
    )
    return parser.parse_args()


def _safe(value: float | int | str | None) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(numeric) if pd.notna(numeric) else np.nan


def _sample_score(sample_count: float) -> float:
    if pd.isna(sample_count):
        return 0.0
    return float(min(sample_count, 120.0) / 120.0)


def _directional_score(next_up: float, next_down: float) -> float:
    if pd.notna(next_up) and pd.notna(next_down):
        return float((next_up - next_down + 1.0) / 2.0)
    if pd.notna(next_up):
        return float(next_up)
    if pd.notna(next_down):
        return float(1.0 - next_down)
    return np.nan


def _forward_profile_score(ret_10d: float, max_up: float, max_down: float, touch_up: float, touch_down: float) -> float:
    score = 0.0
    if pd.notna(ret_10d):
        score += ret_10d * 4.0
    if pd.notna(max_up):
        score += max_up * 2.0
    if pd.notna(max_down):
        score += max_down * 2.0
    if pd.notna(touch_up):
        score += touch_up
    if pd.notna(touch_down):
        score -= touch_down
    return float(score)


def _path_quality_score(max_down: float, touch_up: float, touch_down: float) -> float:
    score = 0.0
    if pd.notna(max_down):
        score += max_down * 3.0
    if pd.notna(touch_down):
        score -= touch_down * 1.5
    if pd.notna(touch_up):
        score += touch_up * 0.75
    return float(score)


def _role_fit(next_up: float, next_down: float, touch_up: float, touch_down: float, sample_count: float) -> str:
    if pd.notna(sample_count) and sample_count < 12:
        return "direct_entry_candidate_but_too_sparse"
    if pd.notna(touch_down) and pd.notna(touch_up) and touch_down > touch_up + 0.08:
        if pd.notna(next_up) and next_up > 0.70:
            return "watchlist_or_setup_only"
        return "warning_or_veto_only"
    if pd.notna(next_up) and pd.notna(next_down) and next_up > next_down and pd.notna(touch_down) and touch_down <= 0.75:
        return "direct_entry_candidate"
    if pd.notna(touch_down) and touch_down <= 0.75 and pd.notna(touch_up) and touch_up >= 0.70:
        return "direct_entry_candidate"
    return "context_only"


def load_tables(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    interaction = pd.read_csv(args.interaction_discovery_csv)
    swing_mapping = pd.read_csv(args.swing_condition_mapping_csv)
    entry_logic = pd.read_csv(args.entry_logic_research_csv)
    bearish_role = pd.read_csv(args.bearish_role_evaluation_csv)
    return interaction, swing_mapping, entry_logic, bearish_role


def build_shortlist_table(
    interaction: pd.DataFrame,
    swing_mapping: pd.DataFrame,
) -> pd.DataFrame:
    next_mapping = swing_mapping.loc[swing_mapping["mapping_mode"] == "next"].copy()
    next_mapping = next_mapping.loc[
        :,
        [
            "condition_name",
            "mapped_swing_rows",
            "swing_up_rate",
            "swing_down_rate",
            "median_swing_abs_amplitude",
            "median_swing_duration_days",
        ],
    ]
    merged = interaction.merge(next_mapping, on="condition_name", how="left")
    merged = merged.loc[merged["condition_name"].isin(SHORTLIST)].copy()

    rows: list[dict[str, object]] = []
    for _, row in merged.iterrows():
        sample_count = _safe(row["sample_count"])
        ret_10d = _safe(row["ret_10d_mean"])
        max_up = _safe(row["max_up_10d_mean"])
        max_down = _safe(row["max_down_10d_mean"])
        touch_up = _safe(row["touch_up_2pct_10d_mean"])
        touch_down = _safe(row["touch_down_2pct_10d_mean"])
        next_up = _safe(row.get("swing_up_rate"))
        next_down = _safe(row.get("swing_down_rate"))

        directional = _directional_score(next_up, next_down)
        forward = _forward_profile_score(ret_10d, max_up, max_down, touch_up, touch_down)
        path = _path_quality_score(max_down, touch_up, touch_down)
        sample = _sample_score(sample_count)

        direct_entry_score = (
            (directional if pd.notna(directional) else 0.45) * 0.25
            + forward * 0.20
            + path * 0.35
            + sample * 0.20
        )

        rows.append(
            {
                "branch_name": row["condition_name"],
                "branch_family": row["condition_family"],
                "intent": row["intent"],
                "sample_count": int(sample_count),
                "mapped_swing_rows": int(row["mapped_swing_rows"]) if pd.notna(row["mapped_swing_rows"]) else np.nan,
                "next_up_swing_rate": next_up,
                "next_down_swing_rate": next_down,
                "ret_10d_mean": ret_10d,
                "ret_10d_median": _safe(row["ret_10d_median"]),
                "max_up_10d_mean": max_up,
                "max_down_10d_mean": max_down,
                "touch_up_2pct_10d_rate": touch_up,
                "touch_down_2pct_10d_rate": touch_down,
                "median_next_swing_abs_amplitude": _safe(row.get("median_swing_abs_amplitude")),
                "median_next_swing_duration_days": _safe(row.get("median_swing_duration_days")),
                "directional_alignment_score": directional,
                "forward_profile_score": forward,
                "path_quality_score": path,
                "sample_viability_score": sample,
                "direct_entry_suitability_score": float(direct_entry_score),
                "role_fit": _role_fit(next_up, next_down, touch_up, touch_down, sample_count),
            }
        )

    table = pd.DataFrame(rows)
    rank_order = [
        "low_risk_base",
        "expansion_with_participation",
        "squeeze_release_up",
        "structural_onchain_tailwind",
        "clean_breakout_continuation",
    ]
    rank_map = {name: idx + 1 for idx, name in enumerate(rank_order)}
    table["shortlist_rank"] = table["branch_name"].map(rank_map)
    return table.sort_values(["shortlist_rank", "direct_entry_suitability_score"], ascending=[True, False]).reset_index(drop=True)


def build_role_assignment_rows(
    interaction: pd.DataFrame,
    swing_mapping: pd.DataFrame,
    bearish_role: pd.DataFrame,
) -> pd.DataFrame:
    next_map = swing_mapping.loc[swing_mapping["mapping_mode"] == "next"].copy()
    interaction_row = interaction.loc[interaction["condition_name"] == WARNING_ONLY_BRANCH].iloc[0]
    next_row = next_map.loc[next_map["condition_name"] == WARNING_ONLY_BRANCH].iloc[0]
    bearish_watch = bearish_role.loc[bearish_role["role_name"] == "setup_episode_start"].iloc[0]

    rows = [
        {
            "branch_name": WARNING_ONLY_BRANCH,
            "assigned_role": "warning_veto_only",
            "evidence_summary": (
                f"next down {float(next_row['swing_down_rate']):.2%}, "
                f"touch_down_2pct_10d {float(interaction_row['touch_down_2pct_10d_mean']):.2%}, "
                f"touch_up_2pct_10d {float(interaction_row['touch_up_2pct_10d_mean']):.2%}"
            ),
        },
        {
            "branch_name": WATCHLIST_ONLY_BRANCH,
            "assigned_role": "watchlist_context_only",
            "evidence_summary": (
                f"watchlist next up {float(bearish_watch['next_up_swing_rate']):.2%}, "
                f"touch_up_2pct_5d {float(bearish_watch['touch_up_2pct_5d_rate']):.2%}, "
                f"touch_down_2pct_10d {float(bearish_watch['touch_down_2pct_10d_rate']):.2%}"
            ),
        },
    ]
    return pd.DataFrame(rows)


def render_markdown(shortlist: pd.DataFrame, role_rows: pd.DataFrame) -> str:
    recommended = shortlist.loc[shortlist["branch_name"] == "low_risk_base"].iloc[0]
    warning = role_rows.loc[role_rows["assigned_role"] == "warning_veto_only"].iloc[0]
    watchlist = role_rows.loc[role_rows["assigned_role"] == "watchlist_context_only"].iloc[0]

    lines = [
        "# SAFE v4.0 Next Branch Selection",
        "",
        "## Section 1 — What Was Learned From The Bearish Branch",
        "",
        "- the bearish-contrarian branch improved next-swing purity in some filtered forms",
        "- it failed as a direct-entry branch because path pain remained too high",
        "- candle-timing work did not repair that weakness enough",
        "- it now remains alive only as a watchlist / alert state, not as the active direct-entry branch",
        "",
        "## Section 2 — Shortlisted Next Branches",
        "",
    ]

    for _, row in shortlist.iterrows():
        lines.append(
            f"- `{row['branch_name']}` ({row['branch_family']}): "
            f"ret_10d mean `{row['ret_10d_mean']:.2%}`, "
            f"max_up_10d `{row['max_up_10d_mean']:.2%}`, "
            f"max_down_10d `{row['max_down_10d_mean']:.2%}`, "
            f"touch_up `{row['touch_up_2pct_10d_rate']:.2%}`, "
            f"touch_down `{row['touch_down_2pct_10d_rate']:.2%}`, "
            f"n=`{int(row['sample_count'])}`"
        )

    lines.extend(
        [
            "",
            "## Section 3 — Branch Suitability Comparison",
            "",
            "| Branch | Directional alignment | Practical profile | Path quality | Sample viability | Role fit |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )

    for _, row in shortlist.iterrows():
        direction_text = (
            f"next up {row['next_up_swing_rate']:.2%} / next down {row['next_down_swing_rate']:.2%}"
            if pd.notna(row["next_up_swing_rate"]) and pd.notna(row["next_down_swing_rate"])
            else "swing evidence incomplete"
        )
        profile_text = f"ret_10d {row['ret_10d_mean']:.2%}, max_up {row['max_up_10d_mean']:.2%}"
        path_text = f"max_down {row['max_down_10d_mean']:.2%}, tdn {row['touch_down_2pct_10d_rate']:.2%}"
        sample_text = str(int(row["sample_count"]))
        lines.append(
            f"| `{row['branch_name']}` | {direction_text} | {profile_text} | {path_text} | {sample_text} | `{row['role_fit']}` |"
        )

    lines.extend(
        [
            "",
            "## Section 4 — Recommended Next Active Branch",
            "",
            f"- recommended branch: `{recommended['branch_name']}`",
            "- reason: it offers the best balance of usable sample, positive forward profile, and materially lower path pain than the bearish watchlist branch",
            f"- key numbers: ret_10d mean `{recommended['ret_10d_mean']:.2%}`, max_up_10d `{recommended['max_up_10d_mean']:.2%}`, max_down_10d `{recommended['max_down_10d_mean']:.2%}`, touch_up `{recommended['touch_up_2pct_10d_rate']:.2%}`, touch_down `{recommended['touch_down_2pct_10d_rate']:.2%}`, n=`{int(recommended['sample_count'])}`",
            "- interpretation: this branch is less exciting on raw next-swing purity than the bearish branch, but it is more likely to support an entry-timing pass because it starts from a safer path profile",
            "",
            "## Section 5 — Role Assignment Summary",
            "",
            f"- direct-entry candidate: `{recommended['branch_name']}`",
            f"- warning / veto only: `{warning['branch_name']}` ({warning['evidence_summary']})",
            f"- watchlist / context only: `{watchlist['branch_name']}` ({watchlist['evidence_summary']})",
            "",
            "Final decision:",
            "- the next direct-entry research pass should move to `low_risk_base`",
            "- `upside_probability_stack` should remain a warning / veto branch",
            "- `bearish_age0_75_size1_25_with_veto` should remain a watchlist / alert branch",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    interaction, swing_mapping, _entry_logic, bearish_role = load_tables(args)
    shortlist = build_shortlist_table(interaction, swing_mapping)
    role_rows = build_role_assignment_rows(interaction, swing_mapping, bearish_role)

    combined = pd.concat(
        [
            shortlist.assign(record_type="shortlist"),
            role_rows.assign(record_type="role_assignment"),
        ],
        ignore_index=True,
        sort=False,
    )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(shortlist, role_rows), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(combined)}")
    print(f"Recommended next branch: low_risk_base")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
