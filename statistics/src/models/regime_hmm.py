from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, List
import numpy as np
import pandas as pd

import os
import joblib


@dataclass(frozen=True)
class HMMConfig:
    n_states: int = 4
    n_iter: int = 80
    tol: float = 1e-4
    seed: int = 42
    reg_covar: float = 1e-4  # diagonal covariance floor
    # for stability on non-stationary markets you can re-fit rolling later
    # but start with global fit.


# Features used for HMM (small & stable subset)
HMM_FEATURE_COLS = [
    "r1",        # 1d log return
    "TS_20",
    "TS_50",
    "band_w",
    "band_pos",
    "vol_20",
    "range_score",
]


def _nan_guard(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    out = df.copy()
    out = out.replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=cols)
    return out


def _standardize(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0)
    sd = np.where(sd == 0, 1.0, sd)
    Xs = (X - mu) / sd
    return Xs, mu, sd


def _logsumexp(a: np.ndarray, axis: int = -1) -> np.ndarray:
    m = np.max(a, axis=axis, keepdims=True)
    return (m + np.log(np.sum(np.exp(a - m), axis=axis, keepdims=True))).squeeze(axis)


def _log_gaussian_diag(X: np.ndarray, means: np.ndarray, vars_diag: np.ndarray) -> np.ndarray:
    """
    X: (T, D)
    means: (K, D)
    vars_diag: (K, D) diagonal variances
    returns logB: (T, K) where logB[t,k] = log N(X[t] | mean_k, diag(var_k))
    """
    T, D = X.shape
    K = means.shape[0]
    # precompute constants per state
    # log det = sum log(var)
    log_det = np.sum(np.log(vars_diag), axis=1)  # (K,)
    # quadratic term
    # (X - mu)^2 / var
    logB = np.empty((T, K), dtype=float)
    for k in range(K):
        diff = X - means[k]
        quad = np.sum((diff * diff) / vars_diag[k], axis=1)  # (T,)
        logB[:, k] = -0.5 * (D * np.log(2.0 * np.pi) + log_det[k] + quad)
    return logB


def hmm_filter_posterior(X: np.ndarray, params: Dict) -> np.ndarray:
    """
    Forward-only (filtering): gamma_filt[t,k] = p(z_t=k | x_1..x_t)
    This does NOT repaint when you append new observations.
    """
    pi = params["pi"]
    A = params["A"]
    means = params["means"]
    vars_diag = params["vars_diag"]

    log_pi = np.log(pi + 1e-12)
    log_A = np.log(A + 1e-12)
    logB = _log_gaussian_diag(X, means, vars_diag)

    T, K = logB.shape
    log_alpha = np.empty((T, K), dtype=float)

    log_alpha[0] = log_pi + logB[0]
    log_alpha[0] -= _logsumexp(log_alpha[0], axis=0)  # normalize

    for t in range(1, T):
        tmp = log_alpha[t - 1][:, None] + log_A
        log_alpha[t] = logB[t] + _logsumexp(tmp, axis=0)
        log_alpha[t] -= _logsumexp(log_alpha[t], axis=0)  # normalize

    gamma_filt = np.exp(log_alpha)  # already normalized per t
    return gamma_filt


