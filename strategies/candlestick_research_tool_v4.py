#!/usr/bin/env python3
"""
candlestick_research_tool_v4.py

Interval similarity search with:
- Query by date range [--start, --end] where the key column is a date such as `date`
- Similarity-first selection across the full candidate universe
- Optional time constraint (max gap days) as a secondary filter
- No forced output: if no matches pass min similarity, returns empty result + report stating so
- HTML report with client-side sorting + filtering (no external JS deps)

Key changes vs v3:
- Similarity is defined as a scaled exponential kernel, which behaves well in high dimensions:

    similarity = exp( - distance / tau )

  where tau is a scale parameter. Default tau is the median distance of candidates.
  With this definition:
    - similarity is in (0,1]
    - similarity=0.5 means: distance <= tau * ln(2)

Distance metrics:
- euclidean (default)
- cosine
- mahalanobis (ridge-stabilized covariance inverse)

Past-only ("live") mode:
- enabled when --train-window > 0
- candidates are restricted to intervals ending strictly before query start
- and starting within the last N rows before query start

Outputs:
- interval_matches.csv  (all matches passing filters, sorted)
- meta.json
- report.html (interactive)

Cum rulezi
Research (tot istoricul)
python candlestick_research_tool_v4.py \
  --input out.csv \
  --key-col date \
  --start 2026-02-05 \
  --end 2026-02-10 \
  --standardize \
  --metric euclidean \
  --min-sim 0.50 \
  --out-dir research_out_v4

Live-mode (doar trecutul, fără look-ahead)
python candlestick_research_tool_v4.py \
  --input out.csv \
  --key-col date \
  --start 2017-08-17 \
  --end 2017-08-25 \
  --standardize \
  --metric euclidean \
  --train-window 800 \
  --min-train 300 \
  --min-sim 0.50 \
  --out-dir research_out_v4_live

Opțional: limitezi și timpul (dar secundar)
  --max-gap-days 365

Dacă 0.50 e prea strict
Nu îți “inventez” rezultate. Dacă nu apar match-uri:
încearcă --min-sim 0.35 (de obicei e un prag bun inițial în spații de dimensiune mare cu exp-kernel)
sau schimbă --tau p75 (face similaritățile mai “îngăduitoare”)
sau --metric cosine (uneori mai stabil pe pattern-uri relative)

UI în report.html (ce ai cerut)
În report.html ai:
input Min similarity
input Max gap days
input Show up to
butoane: sortare după similarity / gap / distance
overlay charts pentru top N după similarity

Output files:
interval_matches.csv
meta.json (include tau_value, match_count, etc.)
report.html

"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
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


# ----------------------------
# Standardization
# ----------------------------

@dataclass(frozen=True)
class Standardizer:
    """z-score: X' = (X - mean) / std"""
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
# Metrics
# ----------------------------

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


# ----------------------------
# Similarity mapping
# ----------------------------

def compute_tau(dist: np.ndarray, tau_mode: str) -> float:
    """
    Scale parameter for similarity kernel.

    tau_mode:
      - "median": tau = median(dist)
      - "p75":    tau = 75th percentile of dist
      - "p50":    same as median
      - numeric string: tau = float(tau_mode)

    Returns tau>0.
    """
    tau_mode = tau_mode.strip().lower()
    if tau_mode in ("median", "p50"):
        tau = float(np.nanmedian(dist))
    elif tau_mode == "p75":
        tau = float(np.nanpercentile(dist, 75))
    else:
        tau = float(tau_mode)

    if not np.isfinite(tau) or tau <= 0:
        raise ValueError(f"Invalid tau computed from tau_mode={tau_mode}: {tau}")
    return tau

def dist_to_similarity_exp(dist: np.ndarray, tau: float) -> np.ndarray:
    """
    similarity = exp(-dist / tau)

    Properties:
      - sim in (0,1]
      - sim=0.5 <=> dist = tau * ln(2)
    """
    return np.exp(-dist / tau)


