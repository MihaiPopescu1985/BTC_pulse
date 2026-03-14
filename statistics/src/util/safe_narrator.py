#!/usr/bin/env python3

# -----------------------------------------------------------------------------
# SAFE NARRATOR – DESIGN NOTES (v1 STABLE)
#
# This narrator is not an arbitrary text generator.
# It is a deterministic explanatory layer built on:
#   - quantile discretization (p30 / p70, etc.)
#   - fixed semantic rules (labels)
#
# Key principles:
# 1) Strict separation between:
#    - facts (semantic labels derived only from data)
#    - narration (text derived only from facts)
#
# 2) Every textual claim must be verifiable:
#    - via truth check (quantile consistency)
#    - via relevance check (forward empirical meaning)
#
# 3) The narrator does not predict.
#    It describes the current probabilistic market context.
#
# 4) Semantic changes are allowed only if:
#    - truth check stays 100% OK
#    - relevance check does not introduce FAILs
#
# Validated by:
#   test/validate_narrator_semantics.py
#   - point truth checks (e.g., 2020-03-12, 2021-05-19)
#   - relevance checks over full history + windows (3y, 5y)
#   - bootstrap sign consistency
#
# -----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


QUANTILE_LEVELS = (0.10, 0.30, 0.70, 0.90)
ONCHAIN_MAX_KEYS = 12


def parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_years_window_dates(
    dates: List[str], anchor_date: Optional[str], years: int
) -> List[str]:
    if years <= 0:
        return []
    parsed = []
    for idx, d in enumerate(dates):
        try:
            parsed.append((idx, parse_date(d)))
        except ValueError:
            parsed.append((idx, None))

    anchor = None
    if anchor_date:
        try:
            anchor = parse_date(anchor_date)
        except ValueError:
            anchor = None
    if anchor is None:
        valid_dates = [d for _, d in parsed if d is not None]
        if not valid_dates:
            return []
        anchor = max(valid_dates)

    start_date = anchor - timedelta(days=years * 365)
    return [dates[idx] for idx, d in parsed if d is not None and start_date <= d <= anchor]


def load_series_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {
        "dates": payload.get("dates", []),
        "series": payload.get("series", {}),
        "meta": payload.get("meta", {}),
    }


def is_finite(value: Optional[float]) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(value)


def quantile(sorted_vals: List[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo))


def compute_quantile_thresholds(values: List[float], qs: Optional[List[float]] = None) -> Dict[str, float]:
    levels = qs if qs is not None else list(QUANTILE_LEVELS)
    clean = sorted(v for v in values if is_finite(v))
    out: Dict[str, float] = {}
    for q in levels:
        out[f"p{int(q * 100)}"] = quantile(clean, q)
    return out


def compute_quantiles(values: List[float]) -> Dict[str, float]:
    return compute_quantile_thresholds(values)


def align_series_to_dates(
    source_dates: List[str], series: Dict[str, List[float]], target_dates: List[str]
) -> Dict[str, List[Optional[float]]]:
    index = {d: i for i, d in enumerate(source_dates)}
    aligned: Dict[str, List[Optional[float]]] = {}
    for key, values in series.items():
        out: List[Optional[float]] = []
        for d in target_dates:
            idx = index.get(d)
            if idx is None or idx >= len(values):
                out.append(None)
            else:
                out.append(values[idx])
        aligned[key] = out
    return aligned


def align_payloads(
    features: Dict, onchain: Optional[Dict]
) -> Tuple[Dict, Optional[Dict], List[str]]:
    dates = features.get("dates", [])
    if not onchain:
        return features, None, dates

    onchain_dates = onchain.get("dates", [])
    if not dates or not onchain_dates:
        return features, {"dates": [], "series": {}, "meta": onchain.get("meta", {})}, dates

    common_set = set(onchain_dates)
    common_dates = [d for d in dates if d in common_set]
    if not common_dates:
        return features, {"dates": [], "series": {}, "meta": onchain.get("meta", {})}, dates

    aligned_features = {
        "dates": common_dates,
        "series": align_series_to_dates(dates, features.get("series", {}), common_dates),
        "meta": features.get("meta", {}),
    }
    aligned_onchain = {
        "dates": common_dates,
        "series": align_series_to_dates(onchain_dates, onchain.get("series", {}), common_dates),
        "meta": onchain.get("meta", {}),
    }
    return aligned_features, aligned_onchain, common_dates


