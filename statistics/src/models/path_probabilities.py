from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.util.safe_touch_probabilities import (
    HMMPackView,
    RegimeCalib,
    SEMANTIC_REGIME_KEYS,
    build_probability_frame,
    calibrate_regimes,
    load_hmm_pack_view,
    mixture_params,
    normalize_probs,
)


SimulationMode = Literal["mixture", "markov"]
AmbiguityMode = Literal["pessimistic", "optimistic", "skip_ambiguous", "label_as_both_same_day"]
PathLabel = Literal[
    "RANGE",
    "UP_FIRST_ONLY",
    "DOWN_FIRST_ONLY",
    "UP_THEN_DOWN",
    "DOWN_THEN_UP",
]

PATH_LABELS: tuple[PathLabel, ...] = (
    "RANGE",
    "UP_FIRST_ONLY",
    "DOWN_FIRST_ONLY",
    "UP_THEN_DOWN",
    "DOWN_THEN_UP",
)
AMBIGUOUS_REALIZED_LABEL = "AMBIGUOUS_BOTH_SAME_DAY"


@dataclass(frozen=True)
class PathBarrierSpec:
    anchor_close: float
    up_pct: float
    down_pct: float

    @property
    def upper_barrier(self) -> float:
        return self.anchor_close * (1.0 + self.up_pct)

    @property
    def lower_barrier(self) -> float:
        return self.anchor_close * (1.0 - self.down_pct)


@dataclass(frozen=True)
class PathProbabilityContext:
    """Precomputed context for path-probability estimation.

    Returns are calibrated from historical daily closes weighted by previous-day
    semantic HMM probabilities, matching the repository's existing touch
    probability logic. Inference for a specific anchor date uses the SAFE state
    on that anchor date and projects forward over the next ``H`` daily steps.
    """

    price_frame: pd.DataFrame
    probability_frame: pd.DataFrame
    calibrations: dict[str, RegimeCalib]
    hmm_pack_view: HMMPackView | None
    winsor_p: float


@dataclass(frozen=True)
class RealizedPathOutcome:
    label: str | None
    ambiguous: bool
    ambiguity_type: str | None
    first_upper_day: int | None
    first_lower_day: int | None
    upper_barrier: float
    lower_barrier: float
    forward_return: float | None


def _string_indexed_price_frame(price_frame: pd.DataFrame) -> pd.DataFrame:
    frame = price_frame.sort_index().copy()
    frame.index = pd.Index(frame.index.strftime("%Y-%m-%d"), name="date")
    return frame


def build_path_probability_context(
    price_frame: pd.DataFrame,
    features_dates: pd.Index,
    features_series: dict[str, list[float | None]],
    *,
    winsor_p: float = 0.0025,
    hmm_pack_path: Path | None = None,
) -> PathProbabilityContext:
    """Build a reusable simulation context from BTC OHLCV and SAFE features."""
    price_frame_by_date = _string_indexed_price_frame(price_frame)
    probability_frame = build_probability_frame(features_dates, features_series, SEMANTIC_REGIME_KEYS)
    calibrations = calibrate_regimes(
        price_frame_by_date["close"],
        probability_frame,
        SEMANTIC_REGIME_KEYS,
        winsor_p=winsor_p,
    )
    hmm_pack_view = load_hmm_pack_view(hmm_pack_path) if hmm_pack_path is not None else None
    return PathProbabilityContext(
        price_frame=price_frame_by_date,
        probability_frame=probability_frame,
        calibrations=calibrations,
        hmm_pack_view=hmm_pack_view,
        winsor_p=winsor_p,
    )


def conditioning_probabilities_for_anchor(
    probability_frame: pd.DataFrame,
    anchor_date: str,
) -> dict[str, float]:
    """Return normalized semantic regime probabilities for the anchor date."""
    if anchor_date not in probability_frame.index:
        raise KeyError(f"Anchor date {anchor_date} not found in features data.")

    row = probability_frame.loc[anchor_date, list(SEMANTIC_REGIME_KEYS)]
    probabilities = {
        key: float(row[key]) if pd.notna(row[key]) else 0.0
        for key in SEMANTIC_REGIME_KEYS
    }
    return normalize_probs(probabilities)


