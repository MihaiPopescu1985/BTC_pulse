from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv, load_feature_csv
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_STATES_CSV_PATH, OUT_DIR


REQUIRED_COLUMNS: tuple[str, ...] = (
    "HMM_LABEL",
    "HMM_CONF",
    "HMM_DOM",
    "TS_20",
    "TS_50",
    "TS_200",
    "atr_pct",
    "vol_20",
    "band_pos",
    "relative_volume_20",
    "volume_z",
    "P_CORRECTION_10D_CAL",
    "P_REBOUND_10D_CAL",
    "P_SHOCK_HMM",
    "hard_risk_off_flag_safe",
)

STATE_COLUMNS: tuple[str, ...] = (
    "state_hmm_label",
    "state_hmm_conf",
    "state_hmm_dom",
    "trend_state",
    "vol_state",
    "position_state",
    "participation_state",
    "risk_state",
    "state_rule_compact",
    "state_market_regime",
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the SAFE v4.0 state-definition stage."""
    parser = argparse.ArgumentParser(
        description="Build explicit HMM-derived and rule-based BTC market states from ../out/features.csv.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--out-csv", default=str(DEFAULT_STATES_CSV_PATH), help="Default: ../out/states.csv")
    parser.add_argument("--out-md", default=str(OUT_DIR / "states.md"), help="Default: ../out/states.md")
    return parser.parse_args()


def _validate_inputs(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate required inputs for deterministic state construction."""
    if frame.empty:
        raise ValueError("State generation received an empty feature table.")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("State generation requires a DatetimeIndex.")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("State generation requires dates sorted in increasing order.")
    if frame.index.has_duplicates:
        raise ValueError("State generation does not accept duplicate timestamps.")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"State generation requires feature columns that are missing: {missing_columns}")

    validated = frame.copy()
    numeric_columns = [column for column in REQUIRED_COLUMNS if column not in {"HMM_LABEL"}]
    validated.loc[:, numeric_columns] = validated.loc[:, numeric_columns].apply(pd.to_numeric, errors="coerce")
    return validated


def percentile_rank(series: pd.Series) -> pd.Series:
    """Return percentile rank in [0, 1] for a numeric series."""
    ranked = series.rank(method="average", pct=True)
    return ranked


def build_thresholds(frame: pd.DataFrame) -> dict[str, float]:
    """Compute explicit threshold values used by rule-based state dimensions."""
    return {
        "atr_pct_q25": float(frame["atr_pct"].quantile(0.25)),
        "atr_pct_q50": float(frame["atr_pct"].quantile(0.50)),
        "atr_pct_q75": float(frame["atr_pct"].quantile(0.75)),
        "vol_20_q25": float(frame["vol_20"].quantile(0.25)),
        "vol_20_q50": float(frame["vol_20"].quantile(0.50)),
        "vol_20_q75": float(frame["vol_20"].quantile(0.75)),
        "participation_weak_pct": 0.20,
        "participation_strong_pct": 0.80,
        "position_lower_max": 1.0 / 3.0,
        "position_upper_min": 2.0 / 3.0,
        "risk_asymmetry_threshold": 0.10,
        "shock_risk_threshold": 0.50,
    }


def classify_trend_state(row: pd.Series) -> str | float:
    """Classify trend as bullish/mixed/bearish from TS_20/50/200 sign majority."""
    values = [row["TS_20"], row["TS_50"], row["TS_200"]]
    if any(pd.isna(value) for value in values):
        return np.nan
    bullish = sum(value > 0 for value in values)
    bearish = sum(value < 0 for value in values)
    if bullish >= 2:
        return "bullish"
    if bearish >= 2:
        return "bearish"
    return "mixed"


def classify_vol_state(row: pd.Series, atr_pct_rank: pd.Series, vol_20_rank: pd.Series) -> str | float:
    """Classify volatility from average percentile rank of atr_pct and vol_20."""
    idx = row.name
    ranks = [atr_pct_rank.loc[idx], vol_20_rank.loc[idx]]
    ranks = [value for value in ranks if pd.notna(value)]
    if not ranks:
        return np.nan
    score = float(np.mean(ranks))
    if score <= 0.25:
        return "low"
    if score <= 0.50:
        return "moderate"
    if score <= 0.75:
        return "elevated"
    return "very_high"


def classify_position_state(row: pd.Series, thresholds: dict[str, float]) -> str | float:
    """Classify location inside the recent price envelope using band_pos."""
    band_pos = row["band_pos"]
    if pd.isna(band_pos):
        return np.nan
    if band_pos <= thresholds["position_lower_max"]:
        return "lower_band_area"
    if band_pos >= thresholds["position_upper_min"]:
        return "upper_band_area"
    return "mid_range"


def classify_participation_state(row: pd.Series, relative_volume_rank: pd.Series, volume_z_rank: pd.Series, thresholds: dict[str, float]) -> str | float:
    """Classify participation from relative_volume_20 and volume_z percentile ranks."""
    idx = row.name
    ranks = [relative_volume_rank.loc[idx], volume_z_rank.loc[idx]]
    ranks = [value for value in ranks if pd.notna(value)]
    if not ranks:
        return np.nan
    score = float(np.mean(ranks))
    if score <= thresholds["participation_weak_pct"]:
        return "weak"
    if score >= thresholds["participation_strong_pct"]:
        return "strong"
    return "normal"


