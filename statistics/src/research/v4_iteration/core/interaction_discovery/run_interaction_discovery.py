from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_ONCHAIN_FEATURES_CSV_PATH, DEFAULT_TARGETS_CSV_PATH, OUT_DIR


@dataclass(frozen=True)
class Template:
    name: str
    family: str
    intent: str
    description: str
    builder: Callable[[pd.DataFrame, dict[str, float]], pd.Series]


TARGETS: tuple[str, ...] = (
    "ret_10d",
    "max_up_10d",
    "max_down_10d",
    "touch_up_2pct_10d",
    "touch_down_2pct_10d",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research-stage interaction discovery across validated SAFE indicator families.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument(
        "--onchain-features-csv",
        default=str(DEFAULT_ONCHAIN_FEATURES_CSV_PATH),
        help="Default: ../out/onchain_features.csv",
    )
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument(
        "--out-csv",
        default=str(OUT_DIR / "interaction_discovery" / "interaction_discovery.csv"),
        help="Default: ../out/interaction_discovery/interaction_discovery.csv",
    )
    return parser.parse_args()


def load_dataset(features_path: str | Path, onchain_path: str | Path, targets_path: str | Path) -> pd.DataFrame:
    features = load_feature_csv(features_path)
    onchain = load_feature_csv(onchain_path)
    targets = load_feature_csv(targets_path)

    merged = (
        features.merge(onchain, on="date", how="inner", validate="one_to_one")
        .merge(targets, on="date", how="inner", validate="one_to_one")
        .sort_values("date")
        .reset_index(drop=True)
    )
    if merged.empty:
        raise ValueError("Interaction discovery dataset is empty after joining features, on-chain features, and targets.")
    return merged


def quantile_cutoffs(frame: pd.DataFrame) -> dict[str, float]:
    columns = [
        "ER_20",
        "ER_50",
        "dist_from_mean_vol_units",
        "band_pos",
        "band_w",
        "atr_pct",
        "ewma_vol",
        "upside_semi_vol",
        "downside_semi_vol",
        "relative_volume_20",
        "volume_z",
        "P_CORRECTION_10D_CAL",
        "P_REBOUND_10D_CAL",
        "P_SHOCK_HMM",
        "P_SURGE_HMM",
        "P_CORE_HMM",
        "ONCHAIN_VOL_Z",
        "ONCHAIN_DOM_Z",
        "ONCHAIN_WHALE_SHARE_Z",
    ]
    quantiles: dict[str, float] = {}
    for column in columns:
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        for q in (0.25, 0.50, 0.75, 0.90):
            quantiles[f"{column}_q{int(q * 100):02d}"] = float(series.quantile(q))
    return quantiles


def build_templates() -> list[Template]:
    return [
        Template(
            name="constructive_pullback",
            family="trend_position_regime",
            intent="upside",
            description="TS_50 > 0, TS_200 > 0, ER_50 at least median, mild pullback from mean, correction risk at or below median, shock risk low.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["TS_200"] > 0)
                & (df["ER_50"] >= q["ER_50_q50"])
                & (df["dist_from_mean_vol_units"] <= q["dist_from_mean_vol_units_q50"])
                & (df["P_CORRECTION_10D_CAL"] <= q["P_CORRECTION_10D_CAL_q50"])
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
            ),
        ),
        Template(
            name="clean_breakout_continuation",
            family="trend_volatility",
            intent="upside",
            description="Short and medium trend aligned, ER_20 high, ER_50 at least median, not already stretched, upside semivol > downside semivol.",
            builder=lambda df, q: (
                (df["TS_20"] > 0)
                & (df["TS_50"] > 0)
                & (df["ER_20"] >= q["ER_20_q75"])
                & (df["ER_50"] >= q["ER_50_q50"])
                & (df["dist_from_mean_vol_units"] <= q["dist_from_mean_vol_units_q75"])
                & (df["upside_semi_vol"] > df["downside_semi_vol"])
            ),
        ),
        Template(
            name="expansion_with_participation",
            family="trend_volatility_participation",
            intent="upside",
            description="Positive medium trend, clean structure, expanding volatility, above-normal participation, low shock risk.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["ER_50"] >= q["ER_50_q75"])
                & ((df["ewma_vol"] >= q["ewma_vol_q75"]) | (df["atr_pct"] >= q["atr_pct_q75"]))
                & ((df["relative_volume_20"] >= q["relative_volume_20_q75"]) | (df["volume_z"] >= q["volume_z_q75"]))
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
            ),
        ),
        Template(
            name="regime_supported_upside",
            family="trend_regime",
            intent="upside",
            description="Supportive trend plus high rebound probability, low correction probability, and low shock regime probability.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["TS_200"] > 0)
                & (df["ER_50"] >= q["ER_50_q50"])
                & (df["P_REBOUND_10D_CAL"] >= q["P_REBOUND_10D_CAL_q75"])
                & (df["P_CORRECTION_10D_CAL"] <= q["P_CORRECTION_10D_CAL_q25"])
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
            ),
        ),
        Template(
            name="structural_onchain_tailwind",
            family="trend_regime_onchain",
            intent="upside",
            description="Supportive trend and rebound context with strong on-chain dominance and flow anomalies.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["TS_200"] > 0)
                & (df["ER_50"] >= q["ER_50_q50"])
                & (df["P_REBOUND_10D_CAL"] >= q["P_REBOUND_10D_CAL_q75"])
                & (df["ONCHAIN_DOM_Z"] >= q["ONCHAIN_DOM_Z_q75"])
                & (df["ONCHAIN_VOL_Z"] >= q["ONCHAIN_VOL_Z_q75"])
            ),
        ),
        Template(
            name="squeeze_release_up",
            family="trend_position_participation",
            intent="upside",
            description="Positive medium trend, tight band width, clean trend, and improving participation.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["ER_50"] >= q["ER_50_q75"])
                & (df["band_w"] <= q["band_w_q25"])
                & ((df["relative_volume_20"] >= q["relative_volume_20_q75"]) | (df["volume_z"] >= q["volume_z_q75"]))
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
            ),
        ),
        Template(
            name="low_risk_base",
            family="trend_regime",
            intent="downside_avoidance",
            description="Positive long backdrop, low correction risk, low shock probability, and high core-state probability.",
            builder=lambda df, q: (
                (df["TS_200"] > 0)
                & (df["P_CORRECTION_10D_CAL"] <= q["P_CORRECTION_10D_CAL_q25"])
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
                & (df["P_CORE_HMM"] >= q["P_CORE_HMM_q75"])
            ),
        ),
        Template(
            name="low_risk_pullback",
            family="trend_position_regime",
            intent="downside_avoidance",
            description="Supportive structure with a mild pullback, correction risk at or below median, and low shock probability.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["TS_200"] > 0)
                & (df["dist_from_mean_vol_units"] <= q["dist_from_mean_vol_units_q50"])
                & (df["P_CORRECTION_10D_CAL"] <= q["P_CORRECTION_10D_CAL_q50"])
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
            ),
        ),
        Template(
            name="downside_avoidance_stack",
            family="trend_regime_onchain",
            intent="downside_avoidance",
            description="Positive backdrop, low risk regime context, and at least neutral-to-positive on-chain dominance.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["TS_200"] > 0)
                & (df["P_CORE_HMM"] >= q["P_CORE_HMM_q50"])
                & (df["P_CORRECTION_10D_CAL"] <= q["P_CORRECTION_10D_CAL_q25"])
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
                & (df["ONCHAIN_DOM_Z"] >= q["ONCHAIN_DOM_Z_q50"])
            ),
        ),
        Template(
            name="upside_probability_stack",
            family="full_stack",
            intent="touch_up",
            description="Supportive trend, clean structure, rebound skew, low shock risk, and positive on-chain/participation support.",
            builder=lambda df, q: (
                (df["TS_50"] > 0)
                & (df["TS_200"] > 0)
                & (df["ER_50"] >= q["ER_50_q75"])
                & (df["P_REBOUND_10D_CAL"] >= q["P_REBOUND_10D_CAL_q75"])
                & (df["P_SHOCK_HMM"] <= q["P_SHOCK_HMM_q50"])
                & (df["relative_volume_20"] >= q["relative_volume_20_q50"])
                & (df["ONCHAIN_DOM_Z"] >= q["ONCHAIN_DOM_Z_q50"])
            ),
        ),
        Template(
            name="shock_whale_risk",
            family="regime_onchain",
            intent="downside",
            description="High shock regime probability with elevated whale-share anomaly and high correction risk.",
            builder=lambda df, q: (
                (df["P_SHOCK_HMM"] >= q["P_SHOCK_HMM_q90"])
                & (df["ONCHAIN_WHALE_SHARE_Z"] >= q["ONCHAIN_WHALE_SHARE_Z_q75"])
                & (df["P_CORRECTION_10D_CAL"] >= q["P_CORRECTION_10D_CAL_q75"])
            ),
        ),
        Template(
            name="bearish_high_risk_stack",
            family="trend_regime_volatility",
            intent="downside",
            description="Negative medium and long trend with high correction risk and downside semivol dominance.",
            builder=lambda df, q: (
                (df["TS_50"] < 0)
                & (df["TS_200"] < 0)
                & (df["P_CORRECTION_10D_CAL"] >= q["P_CORRECTION_10D_CAL_q75"])
                & (df["downside_semi_vol"] >= q["downside_semi_vol_q75"])
                & (df["downside_semi_vol"] > df["upside_semi_vol"])
            ),
        ),
        Template(
            name="rebound_attempt_against_weak_backdrop",
            family="trend_position_regime",
            intent="mixed",
            description="Short trend turns positive from a stretched-down position, but medium or long backdrop remains weak.",
            builder=lambda df, q: (
                (df["TS_20"] > 0)
                & ((df["TS_50"] <= 0) | (df["TS_200"] <= 0))
                & (df["dist_from_mean_vol_units"] <= q["dist_from_mean_vol_units_q25"])
                & (df["P_REBOUND_10D_CAL"] >= q["P_REBOUND_10D_CAL_q75"])
            ),
        ),
        Template(
            name="extended_noisy_chase",
            family="trend_position",
            intent="weakness",
            description="Positive short and medium trend but already stretched and low-cleanliness, a classic chase condition.",
            builder=lambda df, q: (
                (df["TS_20"] > 0)
                & (df["TS_50"] > 0)
                & (df["dist_from_mean_vol_units"] >= q["dist_from_mean_vol_units_q75"])
                & (df["band_pos"] >= q["band_pos_q75"])
                & ((df["ER_20"] <= q["ER_20_q25"]) | (df["ER_50"] <= q["ER_50_q25"]))
            ),
        ),
        Template(
            name="weak_mixed_high_noise",
            family="mixed",
            intent="weakness",
            description="Directionally unclear market with wide bands, low cleanliness, and no participation confirmation.",
            builder=lambda df, q: (
                (df["TS_20"].abs() <= abs(q["TS_20_q25"]) if "TS_20_q25" in q else df["TS_20"].abs() <= 0.13)
            ),
        ),
    ]


