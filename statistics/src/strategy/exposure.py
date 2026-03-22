from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd


Mode = Literal["safe", "aggr"]
HMM_STATE_KEYS: tuple[str, ...] = tuple(f"HMM_STATE_{k}" for k in range(4))
SEMANTIC_HMM_COLUMNS: tuple[str, ...] = (
    "P_CORE_HMM",
    "P_DRIFT_HMM",
    "P_SHOCK_HMM",
    "P_SURGE_HMM",
)


def _clip(x: float, lo: float, hi: float) -> float:
    return float(min(max(x, lo), hi))


@dataclass(frozen=True)
class ExposureConfig:
    """Configuration for SAFE and aggressive exposure targeting.

    SAFE is a nonzero-baseline, risk-modulated long allocation. Full flat
    exposure is allowed only through a distinct hard risk-off override when a
    high-confidence adverse regime and elevated correction risk align.
    """

    # SAFE baseline + modulation.
    E_base_safe: float = 0.15
    alpha_hazard: float = 2.0
    dom_floor: float = 0.35
    dom_span: float = 0.35

    # Hard risk-off override.
    enable_hard_risk_off: bool = True
    shock_prob_threshold: float = 0.70
    correction_prob_threshold: float = 0.65
    positive_regime_max: float = 0.30
    hmm_conf_risk_off_threshold: float = 0.60
    ts50_risk_off_threshold: float = 0.0
    band_pos_risk_off_threshold: float = 0.35
    risk_off_max_daily_change: float = 0.50

    # AGGR.
    d0: float = 0.10
    d1: float = 0.20
    L_cap: float = 2.0
    L_gain: float = 1.0

    # Smoothing.
    max_daily_change: float = 0.10


def _dominance_scale(dom: float, cfg: ExposureConfig) -> float:
    x = (dom - cfg.dom_floor) / cfg.dom_span
    return _clip(x, 0.0, 1.0)


def _finite_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(numeric):
        return None
    return numeric


def _get_semantic_hmm(row: pd.Series, use_hmm: bool = True) -> dict[str, float | str]:
    """Read semantic HMM regime signals.

    Primary path uses the cleaned semantic regime probabilities and labels.
    A low-cost legacy fallback is kept for older frames that only contain raw
    ``HMM_STATE_*`` columns.
    """
    if not use_hmm:
        return {
            "p_core": 0.50,
            "p_drift": 0.25,
            "p_shock": 0.25,
            "p_surge": 0.0,
            "label": "CORE",
            "confidence": 0.50,
        }

    semantic_values = {column: _finite_or_none(row.get(column)) for column in SEMANTIC_HMM_COLUMNS}
    if all(value is not None for value in semantic_values.values()):
        probs = np.array([semantic_values[column] for column in SEMANTIC_HMM_COLUMNS], dtype=float)
        probs = np.where(np.isfinite(probs), probs, 0.0)
        total = float(probs.sum())
        if total > 0.0:
            probs = probs / total
        else:
            probs[:] = 0.25

        label = row.get("HMM_LABEL")
        label = str(label) if isinstance(label, str) and label else str(SEMANTIC_HMM_COLUMNS[int(np.argmax(probs))].removeprefix("P_").removesuffix("_HMM"))
        confidence = _finite_or_none(row.get("HMM_CONF"))
        if confidence is None:
            confidence = float(np.max(probs))

        return {
            "p_core": float(probs[0]),
            "p_drift": float(probs[1]),
            "p_shock": float(probs[2]),
            "p_surge": float(probs[3]),
            "label": label,
            "confidence": float(_clip(confidence, 0.0, 1.0)),
        }

    # Legacy fallback: older pipelines assumed state0 positive, state1 adverse,
    # states2/3 neutral-range. Keep this only for compatibility.
    if all(key in row.index for key in HMM_STATE_KEYS):
        probs = np.array([_finite_or_none(row.get(key)) or 0.0 for key in HMM_STATE_KEYS], dtype=float)
        total = float(probs.sum())
        if total > 0.0:
            probs = probs / total
        else:
            probs[:] = 0.25

        p_drift = float(probs[0])
        p_shock = float(probs[1])
        p_core = float(probs[2] + probs[3])
        p_surge = 0.0
        semantic_probs = {
            "CORE": p_core,
            "DRIFT": p_drift,
            "SHOCK": p_shock,
            "SURGE": p_surge,
        }
        confidence = _finite_or_none(row.get("HMM_CONF"))
        if confidence is None:
            confidence = max(semantic_probs.values())
        label = max(semantic_probs, key=semantic_probs.get)
        return {
            "p_core": p_core,
            "p_drift": p_drift,
            "p_shock": p_shock,
            "p_surge": p_surge,
            "label": label,
            "confidence": float(_clip(confidence, 0.0, 1.0)),
        }

    raise ValueError(
        "Exposure stage requires semantic HMM outputs (P_CORE_HMM, P_DRIFT_HMM, P_SHOCK_HMM, P_SURGE_HMM) "
        "or legacy HMM_STATE_* compatibility columns."
    )


