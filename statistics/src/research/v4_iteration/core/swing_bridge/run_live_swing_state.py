from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import export_feature_csv
from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_PRICE_JSON_PATH, OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.core.swing_detection.run_swing_detection import atr_percent, detect_swings, validate_price_frame
from src.research.v4_iteration.core.swing_bridge.swing_bridge_common import SWING_ATR_WINDOW, SWING_GRANULARITY_LABEL, SWING_REVERSAL_K


DEFAULT_LIVE_SWING_STATE_CSV_PATH = OUT_DIR / "swing_bridge" / "live_swing_state.csv"
DEFAULT_LIVE_SWING_STATE_MD_PATH = STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_LIVE_SWING_STATE.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a causal daily live swing-state table from BTC price structure.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--out-csv", default=str(DEFAULT_LIVE_SWING_STATE_CSV_PATH), help="Default: ../out/swing_bridge/live_swing_state.csv")
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_LIVE_SWING_STATE_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_LIVE_SWING_STATE.md",
    )
    return parser.parse_args()


def build_live_swing_state(price: pd.DataFrame) -> pd.DataFrame:
    validated = validate_price_frame(price)
    validated = validated.assign(atr_pct=atr_percent(validated, SWING_ATR_WINDOW))
    working = validated.dropna(subset=["atr_pct"]).copy()
    swings, _ = detect_swings(validated, reversal_k=SWING_REVERSAL_K, atr_window=SWING_ATR_WINDOW)

    median_abs_amplitude = float(swings["amplitude_pct"].abs().median()) if not swings.empty else np.nan
    median_duration_days = float(swings["duration_days"].median()) if not swings.empty else np.nan

    live = pd.DataFrame(index=validated.index)
    columns = {
        "live_swing_direction": np.nan,
        "days_since_last_pivot": np.nan,
        "distance_from_last_pivot_pct": np.nan,
        "distance_from_last_pivot_atr_units": np.nan,
        "current_swing_confirmed": False,
        "last_confirmed_pivot_date": np.nan,
        "last_confirmed_pivot_price": np.nan,
        "current_leg_start_date": np.nan,
        "current_leg_start_price": np.nan,
        "swing_confirmed_today": False,
        "current_swing_age_pct_of_median": np.nan,
        "current_swing_size_pct_of_median": np.nan,
        "atr_pct": np.nan,
        "swing_granularity": SWING_GRANULARITY_LABEL,
    }
    for name, default_value in columns.items():
        live[name] = default_value

    index = working.index
    high = working["high"].to_numpy(dtype=float)
    low = working["low"].to_numpy(dtype=float)
    close = working["close"].to_numpy(dtype=float)
    atr_pct_values = working["atr_pct"].to_numpy(dtype=float)

    tentative_anchor_idx = 0
    tentative_anchor_price = close[tentative_anchor_idx]
    confirmed_pivot_idx: int | None = None
    confirmed_pivot_price: float | None = None
    direction = 0
    extreme_idx = tentative_anchor_idx
    extreme_price = tentative_anchor_price

    for i in range(len(working)):
        current_date = index[i]
        swing_confirmed_today = False

        if i > 0:
            threshold = SWING_REVERSAL_K * float(atr_pct_values[i])

            if direction == 0:
                up_move = high[i] / tentative_anchor_price - 1.0
                down_move = low[i] / tentative_anchor_price - 1.0
                if up_move >= threshold and up_move >= abs(down_move):
                    direction = 1
                    extreme_idx = i
                    extreme_price = high[i]
                elif abs(down_move) >= threshold:
                    direction = -1
                    extreme_idx = i
                    extreme_price = low[i]
            elif direction == 1:
                updated_extreme = False
                if high[i] >= extreme_price:
                    extreme_idx = i
                    extreme_price = high[i]
                    updated_extreme = True
                if not updated_extreme:
                    reversal_pct = 1.0 - low[i] / extreme_price
                    if reversal_pct >= threshold:
                        confirmed_pivot_idx = extreme_idx
                        confirmed_pivot_price = extreme_price
                        direction = -1
                        extreme_idx = i
                        extreme_price = low[i]
                        swing_confirmed_today = True
            else:
                updated_extreme = False
                if low[i] <= extreme_price:
                    extreme_idx = i
                    extreme_price = low[i]
                    updated_extreme = True
                if not updated_extreme:
                    reversal_pct = high[i] / extreme_price - 1.0
                    if reversal_pct >= threshold:
                        confirmed_pivot_idx = extreme_idx
                        confirmed_pivot_price = extreme_price
                        direction = 1
                        extreme_idx = i
                        extreme_price = high[i]
                        swing_confirmed_today = True

        live.at[current_date, "atr_pct"] = float(atr_pct_values[i])
        live.at[current_date, "swing_confirmed_today"] = bool(swing_confirmed_today)

        if direction == 0:
            live.at[current_date, "live_swing_direction"] = "unknown"
            continue

        live.at[current_date, "live_swing_direction"] = "up" if direction == 1 else "down"
        live.at[current_date, "current_swing_confirmed"] = False

        if confirmed_pivot_idx is None or confirmed_pivot_price is None:
            continue

        pivot_date = index[confirmed_pivot_idx]
        live.at[current_date, "last_confirmed_pivot_date"] = pivot_date.strftime("%Y-%m-%d")
        live.at[current_date, "last_confirmed_pivot_price"] = float(confirmed_pivot_price)
        live.at[current_date, "current_leg_start_date"] = pivot_date.strftime("%Y-%m-%d")
        live.at[current_date, "current_leg_start_price"] = float(confirmed_pivot_price)
        live.at[current_date, "days_since_last_pivot"] = float((current_date - pivot_date).days)

        distance_pct = float(close[i] / confirmed_pivot_price - 1.0)
        current_atr = float(atr_pct_values[i] * close[i])
        live.at[current_date, "distance_from_last_pivot_pct"] = distance_pct
        live.at[current_date, "distance_from_last_pivot_atr_units"] = float((close[i] - confirmed_pivot_price) / current_atr) if current_atr > 0 else np.nan
        live.at[current_date, "current_swing_age_pct_of_median"] = (
            float((current_date - pivot_date).days / median_duration_days) if median_duration_days and not np.isnan(median_duration_days) else np.nan
        )
        live.at[current_date, "current_swing_size_pct_of_median"] = (
            float(abs(distance_pct) / median_abs_amplitude) if median_abs_amplitude and not np.isnan(median_abs_amplitude) else np.nan
        )

    return live


