#!/usr/bin/env python3

"""
Print date-aligned series values from features.json between two dates (inclusive).

Usage:
  python statistics/src/util/print_features_range.py 2023-01-01 2023-01-07

Optional:
  --path PATH  Path to features.json (default: statistics/out/btc/features.json)
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    default_path = Path(__file__).resolve().parents[2] / "out" / "btc" / "features.json"

    parser = argparse.ArgumentParser(
        description="Print date-aligned series values between two dates (inclusive)."
    )
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--path",
        default=str(default_path),
        help="Path to features.json (default: statistics/out/btc/features.json)",
    )
    args = parser.parse_args()

    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if start > end:
        print(f"Start date {args.start_date} is after end date {args.end_date}.")
        return

    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    dates = payload.get("dates", [])
    series = payload.get("series", {})

    if not dates or not series:
        print("No dates or series found in the json file.")
        return

    selected = []
    for i, d in enumerate(dates):
        try:
            d_parsed = parse_date(d)
        except ValueError:
            continue
        if start <= d_parsed <= end:
            selected.append(i)

    if not selected:
        print("No data found in the requested date range.")
        return

    for i in selected:
        date = dates[i]
        print(f"date: {date}")
        for name, values in series.items():
            value = values[i] if i < len(values) else None
            print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
