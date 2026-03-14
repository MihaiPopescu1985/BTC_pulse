#!/usr/bin/env python3
"""
candlestick_research_tool_v3.py

Interval-based candlestick research:
- Query by [start_date, end_date] where timestamp format is "YYYY-MM-DD".
- Finds the most temporally-near intervals AND most similar (pattern-wise).
- No need for --top-k: auto-selects "best" candidates in the nearest time neighborhood.
- Generates:
    - interval_neighbors.csv
    - meta.json
    - report.html (improved: summary + overlay charts for top matches)

Core idea:
- Represent an interval of length L as a vector in R^(d*L) by concatenating candle feature vectors.
- Compute distances between query interval vector and each candidate interval vector.
- Sort by (time_gap_days, distance) and auto-select within a time slack and distance quantile cutoff.

Distance metrics:
- Euclidean (default)
- Cosine
- Mahalanobis (uses covariance inverse; ridge-stabilized)

Standardization:
- z-score on the candidate universe (recommended).

"Closest in time":
- Uses absolute day gap between candidate END date and query END date.

Past-only (live) mode:
- Enabled when --train-window > 0
- Candidate intervals are restricted to those ending strictly before query_start
  and (optionally) to the last N rows before query_start.

Utilizare
# Research (poate include și viitor – util pentru explorare)
python candlestick_research_tool_v3.py \
  --input out.csv \
  --key-col timestamp \
  --start 2017-08-17 \
  --end 2017-08-25 \
  --standardize \
  --metric euclidean \
  --out-dir research_out_interval

# “Live mode” (doar trecutul, fără look-ahead)
# Setezi --train-window (ex: 800 zile istorice înainte de interval):
python candlestick_research_tool_v3.py \
  --input out.csv \
  --key-col timestamp \
  --start 2017-08-17 \
  --end 2017-08-25 \
  --standardize \
  --metric euclidean \
  --train-window 800 \
  --min-train 300 \
  --out-dir research_out_interval_live

Cum interpretezi interval_neighbors.csv (esential)
time_gap_days: cât de aproape e intervalul în timp față de intervalul tău (mai mic = mai aproape)
distance: cât de similar e pattern-ul (mai mic = mai similar)
similarity: scor monoton (mai mare = mai similar)
fwd_logret_k / mfe_k / mae_k: outcomes după finalul intervalului

Dacă vrei să împingi și mai departe “closest in time” (și să fie și mai strict), scazi:
--time-slack-days (ex: 7)
și/sau crești strictness pe distanță:
--distance-quantile (ex: 0.10)
"""

from __future__ import annotations

import argparse
import base64
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


DEFAULT_FEATURES = [
    "pct_range_size",
    "pct_net_move",
    "pct_upper_shadow_size",
    "pct_lower_shadow_size",
    "frac_upper_shadow",
    "frac_lower_shadow",
    "frac_body",
    "direction_sign",
]