def _forward_backward_log(log_pi: np.ndarray, log_A: np.ndarray, logB: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    log-space forward-backward.
    log_pi: (K,)
    log_A: (K,K)
    logB: (T,K)
    returns:
      log_alpha: (T,K)
      log_beta: (T,K)
      loglik: scalar
    """
    T, K = logB.shape
    log_alpha = np.empty((T, K), dtype=float)
    log_beta = np.empty((T, K), dtype=float)

    log_alpha[0] = log_pi + logB[0]
    for t in range(1, T):
        # log_alpha[t,k] = logB[t,k] + logsum_j (log_alpha[t-1,j] + logA[j,k])
        tmp = log_alpha[t - 1][:, None] + log_A  # (K,K)
        log_alpha[t] = logB[t] + _logsumexp(tmp, axis=0)

    loglik = float(_logsumexp(log_alpha[T - 1], axis=0))

    log_beta[T - 1] = 0.0
    for t in range(T - 2, -1, -1):
        # log_beta[t,j] = logsum_k (logA[j,k] + logB[t+1,k] + log_beta[t+1,k])
        tmp = log_A + (logB[t + 1] + log_beta[t + 1])[None, :]  # (K,K)
        log_beta[t] = _logsumexp(tmp, axis=1)

    return log_alpha, log_beta, loglik


def _init_params(X: np.ndarray, K: int, seed: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Simple init:
      - choose K random points as means
      - set diagonal vars to feature variances
      - init A close to identity (sticky regimes)
    """
    rng = np.random.default_rng(seed)
    T, D = X.shape

    idx = rng.choice(T, size=K, replace=False) if T >= K else np.arange(T)
    means = X[idx].copy()

    global_var = np.var(X, axis=0) + 1e-2
    vars_diag = np.tile(global_var[None, :], (K, 1))

    A = np.full((K, K), 1.0 / K, dtype=float)
    # make it sticky
    for k in range(K):
        A[k, k] += 2.0
    A = A / A.sum(axis=1, keepdims=True)

    pi = np.full((K,), 1.0 / K, dtype=float)
    return pi, A, means, vars_diag


def fit_gaussian_hmm(X: np.ndarray, cfg: HMMConfig) -> Dict:
    """
    Fits a Gaussian HMM with diagonal covariance using EM (Baum-Welch).
    Returns dict with parameters and training info.
    """
    K = cfg.n_states
    T, D = X.shape
    if T < 200:
        raise ValueError(f"Too few rows for HMM: {T}")

    pi, A, means, vars_diag = _init_params(X, K, cfg.seed)

    prev_ll = -np.inf
    for it in range(cfg.n_iter):
        log_pi = np.log(pi + 1e-12)
        log_A = np.log(A + 1e-12)

        logB = _log_gaussian_diag(X, means, vars_diag)
        log_alpha, log_beta, ll = _forward_backward_log(log_pi, log_A, logB)

        # gamma (T,K)
        log_gamma = log_alpha + log_beta
        log_gamma = log_gamma - _logsumexp(log_gamma, axis=1)[:, None]
        gamma = np.exp(log_gamma)

        # xi sums (K,K) over t
        xi_sum = np.zeros((K, K), dtype=float)
        for t in range(T - 1):
            # log_xi[j,k] proportional to alpha[t,j] + logA[j,k] + logB[t+1,k] + beta[t+1,k]
            log_xi = (log_alpha[t][:, None] + log_A + logB[t + 1][None, :] + log_beta[t + 1][None, :])
            log_xi = log_xi - _logsumexp(log_xi.reshape(-1), axis=0)  # normalize globally
            xi = np.exp(log_xi)
            xi_sum += xi

        # M-step: update pi, A, means, vars
        pi = gamma[0] / (gamma[0].sum() + 1e-12)

        A = xi_sum / (xi_sum.sum(axis=1, keepdims=True) + 1e-12)
        # avoid zeros
        A = np.clip(A, 1e-8, 1.0)
        A = A / A.sum(axis=1, keepdims=True)

        # update Gaussian params
        gamma_sum = gamma.sum(axis=0) + 1e-12  # (K,)
        means = (gamma.T @ X) / gamma_sum[:, None]

        # diag variances
        vars_new = np.zeros((K, D), dtype=float)
        for k in range(K):
            diff = X - means[k]
            vars_new[k] = (gamma[:, k][:, None] * (diff * diff)).sum(axis=0) / gamma_sum[k]
        vars_diag = np.maximum(vars_new, cfg.reg_covar)

        # convergence
        if it > 2 and abs(ll - prev_ll) < cfg.tol * (1.0 + abs(prev_ll)):
            prev_ll = ll
            break
        prev_ll = ll

    return {
        "pi": pi,
        "A": A,
        "means": means,
        "vars_diag": vars_diag,
        "loglik": prev_ll,
        "n_iter_ran": it + 1,
    }


def hmm_posterior(X: np.ndarray, params: Dict) -> np.ndarray:
    """
    Compute posterior gamma[t,k] for each time t.
    """
    pi = params["pi"]
    A = params["A"]
    means = params["means"]
    vars_diag = params["vars_diag"]

    log_pi = np.log(pi + 1e-12)
    log_A = np.log(A + 1e-12)
    logB = _log_gaussian_diag(X, means, vars_diag)
    log_alpha, log_beta, _ = _forward_backward_log(log_pi, log_A, logB)

    log_gamma = log_alpha + log_beta
    log_gamma = log_gamma - _logsumexp(log_gamma, axis=1)[:, None]
    gamma = np.exp(log_gamma)
    return gamma


def map_states_to_neutral_regimes(features: pd.DataFrame, gamma: np.ndarray) -> pd.DataFrame:
    """
    Map K=4 unnamed HMM states to 4 NEUTRAL regimes:
      CALM, BASE, STRESS, BURST

    Rules (deterministic):
      - CALM  = state with smallest sigma (vol proxy)
      - BASE  = state with largest occupancy (gamma mass)
      - STRESS = among remaining, state with most negative mean r1 (direction) and relatively high vol
      - BURST = remaining state
    """
    df = features.copy()
    T, K = gamma.shape
    if K != 4:
        raise ValueError(f"Neutral mapping expects K=4, got K={K}")

    # signatures from features (not standardized):
    # r1: direction, vol_20 / abs(r1): vol proxy
    cols = ["r1", "vol_20"]
    Xsig = df[cols].values

    eps = 1e-12
    wsum = gamma.sum(axis=0) + eps
    occ = wsum / (wsum.sum() + eps)

    mean_r1 = (gamma.T @ Xsig[:, 0]) / wsum
    mean_vol = (gamma.T @ Xsig[:, 1]) / wsum

    # CALM = min vol
    calm = int(np.argmin(mean_vol))

    # BASE = max occupancy (but avoid picking CALM if it's already the dominant state – still OK if it is)
    base = int(np.argmax(occ))

    remaining = [k for k in range(K) if k not in {calm, base}]
    if len(remaining) != 2:
        # in rare tie situations, fall back to unique ordering
        remaining = [k for k in range(K) if k != calm]
        base = remaining[int(np.argmax(occ[remaining]))]
        remaining = [k for k in range(K) if k not in {calm, base}]

    # STRESS = the most negative mean_r1 among remaining; if tie, pick higher vol
    rem = remaining
    stress = rem[int(np.lexsort((-mean_vol[rem], mean_r1[rem]))[0])]  # sort by mean_r1 asc, vol desc
    stress = int(stress)

    burst = int([k for k in range(K) if k not in {calm, base, stress}][0])

    mapping = {
        "P_CALM_HMM": calm,
        "P_BASE_HMM": base,
        "P_STRESS_HMM": stress,
        "P_BURST_HMM": burst,
    }

    for name, k in mapping.items():
        df[name] = gamma[:, k]

    df.attrs["hmm_mapping"] = {
        "state_signatures": {
            "mean_r1": mean_r1.tolist(),
            "mean_vol_20": mean_vol.tolist(),
            "occupancy": occ.tolist(),
        },
        "mapping": mapping,
        "labels": {"CALM": calm, "BASE": base, "STRESS": stress, "BURST": burst},
    }
    return df


def labels_by_state_from_gamma(r1: np.ndarray, gamma: np.ndarray) -> List[str]:
    T, K = gamma.shape
    if K != 4:
        raise ValueError(f"labels_by_state expects K=4, got K={K}")

    eps = 1e-12
    wsum = gamma.sum(axis=0) + eps
    occ = wsum / (wsum.sum() + eps)

    mu = (gamma.T @ r1) / wsum
    diff = r1[:, None] - mu[None, :]
    var = (gamma * (diff * diff)).sum(axis=0) / wsum
    sigma = np.sqrt(var)

    stress = np.argsort(sigma)[-2:].tolist()
    calm = [k for k in range(K) if k not in stress]

    core = int(calm[int(np.argmax(occ[calm]))])
    drift = int([k for k in calm if k != core][0])

    shock = int(stress[int(np.argmin(mu[stress]))])
    surge = int([k for k in stress if k != shock][0])

    labels = [""] * K
    labels[core] = "CORE"
    labels[drift] = "DRIFT"
    labels[shock] = "SHOCK"
    labels[surge] = "SURGE"
    return labels


def fit_hmm_pack(features: pd.DataFrame, cfg: HMMConfig = HMMConfig()) -> Dict:
    feats = _nan_guard(features, HMM_FEATURE_COLS)
    X = feats[HMM_FEATURE_COLS].values.astype(float)
    Xs, mu, sd = _standardize(X)

    params = fit_gaussian_hmm(Xs, cfg)

    # For mapping we use posterior (you can use smoothing here, it's training)
    gamma_train = hmm_posterior(Xs, params)

    # We build the mapping once and save it
    tmp = features.copy()
    mapped = map_states_to_neutral_regimes(tmp.loc[feats.index], gamma_train)
    mapping = mapped.attrs["hmm_mapping"]["mapping"]
    labels_by_state = labels_by_state_from_gamma(feats["r1"].values.astype(float), gamma_train)

    pack = {
        "cfg": cfg.__dict__,
        "feature_cols": HMM_FEATURE_COLS,
        "standardize": {"mu": mu.tolist(), "sd": sd.tolist()},
        "params": {
            "pi": params["pi"],
            "A": params["A"],
            "means": params["means"],
            "vars_diag": params["vars_diag"],
        },
        "mapping": mapping,  # P_*_HMM -> state_id
        "labels_by_state": labels_by_state,
        "train_info": {"loglik": float(params["loglik"]), "n_iter_ran": int(params["n_iter_ran"])},
    }
    return pack


def apply_hmm_pack(features: pd.DataFrame, pack: Dict, mode: str = "filter") -> Tuple[pd.DataFrame, Dict]:
    """
    Apply frozen HMM pack to features.
    mode:
      - "filter"  : forward-only (NO repaint) recommended for production
      - "smooth"  : forward-backward (may repaint) useful for research
    """
    feats = _nan_guard(features, pack["feature_cols"])
    X = feats[pack["feature_cols"]].values.astype(float)

    mu = np.array(pack["standardize"]["mu"], dtype=float)
    sd = np.array(pack["standardize"]["sd"], dtype=float)
    sd = np.where(sd == 0, 1.0, sd)
    Xs = (X - mu) / sd

    params = pack["params"]
    if mode == "smooth":
        gamma = hmm_posterior(Xs, params)
    else:
        gamma = hmm_filter_posterior(Xs, params)

    out = features.copy()

    # optional: store raw state probabilities
    for k in range(int(pack["cfg"]["n_states"])):
        out.loc[feats.index, f"HMM_STATE_{k}"] = gamma[:, k]
    out.loc[feats.index, "HMM_CONF"] = gamma.max(axis=1)
    out.loc[feats.index, "HMM_DOM"] = gamma.argmax(axis=1).astype(int)

    # Use frozen mapping from pack (cast to builtin int for JSON safety)
    allowed_mapping = {"P_CALM_HMM", "P_BASE_HMM", "P_STRESS_HMM", "P_BURST_HMM"}
    raw_mapping = pack.get("mapping", {})
    mapping = {name: int(k) for name, k in raw_mapping.items() if name in allowed_mapping}
    for name, k in mapping.items():
        out.loc[feats.index, name] = gamma[:, k]

    meta = {
        "cfg": pack["cfg"],
        "feature_cols": pack["feature_cols"],
        "standardize": pack["standardize"],
        "mapping": mapping,
        "labels_by_state": pack.get("labels_by_state", []),
        "mode": mode,
        "train_info": pack.get("train_info", {}),
        "params": {
            "pi": np.asarray(pack["params"]["pi"], dtype=float).tolist(),
            "A":  np.asarray(pack["params"]["A"], dtype=float).tolist(),
        },
    }

    return out, meta


def save_hmm_pack(pack: Dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(pack, path)


def load_hmm_pack(path: str) -> Dict:
    return joblib.load(path)
