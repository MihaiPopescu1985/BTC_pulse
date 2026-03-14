#!/usr/bin/env python3
"""
SAFE Trade Context Classifier (TRADE / NO TRADE)

Produces a daily, deterministic "context call" WITHOUT buy/sell signals:
- NO_TRADE
- TRADE_RANGE_SCALP
- TRADE_TREND_EPISODIC
- TRADE_CAUTION

Reads your existing outputs:
  --dynamics  out/btc/wave_dynamics_v2.csv
  --cells     out/btc/wave_cells_daily.csv
  --entropy   out/btc/wave_cell_entropy.csv

Uses percentile thresholds computed from your own history (no fixed magic numbers),
plus a tiny absolute guard for delta_entropy near zero (safety brake).

Example:
  python src/util/safe_trade_context.py --date 2026-01-21 --show_thresholds
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd


def _pick_persist_col(df: pd.DataFrame, window: int) -> str | None:
    prefs = [f"persist_{window}_loose", f"persist_{window}", "persist_14_loose", "persist_14"]
    for c in prefs:
        if c in df.columns:
            return c
    return None


def _pct(x: pd.Series, q: float) -> float:
    x = x.dropna().astype(float)
    if len(x) == 0:
        return float("nan")
    return float(np.quantile(x.to_numpy(), q))


def _latest_common_date(*dfs: pd.DataFrame) -> pd.Timestamp:
    dates = []
    for df in dfs:
        if "date" not in df.columns:
            continue
        dates.append(df["date"].max())
    return min(dates)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dynamics", default="out/btc/wave_dynamics_v2.csv")
    ap.add_argument("--cells", default="out/btc/wave_cells_daily.csv")
    ap.add_argument("--entropy", default="out/btc/wave_cell_entropy.csv")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: latest common date across inputs)")
    ap.add_argument("--window", type=int, default=14)
    ap.add_argument("--show_thresholds", action="store_true")
    args = ap.parse_args()

    dyn = pd.read_csv(Path(args.dynamics))
    cells = pd.read_csv(Path(args.cells))
    ent = pd.read_csv(Path(args.entropy))

    dyn["date"] = pd.to_datetime(dyn["date"])
    cells["date"] = pd.to_datetime(cells["date"])

    if args.date is None:
        target = _latest_common_date(dyn, cells)
    else:
        target = pd.to_datetime(args.date)

    dyn_row = dyn.loc[dyn["date"] == target]
    cell_row = cells.loc[cells["date"] == target]

    if dyn_row.empty or cell_row.empty:
        print(f"ERROR: target date {target.date()} not found in one of the inputs.")
        print(f"  dynamics_has_date={not dyn_row.empty} | cells_has_date={not cell_row.empty}")
        sys.exit(0)

    dyn_row = dyn_row.iloc[0]
    cell_id = cell_row.iloc[0].get("cell_id", np.nan)

    # Map cell -> entropy stats
    P_stay = float("nan")
    delta_H = float("nan")
    if pd.notna(cell_id):
        er = ent.loc[ent["cell_id"] == int(cell_id)]
        if not er.empty:
            if "P_stay" in er.columns:
                P_stay = float(er.iloc[0]["P_stay"])
            if "delta_entropy" in er.columns:
                delta_H = float(er.iloc[0]["delta_entropy"])

    speed = float(dyn_row.get("speed", np.nan))
    theta = float(dyn_row.get("theta", np.nan))

    persist_col = _pick_persist_col(dyn, args.window)
    persist = float(dyn_row.get(persist_col, np.nan)) if persist_col else float("nan")

    # Percentile thresholds from history
    speed_med = _pct(dyn["speed"], 0.50)
    speed_p75 = _pct(dyn["speed"], 0.75)

    persist_p30 = _pct(dyn[persist_col], 0.30) if persist_col else float("nan")
    persist_p70 = _pct(dyn[persist_col], 0.70) if persist_col else float("nan")

    dH_p70 = _pct(ent["delta_entropy"], 0.70)
    dH_p30 = _pct(ent["delta_entropy"], 0.30)

    Ps_p30 = _pct(ent["P_stay"], 0.30)
    Ps_p70 = _pct(ent["P_stay"], 0.70)

    # ---- Decision logic ----
    no_trade = False
    reasons = []

    # Safety brake: delta_entropy near 0 => transitions close to baseline
    if np.isfinite(delta_H):
        if delta_H > max(dH_p70, -0.1):
            no_trade = True
            reasons.append(f"delta_entropy high (less negative): {delta_H:.3f}")
    else:
        reasons.append("delta_entropy missing")

    if np.isfinite(speed) and np.isfinite(P_stay):
        if (speed > speed_med) and (P_stay < Ps_p30):
            no_trade = True
            reasons.append(
                f"fast+fragile: speed {speed:.3f} > med {speed_med:.3f} & P_stay {P_stay:.3f} < p30 {Ps_p30:.3f}"
            )
    else:
        if not np.isfinite(speed): reasons.append("speed missing")
        if not np.isfinite(P_stay): reasons.append("P_stay missing")

    decision = "NO_TRADE"
    style = "STAY_OUT"

    if not no_trade:
        trend_ok = (
            np.isfinite(persist) and persist_col and (persist > persist_p70)
            and np.isfinite(delta_H) and (delta_H < dH_p30)
            and np.isfinite(speed) and (speed < speed_p75)
        )
        range_ok = (
            np.isfinite(persist) and persist_col and (persist < persist_p30)
            and np.isfinite(P_stay) and (P_stay > Ps_p70)
            and np.isfinite(speed) and (speed < speed_med)
        )

        decision = "TRADE"
        if trend_ok and not range_ok:
            style = "TREND_EPISODIC"
        elif range_ok and not trend_ok:
            style = "RANGE_SCALP"
        elif trend_ok and range_ok:
            style = "MIXED_OK"
        else:
            style = "CAUTION"

    # ---- Print daily card ----
    print(f"SAFE Daily Trade Context — {target.date()}")
    print("-" * 40)
    print(f"Cell: {int(cell_id) if pd.notna(cell_id) else 'NaN'}")
    print(f"P_stay: {P_stay:.3f}" if np.isfinite(P_stay) else "P_stay: NaN")
    print(f"delta_entropy: {delta_H:.3f}" if np.isfinite(delta_H) else "delta_entropy: NaN")
    print(f"speed: {speed:.6f}" if np.isfinite(speed) else "speed: NaN")
    print(f"theta: {theta:.6f}" if np.isfinite(theta) else "theta: NaN")
    if persist_col:
        print(f"{persist_col}: {persist:.6f}" if np.isfinite(persist) else f"{persist_col}: NaN")
    else:
        print("persist: (missing)")

    print("-" * 40)
    print(f"DECISION: {decision}")
    print(f"STYLE: {style}")

    if decision == "NO_TRADE":
        print("WHY: " + ("; ".join(reasons) if reasons else "context flagged as hostile"))

    if args.show_thresholds:
        print("\nThresholds (computed from your history):")
        print(f"  speed: median={speed_med:.6f} | p75={speed_p75:.6f}")
        if persist_col:
            print(f"  {persist_col}: p30={persist_p30:.6f} | p70={persist_p70:.6f}")
        print(f"  delta_entropy: p30={dH_p30:.6f} | p70={dH_p70:.6f} | abs_guard=-0.1")
        print(f"  P_stay: p30={Ps_p30:.6f} | p70={Ps_p70:.6f}")


if __name__ == "__main__":
    main()