def _semantic_markov_inputs(
    probabilities: dict[str, float],
    calibrations: dict[str, RegimeCalib],
    hmm_pack_view: HMMPackView,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    init_probs_by_state = np.zeros(hmm_pack_view.n_states, dtype=float)
    mu_by_state = np.zeros(hmm_pack_view.n_states, dtype=float)
    sigma_by_state = np.zeros(hmm_pack_view.n_states, dtype=float)

    for key in SEMANTIC_REGIME_KEYS:
        label = key.removeprefix("P_").removesuffix("_HMM")
        if label not in hmm_pack_view.semantic_to_state:
            raise KeyError(f"HMM pack is missing semantic label mapping for {label}.")
        state_id = hmm_pack_view.semantic_to_state[label]
        calibration = calibrations[key]
        init_probs_by_state[state_id] = probabilities[key]
        mu_by_state[state_id] = calibration.mu
        sigma_by_state[state_id] = calibration.sigma

    total = float(init_probs_by_state.sum())
    if total <= 0.0:
        init_probs_by_state[:] = 1.0 / hmm_pack_view.n_states
    else:
        init_probs_by_state /= total
    return init_probs_by_state, mu_by_state, sigma_by_state


def _sample_next_states(
    previous_states: np.ndarray,
    transition_matrix: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    next_states = np.empty_like(previous_states)
    for state_id in range(transition_matrix.shape[0]):
        indices = np.where(previous_states == state_id)[0]
        if indices.size == 0:
            continue
        draws = rng.random(indices.size)
        cdf = np.cumsum(transition_matrix[state_id])
        next_states[indices] = np.searchsorted(cdf, draws, side="right")
    return next_states


def simulate_price_paths_mixture(
    anchor_close: float,
    mu: float,
    sigma: float,
    *,
    days: int,
    sims: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate forward daily-close paths under an iid Gaussian mixture approximation."""
    rng = np.random.default_rng(seed)
    daily_log_returns = mu + sigma * rng.standard_normal(size=(days, sims))
    log_price = np.cumsum(daily_log_returns, axis=0)
    price_paths = anchor_close * np.exp(log_price)
    return price_paths, daily_log_returns


def simulate_price_paths_markov(
    anchor_close: float,
    init_probs_by_state: np.ndarray,
    transition_matrix: np.ndarray,
    mu_by_state: np.ndarray,
    sigma_by_state: np.ndarray,
    *,
    days: int,
    sims: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate forward daily-close paths under a Markov-switching Gaussian model."""
    rng = np.random.default_rng(seed)
    states = np.empty((days, sims), dtype=np.int64)
    initial_cdf = np.cumsum(init_probs_by_state)
    states[0] = np.searchsorted(initial_cdf, rng.random(sims), side="right")

    for step in range(1, days):
        states[step] = _sample_next_states(states[step - 1], transition_matrix, rng)

    eps = rng.standard_normal(size=(days, sims))
    mu = mu_by_state[states]
    sigma = sigma_by_state[states]
    daily_log_returns = mu + sigma * eps
    log_price = np.cumsum(daily_log_returns, axis=0)
    price_paths = anchor_close * np.exp(log_price)
    return price_paths, daily_log_returns, states


def classify_simulated_paths(
    price_paths: np.ndarray,
    barrier_spec: PathBarrierSpec,
) -> np.ndarray:
    """Classify each simulated path into one of the canonical path labels."""
    up_hits = price_paths >= barrier_spec.upper_barrier
    down_hits = price_paths <= barrier_spec.lower_barrier

    any_up = up_hits.any(axis=0)
    any_down = down_hits.any(axis=0)
    first_up = np.where(any_up, up_hits.argmax(axis=0), price_paths.shape[0] + 1)
    first_down = np.where(any_down, down_hits.argmax(axis=0), price_paths.shape[0] + 1)

    labels = np.full(price_paths.shape[1], "RANGE", dtype=object)
    labels[any_up & ~any_down] = "UP_FIRST_ONLY"
    labels[any_down & ~any_up] = "DOWN_FIRST_ONLY"
    labels[any_up & any_down & (first_up < first_down)] = "UP_THEN_DOWN"
    labels[any_up & any_down & (first_down < first_up)] = "DOWN_THEN_UP"
    return labels


def summarize_simulated_paths(
    anchor_close: float,
    price_paths: np.ndarray,
    labels: np.ndarray,
) -> dict[str, Any]:
    ending_returns = price_paths[-1] / anchor_close - 1.0
    path_with_anchor = np.vstack([np.full(price_paths.shape[1], anchor_close), price_paths])

    running_max = np.maximum.accumulate(path_with_anchor, axis=0)
    drawdowns = path_with_anchor / running_max - 1.0
    max_drawdown = drawdowns.min(axis=0)

    running_min = np.minimum.accumulate(path_with_anchor, axis=0)
    runups = path_with_anchor / running_min - 1.0
    max_runup = runups.max(axis=0)

    label_counts = {label: int(np.sum(labels == label)) for label in PATH_LABELS}
    n_paths = int(len(labels))
    label_probabilities = {
        label: label_counts[label] / n_paths if n_paths else 0.0
        for label in PATH_LABELS
    }

    return {
        "path_counts": label_counts,
        "path_probabilities": label_probabilities,
        "average_forward_return": float(np.mean(ending_returns)),
        "median_forward_return": float(np.median(ending_returns)),
        "prob_finishing_positive": float(np.mean(ending_returns > 0.0)),
        "prob_finishing_negative": float(np.mean(ending_returns < 0.0)),
        "average_max_drawdown": float(np.mean(max_drawdown)),
        "average_max_runup": float(np.mean(max_runup)),
    }


def estimate_path_probabilities_for_anchor(
    context: PathProbabilityContext,
    anchor_date: str,
    *,
    days: int = 10,
    up_pct: float = 0.02,
    down_pct: float = 0.02,
    sims: int = 20000,
    seed: int = 42,
    mode: SimulationMode = "markov",
) -> dict[str, Any]:
    """Estimate short-horizon path-type probabilities for a single anchor date."""
    if days <= 0:
        raise ValueError("days must be positive.")
    if sims <= 0:
        raise ValueError("sims must be positive.")
    if up_pct <= 0.0 or down_pct <= 0.0:
        raise ValueError("up_pct and down_pct must be strictly positive.")
    if anchor_date not in context.price_frame.index:
        raise KeyError(f"Anchor date {anchor_date} not found in price data.")

    anchor_close = float(context.price_frame.loc[anchor_date, "close"])
    regime_probabilities = conditioning_probabilities_for_anchor(context.probability_frame, anchor_date)
    barrier_spec = PathBarrierSpec(anchor_close=anchor_close, up_pct=up_pct, down_pct=down_pct)

    if mode == "mixture":
        mu, sigma = mixture_params(regime_probabilities, context.calibrations)
        price_paths, daily_log_returns = simulate_price_paths_mixture(
            anchor_close,
            mu,
            sigma,
            days=days,
            sims=sims,
            seed=seed,
        )
        simulation_details: dict[str, Any] = {
            "mixture_mu": float(mu),
            "mixture_sigma": float(sigma),
        }
    else:
        if context.hmm_pack_view is None:
            raise ValueError("Markov mode requires an HMM pack in the path-probability context.")
        init_probs_by_state, mu_by_state, sigma_by_state = _semantic_markov_inputs(
            regime_probabilities,
            context.calibrations,
            context.hmm_pack_view,
        )
        price_paths, daily_log_returns, states = simulate_price_paths_markov(
            anchor_close,
            init_probs_by_state,
            context.hmm_pack_view.transition_matrix,
            mu_by_state,
            sigma_by_state,
            days=days,
            sims=sims,
            seed=seed,
        )
        state_occupancy = {
            str(state_id): float(np.mean(states == state_id))
            for state_id in range(context.hmm_pack_view.n_states)
        }
        simulation_details = {
            "state_occupancy": state_occupancy,
        }

    labels = classify_simulated_paths(price_paths, barrier_spec)
    summary = summarize_simulated_paths(anchor_close, price_paths, labels)
    summary.update(
        {
            "anchor_date": anchor_date,
            "anchor_close": anchor_close,
            "days": int(days),
            "mode": mode,
            "sims": int(sims),
            "seed": int(seed),
            "barriers": {
                "up_pct": float(up_pct),
                "down_pct": float(down_pct),
                "upper_price": barrier_spec.upper_barrier,
                "lower_price": barrier_spec.lower_barrier,
            },
            "regime_probabilities": regime_probabilities,
            "simulation_details": simulation_details,
            "average_daily_log_return": float(np.mean(daily_log_returns)),
        }
    )
    return summary


def realized_path_outcome_from_ohlc(
    price_frame: pd.DataFrame,
    anchor_date: str,
    *,
    days: int = 10,
    up_pct: float = 0.02,
    down_pct: float = 0.02,
    ambiguity_mode: AmbiguityMode = "skip_ambiguous",
) -> RealizedPathOutcome:
    """Label the realized future path using future daily highs/lows.

    The anchor state is the close on ``anchor_date``. The realized horizon scans
    days ``t+1`` through ``t+H``. If both barriers are touched on the same
    future daily candle before either had been touched previously, the daily OHLC
    data cannot determine intraday ordering. The chosen ambiguity mode controls
    how that case is handled.
    """
    if days <= 0:
        raise ValueError("days must be positive.")
    if ambiguity_mode not in {"pessimistic", "optimistic", "skip_ambiguous", "label_as_both_same_day"}:
        raise ValueError(f"Unsupported ambiguity_mode: {ambiguity_mode}")

    frame = _string_indexed_price_frame(price_frame)
    if anchor_date not in frame.index:
        raise KeyError(f"Anchor date {anchor_date} not found in price data.")

    anchor_position = int(frame.index.get_loc(anchor_date))
    future = frame.iloc[anchor_position + 1: anchor_position + 1 + days]
    if len(future) < days:
        raise ValueError(
            f"Not enough future rows after {anchor_date} for a {days}-day realized path label."
        )

    anchor_close = float(frame.loc[anchor_date, "close"])
    barriers = PathBarrierSpec(anchor_close=anchor_close, up_pct=up_pct, down_pct=down_pct)
    first_upper_day: int | None = None
    first_lower_day: int | None = None
    ambiguity_type: str | None = None
    ambiguous = False

    for day_offset, row in enumerate(future.itertuples(index=False), start=1):
        up_hit = float(row.high) >= barriers.upper_barrier
        down_hit = float(row.low) <= barriers.lower_barrier

        if up_hit and down_hit and first_upper_day is None and first_lower_day is None:
            ambiguous = True
            ambiguity_type = "both_barriers_first_touched_same_day"
            if ambiguity_mode == "skip_ambiguous":
                return RealizedPathOutcome(
                    label=None,
                    ambiguous=True,
                    ambiguity_type=ambiguity_type,
                    first_upper_day=None,
                    first_lower_day=None,
                    upper_barrier=barriers.upper_barrier,
                    lower_barrier=barriers.lower_barrier,
                    forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
                )
            if ambiguity_mode == "label_as_both_same_day":
                return RealizedPathOutcome(
                    label=AMBIGUOUS_REALIZED_LABEL,
                    ambiguous=True,
                    ambiguity_type=ambiguity_type,
                    first_upper_day=day_offset,
                    first_lower_day=day_offset,
                    upper_barrier=barriers.upper_barrier,
                    lower_barrier=barriers.lower_barrier,
                    forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
                )
            if ambiguity_mode == "optimistic":
                return RealizedPathOutcome(
                    label="UP_THEN_DOWN",
                    ambiguous=True,
                    ambiguity_type=ambiguity_type,
                    first_upper_day=day_offset,
                    first_lower_day=day_offset,
                    upper_barrier=barriers.upper_barrier,
                    lower_barrier=barriers.lower_barrier,
                    forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
                )
            return RealizedPathOutcome(
                label="DOWN_THEN_UP",
                ambiguous=True,
                ambiguity_type=ambiguity_type,
                first_upper_day=day_offset,
                first_lower_day=day_offset,
                upper_barrier=barriers.upper_barrier,
                lower_barrier=barriers.lower_barrier,
                forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
            )

        if up_hit and first_upper_day is None:
            first_upper_day = day_offset
        if down_hit and first_lower_day is None:
            first_lower_day = day_offset

    if first_upper_day is None and first_lower_day is None:
        label: str | None = "RANGE"
    elif first_upper_day is not None and first_lower_day is None:
        label = "UP_FIRST_ONLY"
    elif first_upper_day is None and first_lower_day is not None:
        label = "DOWN_FIRST_ONLY"
    elif first_upper_day < first_lower_day:
        label = "UP_THEN_DOWN"
    else:
        label = "DOWN_THEN_UP"

    return RealizedPathOutcome(
        label=label,
        ambiguous=ambiguous,
        ambiguity_type=ambiguity_type,
        first_upper_day=first_upper_day,
        first_lower_day=first_lower_day,
        upper_barrier=barriers.upper_barrier,
        lower_barrier=barriers.lower_barrier,
        forward_return=float(future["close"].iloc[-1] / anchor_close - 1.0),
    )
