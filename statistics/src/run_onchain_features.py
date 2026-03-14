#!/usr/bin/env python3
"""
run_onchain_features.py

Builds a small, interpretable on-chain feature set from:
- daily_amounts.json  : { "YYYY-MM-DD": <total_btc_transferred_float>, ... }
- daily_tx_size.json  : [ ["YYYY-MM-DD", b0, b1, ..., bN], ... ]  (counts per size bucket)

Outputs:
- out/onchain_features.json with:
  - dates: list[str]
  - series: dict[str, list[float|None]]
  - meta: basic info

Design goals:
- No modeling, no thresholds-as-signals.
- Robust to missing days / partial overlap.
- Keeps alignment by date so you can merge into the dashboard later.

Usage:
  python src/run_onchain_features.py \
    --amounts daily_amounts.json \
    --txsize daily_tx_size.json \
    --asset btc
"""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import math
from typing import Dict, List, Optional


def _load_amounts(path: Path) -> Dict[str, float]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path} must be a JSON object/dict of date->amount.")
    out: Dict[str, float] = {}
    for k, v in obj.items():
        if v is None:
            continue
        try:
            out[str(k)] = float(v)
        except Exception:
            continue
    return out


def _load_tx_size(path: Path) -> Dict[str, List[float]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(f"{path} must be a JSON array of rows like [date, ...counts].")
    out: Dict[str, List[float]] = {}
    for row in obj:
        if not isinstance(row, list) or len(row) < 2:
            continue
        date = str(row[0])
        vals: List[float] = []
        ok = True
        for x in row[1:]:
            try:
                vals.append(float(x))
            except Exception:
                ok = False
                break
        if ok:
            out[date] = vals
    return out


def _sorted_dates(*dicts) -> List[str]:
    keys = set()
    for d in dicts:
        keys.update(d.keys())
    return sorted(keys)


def _rolling_zscore(x: List[Optional[float]], window: int) -> List[Optional[float]]:
    """Trailing rolling z-score. For first (window-1) points returns None."""
    out: List[Optional[float]] = [None] * len(x)
    buf: List[float] = []
    for i, v in enumerate(x):
        if v is None or not math.isfinite(v):
            buf.append(float("nan"))
        else:
            buf.append(float(v))

        if i + 1 < window:
            continue

        w = buf[i + 1 - window : i + 1]
        w = [t for t in w if math.isfinite(t)]
        if len(w) < max(10, window // 5):
            out[i] = None
            continue

        mu = sum(w) / len(w)
        var = sum((t - mu) ** 2 for t in w) / max(1, (len(w) - 1))
        sd = math.sqrt(var) if var > 0 else 0.0
        if sd == 0.0:
            out[i] = 0.0
        else:
            out[i] = (float(v) - mu) / sd if (v is not None and math.isfinite(v)) else None
    return out


def _pct_change(x: List[Optional[float]]) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(x)
    prev: Optional[float] = None
    for i, v in enumerate(x):
        if v is None or not math.isfinite(v):
            out[i] = None
            continue
        if prev is None or prev == 0 or not math.isfinite(prev):
            out[i] = None
        else:
            out[i] = (v / prev) - 1.0
        prev = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--amounts", type=Path, default=Path("data") / "daily_amounts.json")
    ap.add_argument("--txsize", type=Path, default=Path("data") / "daily_tx_size.json")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output path. Defaults to out/<asset>/onchain_features.json.",
    )
    ap.add_argument("--zwin", type=int, default=365, help="Rolling window for z-scores (days).")

    ap.add_argument(
        "--whale_mode",
        choices=["last_bucket", "last_two_buckets"],
        default="last_bucket",
        help=(
            "How to define WHALE_TX from tx-size buckets. "
            "last_bucket = use the last column; "
            "last_two_buckets = sum of last two columns."
        ),
    )

    args = ap.parse_args()
    if args.out is None:
        args.out = Path("out") / args.asset / "onchain_features.json"

    amounts = _load_amounts(args.amounts)
    tx = _load_tx_size(args.txsize)

    dates = _sorted_dates(amounts, tx)

    # --- Amount series ---
    total_amount: List[Optional[float]] = [amounts.get(d) for d in dates]

    vol_log: List[Optional[float]] = [
        math.log(max(1e-12, v)) if (v is not None and v > 0) else None for v in total_amount
    ]
    vol_z = _rolling_zscore(vol_log, args.zwin)

    # --- Tx bucket aggregation ---
    whale_tx: List[Optional[float]] = []
    mid_tx: List[Optional[float]] = []
    small_tx: List[Optional[float]] = []

    for d in dates:
        row = tx.get(d)
        if not row:
            whale_tx.append(None)
            mid_tx.append(None)
            small_tx.append(None)
            continue

        n = len(row)
        if n < 2:
            whale_tx.append(None)
            mid_tx.append(None)
            small_tx.append(None)
            continue

        last = float(row[-1])
        second_last = float(row[-2]) if n >= 2 else 0.0
        rest = row[:-2] if n >= 2 else []

        if args.whale_mode == "last_two_buckets" and n >= 3:
            w = last + second_last
            m = float(row[-3])
            s = float(sum(row[:-3]))
        else:
            w = last
            m = second_last
            s = float(sum(rest)) if rest else 0.0

        whale_tx.append(w)
        mid_tx.append(m)
        small_tx.append(s)

    whale_share: List[Optional[float]] = []
    dominance: List[Optional[float]] = []

    for w, m, s in zip(whale_tx, mid_tx, small_tx):
        if w is None or m is None or s is None:
            whale_share.append(None)
            dominance.append(None)
            continue
        denom = w + m + s
        whale_share.append((w / denom) if denom > 0 else None)
        dominance.append(((w + m) / s) if s > 0 else None)

    dom_log: List[Optional[float]] = [
        math.log(max(1e-12, v)) if (v is not None and v > 0) else None for v in dominance
    ]
    dom_z = _rolling_zscore(dom_log, args.zwin)
    whale_share_z = _rolling_zscore(whale_share, args.zwin)

    # Optional daily changes (good for exploration)
    vol_chg = _pct_change(total_amount)
    whale_chg = _pct_change(whale_tx)
    dom_chg = _pct_change(dominance)

    out = {
        "dates": dates,
        "series": {
            "ONCHAIN_AMOUNT_TOTAL": total_amount,
            "ONCHAIN_AMOUNT_LOG": vol_log,
            "ONCHAIN_TX_WHALE": whale_tx,
            "ONCHAIN_TX_MID": mid_tx,
            "ONCHAIN_TX_SMALL": small_tx,
            "ONCHAIN_WHALE_SHARE": whale_share,
            "ONCHAIN_DOMINANCE": dominance,
            "ONCHAIN_VOL_Z": vol_z,
            "ONCHAIN_DOM_Z": dom_z,
            "ONCHAIN_WHALE_SHARE_Z": whale_share_z,
            "ONCHAIN_AMOUNT_PCT": vol_chg,
            "ONCHAIN_WHALE_TX_PCT": whale_chg,
            "ONCHAIN_DOM_PCT": dom_chg,
        },
        "meta": {
            "source_amounts": str(args.amounts),
            "source_txsize": str(args.txsize),
            "zwin": int(args.zwin),
            "whale_mode": args.whale_mode,
            "notes": (
                "whale/mid/small are derived from tx-size buckets without assuming exact boundaries. "
                "If your last column is 1000+ BTC and second last is 100-1000 BTC, whale_mode=last_bucket is correct. "
                "If your last two columns together represent >1000 BTC, use whale_mode=last_two_buckets."
            ),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} with {len(dates)} rows and {len(out['series'])} series.")


if __name__ == "__main__":
    main()
