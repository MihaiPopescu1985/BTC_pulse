#!/usr/bin/env python3
"""
candlestick_research_tool.py

FULL RESEARCH TOOL pentru:
- Similarity search (lumânări / secvențe) în spațiul feature-urilor
- Statistici asupra vecinilor (outcomes)
- Clustering (PCA + KMeans) + rezumate

Cerințe:
- pandas, numpy
- opțional: scikit-learn (pentru KMeans/PCA). Dacă lipsește, clustering e dezactivat.

Concept cheie:
- o lumânare (sau o secvență de lumânări) devine un vector numeric x ∈ R^d
- căutăm vecinii cei mai apropiați de un query vector q
- apoi studiem distribuția rezultatelor viitoare condiționat pe acei vecini

Autor: script generat pentru workflow-ul tău de research.


Cum îl folosești (practic)

1) Similarity search pentru o lumânare (prin index)

python candlestick_research_tool.py \
  --input out.csv \
  --query 12000 \
  --standardize \
  --metric euclidean \
  --top-k 50 \
  --exclude-window 10 \
  --out-dir research_out

2) Similarity search pentru o lumânare (prin dată)

python candlestick_research_tool.py \
  --input out.csv \
  --query 2021-05-19 \
  --standardize \
  --metric mahalanobis \
  --top-k 100 \
  --exclude-window 30

3) Similarity search pentru secvență de 3 lumânări

python candlestick_research_tool.py \
  --input out.csv \
  --query 2021-05-17 \
  --seq-len 3 \
  --standardize \
  --metric cosine \
  --top-k 200 \
  --exclude-window 30

4) Clustering (PCA+KMeans) + rezumat clustere

python candlestick_research_tool.py \
  --input out.csv \
  --query 12000 \
  --standardize \
  --do-cluster \
  --cluster-components 4 \
  --clusters 12

"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Optional sklearn
try:
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False


# ----------------------------
# Config
# ----------------------------

DEFAULT_CANDLE_FEATURES = [
    # scale (% din prev_close) - mărimea mișcărilor
    "pct_range_size",
    "pct_net_move",
    "pct_upper_shadow_size",
    "pct_lower_shadow_size",
    # shape (fracții din range) - forma lumânării
    "frac_upper_shadow",
    "frac_lower_shadow",
    "frac_body",
    "direction_sign",
]

DEFAULT_HORIZONS = [1, 3, 5, 7, 10]


# ----------------------------
# Normalizare / standardizare
# ----------------------------

@dataclass(frozen=True)
class Standardizer:
    """
    Standardizare (z-score) pentru fiecare coloană.

    Matematic:
        x' = (x - μ) / σ

    Unde:
        μ = media pe coloană (train set)
        σ = deviația standard pe coloană (train set)

    Scop:
        1) face feature-urile comparabile ca scară
        2) evită ca un singur feature (ex: pct_range_size) să domine distanța
    """
    mean_: np.ndarray
    std_: np.ndarray

    def transform(self, X: np.ndarray) -> np.ndarray:
        std = np.where(self.std_ == 0, 1.0, self.std_)
        return (X - self.mean_) / std

    @staticmethod
    def fit(X: np.ndarray) -> "Standardizer":
        return Standardizer(mean_=np.nanmean(X, axis=0), std_=np.nanstd(X, axis=0, ddof=0))


# ----------------------------
# Metrici de distanță / similaritate
# ----------------------------

def euclidean_distance_matrix(X: np.ndarray, q: np.ndarray) -> np.ndarray:
    """
    Distanța euclidiană între fiecare rând din X și vectorul q.

    Matematic:
        d_i = ||x_i - q||_2 = sqrt( Σ_j (x_{ij} - q_j)^2 )

    Return:
        vector d, shape (n,)
    """
    diff = X - q.reshape(1, -1)
    return np.sqrt(np.sum(diff * diff, axis=1))


def cosine_distance_matrix(X: np.ndarray, q: np.ndarray) -> np.ndarray:
    """
    Distanța cosinus (1 - cos_sim).

    Matematic:
        cos_sim(x, q) = (x·q) / (||x|| * ||q||)
        d = 1 - cos_sim

    Observație:
        util când te interesează "direcția" vectorului (pattern relativ),
        mai mult decât mărimea absolută.
    """
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    qn = q / (np.linalg.norm(q) + 1e-12)
    cos = (Xn @ qn.reshape(-1, 1)).reshape(-1)
    return 1.0 - cos


def fit_mahalanobis_precision(X: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    """
    Estimează matricea de precizie (inv(cov)) pentru distanța Mahalanobis.

    Matematic:
        Σ = cov(X)
        Precision = Σ^{-1}

    Stabilizare:
        Σ <- Σ + ridge * I

    Scop:
        corectează pentru corelații între features.
    """
    # cov pe coloane; folosim rânduri ca observații
    cov = np.cov(X, rowvar=False)
    cov = cov + ridge * np.eye(cov.shape[0])
    return np.linalg.inv(cov)


def mahalanobis_distance_matrix(X: np.ndarray, q: np.ndarray, precision: np.ndarray) -> np.ndarray:
    """
    Distanța Mahalanobis.

    Matematic:
        d_i = sqrt( (x_i - q)^T * Precision * (x_i - q) )

    Avantaj:
        dacă două features sunt corelate, nu dublează "penalizarea".
    """
    diff = X - q.reshape(1, -1)
    # (diff @ P) ⊙ diff -> sum pe col
    v = diff @ precision
    return np.sqrt(np.sum(v * diff, axis=1))


def distance_to_similarity(dist: np.ndarray, method: str = "inv") -> np.ndarray:
    """
    Convertește distanță -> scor de similaritate în (0, 1].

    Variante:
      - "inv":  sim = 1 / (1 + d)
      - "exp":  sim = exp(-d)

    Observație:
      scorul nu e probabilitate; e doar o transformare monotonă a distanței.
    """
    method = method.lower()
    if method == "inv":
        return 1.0 / (1.0 + dist)
    if method == "exp":
        return np.exp(-dist)
    raise ValueError(f"Unknown similarity mapping: {method}")


# ----------------------------
# Construire matrici (lumânări / secvențe)
# ----------------------------

def build_feature_matrix(df: pd.DataFrame, feature_cols: Sequence[str]) -> np.ndarray:
    """
    Extrage matricea X din df[feature_cols].

    Return:
        X shape (n, d)
    """
    X = df.loc[:, list(feature_cols)].to_numpy(dtype=float)
    return X


def build_sequence_matrix(X: np.ndarray, seq_len: int) -> np.ndarray:
    """
    Construiește matrice pentru secvențe consecutive.

    Dacă o lumânare are d features, o secvență de lungime L are d*L features
    prin concatenare:

        s_t = [ x_t | x_{t+1} | ... | x_{t+L-1} ] ∈ R^{dL}

    Return:
        S shape (n-L+1, dL)
    """
    if seq_len <= 0:
        raise ValueError("seq_len must be >= 1")
    n, d = X.shape
    if n < seq_len:
        raise ValueError("Not enough rows for seq_len.")
    out = np.empty((n - seq_len + 1, d * seq_len), dtype=float)
    for i in range(n - seq_len + 1):
        out[i, :] = X[i:i + seq_len, :].reshape(-1)
    return out


def resolve_query_index(df: pd.DataFrame, query: str, date_col: Optional[str]) -> int:
    """
    Query poate fi:
    - un index numeric (ex: "1234")
    - o dată exactă (ex: "2020-03-12") dacă date_col există

    Return:
        index integer în df
    """
    # index numeric
    if query.isdigit():
        idx = int(query)
        if idx < 0 or idx >= len(df):
            raise ValueError("Query index out of range.")
        return idx

    if date_col is None or date_col not in df.columns:
        raise ValueError("Query is not numeric; date column not available.")

    # match exact pe string (presupunem YYYY-MM-DD)
    matches = df.index[df[date_col].astype(str) == query].to_list()
    if not matches:
        raise ValueError(f"No row found for date {query}.")
    return int(matches[0])


# ----------------------------
# Similarity search (kNN)
# ----------------------------

def compute_distances(
    Xs: np.ndarray,
    q: np.ndarray,
    metric: str,
    precision: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Calculează distanțele dintre toate rândurile din Xs și q.

    metric ∈ {"euclidean", "cosine", "mahalanobis"}
    """
    metric = metric.lower()
    if metric == "euclidean":
        return euclidean_distance_matrix(Xs, q)
    if metric == "cosine":
        return cosine_distance_matrix(Xs, q)
    if metric == "mahalanobis":
        if precision is None:
            raise ValueError("precision matrix required for Mahalanobis.")
        return mahalanobis_distance_matrix(Xs, q, precision)
    raise ValueError(f"Unknown metric: {metric}")


