#!/usr/bin/env python3

"""
Print date-aligned SAFE feature values from CSV between two dates (inclusive).

Usage:
  python statistics/src/util/print_features_range.py 2023-01-01 2023-01-07

Optional:
  --path PATH  Path to features.csv (default: statistics/out/features.csv)
"""

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


def parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    default_path = Path(__file__).resolve().parents[2] / "out" / "features.csv"

    parser = argparse.ArgumentParser(
        description="Print date-aligned series values between two dates (inclusive)."
    )
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--path",
        default=str(default_path),
        help="Path to features.csv (default: statistics/out/features.csv)",
    )
    args = parser.parse_args()

    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if start > end:
        print(f"Start date {args.start_date} is after end date {args.end_date}.")
        return

    frame = pd.read_csv(Path(args.path))
    if "date" not in frame.columns or len(frame.columns) <= 1:
        print("No date column or feature columns found in the csv file.")
        return

    selected = []
    for i, d in enumerate(frame["date"].tolist()):
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
        date = frame.iloc[i]["date"]
        print(f"date: {date}")
        for name in frame.columns:
            if name == "date":
                continue
            print(f"  {name}: {frame.iloc[i][name]}")


if __name__ == "__main__":
    main()