def build_additional_cutoffs(frame: pd.DataFrame, quantiles: dict[str, float]) -> dict[str, float]:
    quantiles = dict(quantiles)
    quantiles["TS_20_abs_neutral"] = float(pd.to_numeric(frame["TS_20"], errors="coerce").abs().quantile(0.25))
    return quantiles


def finalize_templates(templates: list[Template]) -> list[Template]:
    fixed: list[Template] = []
    for template in templates:
        if template.name != "weak_mixed_high_noise":
            fixed.append(template)
            continue
        fixed.append(
            Template(
                name=template.name,
                family=template.family,
                intent=template.intent,
                description="Directionally unclear market with wide bands, low cleanliness, and weak participation.",
                builder=lambda df, q: (
                    (df["TS_20"].abs() <= q["TS_20_abs_neutral"])
                    & (df["ER_20"] <= q["ER_20_q25"])
                    & (df["band_w"] >= q["band_w_q75"])
                    & (df["relative_volume_20"] <= q["relative_volume_20_q50"])
                ),
            )
        )
    return fixed


def summarize_condition(frame: pd.DataFrame, template: Template, mask: pd.Series) -> dict[str, float | int | str]:
    valid = frame.loc[mask].copy()
    rest = frame.loc[~mask].copy()
    row: dict[str, float | int | str] = {
        "condition_name": template.name,
        "condition_family": template.family,
        "intent": template.intent,
        "rule_definition": template.description,
        "sample_count": int(mask.sum()),
        "coverage_rate": float(mask.mean()),
    }

    for target in TARGETS:
        in_series = pd.to_numeric(valid[target], errors="coerce").dropna()
        out_series = pd.to_numeric(rest[target], errors="coerce").dropna()
        mean_value = float(in_series.mean()) if not in_series.empty else np.nan
        median_value = float(in_series.median()) if not in_series.empty else np.nan
        separation = mean_value - float(out_series.mean()) if (not in_series.empty and not out_series.empty) else np.nan

        row[f"{target}_mean"] = mean_value
        row[f"{target}_median"] = median_value
        row[f"{target}_separation_vs_rest"] = separation

        if target.startswith("ret_"):
            row[f"{target}_win_rate"] = float((in_series > 0).mean()) if not in_series.empty else np.nan
        else:
            row[f"{target}_win_rate"] = np.nan

        if target.startswith("touch_"):
            row[f"{target}_event_rate"] = float(in_series.mean()) if not in_series.empty else np.nan
        else:
            row[f"{target}_event_rate"] = np.nan

    return row


