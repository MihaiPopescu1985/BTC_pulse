#!/usr/bin/env python3
"""
safe_interpreter_v1.py

SAFE 3.0 market interpreter.

Inputs:
  - features.csv
  - onchain_features.csv

Outputs:
  - interpreter_report.json
  - interpreter_report.html
  - interpreter_report.md

What it does:
  1. Loads and merges SAFE features with on-chain features by date.
  2. Interprets the latest market state with rule-based summaries.
  3. Finds historical analogs using:
       - recent candle sequence similarity
       - weighted indicator-state similarity
       - regime-conditioned similarity
  4. Summarizes what usually happened next after similar states.
  5. Runs simple price-shock scenarios to see how the reading changes.

This script targets the current SAFE 3.0 CSV export format:
  - features.csv: date-first wide feature table
  - onchain_features.csv: date-first wide on-chain feature table

The scenario engine is approximate by design.
It recomputes a subset of price-derived features from the available history,
while keeping on-chain features and model outputs unchanged.

python safe_interpreter_v2.py \
  --features features.csv \
  --onchain onchain_features.csv \
  --out-dir safe_interpreter_out
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from html import escape
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import DEFAULT_FEATURES_CSV_PATH, DEFAULT_ONCHAIN_FEATURES_CSV_PATH, OUT_DIR


DEFAULT_GROUPS: Dict[str, List[str]] = {
    "trend": [
        "R_3", "R_7", "R_14",
        "TS_20", "TS_50", "TS_200",
        "LR_20", "LR_50", "LR_200",
        "ER_20", "ER_50", "ER_200",
        "RVR_20", "RVR_50", "RVR_200",
    ],
    "volatility": [
        "vol_20", "atr_pct", "parkinson_vol", "garman_klass_vol", "ewma_vol",
        "upside_semi_vol", "downside_semi_vol", "band_w",
    ],
    "position": [
        "band_pos", "dist_from_mean_vol_units", "time_since_local_high", "time_since_local_low",
    ],
    "candle": [
        "body_to_range_ratio", "upper_wick_ratio", "lower_wick_ratio", "close_in_range",
        "run_length_up", "run_length_down", "run_magnitude_up", "run_magnitude_down", "return_accel",
    ],
    "participation": ["relative_volume_20", "volume_z"],
    "regime": [
        "P_CORE_HMM", "P_DRIFT_HMM", "P_SHOCK_HMM", "P_SURGE_HMM",
        "P_CORRECTION_10D_CAL", "P_REBOUND_10D_CAL",
        "direction_safe", "E_target_safe", "L_target_safe",
        "conviction_safe", "D_score_safe", "hard_risk_off_flag_safe",
    ],
    "onchain": [
        "ONCHAIN_VOL_Z", "ONCHAIN_DOM_Z", "ONCHAIN_WHALE_SHARE_Z",
        "ONCHAIN_AMOUNT_PCT", "ONCHAIN_WHALE_TX_PCT", "ONCHAIN_DOM_PCT",
    ],
}

DEFAULT_WEIGHTS: Dict[str, float] = {
    "trend": 0.30,
    "volatility": 0.15,
    "position": 0.15,
    "candle": 0.10,
    "participation": 0.10,
    "regime": 0.15,
    "onchain": 0.05,
}

CANDLE_SEQUENCE_FEATURES = [
    "pct_range_size",
    "pct_net_move",
    "pct_upper_shadow_size",
    "pct_lower_shadow_size",
    "frac_upper_shadow",
    "frac_lower_shadow",
    "frac_body",
    "direction_sign",
]

DATE_CANDIDATES = ["timestamp", "date", "Date", "time"]


USED_TERMS_GLOSSARY: dict[str, str] = {
    "CORE": "Neutral or balanced regime with limited directional pressure.",
    "DRIFT": "Orderly upward regime with moderate stress.",
    "SHOCK": "Stress regime where downside damage dominates.",
    "SURGE": "Strong upside expansion regime with more energy.",
    "Participation": "How much volume and activity confirm the move.",
    "Trend repair": "Whether damaged trend structure is improving.",
    "Trend damage": "How weak the structure still looks versus history.",
    "Risk balance": "Whether downside or upside risk currently dominates.",
    "Upside asymmetry": "When rebound odds outweigh correction odds.",
    "Analogs": "Past market setups that looked similar to today.",
    "Touch map": "How often analogs hit upside or downside levels first.",
    "Reliability": "How tight and coherent the analog evidence is.",
}

@dataclass
class AnalogMatch:
    end_index: int
    end_date: str
    distance: float
    similarity: float
    forward_stats: Dict[str, Any]
    regime_label: Optional[str] = None


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and not x.strip():
            return None
        v = float(x)
        if math.isfinite(v):
            return v
        return None
    except Exception:
        return None


def _pick_date_col(df: pd.DataFrame) -> str:
    for c in DATE_CANDIDATES:
        if c in df.columns:
            return c
    raise ValueError(f"Could not identify date column. Tried: {DATE_CANDIDATES}")



def load_csv_rows(path: Path) -> pd.DataFrame:
    """Load a SAFE CSV export into a dataframe."""
    return load_feature_csv(path)


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    date_col = _pick_date_col(df)
    if date_col != "date":
        df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="raise").dt.strftime("%Y-%m-%d")

    for c in df.columns:
        if c == "date" or c == "HMM_LABEL":
            continue
        try:
            df[c] = pd.to_numeric(df[c])
        except Exception:
            pass
    return df.sort_values("date").reset_index(drop=True)


def merge_inputs(features_path: Path, onchain_path: Path) -> pd.DataFrame:
    features = normalize_df(load_csv_rows(features_path))
    onchain = normalize_df(load_csv_rows(onchain_path))

    # Avoid duplicate date columns after merge and prefer feature-side values.
    shared = [c for c in onchain.columns if c in features.columns and c != "date"]
    if shared:
        onchain = onchain.drop(columns=shared)

    merged = features.merge(onchain, on="date", how="left")
    return merged.sort_values("date").reset_index(drop=True)


def validate_ranges(df: pd.DataFrame) -> None:
    """Light sanity checks for bounded indicators."""
    bounded_01 = [
        "band_pos", "upper_wick_ratio", "lower_wick_ratio",
        "close_in_range", "P_CORE_HMM", "P_DRIFT_HMM", "P_SHOCK_HMM", "P_SURGE_HMM",
        "P_CORRECTION_10D_CAL", "P_REBOUND_10D_CAL", "conviction_safe",
    ]
    bounded_pm1 = ["body_to_range_ratio"]
    hard_flags = ["hard_risk_off_flag_safe"]
    for col in bounded_01:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        bad = (~s.between(-1e-9, 1 + 1e-9)).sum()
        if bad:
            raise ValueError(f"Column {col} contains {int(bad)} values outside [0, 1]")
    for col in bounded_pm1:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        bad = (~s.between(-1 - 1e-9, 1 + 1e-9)).sum()
        if bad:
            raise ValueError(f"Column {col} contains {int(bad)} values outside [-1, 1]")
    for col in hard_flags:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        bad = (~s.isin([0, 1])).sum()
        if bad:
            raise ValueError(f"Column {col} contains {int(bad)} values outside {{0, 1}}")
    for price_col in ["open", "high", "low", "close"]:
        if price_col in df.columns:
            s = pd.to_numeric(df[price_col], errors="coerce").dropna()
            if (s <= 0).any():
                raise ValueError(f"Column {price_col} contains non-positive values")



def ensure_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    required_raw = {"open", "high", "low", "close"}
    if not required_raw.issubset(df.columns):
        return df

    o = pd.to_numeric(df["open"], errors="coerce")
    h = pd.to_numeric(df["high"], errors="coerce")
    l = pd.to_numeric(df["low"], errors="coerce")
    c = pd.to_numeric(df["close"], errors="coerce")

    prev_c = c.shift(1)
    eps = 1e-12
    candle_range = (h - l).replace(0, np.nan)
    base = prev_c.abs().replace(0, np.nan)

    computed = {
        "pct_range_size": (h - l) / (base + eps),
        "pct_net_move": (c - o) / (base + eps),
        "pct_upper_shadow_size": (h - np.maximum(o, c)) / (base + eps),
        "pct_lower_shadow_size": (np.minimum(o, c) - l) / (base + eps),
        "frac_upper_shadow": (h - np.maximum(o, c)) / (candle_range + eps),
        "frac_lower_shadow": (np.minimum(o, c) - l) / (candle_range + eps),
        "frac_body": (c - o).abs() / (candle_range + eps),
        "direction_sign": np.sign(c - o),
    }
    for k, v in computed.items():
        if k not in df.columns:
            df[k] = v
    return df


def z_distance(train_df: pd.DataFrame, query: pd.Series, cols: Sequence[str]) -> Optional[np.ndarray]:
    cols = [c for c in cols if c in train_df.columns and c in query.index]
    if not cols:
        return None
    X = train_df[cols].apply(pd.to_numeric, errors="coerce")
    q = pd.to_numeric(query[cols], errors="coerce")

    valid_cols = []
    for c in cols:
        if np.isfinite(q[c]) and X[c].notna().sum() >= max(30, min(10, len(X))):
            valid_cols.append(c)
    if not valid_cols:
        return None

    X = X[valid_cols]
    q = q[valid_cols]
    mu = X.mean(axis=0)
    sigma = X.std(axis=0, ddof=0).replace(0, np.nan)
    Xz = (X - mu) / sigma
    qz = (q - mu) / sigma
    mask = Xz.notna() & qz.notna()
    diff2 = ((Xz - qz) ** 2).where(mask)
    used = mask.sum(axis=1)
    dist = np.sqrt(diff2.sum(axis=1) / used.replace(0, np.nan))
    return dist.to_numpy(dtype=float)


def weighted_state_distance(
    train_df: pd.DataFrame,
    query: pd.Series,
    groups: Dict[str, List[str]],
    weights: Dict[str, float],
) -> np.ndarray:
    parts = []
    wsum = 0.0
    for name, cols in groups.items():
        d = z_distance(train_df, query, cols)
        w = weights.get(name, 0.0)
        if d is None or w <= 0:
            continue
        parts.append((w, d))
        wsum += w
    if not parts or wsum <= 0:
        raise ValueError("No valid feature groups available for state similarity")

    out = np.zeros(len(train_df), dtype=float)
    valid_weight = np.zeros(len(train_df), dtype=float)
    for w, d in parts:
        mask = np.isfinite(d)
        out[mask] += w * d[mask]
        valid_weight[mask] += w

    out = np.where(valid_weight > 0, out / valid_weight, np.nan)
    return out


def exp_similarity(dist: np.ndarray, tau_mode: str = "median") -> np.ndarray:
    finite = dist[np.isfinite(dist)]
    if len(finite) == 0:
        return np.full_like(dist, np.nan, dtype=float)
    if tau_mode == "p75":
        tau = float(np.nanpercentile(finite, 75))
    else:
        tau = float(np.nanmedian(finite))
    if not np.isfinite(tau) or tau <= 0:
        tau = max(float(np.nanmean(finite)), 1e-6)
    return np.exp(-dist / tau)


def compute_forward_stats(df: pd.DataFrame, idx: int, horizons: Sequence[int], touch_pct: Sequence[float]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"returns": {}, "touches": {}}
    if "close" not in df.columns:
        return out

    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(df["high"], errors="coerce").to_numpy(dtype=float) if "high" in df.columns else None
    low = pd.to_numeric(df["low"], errors="coerce").to_numpy(dtype=float) if "low" in df.columns else None
    anchor = close[idx]
    if not np.isfinite(anchor) or anchor <= 0:
        return out

    for h in horizons:
        j = idx + h
        if j < len(close) and np.isfinite(close[j]):
            r = close[j] / anchor - 1.0
            out["returns"][str(h)] = float(r)

    if high is not None and low is not None:
        for pct in touch_pct:
            up = anchor * (1.0 + pct)
            dn = anchor * (1.0 - pct)
            first = None
            max_h = max(horizons) if horizons else 10
            for j in range(idx + 1, min(len(close), idx + max_h + 1)):
                hit_up = np.isfinite(high[j]) and high[j] >= up
                hit_dn = np.isfinite(low[j]) and low[j] <= dn
                if hit_up and hit_dn:
                    first = "both_same_bar"
                    break
                if hit_up:
                    first = "up"
                    break
                if hit_dn:
                    first = "down"
                    break
            out["touches"][f"{int(round(pct*100))}%"] = first or "none"
    return out


def summarize_forward(matches: List[AnalogMatch], horizons: Sequence[int], touch_pct: Sequence[float]) -> Dict[str, Any]:
    returns_summary: Dict[str, Any] = {}
    touches_summary: Dict[str, Any] = {}

    for h in horizons:
        vals = [m.forward_stats.get("returns", {}).get(str(h)) for m in matches]
        vals = [v for v in vals if v is not None and np.isfinite(v)]
        if vals:
            returns_summary[str(h)] = {
                "count": len(vals),
                "median": float(np.median(vals)),
                "mean": float(np.mean(vals)),
                "win_rate": float(np.mean(np.array(vals) > 0)),
                "p25": float(np.percentile(vals, 25)),
                "p75": float(np.percentile(vals, 75)),
            }

    for pct in touch_pct:
        key = f"{int(round(pct*100))}%"
        vals = [m.forward_stats.get("touches", {}).get(key) for m in matches]
        vals = [v for v in vals if v]
        if vals:
            counts = pd.Series(vals).value_counts(dropna=False).to_dict()
            total = sum(counts.values())
            touches_summary[key] = {k: float(v / total) for k, v in counts.items()}

    return {
        "match_count": len(matches),
        "returns": returns_summary,
        "touches": touches_summary,
    }


def _select_reference_horizon(summary: Dict[str, Any]) -> Optional[str]:
    for horizon in ("10", "5", "20", "3"):
        if horizon in summary.get("returns", {}):
            return horizon
    return None


def classify_analog_reliability(matches: List[AnalogMatch], summary: Dict[str, Any]) -> Dict[str, Any]:
    if not matches:
        return {"score": "low", "note": "No close analogs were available."}

    ref_horizon = _select_reference_horizon(summary)
    similarities = [m.similarity for m in matches[:5] if np.isfinite(m.similarity)]
    top_similarity_mean = float(np.mean(similarities)) if similarities else 0.0

    dispersion = None
    win_rate = None
    if ref_horizon is not None:
        ref_stats = summary.get("returns", {}).get(ref_horizon, {})
        p25 = ref_stats.get("p25")
        p75 = ref_stats.get("p75")
        win_rate = ref_stats.get("win_rate")
        if p25 is not None and p75 is not None:
            dispersion = float(p75 - p25)

    if len(matches) >= 12 and top_similarity_mean >= 0.60 and (dispersion is None or dispersion <= 0.08):
        score = "high"
        note = "Many close analogs cluster tightly and their forward paths are relatively coherent."
    elif len(matches) < 6 or top_similarity_mean < 0.35 or (dispersion is not None and dispersion >= 0.18):
        score = "low"
        note = "Analog evidence is sparse, loose, or forward outcomes are widely dispersed."
    else:
        score = "medium"
        note = "Analog evidence is usable, but similarity concentration or forward agreement is only moderate."

    if win_rate is not None and 0.40 <= win_rate <= 0.60:
        note += " Directional follow-through is mixed rather than one-sided."

    return {
        "score": score,
        "note": note,
        "top_similarity_mean": top_similarity_mean,
        "reference_horizon": ref_horizon,
        "forward_dispersion": dispersion,
    }


def enrich_analog_summary(matches: List[AnalogMatch], summary: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(summary)
    reliability = classify_analog_reliability(matches, enriched)
    enriched["reliability"] = reliability["score"]
    enriched["reliability_note"] = reliability["note"]
    enriched["top_similarity_mean"] = reliability.get("top_similarity_mean")
    if reliability.get("reference_horizon") is not None:
        enriched["reference_horizon"] = reliability["reference_horizon"]
    if reliability.get("forward_dispersion") is not None:
        enriched["forward_dispersion"] = reliability["forward_dispersion"]
    return enriched


def regime_label(row: pd.Series) -> str:
    if "HMM_LABEL" in row and isinstance(row["HMM_LABEL"], str) and row["HMM_LABEL"].strip():
        return row["HMM_LABEL"].strip().upper()
    pairs = [("CORE", row.get("P_CORE_HMM")), ("DRIFT", row.get("P_DRIFT_HMM")), ("SHOCK", row.get("P_SHOCK_HMM")), ("SURGE", row.get("P_SURGE_HMM"))]
    scored = [(name, _to_float(v)) for name, v in pairs if _to_float(v) is not None]
    if not scored:
        return "UNKNOWN"
    return max(scored, key=lambda x: x[1])[0]


def find_state_analogs(
    df: pd.DataFrame,
    query_idx: int,
    groups: Dict[str, List[str]],
    weights: Dict[str, float],
    top_k: int,
    min_gap: int,
    horizons: Sequence[int],
    touch_pct: Sequence[float],
    regime_filter: Optional[str] = None,
) -> Tuple[List[AnalogMatch], Dict[str, Any]]:
    query = df.iloc[query_idx]
    train = df.iloc[:query_idx].copy()
    if regime_filter:
        train = train[train.apply(regime_label, axis=1) == regime_filter].copy()

    if len(train) == 0:
        return [], {"match_count": 0}

    dist = weighted_state_distance(train, query, groups, weights)
    sim = exp_similarity(dist)

    train = train.reset_index().rename(columns={"index": "orig_index"})
    train["distance"] = dist
    train["similarity"] = sim
    train = train[np.isfinite(train["distance"])].copy()
    train = train[(query_idx - train["orig_index"]) >= min_gap].copy()
    train = train.sort_values(["distance", "orig_index"]).head(top_k)

    matches: List[AnalogMatch] = []
    for _, row in train.iterrows():
        idx = int(row["orig_index"])
        matches.append(
            AnalogMatch(
                end_index=idx,
                end_date=str(df.iloc[idx]["date"]),
                distance=float(row["distance"]),
                similarity=float(row["similarity"]),
                forward_stats=compute_forward_stats(df, idx, horizons, touch_pct),
                regime_label=regime_label(df.iloc[idx]),
            )
        )

    return matches, summarize_forward(matches, horizons, touch_pct)


def find_candle_sequence_analogs(
    df: pd.DataFrame,
    query_idx: int,
    seq_len: int,
    top_k: int,
    min_gap: int,
    horizons: Sequence[int],
    touch_pct: Sequence[float],
) -> Tuple[List[AnalogMatch], Dict[str, Any]]:
    df = ensure_candle_features(df)
    cols = [c for c in CANDLE_SEQUENCE_FEATURES if c in df.columns]
    if len(cols) == 0 or query_idx < seq_len:
        return [], {"match_count": 0}

    base = df[cols].apply(pd.to_numeric, errors="coerce")
    query_window = base.iloc[query_idx - seq_len + 1: query_idx + 1]
    if len(query_window) != seq_len or query_window.isna().all().all():
        return [], {"match_count": 0}

    train_end_idxs = []
    rows = []
    for end_idx in range(seq_len - 1, query_idx - min_gap):
        window = base.iloc[end_idx - seq_len + 1: end_idx + 1]
        if len(window) != seq_len:
            continue
        rows.append(window.to_numpy(dtype=float).reshape(-1))
        train_end_idxs.append(end_idx)

    if not rows:
        return [], {"match_count": 0}

    X = np.vstack(rows)
    q = query_window.to_numpy(dtype=float).reshape(-1)
    mu = np.nanmean(X, axis=0)
    sigma = np.nanstd(X, axis=0)
    sigma = np.where(sigma == 0, 1.0, sigma)
    Xz = (X - mu) / sigma
    qz = (q - mu) / sigma
    dist = np.sqrt(np.nanmean((Xz - qz.reshape(1, -1)) ** 2, axis=1))
    sim = exp_similarity(dist)

    order = np.argsort(dist)[:top_k]
    matches: List[AnalogMatch] = []
    for i in order:
        idx = train_end_idxs[i]
        matches.append(
            AnalogMatch(
                end_index=idx,
                end_date=str(df.iloc[idx]["date"]),
                distance=float(dist[i]),
                similarity=float(sim[i]),
                forward_stats=compute_forward_stats(df, idx, horizons, touch_pct),
                regime_label=regime_label(df.iloc[idx]),
            )
        )
    return matches, summarize_forward(matches, horizons, touch_pct)


CALIBRATION_COLUMNS: tuple[str, ...] = (
    "R_3", "R_7", "R_14",
    "TS_20", "TS_50", "TS_200",
    "LR_20", "LR_50", "LR_200",
    "ER_20", "ER_50", "ER_200",
    "RVR_20", "RVR_50", "RVR_200",
    "vol_20", "atr_pct", "parkinson_vol", "garman_klass_vol", "ewma_vol",
    "upside_semi_vol", "downside_semi_vol", "band_w",
    "band_pos", "dist_from_mean_vol_units", "time_since_local_high", "time_since_local_low",
    "body_to_range_ratio", "upper_wick_ratio", "lower_wick_ratio", "close_in_range",
    "run_length_up", "run_length_down", "run_magnitude_up", "run_magnitude_down", "return_accel",
    "relative_volume_20", "volume_z",
    "P_CORE_HMM", "P_DRIFT_HMM", "P_SHOCK_HMM", "P_SURGE_HMM",
    "HMM_CONF", "HMM_DOM",
    "P_CORRECTION_10D_CAL", "P_REBOUND_10D_CAL",
    "direction_safe", "E_target_safe", "L_target_safe", "conviction_safe", "D_score_safe", "hard_risk_off_flag_safe",
    "ONCHAIN_VOL_Z", "ONCHAIN_DOM_Z", "ONCHAIN_WHALE_SHARE_Z", "ONCHAIN_AMOUNT_PCT", "ONCHAIN_WHALE_TX_PCT", "ONCHAIN_DOM_PCT",
)
MIN_CALIBRATION_COUNT = 30
MIN_REGIME_CALIBRATION_ROWS = 50
CALIBRATION_PERCENTILES: tuple[float, ...] = (0.05, 0.10, 0.20, 0.33, 0.50, 0.67, 0.80, 0.90, 0.95)


def _finite_numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    series = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return series.astype(float)


def _distribution_summary(series: pd.Series) -> Optional[Dict[str, Any]]:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_CALIBRATION_COUNT:
        return None
    values = np.sort(clean.to_numpy(dtype=float))
    q = np.quantile(values, CALIBRATION_PERCENTILES)
    return {
        "count": int(len(values)),
        "median": float(np.median(values)),
        "iqr": float(np.quantile(values, 0.75) - np.quantile(values, 0.25)),
        "percentiles": {str(int(p * 100)): float(v) for p, v in zip(CALIBRATION_PERCENTILES, q)},
        "sorted_values": values,
    }


def safe_percentile_rank(series: Sequence[float] | pd.Series | np.ndarray, value: Any) -> float:
    numeric_value = _to_float(value)
    if numeric_value is None:
        return float("nan")
    arr = pd.to_numeric(pd.Series(series), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if arr.size == 0:
        return float("nan")
    arr = np.sort(arr)
    rank = np.searchsorted(arr, numeric_value, side="right") / len(arr)
    return float(rank)


def _rank_from_stats(stats: Optional[Dict[str, Any]], value: Any) -> Optional[float]:
    numeric_value = _to_float(value)
    if numeric_value is None or not stats:
        return None
    values = stats.get("sorted_values")
    if values is None or len(values) == 0:
        return None
    rank = np.searchsorted(values, numeric_value, side="right") / len(values)
    return float(rank)


def bucket_from_percentile(percentile: Optional[float]) -> str:
    if percentile is None or not np.isfinite(percentile):
        return "unknown"
    if percentile <= 0.05:
        return "historically extreme low"
    if percentile <= 0.10:
        return "bottom decile"
    if percentile <= 0.20:
        return "bottom quintile"
    if percentile <= 0.33:
        return "below typical"
    if percentile <= 0.67:
        return "near median"
    if percentile <= 0.80:
        return "above typical"
    if percentile <= 0.90:
        return "top quintile"
    if percentile <= 0.95:
        return "top decile"
    return "historically extreme high"


def compare_to_history(value: Any, stats: Optional[Dict[str, Any]]) -> str:
    return bucket_from_percentile(_rank_from_stats(stats, value))


def compare_to_regime_history(value: Any, regime_stats: Optional[Dict[str, Any]]) -> str:
    if not regime_stats:
        return "no regime baseline"
    return bucket_from_percentile(_rank_from_stats(regime_stats, value))


def build_calibration_context(df: pd.DataFrame) -> Dict[str, Any]:
    calibration_frame = df.copy()
    calibration_frame["_dominant_regime_for_interp"] = calibration_frame.apply(regime_label, axis=1)

    context: Dict[str, Any] = {
        "global": {},
        "by_regime": {},
        "regime_counts": calibration_frame["_dominant_regime_for_interp"].value_counts(dropna=False).to_dict(),
    }

    for column in CALIBRATION_COLUMNS:
        if column not in calibration_frame.columns:
            continue
        stats = _distribution_summary(_finite_numeric_series(calibration_frame, column))
        if stats is not None:
            context["global"][column] = stats

    for regime, group in calibration_frame.groupby("_dominant_regime_for_interp"):
        if len(group) < MIN_REGIME_CALIBRATION_ROWS:
            continue
        regime_stats: Dict[str, Dict[str, Any]] = {}
        for column in CALIBRATION_COLUMNS:
            if column not in group.columns:
                continue
            stats = _distribution_summary(_finite_numeric_series(group, column))
            if stats is not None:
                regime_stats[column] = stats
        if regime_stats:
            context["by_regime"][str(regime)] = regime_stats
    return context


def percentile_view(row: pd.Series, calibration_context: Dict[str, Any], column: str) -> Dict[str, Any]:
    value = _to_float(row.get(column))
    regime = regime_label(row)
    global_stats = calibration_context.get("global", {}).get(column)
    regime_stats = calibration_context.get("by_regime", {}).get(regime, {}).get(column)
    global_percentile = _rank_from_stats(global_stats, value)
    regime_percentile = _rank_from_stats(regime_stats, value)
    effective_percentile = regime_percentile if regime_percentile is not None else global_percentile
    return {
        "value": value,
        "global_percentile": global_percentile,
        "regime_percentile": regime_percentile,
        "effective_percentile": effective_percentile,
        "history_label": compare_to_history(value, global_stats),
        "regime_label": compare_to_regime_history(value, regime_stats),
    }


def _score_percentile(row: pd.Series, calibration_context: Dict[str, Any], column: str) -> float:
    view = percentile_view(row, calibration_context, column)
    percentile = view["effective_percentile"]
    if percentile is None or not np.isfinite(percentile):
        return 0.5
    return float(percentile)


def _combine_score(parts: Sequence[Optional[float]], default: float = 0.5) -> float:
    values = [float(part) for part in parts if part is not None and np.isfinite(part)]
    if not values:
        return float(default)
    return float(np.clip(np.mean(values), 0.0, 1.0))


def compute_soft_scores(row: pd.Series, calibration_context: Dict[str, Any]) -> Dict[str, float]:
    percentile = lambda column: _score_percentile(row, calibration_context, column)
    hard_risk_off = 1.0 if (_to_float(row.get("hard_risk_off_flag_safe")) or 0.0) >= 0.5 else 0.0

    trend_damage = _combine_score([
        1.0 - percentile("TS_50"),
        1.0 - percentile("TS_200"),
        1.0 - percentile("LR_50"),
        1.0 - percentile("LR_200"),
        1.0 - percentile("ER_20"),
        1.0 - percentile("RVR_50"),
        1.0 - percentile("band_pos"),
        percentile("time_since_local_high"),
    ])
    trend_repair = _combine_score([
        percentile("R_3"),
        percentile("R_7"),
        percentile("TS_20"),
        percentile("LR_20"),
        percentile("ER_20"),
        percentile("band_pos"),
        percentile("close_in_range"),
        1.0 - percentile("time_since_local_low"),
    ])
    participation = _combine_score([
        percentile("relative_volume_20"),
        percentile("volume_z"),
        percentile("ONCHAIN_VOL_Z"),
        percentile("ONCHAIN_DOM_Z"),
        percentile("ONCHAIN_WHALE_SHARE_Z"),
    ])
    stress = max(hard_risk_off, _combine_score([
        percentile("P_SHOCK_HMM"),
        percentile("P_CORRECTION_10D_CAL"),
        percentile("downside_semi_vol"),
        percentile("atr_pct"),
        percentile("vol_20"),
        1.0 - percentile("close_in_range"),
        1.0 - percentile("band_pos"),
    ]))
    calm = _combine_score([
        1.0 - percentile("P_SHOCK_HMM"),
        percentile("P_CORE_HMM"),
        1.0 - percentile("atr_pct"),
        1.0 - percentile("vol_20"),
        1.0 - percentile("band_w"),
    ])
    stretch_up = _combine_score([
        percentile("band_pos"),
        percentile("dist_from_mean_vol_units"),
        percentile("close_in_range"),
        1.0 - percentile("time_since_local_high"),
    ])
    stretch_down = _combine_score([
        1.0 - percentile("band_pos"),
        1.0 - percentile("dist_from_mean_vol_units"),
        1.0 - percentile("close_in_range"),
        1.0 - percentile("time_since_local_low"),
    ])
    downside_asymmetry = _combine_score([
        percentile("P_CORRECTION_10D_CAL"),
        1.0 - percentile("P_REBOUND_10D_CAL"),
    ])
    upside_asymmetry = _combine_score([
        percentile("P_REBOUND_10D_CAL"),
        1.0 - percentile("P_CORRECTION_10D_CAL"),
    ])
    directional_asymmetry = float(downside_asymmetry - upside_asymmetry)

    return {
        "trend_damage_score": trend_damage,
        "trend_repair_score": trend_repair,
        "participation_score": participation,
        "stress_score": stress,
        "calm_score": calm,
        "stretch_up_score": stretch_up,
        "stretch_down_score": stretch_down,
        "downside_asymmetry_score": downside_asymmetry,
        "upside_asymmetry_score": upside_asymmetry,
        "directional_asymmetry_score": directional_asymmetry,
    }


def _regime_adjustment_note(row: pd.Series, calibration_context: Dict[str, Any], column: str, label: str) -> Optional[str]:
    view = percentile_view(row, calibration_context, column)
    global_percentile = view["global_percentile"]
    regime_percentile = view["regime_percentile"]
    if global_percentile is None or regime_percentile is None:
        return None
    if abs(global_percentile - regime_percentile) < 0.15:
        return None
    regime = regime_label(row)
    if regime_percentile > global_percentile:
        return f"{label} looks stronger inside {regime} than it does versus full history."
    return f"{label} looks softer inside {regime} than it does versus full history."


def build_historical_context(row: pd.Series, calibration_context: Dict[str, Any], scores: Dict[str, float]) -> Tuple[Dict[str, Any], str]:
    trend_view = percentile_view(row, calibration_context, "TS_50")
    participation_view = percentile_view(row, calibration_context, "relative_volume_20")
    correction_view = percentile_view(row, calibration_context, "P_CORRECTION_10D_CAL")
    band_view = percentile_view(row, calibration_context, "band_pos")

    context = {
        "trend_vs_history": trend_view["history_label"],
        "trend_vs_regime": trend_view["regime_label"],
        "participation_vs_history": participation_view["history_label"],
        "participation_vs_regime": participation_view["regime_label"],
        "correction_vs_history": correction_view["history_label"],
        "correction_vs_regime": correction_view["regime_label"],
        "position_vs_history": band_view["history_label"],
        "position_vs_regime": band_view["regime_label"],
    }

    notes: List[str] = []
    if scores["trend_damage_score"] >= 0.70:
        notes.append("Trend damage remains meaningful relative to past observations.")
    elif scores["trend_repair_score"] >= 0.65 and scores["trend_damage_score"] >= 0.50:
        notes.append("Trend repair is improving, but still below typical constructive conditions.")
    elif scores["trend_repair_score"] >= 0.70:
        notes.append("Trend repair is stronger than typical and increasingly constructive.")

    if scores["participation_score"] <= 0.40:
        notes.append("Participation is below typical for this market's history.")
    elif scores["participation_score"] >= 0.65:
        notes.append("Participation is stronger than typical for recent history.")

    if scores["downside_asymmetry_score"] >= 0.65:
        notes.append("Downside asymmetry is present relative to its own history.")
    elif scores["upside_asymmetry_score"] >= 0.65:
        notes.append("Upside asymmetry is present relative to its own history.")

    for adjustment in [
        _regime_adjustment_note(row, calibration_context, "relative_volume_20", "Participation"),
        _regime_adjustment_note(row, calibration_context, "P_CORRECTION_10D_CAL", "Correction risk"),
        _regime_adjustment_note(row, calibration_context, "band_pos", "Positioning"),
    ]:
        if adjustment:
            notes.append(adjustment)

    if not notes:
        notes.append("Current readings sit near their own historical middle rather than at extreme levels.")

    return context, " ".join(dict.fromkeys(notes))


def bucket_trend(latest: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(latest, calibration_context)
    if scores["trend_damage_score"] >= 0.82 and scores["trend_repair_score"] <= 0.40:
        return "deeply damaged"
    if scores["trend_damage_score"] >= 0.65 and scores["trend_repair_score"] <= 0.50:
        return "damaged"
    if scores["trend_repair_score"] >= 0.72 and scores["trend_damage_score"] <= 0.40:
        return "constructive"
    if scores["trend_repair_score"] >= 0.60 and scores["trend_damage_score"] >= 0.50:
        return "improving"
    if scores["trend_damage_score"] >= 0.55:
        return "mildly weak"
    return "mixed"


def bucket_volatility(latest: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(latest, calibration_context)
    band_width_view = percentile_view(latest, calibration_context, "band_w")
    if scores["stress_score"] >= 0.75:
        return "stressed"
    if scores["calm_score"] >= 0.70:
        return "calm"
    if band_width_view["effective_percentile"] is not None and band_width_view["effective_percentile"] <= 0.20:
        return "compressed"
    return "active"


def bucket_participation(latest: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(latest, calibration_context)
    if scores["participation_score"] >= 0.70:
        return "confirmed"
    if scores["participation_score"] >= 0.58:
        return "supportive"
    if scores["participation_score"] <= 0.35:
        return "thin"
    if scores["participation_score"] <= 0.45:
        return "below typical"
    return "typical"


def bucket_position(latest: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(latest, calibration_context)
    if scores["stretch_up_score"] >= 0.72:
        return "upside stretched"
    if scores["stretch_down_score"] >= 0.72:
        return "downside stretched"
    band_width_view = percentile_view(latest, calibration_context, "band_w")
    if band_width_view["effective_percentile"] is not None and band_width_view["effective_percentile"] <= 0.20:
        return "compressed mid-range"
    return "balanced"


def bucket_risk(latest: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(latest, calibration_context)
    hard_risk_off = (_to_float(latest.get("hard_risk_off_flag_safe")) or 0.0) >= 0.5
    if hard_risk_off or scores["stress_score"] >= 0.88:
        return "risk_off"
    if scores["directional_asymmetry_score"] >= 0.18 and scores["stress_score"] >= 0.60:
        return "downside_risk_elevated"
    if scores["directional_asymmetry_score"] <= -0.18 and scores["trend_repair_score"] >= 0.50:
        return "rebound_potential_elevated"
    return "balanced"


def classify_regime_context(row: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    regime = regime_label(row)
    shock_view = percentile_view(row, calibration_context, "P_SHOCK_HMM")
    drift_view = percentile_view(row, calibration_context, "P_DRIFT_HMM")
    surge_view = percentile_view(row, calibration_context, "P_SURGE_HMM")
    core_view = percentile_view(row, calibration_context, "P_CORE_HMM")

    if regime == "SHOCK" and (shock_view["effective_percentile"] or 0.5) >= 0.67:
        return "shock-like and historically elevated"
    if regime == "SURGE" and (surge_view["effective_percentile"] or 0.5) >= 0.67:
        return "surge-like and historically strong"
    if regime == "DRIFT" and (drift_view["effective_percentile"] or 0.5) >= 0.50:
        return "drift-like and orderly"
    if regime == "CORE" and (core_view["effective_percentile"] or 0.5) >= 0.50:
        return "core-like and balanced"
    return f"mixed transition around {regime}"


def classify_trend_context(row: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(row, calibration_context)
    if scores["trend_damage_score"] >= 0.82 and scores["trend_repair_score"] <= 0.40:
        return "deeply damaged"
    if scores["trend_damage_score"] >= 0.65 and scores["trend_repair_score"] <= 0.50:
        return "damaged"
    if scores["trend_repair_score"] >= 0.72 and scores["trend_damage_score"] <= 0.40:
        return "constructive"
    if scores["trend_repair_score"] >= 0.62 and scores["trend_damage_score"] >= 0.50:
        return "repairing but still damaged"
    if scores["trend_repair_score"] >= 0.55:
        return "improving"
    if scores["trend_damage_score"] >= 0.55:
        return "mildly weak"
    return "mixed"


def classify_volatility_context(row: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(row, calibration_context)
    if scores["stress_score"] >= 0.75:
        return "historically elevated stress"
    if scores["calm_score"] >= 0.70:
        return "historically calm"
    band_width_view = percentile_view(row, calibration_context, "band_w")
    if band_width_view["effective_percentile"] is not None and band_width_view["effective_percentile"] <= 0.20:
        return "compressed"
    return "active but not extreme"


def classify_participation_context(row: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(row, calibration_context)
    if scores["participation_score"] >= 0.70:
        return "confirmed"
    if scores["participation_score"] >= 0.58:
        return "supportive"
    if scores["participation_score"] <= 0.35:
        return "thin"
    if scores["participation_score"] <= 0.45:
        return "below typical"
    return "typical"


def classify_stretch_context(row: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(row, calibration_context)
    if scores["stretch_up_score"] >= 0.78:
        return "historically stretched up"
    if scores["stretch_down_score"] >= 0.78:
        return "historically stretched down"
    if scores["stretch_up_score"] >= 0.62:
        return "leaning high in range"
    if scores["stretch_down_score"] >= 0.62:
        return "leaning low in range"
    return "balanced in range"


def classify_correction_asymmetry(row: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(row, calibration_context)
    spread = scores["directional_asymmetry_score"]
    if spread >= 0.25:
        return "clear downside asymmetry"
    if spread >= 0.10:
        return "mild downside asymmetry"
    if spread <= -0.25:
        return "clear upside asymmetry"
    if spread <= -0.10:
        return "mild upside asymmetry"
    return "balanced asymmetry"


def classify_repair_state(row: pd.Series, calibration_context: Dict[str, Any], scores: Optional[Dict[str, float]] = None) -> str:
    scores = scores or compute_soft_scores(row, calibration_context)
    participation_context = classify_participation_context(row, calibration_context, scores)
    volatility_context = classify_volatility_context(row, calibration_context, scores)

    if scores["trend_damage_score"] >= 0.65 and scores["trend_repair_score"] >= 0.58:
        if participation_context in {"thin", "below typical"}:
            return "fragile rebound"
        return "repair attempt"
    if scores["trend_damage_score"] >= 0.65 and scores["trend_repair_score"] <= 0.45 and volatility_context == "compressed":
        return "post-selloff compression"
    if scores["trend_damage_score"] >= 0.68 and scores["trend_repair_score"] <= 0.40:
        return "rolling weakness"
    if scores["trend_repair_score"] >= 0.72 and participation_context in {"confirmed", "supportive"}:
        if scores["stretch_up_score"] >= 0.78:
            return "late-stage surge"
        return "constructive continuation"
    if scores["trend_repair_score"] >= 0.62 and participation_context in {"thin", "below typical"}:
        return "continuation without participation"
    if volatility_context == "compressed" and 0.40 <= scores["trend_damage_score"] <= 0.60 and 0.40 <= scores["trend_repair_score"] <= 0.60:
        return "compression before expansion"
    if scores["trend_repair_score"] > scores["trend_damage_score"]:
        return "improving but not fixed"
    return "transition"


def interpret_now(latest: pd.Series, calibration_context: Dict[str, Any]) -> Dict[str, Any]:
    regime = regime_label(latest)
    conf = max([_to_float(latest.get(c)) or -np.inf for c in ["HMM_CONF", "P_CORE_HMM", "P_DRIFT_HMM", "P_SHOCK_HMM", "P_SURGE_HMM"]])
    scores = compute_soft_scores(latest, calibration_context)

    trend = bucket_trend(latest, calibration_context, scores)
    vol = bucket_volatility(latest, calibration_context, scores)
    part = bucket_participation(latest, calibration_context, scores)
    pos = bucket_position(latest, calibration_context, scores)
    risk = bucket_risk(latest, calibration_context, scores)

    regime_context = classify_regime_context(latest, calibration_context, scores)
    trend_context = classify_trend_context(latest, calibration_context, scores)
    volatility_context = classify_volatility_context(latest, calibration_context, scores)
    participation_context = classify_participation_context(latest, calibration_context, scores)
    stretch_context = classify_stretch_context(latest, calibration_context, scores)
    asymmetry_context = classify_correction_asymmetry(latest, calibration_context, scores)
    repair_state = classify_repair_state(latest, calibration_context, scores)
    historical_context, calibration_note = build_historical_context(latest, calibration_context, scores)

    if repair_state == "post-selloff compression":
        market_mode = "post-shock stabilization"
        market_read = "The market appears to be stabilizing after prior damage, but not repairing yet."
    elif repair_state == "fragile rebound":
        market_mode = "fragile rebound inside damaged structure"
        market_read = "Current upside looks like a rebound inside damage rather than a repaired advance."
    elif repair_state == "repair attempt" and part in {"thin", "below typical"}:
        market_mode = "trend repair attempt without participation"
        market_read = "Trend repair is improving, but participation is still below typical and keeps the bounce fragile."
    elif repair_state == "late-stage surge":
        market_mode = "late-stage surge with correction risk"
        market_read = "The market remains constructive, but the move is stretched and correction risk is no longer low versus history."
    elif repair_state == "compression before expansion":
        market_mode = "compression before expansion"
        market_read = "Price is compressed versus its own history, so the setup looks more like coiling than resolution."
    elif repair_state == "rolling weakness":
        market_mode = "rolling weakness"
        market_read = "Weakness remains meaningful relative to past observations, even though panic is not fully dominant."
    elif repair_state == "constructive continuation":
        market_mode = "constructive continuation"
        market_read = "Trend repair is strong relative to history and participation is at least supportive."
    elif trend_context in {"damaged", "deeply damaged"} and vol == "calm":
        market_mode = "calm but structurally weak drift"
        market_read = "Current calm is more consistent with drift inside weakness than with fresh strength."
    else:
        market_mode = "mixed transition"
        market_read = "Signals are mixed: some repair is visible, but the market is not yet in a clean historically constructive state."

    return {
        "market_mode": market_mode,
        "market_read": market_read,
        "summary_text": market_read,
        "trend": trend,
        "volatility": vol,
        "participation": part,
        "positioning": pos,
        "regime": {
            "label": regime,
            "confidence": None if not np.isfinite(conf) else float(conf),
        },
        "risk": risk,
        "regime_context": regime_context,
        "trend_context": trend_context,
        "volatility_context": volatility_context,
        "participation_context": participation_context,
        "stretch_context": stretch_context,
        "correction_rebound_context": asymmetry_context,
        "repair_state": repair_state,
        "historical_context": historical_context,
        "calibration_note": calibration_note,
        "soft_scores": {key: round(float(value), 4) for key, value in scores.items()},
    }


def interpret_path(df: pd.DataFrame, idx: int, calibration_context: Dict[str, Any]) -> Dict[str, Any]:
    row = df.iloc[idx]
    scores = compute_soft_scores(row, calibration_context)
    evidence = {}
    for column in [
        "R_3", "R_7", "R_14", "TS_20", "TS_50", "TS_200", "band_pos", "close_in_range",
        "run_length_up", "run_length_down", "run_magnitude_up", "run_magnitude_down",
        "time_since_local_high", "time_since_local_low", "relative_volume_20", "volume_z",
        "ONCHAIN_VOL_Z", "ONCHAIN_DOM_Z",
    ]:
        value = _to_float(row.get(column))
        if value is not None:
            evidence[column] = float(value)

    repair_state = classify_repair_state(row, calibration_context, scores)
    trend_context = classify_trend_context(row, calibration_context, scores)
    participation_context = classify_participation_context(row, calibration_context, scores)
    asymmetry_context = classify_correction_asymmetry(row, calibration_context, scores)
    historical_context, calibration_note = build_historical_context(row, calibration_context, scores)

    if repair_state == "fragile rebound":
        label = "short-term bounce inside damaged structure"
        summary = "Recent returns improved versus their own history, but the broader structure is still damaged and participation remains below typical."
    elif repair_state == "constructive continuation":
        label = "constructive continuation"
        summary = "The market arrived here through a continuation that still looks constructive relative to its own history."
    elif repair_state == "continuation without participation":
        label = "upside continuation with weakening participation"
        summary = "Price kept improving, but participation stayed soft relative to history, so the continuation looks thinner than the move itself."
    elif repair_state == "repair attempt":
        label = "trend repair attempt"
        summary = "Short-term repair measures improved meaningfully versus history, but medium-term damage has not fully normalized."
    elif repair_state == "post-selloff compression":
        label = "post-selloff compression"
        summary = "The path into here is less about trend repair and more about compression after damage."
    elif repair_state == "rolling weakness":
        label = "rolling weakness"
        summary = "The path into here still looks weak relative to history, with damage outpacing repair."
    elif repair_state == "compression before expansion":
        label = "compression before expansion"
        summary = "Recent movement is sitting in a historically quieter band, so the path looks coiled rather than resolved."
    elif repair_state == "late-stage surge":
        label = "late-stage surge with correction risk"
        summary = "The path into here has been strong, but several stretch measures are now high versus history."
    else:
        label = "mixed transition"
        summary = "The path into here mixes repair and residual damage, so the historical read remains mixed rather than clean."

    if asymmetry_context in {"clear downside asymmetry", "mild downside asymmetry"}:
        summary += " Downside asymmetry is still present relative to recent history."
    if participation_context in {"thin", "below typical"}:
        summary += " Participation continues to lag its own baseline."

    return {
        "label": label,
        "summary": summary,
        "evidence": evidence,
        "historical_context": historical_context,
        "calibration_note": calibration_note,
    }


def _summary_median(summary: Dict[str, Any], horizon: str) -> Optional[float]:
    try:
        value = summary["returns"][horizon]["median"]
        return float(value) if value is not None else None
    except Exception:
        return None


def _summary_direction(summary: Dict[str, Any], horizon: str = "10") -> int:
    value = _summary_median(summary, horizon)
    if value is None:
        return 0
    if value > 0.005:
        return 1
    if value < -0.005:
        return -1
    return 0


def _reliability_weight(summary: Dict[str, Any]) -> float:
    score = summary.get("reliability", "medium")
    return {"high": 1.0, "medium": 0.7, "low": 0.4}.get(score, 0.7)


def expectation_from_summaries(
    now: Dict[str, Any],
    state_summary: Dict[str, Any],
    candle_summary: Dict[str, Any],
    regime_summary: Dict[str, Any],
) -> Dict[str, Any]:
    summaries = {
        "state": state_summary,
        "candles": candle_summary,
        "regime": regime_summary,
    }
    weighted = []
    for name, summary in summaries.items():
        median_10 = _summary_median(summary, "10")
        if median_10 is None:
            continue
        weighted.append((name, median_10, _reliability_weight(summary)))

    if not weighted:
        base = "Insufficient analog history for a forward statistical view."
        analog_confidence = "low"
    else:
        weighted_avg = float(sum(value * weight for _, value, weight in weighted) / sum(weight for _, _, weight in weighted))
        directions = [_summary_direction(summary) for summary in summaries.values()]
        conflict = any(direction > 0 for direction in directions) and any(direction < 0 for direction in directions)
        confidence_votes = [summary.get("reliability", "medium") for summary in summaries.values() if summary.get("match_count", 0) > 0]
        if confidence_votes.count("high") >= 2:
            analog_confidence = "high"
        elif confidence_votes.count("low") >= 2:
            analog_confidence = "low"
        else:
            analog_confidence = "medium"

        if conflict or abs(weighted_avg) < 0.007:
            base = "Historical analogs point to a low-confidence choppy environment with only a weak directional edge."
        elif weighted_avg > 0.025:
            base = "Historical analogs favor constructive continuation over the next 10 days."
        elif weighted_avg > 0.005:
            base = "Historical analogs lean to a fragile positive bias rather than a clean breakout."
        elif weighted_avg < -0.025:
            base = "Historical analogs point to elevated downside vulnerability over the next 10 days."
        else:
            base = "Historical analogs lean to a fragile negative bias rather than outright panic."

    calibration_bits: List[str] = []
    if now.get("participation_context") in {"thin", "below typical"}:
        calibration_bits.append("Participation is below typical for this market's history, so positive analogs deserve caution.")
    if now.get("trend_context") in {"damaged", "deeply damaged", "repairing but still damaged"}:
        calibration_bits.append("Trend repair remains below typical constructive conditions.")
    if now.get("correction_rebound_context") in {"clear downside asymmetry", "mild downside asymmetry"}:
        calibration_bits.append("Downside asymmetry is still present relative to the historical distribution of correction versus rebound risk.")
    if _summary_direction(regime_summary) != 0 and (
        _summary_direction(state_summary) == -_summary_direction(regime_summary)
        or _summary_direction(candle_summary) == -_summary_direction(regime_summary)
    ):
        calibration_bits.append("Same-regime analogs disagree with broader analogs, so directional conviction should stay capped.")
    if not calibration_bits:
        calibration_bits.append("Analog families are reasonably aligned, but the read still depends on follow-through from structure and participation.")

    bull_case = "Upside follow-through improves if repair measures continue to climb versus their own history and participation firms up."
    bear_case = "Downside risk rises if stress measures move back into historically elevated territory."
    if now.get("participation_context") in {"thin", "below typical"}:
        bull_case = "Any upside likely remains fragile unless participation improves from below-typical levels."
    if now.get("correction_rebound_context") in {"clear downside asymmetry", "mild downside asymmetry"}:
        bear_case = "Downside remains more sensitive than upside because correction risk is elevated relative to its own history."

    return {
        "base_case": base,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "analog_confidence": analog_confidence,
        "confidence_note": " ".join(calibration_bits),
    }


def recompute_price_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Approximate recalculation for scenarios using only price/volume history."""
    df = df.copy()
    if not {"close", "high", "low", "open"}.issubset(df.columns):
        return df

    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    open_ = pd.to_numeric(df["open"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce") if "volume" in df.columns else None

    ret1 = close.pct_change()
    logr = np.log(close / close.shift(1))

    df["r1"] = ret1
    for w in [3, 7, 14]:
        df[f"R_{w}"] = close / close.shift(w) - 1.0
    for w in [20, 50, 200]:
        ma = close.rolling(w).mean()
        std = close.rolling(w).std(ddof=0)
        df[f"TS_{w}"] = close / ma - 1.0
        df[f"LR_{w}"] = np.log(close / close.shift(w))
        direction = np.sign(close.diff().fillna(0.0))
        df[f"ER_{w}"] = close.diff(w).abs() / direction.abs().rolling(w).sum().replace(0, np.nan)
        df[f"RVR_{w}"] = (close - ma) / std.replace(0, np.nan)

    tr = pd.concat([
        (high - low),
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["true_range"] = tr
    df["atr"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr"] / close
    df["vol_20"] = logr.rolling(20).std(ddof=0)
    df["ewma_vol"] = logr.ewm(span=20, adjust=False).std(bias=False)
    up = logr.where(logr > 0)
    dn = logr.where(logr < 0)
    df["upside_semi_vol"] = up.rolling(20).std(ddof=0)
    df["downside_semi_vol"] = dn.rolling(20).std(ddof=0)

    # Simple band approximation from rolling min/max.
    band_hi = close.rolling(200).max()
    band_lo = close.rolling(200).min()
    df["band_hi"] = band_hi
    df["band_lo"] = band_lo
    df["band_w"] = (band_hi - band_lo) / close
    df["band_pos"] = (close - band_lo) / (band_hi - band_lo).replace(0, np.nan)

    mid = close.rolling(20).mean()
    std20 = close.rolling(20).std(ddof=0)
    df["dist_from_mean_vol_units"] = (close - mid) / std20.replace(0, np.nan)

    df["candle_body"] = close - open_
    df["candle_range"] = high - low
    rng = (high - low).replace(0, np.nan)
    df["body_to_range_ratio"] = (close - open_) / rng
    df["upper_wick_ratio"] = (high - np.maximum(open_, close)) / rng
    df["lower_wick_ratio"] = (np.minimum(open_, close) - low) / rng
    df["close_in_range"] = (close - low) / rng

    if volume is not None:
        df["volume_log1p"] = np.log1p(volume)
        vol20 = volume.rolling(20).mean()
        vol20_std = volume.rolling(20).std(ddof=0)
        df["relative_volume_20"] = volume / vol20.replace(0, np.nan)
        df["volume_z"] = (volume - vol20) / vol20_std.replace(0, np.nan)

    dir1 = np.sign(ret1.fillna(0.0))
    switch = (dir1 != dir1.shift(1)).astype(float)
    df["switch_rate_50"] = switch.rolling(50).mean()

    up_run = np.zeros(len(df))
    dn_run = np.zeros(len(df))
    up_mag = np.zeros(len(df))
    dn_mag = np.zeros(len(df))
    ret_vals = ret1.fillna(0.0).to_numpy()
    for i in range(1, len(df)):
        if ret_vals[i] > 0:
            up_run[i] = up_run[i - 1] + 1
            up_mag[i] = up_mag[i - 1] + ret_vals[i]
            dn_run[i] = 0
            dn_mag[i] = 0
        elif ret_vals[i] < 0:
            dn_run[i] = dn_run[i - 1] + 1
            dn_mag[i] = dn_mag[i - 1] + abs(ret_vals[i])
            up_run[i] = 0
            up_mag[i] = 0
        else:
            up_run[i] = dn_run[i] = up_mag[i] = dn_mag[i] = 0
    df["run_length_up"] = up_run
    df["run_length_down"] = dn_run
    df["run_magnitude_up"] = up_mag
    df["run_magnitude_down"] = dn_mag
    df["return_accel"] = ret1 - ret1.shift(1)

    roll_hi = close.rolling(50).max()
    roll_lo = close.rolling(50).min()
    df["time_since_local_high"] = np.nan
    df["time_since_local_low"] = np.nan
    for i in range(len(df)):
        start = max(0, i - 49)
        window = close.iloc[start:i + 1].to_numpy()
        if len(window):
            argmax = int(np.nanargmax(window))
            argmin = int(np.nanargmin(window))
            df.at[i, "time_since_local_high"] = len(window) - 1 - argmax
            df.at[i, "time_since_local_low"] = len(window) - 1 - argmin
    return ensure_candle_features(df)


def scenario_row(df: pd.DataFrame, shock: float) -> pd.Series:
    sim = df.copy()
    last = sim.iloc[-1].copy()
    if not {"open", "high", "low", "close"}.issubset(sim.columns):
        return last

    old_close = float(last["close"])
    new_close = old_close * (1.0 + shock)
    new_high = max(float(last["high"]), float(last["open"]), new_close)
    new_low = min(float(last["low"]), float(last["open"]), new_close)

    sim.at[sim.index[-1], "close"] = new_close
    sim.at[sim.index[-1], "high"] = new_high
    sim.at[sim.index[-1], "low"] = new_low
    sim = recompute_price_derived_features(sim)
    out = sim.iloc[-1].copy()

    # Keep regime/on-chain/model outputs fixed unless absent.
    for c in df.columns:
        if c.startswith("ONCHAIN_") or c.startswith("P_") or c.endswith("_safe") or c in {"HMM_LABEL", "HMM_CONF", "HMM_DOM"}:
            if c in out.index and c in last.index and pd.isna(out[c]):
                out[c] = last[c]
            elif c in last.index:
                out[c] = last[c]
    return out


def compact_match(m: AnalogMatch) -> Dict[str, Any]:
    return {
        "date": m.end_date,
        "distance": m.distance,
        "similarity": m.similarity,
        "regime": m.regime_label,
        "forward_stats": m.forward_stats,
    }


def scenario_comment(base_now: Dict[str, Any], scenario_now: Dict[str, Any], shock: float) -> str:
    shock_text = f"{shock:+.0%}"
    base_scores = base_now.get("soft_scores", {})
    scenario_scores = scenario_now.get("soft_scores", {})
    stress_delta = float(scenario_scores.get("stress_score", 0.5)) - float(base_scores.get("stress_score", 0.5))
    repair_delta = float(scenario_scores.get("trend_repair_score", 0.5)) - float(base_scores.get("trend_repair_score", 0.5))
    damage_delta = float(scenario_scores.get("trend_damage_score", 0.5)) - float(base_scores.get("trend_damage_score", 0.5))

    if shock < 0:
        if scenario_now.get("risk") == "risk_off" or scenario_now.get("volatility_context") == "historically elevated stress":
            return f"A {shock_text} move would push several stress measures into historically elevated territory."
        if stress_delta > 0.12:
            return f"A {shock_text} move would materially worsen stress relative to recent history."
        return f"A {shock_text} move would still look historically ordinary inside a weak structure, but the damage would deepen."

    if repair_delta > 0.12 and scenario_now.get("trend_context") in {"repairing but still damaged", "improving"}:
        return f"A {shock_text} move would improve short-term repair, but medium-term damage would still remain below typical recovery levels."
    if repair_delta > 0.18 and damage_delta < 0:
        return f"A {shock_text} move would move trend-repair measures meaningfully higher versus recent history."
    if scenario_now.get("repair_state") == "late-stage surge":
        return f"A {shock_text} move would reinforce upside, but also leave the market more stretched than typical."
    return f"A {shock_text} move would improve the near-term read, but not fully settle the broader structural question."


def build_report(
    df: pd.DataFrame,
    candle_matches: List[AnalogMatch],
    candle_summary: Dict[str, Any],
    state_matches: List[AnalogMatch],
    state_summary: Dict[str, Any],
    regime_matches: List[AnalogMatch],
    regime_summary: Dict[str, Any],
    horizons: Sequence[int],
    touch_pct: Sequence[float],
    scenario_shocks: Sequence[float],
    calibration_context: Dict[str, Any],
) -> Dict[str, Any]:
    latest = df.iloc[-1]
    candle_summary = enrich_analog_summary(candle_matches, candle_summary)
    state_summary = enrich_analog_summary(state_matches, state_summary)
    regime_summary = enrich_analog_summary(regime_matches, regime_summary)

    now = interpret_now(latest, calibration_context)
    path = interpret_path(df, len(df) - 1, calibration_context)
    expct = expectation_from_summaries(now, state_summary, candle_summary, regime_summary)

    scenarios = []
    for shock in scenario_shocks:
        row = scenario_row(df, shock)
        scenario_now = interpret_now(row, calibration_context)
        scenario_path = interpret_path(pd.concat([df.iloc[:-1], row.to_frame().T], ignore_index=True), len(df) - 1, calibration_context)
        scenarios.append({
            "shock": shock,
            "price": _to_float(row.get("close")),
            "state_now": scenario_now,
            "path_into_here": scenario_path,
            "scenario_comment": scenario_comment(now, scenario_now, shock),
            "selected_metrics": {
                k: _to_float(row.get(k)) for k in [
                    "R_3", "R_7", "TS_20", "TS_50", "TS_200", "atr_pct", "band_pos",
                    "body_to_range_ratio", "close_in_range", "relative_volume_20", "volume_z",
                ] if k in row.index
            },
        })

    return {
        "date": str(latest["date"]),
        "state_now": now,
        "path_into_here": path,
        "historical_analogs": {
            "candles": {
                "summary": candle_summary,
                "top_matches": [compact_match(m) for m in candle_matches],
            },
            "state_vector": {
                "summary": state_summary,
                "top_matches": [compact_match(m) for m in state_matches],
            },
            "regime_conditioned": {
                "summary": regime_summary,
                "top_matches": [compact_match(m) for m in regime_matches],
            },
        },
        "forward_expectation": expct,
        "scenario_sensitivity": scenarios,
        "meta": {
            "rows": len(df),
            "horizons": list(horizons),
            "touch_pct": list(touch_pct),
        },
    }


def _fmt_pct(value: Optional[float], digits: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):+.{digits}%}"


def _fmt_pct_plain(value: Optional[float], digits: int = 1) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.{digits}%}"


def _score_pct(value: Optional[float]) -> int:
    if value is None or not np.isfinite(value):
        return 0
    return max(0, min(100, int(round(float(value) * 100))))


def _soft_score_label(value: Optional[float]) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    if value >= 0.75:
        return "high"
    if value >= 0.55:
        return "firm"
    if value >= 0.35:
        return "mixed"
    return "low"


def _reliability_class(score: str) -> str:
    return {
        "high": "high",
        "medium": "medium",
        "low": "low",
    }.get(score, "medium")


def _display_reliability_note(summary: Dict[str, Any]) -> str:
    score = str(summary.get("reliability", "medium"))
    if score == "high":
        return "The analog evidence is tight enough to support a clearer directional read."
    if score == "low":
        return "The analog evidence is thin or inconsistent, so any directional read stays tentative."
    return "The analog evidence is usable, though not clean enough to support high conviction."


def _pick_return_stats(summary: Dict[str, Any], horizons: Sequence[str]) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    returns = summary.get("returns", {})
    for horizon in horizons:
        stats = returns.get(horizon)
        if stats:
            return horizon, stats
    return None, None


def _analog_direction_label(summary: Dict[str, Any]) -> str:
    short = _summary_median(summary, "3")
    if short is None:
        short = _summary_median(summary, "5")
    long = _summary_median(summary, "10")
    if long is None:
        long = _summary_median(summary, "20")

    values = [v for v in [short, long] if v is not None]
    if not values:
        return "Unclear"
    avg = float(np.mean(values))
    if avg > 0.02:
        return "Constructive"
    if avg > 0.005:
        return "Mildly constructive"
    if avg < -0.02:
        return "Weak"
    if avg < -0.005:
        return "Fragile"
    return "Mixed"


def _touch_lines(summary: Dict[str, Any]) -> List[str]:
    touches = summary.get("touches", {})
    lines: List[str] = []
    for key in ("2%", "5%", "10%"):
        probs = touches.get(key)
        if not probs:
            continue
        ordered_parts = []
        for name in ("up", "down", "both_same_bar", "none"):
            value = probs.get(name)
            if value is None:
                continue
            label = {
                "up": "up",
                "down": "down",
                "both_same_bar": "both",
                "none": "none",
            }[name]
            ordered_parts.append(f"{label} {_fmt_pct_plain(value, 0)}")
        if ordered_parts:
            lines.append(f"+/-{key}: " + ", ".join(ordered_parts))
    return lines or ["Touch map unavailable"]


def summarize_analog_card(summary: Dict[str, Any]) -> Dict[str, Any]:
    short_h, short_stats = _pick_return_stats(summary, ("3", "5"))
    long_h, long_stats = _pick_return_stats(summary, ("10", "20"))

    if short_h and short_stats:
        short_text = f"{short_h}d median {_fmt_pct(short_stats.get('median'))}, wins {_fmt_pct_plain(short_stats.get('win_rate'), 1)}"
    else:
        short_text = "Short-horizon follow-through unavailable"

    if long_h and long_stats:
        long_text = f"{long_h}d median {_fmt_pct(long_stats.get('median'))}, wins {_fmt_pct_plain(long_stats.get('win_rate'), 1)}"
    else:
        long_text = "Long-horizon follow-through unavailable"

    return {
        "reliability": summary.get("reliability", "medium"),
        "reliability_note": _display_reliability_note(summary),
        "short_text": short_text,
        "long_text": long_text,
        "direction": _analog_direction_label(summary),
        "touch_lines": _touch_lines(summary),
        "match_count": summary.get("match_count", 0),
    }


def collect_used_terms(report: Dict[str, Any]) -> List[tuple[str, str]]:
    now = report["state_now"]
    terms = [
        now.get("regime", {}).get("label"),
        "Participation",
        "Trend repair",
        "Trend damage",
        "Risk balance",
        "Analogs",
        "Touch map",
        "Reliability",
    ]
    if "upside" in str(now.get("correction_rebound_context", "")).lower():
        terms.append("Upside asymmetry")
    seen = set()
    items: List[tuple[str, str]] = []
    for term in terms:
        if not term or term in seen or term not in USED_TERMS_GLOSSARY:
            continue
        seen.add(term)
        items.append((term, USED_TERMS_GLOSSARY[term]))
    return items


def render_used_terms_markdown(report: Dict[str, Any]) -> List[str]:
    lines = ["## Used terms", ""]
    for name, note in collect_used_terms(report):
        lines.append(f"- **{name}**: {note}")
    lines.append("")
    return lines


def _html_badge(text: str, klass: str) -> str:
    return f'<span class="badge {escape(klass)}">{escape(text)}</span>'


def _html_bar(label: str, value: Optional[float]) -> str:
    pct = _score_pct(value)
    value_text = f"{pct}%" if value is not None else "n/a"
    tone = _soft_score_label(value)
    return (
        '<div class="metric-bar">'
        f'<div class="metric-head"><span>{escape(label)}</span><span>{escape(tone)} · {escape(value_text)}</span></div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
        '</div>'
    )


def render_html_report(report: Dict[str, Any]) -> str:
    now = report["state_now"]
    path = report["path_into_here"]
    forward = report["forward_expectation"]
    analogs = report["historical_analogs"]
    scenarios = report["scenario_sensitivity"]
    soft_scores = now.get("soft_scores", {})

    summary_cards = [
        ("Trend", now.get("trend", "n/a"), now.get("trend_context", "")),
        ("Regime", now.get("regime", {}).get("label", "n/a"), now.get("regime_context", "")),
        ("Participation", now.get("participation", "n/a"), now.get("participation_context", "")),
        ("Risk balance", now.get("risk", "n/a"), now.get("correction_rebound_context", "")),
        ("Repair state", now.get("repair_state", "n/a"), now.get("calibration_note", "")),
    ]

    market_map = [
        ("Trend repair", soft_scores.get("trend_repair_score")),
        ("Trend damage", soft_scores.get("trend_damage_score")),
        ("Participation", soft_scores.get("participation_score")),
        ("Calm / stability", soft_scores.get("calm_score")),
        ("Upside asymmetry", soft_scores.get("upside_asymmetry_score")),
    ]

    analog_cards = [
        ("Candles", summarize_analog_card(analogs["candles"]["summary"])),
        ("Full state", summarize_analog_card(analogs["state_vector"]["summary"])),
        ("Same regime", summarize_analog_card(analogs["regime_conditioned"]["summary"])),
    ]

    cards_html = "".join(
        f'''<div class="summary-card">
            <div class="eyebrow">{escape(title)}</div>
            <div class="card-value">{escape(str(value))}</div>
            <div class="card-note">{escape(str(note))}</div>
        </div>'''
        for title, value, note in summary_cards
    )

    bars_html = "".join(_html_bar(label, value) for label, value in market_map)

    analogs_html = "".join(
        f'''<div class="analog-card">
            <div class="analog-head">
                <h3>{escape(title)}</h3>
                {_html_badge(card['reliability'].title(), _reliability_class(card['reliability']))}
            </div>
            <p class="muted">{escape(card['reliability_note'])}</p>
            <div class="analog-line"><span>3-5d</span><strong>{escape(card['short_text'])}</strong></div>
            <div class="analog-line"><span>10-20d</span><strong>{escape(card['long_text'])}</strong></div>
            <div class="analog-line"><span>Direction</span><strong>{escape(card['direction'])}</strong></div>
            <div class="touch-map">
                {''.join(f'<div>{escape(line)}</div>' for line in card['touch_lines'])}
            </div>
        </div>'''
        for title, card in analog_cards
    )

    scenario_rows = "".join(
        f'''<tr>
            <td>{escape(f"{scenario['shock']:+.1%}")}</td>
            <td>{escape(str(scenario['state_now'].get('trend', 'n/a')))}</td>
            <td>{escape(str(scenario['state_now'].get('risk', 'n/a')))}</td>
            <td>{escape(str(scenario.get('scenario_comment', '')))}</td>
        </tr>'''
        for scenario in scenarios
    )

    used_terms_html = "".join(
        f'''<div class="term"><strong>{escape(name)}</strong><span>{escape(note)}</span></div>'''
        for name, note in collect_used_terms(report)
    )

    detail_points = [
        ("Trend", now.get("trend_context", "")),
        ("Regime", now.get("regime_context", "")),
        ("Participation", now.get("participation_context", "")),
        ("Risk", now.get("correction_rebound_context", "")),
    ]
    detail_list_html = "".join(
        f"<li><strong>{escape(label)}:</strong> {escape(str(note))}</li>"
        for label, note in detail_points if note
    )

    hero_detail = str(now.get("calibration_note") or path.get("summary") or forward.get("confidence_note") or "").strip()

    bottom_line = " ".join(
        bit.strip() for bit in [
            str(now.get("market_read", "")),
            str(path.get("summary", "")),
            str(forward.get("base_case", "")),
        ] if bit
    )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SAFE Interpreter Report - {escape(str(report['date']))}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f0e8;
      --panel: #fffdf8;
      --ink: #1d1b18;
      --muted: #625c53;
      --line: #ddd3c2;
      --good: #2e7d5a;
      --warn: #b8772e;
      --bad: #9f3e2b;
      --shadow: 0 14px 32px rgba(54, 38, 19, 0.08);
      --radius: 18px;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Georgia, "Times New Roman", serif; background: linear-gradient(180deg, #efe7db 0%, var(--bg) 100%); color: var(--ink); }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    .hero {{ background: radial-gradient(circle at top left, #fff7ea 0%, var(--panel) 55%, #f7f1e7 100%); border: 1px solid var(--line); border-radius: 26px; padding: 28px; box-shadow: var(--shadow); }}
    .hero .date {{ color: var(--muted); font-size: 0.95rem; margin-bottom: 10px; }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: clamp(2rem, 4vw, 3.1rem); line-height: 1.05; margin-bottom: 12px; }}
    .hero-summary {{ font-size: 1.18rem; line-height: 1.45; margin-bottom: 10px; max-width: 900px; }}
    .hero-sub {{ color: var(--muted); line-height: 1.5; max-width: 900px; }}
    section {{ margin-top: 24px; }}
    .section-title {{ font-size: 1.3rem; margin-bottom: 14px; }}
    .grid-5 {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }}
    .grid-3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .summary-card, .panel, .analog-card, .term {{ background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }}
    .summary-card {{ padding: 16px; min-height: 132px; }}
    .eyebrow {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.72rem; margin-bottom: 10px; }}
    .card-value {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 8px; }}
    .card-note, .muted {{ color: var(--muted); line-height: 1.45; }}
    .panel {{ padding: 18px; }}
    .metric-bar + .metric-bar {{ margin-top: 14px; }}
    .metric-head {{ display: flex; justify-content: space-between; gap: 16px; font-size: 0.95rem; margin-bottom: 6px; }}
    .bar-track {{ height: 12px; border-radius: 999px; background: #efe5d8; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 999px; background: linear-gradient(90deg, #c88a4f 0%, #8f5b2d 100%); }}
    .explain-list {{ margin: 14px 0 0; padding-left: 18px; line-height: 1.55; }}
    .analog-card {{ padding: 18px; }}
    .analog-head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; }}
    .badge {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 5px 10px; font-size: 0.78rem; font-weight: 700; }}
    .badge.high {{ background: rgba(46,125,90,0.14); color: var(--good); }}
    .badge.medium {{ background: rgba(184,119,46,0.14); color: var(--warn); }}
    .badge.low {{ background: rgba(159,62,43,0.14); color: var(--bad); }}
    .analog-line {{ display: flex; justify-content: space-between; gap: 16px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee2d3; }}
    .analog-line span {{ color: var(--muted); }}
    .touch-map {{ margin-top: 14px; padding: 12px; border-radius: 14px; background: #f7f0e5; color: var(--muted); line-height: 1.5; }}
    .confidence-line {{ margin-top: 12px; color: var(--muted); line-height: 1.5; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }}
    th, td {{ padding: 14px 12px; text-align: left; border-bottom: 1px solid #eee2d3; vertical-align: top; }}
    th {{ background: #f7f0e5; font-size: 0.83rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }}
    tr:last-child td {{ border-bottom: none; }}
    .bottom-line {{ font-size: 1.05rem; line-height: 1.7; background: #fff7ea; border: 1px solid var(--line); border-radius: 22px; padding: 22px; box-shadow: var(--shadow); }}
    .terms-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .term {{ padding: 14px; display: flex; flex-direction: column; gap: 6px; }}
    .term span {{ color: var(--muted); line-height: 1.45; }}
    @media (max-width: 980px) {{
      .grid-5, .grid-3, .terms-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 720px) {{
      .grid-5, .grid-3, .terms-grid {{ grid-template-columns: 1fr; }}
      .analog-line, .metric-head, .analog-head {{ flex-direction: column; align-items: flex-start; }}
      th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="date">SAFE market note · {escape(str(report['date']))}</div>
      <h1>SAFE Interpreter Report</h1>
      <p class="hero-summary">{escape(str(now.get('market_read', 'No current market reading available.')))}</p>
      <p class="hero-sub">{escape(hero_detail)}</p>
    </section>

    <section>
      <h2 class="section-title">Summary cards</h2>
      <div class="grid-5">{cards_html}</div>
    </section>

    <section>
      <h2 class="section-title">Current market map</h2>
      <div class="panel">{bars_html}</div>
    </section>

    <section>
      <h2 class="section-title">Why SAFE thinks this</h2>
      <div class="grid-3">
        <div class="panel"><div class="eyebrow">Now</div><p>{escape(str(now.get('summary_text', now.get('market_read', ''))))}</p></div>
        <div class="panel"><div class="eyebrow">Past path</div><p>{escape(str(path.get('summary', '')))}</p></div>
        <div class="panel"><div class="eyebrow">Forward bias</div><p>{escape(str(forward.get('base_case', '')))}</p></div>
      </div>
      <div class="panel" style="margin-top:14px;">
        <ul class="explain-list">{detail_list_html}</ul>
      </div>
    </section>

    <section>
      <h2 class="section-title">Historical analogs</h2>
      <div class="grid-3">{analogs_html}</div>
    </section>

    <section>
      <h2 class="section-title">Forward view</h2>
      <div class="grid-3">
        <div class="panel"><div class="eyebrow">Base case</div><p>{escape(str(forward.get('base_case', '')))}</p></div>
        <div class="panel"><div class="eyebrow">Bull case</div><p>{escape(str(forward.get('bull_case', '')))}</p></div>
        <div class="panel"><div class="eyebrow">Bear case</div><p>{escape(str(forward.get('bear_case', '')))}</p></div>
      </div>
      <div class="confidence-line"><strong>Analog confidence:</strong> {escape(str(forward.get('analog_confidence', 'n/a')))} · {escape(str(forward.get('confidence_note', '')))}</div>
    </section>

    <section>
      <h2 class="section-title">Scenario sensitivity</h2>
      <table>
        <thead>
          <tr><th>Shock</th><th>Trend view</th><th>Risk view</th><th>Interpretation</th></tr>
        </thead>
        <tbody>{scenario_rows}</tbody>
      </table>
    </section>

    <section>
      <h2 class="section-title">Bottom line</h2>
      <div class="bottom-line">{escape(bottom_line)}</div>
    </section>

    <section>
      <h2 class="section-title">Used terms</h2>
      <div class="terms-grid">{used_terms_html}</div>
    </section>
  </div>
</body>
</html>'''
    return html


def md_from_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    now = report["state_now"]
    path = report["path_into_here"]
    forward = report["forward_expectation"]
    lines.append(f"# SAFE Interpreter Report — {report['date']}")
    lines.append("")
    lines.append("## Executive summary")
    lines.append(now.get("market_read", ""))
    lines.append("")
    lines.append(path.get("summary", ""))
    lines.append("")
    lines.append("## Summary cards")
    lines.append(f"- Trend: **{now.get('trend', 'n/a')}** — {now.get('trend_context', '')}")
    lines.append(f"- Regime: **{now.get('regime', {}).get('label', 'n/a')}** — {now.get('regime_context', '')}")
    lines.append(f"- Participation: **{now.get('participation', 'n/a')}** — {now.get('participation_context', '')}")
    lines.append(f"- Risk balance: **{now.get('risk', 'n/a')}** — {now.get('correction_rebound_context', '')}")
    lines.append(f"- Repair state: **{now.get('repair_state', 'n/a')}** — {now.get('calibration_note', '')}")
    lines.append("")
    lines.append("## Forward view")
    lines.append(f"- Base case: {forward.get('base_case', '')}")
    lines.append(f"- Bull case: {forward.get('bull_case', '')}")
    lines.append(f"- Bear case: {forward.get('bear_case', '')}")
    lines.append(f"- Analog confidence: **{forward.get('analog_confidence', 'n/a')}**")
    if forward.get("confidence_note"):
        lines.append(f"- Confidence note: {forward['confidence_note']}")
    lines.append("")
    lines.append("## Scenario sensitivity")
    for scenario in report["scenario_sensitivity"]:
        lines.append(
            f"- {scenario['shock']:+.1%}: trend={scenario['state_now'].get('trend', 'n/a')}, risk={scenario['state_now'].get('risk', 'n/a')} — {scenario.get('scenario_comment', '')}"
        )
    lines.append("")
    lines.extend(render_used_terms_markdown(report))
    return "\n".join(lines)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interpret SAFE 3.0 features and historical analogs")
    p.add_argument("--features", required=False, help="Path to features.csv", default=str(DEFAULT_FEATURES_CSV_PATH))
    p.add_argument("--onchain", required=False, help="Path to onchain_features.csv", default=str(DEFAULT_ONCHAIN_FEATURES_CSV_PATH))
    p.add_argument("--out-dir", default=str(OUT_DIR / "safe_interpreter_out_v2"), help="Output directory")
    p.add_argument("--seq-len", type=int, default=5, help="Candle sequence length")
    p.add_argument("--top-k", type=int, default=20, help="Top matches per engine")
    p.add_argument("--min-gap", type=int, default=20, help="Minimum row gap from current state")
    p.add_argument("--horizons", default="3,5,10,20", help="Comma-separated forward horizons")
    p.add_argument("--touch-pct", default="0.02,0.05,0.10", help="Comma-separated touch percentages")
    p.add_argument("--scenario-shocks", default="-0.10,-0.05,-0.03,-0.02,0.02,0.03,0.05,0.10", help="Comma-separated price shocks")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    horizons = [int(x.strip()) for x in args.horizons.split(",") if x.strip()]
    touch_pct = [float(x.strip()) for x in args.touch_pct.split(",") if x.strip()]
    scenario_shocks = [float(x.strip()) for x in args.scenario_shocks.split(",") if x.strip()]

    df = merge_inputs(Path(args.features), Path(args.onchain))
    validate_ranges(df)
    df = ensure_candle_features(df)
    calibration_context = build_calibration_context(df)

    if len(df) < max(250, args.seq_len + args.min_gap + max(horizons, default=20) + 1):
        raise ValueError("Not enough history for stable analog search and forward summaries")

    query_idx = len(df) - 1
    current_regime = regime_label(df.iloc[query_idx])

    candle_matches, candle_summary = find_candle_sequence_analogs(
        df=df,
        query_idx=query_idx,
        seq_len=args.seq_len,
        top_k=args.top_k,
        min_gap=args.min_gap,
        horizons=horizons,
        touch_pct=touch_pct,
    )

    state_matches, state_summary = find_state_analogs(
        df=df,
        query_idx=query_idx,
        groups=DEFAULT_GROUPS,
        weights=DEFAULT_WEIGHTS,
        top_k=args.top_k,
        min_gap=args.min_gap,
        horizons=horizons,
        touch_pct=touch_pct,
        regime_filter=None,
    )

    regime_matches, regime_summary = find_state_analogs(
        df=df,
        query_idx=query_idx,
        groups=DEFAULT_GROUPS,
        weights=DEFAULT_WEIGHTS,
        top_k=args.top_k,
        min_gap=args.min_gap,
        horizons=horizons,
        touch_pct=touch_pct,
        regime_filter=current_regime,
    )

    report = build_report(
        df=df,
        candle_matches=candle_matches,
        candle_summary=candle_summary,
        state_matches=state_matches,
        state_summary=state_summary,
        regime_matches=regime_matches,
        regime_summary=regime_summary,
        horizons=horizons,
        touch_pct=touch_pct,
        scenario_shocks=scenario_shocks,
        calibration_context=calibration_context,
    )

    json_path = out_dir / "interpreter_report.json"
    html_path = out_dir / "interpreter_report.html"
    md_path = out_dir / "interpreter_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    html_path.write_text(render_html_report(report), encoding="utf-8")
    md_path.write_text(md_from_report(report), encoding="utf-8")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {html_path}")
    print(f"Wrote: {md_path}")


if __name__ == "__main__":
    main()
