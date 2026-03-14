#!/usr/bin/env python3
"""
SAFE-grade touch probability estimator
-------------------------------------

Goal:
  Estimate the probability that price touches certain up/down targets within N days,
  using a Monte Carlo model whose drift/volatility are *calibrated from your own history*
  and conditioned on SAFE/HMM regime probabilities.

Key properties:
  - Uses log-returns (no negative prices)
  - Calibrates per-regime (mu_k, sigma_k) from historical returns with *soft weights*
    from HMM probabilities (shifted by 1 day to avoid lookahead)
  - For a given day, builds a mixture distribution from the day's regime probabilities
    (mu_mix, sigma_mix) and simulates paths
  - Outputs touch probabilities (max/min hit) for common targets

Inputs expected (your current stable structures):
  - daily_price.json: list of {"timestamp","open","high","low","close","volume"}
  - features.json: {"dates":[...], "series":{ ... HMM_STATE_* ... }}

No capital management. No trades. Pure "realism / expectation" tool.

Example:
python src/util/safe_touch_probabilities.py \
--price-json data/daily_price.json \
--features-json out/btc/features.json \
--date 2026-01-07 \
--days 10 --sims 20000

# Pentru probabilitati P_R*_HMM (optional)
    python src/safe_touch_probabilities.py \
    --price-json data/daily_price.json \
    --features-json out/btc/features.json \
    --date 2026-01-04 \
    --days 10 --sims 20000 \
    --use-raw-probs
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import joblib
except Exception:
    joblib = None


HMM_STATE_KEYS = [f"HMM_STATE_{k}" for k in range(4)]
REGIME_KEYS_DEFAULT = HMM_STATE_KEYS
REGIME_KEYS_ALT = [f"P_R{k}_HMM" for k in range(4)]


def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def load_prices(price_json: str) -> Dict[str, float]:
    """Return date->close map."""
    with open(price_json, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {r["timestamp"]: float(r["close"]) for r in raw}


def load_features(features_json: str) -> Tuple[List[str], Dict[str, List[float]]]:
    with open(features_json, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw["dates"], raw["series"]


def state_id_from_key(key: str) -> int:
    if key.startswith("HMM_STATE_"):
        tail = key.split("_")[-1]
        return int(tail) if tail.isdigit() else -1
    if key.startswith("P_R") and key.endswith("_HMM"):
        tail = key[3:-4]
        return int(tail) if tail.isdigit() else -1
    return -1


def normalize_probs(p: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, float(v)) for v in p.values())
    if s <= 0:
        # fallback uniform
        n = len(p)
        return {k: 1.0 / n for k in p.keys()}
    return {k: max(0.0, float(v)) / s for k, v in p.items()}


def weighted_mean_var(x: np.ndarray, w: np.ndarray) -> Tuple[float, float]:
    """Return (mean, var) with non-negative weights."""
    w = np.maximum(w, 0.0)
    s = float(np.sum(w))
    if s <= 0:
        m = float(np.mean(x))
        v = float(np.var(x))
        return m, v
    m = float(np.sum(w * x) / s)
    v = float(np.sum(w * (x - m) ** 2) / s)
    return m, v


@dataclass
class RegimeCalib:
    mu: float
    sigma: float
    weight_sum: float


def calibrate_regimes(
    dates: List[str],
    series: Dict[str, List[float]],
    close_by_date: Dict[str, float],
    regime_keys: List[str],
    winsor_p: float = 0.0025,
) -> Dict[str, RegimeCalib]:
    """
    Calibrate per-regime (mu_k, sigma_k) from historical log-returns using soft weights:
      r_t = log(C_t / C_{t-1})
      weight for r_t uses probs from day t-1 (shift) to avoid lookahead.
    """
    # Build aligned arrays for dates in features that exist in price map.
    aligned_dates = [d for d in dates if d in close_by_date]
    if len(aligned_dates) < 50:
        raise ValueError("Not enough overlapping dates between features and price data.")

    closes = np.array([close_by_date[d] for d in aligned_dates], dtype=float)
    # log returns r_t for t>=1
    r = np.log(closes[1:] / closes[:-1])

    # Winsorize returns to reduce rare extreme artifacts dominating sigma
    if winsor_p > 0:
        lo = float(np.quantile(r, winsor_p))
        hi = float(np.quantile(r, 1.0 - winsor_p))
        r = np.clip(r, lo, hi)

    out: Dict[str, RegimeCalib] = {}

    # For each regime, weights are probs at t-1 aligned with r_t (length = len(closes)-1)
    for k in regime_keys:
        if k not in series:
            raise KeyError(f"Missing regime key in features.json series: {k}")

        probs = np.array([float(series[k][dates.index(d)]) for d in aligned_dates], dtype=float)
        probs = np.maximum(probs, 0.0)

        # shift: weight for r_t uses probs at day t-1
        w = probs[:-1]

        mu_k, var_k = weighted_mean_var(r, w)
        sigma_k = math.sqrt(max(1e-12, var_k))
        out[k] = RegimeCalib(mu=mu_k, sigma=sigma_k, weight_sum=float(np.sum(w)))

    return out


def mixture_params(probs: Dict[str, float], calib: Dict[str, RegimeCalib]) -> Tuple[float, float]:
    """
    Given probs p_k and per-regime (mu_k, sigma_k), compute mixture mu and sigma.
    Variance of mixture = sum p_k*(sigma_k^2 + mu_k^2) - mu^2
    """
    probs = normalize_probs(probs)
    mu = 0.0
    second = 0.0
    for k, p in probs.items():
        c = calib[k]
        mu += p * c.mu
        second += p * (c.sigma ** 2 + c.mu ** 2)
    var = max(1e-12, second - mu ** 2)
    return float(mu), float(math.sqrt(var))


def simulate_touch(
    s0: float,
    mu: float,
    sigma: float,
    days: int,
    sims: int,
    targets_up: List[float],
    targets_down: List[float],
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """
    Monte Carlo on log-returns:
      log S_{t} = log S0 + sum_{i=1..t} (mu + sigma*eps)
    Touch probability uses max/min over horizon.
    targets_up/down are multipliers (e.g., 1.02, 0.95).
    """
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(size=(days, sims))
    log_rets = mu + sigma * eps
    log_price = np.cumsum(log_rets, axis=0)
    paths = s0 * np.exp(log_price)

    maxp = np.max(paths, axis=0)
    minp = np.min(paths, axis=0)

    res_up = {}
    for t in targets_up:
        level = s0 * t
        res_up[f"+{int(round((t - 1.0) * 100))}%"] = float(np.mean(maxp >= level))

    res_down = {}
    for t in targets_down:
        level = s0 * t
        res_down[f"{int(round((t - 1.0) * 100))}%"] = float(np.mean(minp <= level))

    return {"up": res_up, "down": res_down}


def get_probs_for_date(d: str, dates: List[str], series: Dict[str, List[float]], regime_keys: List[str]) -> Dict[str, float]:
    if d not in dates:
        raise KeyError(f"Date {d} not found in features dates.")
    i = dates.index(d)
    return {k: float(series[k][i]) for k in regime_keys}


def _sample_next_states(prev: np.ndarray, A: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    prev: (sims,)
    A: (K,K) row-stochastic transition matrix
    """
    next_states = np.empty_like(prev)
    for k in range(A.shape[0]):
        idx = np.where(prev == k)[0]
        if idx.size == 0:
            continue
        u = rng.random(idx.size)
        cdf = np.cumsum(A[k], axis=0)
        next_states[idx] = np.searchsorted(cdf, u, side="right")
    return next_states