def top_k_neighbors(
    df: pd.DataFrame,
    X: np.ndarray,
    query_row_index: int,
    top_k: int,
    standardize: bool,
    metric: str,
    similarity_map: str,
    exclude_window: int = 0,
) -> pd.DataFrame:
    """
    k-NN pentru o singură lumânare (query = un rând din df).

    exclude_window:
        exclude rândurile din [query-exclude_window, query+exclude_window]
        ca să nu-ți “întoarcă” același context imediat.

    Return:
        DataFrame cu vecinii (rânduri din df) + distance + similarity
    """
    X_use = X.copy()

    if standardize:
        scaler = Standardizer.fit(X_use)
        Xs = scaler.transform(X_use)
        q = Xs[query_row_index]
        precision = fit_mahalanobis_precision(Xs) if metric.lower() == "mahalanobis" else None
        dist = compute_distances(Xs, q, metric=metric, precision=precision)
    else:
        q = X_use[query_row_index]
        precision = fit_mahalanobis_precision(X_use) if metric.lower() == "mahalanobis" else None
        dist = compute_distances(X_use, q, metric=metric, precision=precision)

    # excludere locală
    if exclude_window > 0:
        lo = max(0, query_row_index - exclude_window)
        hi = min(len(dist) - 1, query_row_index + exclude_window)
        dist[lo:hi + 1] = np.inf

    # top-k (dist mic)
    idx = np.argsort(dist)[:top_k]
    out = df.iloc[idx].copy()
    out["distance"] = dist[idx]
    out["similarity"] = distance_to_similarity(out["distance"].to_numpy(), method=similarity_map)
    out["neighbor_rank"] = np.arange(1, len(out) + 1)
    return out