def _get_hazards(row: pd.Series) -> tuple[float, float]:
    """Read calibrated hazard probabilities with low-cost legacy fallbacks."""
    p_corr = _finite_or_none(row.get("P_CORRECTION_10D_CAL"))
    if p_corr is None:
        p_corr = _finite_or_none(row.get("P_CORRECTION_10D"))
    p_reb = _finite_or_none(row.get("P_REBOUND_10D_CAL"))
    if p_reb is None:
        p_reb = _finite_or_none(row.get("P_REBOUND_10D"))

    if p_corr is None:
        p_corr = 0.20
    if p_reb is None:
        p_reb = 0.20
    return _clip(p_corr, 0.0, 1.0), _clip(p_reb, 0.0, 1.0)


def _regime_support(hmm: dict[str, float | str]) -> tuple[float, float, float, float]:
    p_core = float(hmm["p_core"])
    p_drift = float(hmm["p_drift"])
    p_shock = float(hmm["p_shock"])
    p_surge = float(hmm["p_surge"])
    positive_regime = _clip(p_drift + p_surge, 0.0, 1.0)
    supportive_regime = _clip(positive_regime + 0.50 * p_core, 0.0, 1.0)
    directional_score = _clip(positive_regime - p_shock, -1.0, 1.0)
    return positive_regime, supportive_regime, p_shock, directional_score


def _evaluate_hard_risk_off(
    row: pd.Series,
    hmm: dict[str, float | str],
    p_corr: float,
    cfg: ExposureConfig,
) -> bool:
    """Return ``True`` only for explicit high-confidence SAFE risk-off conditions."""
    if not cfg.enable_hard_risk_off:
        return False

    positive_regime, _, p_shock, _ = _regime_support(hmm)
    confidence = float(hmm["confidence"])
    label = str(hmm["label"])

    ts50 = _finite_or_none(row.get("TS_50"))
    band_pos = _finite_or_none(row.get("band_pos"))
    trend_weak = ts50 is not None and ts50 <= cfg.ts50_risk_off_threshold
    structure_weak = band_pos is not None and band_pos <= cfg.band_pos_risk_off_threshold
    confident_shock = label == "SHOCK" and confidence >= cfg.hmm_conf_risk_off_threshold

    return bool(
        p_shock >= cfg.shock_prob_threshold
        and positive_regime <= cfg.positive_regime_max
        and p_corr >= cfg.correction_prob_threshold
        and (trend_weak or structure_weak or confident_shock)
    )