def is_numeric_series(values: List[float]) -> bool:
    return any(is_finite(v) for v in values)


def is_redundant_onchain_key(key: str) -> bool:
    lower = key.lower()
    if "meta" in lower:
        return True
    if key.endswith(("_Z", "_PCT", "_LOG")):
        return True
    return False


def onchain_key_priority(key: str) -> int:
    lower = key.lower()
    if "amount" in lower or "volume" in lower or "vol_" in lower or lower.endswith("vol"):
        return 0
    if "tx" in lower and any(token in lower for token in ("size", "large", "small", "share")):
        return 1
    return 2


def select_onchain_keys(series: Dict[str, List[float]], max_keys: int = ONCHAIN_MAX_KEYS) -> List[str]:
    keys = list(series.keys())
    numeric_keys = [
        key
        for key in keys
        if isinstance(series.get(key), list)
        and is_numeric_series(series[key])
        and not is_redundant_onchain_key(key)
    ]
    if len(numeric_keys) <= max_keys:
        return numeric_keys

    indexed = [(onchain_key_priority(key), idx, key) for idx, key in enumerate(numeric_keys)]
    indexed.sort()
    chosen = indexed[:max_keys]
    chosen.sort(key=lambda item: item[1])
    return [key for _, _, key in chosen]


def select_amount_key(keys: List[str]) -> Optional[str]:
    for key in keys:
        lower = key.lower()
        if "amount" in lower or "volume" in lower or "vol_" in lower or lower.endswith("vol"):
            return key
    return None


def select_share_key(keys: List[str], kind: str) -> Optional[str]:
    tokens = ("large", "whale") if kind == "large" else ("small",)
    for key in keys:
        lower = key.lower()
        if any(token in lower for token in tokens) and ("share" in lower or "pct" in lower):
            return key
    return None


def state_from_thresholds(value: Optional[float], q: Dict[str, float]) -> Optional[str]:
    if value is None:
        return None
    p30 = q.get("p30")
    p70 = q.get("p70")
    if not (is_finite(p30) and is_finite(p70)):
        return None
    if value <= p30:
        return "low"
    if value >= p70:
        return "high"
    return "medium"


def build_onchain_text(
    activity_state: Optional[str],
    structure_state: str,
    has_data: bool,
) -> str:
    if not has_data:
        return "Date on-chain limitate pentru interpretare azi."

    if activity_state == "high":
        activity_sentence = "Activitate on-chain ridicata; capital activ."
    elif activity_state == "low":
        activity_sentence = "Activitate redusa; miscare posibil mai fragila."
    elif activity_state == "medium":
        activity_sentence = "Activitate on-chain moderata; capitalul pare selectiv."
    else:
        activity_sentence = "Activitatea on-chain are un semnal limitat in datele disponibile."

    return f"{activity_sentence} {structure_state}"


def build_onchain_structure_sentence(large_active: bool, small_active: bool) -> str:
    if large_active and small_active:
        return "Entitati mari si retail mai active."
    if large_active:
        return "Entitati mari mai active."
    if small_active:
        return "Participare retail mai activa."
    return "Participare mixta."