def top_k_neighbors_sequence(
    df: pd.DataFrame,
    X: np.ndarray,
    query_start_index: int,
    seq_len: int,
    top_k: int,
    standardize: bool,
    metric: str,
    similarity_map: str,
    exclude_window: int = 0,
) -> pd.DataFrame:
    """
    k-NN pentru secvențe consecutive de lungime seq_len.

    Query:
        secvența care începe la query_start_index: [t, t+1, ..., t+seq_len-1]

    Observație:
        Matricea secvențelor are (n-seq_len+1) rânduri.
        Un vecin "i" reprezintă secvența care începe la i.

    Return:
        df cu rândul de start al secvenței + distance + similarity
    """
    if seq_len <= 0:
        raise ValueError("seq_len must be >= 1")
    if query_start_index < 0 or query_start_index + seq_len - 1 >= len(df):
        raise ValueError("Query sequence out of range.")

    # Build sequence matrix
    S = build_sequence_matrix(X, seq_len=seq_len)

    # standardize on sequences
    if standardize:
        scaler = Standardizer.fit(S)
        Ss = scaler.transform(S)
        q = Ss[query_start_index]  # query start maps directly
        precision = fit_mahalanobis_precision(Ss) if metric.lower() == "mahalanobis" else None
        dist = compute_distances(Ss, q, metric=metric, precision=precision)
    else:
        q = S[query_start_index]
        precision = fit_mahalanobis_precision(S) if metric.lower() == "mahalanobis" else None
        dist = compute_distances(S, q, metric=metric, precision=precision)

    # exclude local window on "start indices"
    if exclude_window > 0:
        lo = max(0, query_start_index - exclude_window)
        hi = min(len(dist) - 1, query_start_index + exclude_window)
        dist[lo:hi + 1] = np.inf

    idx = np.argsort(dist)[:top_k]

    # build output with start/end rows
    out = pd.DataFrame({
        "seq_start_index": idx.astype(int),
        "seq_end_index": (idx + seq_len - 1).astype(int),
        "distance": dist[idx],
    })
    out["similarity"] = distance_to_similarity(out["distance"].to_numpy(), method=similarity_map)
    out["neighbor_rank"] = np.arange(1, len(out) + 1)

    # attach dates if present
    # also attach outcomes anchored at the last candle in the sequence (end index)
    return out


