
#!/usr/bin/env python3
"""
candlestick_research_tool_v2.py

Full research tool for candlestick similarity + sequences + clustering,
with two upgrades requested/needed for serious research:

1) Walk-forward (no look-ahead) fitting for scaling/covariance:
   - When querying at time t, fit standardization (and Mahalanobis precision)
     ONLY on training window (e.g., rows < t), optionally with a rolling window.
   This avoids using future information in distance geometry.

2) Novelty detection:
   - Measures how "unlike history" a query candle/sequence is, by comparing its
     nearest-neighbor distance against the empirical distribution of nearest-neighbor
     distances inside the training set.
   - Output includes novelty_percentile (higher = more novel / rarer).

3) HTML report:
   - Produces a small self-contained HTML report with:
     - query candle/sequence summary
     - nearest neighbors table
     - neighbor outcome summaries across horizons
     - novelty diagnostics
     - optional clustering summary (if scikit-learn is installed)

Input:
  A CSV/Parquet table like your out.csv, containing candlestick features and outcomes.

Key math (summary):

Feature vector:
  x_t ∈ R^d (single candle) or s_t ∈ R^{dL} (sequence length L).

Standardization (z-score):
  x' = (x - μ) / σ

Euclidean distance:
  d(x,q)=||x-q||_2

Cosine distance:
  d=1 - (x·q)/(||x|| ||q||)

Mahalanobis distance:
  d = sqrt( (x-q)^T Σ^{-1} (x-q) )

Novelty:
  Let nn_dist(q) = min_{i in train} d(x_i, q)
  Compute distribution { nn_dist(x_i) } within training.
  novelty_percentile = percentile_rank(nn_dist(q), {nn_dist(x_i)})

Notes:
- For BTC daily (~3k rows), exact nearest-neighbor distance computation is feasible
  without external ANN libraries.

Cum îl folosești (esențial)
1) Single-candle kNN, walk-forward pe tot trecutul
python candlestick_research_tool_v2.py \
  --input out.csv \
  --key-col timestamp \
  --query 2000 \
  --standardize \
  --metric euclidean \
  --top-k 100 \
  --exclude-window 10 \
  --min-train 300 \
  --train-window 0 \
  --out-dir research_out_v2

2) Rolling walk-forward (doar ultimele N zile din trecut)
python candlestick_research_tool_v2.py \
  --input out.csv \
  --key-col timestamp \
  --query 2000 \
  --standardize \
  --metric mahalanobis \
  --top-k 200 \
  --exclude-window 30 \
  --min-train 300 \
  --train-window 800 \
  --out-dir research_out_v2

3) Sequence search (ex: 3 lumânări consecutive)
python candlestick_research_tool_v2.py \
  --input out.csv \
  --key-col timestamp \
  --query 2000 \
  --seq-len 3 \
  --standardize \
  --metric cosine \
  --top-k 200 \
  --exclude-window 30 \
  --min-train 300 \
  --train-window 0 \
  --out-dir research_out_v2_seq3

Ce înseamnă “novelty_percentile”

În meta.json ai:

nn_query = distanța până la cel mai apropiat vecin din training

novelty_percentile = unde cade nn_query în distribuția distanțelor NN din training (0–100)

Interpretare:

~10–30%: foarte comun

~50%: tipic

~80–95%: rar / neobișnuit

95%: extrem (potențial “regim nou” sau eveniment)

Clustering (opțional)

Scriptul are PCA+KMeans (dacă ai scikit-learn). Eu nu am inclus un output aici deoarece în mediul curent rularea cu clustering a depășit limita de execuție, dar pe sistemul tău ar trebui să meargă (și e marcat ca opțional în script).

Dacă vrei, următorul pas corect este să stabilim un workflow standard:

rulezi kNN pe lumânarea curentă zilnic (single + seq_len=3)

citești neighbors_summary din meta.json

urmărești cum se schimbă novelty_percentile în timp (detecție de schimbări de regim).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Optional sklearn for clustering
try:
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False


DEFAULT_CANDLE_FEATURES = [
    "pct_range_size",
    "pct_net_move",
    "pct_upper_shadow_size",
    "pct_lower_shadow_size",
    "frac_upper_shadow",
    "frac_lower_shadow",
    "frac_body",
    "direction_sign",
]

DEFAULT_HORIZONS = [1, 3, 5, 7, 10]


# ----------------------------
# Utilities
# ----------------------------

def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in [".parquet", ".pq"]:
        return pd.read_parquet(path)
    raise ValueError("Unsupported input format. Use .csv or .parquet")


def export_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
        return
    if path.suffix.lower() in [".parquet", ".pq"]:
        df.to_parquet(path, index=False)
        return
    raise ValueError("Unsupported output format. Use .csv or .parquet")


def export_json(obj: Dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def safe_to_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


# ----------------------------
# Standardization
# ----------------------------

@dataclass(frozen=True)
class Standardizer:
    """
    Column-wise z-score standardizer.

    x' = (x - μ) / σ
    """
    mean_: np.ndarray
    std_: np.ndarray

    def transform(self, X: np.ndarray) -> np.ndarray:
        std = np.where(self.std_ == 0, 1.0, self.std_)
        return (X - self.mean_) / std

    @staticmethod
    def fit(X: np.ndarray) -> "Standardizer":
        return Standardizer(
            mean_=np.nanmean(X, axis=0),
            std_=np.nanstd(X, axis=0, ddof=0),
        )


# ----------------------------
# Distances
# ----------------------------

def euclidean_distance(X: np.ndarray, q: np.ndarray) -> np.ndarray:
    diff = X - q.reshape(1, -1)
    return np.sqrt(np.sum(diff * diff, axis=1))


def cosine_distance(X: np.ndarray, q: np.ndarray) -> np.ndarray:
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    qn = q / (np.linalg.norm(q) + 1e-12)
    cos = (Xn @ qn.reshape(-1, 1)).reshape(-1)
    return 1.0 - cos


def fit_precision_mahalanobis(X: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    cov = np.cov(X, rowvar=False)
    cov = cov + ridge * np.eye(cov.shape[0])
    return np.linalg.inv(cov)


def mahalanobis_distance(X: np.ndarray, q: np.ndarray, precision: np.ndarray) -> np.ndarray:
    diff = X - q.reshape(1, -1)
    v = diff @ precision
    return np.sqrt(np.sum(v * diff, axis=1))


def compute_distances(X: np.ndarray, q: np.ndarray, metric: str, precision: Optional[np.ndarray]) -> np.ndarray:
    metric = metric.lower()
    if metric == "euclidean":
        return euclidean_distance(X, q)
    if metric == "cosine":
        return cosine_distance(X, q)
    if metric == "mahalanobis":
        if precision is None:
            raise ValueError("precision required for mahalanobis")
        return mahalanobis_distance(X, q, precision)
    raise ValueError(f"Unknown metric: {metric}")


def distance_to_similarity(dist: np.ndarray, method: str = "inv") -> np.ndarray:
    method = method.lower()
    if method == "inv":
        return 1.0 / (1.0 + dist)
    if method == "exp":
        return np.exp(-dist)
    raise ValueError(f"Unknown similarity mapping: {method}")


# ----------------------------
# Feature matrices
# ----------------------------

def build_feature_matrix(df: pd.DataFrame, feature_cols: Sequence[str]) -> np.ndarray:
    return df.loc[:, list(feature_cols)].to_numpy(dtype=float)


def build_sequence_matrix(X: np.ndarray, seq_len: int) -> np.ndarray:
    """
    Concatenate consecutive rows into a longer vector.

    s_t = [x_t | x_{t+1} | ... | x_{t+L-1}] ∈ R^{dL}
    """
    if seq_len <= 0:
        raise ValueError("seq_len must be >= 1")
    n, d = X.shape
    if n < seq_len:
        raise ValueError("Not enough rows for seq_len")
    out = np.empty((n - seq_len + 1, d * seq_len), dtype=float)
    for i in range(n - seq_len + 1):
        out[i] = X[i:i + seq_len].reshape(-1)
    return out


def resolve_query_index(df: pd.DataFrame, query: str, key_col: Optional[str]) -> int:
    """
    query can be:
    - numeric row index (e.g., "1234")
    - exact match in key_col (e.g., timestamp, date string)
    """
    if query.isdigit():
        idx = int(query)
        if idx < 0 or idx >= len(df):
            raise ValueError("Query index out of range")
        return idx

    if not key_col or key_col not in df.columns:
        raise ValueError("Non-numeric query requires --key-col present in data")

    matches = df.index[df[key_col].astype(str) == query].to_list()
    if not matches:
        raise ValueError(f"No row found for {key_col}={query}")
    return int(matches[0])


# ----------------------------
# Walk-forward training window
# ----------------------------

def training_slice_end_at(
    n_rows: int,
    query_index: int,
    train_window: Optional[int],
    min_train: int,
) -> slice:
    """
    Training set is strictly BEFORE the query index to avoid lookahead.

    If train_window is None:
      train = [0 .. query_index-1]
    Else:
      train = [max(0, query_index-train_window) .. query_index-1]

    min_train:
      minimum rows required in training.
    """
    end = query_index
    if end < min_train:
        raise ValueError(f"Not enough past data for training: need >= {min_train} rows before query.")
    if train_window is None:
        start = 0
    else:
        start = max(0, end - train_window)
        if end - start < min_train:
            start = max(0, end - min_train)
    return slice(start, end)


# ----------------------------
# Nearest-neighbor novelty
# ----------------------------

def nearest_neighbor_distances_within_set(
    X: np.ndarray,
    metric: str,
    precision: Optional[np.ndarray],
    chunk: int = 512,
) -> np.ndarray:
    """
    Compute nearest-neighbor distance for each row within the same set (excluding itself).

    This is used for novelty detection.

    Efficient exact computation for n~few-thousand:
    - For Euclidean on transformed space: use
        ||a-b||^2 = ||a||^2 + ||b||^2 - 2 a·b
      computed in chunks to control memory.
    - For Cosine distance: normalize rows to unit length and use dot products.
      cosine_distance = 1 - cos_sim => nearest neighbor = max cos_sim (excluding self).
    - For Mahalanobis: if Precision = Σ^{-1}, whiten using Cholesky:
        let W s.t. W^T W = Precision
        then d_M(a,b) = || (a-b) W ||_2
      so we compute Euclidean NN on Xw = X @ W.

    Returns:
      nn[i] = min_{j != i} d(x_i, x_j)
    """
    metric = metric.lower()
    X_use = X

    if metric == "mahalanobis":
        if precision is None:
            raise ValueError("precision required for mahalanobis")
        # Cholesky of precision (SPD after ridge)
        W = np.linalg.cholesky(precision)
        X_use = X_use @ W  # whitened so Mahalanobis becomes Euclidean

        metric = "euclidean"

    n, d = X_use.shape
    nn = np.full(n, np.inf, dtype=float)

    if metric == "euclidean":
        # Precompute squared norms
        norms = np.sum(X_use * X_use, axis=1)

        for i0 in range(0, n, chunk):
            i1 = min(n, i0 + chunk)
            A = X_use[i0:i1]  # (m,d)
            # squared distances to all points: m x n
            # dist2 = ||A||^2 + ||X||^2 - 2 A X^T
            dist2 = norms[i0:i1].reshape(-1, 1) + norms.reshape(1, -1) - 2.0 * (A @ X_use.T)
            # exclude self-distances for rows in this block
            for ii, gi in enumerate(range(i0, i1)):
                dist2[ii, gi] = np.inf
            # nearest squared dist per row
            nn[i0:i1] = np.sqrt(np.min(dist2, axis=1))
        return nn

    if metric == "cosine":
        Xn = X_use / (np.linalg.norm(X_use, axis=1, keepdims=True) + 1e-12)
        for i0 in range(0, n, chunk):
            i1 = min(n, i0 + chunk)
            A = Xn[i0:i1]
            sim = A @ Xn.T  # cosine similarity
            # exclude self
            for ii, gi in enumerate(range(i0, i1)):
                sim[ii, gi] = -np.inf
            best = np.max(sim, axis=1)  # max similarity => min distance
            nn[i0:i1] = 1.0 - best
        return nn

    raise ValueError(f"Unsupported metric for novelty: {metric}")


def novelty_percentile(nn_query: float, nn_train: np.ndarray) -> float:
    """
    Percentile rank of nn_query among nn_train.
    Higher => more novel (farther from its nearest historical neighbor).
    """
    nn_train = nn_train[np.isfinite(nn_train)]
    if len(nn_train) == 0 or not np.isfinite(nn_query):
        return float("nan")
    return float(np.mean(nn_train <= nn_query) * 100.0)


# ----------------------------
# Outcomes summary
# ----------------------------

def outcome_cols(horizons: Sequence[int]) -> List[str]:
    cols: List[str] = []
    for k in horizons:
        cols += [f"fwd_logret_{k}", f"mfe_{k}", f"mae_{k}"]
    return cols


def summarize_neighbors(nei: pd.DataFrame, horizons: Sequence[int]) -> Dict[str, object]:
    out: Dict[str, object] = {}
    out["n"] = int(len(nei))
    out["similarity_min"] = safe_to_float(np.nanmin(nei["similarity"]))
    out["similarity_median"] = safe_to_float(np.nanmedian(nei["similarity"]))
    out["similarity_max"] = safe_to_float(np.nanmax(nei["similarity"]))

    for k in horizons:
        rcol = f"fwd_logret_{k}"
        mfecol = f"mfe_{k}"
        maecol = f"mae_{k}"
        if rcol not in nei.columns:
            continue
        r = nei[rcol].to_numpy(dtype=float)
        out[f"h{k}"] = {
            "logret_mean": safe_to_float(np.nanmean(r)),
            "logret_median": safe_to_float(np.nanmedian(r)),
            "winrate": safe_to_float(np.nanmean(r > 0)),
            "mfe_median": safe_to_float(np.nanmedian(nei[mfecol].to_numpy(dtype=float))) if mfecol in nei.columns else float("nan"),
            "mae_median": safe_to_float(np.nanmedian(nei[maecol].to_numpy(dtype=float))) if maecol in nei.columns else float("nan"),
        }
    return out


# ----------------------------
# Similarity search core (single / sequence)
# ----------------------------

def knn_single(
    df: pd.DataFrame,
    X: np.ndarray,
    query_index: int,
    feature_cols: Sequence[str],
    horizons: Sequence[int],
    metric: str,
    similarity_map: str,
    standardize: bool,
    train_window: Optional[int],
    min_train: int,
    exclude_window: int,
    top_k: int,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    train_sl = training_slice_end_at(len(df), query_index, train_window, min_train)
    X_train = X[train_sl]

    scaler = Standardizer.fit(X_train) if standardize else None
    Xt = scaler.transform(X_train) if scaler else X_train
    q = scaler.transform(X[query_index:query_index+1])[0] if scaler else X[query_index]

    precision = fit_precision_mahalanobis(Xt) if metric.lower() == "mahalanobis" else None
    dist_train = compute_distances(Xt, q, metric=metric, precision=precision)

    # map train indices back to global indices
    train_indices = np.arange(train_sl.start, train_sl.stop)

    # exclude local window around query (in global indices)
    if exclude_window > 0:
        lo = max(0, query_index - exclude_window)
        hi = min(len(df) - 1, query_index + exclude_window)
        mask_excl = (train_indices >= lo) & (train_indices <= hi)
        dist_train[mask_excl] = np.inf

    pick = np.argsort(dist_train)[:top_k]
    global_idx = train_indices[pick]

    neighbors = df.iloc[global_idx].copy()
    neighbors["distance"] = dist_train[pick]
    neighbors["similarity"] = distance_to_similarity(neighbors["distance"].to_numpy(), method=similarity_map)
    neighbors["neighbor_rank"] = np.arange(1, len(neighbors) + 1)

    # novelty
    nn_train = nearest_neighbor_distances_within_set(Xt, metric=metric, precision=precision)
    nn_query = float(np.min(dist_train[np.isfinite(dist_train)])) if np.isfinite(dist_train).any() else float("nan")
    nov_pct = novelty_percentile(nn_query, nn_train)

    meta = {
        "mode": "single",
        "query_index": int(query_index),
        "train_start": int(train_sl.start),
        "train_end": int(train_sl.stop - 1),
        "train_size": int(train_sl.stop - train_sl.start),
        "metric": metric,
        "standardize": bool(standardize),
        "train_window": train_window,
        "min_train": int(min_train),
        "exclude_window": int(exclude_window),
        "top_k": int(top_k),
        "nn_query": nn_query,
        "novelty_percentile": nov_pct,
        "features": list(feature_cols),
        "neighbor_summary": summarize_neighbors(neighbors, horizons),
    }
    return neighbors, meta


def knn_sequence(
    df: pd.DataFrame,
    X: np.ndarray,
    query_start: int,
    seq_len: int,
    horizons: Sequence[int],
    metric: str,
    similarity_map: str,
    standardize: bool,
    train_window: Optional[int],
    min_train: int,
    exclude_window: int,
    top_k: int,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    # sequence matrix has n-seq_len+1 rows; sequence index == start index
    S = build_sequence_matrix(X, seq_len)
    n_seq = S.shape[0]
    if query_start < 0 or query_start >= n_seq:
        raise ValueError("Query sequence start out of range for seq matrix.")

    # training sequences must end strictly before query sequence start index
    # i.e., their start < query_start, because they are formed from past rows.
    train_sl = training_slice_end_at(n_seq, query_start, train_window, min_train)
    S_train = S[train_sl]

    scaler = Standardizer.fit(S_train) if standardize else None
    St = scaler.transform(S_train) if scaler else S_train
    q = scaler.transform(S[query_start:query_start+1])[0] if scaler else S[query_start]

    precision = fit_precision_mahalanobis(St) if metric.lower() == "mahalanobis" else None
    dist_train = compute_distances(St, q, metric=metric, precision=precision)

    train_indices = np.arange(train_sl.start, train_sl.stop)  # sequence start indices

    # exclude local window on start indices
    if exclude_window > 0:
        lo = max(0, query_start - exclude_window)
        hi = min(n_seq - 1, query_start + exclude_window)
        mask_excl = (train_indices >= lo) & (train_indices <= hi)
        dist_train[mask_excl] = np.inf

    pick = np.argsort(dist_train)[:top_k]
    start_idx = train_indices[pick]
    end_idx = start_idx + seq_len - 1

    neighbors = pd.DataFrame({
        "seq_start_index": start_idx.astype(int),
        "seq_end_index": end_idx.astype(int),
        "distance": dist_train[pick],
    })
    neighbors["similarity"] = distance_to_similarity(neighbors["distance"].to_numpy(), method=similarity_map)
    neighbors["neighbor_rank"] = np.arange(1, len(neighbors) + 1)

    # attach outcomes anchored at end_index
    for k in horizons:
        for col in [f"fwd_logret_{k}", f"mfe_{k}", f"mae_{k}"]:
            if col in df.columns:
                neighbors[col] = df.iloc[end_idx][col].to_numpy()

    # novelty within training sequences
    nn_train = nearest_neighbor_distances_within_set(St, metric=metric, precision=precision)
    nn_query = float(np.min(dist_train[np.isfinite(dist_train)])) if np.isfinite(dist_train).any() else float("nan")
    nov_pct = novelty_percentile(nn_query, nn_train)

    meta = {
        "mode": "sequence",
        "seq_len": int(seq_len),
        "query_start_index": int(query_start),
        "query_end_index": int(query_start + seq_len - 1),
        "train_start": int(train_sl.start),
        "train_end": int(train_sl.stop - 1),
        "train_size": int(train_sl.stop - train_sl.start),
        "metric": metric,
        "standardize": bool(standardize),
        "train_window": train_window,
        "min_train": int(min_train),
        "exclude_window": int(exclude_window),
        "top_k": int(top_k),
        "nn_query": nn_query,
        "novelty_percentile": nov_pct,
        "neighbor_summary": summarize_neighbors(neighbors, horizons),
    }
    return neighbors, meta


# ----------------------------
# Clustering (optional)
# ----------------------------

def cluster_candles(X: np.ndarray, n_components: int, n_clusters: int, random_state: int = 42) -> Tuple[np.ndarray, np.ndarray, Dict[str, object]]:
    if not SKLEARN_OK:
        raise RuntimeError("scikit-learn not available")
    scaler = Standardizer.fit(X)
    Xs = scaler.transform(X)
    pca = PCA(n_components=n_components, random_state=random_state)
    coords = pca.fit_transform(Xs)
    km = KMeans(n_clusters=n_clusters, n_init=20, random_state=random_state)
    labels = km.fit_predict(coords)
    info = {
        "pca_explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "n_components": int(n_components),
        "n_clusters": int(n_clusters),
    }
    return labels, coords, info


def summarize_clusters(df: pd.DataFrame, labels: np.ndarray, horizons: Sequence[int]) -> pd.DataFrame:
    tmp = df.copy()
    tmp["cluster"] = labels.astype(int)
    rows = []
    for cid, g in tmp.groupby("cluster"):
        rec: Dict[str, object] = {"cluster": int(cid), "n": int(len(g))}
        for k in horizons:
            rcol = f"fwd_logret_{k}"
            if rcol in g.columns:
                r = g[rcol].to_numpy(dtype=float)
                rec[f"logret_median_{k}"] = float(np.nanmedian(r))
                rec[f"winrate_{k}"] = float(np.nanmean(r > 0))
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("n", ascending=False).reset_index(drop=True)


# ----------------------------
# HTML report
# ----------------------------

def html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def write_html_report(
    path: Path,
    title: str,
    query_info: Dict[str, object],
    query_row: Optional[pd.Series],
    feature_cols: Sequence[str],
    neighbors_df: pd.DataFrame,
    horizons: Sequence[int],
    key_col: Optional[str],
    cluster_info: Optional[Dict[str, object]] = None,
    cluster_table: Optional[pd.DataFrame] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    # compact neighbors table
    keep = []
    if key_col and key_col in neighbors_df.columns:
        keep.append(key_col)
    keep += list(feature_cols)
    keep += outcome_cols(horizons)
    keep += [c for c in ["distance", "similarity", "neighbor_rank", "seq_start_index", "seq_end_index"] if c in neighbors_df.columns]
    keep = [c for c in keep if c in neighbors_df.columns]
    neigh = neighbors_df.loc[:, keep].copy()

    # format floats
    for c in neigh.columns:
        if neigh[c].dtype.kind in "fc":
            neigh[c] = neigh[c].astype(float).round(6)

    summary = query_info.get("neighbor_summary", {})

    parts = []
    parts.append(f"<h1>{html_escape(title)}</h1>")
    parts.append("<h2>Query</h2>")
    parts.append("<pre>" + html_escape(json.dumps({k: query_info[k] for k in query_info if k != "neighbor_summary"}, indent=2, ensure_ascii=False)) + "</pre>")

    if query_row is not None:
        qr = query_row.to_frame().T
        qkeep = []
        if key_col and key_col in qr.columns:
            qkeep.append(key_col)
        qkeep += list(feature_cols)
        qkeep += outcome_cols(horizons)
        qkeep = [c for c in qkeep if c in qr.columns]
        qr = qr[qkeep].copy()
        for c in qr.columns:
            if qr[c].dtype.kind in "fc":
                qr[c] = qr[c].astype(float).round(6)
        parts.append("<h3>Query row values</h3>")
        parts.append(qr.to_html(index=False))

    parts.append("<h2>Nearest neighbors</h2>")
    parts.append(neigh.to_html(index=False))

    parts.append("<h2>Neighbors outcome summary</h2>")
    parts.append("<pre>" + html_escape(json.dumps(summary, indent=2, ensure_ascii=False)) + "</pre>")

    if cluster_info and cluster_table is not None:
        parts.append("<h2>Clustering (PCA + KMeans)</h2>")
        parts.append("<pre>" + html_escape(json.dumps(cluster_info, indent=2, ensure_ascii=False)) + "</pre>")
        parts.append(cluster_table.to_html(index=False))

    html = "<html><head><meta charset='utf-8'><style>body{font-family:Arial,Helvetica,sans-serif} table{border-collapse:collapse} td,th{border:1px solid #ccc;padding:4px 6px;font-size:12px} pre{background:#f7f7f7;padding:10px;border:1px solid #ddd;}</style></head><body>" + "\n".join(parts) + "</body></html>"
    path.write_text(html, encoding="utf-8")


# ----------------------------
# main
# ----------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Candlestick research tool v2: walk-forward kNN + novelty + report.")
    p.add_argument("--input", required=True, type=Path, help="out.csv / out.parquet")
    p.add_argument("--key-col", default="timestamp", help="Optional id/date column for querying by value. Use '' to disable.")
    p.add_argument("--features", default=",".join(DEFAULT_CANDLE_FEATURES))
    p.add_argument("--horizons", default="1,3,5,7,10")

    p.add_argument("--query", required=True, help="Row index (e.g. 1234) or exact key-col value")
    p.add_argument("--seq-len", type=int, default=1)
    p.add_argument("--top-k", type=int, default=50)
    p.add_argument("--metric", choices=["euclidean", "cosine", "mahalanobis"], default="euclidean")
    p.add_argument("--standardize", action="store_true")
    p.add_argument("--similarity-map", choices=["inv", "exp"], default="inv")

    # walk-forward
    p.add_argument("--train-window", type=int, default=0, help="0=all past; else rolling window size (rows).")
    p.add_argument("--min-train", type=int, default=300, help="Minimum training rows before query.")
    p.add_argument("--exclude-window", type=int, default=5)

    # outputs
    p.add_argument("--out-dir", type=Path, default=Path("research_out_v2"))
    p.add_argument("--neighbors-file", default="neighbors.csv")
    p.add_argument("--meta-file", default="meta.json")
    p.add_argument("--report-file", default="report.html")

    # clustering
    p.add_argument("--do-cluster", action="store_true")
    p.add_argument("--cluster-components", type=int, default=4)
    p.add_argument("--clusters", type=int, default=12)

    args = p.parse_args()

    df = read_table(args.input)

    key_col = args.key_col.strip()
    if key_col == "" or key_col not in df.columns:
        key_col = None

    features = [c.strip() for c in args.features.split(",") if c.strip()]
    horizons = sorted(set(int(x.strip()) for x in args.horizons.split(",") if x.strip()))

    # Ensure no NaNs in features (drop rows that cannot be used)
    # Keep a mapping to original indices for reporting.
    usable = df[features].notna().all(axis=1)
    df_use = df.loc[usable].reset_index(drop=False).rename(columns={"index": "_orig_index"})
    X = build_feature_matrix(df_use, features)

    query_idx = resolve_query_index(df_use, args.query, key_col=key_col)

    train_window = None if args.train_window == 0 else int(args.train_window)

    if args.seq_len <= 1:
        neighbors, meta = knn_single(
            df=df_use,
            X=X,
            query_index=query_idx,
            feature_cols=features,
            horizons=horizons,
            metric=args.metric,
            similarity_map=args.similarity_map,
            standardize=bool(args.standardize),
            train_window=train_window,
            min_train=int(args.min_train),
            exclude_window=int(args.exclude_window),
            top_k=int(args.top_k),
        )
        # attach orig indices
        neighbors["_orig_index"] = neighbors["_orig_index"].astype(int)
        query_row = df_use.iloc[query_idx]
        title = f"Single-candle kNN report (query idx={query_idx})"
    else:
        neighbors, meta = knn_sequence(
            df=df_use,
            X=X,
            query_start=query_idx,
            seq_len=int(args.seq_len),
            horizons=horizons,
            metric=args.metric,
            similarity_map=args.similarity_map,
            standardize=bool(args.standardize),
            train_window=train_window,
            min_train=int(args.min_train),
            exclude_window=int(args.exclude_window),
            top_k=int(args.top_k),
        )
        query_row = None
        title = f"Sequence kNN report (seq_len={args.seq_len}, query start idx={query_idx})"

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    export_df(neighbors, out_dir / args.neighbors_file)
    export_json(meta, out_dir / args.meta_file)

    # clustering optional (on all usable rows)
    cluster_info = None
    cluster_table = None
    if args.do_cluster and SKLEARN_OK:
        labels, coords, info = cluster_candles(X, n_components=args.cluster_components, n_clusters=args.clusters)
        cluster_info = info
        cluster_table = summarize_clusters(df_use, labels, horizons)
        # also export cluster labels table
        df_clusters = df_use.copy()
        df_clusters["cluster"] = labels.astype(int)
        for i in range(coords.shape[1]):
            df_clusters[f"pca_{i+1}"] = coords[:, i]
        export_df(df_clusters, out_dir / "clusters.csv")
        export_df(cluster_table, out_dir / "cluster_table.csv")
        export_json(cluster_info, out_dir / "cluster_info.json")

    write_html_report(
        path=out_dir / args.report_file,
        title=title,
        query_info=meta,
        query_row=query_row,
        feature_cols=features,
        neighbors_df=neighbors,
        horizons=horizons,
        key_col=key_col,
        cluster_info=cluster_info,
        cluster_table=cluster_table,
    )


if __name__ == "__main__":
    main()
