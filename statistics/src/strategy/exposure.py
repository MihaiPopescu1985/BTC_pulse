from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Dict, Tuple
import numpy as np
import pandas as pd


Mode = Literal["safe", "aggr"]


HMM_STATE_KEYS = [f"HMM_STATE_{k}" for k in range(4)]


def _clip(x: float, lo: float, hi: float) -> float:
    return float(min(max(x, lo), hi))


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


@dataclass(frozen=True)
class ExposureConfig:
    # SAFE
    E_base_safe: float = 0.35     # "mai in piata"
    alpha_hazard: float = 2.0     # how strongly hazard throttles exposure
    dom_floor: float = 0.35       # minimum dominance for confidence
    dom_span: float = 0.35        # dominance scaling span

    # AGGR
    d0: float = 0.10              # deadzone for direction
    d1: float = 0.20              # hysteresis threshold
    L_cap: float = 2.0            # max leverage
    L_gain: float = 1.0           # leverage gain multiplier

    # Smoothing (avoid jerk)
    max_daily_change: float = 0.10  # cap change in exposure per day (10%)


def _dominance_scale(dom: float, cfg: ExposureConfig) -> float:
    # scale to [0,1]
    x = (dom - cfg.dom_floor) / cfg.dom_span
    return _clip(x, 0.0, 1.0)


def _get_state_probs(row: pd.Series) -> Tuple[np.ndarray, int, float]:
    """
    Pull HMM state probabilities from row.
    Returns (probs, regime_id, confidence).
    """
    missing = [k for k in HMM_STATE_KEYS if k not in row.index]
    assert not missing, f"Missing HMM state columns: {missing}"

    probs = np.array([float(row.get(k, 0.0)) for k in HMM_STATE_KEYS], dtype=float)
    probs = np.where(np.isfinite(probs), probs, 0.0)
    s = float(np.sum(probs))
    if s > 0:
        probs = probs / s
    else:
        probs[:] = 1.0 / len(probs)

    regime_id = int(np.argmax(probs))
    confidence = float(np.max(probs))
    return probs, regime_id, confidence


def _get_hazards(row: pd.Series) -> Tuple[float, float]:
    # Prefer CAL2 (hazard conditioned on regimes), then CAL, then heuristic
    pc = row.get("P_CORRECTION_10D_CAL2",
         row.get("P_CORRECTION_10D_CAL",
         row.get("P_CORRECTION_10D", np.nan)))
    pr = row.get("P_REBOUND_10D_CAL2",
         row.get("P_REBOUND_10D_CAL",
         row.get("P_REBOUND_10D", np.nan)))

    pc = float(pc) if np.isfinite(pc) else 0.2
    pr = float(pr) if np.isfinite(pr) else 0.2
    return _clip(pc, 0.0, 1.0), _clip(pr, 0.0, 1.0)


