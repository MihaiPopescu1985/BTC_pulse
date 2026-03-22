from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from typing import Any, Literal
import os

import joblib
import numpy as np
import pandas as pd


HMMMode = Literal["filter", "smooth"]
SEMANTIC_REGIME_LABELS: tuple[str, ...] = ("CORE", "DRIFT", "SHOCK", "SURGE")
# Canonical descriptive input set for the diagonal-covariance HMM.
# Keep this compact and stable to limit redundancy and seed sensitivity.
HMM_FEATURE_COLS: tuple[str, ...] = (
    "r1",
    "TS_50",
    "ER_20",
    "atr_pct",
    "band_pos",
    "relative_volume_20",
)
STATE_SIGNATURE_COLUMNS: tuple[str, ...] = (
    "r1",
    "TS_20",
    "TS_50",
    "ER_20",
    "vol_20",
    "atr_pct",
    "ewma_vol",
    "band_w",
    "band_pos",
    "dist_from_mean_vol_units",
    "relative_volume_20",
)


@dataclass(frozen=True)
class HMMConfig:
    """Configuration for the descriptive-feature HMM regime model.

    The fitted HMM operates on a fixed descriptive feature contract defined by
    ``HMM_FEATURE_COLS``. Semantic labeling is intentionally defined only for a
    4-state model. Latent states are inferred statistically first, then mapped
    afterward to the directional semantic labels ``CORE``, ``DRIFT``,
    ``SHOCK``, and ``SURGE``.
    """

    n_states: int = 4
    n_iter: int = 80
    tol: float = 1e-4
    seed: int = 42
    reg_covar: float = 1e-4
    min_rows: int = 250
    init_kmeans_iter: int = 12
    sticky_self_transition: float = 0.85


# -----------------------------
# Validation and preparation
# -----------------------------


def _validate_hmm_config(cfg: HMMConfig) -> None:
    if cfg.n_states != 4:
        raise ValueError(
            "Semantic HMM labeling is defined only for n_states == 4. "
            f"Received n_states={cfg.n_states}."
        )
    if not 0.0 < cfg.sticky_self_transition < 1.0:
        raise ValueError("sticky_self_transition must be strictly between 0 and 1.")


def _prepare_hmm_features(
    features: pd.DataFrame,
    feature_cols: tuple[str, ...],
) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    """Validate the explicit HMM feature contract and drop incomplete rows.

    The active HMM feature set is fixed by the caller. This stage does not
    silently degrade to a smaller subset when columns are missing.
    """
    cleaned = features.replace([np.inf, -np.inf], np.nan).copy()

    missing_columns = [column for column in feature_cols if column not in cleaned.columns]
    if missing_columns:
        raise ValueError(
            "Descriptive feature table is missing required HMM inputs: "
            f"{missing_columns}. Expected fixed input set: {list(feature_cols)}."
        )

    empty_columns = [column for column in feature_cols if cleaned[column].isna().all()]
    if empty_columns:
        raise ValueError(
            "HMM input columns contain no usable values after cleaning: "
            f"{empty_columns}."
        )

    usable = cleaned.dropna(subset=list(feature_cols))
    dropped_rows = len(cleaned) - len(usable)
    usable_info = {
        "feature_cols": list(feature_cols),
        "total_rows": int(len(cleaned)),
        "usable_rows": int(len(usable)),
        "dropped_rows": int(dropped_rows),
        "usable_start": usable.index.min().strftime("%Y-%m-%d") if not usable.empty else None,
        "usable_end": usable.index.max().strftime("%Y-%m-%d") if not usable.empty else None,
    }
    return usable, list(feature_cols), usable_info


# -----------------------------
# Numeric helpers
# -----------------------------