def add_rank_scores(summary: pd.DataFrame) -> pd.DataFrame:
    ranked = summary.copy()
    ranked["overall_rank_score_raw"] = (
        ranked["ret_10d_mean"].rank(pct=True)
        + ranked["max_up_10d_mean"].rank(pct=True)
        + ranked["touch_up_2pct_10d_event_rate"].rank(pct=True)
        + ranked["max_down_10d_mean"].rank(pct=True)
        + (1.0 - ranked["touch_down_2pct_10d_event_rate"].rank(pct=True))
    ) / 5.0
    ranked["upside_rank_score_raw"] = (
        ranked["ret_10d_mean"].rank(pct=True)
        + ranked["max_up_10d_mean"].rank(pct=True)
        + ranked["touch_up_2pct_10d_event_rate"].rank(pct=True)
    ) / 3.0
    ranked["downside_rank_score_raw"] = (
        ranked["max_down_10d_mean"].rank(pct=True)
        + (1.0 - ranked["touch_down_2pct_10d_event_rate"].rank(pct=True))
        + ranked["ret_10d_mean"].rank(pct=True)
    ) / 3.0
    ranked["sample_weight"] = ranked["sample_count"].clip(lower=0, upper=75) / 75.0
    ranked["overall_rank_score"] = ranked["overall_rank_score_raw"] * ranked["sample_weight"]
    ranked["upside_rank_score"] = ranked["upside_rank_score_raw"] * ranked["sample_weight"]
    ranked["downside_rank_score"] = ranked["downside_rank_score_raw"] * ranked["sample_weight"]
    return ranked.sort_values(["overall_rank_score", "sample_count"], ascending=[False, False]).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    dataset = load_dataset(args.features_csv, args.onchain_features_csv, args.targets_csv)
    quantiles = build_additional_cutoffs(dataset, quantile_cutoffs(dataset))
    templates = finalize_templates(build_templates())

    summaries: list[dict[str, float | int | str]] = []
    for template in templates:
        mask = template.builder(dataset, quantiles).fillna(False)
        summaries.append(summarize_condition(dataset, template, mask))

    summary_frame = add_rank_scores(pd.DataFrame(summaries))
    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(out_path, index=False)

    print(f"rows_scanned={len(dataset)}")
    print(f"conditions_tested={len(summary_frame)}")
    best = summary_frame.iloc[0]
    print(
        "best_overall="
        f"{best['condition_name']} "
        f"(overall_rank_score={best['overall_rank_score']:.3f}, sample_count={int(best['sample_count'])})"
    )
    print(f"wrote={out_path}")


if __name__ == "__main__":
    main()