def compute_targets_for_row(
    row: pd.Series,
    mode: Mode,
    cfg: ExposureConfig = ExposureConfig(),
    *,
    use_hmm: bool = True,
    health: float | None = None,
    prev_exposure: float = 0.0,
    prev_direction: int = 0,  # -1 short, 0 neutral, +1 long
) -> Dict[str, float]:
    """
    Returns dict:
      direction (-1/0/+1)
      E_target (signed for aggr, 0..1 for safe)
      L_target (>=1)
      entry_step (how much to add if E_target > prev)
      conviction (debug)
      D_score (debug)
    """
    # use_hmm kept for compatibility; HMM_STATE_* required now.
    probs, regime_id, confidence = _get_state_probs(row)
    # Temporary mapping: state 0=up, 1=down, 2/3=range
    p_up, p_down, p_range_low, p_range_high = probs
    p_range = p_range_low + p_range_high
    p_corr, p_reb = _get_hazards(row)

    # Health: if you don't have it yet, default to 1.0 (BTC long-term assumption)
    H = 1.0 if health is None else _clip(float(health), 0.0, 1.0)

    # Conviction: non-range mass * dominance scale
    C = _clip(1.0 - p_range, 0.0, 1.0)

    DomScale = _dominance_scale(confidence, cfg)

    conviction = _clip(C * DomScale, 0.0, 1.0)

    # Direction score
    D = p_up - p_down

    if mode == "safe":
        # Always long, but modulate exposure target
        RT_long = H * ((1.0 - p_corr) ** cfg.alpha_hazard)
        RT_long = _clip(RT_long, 0.0, 1.0)

        E_star = cfg.E_base_safe + (1.0 - cfg.E_base_safe) * conviction * RT_long
        E_star = _clip(E_star, 0.0, 1.0)

        # Smooth changes (no sudden dumps)
        E_target = _clip(
            prev_exposure + _clip(E_star - prev_exposure, -cfg.max_daily_change, cfg.max_daily_change),
            0.0, 1.0
        )

        # Entry step is only for increasing exposure
        entry_step = max(0.0, E_target - prev_exposure)

        return {
            "direction": 1.0,
            "E_target": float(E_target),
            "L_target": 1.0,
            "entry_step": float(entry_step),
            "conviction": float(conviction),
            "D_score": float(D),
            "p_corr": float(p_corr),
            "p_reb": float(p_reb),
        }

    # AGGRESSIVE mode
    # Determine desired direction with hysteresis
    direction = 0
    if prev_direction >= 0:
        if D > cfg.d0:
            direction = 1
        elif D < -cfg.d1:
            direction = -1
        else:
            direction = 0
    else:
        if D < -cfg.d0:
            direction = -1
        elif D > cfg.d1:
            direction = 1
        else:
            direction = 0

    # Risk throttle depends on direction
    if direction >= 0:
        hazard = p_corr
    else:
        hazard = p_reb

    RT = H * ((1.0 - hazard) ** cfg.alpha_hazard)
    RT = _clip(RT, 0.0, 1.0)

    # Signed exposure target
    E_star = float(direction) * conviction * RT
    E_star = _clip(E_star, -1.0, 1.0)

    # Smooth
    E_target = _clip(
        prev_exposure + _clip(E_star - prev_exposure, -cfg.max_daily_change, cfg.max_daily_change),
        -1.0, 1.0
    )

    # Leverage: higher in FAST regimes, lower when hazard high or conviction low
    p_fast = p_up + p_down
    L_star = 1.0 + cfg.L_gain * (cfg.L_cap - 1.0) * p_fast * conviction * (1.0 - hazard)
    L_target = _clip(L_star, 1.0, cfg.L_cap)

    # entry step only if increasing magnitude in same direction
    entry_step = 0.0
    if np.sign(E_target) == np.sign(prev_exposure) or prev_exposure == 0.0:
        entry_step = max(0.0, abs(E_target) - abs(prev_exposure))

    return {
        "direction": float(direction),
        "E_target": float(E_target),
        "L_target": float(L_target),
        "entry_step": float(entry_step),
        "conviction": float(conviction),
        "D_score": float(D),
        "p_corr": float(p_corr),
        "p_reb": float(p_reb),
    }


def compute_exposure_series(
    features: pd.DataFrame,
    mode: Mode,
    cfg: ExposureConfig = ExposureConfig(),
    *,
    use_hmm: bool = True,
    health_series: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Runs exposure function over time with memory (prev_exposure, prev_direction).
    Adds columns:
      direction_{mode}
      E_target_{mode}
      L_target_{mode}
      entry_step_{mode}
      conviction_{mode}
      D_score_{mode}
    """
    df = features.copy()

    dir_col = f"direction_{mode}"
    e_col = f"E_target_{mode}"
    l_col = f"L_target_{mode}"
    step_col = f"entry_step_{mode}"
    conv_col = f"conviction_{mode}"
    d_col = f"D_score_{mode}"

    prev_e = 0.0 if mode == "aggr" else cfg.E_base_safe
    prev_dir = 1 if mode == "safe" else 0

    out_dir = []
    out_e = []
    out_l = []
    out_step = []
    out_conv = []
    out_d = []

    for idx, row in df.iterrows():
        H = None
        if health_series is not None and idx in health_series.index:
            H = float(health_series.loc[idx])

        res = compute_targets_for_row(
            row, mode, cfg, use_hmm=use_hmm, health=H,
            prev_exposure=prev_e, prev_direction=prev_dir
        )

        prev_e = float(res["E_target"])
        prev_dir = int(np.sign(res["direction"]))

        out_dir.append(res["direction"])
        out_e.append(res["E_target"])
        out_l.append(res["L_target"])
        out_step.append(res["entry_step"])
        out_conv.append(res["conviction"])
        out_d.append(res["D_score"])

    df[dir_col] = out_dir
    df[e_col] = out_e
    df[l_col] = out_l
    df[step_col] = out_step
    df[conv_col] = out_conv
    df[d_col] = out_d

    return df