def _standardize(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.nanmean(X, axis=0)
    std = np.nanstd(X, axis=0)
    std = np.where(std == 0.0, 1.0, std)
    standardized = (X - mean) / std
    return standardized, mean, std


def _logsumexp(a: np.ndarray, axis: int = -1) -> np.ndarray:
    maximum = np.max(a, axis=axis, keepdims=True)
    return (maximum + np.log(np.sum(np.exp(a - maximum), axis=axis, keepdims=True))).squeeze(axis)


def _log_gaussian_diag(X: np.ndarray, means: np.ndarray, vars_diag: np.ndarray) -> np.ndarray:
    """Evaluate diagonal-Gaussian log likelihoods for every state."""
    num_rows, num_features = X.shape
    num_states = means.shape[0]
    log_det = np.sum(np.log(vars_diag), axis=1)
    log_density = np.empty((num_rows, num_states), dtype=float)
    for state in range(num_states):
        diff = X - means[state]
        quad = np.sum((diff * diff) / vars_diag[state], axis=1)
        log_density[:, state] = -0.5 * (num_features * np.log(2.0 * np.pi) + log_det[state] + quad)
    return log_density


# -----------------------------
# Posterior computation
# -----------------------------


def hmm_filter_posterior(X: np.ndarray, params: dict[str, np.ndarray]) -> np.ndarray:
    """Compute forward-only state posteriors.

    Filtering uses information up to time ``t`` only and is suitable for
    non-repainting online inference.
    """
    pi = params["pi"]
    transitions = params["A"]
    means = params["means"]
    vars_diag = params["vars_diag"]

    log_pi = np.log(pi + 1e-12)
    log_A = np.log(transitions + 1e-12)
    logB = _log_gaussian_diag(X, means, vars_diag)

    num_rows, num_states = logB.shape
    log_alpha = np.empty((num_rows, num_states), dtype=float)

    log_alpha[0] = log_pi + logB[0]
    log_alpha[0] -= _logsumexp(log_alpha[0], axis=0)

    for row in range(1, num_rows):
        transition_term = log_alpha[row - 1][:, None] + log_A
        log_alpha[row] = logB[row] + _logsumexp(transition_term, axis=0)
        log_alpha[row] -= _logsumexp(log_alpha[row], axis=0)

    return np.exp(log_alpha)


def _forward_backward_log(log_pi: np.ndarray, log_A: np.ndarray, logB: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    num_rows, num_states = logB.shape
    log_alpha = np.empty((num_rows, num_states), dtype=float)
    log_beta = np.empty((num_rows, num_states), dtype=float)

    log_alpha[0] = log_pi + logB[0]
    for row in range(1, num_rows):
        transition_term = log_alpha[row - 1][:, None] + log_A
        log_alpha[row] = logB[row] + _logsumexp(transition_term, axis=0)

    loglik = float(_logsumexp(log_alpha[num_rows - 1], axis=0))

    log_beta[num_rows - 1] = 0.0
    for row in range(num_rows - 2, -1, -1):
        transition_term = log_A + (logB[row + 1] + log_beta[row + 1])[None, :]
        log_beta[row] = _logsumexp(transition_term, axis=1)

    return log_alpha, log_beta, loglik


def hmm_posterior(X: np.ndarray, params: dict[str, np.ndarray]) -> np.ndarray:
    """Compute smoothed posteriors using the full sample.

    Smoothing uses past and future observations and can repaint when new data is
    appended. It is useful for research and retrospective diagnostics.
    """
    log_pi = np.log(params["pi"] + 1e-12)
    log_A = np.log(params["A"] + 1e-12)
    logB = _log_gaussian_diag(X, params["means"], params["vars_diag"])

    log_alpha, log_beta, _ = _forward_backward_log(log_pi, log_A, logB)
    log_gamma = log_alpha + log_beta
    log_gamma = log_gamma - _logsumexp(log_gamma, axis=1)[:, None]
    return np.exp(log_gamma)


# -----------------------------
# Initialization
# -----------------------------


def _pairwise_squared_distance(X: np.ndarray, centers: np.ndarray) -> np.ndarray:
    diff = X[:, None, :] - centers[None, :, :]
    return np.sum(diff * diff, axis=2)


def _kmeans_plus_plus(X: np.ndarray, n_clusters: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    num_rows = X.shape[0]
    centers = np.empty((n_clusters, X.shape[1]), dtype=float)

    first_idx = int(rng.integers(num_rows))
    centers[0] = X[first_idx]
    min_dist_sq = np.sum((X - centers[0]) ** 2, axis=1)

    for cluster in range(1, n_clusters):
        total_dist = float(min_dist_sq.sum())
        if total_dist <= 0.0:
            centers[cluster] = X[int(rng.integers(num_rows))]
        else:
            probs = min_dist_sq / total_dist
            next_idx = int(rng.choice(num_rows, p=probs))
            centers[cluster] = X[next_idx]
        min_dist_sq = np.minimum(min_dist_sq, np.sum((X - centers[cluster]) ** 2, axis=1))

    return centers


def _run_simple_kmeans(X: np.ndarray, n_clusters: int, seed: int, n_iter: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    centers = _kmeans_plus_plus(X, n_clusters, seed)

    for _ in range(n_iter):
        dist_sq = _pairwise_squared_distance(X, centers)
        labels = dist_sq.argmin(axis=1)
        updated = centers.copy()
        for cluster in range(n_clusters):
            members = X[labels == cluster]
            if len(members) == 0:
                updated[cluster] = X[int(rng.integers(len(X)))]
            else:
                updated[cluster] = members.mean(axis=0)
        if np.allclose(updated, centers):
            centers = updated
            break
        centers = updated

    final_labels = _pairwise_squared_distance(X, centers).argmin(axis=1)
    return centers, final_labels


def _init_params(X: np.ndarray, cfg: HMMConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Initialize HMM parameters with light k-means clustering in standardized space."""
    num_rows, num_features = X.shape
    centers, labels = _run_simple_kmeans(X, cfg.n_states, cfg.seed, cfg.init_kmeans_iter)

    global_var = np.var(X, axis=0) + cfg.reg_covar
    vars_diag = np.tile(global_var[None, :], (cfg.n_states, 1))
    occupancy = np.zeros(cfg.n_states, dtype=float)

    for state in range(cfg.n_states):
        members = X[labels == state]
        occupancy[state] = float(len(members))
        if len(members) >= 2:
            vars_diag[state] = np.maximum(members.var(axis=0), cfg.reg_covar)

    occupancy = occupancy + 1.0
    pi = occupancy / occupancy.sum()

    off_diag_value = (1.0 - cfg.sticky_self_transition) / (cfg.n_states - 1)
    transitions = np.full((cfg.n_states, cfg.n_states), off_diag_value, dtype=float)
    np.fill_diagonal(transitions, cfg.sticky_self_transition)

    if num_rows < cfg.n_states:
        raise ValueError(f"Too few rows for HMM initialization: {num_rows} < {cfg.n_states}")

    return pi, transitions, centers, vars_diag


# -----------------------------
# Training
# -----------------------------


def _count_hmm_parameters(n_states: int, n_features: int) -> int:
    return (n_states - 1) + n_states * (n_states - 1) + 2 * n_states * n_features


def fit_gaussian_hmm(X: np.ndarray, cfg: HMMConfig | None = None) -> dict[str, Any]:
    """Fit a diagonal-covariance Gaussian HMM using EM."""
    if cfg is None:
        cfg = HMMConfig()
    _validate_hmm_config(cfg)

    num_rows, num_features = X.shape
    if num_rows < cfg.min_rows:
        raise ValueError(f"Too few rows for HMM fitting: {num_rows} < {cfg.min_rows}")

    pi, transitions, means, vars_diag = _init_params(X, cfg)

    prev_loglik = -np.inf
    converged = False
    n_iter_ran = 0
    for iteration in range(cfg.n_iter):
        log_pi = np.log(pi + 1e-12)
        log_A = np.log(transitions + 1e-12)
        logB = _log_gaussian_diag(X, means, vars_diag)
        log_alpha, log_beta, loglik = _forward_backward_log(log_pi, log_A, logB)

        log_gamma = log_alpha + log_beta
        log_gamma = log_gamma - _logsumexp(log_gamma, axis=1)[:, None]
        gamma = np.exp(log_gamma)

        xi_sum = np.zeros((cfg.n_states, cfg.n_states), dtype=float)
        for row in range(num_rows - 1):
            log_xi = (
                log_alpha[row][:, None]
                + log_A
                + logB[row + 1][None, :]
                + log_beta[row + 1][None, :]
            )
            log_xi = log_xi - _logsumexp(log_xi.reshape(-1), axis=0)
            xi_sum += np.exp(log_xi)

        gamma_sum = gamma.sum(axis=0) + 1e-12
        pi = gamma[0] / gamma[0].sum()

        transitions = xi_sum / (xi_sum.sum(axis=1, keepdims=True) + 1e-12)
        transitions = np.clip(transitions, 1e-8, 1.0)
        transitions = transitions / transitions.sum(axis=1, keepdims=True)

        means = (gamma.T @ X) / gamma_sum[:, None]

        vars_new = np.zeros((cfg.n_states, num_features), dtype=float)
        for state in range(cfg.n_states):
            diff = X - means[state]
            vars_new[state] = (gamma[:, state][:, None] * (diff * diff)).sum(axis=0) / gamma_sum[state]
        vars_diag = np.maximum(vars_new, cfg.reg_covar)

        n_iter_ran = iteration + 1
        if iteration > 2 and abs(loglik - prev_loglik) < cfg.tol * (1.0 + abs(prev_loglik)):
            prev_loglik = loglik
            converged = True
            break
        prev_loglik = loglik

    num_params = _count_hmm_parameters(cfg.n_states, num_features)
    aic = 2.0 * num_params - 2.0 * prev_loglik
    bic = np.log(num_rows) * num_params - 2.0 * prev_loglik

    return {
        "pi": pi,
        "A": transitions,
        "means": means,
        "vars_diag": vars_diag,
        "loglik": float(prev_loglik),
        "n_iter_ran": int(n_iter_ran),
        "converged": converged,
        "aic": float(aic),
        "bic": float(bic),
    }


# -----------------------------
# Semantic labeling
# -----------------------------


def _weighted_state_mean(values: pd.Series, gamma: np.ndarray) -> np.ndarray:
    array = values.to_numpy(dtype=float)
    result = np.full(gamma.shape[1], np.nan, dtype=float)
    finite_mask = np.isfinite(array)
    if not finite_mask.any():
        return result

    weights = gamma[finite_mask]
    denom = weights.sum(axis=0)
    valid = denom > 0.0
    if valid.any():
        result[valid] = (weights[:, valid].T @ array[finite_mask]) / denom[valid]
    return result


def _zscore_state_metric(values: np.ndarray) -> np.ndarray:
    mean = np.nanmean(values)
    std = np.nanstd(values)
    if not np.isfinite(std) or std == 0.0:
        return np.zeros_like(values)
    return (values - mean) / std


def _build_state_signature_table(features: pd.DataFrame, gamma: np.ndarray, transitions: np.ndarray) -> pd.DataFrame:
    signature_data: dict[str, np.ndarray] = {}
    for column in STATE_SIGNATURE_COLUMNS:
        if column in features.columns:
            signature_data[f"mean_{column}"] = _weighted_state_mean(features[column], gamma)

    occupancy = gamma.mean(axis=0)
    signature_data["occupancy"] = occupancy
    signature_data["self_transition"] = np.diag(transitions)

    signatures = pd.DataFrame(signature_data)
    signatures.index = [f"state_{state}" for state in range(gamma.shape[1])]
    return signatures


def _semantic_mapping_from_signatures(signatures: pd.DataFrame) -> tuple[dict[str, int], pd.DataFrame]:
    """Assign directional semantic labels from latent-state signatures.

    Latent states come from the statistical HMM fit. Semantic labels are added
    afterward by a deterministic rule over state signatures. The vocabulary is
    intentionally directional by design:
    - ``CORE``: lower-vol, neutral or balanced background regime.
    - ``DRIFT``: orderly positive directional regime.
    - ``SHOCK``: adverse, stressed, high-vol regime.
    - ``SURGE``: strong positive expansion regime.
    """
    mean_r1 = _zscore_state_metric(signatures["mean_r1"].to_numpy())
    mean_ts20 = _zscore_state_metric(signatures["mean_TS_20"].to_numpy())
    mean_ts50 = _zscore_state_metric(signatures["mean_TS_50"].to_numpy())
    mean_er20 = _zscore_state_metric(signatures["mean_ER_20"].to_numpy())
    mean_vol20 = _zscore_state_metric(signatures["mean_vol_20"].to_numpy())
    mean_band_w = _zscore_state_metric(signatures["mean_band_w"].to_numpy())
    mean_band_pos = _zscore_state_metric(signatures["mean_band_pos"].to_numpy() - 0.5)
    mean_dist = _zscore_state_metric(signatures["mean_dist_from_mean_vol_units"].to_numpy())
    occupancy = _zscore_state_metric(signatures["occupancy"].to_numpy())
    self_transition = _zscore_state_metric(signatures["self_transition"].to_numpy())

    atr_component = _zscore_state_metric(signatures.get("mean_atr_pct", pd.Series(np.zeros(len(signatures)))).to_numpy())
    ewma_component = _zscore_state_metric(signatures.get("mean_ewma_vol", pd.Series(np.zeros(len(signatures)))).to_numpy())

    direction = mean_r1 + 0.35 * mean_ts20 + 0.45 * mean_ts50 + 0.20 * mean_band_pos
    trend_quality = 0.45 * np.abs(mean_ts20) + 0.35 * np.abs(mean_ts50) + 0.55 * mean_er20
    volatility = mean_vol20 + 0.75 * atr_component + 0.50 * ewma_component + 0.40 * mean_band_w
    stretch = np.abs(mean_dist)

    label_score_table = pd.DataFrame(
        {
            "CORE": -1.10 * volatility - 0.90 * np.abs(direction) - 0.50 * stretch + 0.40 * occupancy + 0.35 * self_transition,
            "DRIFT": 0.95 * direction + 0.80 * trend_quality - 0.55 * volatility + 0.40 * self_transition - 0.20 * stretch,
            "SHOCK": -1.00 * direction + 1.05 * volatility - 0.30 * trend_quality + 0.20 * stretch - 0.10 * mean_band_pos,
            "SURGE": 1.10 * direction + 0.65 * trend_quality + 0.80 * volatility + 0.20 * mean_band_pos + 0.10 * stretch,
        },
        index=signatures.index,
    )

    states = list(range(len(signatures)))
    best_perm: tuple[str, ...] | None = None
    best_score = -np.inf
    for perm in permutations(SEMANTIC_REGIME_LABELS):
        total = 0.0
        for state, label in zip(states, perm):
            total += float(label_score_table.iloc[state][label])
        if total > best_score:
            best_score = total
            best_perm = perm

    assert best_perm is not None
    semantic_to_state = {label: state for state, label in zip(states, best_perm)}
    return semantic_to_state, label_score_table


# -----------------------------
# Public fit/apply API
# -----------------------------


def fit_hmm_pack(features: pd.DataFrame, cfg: HMMConfig | None = None) -> dict[str, Any]:
    """Fit the 4-state HMM on the canonical descriptive feature subset.

    The HMM consumes only ``HMM_FEATURE_COLS``. Semantic labels are not learned
    directly by the HMM; they are assigned afterward from the fitted state
    signatures.
    """
    if cfg is None:
        cfg = HMMConfig()
    _validate_hmm_config(cfg)

    usable_features, feature_cols, missing_info = _prepare_hmm_features(features, HMM_FEATURE_COLS)
    if missing_info["usable_rows"] < cfg.min_rows:
        raise ValueError(
            f"Too few usable rows for HMM fitting: {missing_info['usable_rows']} < {cfg.min_rows}"
        )

    X = usable_features[feature_cols].to_numpy(dtype=float)
    Xs, mean, std = _standardize(X)
    params = fit_gaussian_hmm(Xs, cfg)
    gamma_train = hmm_posterior(Xs, params)

    signatures = _build_state_signature_table(usable_features, gamma_train, params["A"])
    semantic_to_state, label_score_table = _semantic_mapping_from_signatures(signatures)
    state_to_semantic = {state: label for label, state in semantic_to_state.items()}

    occupancy = gamma_train.mean(axis=0)
    self_transition = np.diag(params["A"])
    diagnostics = {
        "usable_rows": missing_info["usable_rows"],
        "dropped_rows": missing_info["dropped_rows"],
        "usable_start": missing_info["usable_start"],
        "usable_end": missing_info["usable_end"],
        "final_loglik": float(params["loglik"]),
        "n_iter_ran": int(params["n_iter_ran"]),
        "converged": bool(params["converged"]),
        "aic": float(params["aic"]),
        "bic": float(params["bic"]),
        "state_occupancy": occupancy.tolist(),
        "min_state_occupancy": float(occupancy.min()),
        "max_state_occupancy": float(occupancy.max()),
        "self_transition": self_transition.tolist(),
        "transition_matrix": np.asarray(params["A"], dtype=float).tolist(),
        "state_signatures": signatures.reset_index(names="state").to_dict(orient="records"),
        "label_score_table": label_score_table.reset_index(names="state").to_dict(orient="records"),
        "effective_sample_count": int(len(usable_features)),
    }

    return {
        "cfg": cfg.__dict__,
        "feature_cols": feature_cols,
        "standardize": {"mu": mean.tolist(), "sd": std.tolist()},
        "params": {
            "pi": np.asarray(params["pi"], dtype=float),
            "A": np.asarray(params["A"], dtype=float),
            "means": np.asarray(params["means"], dtype=float),
            "vars_diag": np.asarray(params["vars_diag"], dtype=float),
        },
        "semantic_to_state": semantic_to_state,
        "state_to_semantic": state_to_semantic,
        "diagnostics": diagnostics,
    }


def apply_hmm_pack(features: pd.DataFrame, pack: dict[str, Any], mode: HMMMode = "filter") -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply a fitted HMM pack to descriptive features.

    Outputs:
    - ``HMM_STATE_0..K-1``: latent-state posteriors.
    - ``HMM_DOM``: dominant latent state index.
    - ``HMM_CONF``: dominant latent-state posterior.
    - ``P_CORE_HMM`` / ``P_DRIFT_HMM`` / ``P_SHOCK_HMM`` / ``P_SURGE_HMM``:
      semantic probabilities derived from the post hoc directional mapping.
    - ``HMM_LABEL``: semantic label with the highest mapped probability.
    """
    if mode not in {"filter", "smooth"}:
        raise ValueError(f"Unsupported HMM mode: {mode}")

    feature_cols = tuple(pack["feature_cols"])
    usable_features, _, missing_info = _prepare_hmm_features(features, feature_cols)
    if usable_features.empty:
        raise ValueError("No usable rows remain after dropping NaNs for HMM inference.")

    X = usable_features[list(feature_cols)].to_numpy(dtype=float)
    mean = np.asarray(pack["standardize"]["mu"], dtype=float)
    std = np.asarray(pack["standardize"]["sd"], dtype=float)
    std = np.where(std == 0.0, 1.0, std)
    Xs = (X - mean) / std

    params = {
        "pi": np.asarray(pack["params"]["pi"], dtype=float),
        "A": np.asarray(pack["params"]["A"], dtype=float),
        "means": np.asarray(pack["params"]["means"], dtype=float),
        "vars_diag": np.asarray(pack["params"]["vars_diag"], dtype=float),
    }

    gamma = hmm_posterior(Xs, params) if mode == "smooth" else hmm_filter_posterior(Xs, params)
    out = features.copy()

    num_states = int(pack["cfg"]["n_states"])
    for state in range(num_states):
        out.loc[usable_features.index, f"HMM_STATE_{state}"] = gamma[:, state]
    dominant_state = gamma.argmax(axis=1).astype(int)
    out.loc[usable_features.index, "HMM_CONF"] = gamma.max(axis=1)
    out.loc[usable_features.index, "HMM_DOM"] = dominant_state

    semantic_to_state = {label: int(state) for label, state in pack["semantic_to_state"].items()}
    semantic_series = {}
    for label in SEMANTIC_REGIME_LABELS:
        column_name = f"P_{label}_HMM"
        state = semantic_to_state[label]
        probabilities = gamma[:, state]
        out.loc[usable_features.index, column_name] = probabilities
        semantic_series[label] = probabilities

    semantic_probability_frame = pd.DataFrame(semantic_series, index=usable_features.index)
    out.loc[usable_features.index, "HMM_LABEL"] = semantic_probability_frame.idxmax(axis=1)

    meta = {
        "cfg": pack["cfg"],
        "feature_cols": list(feature_cols),
        "mode": mode,
        "mode_description": (
            "filter uses only observations available up to each timestamp"
            if mode == "filter"
            else "smooth uses the full sample and can repaint historical posteriors"
        ),
        "semantic_to_state": semantic_to_state,
        "state_to_semantic": pack["state_to_semantic"],
        "diagnostics": pack.get("diagnostics", {}),
        "inference_rows": int(len(usable_features)),
        "dropped_rows": int(missing_info["dropped_rows"]),
        "usable_start": missing_info["usable_start"],
        "usable_end": missing_info["usable_end"],
        "train_info": {
            "loglik": pack.get("diagnostics", {}).get("final_loglik"),
            "n_iter_ran": pack.get("diagnostics", {}).get("n_iter_ran"),
            "converged": pack.get("diagnostics", {}).get("converged"),
        },
        "params": {
            "pi": params["pi"].tolist(),
            "A": params["A"].tolist(),
        },
    }
    return out, meta


def save_hmm_pack(pack: dict[str, Any], path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    joblib.dump(pack, path)


def load_hmm_pack(path: str) -> dict[str, Any]:
    return joblib.load(path)