# ----------------------------
# Statistici outcomes pe vecini
# ----------------------------

def outcome_columns_for_horizons(horizons: Sequence[int]) -> List[str]:
    cols = []
    for k in horizons:
        cols += [f"fwd_logret_{k}", f"mfe_{k}", f"mae_{k}"]
    return cols


def summarize_neighbors(
    neighbors_df: pd.DataFrame,
    horizons: Sequence[int],
) -> Dict[str, object]:
    """
    Produce un rezumat numeric al vecinilor.

    Pentru fiecare k:
      - median/mean fwd_logret_k
      - winrate: P(fwd_logret_k > 0)
      - median mfe_k
      - median mae_k

    plus:
      - n
      - top similarity stats
    """
    summary: Dict[str, object] = {}
    summary["n"] = int(len(neighbors_df))
    summary["similarity_min"] = float(np.nanmin(neighbors_df["similarity"]))
    summary["similarity_median"] = float(np.nanmedian(neighbors_df["similarity"]))
    summary["similarity_max"] = float(np.nanmax(neighbors_df["similarity"]))

    for k in horizons:
        r = neighbors_df.get(f"fwd_logret_{k}")
        mfe = neighbors_df.get(f"mfe_{k}")
        mae = neighbors_df.get(f"mae_{k}")

        if r is None:
            continue

        r_vals = r.to_numpy(dtype=float)
        mfe_vals = mfe.to_numpy(dtype=float) if mfe is not None else np.full_like(r_vals, np.nan)
        mae_vals = mae.to_numpy(dtype=float) if mae is not None else np.full_like(r_vals, np.nan)

        key = f"h{k}"
        summary[key] = {
            "logret_mean": float(np.nanmean(r_vals)),
            "logret_median": float(np.nanmedian(r_vals)),
            "winrate": float(np.nanmean(r_vals > 0)),
            "mfe_median": float(np.nanmedian(mfe_vals)),
            "mae_median": float(np.nanmedian(mae_vals)),
        }

    return summary


def attach_sequence_outcomes(
    df: pd.DataFrame,
    seq_df: pd.DataFrame,
    seq_len: int,
    horizons: Sequence[int],
    date_col: Optional[str],
) -> pd.DataFrame:
    """
    Pentru secvențe: outcomes se ancorează la ultima lumânare din secvență (end index).

    Asta răspunde întrebării:
      “ce s-a întâmplat după ce secvența s-a încheiat?”

    Return:
      seq_df + coloane date_start/date_end (dacă există) + outcomes de la end index
    """
    out = seq_df.copy()
    end_idx = out["seq_end_index"].to_numpy(dtype=int)

    if date_col and date_col in df.columns:
        out["date_start"] = df.iloc[out["seq_start_index"].to_numpy(dtype=int)][date_col].astype(str).to_numpy()
        out["date_end"] = df.iloc[end_idx][date_col].astype(str).to_numpy()

    for k in horizons:
        for col in [f"fwd_logret_{k}", f"mfe_{k}", f"mae_{k}"]:
            if col in df.columns:
                out[col] = df.iloc[end_idx][col].to_numpy()
    return out


# ----------------------------
# Clustering (PCA + KMeans)
# ----------------------------

def cluster_candles(
    X: np.ndarray,
    standardize: bool,
    n_components: int,
    n_clusters: int,
    random_state: int = 42,
) -> Tuple[np.ndarray, Optional[np.ndarray], Dict[str, object]]:
    """
    Clustering pe lumânări (nu secvențe).

    Pași:
      1) standardizare (opțional)
      2) PCA (opțional, dar recomandat) -> reduce dimensiunea, denoise
      3) KMeans -> cluster labels

    Return:
      labels shape (n,)
      pca_coords shape (n, n_components) sau None
      info dict (explained_variance, etc)

    Necesită scikit-learn.
    """
    if not SKLEARN_OK:
        raise RuntimeError("scikit-learn not available; clustering disabled.")

    X_use = X.copy()
    if standardize:
        scaler = Standardizer.fit(X_use)
        X_use = scaler.transform(X_use)

    pca = PCA(n_components=n_components, random_state=random_state)
    coords = pca.fit_transform(X_use)

    km = KMeans(n_clusters=n_clusters, n_init=20, random_state=random_state)
    labels = km.fit_predict(coords)

    info = {
        "pca_explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "pca_components": int(n_components),
        "kmeans_clusters": int(n_clusters),
    }
    return labels, coords, info


