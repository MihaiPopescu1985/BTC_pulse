from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_PRICE_JSON_PATH, OUT_DIR, STATISTICS_DIR


DEFAULT_SWINGS_CSV_PATH = OUT_DIR / "swing_detection" / "swings.csv"
DEFAULT_SWING_DISTRIBUTION_MD_PATH = STATISTICS_DIR / "docs" / "swing_detection" / "SAFE_v4.0_SWING_DISTRIBUTION.md"


@dataclass(frozen=True)
class Swing:
    start_date: str
    end_date: str
    direction: str
    amplitude_pct: float
    duration_days: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract BTC price swings using a volatility-normalized ZigZag.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--atr-window", type=int, default=14, help="ATR lookback window. Default: 14")
    parser.add_argument("--reversal-k", type=float, default=1.5, help="Reversal threshold multiplier. Default: 1.5")
    parser.add_argument("--out-csv", default=str(DEFAULT_SWINGS_CSV_PATH), help="Default: ../out/swing_detection/swings.csv")
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SWING_DISTRIBUTION_MD_PATH),
        help="Default: ../docs/swing_detection/SAFE_v4.0_SWING_DISTRIBUTION.md",
    )
    return parser.parse_args()


def validate_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("Swing detection received an empty price table.")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("Swing detection requires a DatetimeIndex.")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("Swing detection requires dates sorted in increasing order.")
    if frame.index.has_duplicates:
        raise ValueError("Swing detection does not accept duplicate timestamps.")

    required_columns = ("high", "low", "close")
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Swing detection is missing required OHLC columns: {missing_columns}")

    validated = frame.copy()
    for column in required_columns:
        validated[column] = pd.to_numeric(validated[column], errors="coerce")
    if validated[list(required_columns)].isna().any().any():
        raise ValueError("Swing detection found NaN OHLC values after numeric conversion.")
    return validated


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr_percent(frame: pd.DataFrame, atr_window: int) -> pd.Series:
    tr = true_range(frame["high"], frame["low"], frame["close"])
    atr = tr.rolling(atr_window, min_periods=atr_window).mean()
    return atr / frame["close"]


