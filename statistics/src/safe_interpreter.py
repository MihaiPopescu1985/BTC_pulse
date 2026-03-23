#!/usr/bin/env python3
"""
safe_interpreter_v1.py

SAFE 3.0 market interpreter.

Inputs:
  - features.json
  - onchain_features.json

Outputs:
  - interpreter_report.json
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

This script targets the current SAFE 3.0 export format:
  - features.json: {"meta": ..., "dates": [...], "series": {...}}
  - onchain_features.json: {"meta": ..., "dates": [...], "series": {...}}

The scenario engine is approximate by design.
It recomputes a subset of price-derived features from the available history,
while keeping on-chain features and model outputs unchanged.

python safe_interpreter_v2.py \
  --features features.json \
  --onchain onchain_features.json \
  --out-dir safe_interpreter_out
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


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



def load_json_rows(path: Path) -> pd.DataFrame:
    """Load a SAFE 3.0 JSON export into a dataframe."""
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    if not isinstance(obj, dict):
        raise ValueError(f"{path} must be a JSON object")
    if "dates" not in obj or "series" not in obj:
        raise ValueError(f"{path} must contain 'dates' and 'series'")
    if not isinstance(obj["dates"], list):
        raise ValueError(f"{path} -> 'dates' must be a list")
    if not isinstance(obj["series"], dict):
        raise ValueError(f"{path} -> 'series' must be an object")

    df = pd.DataFrame({"date": pd.to_datetime(obj["dates"], errors="coerce")})
    if df["date"].isna().any():
        raise ValueError(f"{path} contains invalid date values")

    bad_lengths: List[Tuple[str, int]] = []
    for name, values in obj["series"].items():
        if not isinstance(values, list):
            raise ValueError(f"{path} -> series['{name}'] must be a list")
        if len(values) != len(df):
            bad_lengths.append((name, len(values)))
            continue
        df[name] = values

    if bad_lengths:
        preview = ", ".join(f"{k}={n}" for k, n in bad_lengths[:5])
        raise ValueError(
            f"{path} contains series with lengths different from dates ({len(df)}): {preview}"
        )
    return df


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
    features = normalize_df(load_json_rows(features_path))
    onchain = normalize_df(load_json_rows(onchain_path))

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


def bucket_trend(latest: pd.Series) -> str:
    ts20 = _to_float(latest.get("TS_20"))
    ts50 = _to_float(latest.get("TS_50"))
    ts200 = _to_float(latest.get("TS_200"))
    vals = [v for v in [ts20, ts50, ts200] if v is not None]
    if not vals:
        return "unknown"
    neg = sum(v < 0 for v in vals)
    pos = sum(v > 0 for v in vals)
    if neg >= 2:
        return "bearish"
    if pos >= 2:
        return "bullish"
    return "mixed"


def bucket_volatility(latest: pd.Series) -> str:
    atr_pct = _to_float(latest.get("atr_pct"))
    vol20 = _to_float(latest.get("vol_20"))
    if atr_pct is None and vol20 is None:
        return "unknown"
    score = max(v for v in [atr_pct or -np.inf, vol20 or -np.inf] if v is not None)
    if score >= 0.07:
        return "very high"
    if score >= 0.04:
        return "elevated"
    if score >= 0.02:
        return "moderate"
    return "low"


def bucket_participation(latest: pd.Series) -> str:
    rv = _to_float(latest.get("relative_volume_20"))
    vz = _to_float(latest.get("volume_z"))
    onz = _to_float(latest.get("ONCHAIN_VOL_Z"))
    votes = []
    if rv is not None:
        votes.append("strong" if rv > 1.15 else "weak" if rv < 0.85 else "normal")
    if vz is not None:
        votes.append("strong" if vz > 0.75 else "weak" if vz < -0.75 else "normal")
    if onz is not None:
        votes.append("strong" if onz > 0.75 else "weak" if onz < -0.75 else "normal")
    if not votes:
        return "unknown"
    if votes.count("weak") >= 2:
        return "weak"
    if votes.count("strong") >= 2:
        return "strong"
    return "normal"


def bucket_position(latest: pd.Series) -> str:
    band_pos = _to_float(latest.get("band_pos"))
    close_in_range = _to_float(latest.get("close_in_range"))
    if band_pos is not None:
        if band_pos <= 0.25:
            return "lower_band_area"
        if band_pos >= 0.75:
            return "upper_band_area"
    if close_in_range is not None:
        if close_in_range <= 0.25:
            return "closed_near_low"
        if close_in_range >= 0.75:
            return "closed_near_high"
    return "mid_range"


def bucket_risk(latest: pd.Series) -> str:
    shock = _to_float(latest.get("P_SHOCK_HMM")) or 0.0
    corr = _to_float(latest.get("P_CORRECTION_10D_CAL")) or 0.0
    reb = _to_float(latest.get("P_REBOUND_10D_CAL")) or 0.0
    risk_off = _to_float(latest.get("hard_risk_off_flag_safe")) or 0.0
    if risk_off >= 0.5 or shock >= 0.5:
        return "risk_off"
    if corr >= 0.35 and corr > reb:
        return "downside_risk_elevated"
    if reb >= 0.35 and reb > corr:
        return "rebound_potential_elevated"
    return "balanced"


def interpret_now(latest: pd.Series) -> Dict[str, Any]:
    regime = regime_label(latest)
    conf = max([_to_float(latest.get(c)) or -np.inf for c in ["HMM_CONF", "P_CORE_HMM", "P_DRIFT_HMM", "P_SHOCK_HMM", "P_SURGE_HMM"]])
    trend = bucket_trend(latest)
    vol = bucket_volatility(latest)
    part = bucket_participation(latest)
    pos = bucket_position(latest)
    risk = bucket_risk(latest)

    market_mode = regime.lower()
    if regime == "DRIFT" and trend == "bearish":
        market_mode = "fragile drift in damaged structure"
    elif regime == "SURGE" and trend == "bullish":
        market_mode = "bullish expansion"
    elif regime == "SHOCK":
        market_mode = "stress / shock"
    elif regime == "CORE":
        market_mode = "core trend state"

    return {
        "market_mode": market_mode,
        "trend": trend,
        "volatility": vol,
        "participation": part,
        "positioning": pos,
        "regime": {
            "label": regime,
            "confidence": None if not np.isfinite(conf) else float(conf),
        },
        "risk": risk,
    }


def interpret_path(df: pd.DataFrame, idx: int) -> Dict[str, Any]:
    row = df.iloc[idx]
    parts = []
    evidence = {}
    for c in ["R_3", "R_7", "R_14", "TS_20", "TS_50", "TS_200", "time_since_local_high", "time_since_local_low"]:
        v = _to_float(row.get(c))
        if v is not None:
            evidence[c] = float(v)

    r3 = _to_float(row.get("R_3"))
    r7 = _to_float(row.get("R_7"))
    r14 = _to_float(row.get("R_14"))
    trend = bucket_trend(row)

    if r3 is not None and r7 is not None:
        if r3 < 0 and r7 < 0:
            parts.append("came from short-term weakness")
        elif r3 > 0 and r7 > 0:
            parts.append("came from short-term strength")
        else:
            parts.append("came from choppy short-term movement")

    if r14 is not None:
        if r14 > 0 and (r3 is not None and r3 < 0):
            parts.append("after a pullback inside a stronger 2-week move")
        elif r14 < 0 and (r3 is not None and r3 > 0):
            parts.append("after a bounce inside a weaker 2-week structure")

    if trend == "bearish":
        parts.append("inside a still-damaged medium/long-term structure")
    elif trend == "bullish":
        parts.append("inside a constructive medium/long-term structure")

    summary = ", ".join(dict.fromkeys(parts)) if parts else "path not clear"
    return {"summary": summary, "evidence": evidence}


def expectation_from_summaries(now: Dict[str, Any], state_summary: Dict[str, Any], candle_summary: Dict[str, Any], regime_summary: Dict[str, Any]) -> Dict[str, Any]:
    def med(summary: Dict[str, Any], h: str) -> Optional[float]:
        try:
            return summary["returns"][h]["median"]
        except Exception:
            return None

    vals_10 = [v for v in [med(state_summary, "10"), med(candle_summary, "10"), med(regime_summary, "10")] if v is not None]
    avg10 = float(np.mean(vals_10)) if vals_10 else None

    if avg10 is None:
        base = "insufficient analog history for a forward statistical view"
    elif avg10 > 0.03:
        base = "historical analogs favor upside continuation over the next 10 days"
    elif avg10 > 0.005:
        base = "historical analogs lean mildly positive over the next 10 days"
    elif avg10 < -0.03:
        base = "historical analogs favor downside continuation over the next 10 days"
    elif avg10 < -0.005:
        base = "historical analogs lean mildly negative over the next 10 days"
    else:
        base = "historical analogs suggest drift / range with weak directional edge"

    mode = now.get("market_mode", "unknown")
    trend = now.get("trend", "unknown")
    part = now.get("participation", "unknown")
    risk = now.get("risk", "unknown")

    bull = "needs stronger participation and improving short-term structure"
    bear = "fails if shock risk rises or trend weakness resumes"

    if trend == "bearish" and part == "weak":
        bull = "upside likely remains fragile unless participation and trend repair improve together"
    if risk in {"risk_off", "downside_risk_elevated"}:
        bear = "downside remains sensitive because risk state is not fully benign"

    return {
        "base_case": f"{mode}: {base}",
        "bull_case": bull,
        "bear_case": bear,
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
) -> Dict[str, Any]:
    latest = df.iloc[-1]
    now = interpret_now(latest)
    path = interpret_path(df, len(df) - 1)
    expct = expectation_from_summaries(now, state_summary, candle_summary, regime_summary)

    scenarios = []
    for shock in scenario_shocks:
        row = scenario_row(df, shock)
        scenarios.append({
            "shock": shock,
            "price": _to_float(row.get("close")),
            "state_now": interpret_now(row),
            "path_into_here": interpret_path(pd.concat([df.iloc[:-1], row.to_frame().T], ignore_index=True), len(df) - 1),
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


def md_from_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# SAFE Interpreter Report — {report['date']}")
    lines.append("")

    now = report["state_now"]
    lines.append("## State now")
    lines.append(f"- Market mode: **{now['market_mode']}**")
    lines.append(f"- Trend: **{now['trend']}**")
    lines.append(f"- Volatility: **{now['volatility']}**")
    lines.append(f"- Participation: **{now['participation']}**")
    lines.append(f"- Positioning: **{now['positioning']}**")
    lines.append(f"- Regime: **{now['regime']['label']}**")
    if now['regime']['confidence'] is not None:
        lines.append(f"- Regime confidence: **{now['regime']['confidence']:.4f}**")
    lines.append(f"- Risk: **{now['risk']}**")
    lines.append("")

    path = report["path_into_here"]
    lines.append("## Path into here")
    lines.append(path["summary"])
    lines.append("")

    lines.append("## What usually came next")
    for name, block in report["historical_analogs"].items():
        lines.append(f"### {name.replace('_', ' ').title()}")
        summary = block["summary"]
        returns = summary.get("returns", {})
        if returns:
            for h, r in returns.items():
                lines.append(
                    f"- {h}d median={r['median']:+.2%}, mean={r['mean']:+.2%}, win_rate={r['win_rate']:.1%}, n={r['count']}"
                )
        else:
            lines.append("- No forward return summary available")
        touches = summary.get("touches", {})
        for t, probs in touches.items():
            parts = ", ".join(f"{k}={v:.1%}" for k, v in probs.items())
            lines.append(f"- Touch {t}: {parts}")
        lines.append("")

    expct = report["forward_expectation"]
    lines.append("## Forward expectation")
    lines.append(f"- Base case: {expct['base_case']}")
    lines.append(f"- Bull case: {expct['bull_case']}")
    lines.append(f"- Bear case: {expct['bear_case']}")
    lines.append("")

    lines.append("## Scenario sensitivity")
    for s in report["scenario_sensitivity"]:
        shock = s["shock"]
        state = s["state_now"]
        lines.append(
            f"- {shock:+.1%}: price={s['price']:.2f}, mode={state['market_mode']}, trend={state['trend']}, vol={state['volatility']}, risk={state['risk']}"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interpret SAFE 3.0 features and historical analogs")
    p.add_argument("--features", required=False, help="Path to features.json", default="/home/mihai/Documents/BTC_pulse/statistics/out/features.json")
    p.add_argument("--onchain", required=False, help="Path to onchain_features.json", default="/home/mihai/Documents/BTC_pulse/statistics/out/onchain_features.json")
    p.add_argument("--out-dir", default="/home/mihai/Documents/BTC_pulse/statistics/out/safe_interpreter_out", help="Output directory")
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
    )

    json_path = out_dir / "interpreter_report.json"
    md_path = out_dir / "interpreter_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(md_from_report(report), encoding="utf-8")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")


if __name__ == "__main__":
    main()