def classify_risk_state(row: pd.Series, thresholds: dict[str, float]) -> str | float:
    """Classify risk balance from calibrated hazard probabilities, HMM shock probability, and SAFE risk-off flag."""
    if any(pd.isna(row[column]) for column in ("P_CORRECTION_10D_CAL", "P_REBOUND_10D_CAL", "P_SHOCK_HMM", "hard_risk_off_flag_safe")):
        return np.nan
    if row["hard_risk_off_flag_safe"] >= 0.5:
        return "risk_off"

    asymmetry = float(row["P_REBOUND_10D_CAL"] - row["P_CORRECTION_10D_CAL"])
    if row["P_SHOCK_HMM"] >= thresholds["shock_risk_threshold"] and asymmetry <= 0:
        return "downside_risk_elevated"
    if asymmetry <= -thresholds["risk_asymmetry_threshold"]:
        return "downside_risk_elevated"
    if asymmetry >= thresholds["risk_asymmetry_threshold"]:
        return "rebound_potential_elevated"
    return "balanced"


def synthesize_market_regime(row: pd.Series) -> str | float:
    """Synthesize a compact human-readable regime from the rule-based dimensions."""
    required = ("trend_state", "vol_state", "position_state", "participation_state", "risk_state", "state_hmm_label")
    if any(pd.isna(row[column]) for column in required):
        return np.nan

    if row["risk_state"] == "risk_off" or (row["state_hmm_label"] == "SHOCK" and row["vol_state"] in {"elevated", "very_high"}):
        return "high_vol_stress"
    if row["risk_state"] == "downside_risk_elevated" and row["trend_state"] == "bearish":
        return "downside_risk"
    if row["risk_state"] == "rebound_potential_elevated" and row["position_state"] == "lower_band_area":
        return "rebound_setup"
    if row["trend_state"] == "bullish" and row["participation_state"] in {"normal", "strong"} and row["risk_state"] == "balanced":
        return "constructive_trend"
    if row["trend_state"] == "bullish":
        return "fragile_trend"
    if row["trend_state"] == "mixed" and row["vol_state"] == "low" and row["position_state"] == "mid_range":
        return "compressed_balance"
    if row["trend_state"] == "mixed" and row["risk_state"] == "balanced":
        return "neutral_balance"
    return "transitional_mix"


