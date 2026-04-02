#!/usr/bin/env python3
"""Regime-conditioned touch probability estimation.

This utility calibrates historical daily log-return distributions conditioned on
HMM regime probabilities, then estimates the probability of touching selected
upside or downside price targets within a fixed horizon. Conditioning uses the
latest safely available regime probabilities prior to the anchor date to avoid
lookahead.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_series
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_HMM_PACK_PATH, DEFAULT_PRICE_JSON_PATH


try:
    import joblib
except Exception:  # pragma: no cover - optional dependency guard
    joblib = None


SEMANTIC_REGIME_KEYS: tuple[str, ...] = (
    "P_CORE_HMM",
    "P_DRIFT_HMM",
    "P_SHOCK_HMM",
    "P_SURGE_HMM",
)
SEMANTIC_LABELS: tuple[str, ...] = ("CORE", "DRIFT", "SHOCK", "SURGE")
LEGACY_STATE_KEYS: tuple[str, ...] = tuple(f"HMM_STATE_{state}" for state in range(4))
LEGACY_ALT_KEYS: tuple[str, ...] = tuple(f"P_R{state}_HMM" for state in range(4))
DEFAULT_TARGETS_UP: tuple[float, ...] = (1.02, 1.05, 1.10)
DEFAULT_TARGETS_DOWN: tuple[float, ...] = (0.98, 0.95, 0.90)


@dataclass(frozen=True)
class RegimeCalib:
    mu: float
    sigma: float
    weight_sum: float


@dataclass(frozen=True)
class HMMPackView:
    transition_matrix: np.ndarray
    n_states: int
    semantic_to_state: dict[str, int]
    state_to_semantic: dict[int, str]


def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def _resolve_features_path(features_path: str | None) -> Path:
    return Path(features_path) if features_path else DEFAULT_FEATURES_CSV_PATH


def _resolve_hmm_pack_path(hmm_pack: str | None) -> Path:
    return Path(hmm_pack) if hmm_pack else DEFAULT_HMM_PACK_PATH


def _format_target_label(multiplier: float, side: str) -> str:
    pct = abs((multiplier - 1.0) * 100.0)
    sign = "+" if side == "up" else "-"
    rounded = int(round(pct)) if abs(pct - round(pct)) < 1e-9 else round(pct, 2)
    return f"{sign}{rounded}%"


def _parse_target_arg(raw: str | None, default: tuple[float, ...], side: str) -> list[float]:
    if raw is None:
        values = list(default)
    else:
        try:
            values = [float(part.strip()) for part in raw.split(",") if part.strip()]
        except ValueError as exc:
            raise ValueError(f"Invalid {side} target list: {raw!r}") from exc

    if not values:
        raise ValueError(f"At least one {side} target is required.")

    if side == "up" and any(value <= 1.0 for value in values):
        raise ValueError("Up targets must be multiplicative price levels greater than 1.0.")
    if side == "down" and any(value >= 1.0 for value in values):
        raise ValueError("Down targets must be multiplicative price levels below 1.0.")
    return values


def load_prices(price_json: str) -> pd.Series:
    """Return a date-indexed close-price series."""
    with open(price_json, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    close_by_date = {row["timestamp"]: float(row["close"]) for row in raw}
    return pd.Series(close_by_date, dtype=float).sort_index()


def load_features(features_path: str) -> tuple[pd.Index, dict[str, list[float | None]]]:
    return load_feature_series(features_path)


def build_probability_frame(dates: pd.Index, series: dict[str, list[float | None]], regime_keys: tuple[str, ...]) -> pd.DataFrame:
    missing_columns = [key for key in regime_keys if key not in series]
    if missing_columns:
        raise KeyError(f"Missing regime keys in features series: {missing_columns}")

    frame = pd.DataFrame(
        {
            key: pd.to_numeric(pd.Series(series[key], index=dates), errors="coerce")
            for key in regime_keys
        }
    )
    frame.index = dates
    return frame


def state_id_from_key(key: str) -> int:
    if key.startswith("HMM_STATE_"):
        tail = key.split("_")[-1]
        return int(tail) if tail.isdigit() else -1
    if key.startswith("P_R") and key.endswith("_HMM"):
        tail = key[3:-4]
        return int(tail) if tail.isdigit() else -1
    return -1


def normalize_probs(probabilities: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(value)) for value in probabilities.values())
    if total <= 0.0:
        n = len(probabilities)
        return {key: 1.0 / n for key in probabilities}
    return {key: max(0.0, float(value)) / total for key, value in probabilities.items()}


def weighted_mean_var(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    weights = np.maximum(weights, 0.0)
    weight_sum = float(np.sum(weights))
    if weight_sum <= 0.0:
        return float(np.mean(values)), float(np.var(values))
    mean = float(np.sum(weights * values) / weight_sum)
    var = float(np.sum(weights * (values - mean) ** 2) / weight_sum)
    return mean, var


def calibrate_regimes(
    close_series: pd.Series,
    probability_frame: pd.DataFrame,
    regime_keys: tuple[str, ...],
    winsor_p: float = 0.0025,
) -> dict[str, RegimeCalib]:
    """Calibrate regime-specific daily log-return distributions.

    Daily return ``r_t = log(C_t / C_{t-1})`` is weighted by the regime
    probability from day ``t-1``. This one-day shift avoids lookahead when
    estimating regime-conditioned return moments.
    """
    aligned = pd.concat([close_series.rename("close"), probability_frame], axis=1).dropna(subset=["close"])
    if len(aligned) < 50:
        raise ValueError("Not enough overlapping dates between features and price data.")

    closes = aligned["close"].to_numpy(dtype=float)
    returns = np.log(closes[1:] / closes[:-1])
    if winsor_p > 0.0:
        lo = float(np.quantile(returns, winsor_p))
        hi = float(np.quantile(returns, 1.0 - winsor_p))
        returns = np.clip(returns, lo, hi)

    shifted_probs = aligned.loc[:, list(regime_keys)].shift(1).iloc[1:].fillna(0.0)
    calibrations: dict[str, RegimeCalib] = {}
    for key in regime_keys:
        weights = shifted_probs[key].to_numpy(dtype=float)
        mu, var = weighted_mean_var(returns, weights)
        calibrations[key] = RegimeCalib(
            mu=mu,
            sigma=math.sqrt(max(1e-12, var)),
            weight_sum=float(np.sum(np.maximum(weights, 0.0))),
        )
    return calibrations


def mixture_params(probabilities: dict[str, float], calibrations: dict[str, RegimeCalib]) -> tuple[float, float]:
    probabilities = normalize_probs(probabilities)
    mu = 0.0
    second_moment = 0.0
    for key, prob in probabilities.items():
        calibration = calibrations[key]
        mu += prob * calibration.mu
        second_moment += prob * (calibration.sigma ** 2 + calibration.mu ** 2)
    variance = max(1e-12, second_moment - mu ** 2)
    return float(mu), float(math.sqrt(variance))


def simulate_touch(
    s0: float,
    mu: float,
    sigma: float,
    days: int,
    sims: int,
    targets_up: list[float],
    targets_down: list[float],
    seed: int = 42,
) -> dict[str, dict[str, float]]:
    """Estimate touch probabilities with an iid daily log-return model."""
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(size=(days, sims))
    log_returns = mu + sigma * eps
    log_price = np.cumsum(log_returns, axis=0)
    paths = s0 * np.exp(log_price)

    max_price = np.max(paths, axis=0)
    min_price = np.min(paths, axis=0)

    result_up = {}
    for target in targets_up:
        result_up[_format_target_label(target, "up")] = float(np.mean(max_price >= s0 * target))

    result_down = {}
    for target in targets_down:
        result_down[_format_target_label(target, "down")] = float(np.mean(min_price <= s0 * target))

    return {"up": result_up, "down": result_down}


def _sample_next_states(prev_states: np.ndarray, transition_matrix: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    next_states = np.empty_like(prev_states)
    for state in range(transition_matrix.shape[0]):
        idx = np.where(prev_states == state)[0]
        if idx.size == 0:
            continue
        u = rng.random(idx.size)
        cdf = np.cumsum(transition_matrix[state], axis=0)
        next_states[idx] = np.searchsorted(cdf, u, side="right")
    return next_states


def simulate_touch_markov(
    s0: float,
    init_probs_by_state: np.ndarray,
    transition_matrix: np.ndarray,
    mu_by_state: np.ndarray,
    sigma_by_state: np.ndarray,
    days: int,
    sims: int,
    targets_up: list[float],
    targets_down: list[float],
    seed: int,
) -> dict[str, dict[str, float]]:
    """Estimate touch probabilities with a Markov-switching daily return model."""
    rng = np.random.default_rng(seed)
    init_cdf = np.cumsum(init_probs_by_state)
    u0 = rng.random(sims)
    states = np.empty((days, sims), dtype=np.int64)
    states[0] = np.searchsorted(init_cdf, u0, side="right")

    for t in range(1, days):
        states[t] = _sample_next_states(states[t - 1], transition_matrix, rng)

    eps = rng.standard_normal(size=(days, sims))
    mu = mu_by_state[states]
    sigma = sigma_by_state[states]
    log_returns = mu + sigma * eps

    log_price = np.cumsum(log_returns, axis=0)
    paths = s0 * np.exp(log_price)
    max_price = np.max(paths, axis=0)
    min_price = np.min(paths, axis=0)

    result_up = {}
    for target in targets_up:
        result_up[_format_target_label(target, "up")] = float(np.mean(max_price >= s0 * target))

    result_down = {}
    for target in targets_down:
        result_down[_format_target_label(target, "down")] = float(np.mean(min_price <= s0 * target))

    return {"up": result_up, "down": result_down}


def load_hmm_pack_view(path: Path) -> HMMPackView:
    """Load the HMM pack and validate the transition/semantic mapping contract."""
    if joblib is None:
        raise RuntimeError("joblib is required to read HMM packs for markov mode.")
    if not path.exists():
        raise FileNotFoundError(f"HMM pack not found: {path}")

    pack = joblib.load(path)
    if "params" in pack and "A" in pack["params"]:
        transition_matrix = np.asarray(pack["params"]["A"], dtype=float)
    elif "A" in pack:
        transition_matrix = np.asarray(pack["A"], dtype=float)
    else:
        raise KeyError("HMM pack is missing transition matrix A.")

    if transition_matrix.ndim != 2 or transition_matrix.shape[0] != transition_matrix.shape[1]:
        raise ValueError("HMM transition matrix must be square.")

    row_sums = transition_matrix.sum(axis=1, keepdims=True)
    transition_matrix = np.divide(transition_matrix, np.maximum(row_sums, 1e-12))

    raw_semantic_to_state = pack.get("semantic_to_state", {})
    semantic_to_state = {str(label): int(state) for label, state in raw_semantic_to_state.items()}
    raw_state_to_semantic = pack.get("state_to_semantic", {})
    state_to_semantic = {int(state): str(label) for state, label in raw_state_to_semantic.items()}

    if semantic_to_state:
        missing_labels = [label for label in SEMANTIC_LABELS if label not in semantic_to_state]
        if missing_labels:
            raise ValueError(f"HMM pack semantic mapping is missing labels: {missing_labels}")

    return HMMPackView(
        transition_matrix=transition_matrix,
        n_states=int(transition_matrix.shape[0]),
        semantic_to_state=semantic_to_state,
        state_to_semantic=state_to_semantic,
    )


def _select_regime_keys(series: dict[str, list[float | None]], use_legacy_raw_regimes: bool) -> tuple[str, ...]:
    if not use_legacy_raw_regimes:
        missing = [key for key in SEMANTIC_REGIME_KEYS if key not in series]
        if missing:
            raise KeyError(
                "Missing semantic HMM probabilities in features.csv. "
                f"Expected {list(SEMANTIC_REGIME_KEYS)}, missing {missing}."
            )
        return SEMANTIC_REGIME_KEYS

    if all(key in series for key in LEGACY_STATE_KEYS):
        return LEGACY_STATE_KEYS
    if all(key in series for key in LEGACY_ALT_KEYS):
        return LEGACY_ALT_KEYS
    raise KeyError(
        "Legacy raw regime mode requested, but features.csv does not contain HMM_STATE_* or P_R*_HMM columns."
    )


def _conditioning_probs_for_eval(
    evaluation_date: str,
    dates: pd.Index,
    probability_frame: pd.DataFrame,
    regime_keys: tuple[str, ...],
) -> tuple[str, dict[str, float]]:
    if evaluation_date not in dates:
        raise KeyError(f"Evaluation date {evaluation_date} not found in features dates.")

    position = int(dates.get_loc(evaluation_date))
    if position == 0:
        raise ValueError("Need at least one previous regime-observation day to avoid lookahead.")

    conditioning_date = str(dates[position - 1])
    row = probability_frame.loc[conditioning_date, list(regime_keys)]
    probabilities = {key: float(row[key]) if pd.notna(row[key]) else 0.0 for key in regime_keys}
    return conditioning_date, normalize_probs(probabilities)


def _build_markov_inputs(
    regime_keys: tuple[str, ...],
    probabilities: dict[str, float],
    calibrations: dict[str, RegimeCalib],
    hmm_pack_view: HMMPackView,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    init_probs_by_state = np.zeros(hmm_pack_view.n_states, dtype=float)
    mu_by_state = np.zeros(hmm_pack_view.n_states, dtype=float)
    sigma_by_state = np.zeros(hmm_pack_view.n_states, dtype=float)

    semantic_mode = regime_keys == SEMANTIC_REGIME_KEYS
    for key in regime_keys:
        if semantic_mode:
            label = key.removeprefix("P_").removesuffix("_HMM")
            if label not in hmm_pack_view.semantic_to_state:
                raise KeyError(f"HMM pack is missing semantic label mapping for {label}.")
            state_id = hmm_pack_view.semantic_to_state[label]
        else:
            state_id = state_id_from_key(key)
        if state_id < 0 or state_id >= hmm_pack_view.n_states:
            raise KeyError(f"Invalid state id for regime key {key}: {state_id}")

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate touch probabilities from regime-conditioned daily return calibration.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--features-csv", "--features-json", dest="features_csv", default=None, help="Default: ../out/features.csv")
    parser.add_argument("--hmm-pack", default=None, help="Default: ../out/models/hmm_pack.joblib")
    parser.add_argument("--date", default=None, help="Evaluation anchor date YYYY-MM-DD. Default: last date in features.")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--sims", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--winsor-p", type=float, default=0.0025)
    parser.add_argument("--mode", choices=["mixture", "markov"], default="markov")
    parser.add_argument(
        "--targets-up",
        default=None,
        help="Comma-separated multiplicative upside targets, e.g. 1.02,1.05,1.10",
    )
    parser.add_argument(
        "--targets-down",
        default=None,
        help="Comma-separated multiplicative downside targets, e.g. 0.98,0.95,0.90",
    )
    parser.add_argument(
        "--use-legacy-raw-regimes",
        action="store_true",
        help="Legacy fallback: condition on HMM_STATE_* or P_R*_HMM instead of semantic P_*_HMM columns.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features_path = _resolve_features_path(args.features_csv)
    hmm_pack_path = _resolve_hmm_pack_path(args.hmm_pack)

    close_series = load_prices(args.price_json)
    dates, series = load_features(str(features_path))
    regime_keys = _select_regime_keys(series, args.use_legacy_raw_regimes)
    probability_frame = build_probability_frame(dates, series, regime_keys)
    calibrations = calibrate_regimes(close_series, probability_frame, regime_keys, winsor_p=args.winsor_p)

    evaluation_date = args.date or str(dates[-1])
    if evaluation_date not in close_series.index:
        raise KeyError(f"Evaluation date {evaluation_date} not found in price data.")

    conditioning_date, probabilities = _conditioning_probs_for_eval(
        evaluation_date,
        dates,
        probability_frame,
        regime_keys,
    )
    mu_mix, sigma_mix = mixture_params(probabilities, calibrations)

    s0 = float(close_series.loc[evaluation_date])
    targets_up = _parse_target_arg(args.targets_up, DEFAULT_TARGETS_UP, side="up")
    targets_down = _parse_target_arg(args.targets_down, DEFAULT_TARGETS_DOWN, side="down")

    if args.mode == "mixture":
        result = simulate_touch(
            s0=s0,
            mu=mu_mix,
            sigma=sigma_mix,
            days=args.days,
            sims=args.sims,
            targets_up=targets_up,
            targets_down=targets_down,
            seed=args.seed,
        )
        hmm_pack_view = None
    else:
        hmm_pack_view = load_hmm_pack_view(hmm_pack_path)
        init_probs_by_state, mu_by_state, sigma_by_state = _build_markov_inputs(
            regime_keys=regime_keys,
            probabilities=probabilities,
            calibrations=calibrations,
            hmm_pack_view=hmm_pack_view,
        )
        result = simulate_touch_markov(
            s0=s0,
            init_probs_by_state=init_probs_by_state,
            transition_matrix=hmm_pack_view.transition_matrix,
            mu_by_state=mu_by_state,
            sigma_by_state=sigma_by_state,
            days=args.days,
            sims=args.sims,
            targets_up=targets_up,
            targets_down=targets_down,
            seed=args.seed,
        )

    print("=== Regime-Conditioned Touch Probabilities ===")
    print(f"Mode: {args.mode}")
    print(f"Evaluation date: {evaluation_date} | anchor close={s0:,.2f}")
    print(f"Conditioning date: {conditioning_date}")
    print(f"Features file: {features_path}")
    if args.mode == "markov":
        print(f"HMM pack: {hmm_pack_path}")
    print(f"Targets up: {targets_up}")
    print(f"Targets down: {targets_down}")
    print("")
    print("Conditioning regime probabilities:")
    for key in regime_keys:
        print(f"  {key:20s}: {probabilities[key]:.4f}")
    print("")
    print("Calibrated mixture parameters (daily log returns):")
    print(f"  mu    = {mu_mix:+.6f}  (~{(math.exp(mu_mix) - 1.0) * 100:+.3f}% per day)")
    print(f"  sigma = {sigma_mix:.6f} (~{sigma_mix * 100:.3f}% daily)")
    print("")
    print("--- Touch probabilities within horizon ---")
    print(f"Horizon: {args.days} days | sims: {args.sims}")
    print("")
    print("UP targets:")
    for label, probability in result["up"].items():
        print(f"  {label:>6s}: {probability * 100:5.1f}%")
    print("DOWN targets:")
    for label, probability in result["down"].items():
        print(f"  {label:>6s}: {probability * 100:5.1f}%")
    print("")
    print("--- Calibration per conditioning regime (mu, sigma, weight_sum) ---")
    for key in regime_keys:
        calibration = calibrations[key]
        print(f"{key:20s} mu={calibration.mu:+.6f} sigma={calibration.sigma:.6f} wsum={calibration.weight_sum:.1f}")
    if hmm_pack_view is not None and hmm_pack_view.semantic_to_state:
        print("")
        print("Semantic-to-latent mapping:")
        for label in SEMANTIC_LABELS:
            print(f"  {label:6s} -> state {hmm_pack_view.semantic_to_state[label]}")


if __name__ == "__main__":
    main()