# ----------------------------
# Matrix construction
# ----------------------------

def build_X(df: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    return df.loc[:, list(features)].to_numpy(dtype=float)

def build_sequence_matrix(X: np.ndarray, seq_len: int) -> np.ndarray:
    n, d = X.shape
    if seq_len <= 0:
        raise ValueError("seq_len must be >= 1")
    if n < seq_len:
        raise ValueError("Not enough rows for seq_len.")
    S = np.empty((n - seq_len + 1, d * seq_len), dtype=float)
    for i in range(n - seq_len + 1):
        S[i, :] = X[i:i + seq_len].reshape(-1)
    return S


# ----------------------------
# Date handling
# ----------------------------

def ensure_date_col(df: pd.DataFrame, key_col: str) -> pd.DataFrame:
    out = df.copy()
    out[key_col] = pd.to_datetime(out[key_col], errors="coerce")
    if out[key_col].isna().any():
        bad = out[out[key_col].isna()].head(5)
        raise ValueError(f"Some values in {key_col} could not be parsed as dates. Example rows:\n{bad}")
    return out

def locate_range_indices_fuzzy(df: pd.DataFrame, key_col: str, start: str, end: str) -> Tuple[int, int]:
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


# ----------------------------
# Candidate filtering
# ----------------------------

def exclude_overlaps(candidate_starts: np.ndarray, q_start: int, q_end: int, seq_len: int, exclude_window: int) -> np.ndarray:
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


# ----------------------------
# Outcomes
# ----------------------------

def outcome_cols(horizons: Sequence[int]) -> List[str]:
    cols: List[str] = []
    for k in horizons:
        cols += [f"fwd_logret_{k}", f"mfe_{k}", f"mae_{k}"]
    return cols

def attach_interval_outcomes(df: pd.DataFrame, intervals: pd.DataFrame, horizons: Sequence[int]) -> pd.DataFrame:
    out = intervals.copy()
    end_idx = out["cand_end_index"].to_numpy(dtype=int)
    for c in outcome_cols(horizons):
        if c in df.columns:
            out[c] = df.iloc[end_idx][c].to_numpy()
    return out

def summarize_outcomes(table: pd.DataFrame, horizons: Sequence[int]) -> Dict[str, object]:
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


# ----------------------------
# HTML report (interactive)
# ----------------------------

def _plot_overlay_png_base64(query_close: np.ndarray, cand_close: np.ndarray, title: str) -> str:
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
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def write_html_report(
    path: Path,
    meta: Dict[str, object],
    outcome_summary: Dict[str, object],
    query_slice: pd.DataFrame,
    matches: pd.DataFrame,
    df: pd.DataFrame,
    key_col: str,
    price_col: str,
    horizons: Sequence[int],
    chart_top_n: int = 30,
    match_extra_points: int = 3,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def df_to_html(df_: pd.DataFrame, max_rows: int = 200) -> str:
        return df_.head(max_rows).to_html(index=False, escape=False)

    base_cols = ["cand_start_index", "cand_end_index", "start_ts", "end_ts", "time_gap_days", "distance", "similarity"]
    keep_cols = base_cols + [c for c in outcome_cols(horizons) if c in matches.columns]
    keep_cols = [c for c in keep_cols if c in matches.columns]

    # JS for sorting + filtering
    js = r"""
    function parseFloatSafe(x){ const v=parseFloat(x); return isNaN(v) ? null : v; }
    function parseIntSafe(x){ const v=parseInt(x); return isNaN(v) ? null : v; }

    function applyFilters(){
      const minSim = parseFloatSafe(document.getElementById('minSim').value);
      const maxGap = parseIntSafe(document.getElementById('maxGap').value);
      const maxRows = parseIntSafe(document.getElementById('maxRows').value);

      const table = document.getElementById('matchesTable');
      const rows = Array.from(table.tBodies[0].rows);

      let shown = 0;
      for (const r of rows){
        const sim = parseFloatSafe(r.dataset.sim);
        const gap = parseIntSafe(r.dataset.gap);

        let ok = true;
        if (minSim !== null && sim !== null) ok = ok && (sim >= minSim);
        if (maxGap !== null && gap !== null) ok = ok && (gap <= maxGap);

        if (ok && (maxRows === null || shown < maxRows)){
          r.style.display = '';
          shown += 1;
        } else {
          r.style.display = 'none';
        }
      }
      document.getElementById('shownCount').innerText = shown.toString();
    }

    function sortTable(col, numeric=true, desc=true){
      const table = document.getElementById('matchesTable');
      const tbody = table.tBodies[0];
      const rows = Array.from(tbody.rows);

      rows.sort((a,b)=>{
        const av = a.dataset[col];
        const bv = b.dataset[col];

        if (numeric){
          const an = parseFloatSafe(av);
          const bn = parseFloatSafe(bv);
          if (an === null && bn === null) return 0;
          if (an === null) return 1;
          if (bn === null) return -1;
          return desc ? (bn - an) : (an - bn);
        } else {
          if (av === bv) return 0;
          return desc ? (bv.localeCompare(av)) : (av.localeCompare(bv));
        }
      });

      for (const r of rows) tbody.appendChild(r);
      applyFilters();
    }
    """

    html: List[str] = []
    html.append("<html><head><meta charset='utf-8'><title>Candlestick Interval Research Report</title>")
    html.append(
        "<style>"
        "body{font-family:Arial, sans-serif; padding:16px;}"
        "table{border-collapse:collapse; font-size:12px; width:100%;}"
        "td,th{border:1px solid #ccc; padding:4px 6px;}"
        "h2{margin-top:28px;}"
        ".grid{display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start;}"
        ".card{border:1px solid #ddd; border-radius:8px; padding:12px;}"
        ".small{font-size:12px; color:#444;}"
        ".controls{display:flex; gap:12px; align-items:center; flex-wrap:wrap;}"
        "input{padding:4px 6px;}"
        "button{padding:6px 10px; cursor:pointer;}"
        "</style>"
    )
    html.append("</head><body>")
    html.append("<h1>Candlestick Interval Research Report</h1>")

    html.append("<div class='grid'>")
    html.append("<div class='card'><h2 style='margin-top:0;'>Meta</h2>")
    html.append("<pre class='small'>" + json.dumps(meta, ensure_ascii=False, indent=2) + "</pre></div>")
    html.append("<div class='card'><h2 style='margin-top:0;'>Matches outcomes summary</h2>")
    html.append("<pre class='small'>" + json.dumps(outcome_summary, ensure_ascii=False, indent=2) + "</pre></div>")
    html.append("</div>")

    html.append("<h2>Query interval candles</h2>")
    # show date + close only to keep readable
    qcols = [key_col, price_col]
    qcols = [c for c in qcols if c in query_slice.columns]
    html.append(df_to_html(query_slice[qcols], max_rows=600))

    html.append("<h2>Matches (interactive table)</h2>")
    html.append("<div class='controls small'>"
                "Min similarity: <input id='minSim' type='number' step='0.01' value='0.50' oninput='applyFilters()'/> "
                "Max gap days: <input id='maxGap' type='number' step='1' value='' placeholder='(none)' oninput='applyFilters()'/> "
                "Show up to: <input id='maxRows' type='number' step='1' value='200' oninput='applyFilters()'/> "
                "<button onclick=\"sortTable('sim', true, true)\">Sort sim ↓</button>"
                "<button onclick=\"sortTable('gap', true, false)\">Sort gap ↑</button>"
                "<button onclick=\"sortTable('dist', true, false)\">Sort dist ↑</button>"
                "Shown: <span id='shownCount'>0</span>"
                "</div>")

    if len(matches) == 0:
        html.append("<div class='card small'>No matches passed the filters used during generation.</div>")
    else:
        # Build custom table so we can embed data-* attributes
        html.append("<table id='matchesTable'><thead><tr>")
        for c in keep_cols:
            html.append(f"<th>{c}</th>")
        html.append("</tr></thead><tbody>")

        for _, row in matches.iterrows():
            gap = int(row["time_gap_days"])
            dist = float(row["distance"])
            sim = float(row["similarity"])
            html.append(f"<tr data-gap='{gap}' data-dist='{dist:.10f}' data-sim='{sim:.10f}'>")
            for c in keep_cols:
                v = row.get(c, "")
                if isinstance(v, float):
                    html.append(f"<td>{v:.6f}</td>")
                else:
                    html.append(f"<td>{v}</td>")
            html.append("</tr>")
        html.append("</tbody></table>")

    # Overlay charts (top by similarity)
    html.append("<h2>Top matches overlays (normalized closes)</h2>")
    html.append("<div class='small'>Charts are sorted by similarity descending.</div>")

    if len(matches) > 0:
        query_close = query_slice[price_col].to_numpy(dtype=float)
        top = matches.sort_values("similarity", ascending=False).head(chart_top_n)

        for _, row in top.iterrows():
            s = int(row["cand_start_index"])
            e = int(row["cand_end_index"])

            e_ext = min(len(df) - 1, e + match_extra_points)
            match_close = df.iloc[s:e_ext + 1][price_col].to_numpy(dtype=float)

            title = (
                f"sim={float(row['similarity']):.3f} dist={float(row['distance']):.3f} gap_days={int(row['time_gap_days'])} "
                f"({row['start_ts']} → {row['end_ts']}, +{e_ext - e} extra)"
            )

            b64 = _plot_overlay_png_base64(query_close, match_close, title=title)
            html.append("<div class='card' style='margin-top:12px;'>")
            html.append(f"<div class='small'>{title}</div>")
            html.append(f"<img src='data:image/png;base64,{b64}'/>")
            html.append("</div>")

    html.append(f"<script>{js}\napplyFilters();</script>")
    html.append("</body></html>")
    path.write_text("\n".join(html), encoding="utf-8")


# ----------------------------
# Main
# ----------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Interval similarity search (similarity-first, optional time constraints).")

    p.add_argument("--input", required=True, type=Path, help="out.csv (must include date + close + features)")
    p.add_argument("--key-col", required=True, help="date column name, e.g. date")
    p.add_argument("--price-col", default="close", help="price column for overlays")
    p.add_argument("--features", default=",".join(DEFAULT_FEATURES), help="comma-separated feature columns")
    p.add_argument("--horizons", default="1,3,5,7,10", help="comma-separated horizons")

    p.add_argument("--start", required=True, help="query interval start date (YYYY-MM-DD)")
    p.add_argument("--end", required=True, help="query interval end date (YYYY-MM-DD)")

    # Similarity
    p.add_argument("--standardize", action="store_true", help="z-score candidate vectors before distance")
    p.add_argument("--metric", choices=["euclidean", "cosine", "mahalanobis"], default="euclidean")

    p.add_argument("--tau", default="median", help="similarity scale tau: median|p75|<number>")
    p.add_argument("--min-sim", type=float, default=0.50, help="minimum similarity in [0,1]. No forcing: may return none.")
    p.add_argument("--max-gap-days", type=int, default=0, help="0 = no time filter; else keep only intervals with time_gap_days <= this")

    # Candidate universe / live mode
    p.add_argument("--train-window", type=int, default=0, help="0 = all history (research). >0 = past-only using last N rows before query_start")
    p.add_argument("--min-train", type=int, default=300, help="min history rows before query_start (past-only)")
    p.add_argument("--exclude-window", type=int, default=10, help="exclude overlaps and +/- start window near query")

    # Output control
    p.add_argument("--out-dir", default="research_out_interval_v4", help="output directory")
    p.add_argument("--chart-top-n", type=int, default=30, help="overlay charts count (top by similarity)")

    args = p.parse_args()

    df = pd.read_csv(args.input)
    df = ensure_date_col(df, args.key_col)
    df = df.sort_values(args.key_col).reset_index(drop=True)

    if args.price_col not in df.columns:
        raise ValueError(f"--price-col '{args.price_col}' not found in input.")

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
        # candidates must end before query_start
        max_start = q_start - seq_len
        candidate_starts = candidate_starts[candidate_starts <= max_start]
        # restrict to last N rows before query_start
        train_start_row = max(0, q_start - args.train_window)
        candidate_starts = candidate_starts[candidate_starts >= train_start_row]

    candidate_starts = exclude_overlaps(candidate_starts, q_start=q_start, q_end=q_end, seq_len=seq_len, exclude_window=args.exclude_window)
    if len(candidate_starts) == 0:
        raise ValueError("No candidates left after filtering. Reduce exclude window or adjust date range.")

    cand_end = candidate_starts + (seq_len - 1)

    # Prepare candidate matrix
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

    # Similarity kernel
    tau = compute_tau(dist, args.tau)
    sim = dist_to_similarity_exp(dist, tau=tau)

    # Time gap
    query_end_ts = df.loc[q_end, args.key_col]
    end_ts = df.loc[cand_end, args.key_col].to_numpy()
    time_gap_days = np.array([day_gap(pd.Timestamp(t), pd.Timestamp(query_end_ts)) for t in end_ts], dtype=int)

    # Build table
    neighbors = pd.DataFrame({
        "cand_start_index": candidate_starts,
        "cand_end_index": cand_end,
        "start_ts": df.loc[candidate_starts, args.key_col].astype("datetime64[ns]").astype(str).to_numpy(),
        "end_ts": df.loc[cand_end, args.key_col].astype("datetime64[ns]").astype(str).to_numpy(),
        "time_gap_days": time_gap_days,
        "distance": dist,
        "similarity": sim,
    })

    # Filters: similarity-first
    matches = neighbors[neighbors["similarity"] >= float(args.min_sim)].copy()
    if args.max_gap_days and args.max_gap_days > 0:
        matches = matches[matches["time_gap_days"] <= int(args.max_gap_days)].copy()

    # Sort: similarity desc first, then time gap asc
    matches = matches.sort_values(["similarity", "time_gap_days"], ascending=[False, True]).reset_index(drop=True)

    # Attach outcomes
    matches = attach_interval_outcomes(df, matches, horizons=horizons)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    matches.to_csv(out_dir / "interval_matches.csv", index=False)

    meta = {
        "query_start_index": int(q_start),
        "query_end_index": int(q_end),
        "query_start_ts": str(df.loc[q_start, args.key_col].date()),
        "query_end_ts": str(df.loc[q_end, args.key_col].date()),
        "seq_len": int(seq_len),
        "metric": args.metric,
        "standardize": bool(args.standardize),
        "tau_mode": str(args.tau),
        "tau_value": float(tau),
        "min_sim": float(args.min_sim),
        "max_gap_days": int(args.max_gap_days),
        "past_only": bool(past_only),
        "train_window": int(args.train_window),
        "min_train": int(args.min_train),
        "exclude_window": int(args.exclude_window),
        "candidate_count": int(len(neighbors)),
        "match_count": int(len(matches)),
        "similarity_definition": "similarity = exp(-distance/tau), tau from tau_mode over candidate distances",
        "note": "If match_count==0, reduce --min-sim (e.g., 0.35) or change metric/tau/standardize.",
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    outcome_summary = summarize_outcomes(matches, horizons=horizons)

    query_slice = df.iloc[q_start:q_end + 1].copy()
    write_html_report(
        path=out_dir / "report.html",
        meta=meta,
        outcome_summary=outcome_summary,
        query_slice=query_slice,
        matches=matches,
        df=df,
        key_col=args.key_col,
        price_col=args.price_col,
        horizons=horizons,
        chart_top_n=args.chart_top_n,
    )


if __name__ == "__main__":
    main()