def render_markdown(frame: pd.DataFrame) -> str:
    valid = frame.loc[frame["live_swing_direction"].notna()].copy()
    latest = valid.iloc[-1] if not valid.empty else None
    lines = [
        "# SAFE v4.0 Live Swing State",
        "",
        f"Chosen swing granularity: `{SWING_GRANULARITY_LABEL}`",
        f"- ATR window: `{SWING_ATR_WINDOW}`",
        f"- reversal multiplier: `{SWING_REVERSAL_K:.2f}`",
        "",
        "This table is causal. Each daily row uses only pivots that would already have been confirmed by that date.",
        "",
        "Fields:",
        "- `live_swing_direction`: current open leg direction (`up`, `down`, `unknown`)",
        "- `days_since_last_pivot`: calendar days since the last confirmed pivot",
        "- `distance_from_last_pivot_pct`: close relative to the last confirmed pivot price",
        "- `distance_from_last_pivot_atr_units`: same distance measured in current ATR units",
        "- `current_swing_confirmed`: false for the live leg by construction; the active leg is still open",
        "- `swing_confirmed_today`: true on days when a prior leg becomes a confirmed swing and a new live leg begins",
        "",
    ]

    if latest is not None:
        lines.extend(
            [
                "## Latest Snapshot",
                "",
                f"- date: `{latest.name.strftime('%Y-%m-%d')}`",
                f"- live_swing_direction: `{latest['live_swing_direction']}`",
                f"- days_since_last_pivot: `{int(latest['days_since_last_pivot']) if pd.notna(latest['days_since_last_pivot']) else 'nan'}`",
                f"- distance_from_last_pivot_pct: `{latest['distance_from_last_pivot_pct']:.2%}`" if pd.notna(latest["distance_from_last_pivot_pct"]) else "- distance_from_last_pivot_pct: `nan`",
                f"- distance_from_last_pivot_atr_units: `{latest['distance_from_last_pivot_atr_units']:.2f}`" if pd.notna(latest["distance_from_last_pivot_atr_units"]) else "- distance_from_last_pivot_atr_units: `nan`",
                f"- last_confirmed_pivot_date: `{latest['last_confirmed_pivot_date']}`" if pd.notna(latest["last_confirmed_pivot_date"]) else "- last_confirmed_pivot_date: `nan`",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    price = load_daily_price_json(args.price_json)
    live_state = build_live_swing_state(price)

    out_csv = Path(args.out_csv)
    export_feature_csv(live_state, out_csv, columns=list(live_state.columns))

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(live_state), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(live_state)}")
    print(f"Range: {live_state.index.min().strftime('%Y-%m-%d')} -> {live_state.index.max().strftime('%Y-%m-%d')}")
    latest = live_state.dropna(subset=["live_swing_direction"]).iloc[-1]
    print(
        "Latest:",
        f"direction={latest['live_swing_direction']}",
        f"days_since_last_pivot={latest['days_since_last_pivot']}",
    )
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
