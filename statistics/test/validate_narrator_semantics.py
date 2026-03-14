#!/usr/bin/env python3

# -----------------------------------------------------------------------------
# NARRATOR VALIDATION FRAMEWORK
#
# This script validates the SAFE narrator along two independent axes:
#
# 1) TRUTH CHECK (semantic invariants)
#    - each label must match the quantile rule exactly
#    - the narrator must not overstate textually
#
# 2) RELEVANCE CHECK (empirical sanity)
#    - labels should separate contexts with different forward behavior
#    - evaluation on:
#        * forward returns
#        * max drawdown
#        * volatility
#
# OPTIONAL:
# 3) BOOTSTRAP SIGN CONSISTENCY
#    - checks sign stability of differences
#    - avoids conclusions driven by outliers
#
# IMPORTANT:
# - FAIL means a real regression (semantic or empirical)
# - SKIP means "no declared expectations" (not an error)
#
# -----------------------------------------------------------------------------

"""
Validate SAFE narrator semantics.
Modes:
  --mode truth     Check narrator facts vs computed discretization for a given date
  --mode relevance Compute forward stats for narrative tags across full history
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.util import safe_narrator as sn


def parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def slice_payload(payload: Optional[Dict], idxs: List[int]) -> Optional[Dict]:
    if payload is None:
        return None
    dates = payload.get("dates", [])
    series = payload.get("series", {})
    new_dates = [dates[i] for i in idxs if i < len(dates)]
    new_series = {}
    for key, values in series.items():
        new_series[key] = [values[i] if i < len(values) else None for i in idxs]
    return {"dates": new_dates, "series": new_series, "meta": payload.get("meta", {})}


def align_and_filter(
    features: Dict, onchain: Optional[Dict], _years: Optional[int]
) -> Tuple[Dict, Optional[Dict]]:
    aligned_features, aligned_onchain, _ = sn.align_payloads(features, onchain)
    return aligned_features, aligned_onchain


def load_payloads(
    asset: str, features_json: Optional[str], onchain_json: Optional[str]
) -> Tuple[Dict, Optional[Dict], Path, Path]:
    base_dir = ROOT / "out" / asset
    if features_json:
        features_path = Path(features_json)
        if not features_path.is_absolute():
            features_path = ROOT / features_path
    else:
        features_path = base_dir / "features.json"
    if onchain_json:
        onchain_path = Path(onchain_json)
        if not onchain_path.is_absolute():
            onchain_path = ROOT / onchain_path
    else:
        onchain_path = base_dir / "onchain_features.json"

    features = sn.load_series_json(str(features_path))
    onchain = None
    if onchain_path.exists():
        onchain = sn.load_series_json(str(onchain_path))
    return features, onchain, features_path, onchain_path


def safe_log_return(c0: float, c1: float) -> Optional[float]:
    if not sn.is_finite(c0) or not sn.is_finite(c1) or c0 <= 0 or c1 <= 0:
        return None
    return math.log(c1 / c0)


def compute_forward_metrics(closes: List[float], idx: int, horizon: int) -> Dict[str, Optional[float]]:
    out = {"fwd1": None, "fwd5": None, "fwd10": None, "mdd": None, "vol": None}
    n = len(closes)

    def fwd(h: int) -> Optional[float]:
        if idx + h >= n:
            return None
        return safe_log_return(closes[idx], closes[idx + h])

    out["fwd1"] = fwd(1)
    out["fwd5"] = fwd(5)
    out["fwd10"] = fwd(horizon)

    if idx + horizon >= n:
        return out

    window = closes[idx : idx + horizon + 1]
    if any(not sn.is_finite(x) for x in window):
        return out

    peak = window[0]
    mdd = 0.0
    for value in window:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > mdd:
                mdd = dd
    out["mdd"] = mdd

    rets = []
    for i in range(1, len(window)):
        r = safe_log_return(window[i - 1], window[i])
        if r is not None:
            rets.append(r)
    if len(rets) >= 2:
        out["vol"] = statistics.stdev(rets) * math.sqrt(365.0)
    elif len(rets) == 1:
        out["vol"] = 0.0
    return out


def format_float(value: Optional[float]) -> str:
    if value is None or not sn.is_finite(value):
        return "n/a"
    return f"{value:.6g}"


def narr_phrase(label: Optional[str], kind: str) -> str:
    if label is None:
        return "n/a"
    if kind == "ts":
        return f"bias {label}"
    if kind == "band_pos":
        return f"pozitionare {label}"
    if kind == "band_w":
        return f"latime {label}"
    if kind == "range":
        return f"range_score {label}"
    if kind == "corr":
        mapping = {"low": "scazuta", "medium": "moderata", "high": "ridicata"}
        return f"P_CORRECTION_10D {mapping.get(label, label)}"
    if kind == "reb":
        mapping = {"low": "scazuta", "medium": "moderata", "high": "ridicata"}
        return f"P_REBOUND_10D {mapping.get(label, label)}"
    if kind == "conf":
        mapping = {"clar": "clara", "ambiguu": "ambigua"}
        return f"incredere {mapping.get(label, label)}"
    if kind == "step":
        return f"pas {label}"
    if kind == "conviction":
        return f"convictie {label}"
    if kind == "onchain":
        mapping = {
            "low": "Activitate redusa",
            "medium": "Activitate moderata",
            "high": "Activitate ridicata",
        }
        return mapping.get(label, label)
    if kind == "regime":
        return f"regim {label}"
    return label


# NOTE:
# Truth check is a point-in-time test. Missing dates or incomplete series
# should be treated as a soft stop for this mode rather than a semantic failure.
def run_truth_check(args: argparse.Namespace) -> int:
    if not args.date:
        print("Missing --date for truth check.")
        return 1

    features, onchain, _, _ = load_payloads(args.asset, args.features_json, args.onchain_json)
    features, onchain = align_and_filter(features, onchain, args.years)
    dates = features.get("dates", [])
    series = features.get("series", {})
    if args.date not in dates:
        print(f"Date {args.date} not found after alignment/filtering.")
        return 1
    idx = dates.index(args.date)

    date_subset = None
    if args.years:
        date_subset = sn.parse_years_window_dates(dates, args.date, args.years)
        if not date_subset:
            date_subset = None

    thresholds = sn.thresholds_for_keys(
        dates,
        series,
        [
            "TS_50",
            "band_w",
            "band_pos",
            "range_score",
            "P_CORRECTION_10D",
            "P_REBOUND_10D",
            "HMM_CONF",
            "entry_step_safe",
            "conviction_safe",
        ],
        date_subset=date_subset,
    )

    onchain_keys_used = []
    onchain_thresholds = {}
    if onchain and onchain.get("series"):
        onchain_keys_used = sn.select_onchain_keys(onchain["series"])
        if onchain_keys_used:
            onchain_thresholds = sn.thresholds_for_keys(
                onchain.get("dates", []),
                onchain["series"],
                onchain_keys_used,
                date_subset=date_subset,
            )

    text, facts = sn.narrate_safe_context(features, args.date, onchain, return_facts=True)

    values = {k: sn.get_value(series, k, idx) for k in thresholds.keys()}
    expected = {
        "ts_label": sn.discretize_value(
            values["TS_50"], thresholds["TS_50"], ["p30", "p70"], ["negativ", "neutru", "pozitiv"]
        ),
        "band_w_label": sn.discretize_value(
            values["band_w"],
            thresholds["band_w"],
            ["p30", "p70", "p90"],
            ["calm", "normal", "tensionat", "extrem"],
        ),
        "band_pos_label": sn.discretize_value(
            values["band_pos"], thresholds["band_pos"], ["p30", "p70"], ["inferior", "median", "superior"]
        ),
        "range_label": sn.discretize_value(
            values["range_score"], thresholds["range_score"], ["p30", "p70"], ["low", "medium", "high"]
        ),
        "corr_label": sn.discretize_value(
            values["P_CORRECTION_10D"],
            thresholds["P_CORRECTION_10D"],
            ["p30", "p70"],
            ["low", "medium", "high"],
        ),
        "reb_label": sn.discretize_value(
            values["P_REBOUND_10D"],
            thresholds["P_REBOUND_10D"],
            ["p30", "p70"],
            ["low", "medium", "high"],
        ),
        "regime_clarity": sn.classify_hmm_conf(values["HMM_CONF"], thresholds["HMM_CONF"]),
        "step_label": sn.discretize_value(
            values["entry_step_safe"],
            thresholds["entry_step_safe"],
            ["p30", "p70"],
            ["mic", "mediu", "mare"],
        ),
        "conviction_label": sn.discretize_value(
            values["conviction_safe"],
            thresholds["conviction_safe"],
            ["p30", "p70"],
            ["scazuta", "medie", "ridicata"],
        ),
    }

    label_map = sn.hmm_labels(features)
    hmm_dom_val = sn.get_value(series, "HMM_DOM", idx)
    hmm_dom = int(hmm_dom_val) if sn.is_finite(hmm_dom_val) else None
    expected["regime_dom"] = label_map.get(
        hmm_dom, f"STATE_{hmm_dom}" if hmm_dom is not None else "necunoscut"
    )

    amount_key = sn.select_amount_key(onchain_keys_used) if onchain_keys_used else None
    if onchain and amount_key:
        amount_val = sn.get_value(onchain["series"], amount_key, idx)
        expected["onchain_activity_label"] = sn.state_from_thresholds(
            amount_val, onchain_thresholds.get(amount_key, {})
        )
    else:
        expected["onchain_activity_label"] = None

    print(f"=== TRUTH CHECK – {args.date} ===")
    all_ok = True

    def check(
        name: str,
        value: Optional[float],
        thresholds_local: Optional[Dict[str, float]],
        expected_label: Optional[str],
        fact_key: str,
        phrase_kind: str,
    ) -> None:
        nonlocal all_ok
        narrator_label = facts.get(fact_key)
        status = "OK" if expected_label == narrator_label else "FAIL"
        if status != "OK":
            all_ok = False
        if thresholds_local:
            p30 = thresholds_local.get("p30")
            p70 = thresholds_local.get("p70")
            print(
                f"{name}: value={format_float(value)}, p30={format_float(p30)}, "
                f"p70={format_float(p70)} -> label={expected_label} [{status}] "
                f'narrator: "{narr_phrase(narrator_label, phrase_kind)}"'
            )
        else:
            print(
                f"{name}: value={format_float(value)} -> label={expected_label} [{status}] "
                f'narrator: "{narr_phrase(narrator_label, phrase_kind)}"'
            )

    check("TS_50", values["TS_50"], thresholds["TS_50"], expected["ts_label"], "ts_label", "ts")
    check("band_w", values["band_w"], thresholds["band_w"], expected["band_w_label"], "band_w_label", "band_w")
    check(
        "band_pos",
        values["band_pos"],
        thresholds["band_pos"],
        expected["band_pos_label"],
        "band_pos_label",
        "band_pos",
    )
    check(
        "range_score",
        values["range_score"],
        thresholds["range_score"],
        expected["range_label"],
        "range_label",
        "range",
    )
    check(
        "P_CORRECTION_10D",
        values["P_CORRECTION_10D"],
        thresholds["P_CORRECTION_10D"],
        expected["corr_label"],
        "corr_label",
        "corr",
    )
    check(
        "P_REBOUND_10D",
        values["P_REBOUND_10D"],
        thresholds["P_REBOUND_10D"],
        expected["reb_label"],
        "reb_label",
        "reb",
    )
    check("HMM_CONF", values["HMM_CONF"], thresholds["HMM_CONF"], expected["regime_clarity"], "regime_clarity", "conf")

    check(
        "HMM_DOM",
        hmm_dom_val,
        None,
        expected["regime_dom"],
        "regime_dom",
        "regime",
    )
    check(
        "entry_step_safe",
        values["entry_step_safe"],
        thresholds["entry_step_safe"],
        expected["step_label"],
        "step_label",
        "step",
    )
    check(
        "conviction_safe",
        values["conviction_safe"],
        thresholds["conviction_safe"],
        expected["conviction_label"],
        "conviction_label",
        "conviction",
    )

    if expected["onchain_activity_label"] is not None:
        check(
            "onchain_activity",
            None,
            None,
            expected["onchain_activity_label"],
            "onchain_activity_label",
            "onchain",
        )
    else:
        print("onchain_activity: n/a (no on-chain data)")

    if all_ok:
        print("[SUCCESS] all claims consistent")
        return 0
    print("[FAIL] mismatched facts vs discretization")
    return 1


def summarize(values: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    return statistics.mean(values), statistics.median(values)


def bootstrap_sign_consistency(
    values: List[float],
    base_mean: Optional[float],
    expectation: str,
    n_bootstrap: int,
    rng: random.Random,
) -> Optional[float]:
    if not values or base_mean is None or n_bootstrap <= 0:
        return None
    n = len(values)
    if n == 0:
        return None
    sign_match = 0
    for _ in range(n_bootstrap):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        mean_sample = statistics.mean(sample)
        delta = mean_sample - base_mean
        if expectation == "higher" and delta > 0:
            sign_match += 1
        elif expectation == "lower" and delta < 0:
            sign_match += 1
    return sign_match / n_bootstrap if n_bootstrap > 0 else None


def evaluate_expectations(
    tag_stats: Dict[str, Optional[float]],
    baseline_stats: Dict[str, Optional[float]],
    expectations: Dict[str, Optional[str]],
    eps: float = 1e-6,
    min_delta: Optional[float] = None,
) -> List[Dict[str, object]]:
    delta_threshold = 0.0 if min_delta is None else min_delta
    results = []
    for metric, direction in expectations.items():
        if direction is None:
            results.append(
                {"metric": metric, "direction": None, "delta": None, "status": "SKIP"}
            )
            continue
        tag_value = tag_stats.get(metric)
        base_value = baseline_stats.get(metric)
        if tag_value is None or base_value is None:
            results.append(
                {"metric": metric, "direction": direction, "delta": None, "status": "SKIP"}
            )
            continue
        delta = tag_value - base_value
        if abs(delta) <= max(delta_threshold, eps):
            status = "WEAK"
        elif direction == "higher":
            status = "PASS" if delta > 0 else "FAIL"
        elif direction == "lower":
            status = "PASS" if delta < 0 else "FAIL"
        else:
            status = "SKIP"
        results.append(
            {"metric": metric, "direction": direction, "delta": delta, "status": status}
        )
    return results


def run_relevance_check(args: argparse.Namespace) -> int:
    features, onchain, _, _ = load_payloads(args.asset, args.features_json, args.onchain_json)
    features, onchain = align_and_filter(features, onchain, args.years)
    dates = features.get("dates", [])
    series = features.get("series", {})

    if "close" not in series:
        print("Missing 'close' in features.json series.")
        return 1

    date_subset = None
    if args.years:
        anchor = dates[-1] if dates else None
        date_subset = sn.parse_years_window_dates(dates, anchor, args.years)
        if not date_subset:
            date_subset = None

    thresholds = sn.thresholds_for_keys(
        dates,
        series,
        [
            "TS_50",
            "band_w",
            "band_pos",
            "range_score",
            "P_CORRECTION_10D",
            "P_REBOUND_10D",
            "HMM_CONF",
            "entry_step_safe",
            "conviction_safe",
        ],
        date_subset=date_subset,
    )

    onchain_keys_used = []
    onchain_thresholds = {}
    if onchain and onchain.get("series"):
        onchain_keys_used = sn.select_onchain_keys(onchain["series"])
        if onchain_keys_used:
            onchain_thresholds = sn.thresholds_for_keys(
                onchain.get("dates", []),
                onchain["series"],
                onchain_keys_used,
                date_subset=date_subset,
            )

    closes = [float(v) if sn.is_finite(v) else None for v in series.get("close", [])]
    records = []
    for idx in range(len(dates)):
        metrics = compute_forward_metrics(closes, idx, args.horizon)
        if metrics["fwd10"] is None:
            continue
        facts = sn.compute_facts_for_day(
            features,
            idx,
            thresholds=thresholds,
            onchain=onchain,
            onchain_thresholds=onchain_thresholds,
            onchain_keys_used=onchain_keys_used,
        )
        records.append({"facts": facts, "metrics": metrics})

    baseline = {
        "fwd1": [r["metrics"]["fwd1"] for r in records if r["metrics"]["fwd1"] is not None],
        "fwd5": [r["metrics"]["fwd5"] for r in records if r["metrics"]["fwd5"] is not None],
        "fwd10": [r["metrics"]["fwd10"] for r in records if r["metrics"]["fwd10"] is not None],
        "mdd": [r["metrics"]["mdd"] for r in records if r["metrics"]["mdd"] is not None],
        "vol": [r["metrics"]["vol"] for r in records if r["metrics"]["vol"] is not None],
    }

    base_mean_fwd10, base_med_fwd10 = summarize(baseline["fwd10"])
    base_mean_mdd, _ = summarize(baseline["mdd"])
    base_mean_vol, _ = summarize(baseline["vol"])

    print(f"=== RELEVANCE CHECK (horizon={args.horizon}d) ===")
    print(
        f"Baseline: mean_fwd10={format_float(base_mean_fwd10)}, "
        f"median_fwd10={format_float(base_med_fwd10)}, "
        f"mean_mdd{args.horizon}={format_float(base_mean_mdd)}, "
        f"mean_vol{args.horizon}={format_float(base_mean_vol)}"
    )

    # EXPECTATIONS DESIGN NOTE:
    #
    # Expectations are deliberately conservative.
    # Many tags are None (SKIP) to avoid narrative overfitting.
    #
    # Principle:
    #   Better SKIP than a false FAIL.
    #
    # Expectations should be tightened only after stable empirical
    # confirmation (multiple windows + bootstrap).
    expectations_table = {
        "bandw_extreme": {"mean_vol10": "higher", "mean_mdd10": "higher", "mean_fwd10": None},
        "regime_SURGE": {"mean_vol10": "higher", "mean_mdd10": None, "mean_fwd10": "higher"},
        "regime_SHOCK": {"mean_vol10": "higher", "mean_mdd10": "higher", "mean_fwd10": None},
        "corr_high": {"mean_vol10": "higher", "mean_mdd10": None, "mean_fwd10": None},
        "reb_high": {"mean_vol10": None, "mean_mdd10": None, "mean_fwd10": "higher"},
        "conf_amb": {"mean_vol10": "lower", "mean_mdd10": None, "mean_fwd10": "lower"},
        "onchain_low": {"mean_vol10": None, "mean_mdd10": None, "mean_fwd10": None},
    }

    tag_predicates = {
        "corr_high": lambda f: f.get("corr_label") == "high",
        "reb_high": lambda f: f.get("reb_label") == "high",
        "conf_amb": lambda f: f.get("regime_clarity") == "ambiguu",
        "bandw_extreme": lambda f: f.get("band_w_label") == "extrem",
        "regime_CORE": lambda f: f.get("regime_dom") == "CORE",
        "regime_DRIFT": lambda f: f.get("regime_dom") == "DRIFT",
        "regime_SURGE": lambda f: f.get("regime_dom") == "SURGE",
        "regime_SHOCK": lambda f: f.get("regime_dom") == "SHOCK",
    }
    if onchain_keys_used:
        tag_predicates["onchain_low"] = lambda f: f.get("onchain_activity_label") == "low"

    expected_notes = {
        "corr_high": "expected: worse mdd, higher vol",
        "bandw_extreme": "expected: higher vol, worse mdd",
        "regime_SHOCK": "expected: worse mdd, higher vol",
        "regime_SURGE": "expected: higher returns, higher vol",
    }

    baseline_stats = {
        "mean_fwd10": base_mean_fwd10,
        "mean_mdd10": base_mean_mdd,
        "mean_vol10": base_mean_vol,
    }
    rng = random.Random(1337)
    tags_passed = 0
    tags_failed = 0
    tags_weak = 0

    rows = []
    for tag, predicate in tag_predicates.items():
        subset = [r for r in records if predicate(r["facts"])]
        fwd1_vals = [r["metrics"]["fwd1"] for r in subset if r["metrics"]["fwd1"] is not None]
        fwd5_vals = [r["metrics"]["fwd5"] for r in subset if r["metrics"]["fwd5"] is not None]
        fwd10_vals = [r["metrics"]["fwd10"] for r in subset if r["metrics"]["fwd10"] is not None]
        mdd_vals = [r["metrics"]["mdd"] for r in subset if r["metrics"]["mdd"] is not None]
        vol_vals = [r["metrics"]["vol"] for r in subset if r["metrics"]["vol"] is not None]

        mean_fwd1, _ = summarize(fwd1_vals)
        mean_fwd5, _ = summarize(fwd5_vals)
        mean_fwd10, med_fwd10 = summarize(fwd10_vals)
        mean_mdd, _ = summarize(mdd_vals)
        mean_vol, _ = summarize(vol_vals)

        n = len(fwd10_vals)
        low_sample = " low sample" if n < 50 else ""
        print(f"Tag: {tag} (N={n}){low_sample}")
        print(
            f"  mean_fwd1={format_float(mean_fwd1)} "
            f"mean_fwd5={format_float(mean_fwd5)} "
            f"mean_fwd10={format_float(mean_fwd10)} "
            f"(Δ vs base {format_float(None if mean_fwd10 is None or base_mean_fwd10 is None else mean_fwd10 - base_mean_fwd10)})"
        )
        print(
            f"  median_fwd10={format_float(med_fwd10)} "
            f"mean_mdd{args.horizon}={format_float(mean_mdd)} "
            f"(Δ {format_float(None if mean_mdd is None or base_mean_mdd is None else mean_mdd - base_mean_mdd)}) "
            f"mean_vol{args.horizon}={format_float(mean_vol)} "
            f"(Δ {format_float(None if mean_vol is None or base_mean_vol is None else mean_vol - base_mean_vol)})"
        )
        note = expected_notes.get(tag)
        if note:
            print(f"  {note}")

        tag_stats = {
            "mean_fwd10": mean_fwd10,
            "mean_mdd10": mean_mdd,
            "mean_vol10": mean_vol,
        }
        expectations = expectations_table.get(
            tag, {"mean_vol10": None, "mean_mdd10": None, "mean_fwd10": None}
        )
        results = evaluate_expectations(
            tag_stats,
            baseline_stats,
            expectations,
            min_delta=args.min_delta,
        )
        detail_chunks = []
        pass_count = 0
        fail_count = 0
        weak_count = 0
        total_count = 0
        for res in results:
            metric = res["metric"]
            direction = res["direction"]
            status = res["status"]
            delta = res["delta"]
            if direction is None or status == "SKIP":
                continue
            total_count += 1
            if status == "PASS":
                pass_count += 1
            elif status == "FAIL":
                fail_count += 1
            elif status == "WEAK":
                weak_count += 1

            metric_values = {
                "mean_fwd10": fwd10_vals,
                "mean_mdd10": mdd_vals,
                "mean_vol10": vol_vals,
            }.get(metric, [])
            sign_consistency = None
            if args.bootstrap > 0 and metric_values:
                sign_consistency = bootstrap_sign_consistency(
                    metric_values,
                    baseline_stats.get(metric),
                    direction,
                    args.bootstrap,
                    rng,
                )

            metric_label = {
                "mean_fwd10": "fwd10",
                "mean_mdd10": "mdd",
                "mean_vol10": "vol",
            }.get(metric, metric)
            delta_text = (
                "n/a" if delta is None else f"{delta:+.6g}"
            )
            detail = f"{metric_label} {status} (delta={delta_text}"
            if sign_consistency is not None:
                detail += f", sign_consistency={sign_consistency * 100:.0f}%"
            detail += ")"
            detail_chunks.append(detail)

        # Verdict semantics:
        # - PASS  : data confirms the expectation
        # - WEAK  : correct sign but small magnitude / small N
        # - SKIP  : no defined expectation
        # - FAIL  : empirical contradiction (regression)
        #
        # In --strict mode:
        #   FAIL => exit code != 0 (CI-friendly)
        if n < 30 and not args.strict_small:
            verdict = "WEAK/INSUFFICIENT"
            tags_weak += 1
        else:
            if total_count == 0:
                verdict = "SKIP"
                tags_weak += 1
            elif fail_count > 0:
                verdict = "FAIL"
                tags_failed += 1
            elif weak_count > 0:
                verdict = "WEAK"
                tags_weak += 1
            else:
                verdict = "PASS"
                tags_passed += 1

        details_text = " | details: " + ", ".join(detail_chunks) if detail_chunks else " | details: n/a"
        print(f"  Verdict: {verdict} ({pass_count}/{total_count}){details_text}")

        rows.append(
            {
                "tag": tag,
                "n": n,
                "mean_fwd1": mean_fwd1,
                "mean_fwd5": mean_fwd5,
                "mean_fwd10": mean_fwd10,
                "median_fwd10": med_fwd10,
                "mean_mdd": mean_mdd,
                "mean_vol": mean_vol,
                "delta_fwd10": None if mean_fwd10 is None or base_mean_fwd10 is None else mean_fwd10 - base_mean_fwd10,
                "delta_mdd": None if mean_mdd is None or base_mean_mdd is None else mean_mdd - base_mean_mdd,
                "delta_vol": None if mean_vol is None or base_mean_vol is None else mean_vol - base_mean_vol,
                "low_sample": n < 50,
            }
        )

    if args.out_csv:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "tag",
                "n",
                "mean_fwd1",
                "mean_fwd5",
                "mean_fwd10",
                "median_fwd10",
                "mean_mdd",
                "mean_vol",
                "delta_fwd10",
                "delta_mdd",
                "delta_vol",
                "low_sample",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote CSV: {args.out_csv}")

    print(f"Totals: tags_passed={tags_passed}, tags_failed={tags_failed}, tags_weak={tags_weak}")
    if args.strict and tags_failed > 0:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate SAFE narrator semantics.")
    parser.add_argument("--asset", default="btc", help="Asset symbol (default: btc)")
    parser.add_argument(
        "--mode",
        choices=["truth", "relevance"],
        default="relevance",
        help="Validation mode: truth or relevance (default: relevance)",
    )
    parser.add_argument("--date", default=None, help="Date for truth mode (YYYY-MM-DD)")
    parser.add_argument("--years", type=int, default=None, help="Use last N years for thresholds")
    parser.add_argument("--horizon", type=int, default=10, help="Forward horizon in days (relevance mode)")
    parser.add_argument("--features-json", default=None, help="Override features.json path")
    parser.add_argument("--onchain-json", default=None, help="Override onchain_features.json path")
    parser.add_argument("--out-csv", default=None, help="Write relevance summary to CSV")
    parser.add_argument("--bootstrap", type=int, default=0, help="Bootstrap iterations (default: 0)")
    parser.add_argument("--min-delta", type=float, default=0.0, help="Min delta for PASS")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any FAIL")
    parser.add_argument(
        "--strict-small",
        action="store_true",
        help="Treat low-sample tags as strict (no auto-WEAK)",
    )
    args = parser.parse_args()

    if args.mode == "truth":
        sys.exit(run_truth_check(args))
    sys.exit(run_relevance_check(args))


if __name__ == "__main__":
    main()