def simulate_touch_markov(
    s0: float,
    init_probs_by_state: np.ndarray,  # (K,)
    A: np.ndarray,                    # (K,K)
    mu_by_state: np.ndarray,          # (K,)
    sigma_by_state: np.ndarray,       # (K,)
    days: int,
    sims: int,
    targets_up: List[float],
    targets_down: List[float],
    seed: int,
) -> Dict[str, Dict[str, float]]:
    rng = np.random.default_rng(seed)

    init_cdf = np.cumsum(init_probs_by_state)
    u0 = rng.random(sims)
    states = np.empty((days, sims), dtype=np.int64)
    states[0] = np.searchsorted(init_cdf, u0, side="right")

    for t in range(1, days):
        states[t] = _sample_next_states(states[t - 1], A, rng)

    eps = rng.standard_normal(size=(days, sims))
    mu = mu_by_state[states]
    sig = sigma_by_state[states]
    log_rets = mu + sig * eps

    log_price = np.cumsum(log_rets, axis=0)
    paths = s0 * np.exp(log_price)

    maxp = np.max(paths, axis=0)
    minp = np.min(paths, axis=0)

    out_up = {}
    out_dn = {}
    for t in targets_up:
        out_up[f"+{int(round((t - 1.0) * 100))}%"] = float(np.mean(maxp >= s0 * t))
    for t in targets_down:
        out_dn[f"-{int(round((1.0 - t) * 100))}%"] = float(np.mean(minp <= s0 * t))
    return {"up": out_up, "down": out_dn}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--price-json", required=True)
    ap.add_argument("--features-json", required=True)
    ap.add_argument("--date", default=None, help="Date to evaluate (YYYY-MM-DD). Default: last date in features.")
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--sims", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for Monte Carlo simulations (default: 42)")
    ap.add_argument("--winsor-p", type=float, default=0.0025, help="Winsorization percentile for returns.")
    ap.add_argument("--use-raw-probs", action="store_true",
                    help="Use P_R*_HMM keys instead of HMM_STATE_* if present.")
    ap.add_argument("--mode", choices=["mixture", "markov"], default="markov",
                    help="Simulation engine: iid mixture (default) or Markov-switching regimes.")
    ap.add_argument("--hmm-pack", default="models/btc/hmm_pack.joblib",
                    help="Path to hmm_pack.joblib (required for --mode markov).")
    args = ap.parse_args()

    close_by_date = load_prices(args.price_json)
    dates, series = load_features(args.features_json)

    # pick regime keys
    if args.use_raw_probs:
        regime_keys = REGIME_KEYS_ALT
    else:
        regime_keys = REGIME_KEYS_DEFAULT

    missing = [k for k in regime_keys if k not in series]
    assert not missing, f"Missing regime keys in features.json series: {missing}"

    # calibrate
    calib = calibrate_regimes(dates, series, close_by_date, regime_keys, winsor_p=args.winsor_p)

    # choose eval date
    d_eval = args.date or dates[-1]
    if d_eval not in close_by_date:
        raise KeyError(f"Eval date {d_eval} not found in price data.")

    # IMPORTANT: to avoid lookahead, we use probs from yesterday to forecast next days.
    # So if evaluating "today", we take probs of previous available SAFE date.
    idx = dates.index(d_eval)
    if idx == 0:
        raise ValueError("Need at least one previous day to use as conditioning (no lookahead).")
    d_cond = dates[idx - 1]

    probs = get_probs_for_date(d_cond, dates, series, regime_keys)
    probs = normalize_probs(probs)

    mu_mix, sigma_mix = mixture_params(probs, calib)

    s0 = float(close_by_date[d_eval])

    targets_up = [1.02, 1.05, 1.10]
    targets_down = [0.98, 0.95, 0.90]

    if args.mode == "markov":
        if joblib is None:
            raise RuntimeError("joblib not available. Install it or run with --mode mixture.")
        if not args.hmm_pack:
            raise RuntimeError("--hmm-pack is required when --mode markov.")

    if args.mode == "mixture":
        res = simulate_touch(
            s0=s0,
            mu=mu_mix,
            sigma=sigma_mix,
            days=args.days,
            sims=args.sims,
            targets_up=targets_up,
            targets_down=targets_down,
            seed=args.seed,
        )
    else:
        pack = joblib.load(args.hmm_pack)

        if "params" in pack and "A" in pack["params"]:
            A = np.asarray(pack["params"]["A"], dtype=float)
        elif "A" in pack:
            A = np.asarray(pack["A"], dtype=float)
        else:
            raise KeyError("hmm_pack missing transition matrix A (expected pack['params']['A'] or pack['A']).")

        row_sums = A.sum(axis=1, keepdims=True)
        A = np.divide(A, np.maximum(row_sums, 1e-12))

        mapping = pack.get("mapping", None)

        K = A.shape[0]
        mu_by_state = np.zeros(K, dtype=float)
        sigma_by_state = np.zeros(K, dtype=float)
        init_by_state = np.zeros(K, dtype=float)

        for rk in regime_keys:
            sid = state_id_from_key(rk)
            if sid < 0 and mapping is not None:
                sid = int(mapping.get(rk, -1))
            if sid < 0 or sid >= K:
                raise KeyError(f"Invalid state id for regime key: {rk}")
            c = calib[rk]
            mu_by_state[sid] = c.mu
            sigma_by_state[sid] = c.sigma
            init_by_state[sid] = probs[rk]

        s = init_by_state.sum()
        if s <= 0:
            init_by_state[:] = 1.0 / K
        else:
            init_by_state /= s

        res = simulate_touch_markov(
            s0=s0,
            init_probs_by_state=init_by_state,
            A=A,
            mu_by_state=mu_by_state,
            sigma_by_state=sigma_by_state,
            days=args.days,
            sims=args.sims,
            targets_up=targets_up,
            targets_down=targets_down,
            seed=args.seed,
        )

    # Print report
    print("=== SAFE Touch Probabilities (calibrated) ===")
    if args.mode == "markov":
        print("Engine: markov (HMM regime transitions)")
    else:
        print("Engine: mixture (iid)")
    print(f"Eval date (price anchor): {d_eval} | close={s0:,.2f}")
    print(f"Conditioning SAFE date:   {d_cond}")
    print("")
    print("Regime probs (conditioning):")
    for k in regime_keys:
        print(f"  {k:20s}: {probs[k]:.4f}")
    print("")
    print("Calibrated mixture params (daily log-return):")
    print(f"  mu    = {mu_mix:+.6f}  (~{(math.exp(mu_mix)-1)*100:+.3f}% per day)")
    print(f"  sigma = {sigma_mix:.6f} (~{sigma_mix*100:.3f}% daily)")
    print("")
    print("--- Touch probabilities within horizon ---")
    print(f"Horizon: {args.days} days | sims: {args.sims}")
    print("")
    print("UP targets:")
    for k, v in res["up"].items():
        print(f"  {k:>5s}: {v*100:5.1f}%")
    print("DOWN targets:")
    for k, v in res["down"].items():
        print(f"  {k:>5s}: {v*100:5.1f}%")

    # Extra: quick sanity about calibration coverage
    # (not essential, but helps trust)
    print("")
    print("--- Calibration per regime (mu, sigma, weight_sum) ---")
    for k in regime_keys:
        c = calib[k]
        print(f"{k:20s} mu={c.mu:+.6f} sigma={c.sigma:.6f} wsum={c.weight_sum:.1f}")


if __name__ == "__main__":
    main()