def thresholds_for_keys(
    dates: List[str],
    series: Dict[str, List[float]],
    keys: List[str],
    date_subset: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    idxs = list(range(len(dates)))
    subset = set(date_subset) if date_subset else None
    thresholds: Dict[str, Dict[str, float]] = {}
    for key in keys:
        values = []
        arr = series.get(key, [])
        for i in idxs:
            if subset is not None and dates[i] not in subset:
                continue
            if i < len(arr) and is_finite(arr[i]):
                values.append(float(arr[i]))
        thresholds[key] = compute_quantiles(values)
    return thresholds


def get_value(series: Dict[str, List[float]], key: str, idx: int) -> Optional[float]:
    arr = series.get(key, [])
    if idx < 0 or idx >= len(arr):
        return None
    value = arr[idx]
    return float(value) if is_finite(value) else None


def bucket(
    value: Optional[float],
    q: Dict[str, float],
    cutoffs: List[str],
    labels: List[str],
) -> str:
    if value is None:
        return "necunoscut"
    bounds = [q.get(c) for c in cutoffs]
    if not all(is_finite(b) for b in bounds):
        return "necunoscut"
    for bound, label in zip(bounds, labels):
        if value <= bound:
            return label
    return labels[-1]


def discretize_value(
    value: Optional[float],
    q: Dict[str, float],
    cutoffs: List[str],
    labels: List[str],
) -> str:
    return bucket(value, q, cutoffs, labels)

# NOTE:
# HMM_STATE_* keys are detected dynamically (no hard-coded K).
# Reason:
#   - SAFE may scan a variable K (2..10)
#   - the narrator must remain compatible with any K
#
# Rule:
#   - regime_dom = state with highest probability
#   - regime_alt = second-highest probability
#   - regime_clarity derived from the probability distribution
#
# Any change here must be validated with:
#   validate_narrator_semantics.py (truth + relevance)

def hmm_labels(features: Dict) -> Dict[int, str]:
    meta = features.get("meta", {})
    labels = meta.get("hmm", {}).get("labels_by_state") or meta.get("labels_by_state")
    if labels and isinstance(labels, list):
        return {i: labels[i] for i in range(len(labels))}
    return {}


def hmm_state_probs(series: Dict[str, List[float]], idx: int) -> List[Tuple[int, float]]:
    items: List[Tuple[int, float]] = []
    key_pairs = []
    for key in series.keys():
        match = re.match(r"^HMM_STATE_(\d+)$", key)
        if match:
            key_pairs.append((int(match.group(1)), key))
    key_pairs.sort(key=lambda x: x[0])
    for state_id, key in key_pairs:
        v = get_value(series, key, idx)
        if v is not None:
            items.append((state_id, v))
    if not items:
        return []
    return sorted(items, key=lambda x: x[1], reverse=True)


def hmm_dom_changed_recently(series: Dict[str, List[float]], idx: int, lookback: int = 3) -> bool:
    arr = series.get("HMM_DOM", [])
    start = max(0, idx - lookback)
    vals = []
    for i in range(start, idx + 1):
        if i < len(arr) and is_finite(arr[i]):
            vals.append(int(arr[i]))
    return len(set(vals)) > 1


def classify_hmm_conf(value: Optional[float], thresholds: Dict[str, float]) -> str:
    p70 = thresholds.get("p70")
    if is_finite(value) and is_finite(p70) and value >= p70:
        return "clar"
    return "ambiguu"


def is_hmm_conf_low(value: Optional[float], thresholds: Dict[str, float]) -> bool:
    p30 = thresholds.get("p30")
    return is_finite(value) and is_finite(p30) and value <= p30


def compute_facts_for_day(
    features: Dict,
    idx: int,
    thresholds: Optional[Dict[str, Dict[str, float]]] = None,
    onchain: Optional[Dict] = None,
    onchain_thresholds: Optional[Dict[str, Dict[str, float]]] = None,
    onchain_keys_used: Optional[List[str]] = None,
) -> Dict[str, object]:
    dates = features.get("dates", [])
    series = features.get("series", {})
    if not dates or not series:
        raise ValueError("features must include 'dates' and 'series'.")

    if thresholds is None:
        keys_for_thresholds = [
            "TS_50",
            "band_w",
            "band_pos",
            "range_score",
            "P_CORRECTION_10D",
            "P_REBOUND_10D",
            "HMM_CONF",
            "entry_step_safe",
            "conviction_safe",
        ]
        thresholds = thresholds_for_keys(dates, series, keys_for_thresholds)

    values = {k: get_value(series, k, idx) for k in thresholds.keys()}

    ts_state = bucket(values["TS_50"], thresholds["TS_50"], ["p30", "p70"], ["negativ", "neutru", "pozitiv"])
    band_w_state = bucket(
        values["band_w"], thresholds["band_w"], ["p30", "p70", "p90"], ["calm", "normal", "tensionat", "extrem"]
    )
    band_pos_state = bucket(
        values["band_pos"], thresholds["band_pos"], ["p30", "p70"], ["inferior", "median", "superior"]
    )
    range_state = bucket(
        values["range_score"], thresholds["range_score"], ["p30", "p70"], ["low", "medium", "high"]
    )
    corr_state = bucket(
        values["P_CORRECTION_10D"], thresholds["P_CORRECTION_10D"], ["p30", "p70"], ["low", "medium", "high"]
    )
    reb_state = bucket(
        values["P_REBOUND_10D"], thresholds["P_REBOUND_10D"], ["p30", "p70"], ["low", "medium", "high"]
    )
    conf_state = classify_hmm_conf(values["HMM_CONF"], thresholds["HMM_CONF"])
    hmm_conf_low = is_hmm_conf_low(values["HMM_CONF"], thresholds["HMM_CONF"])
    step_state = bucket(
        values["entry_step_safe"], thresholds["entry_step_safe"], ["p30", "p70"], ["mic", "mediu", "mare"]
    )
    conv_state = bucket(
        values["conviction_safe"], thresholds["conviction_safe"], ["p30", "p70"], ["scazuta", "medie", "ridicata"]
    )

    label_map = hmm_labels(features)
    hmm_dom_val = get_value(series, "HMM_DOM", idx)
    hmm_dom = int(hmm_dom_val) if is_finite(hmm_dom_val) else None
    dominant_label = label_map.get(hmm_dom, f"STATE_{hmm_dom}" if hmm_dom is not None else "necunoscut")

    probs = hmm_state_probs(series, idx)
    alt_label = None
    if len(probs) > 1:
        alt_label = label_map.get(probs[1][0], f"STATE_{probs[1][0]}")

    onchain_amount_state = None
    onchain_large_active = False
    onchain_small_active = False
    onchain_amount_key = None
    onchain_large_share_key = None
    onchain_small_share_key = None
    onchain_keys = onchain_keys_used[:] if onchain_keys_used else []
    if onchain and onchain.get("series"):
        onchain_series = onchain.get("series", {})
        if not onchain_keys:
            onchain_keys = select_onchain_keys(onchain_series)
        onchain_thresholds_local = onchain_thresholds
        if onchain_thresholds_local is None and onchain_keys:
            onchain_thresholds_local = thresholds_for_keys(
                onchain.get("dates", []),
                onchain_series,
                onchain_keys,
            )
        if onchain_thresholds_local is None:
            onchain_thresholds_local = {}

        onchain_amount_key = select_amount_key(onchain_keys)
        if onchain_amount_key:
            amount_val = get_value(onchain_series, onchain_amount_key, idx)
            onchain_amount_state = state_from_thresholds(
                amount_val, onchain_thresholds_local.get(onchain_amount_key, {})
            )

        onchain_large_share_key = select_share_key(onchain_keys, "large")
        onchain_small_share_key = select_share_key(onchain_keys, "small")
        if onchain_large_share_key:
            large_val = get_value(onchain_series, onchain_large_share_key, idx)
            large_state = state_from_thresholds(
                large_val, onchain_thresholds_local.get(onchain_large_share_key, {})
            )
            onchain_large_active = large_state == "high"
        if onchain_small_share_key:
            small_val = get_value(onchain_series, onchain_small_share_key, idx)
            small_state = state_from_thresholds(
                small_val, onchain_thresholds_local.get(onchain_small_share_key, {})
            )
            onchain_small_active = small_state == "high"

    return {
        "date": dates[idx] if dates else None,
        "ts_label": ts_state,
        "band_w_label": band_w_state,
        "band_pos_label": band_pos_state,
        "range_label": range_state,
        "corr_label": corr_state,
        "reb_label": reb_state,
        "regime_dom": dominant_label,
        "regime_alt": alt_label,
        "regime_clarity": conf_state,
        "hmm_conf": values["HMM_CONF"],
        "hmm_conf_low": hmm_conf_low,
        "hmm_dom": hmm_dom,
        "step_label": step_state,
        "conviction_label": conv_state,
        "onchain_activity_label": onchain_amount_state,
        "onchain_large_active": onchain_large_active,
        "onchain_small_active": onchain_small_active,
        "onchain_amount_key": onchain_amount_key,
        "onchain_large_share_key": onchain_large_share_key,
        "onchain_small_share_key": onchain_small_share_key,
        "onchain_keys_used": onchain_keys,
    }


def build_regime_text(dominant: str, conf_state: str, alt_label: Optional[str]) -> str:
    conf_phrase = {"clar": "clara", "ambiguu": "ambigua"}.get(conf_state, conf_state)
    sentence = f"Dominanta HMM sugereaza un regim {dominant}, cu incredere {conf_phrase}."
    if not alt_label:
        return sentence
    if conf_state == "ambiguu":
        return f"{sentence} Alternative precum {alt_label} raman relevante, deci contextul este mixt."
    return f"{sentence} Alternativa principala ramane {alt_label}, dar cu o pondere vizibil mai mica."


def build_trend_text(ts_state: str, band_pos_state: str, range_state: str) -> str:
    if "necunoscut" in (ts_state, band_pos_state, range_state):
        return "Date insuficiente pentru un rezumat clar al trendului si pozitionarii."
    range_desc = {"low": "scazuta", "medium": "moderata", "high": "ridicata"}
    range_ctx = {"low": "mai directional", "medium": "echilibrat", "high": "mai lateral"}
    band_pos_desc = {"inferior": "inferioara", "median": "mediana", "superior": "superioara"}
    sentence1 = (
        f"TS_50 sugereaza un bias {ts_state}, iar pozitionarea in banda este {band_pos_desc[band_pos_state]}."
    )
    sentence2 = (
        f"range_score este {range_desc[range_state]}, iar contextul pare {range_ctx[range_state]}."
    )
    return f"{sentence1} {sentence2}"


def build_tension_text(band_w_state: str) -> str:
    if band_w_state == "necunoscut":
        return "Date insuficiente pentru tensiune si volatilitate."
    band_desc = {"calm": "calma", "normal": "normala", "tensionat": "tensionata", "extrem": "extrema"}
    vol_desc = {
        "calm": "volatilitate mai redusa",
        "normal": "volatilitate moderata",
        "tensionat": "volatilitate in crestere",
        "extrem": "volatilitate foarte ridicata",
    }
    return (
        f"Latimea benzii este {band_desc[band_w_state]}, ceea ce sugereaza {vol_desc[band_w_state]}."
    )


def build_risk_text(corr_state: str) -> str:
    if corr_state == "necunoscut":
        return "Date insuficiente pentru evaluarea riscului advers."
    level_desc = {"low": "scazuta", "medium": "moderata", "high": "ridicata"}
    risk_desc = {"low": "scazut", "medium": "moderat", "high": "ridicat"}
    return (
        f"P_CORRECTION_10D este {level_desc[corr_state]}, iar riscul advers pare {risk_desc[corr_state]}."
    )


def build_rebound_text(reb_state: str) -> str:
    if reb_state == "necunoscut":
        return "Date insuficiente pentru elasticitate pozitiva."
    level_desc = {"low": "scazuta", "medium": "moderata", "high": "ridicata"}
    elastic_desc = {"low": "limitata", "medium": "moderata", "high": "ridicata"}
    return (
        f"P_REBOUND_10D este {level_desc[reb_state]}, ceea ce sugereaza o elasticitate pozitiva {elastic_desc[reb_state]}."
    )


def build_decision_text(conv_state: str, step_state: str) -> str:
    if "necunoscut" in (conv_state, step_state):
        return "Date insuficiente pentru o formulare SAFE coerenta."
    if conv_state == "ridicata" and step_state == "mare":
        posture = "mai permisiva"
    elif conv_state == "scazuta" and step_state == "mic":
        posture = "prudenta"
    else:
        posture = "graduala"
    sentence1 = (
        f"Convictia SAFE este {conv_state}, iar marimea pasilor de ajustare este {step_state}."
    )
    sentence2 = f"SAFE prefera o postura {posture}, in linie cu acest context."
    return f"{sentence1} {sentence2}"


def build_safe_context(
    features: Dict,
    date: Optional[str] = None,
    onchain: Optional[Dict] = None,
    years: Optional[int] = None,
) -> Tuple[str, Dict]:
    aligned_features, aligned_onchain, aligned_dates = align_payloads(features, onchain)
    dates = aligned_features.get("dates", [])
    series = aligned_features.get("series", {})
    if not dates or not series:
        raise ValueError("features must include 'dates' and 'series'.")

    if date is None:
        idx = len(dates) - 1
    else:
        try:
            idx = dates.index(date)
        except ValueError as exc:
            raise ValueError(f"Date not found in features: {date}") from exc

    date_subset = None
    if years is not None and years > 0:
        anchor = date if date is not None else dates[-1]
        date_subset = parse_years_window_dates(dates, anchor, years)
        if not date_subset:
            date_subset = None

    keys_for_thresholds = [
        "TS_50",
        "band_w",
        "band_pos",
        "range_score",
        "P_CORRECTION_10D",
        "P_REBOUND_10D",
        "HMM_CONF",
        "entry_step_safe",
        "conviction_safe",
    ]
    thresholds = thresholds_for_keys(dates, series, keys_for_thresholds, date_subset=date_subset)

    onchain_keys_used: List[str] = []
    onchain_thresholds: Dict[str, Dict[str, float]] = {}
    if aligned_onchain is not None:
        onchain_series = aligned_onchain.get("series", {})
        onchain_keys_used = select_onchain_keys(onchain_series) if onchain_series else []
        if onchain_keys_used:
            onchain_thresholds = thresholds_for_keys(
                aligned_onchain.get("dates", []),
                onchain_series,
                onchain_keys_used,
                date_subset=date_subset,
            )

    facts = compute_facts_for_day(
        aligned_features,
        idx,
        thresholds=thresholds,
        onchain=aligned_onchain,
        onchain_thresholds=onchain_thresholds,
        onchain_keys_used=onchain_keys_used,
    )

    ts_state = facts["ts_label"]
    band_w_state = facts["band_w_label"]
    band_pos_state = facts["band_pos_label"]
    range_state = facts["range_label"]
    corr_state = facts["corr_label"]
    reb_state = facts["reb_label"]
    conf_state = facts["regime_clarity"]
    hmm_conf_low = facts["hmm_conf_low"]
    dominant_label = facts["regime_dom"]
    alt_label = facts["regime_alt"]
    onchain_amount_state = facts["onchain_activity_label"]
    onchain_large_active = facts["onchain_large_active"]
    onchain_small_active = facts["onchain_small_active"]
    onchain_amount_key = facts["onchain_amount_key"]
    onchain_large_share_key = facts["onchain_large_share_key"]
    onchain_small_share_key = facts["onchain_small_share_key"]

    onchain_text: Optional[str] = None
    if aligned_onchain is not None:
        structure_sentence = build_onchain_structure_sentence(
            onchain_large_active, onchain_small_active
        )
        has_onchain_data = bool(
            onchain_amount_key or onchain_large_share_key or onchain_small_share_key
        )
        onchain_text = build_onchain_text(onchain_amount_state, structure_sentence, has_onchain_data)

    warnings: List[str] = []
    if dominant_label == "CORE" and band_w_state == "extrem":
        warnings.append("CORE cu band_w extrem indica un mix neobisnuit intre stabilitate si tensiune.")
    if dominant_label == "SHOCK" and ts_state == "pozitiv":
        warnings.append("SHOCK cu TS_50 pozitiv sugereaza o disonanta intre regim si trend.")
    if corr_state == "high" and reb_state == "high":
        warnings.append("P_CORRECTION_10D mare si P_REBOUND_10D mare indica presiuni in ambele directii.")
    if hmm_conf_low and hmm_dom_changed_recently(series, idx):
        warnings.append("HMM_CONF mic cu schimbare recenta de HMM_DOM indica un regim in tranzitie.")
    if onchain_text is not None:
        if band_w_state in ("tensionat", "extrem") and onchain_amount_state == "low":
            warnings.append("Volatilitate ridicata fara suport on-chain.")
        if dominant_label == "SHOCK" and onchain_large_active:
            warnings.append("Stres structural sustinut de fluxuri mari.")
        if dominant_label == "SURGE" and onchain_amount_state == "high":
            warnings.append("Miscare populata; oportunitate + risc.")

    lines = [
        f"SAFE Daily Context – {dates[idx]}",
        "(generat de SAFE Narator)",
        "",
        "Regime:",
        build_regime_text(dominant_label, conf_state, alt_label),
        "Trend & Poziționare:",
        build_trend_text(ts_state, band_pos_state, range_state),
        "Tensiune & Volatilitate:",
        build_tension_text(band_w_state),
        "Risc Advers:",
        build_risk_text(corr_state),
        "Elasticitate Pozitivă:",
        build_rebound_text(reb_state),
    ]

    if onchain_text is not None:
        lines.extend(["On-chain Activity & Structure:", onchain_text])

    lines.extend([
        "Decizie SAFE:",
        build_decision_text(facts["conviction_label"], facts["step_label"]),
    ])

    if warnings:
        lines.extend(["Atenționări:", " ".join(warnings)])

    debug = {
        "features_thresholds": thresholds,
        "onchain_thresholds": onchain_thresholds,
        "onchain_keys_used": onchain_keys_used,
        "aligned_dates": aligned_dates,
    }
    return "\n".join(lines), {"facts": facts, "debug": debug}


def narrate_safe_context(
    features: dict,
    date: Optional[str] = None,
    onchain: Optional[dict] = None,
    years: Optional[int] = None,
    return_facts: bool = False,
) -> object:
    text, meta = build_safe_context(features, date, onchain, years=years)
    facts = meta.get("facts", {})
    if return_facts:
        return text, facts
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Narrate SAFE context from features.json.")
    parser.add_argument("--asset", default="btc", help="Asset symbol (default: btc)")
    parser.add_argument(
        "--features-json",
        default=None,
        help="Path to features.json (default: out/<asset>/features.json)",
    )
    parser.add_argument(
        "--onchain-json",
        default=None,
        help="Path to onchain_features.json (default: out/<asset>/onchain_features.json)",
    )
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD format")
    parser.add_argument("--years", type=int, default=None, help="Use last N years for thresholds")
    parser.add_argument("--debug", action="store_true", help="Print on-chain keys and thresholds")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parents[2] / "out" / args.asset
    features_path = args.features_json or str(base_dir / "features.json")
    onchain_path = args.onchain_json or str(base_dir / "onchain_features.json")

    features = load_series_json(features_path)
    onchain = None
    try:
        onchain = load_series_json(onchain_path)
    except FileNotFoundError:
        onchain = None

    text, meta = build_safe_context(features, args.date, onchain, years=args.years)
    debug = meta.get("debug", {})
    if args.debug:
        print(f"onchain_keys_used: {debug.get('onchain_keys_used', [])}")
        print("features_thresholds:")
        print(json.dumps(debug.get("features_thresholds", {}), indent=2, sort_keys=True))
        if debug.get("onchain_thresholds"):
            print("onchain_thresholds:")
            print(json.dumps(debug.get("onchain_thresholds", {}), indent=2, sort_keys=True))
    print(text)


if __name__ == "__main__":
    main()