def _duration_days(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return int((end - start).days)


def detect_swings(frame: pd.DataFrame, reversal_k: float, atr_window: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    validated = validate_price_frame(frame)
    validated = validated.assign(atr_pct=atr_percent(validated, atr_window))
    working = validated.dropna(subset=["atr_pct"]).copy()
    if len(working) < 3:
        raise ValueError("Not enough ATR-valid rows to detect swings.")

    index = working.index
    high = working["high"].to_numpy(dtype=float)
    low = working["low"].to_numpy(dtype=float)
    close = working["close"].to_numpy(dtype=float)
    atr_pct_values = working["atr_pct"].to_numpy(dtype=float)

    start_idx = 0
    last_pivot_idx = start_idx
    last_pivot_price = close[start_idx]
    direction = 0
    extreme_idx = start_idx
    extreme_price = close[start_idx]

    swings: list[Swing] = []

    for i in range(start_idx + 1, len(working)):
        threshold = reversal_k * float(atr_pct_values[i])

        if direction == 0:
            up_move = high[i] / last_pivot_price - 1.0
            down_move = low[i] / last_pivot_price - 1.0

            if up_move >= threshold and up_move >= abs(down_move):
                direction = 1
                extreme_idx = i
                extreme_price = high[i]
            elif abs(down_move) >= threshold:
                direction = -1
                extreme_idx = i
                extreme_price = low[i]
            continue

        if direction == 1:
            updated_extreme = False
            if high[i] >= extreme_price:
                extreme_idx = i
                extreme_price = high[i]
                updated_extreme = True

            if updated_extreme:
                continue

            reversal_pct = 1.0 - low[i] / extreme_price
            if reversal_pct >= threshold:
                start_date = index[last_pivot_idx]
                end_date = index[extreme_idx]
                swings.append(
                    Swing(
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        direction="up",
                        amplitude_pct=float(extreme_price / last_pivot_price - 1.0),
                        duration_days=_duration_days(start_date, end_date),
                    )
                )
                last_pivot_idx = extreme_idx
                last_pivot_price = extreme_price
                direction = -1
                extreme_idx = i
                extreme_price = low[i]
            continue

        updated_extreme = False
        if low[i] <= extreme_price:
            extreme_idx = i
            extreme_price = low[i]
            updated_extreme = True

        if updated_extreme:
            continue

        reversal_pct = high[i] / extreme_price - 1.0
        if reversal_pct >= threshold:
            start_date = index[last_pivot_idx]
            end_date = index[extreme_idx]
            swings.append(
                Swing(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                    direction="down",
                    amplitude_pct=float(extreme_price / last_pivot_price - 1.0),
                    duration_days=_duration_days(start_date, end_date),
                )
            )
            last_pivot_idx = extreme_idx
            last_pivot_price = extreme_price
            direction = 1
            extreme_idx = i
            extreme_price = high[i]

    swings_frame = pd.DataFrame([s.__dict__ for s in swings])
    return swings_frame, working


def amplitude_bin_summary(swings: pd.DataFrame) -> pd.DataFrame:
    if swings.empty:
        return pd.DataFrame(columns=["bin", "count"])
    amplitude = swings["amplitude_pct"].abs()
    bins = [0.0, 0.05, 0.10, 0.20, 0.30, np.inf]
    labels = ["0-5%", "5-10%", "10-20%", "20-30%", "30%+"]
    bucketed = pd.cut(amplitude, bins=bins, labels=labels, include_lowest=True, right=False)
    return bucketed.value_counts(sort=False).rename_axis("bin").reset_index(name="count")


def duration_bin_summary(swings: pd.DataFrame) -> pd.DataFrame:
    if swings.empty:
        return pd.DataFrame(columns=["bin", "count"])
    bins = [0, 7, 14, 30, 60, np.inf]
    labels = ["0-6d", "7-13d", "14-29d", "30-59d", "60d+"]
    bucketed = pd.cut(swings["duration_days"], bins=bins, labels=labels, include_lowest=True, right=False)
    return bucketed.value_counts(sort=False).rename_axis("bin").reset_index(name="count")


def render_markdown(swings: pd.DataFrame, atr_window: int, reversal_k: float) -> str:
    if swings.empty:
        return (
            "# SAFE v4.0 Swing Distribution\n\n"
            "No confirmed swings were extracted for the chosen ATR-normalized ZigZag parameters.\n"
        )

    up_swings = swings.loc[swings["direction"] == "up"]
    down_swings = swings.loc[swings["direction"] == "down"]
    amplitude_bins = amplitude_bin_summary(swings)
    duration_bins = duration_bin_summary(swings)
    corr = swings["amplitude_pct"].abs().corr(swings["duration_days"], method="spearman")

    lines = [
        "# SAFE v4.0 Swing Distribution",
        "",
        "This note summarizes confirmed swings extracted from BTC daily OHLC with a volatility-normalized ZigZag.",
        "",
        "Method:",
        f"- volatility proxy: ATR percent with `{atr_window}`-day window",
        f"- reversal threshold: `{reversal_k:.2f} x ATR%`",
        "- pivots are confirmed only after a reversal threshold breach",
        "- unfinished final leg is not exported as a swing",
        "",
        "## Summary",
        "",
        f"- swings extracted: `{len(swings)}`",
        f"- up swings: `{len(up_swings)}`",
        f"- down swings: `{len(down_swings)}`",
        f"- median absolute amplitude: `{swings['amplitude_pct'].abs().median():.2%}`",
        f"- median duration: `{int(swings['duration_days'].median())}` days",
        f"- amplitude-duration Spearman: `{corr:.3f}`",
        "",
        "## Amplitude Distribution",
        "",
    ]

    for _, row in amplitude_bins.iterrows():
        lines.append(f"- `{row['bin']}`: `{int(row['count'])}`")

    lines.extend(
        [
            "",
            "## Duration Distribution",
            "",
        ]
    )
    for _, row in duration_bins.iterrows():
        lines.append(f"- `{row['bin']}`: `{int(row['count'])}`")

    lines.extend(
        [
            "",
            "## Joint Stats",
            "",
            f"- up-swing median amplitude: `{up_swings['amplitude_pct'].median():.2%}`",
            f"- down-swing median amplitude: `{down_swings['amplitude_pct'].median():.2%}`",
            f"- up-swing median duration: `{int(up_swings['duration_days'].median())}` days",
            f"- down-swing median duration: `{int(down_swings['duration_days'].median())}` days",
            "",
            "Interpretation:",
            "- this is a structural market description layer, not a trading rule",
            "- larger reversals are intentionally filtered out until they exceed the ATR-normalized reversal threshold",
            "- changing `k` or the ATR window will change the swing granularity",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    price = load_daily_price_json(args.price_json)
    swings, atr_valid = detect_swings(price, reversal_k=args.reversal_k, atr_window=args.atr_window)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    swings.to_csv(out_csv, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(swings, args.atr_window, args.reversal_k), encoding="utf-8")

    first_date = atr_valid.index.min().strftime("%Y-%m-%d")
    last_date = atr_valid.index.max().strftime("%Y-%m-%d")
    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(swings)}")
    print(f"ATR-valid range: {first_date} -> {last_date}")
    if not swings.empty:
        print(
            "Swing summary:",
            f"up={int((swings['direction'] == 'up').sum())}",
            f"down={int((swings['direction'] == 'down').sum())}",
            f"median_abs_amplitude={swings['amplitude_pct'].abs().median():.4f}",
            f"median_duration_days={int(swings['duration_days'].median())}",
        )
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()