def compute_states(feature_frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Compute HMM-derived and rule-based state columns."""
    validated = _validate_inputs(feature_frame)
    thresholds = build_thresholds(validated)

    states = pd.DataFrame(index=validated.index)
    states["state_hmm_label"] = validated["HMM_LABEL"]
    states["state_hmm_conf"] = validated["HMM_CONF"]
    states["state_hmm_dom"] = validated["HMM_DOM"]

    atr_pct_rank = percentile_rank(validated["atr_pct"])
    vol_20_rank = percentile_rank(validated["vol_20"])
    relative_volume_rank = percentile_rank(validated["relative_volume_20"])
    volume_z_rank = percentile_rank(validated["volume_z"])

    states["trend_state"] = validated.apply(classify_trend_state, axis=1)
    states["vol_state"] = validated.apply(classify_vol_state, axis=1, atr_pct_rank=atr_pct_rank, vol_20_rank=vol_20_rank)
    states["position_state"] = validated.apply(classify_position_state, axis=1, thresholds=thresholds)
    states["participation_state"] = validated.apply(
        classify_participation_state,
        axis=1,
        relative_volume_rank=relative_volume_rank,
        volume_z_rank=volume_z_rank,
        thresholds=thresholds,
    )
    states["risk_state"] = validated.apply(classify_risk_state, axis=1, thresholds=thresholds)

    states["state_rule_compact"] = states.loc[:, ["trend_state", "vol_state", "position_state", "participation_state", "risk_state"]].agg(
        lambda values: "|".join(values.astype(str)) if values.notna().all() else np.nan,
        axis=1,
    )
    states["state_market_regime"] = pd.concat([validated, states], axis=1).apply(synthesize_market_regime, axis=1)
    return states.loc[:, list(STATE_COLUMNS)], thresholds


def _count_lines(series: pd.Series) -> list[str]:
    counts = series.fillna("missing").value_counts(dropna=False)
    return [f"- `{index}`: {int(value)}" for index, value in counts.items()]


def render_markdown(states: pd.DataFrame, thresholds: dict[str, float]) -> str:
    """Render a compact human-readable summary of the state definitions and counts."""
    latest = states.iloc[-1]
    lines = [
        "# States",
        "",
        "This file defines explicit market states from SAFE features. The rule-based states are deterministic and auditable; they do not change model logic.",
        "",
        "## Definitions",
        "",
        "- `state_hmm_label`: copied from `HMM_LABEL`.",
        "- `state_hmm_conf`: copied from `HMM_CONF`.",
        "- `state_hmm_dom`: copied from `HMM_DOM`.",
        "- `trend_state`: bullish if at least 2 of `TS_20`, `TS_50`, `TS_200` are positive; bearish if at least 2 are negative; otherwise mixed.",
        "- `vol_state`: average percentile rank of `atr_pct` and `vol_20` bucketed into `low`, `moderate`, `elevated`, `very_high` by quartiles.",
        f"- `position_state`: `lower_band_area` if `band_pos <= {thresholds['position_lower_max']:.4f}`, `upper_band_area` if `band_pos >= {thresholds['position_upper_min']:.4f}`, else `mid_range`.",
        f"- `participation_state`: average percentile rank of `relative_volume_20` and `volume_z`; weak <= {thresholds['participation_weak_pct']:.2f}, strong >= {thresholds['participation_strong_pct']:.2f}, else normal.",
        f"- `risk_state`: `risk_off` if `hard_risk_off_flag_safe == 1`; `downside_risk_elevated` if correction-rebound asymmetry <= -{thresholds['risk_asymmetry_threshold']:.2f} or `P_SHOCK_HMM >= {thresholds['shock_risk_threshold']:.2f}` with non-positive asymmetry; `rebound_potential_elevated` if asymmetry >= {thresholds['risk_asymmetry_threshold']:.2f}; else balanced.",
        "- `state_rule_compact`: `trend|vol|position|participation|risk`.",
        "- `state_market_regime`: deterministic synthesis into labels such as `constructive_trend`, `fragile_trend`, `high_vol_stress`, `compressed_balance`, `rebound_setup`, `downside_risk`.",
        "",
        "## Threshold Snapshot",
        "",
        f"- `atr_pct` quartiles: q25={thresholds['atr_pct_q25']:.6f}, q50={thresholds['atr_pct_q50']:.6f}, q75={thresholds['atr_pct_q75']:.6f}",
        f"- `vol_20` quartiles: q25={thresholds['vol_20_q25']:.6f}, q50={thresholds['vol_20_q50']:.6f}, q75={thresholds['vol_20_q75']:.6f}",
        "",
        "## Dimension Counts",
        "",
        "### HMM labels",
        *_count_lines(states["state_hmm_label"]),
        "",
        "### trend_state",
        *_count_lines(states["trend_state"]),
        "",
        "### vol_state",
        *_count_lines(states["vol_state"]),
        "",
        "### position_state",
        *_count_lines(states["position_state"]),
        "",
        "### participation_state",
        *_count_lines(states["participation_state"]),
        "",
        "### risk_state",
        *_count_lines(states["risk_state"]),
        "",
        "## Composite State Counts",
        "",
        "### state_rule_compact",
        *_count_lines(states["state_rule_compact"]),
        "",
        "### state_market_regime",
        *_count_lines(states["state_market_regime"]),
        "",
        "## Latest State",
        "",
        f"- date: `{states.index[-1].strftime('%Y-%m-%d')}`",
        f"- state_hmm_label: `{latest['state_hmm_label']}`",
        f"- state_hmm_conf: `{float(latest['state_hmm_conf']):.6f}`" if pd.notna(latest["state_hmm_conf"]) else "- state_hmm_conf: `missing`",
        f"- trend_state: `{latest['trend_state']}`",
        f"- vol_state: `{latest['vol_state']}`",
        f"- position_state: `{latest['position_state']}`",
        f"- participation_state: `{latest['participation_state']}`",
        f"- risk_state: `{latest['risk_state']}`",
        f"- state_rule_compact: `{latest['state_rule_compact']}`",
        f"- state_market_regime: `{latest['state_market_regime']}`",
        "",
    ]
    return "\n".join(lines)


def print_summary(states: pd.DataFrame, out_csv: Path) -> None:
    """Print a compact CLI summary for the state-definition stage."""
    latest = states.iloc[-1]
    distinct_compact = int(states["state_rule_compact"].dropna().nunique())
    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(states)}")
    print(f"Distinct rule-based composite states: {distinct_compact}")
    print("Latest state snapshot:")
    print(f"  date: {states.index[-1].strftime('%Y-%m-%d')}")
    print(f"  state_hmm_label: {latest['state_hmm_label']}")
    print(f"  trend_state: {latest['trend_state']}")
    print(f"  vol_state: {latest['vol_state']}")
    print(f"  position_state: {latest['position_state']}")
    print(f"  participation_state: {latest['participation_state']}")
    print(f"  risk_state: {latest['risk_state']}")
    print(f"  state_market_regime: {latest['state_market_regime']}")


def main() -> None:
    """Run the SAFE v4.0 Phase 4 state-definition stage."""
    try:
        args = parse_args()
        features = load_feature_csv(args.features_csv).set_index("date")
        states, thresholds = compute_states(features)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_feature_csv(states, out_csv, columns=list(STATE_COLUMNS))
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(states, thresholds), encoding="utf-8")

        print_summary(states, out_csv)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"State pipeline failed: {exc}") from exc


if __name__ == "__main__":
    main()