@dataclass(frozen=True)
class Standardizer:
    """
    z-score standardization

    Math:
        X' = (X - mean) / std
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


def euclidean_dist(X: np.ndarray, q: np.ndarray) -> np.ndarray:
    diff = X - q.reshape(1, -1)
    return np.sqrt(np.sum(diff * diff, axis=1))


def cosine_dist(X: np.ndarray, q: np.ndarray) -> np.ndarray:
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    qn = q / (np.linalg.norm(q) + 1e-12)
    cos = (Xn @ qn.reshape(-1, 1)).reshape(-1)
    return 1.0 - cos


def fit_precision(X: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    cov = np.cov(X, rowvar=False)
    cov = cov + ridge * np.eye(cov.shape[0])
    return np.linalg.inv(cov)


def mahalanobis_dist(X: np.ndarray, q: np.ndarray, precision: np.ndarray) -> np.ndarray:
    diff = X - q.reshape(1, -1)
    v = diff @ precision
    return np.sqrt(np.sum(v * diff, axis=1))


def compute_distances(X: np.ndarray, q: np.ndarray, metric: str, precision: Optional[np.ndarray]) -> np.ndarray:
    metric = metric.lower()
    if metric == "euclidean":
        return euclidean_dist(X, q)
    if metric == "cosine":
        return cosine_dist(X, q)
    if metric == "mahalanobis":
        if precision is None:
            raise ValueError("precision required for mahalanobis")
        return mahalanobis_dist(X, q, precision)
    raise ValueError(f"Unknown metric: {metric}")


def dist_to_similarity(d: np.ndarray, method: str = "inv") -> np.ndarray:
    """
    Map distance -> similarity in (0, 1].

    inv:
        sim = 1 / (1 + d)
    exp:
        sim = exp(-d)
    """
    method = method.lower()
    if method == "inv":
        return 1.0 / (1.0 + d)
    if method == "exp":
        return np.exp(-d)
    raise ValueError(f"Unknown similarity map: {method}")


def build_X(df: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    return df.loc[:, list(features)].to_numpy(dtype=float)


def build_sequence_matrix(X: np.ndarray, seq_len: int) -> np.ndarray:
    """
    Concatenate candle feature vectors across seq_len consecutive rows.

    If X is (n, d) then S is (n-seq_len+1, d*seq_len) with:
        S[i] = [X[i] | X[i+1] | ... | X[i+seq_len-1]]
    """
    n, d = X.shape
    if seq_len <= 0:
        raise ValueError("seq_len must be >= 1")
    if n < seq_len:
        raise ValueError("Not enough rows for seq_len.")
    S = np.empty((n - seq_len + 1, d * seq_len), dtype=float)
    for i in range(n - seq_len + 1):
        S[i, :] = X[i:i + seq_len].reshape(-1)
    return S


def ensure_date_col(df: pd.DataFrame, key_col: str) -> pd.DataFrame:
    """
    Parse key_col as pandas datetime (expects YYYY-MM-DD strings).
    """
    out = df.copy()
    out[key_col] = pd.to_datetime(out[key_col], errors="coerce")
    if out[key_col].isna().any():
        bad = out[out[key_col].isna()].head(5)
        raise ValueError(f"Some values in {key_col} could not be parsed as dates. Example rows:\n{bad}")
    return out


def locate_range_indices_fuzzy(df: pd.DataFrame, key_col: str, start: str, end: str) -> Tuple[int, int]:
    """
    Inclusive fuzzy selection:
      - start_idx = first row with date >= start
      - end_idx   = last row with date <= end
    """
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    if end_dt < start_dt:
        raise ValueError("End date is before start date.")

    dates = df[key_col]
    start_candidates = df.index[dates >= start_dt].to_list()
    end_candidates = df.index[dates <= end_dt].to_list()

    if not start_candidates:
        raise ValueError(f"No rows with {key_col} >= {start}.")
    if not end_candidates:
        raise ValueError(f"No rows with {key_col} <= {end}.")

    i0 = int(start_candidates[0])
    i1 = int(end_candidates[-1])
    if i1 < i0:
        raise ValueError("After fuzzy matching, end index is before start index.")
    return i0, i1


def day_gap(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return int(abs((a - b).days))


def exclude_overlaps(candidate_starts: np.ndarray, q_start: int, q_end: int, seq_len: int, exclude_window: int) -> np.ndarray:
    """
    Exclude:
      - start indices within +/- exclude_window around q_start
      - any candidate interval overlapping query interval
    """
    keep = np.ones_like(candidate_starts, dtype=bool)

    if exclude_window > 0:
        lo = max(0, q_start - exclude_window)
        hi = q_start + exclude_window
        keep &= ~((candidate_starts >= lo) & (candidate_starts <= hi))

    c_start = candidate_starts
    c_end = candidate_starts + (seq_len - 1)
    overlap = ~((c_end < q_start) | (c_start > q_end))
    keep &= ~overlap

    return candidate_starts[keep]


def auto_select(nei: pd.DataFrame, time_slack_days: int, distance_quantile: float, max_results: int) -> pd.DataFrame:
    """
    No top-k selection.

    Steps:
      1) best_gap = min(time_gap_days)
      2) keep within time window: gap <= best_gap + time_slack_days
      3) within that window keep best distances: distance <= quantile(distance, distance_quantile)
      4) cap by max_results
    """
    if len(nei) == 0:
        return nei

    best_gap = int(nei["time_gap_days"].min())
    window = nei[nei["time_gap_days"] <= best_gap + time_slack_days].copy()
    if len(window) == 0:
        return window

    cutoff = float(window["distance"].quantile(distance_quantile))
    window = window[window["distance"] <= cutoff].copy()
    window = window.sort_values(["time_gap_days", "distance"]).head(max_results).reset_index(drop=True)

    window["neighbor_rank"] = np.arange(1, len(window) + 1)
    window["best_gap_days"] = best_gap
    window["distance_cutoff"] = cutoff
    return window


def outcome_cols(horizons: Sequence[int]) -> List[str]:
    cols: List[str] = []
    for k in horizons:
        cols += [f"fwd_logret_{k}", f"mfe_{k}", f"mae_{k}"]
    return cols


def attach_interval_outcomes(df: pd.DataFrame, intervals: pd.DataFrame, horizons: Sequence[int]) -> pd.DataFrame:
    """
    Outcomes anchored at interval end index:
      interval end = cand_end_index
    """
    out = intervals.copy()
    end_idx = out["cand_end_index"].to_numpy(dtype=int)
    for c in outcome_cols(horizons):
        if c in df.columns:
            out[c] = df.iloc[end_idx][c].to_numpy()
    return out


def summarize_outcomes(table: pd.DataFrame, horizons: Sequence[int]) -> Dict[str, object]:
    """
    Summaries for selected intervals.

    For each k:
      - mean/median fwd_logret_k
      - winrate P(fwd_logret_k > 0)
      - median mfe_k
      - median mae_k
    """
    s: Dict[str, object] = {"n": int(len(table))}
    if len(table) == 0:
        return s

    s["similarity_min"] = float(np.nanmin(table["similarity"]))
    s["similarity_median"] = float(np.nanmedian(table["similarity"]))
    s["similarity_max"] = float(np.nanmax(table["similarity"]))

    for k in horizons:
        r = table.get(f"fwd_logret_{k}")
        if r is None:
            continue
        rv = r.to_numpy(dtype=float)
        mf = table.get(f"mfe_{k}")
        ma = table.get(f"mae_{k}")
        mfv = mf.to_numpy(dtype=float) if mf is not None else np.full_like(rv, np.nan)
        mav = ma.to_numpy(dtype=float) if ma is not None else np.full_like(rv, np.nan)

        s[f"h{k}"] = {
            "logret_mean": float(np.nanmean(rv)),
            "logret_median": float(np.nanmedian(rv)),
            "winrate": float(np.nanmean(rv > 0)),
            "mfe_median": float(np.nanmedian(mfv)),
            "mae_median": float(np.nanmedian(mav)),
        }
    return s


def _plot_overlay_png_base64(query_close: np.ndarray, cand_close: np.ndarray, title: str) -> str:
    """
    Create a small overlay plot as PNG base64.

    Normalization:
      both series are divided by their first value, so they start at 1.0
    """
    import matplotlib.pyplot as plt

    q = query_close.astype(float)
    c = cand_close.astype(float)
    q = q / (q[0] if q[0] != 0 else 1.0)
    c = c / (c[0] if c[0] != 0 else 1.0)

    fig = plt.figure(figsize=(5.2, 2.2), dpi=140)
    ax = fig.add_subplot(111)
    ax.plot(q, linewidth=1.6, label="query")
    ax.plot(c, linewidth=1.2, label="match")
    ax.set_title(title, fontsize=9)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, loc="best")
    ax.tick_params(axis="both", labelsize=7)

    buf = io.BytesIO()
    fig.tight_layout(pad=0.6)
    fig.savefig(buf, format="png")
    import matplotlib.pyplot as plt2
    plt2.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def write_html_report(
    path: Path,
    meta: Dict[str, object],
    outcome_summary: Dict[str, object],
    query_slice: pd.DataFrame,
    selected: pd.DataFrame,
    df: pd.DataFrame,
    key_col: str,
    price_col: str,
    features: Sequence[str],
    horizons: Sequence[int],
    chart_top_n: int = 30,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def df_to_html(df_: pd.DataFrame, max_rows: int = 200) -> str:
        return df_.head(max_rows).to_html(index=False, escape=False)

    q_keep = [key_col, price_col] + list(features)
    q_keep = [c for c in q_keep if c in query_slice.columns]

    base_cols = ["cand_start_index", "cand_end_index", "start_ts", "end_ts", "time_gap_days", "distance", "similarity", "neighbor_rank"]
    keep_cols = base_cols + [c for c in outcome_cols(horizons) if c in selected.columns]
    keep_cols = [c for c in keep_cols if c in selected.columns]

    html: List[str] = []
    html.append("<html><head><meta charset='utf-8'><title>Candlestick Interval Research Report</title>")
    html.append(
        "<style>"
        "body{font-family:Arial, sans-serif; padding:16px;}"
        "table{border-collapse:collapse; font-size:12px;}"
        "td,th{border:1px solid #ccc; padding:4px 6px;}"
        "h2{margin-top:28px;}"
        ".grid{display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start;}"
        ".card{border:1px solid #ddd; border-radius:8px; padding:12px;}"
        ".small{font-size:12px; color:#444;}"
        "</style>"
    )
    html.append("</head><body>")
    html.append("<h1>Candlestick Interval Research Report</h1>")

    html.append("<div class='grid'>")
    html.append("<div class='card'><h2 style='margin-top:0;'>Meta</h2>")
    html.append("<pre class='small'>" + json.dumps(meta, ensure_ascii=False, indent=2) + "</pre></div>")
    html.append("<div class='card'><h2 style='margin-top:0;'>Neighbor outcomes summary</h2>")
    html.append("<pre class='small'>" + json.dumps(outcome_summary, ensure_ascii=False, indent=2) + "</pre></div>")
    html.append("</div>")

    html.append("<h2>Query interval candles</h2>")
    html.append(df_to_html(query_slice[q_keep], max_rows=600))

    html.append("<h2>Selected similar intervals (table)</h2>")
    html.append(df_to_html(selected[keep_cols], max_rows=400))

    html.append("<h2>Top matches overlays (normalized closes)</h2>")
    html.append("<div class='small'>Each chart normalizes both query and match closes to start at 1.0.</div>")

    query_close = query_slice[price_col].to_numpy(dtype=float)

    shown = min(chart_top_n, len(selected))
    for i in range(shown):
        row = selected.iloc[i]
        s = int(row["cand_start_index"])
        e = int(row["cand_end_index"])
        match_close = df.iloc[s:e + 1][price_col].to_numpy(dtype=float)
        title = (
            f"rank={int(row['neighbor_rank'])} gap_days={int(row['time_gap_days'])} "
            f"dist={row['distance']:.4f} sim={row['similarity']:.3f} "
            f"({row['start_ts']} → {row['end_ts']})"
        )
        b64 = _plot_overlay_png_base64(query_close, match_close, title=title)
        html.append("<div class='card' style='margin-top:12px;'>")
        html.append(f"<div class='small'>{title}</div>")
        html.append(f"<img src='data:image/png;base64,{b64}'/>")
        html.append("</div>")

    html.append("</body></html>")
    path.write_text("\n".join(html), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Interval similarity search: closest in time + most similar pattern.")

    p.add_argument("--input", required=True, type=Path, help="out.csv (features/outcomes + timestamp + close)")
    p.add_argument("--key-col", required=True, help="date column name, e.g. timestamp (YYYY-MM-DD)")
    p.add_argument("--price-col", default="close", help="price column for overlays (default: close)")
    p.add_argument("--features", default=",".join(DEFAULT_FEATURES), help="comma-separated feature columns")
    p.add_argument("--horizons", default="1,3,5,7,10", help="comma-separated horizons")

    p.add_argument("--start", required=True, help="query interval start date (YYYY-MM-DD)")
    p.add_argument("--end", required=True, help="query interval end date (YYYY-MM-DD)")

    p.add_argument("--standardize", action="store_true", help="z-score candidate vectors before distance")
    p.add_argument("--metric", choices=["euclidean", "cosine", "mahalanobis"], default="euclidean")
    p.add_argument("--similarity-map", choices=["inv", "exp"], default="inv")

    p.add_argument("--train-window", type=int, default=0, help="0 = research (all history). >0 = past-only using last N rows before query_start")
    p.add_argument("--min-train", type=int, default=300, help="min history rows before query_start (past-only)")
    p.add_argument("--exclude-window", type=int, default=10, help="exclude overlaps and +/- start window near query")

    p.add_argument("--time-slack-days", type=int, default=30, help="keep intervals within best_gap + slack days")
    p.add_argument("--distance-quantile", type=float, default=0.20, help="keep best distances within time window (0.20=best 20%)")
    p.add_argument("--max-results", type=int, default=200, help="cap results")
    p.add_argument("--chart-top-n", type=int, default=30, help="how many overlay charts to embed in report")

    p.add_argument("--out-dir", default="research_out_interval", help="output directory")

    args = p.parse_args()

    df = pd.read_csv(args.input)
    df = ensure_date_col(df, args.key_col)
    df = df.sort_values(args.key_col).reset_index(drop=True)

    if args.price_col not in df.columns:
        raise ValueError(f"--price-col '{args.price_col}' not found. Columns start: {list(df.columns)[:30]} ...")

    features = [c.strip() for c in args.features.split(",") if c.strip()]
    missing = [c for c in features if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns in input: {missing}")

    horizons = sorted(set(int(x.strip()) for x in args.horizons.split(",") if x.strip()))

    q_start, q_end = locate_range_indices_fuzzy(df, args.key_col, args.start, args.end)
    seq_len = q_end - q_start + 1

    X = build_X(df, features)
    S = build_sequence_matrix(X, seq_len=seq_len)
    q_vec = S[q_start].copy()

    n_seq = len(S)
    candidate_starts = np.arange(n_seq, dtype=int)

    past_only = args.train_window > 0
    if past_only:
        if q_start < args.min_train:
            raise ValueError(f"Not enough history before query_start. Need >= {args.min_train} rows.")
        max_start = q_start - seq_len
        candidate_starts = candidate_starts[candidate_starts <= max_start]
        train_start_row = max(0, q_start - args.train_window)
        candidate_starts = candidate_starts[candidate_starts >= train_start_row]

    candidate_starts = exclude_overlaps(
        candidate_starts,
        q_start=q_start,
        q_end=q_end,
        seq_len=seq_len,
        exclude_window=args.exclude_window,
    )

    if len(candidate_starts) == 0:
        raise ValueError("No candidates left after filtering. Reduce exclude window or adjust date range.")

    S_cand = S[candidate_starts].copy()

    precision = None
    if args.standardize:
        scaler = Standardizer.fit(S_cand)
        S_cand_use = scaler.transform(S_cand)
        q_use = scaler.transform(q_vec.reshape(1, -1)).reshape(-1)
        if args.metric == "mahalanobis":
            precision = fit_precision(S_cand_use)
    else:
        S_cand_use = S_cand
        q_use = q_vec
        if args.metric == "mahalanobis":
            precision = fit_precision(S_cand_use)

    dist = compute_distances(S_cand_use, q_use, metric=args.metric, precision=precision)

    cand_end = candidate_starts + (seq_len - 1)
    query_end_ts = df.loc[q_end, args.key_col]

    start_ts = df.loc[candidate_starts, args.key_col].to_numpy()
    end_ts = df.loc[cand_end, args.key_col].to_numpy()
    time_gap_days = np.array([day_gap(pd.Timestamp(t), pd.Timestamp(query_end_ts)) for t in end_ts], dtype=int)

    neighbors = pd.DataFrame({
        "cand_start_index": candidate_starts,
        "cand_end_index": cand_end,
        "start_ts": start_ts.astype("datetime64[ns]").astype(str),
        "end_ts": end_ts.astype("datetime64[ns]").astype(str),
        "time_gap_days": time_gap_days,
        "distance": dist,
    })
    neighbors["similarity"] = dist_to_similarity(neighbors["distance"].to_numpy(), method=args.similarity_map)
    neighbors = neighbors.sort_values(["time_gap_days", "distance"]).reset_index(drop=True)

    selected = auto_select(
        neighbors,
        time_slack_days=args.time_slack_days,
        distance_quantile=args.distance_quantile,
        max_results=args.max_results,
    )
    selected = attach_interval_outcomes(df, selected, horizons=horizons)

    meta = {
        "query_start_index": int(q_start),
        "query_end_index": int(q_end),
        "query_start_ts": str(df.loc[q_start, args.key_col].date()),
        "query_end_ts": str(df.loc[q_end, args.key_col].date()),
        "seq_len": int(seq_len),
        "features": features,
        "metric": args.metric,
        "standardize": bool(args.standardize),
        "similarity_map": args.similarity_map,
        "past_only": bool(past_only),
        "train_window": int(args.train_window),
        "min_train": int(args.min_train),
        "exclude_window": int(args.exclude_window),
        "time_slack_days": int(args.time_slack_days),
        "distance_quantile": float(args.distance_quantile),
        "max_results": int(args.max_results),
        "selected_n": int(len(selected)),
        "best_gap_days": int(selected["best_gap_days"].iloc[0]) if len(selected) else None,
        "distance_cutoff": float(selected["distance_cutoff"].iloc[0]) if len(selected) else None,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected.to_csv(out_dir / "interval_neighbors.csv", index=False)
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    outcome_summary = summarize_outcomes(selected, horizons=horizons)

    query_slice = df.iloc[q_start:q_end + 1].copy()
    write_html_report(
        path=out_dir / "report.html",
        meta=meta,
        outcome_summary=outcome_summary,
        query_slice=query_slice,
        selected=selected,
        df=df,
        key_col=args.key_col,
        price_col=args.price_col,
        features=features,
        horizons=horizons,
        chart_top_n=args.chart_top_n,
    )


if __name__ == "__main__":
    main()