def summarize_clusters(
    df: pd.DataFrame,
    labels: np.ndarray,
    horizons: Sequence[int],
) -> pd.DataFrame:
    """
    Rezumat pe cluster:
      - count
      - mean/median logret pe orizonturi
      - winrate
      - median mfe/mae
    """
    tmp = df.copy()
    tmp["cluster"] = labels.astype(int)

    rows = []
    for cid, g in tmp.groupby("cluster"):
        rec: Dict[str, object] = {"cluster": int(cid), "n": int(len(g))}
        for k in horizons:
            rcol = f"fwd_logret_{k}"
            mfecol = f"mfe_{k}"
            maecol = f"mae_{k}"
            if rcol in g.columns:
                r = g[rcol].to_numpy(dtype=float)
                rec[f"logret_mean_{k}"] = float(np.nanmean(r))
                rec[f"logret_median_{k}"] = float(np.nanmedian(r))
                rec[f"winrate_{k}"] = float(np.nanmean(r > 0))
            if mfecol in g.columns:
                rec[f"mfe_median_{k}"] = float(np.nanmedian(g[mfecol].to_numpy(dtype=float)))
            if maecol in g.columns:
                rec[f"mae_median_{k}"] = float(np.nanmedian(g[maecol].to_numpy(dtype=float)))
        rows.append(rec)

    return pd.DataFrame(rows).sort_values("n", ascending=False).reset_index(drop=True)


# ----------------------------
# IO
# ----------------------------

def read_table(path: Path) -> pd.DataFrame:
    """
    Citește CSV sau Parquet după extensie.
    """
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in [".parquet", ".pq"]:
        return pd.read_parquet(path)
    raise ValueError("Unsupported input format. Use .csv or .parquet")


def export_df(df: pd.DataFrame, path: Path) -> None:
    """
    Exportă CSV sau Parquet după extensie.
    """
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