def compute_targets_for_row(
    row: pd.Series,
    mode: Mode,
    cfg: ExposureConfig | None = None,
    *,
    use_hmm: bool = True,
    health: float | None = None,
    prev_exposure: float = 0.0,
    prev_direction: int = 0,
) -> dict[str, float]:
    """Compute a single-row exposure target.

    SAFE normally keeps a nonzero baseline floor and scales around it using
    regime conviction and calibrated hazards. Full flat exposure is only
    allowed through a distinct hard risk-off override.
    """
    if cfg is None:
        cfg = ExposureConfig()

    hmm = _get_semantic_hmm(row, use_hmm=use_hmm)
    p_corr, p_reb = _get_hazards(row)
    positive_regime, supportive_regime, _, directional_score = _regime_support(hmm)

    health_value = 1.0 if health is None else _clip(float(health), 0.0, 1.0)
    dom_scale = _dominance_scale(float(hmm["confidence"]), cfg)
    conviction = _clip(supportive_regime * dom_scale, 0.0, 1.0)

    hard_risk_off = _evaluate_hard_risk_off(row, hmm, p_corr, cfg)

    if mode == "safe":
        if hard_risk_off:
            e_star = 0.0
            max_change = cfg.risk_off_max_daily_change
        else:
            risk_throttle = health_value * ((1.0 - p_corr) ** cfg.alpha_hazard)
            risk_throttle = _clip(risk_throttle, 0.0, 1.0)
            e_star = cfg.E_base_safe + (1.0 - cfg.E_base_safe) * conviction * risk_throttle
            e_star = _clip(e_star, 0.0, 1.0)
            max_change = cfg.max_daily_change

        e_target = _clip(
            prev_exposure + _clip(e_star - prev_exposure, -max_change, max_change),
            0.0,
            1.0,
        )
        entry_step = max(0.0, e_target - prev_exposure)
        return {
            "direction": 1.0,
            "E_target": float(e_target),
            "L_target": 1.0,
            "entry_step": float(entry_step),
            "conviction": float(conviction),
            "D_score": float(directional_score),
            "p_corr": float(p_corr),
            "p_reb": float(p_reb),
            "hard_risk_off_flag": float(hard_risk_off),
        }

    if hard_risk_off:
        direction = 0.0
        e_star = 0.0
        hazard_for_direction = p_corr
        max_change = cfg.risk_off_max_daily_change
    else:
        direction = 0.0
        if prev_direction >= 0:
            if directional_score > cfg.d0:
                direction = 1.0
            elif directional_score < -cfg.d1:
                direction = -1.0
        else:
            if directional_score < -cfg.d0:
                direction = -1.0
            elif directional_score > cfg.d1:
                direction = 1.0

        hazard_for_direction = p_corr if direction >= 0 else p_reb
        risk_throttle = health_value * ((1.0 - hazard_for_direction) ** cfg.alpha_hazard)
        risk_throttle = _clip(risk_throttle, 0.0, 1.0)
        e_star = _clip(direction * conviction * risk_throttle, -1.0, 1.0)
        max_change = cfg.max_daily_change

    e_target = _clip(
        prev_exposure + _clip(e_star - prev_exposure, -max_change, max_change),
        -1.0,
        1.0,
    )
    leverage_fast = _clip(positive_regime, 0.0, 1.0)
    l_star = 1.0 + cfg.L_gain * (cfg.L_cap - 1.0) * leverage_fast * conviction * (1.0 - hazard_for_direction)
    l_target = _clip(l_star, 1.0, cfg.L_cap)

    entry_step = 0.0
    if np.sign(e_target) == np.sign(prev_exposure) or prev_exposure == 0.0:
        entry_step = max(0.0, abs(e_target) - abs(prev_exposure))

    return {
        "direction": float(direction),
        "E_target": float(e_target),
        "L_target": float(l_target),
        "entry_step": float(entry_step),
        "conviction": float(conviction),
        "D_score": float(directional_score),
        "p_corr": float(p_corr),
        "p_reb": float(p_reb),
        "hard_risk_off_flag": float(hard_risk_off),
    }


def compute_exposure_series(
    features: pd.DataFrame,
    mode: Mode,
    cfg: ExposureConfig | None = None,
    *,
    use_hmm: bool = True,
    health_series: pd.Series | None = None,
) -> pd.DataFrame:
    """Run exposure targeting over time with stateful smoothing.

    SAFE keeps a normal nonzero baseline floor during standard operation.
    Hard risk-off can drive the target to zero, and it de-risks faster than
    routine exposure adjustments.
    """
    if cfg is None:
        cfg = ExposureConfig()

    df = features.copy()
    dir_col = f"direction_{mode}"
    e_col = f"E_target_{mode}"
    l_col = f"L_target_{mode}"
    step_col = f"entry_step_{mode}"
    conv_col = f"conviction_{mode}"
    d_col = f"D_score_{mode}"
    risk_off_col = f"hard_risk_off_flag_{mode}"

    prev_e = 0.0 if mode == "aggr" else cfg.E_base_safe
    prev_dir = 1 if mode == "safe" else 0

    out_dir: list[float] = []
    out_e: list[float] = []
    out_l: list[float] = []
    out_step: list[float] = []
    out_conv: list[float] = []
    out_d: list[float] = []
    out_risk_off: list[float] = []

    for idx, row in df.iterrows():
        health = None
        if health_series is not None and idx in health_series.index:
            health = float(health_series.loc[idx])

        result = compute_targets_for_row(
            row,
            mode,
            cfg,
            use_hmm=use_hmm,
            health=health,
            prev_exposure=prev_e,
            prev_direction=prev_dir,
        )

        prev_e = float(result["E_target"])
        prev_dir = int(np.sign(result["direction"]))

        out_dir.append(float(result["direction"]))
        out_e.append(float(result["E_target"]))
        out_l.append(float(result["L_target"]))
        out_step.append(float(result["entry_step"]))
        out_conv.append(float(result["conviction"]))
        out_d.append(float(result["D_score"]))
        out_risk_off.append(float(result["hard_risk_off_flag"]))

    df[dir_col] = out_dir
    df[e_col] = out_e
    df[l_col] = out_l
    df[step_col] = out_step
    df[conv_col] = out_conv
    df[d_col] = out_d
    df[risk_off_col] = out_risk_off
    return df