# ----------------------------
# main
# ----------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Candlestick full research tool: similarity + sequences + clustering.")

    p.add_argument("--input", required=True, type=Path, help="out.csv (features/outcomes table)")
    p.add_argument("--date-col", default="timestamp", help="date column name (optional). Use '' to disable.")
    p.add_argument("--features", default=",".join(DEFAULT_CANDLE_FEATURES), help="comma-separated feature columns")

    # Query & similarity
    p.add_argument("--query", required=True, help="row index (e.g. 1234) or date (YYYY-MM-DD) if date-col exists")
    p.add_argument("--top-k", type=int, default=50)
    p.add_argument("--metric", choices=["euclidean", "cosine", "mahalanobis"], default="euclidean")
    p.add_argument("--standardize", action="store_true", help="apply z-score standardization before distances")
    p.add_argument("--similarity-map", choices=["inv", "exp"], default="inv")
    p.add_argument("--exclude-window", type=int, default=5, help="exclude +/- N rows around query from results")

    # Sequence search
    p.add_argument("--seq-len", type=int, default=1, help="1 = single candle, >1 = sequence search")

    # Horizons (outcome columns)
    p.add_argument("--horizons", default="1,3,5,7,10", help="comma-separated horizons")

    # Exports
    p.add_argument("--out-dir", default="research_out", help="output directory")
    p.add_argument("--neighbors-file", default="neighbors.csv")
    p.add_argument("--neighbors-summary", default="neighbors_summary.json")

    # Clustering
    p.add_argument("--do-cluster", action="store_true", help="run PCA+KMeans clustering (requires scikit-learn)")
    p.add_argument("--cluster-components", type=int, default=4, help="PCA components")
    p.add_argument("--clusters", type=int, default=12, help="KMeans clusters")
    p.add_argument("--cluster-file", default="clusters.csv")
    p.add_argument("--cluster-summary", default="cluster_summary.json")
    p.add_argument("--cluster-table", default="cluster_table.csv")

    args = p.parse_args()

    df = read_table(args.input)

    date_col = args.date_col.strip()
    if date_col == "" or date_col not in df.columns:
        date_col = None

    features = [c.strip() for c in args.features.split(",") if c.strip()]
    horizons = [int(x.strip()) for x in args.horizons.split(",") if x.strip()]
    horizons = sorted(set(horizons))

    # Build feature matrix
    X = build_feature_matrix(df, features)

    # Resolve query
    query_idx = resolve_query_index(df, args.query, date_col=date_col)

    out_dir = Path(args.out_dir)

    # Similarity search: single candle vs sequence
    if args.seq_len <= 1:
        neighbors = top_k_neighbors(
            df=df,
            X=X,
            query_row_index=query_idx,
            top_k=args.top_k,
            standardize=args.standardize,
            metric=args.metric,
            similarity_map=args.similarity_map,
            exclude_window=args.exclude_window,
        )

        # Keep a compact set of columns (features + outcomes + meta)
        keep_cols = []
        if date_col:
            keep_cols.append(date_col)
        keep_cols += features
        keep_cols += outcome_columns_for_horizons(horizons)
        keep_cols += ["distance", "similarity", "neighbor_rank"]
        keep_cols = [c for c in keep_cols if c in neighbors.columns]
        neighbors_out = neighbors.loc[:, keep_cols]

        export_df(neighbors_out, out_dir / args.neighbors_file)

        summary = summarize_neighbors(neighbors, horizons=horizons)
        summary["mode"] = "single_candle"
        summary["query_index"] = int(query_idx)
        if date_col:
            summary["query_date"] = str(df.iloc[query_idx][date_col])
        summary["metric"] = args.metric
        summary["standardize"] = bool(args.standardize)
        summary["features"] = features
        export_json(summary, out_dir / args.neighbors_summary)

    else:
        seq_neighbors = top_k_neighbors_sequence(
            df=df,
            X=X,
            query_start_index=query_idx,
            seq_len=args.seq_len,
            top_k=args.top_k,
            standardize=args.standardize,
            metric=args.metric,
            similarity_map=args.similarity_map,
            exclude_window=args.exclude_window,
        )
        seq_neighbors = attach_sequence_outcomes(
            df=df,
            seq_df=seq_neighbors,
            seq_len=args.seq_len,
            horizons=horizons,
            date_col=date_col,
        )
        export_df(seq_neighbors, out_dir / args.neighbors_file)

        # summary on sequence neighbors (anchored outcomes are in seq_neighbors now)
        summary = summarize_neighbors(seq_neighbors, horizons=horizons)
        summary["mode"] = "sequence"
        summary["seq_len"] = int(args.seq_len)
        summary["query_start_index"] = int(query_idx)
        if date_col:
            summary["query_start_date"] = str(df.iloc[query_idx][date_col])
            summary["query_end_date"] = str(df.iloc[query_idx + args.seq_len - 1][date_col])
        summary["metric"] = args.metric
        summary["standardize"] = bool(args.standardize)
        summary["features"] = features
        export_json(summary, out_dir / args.neighbors_summary)

    # Clustering
    if args.do_cluster:
        if not SKLEARN_OK:
            raise RuntimeError("scikit-learn not available; cannot cluster.")
        labels, coords, info = cluster_candles(
            X=X,
            standardize=True,  # clustering almost always should standardize
            n_components=args.cluster_components,
            n_clusters=args.clusters,
        )

        cluster_df = df.copy()
        cluster_df["cluster"] = labels.astype(int)
        if coords is not None:
            for i in range(coords.shape[1]):
                cluster_df[f"pca_{i+1}"] = coords[:, i]
        export_df(cluster_df, out_dir / args.cluster_file)

        cluster_table = summarize_clusters(df=df, labels=labels, horizons=horizons)
        export_df(cluster_table, out_dir / args.cluster_table)

        info["features"] = features
        export_json(info, out_dir / args.cluster_summary)


if __name__ == "__main__":
    main()
