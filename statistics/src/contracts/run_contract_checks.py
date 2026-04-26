from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.contracts.safe_v4 import ContractResult, validate_groups


GROUPS: tuple[str, ...] = ("features", "foundation", "signals", "dashboard")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate retained SAFE layer contracts.")
    parser.add_argument(
        "--group",
        action="append",
        choices=GROUPS,
        help="Contract group to validate. Can be passed multiple times. Defaults to all groups.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip missing retained outputs instead of failing. Useful before regenerating the full retained chain.",
    )
    return parser.parse_args()


def print_results(results: list[ContractResult]) -> None:
    current_group: str | None = None
    for result in results:
        if result.group != current_group:
            current_group = result.group
            print(f"\n[{current_group}]")
        path = f" ({result.path})" if result.path else ""
        print(f"{result.status:4} {result.name}{path}: {result.message}")


def main() -> None:
    args = parse_args()
    groups = tuple(args.group or GROUPS)
    results = validate_groups(groups, allow_missing=args.allow_missing)
    print_results(results)

    failures = [result for result in results if result.is_failure]
    if failures:
        print(f"\nContract check failed: {len(failures)} failure(s).")
        raise SystemExit(1)

    passed = sum(1 for result in results if result.status == "PASS")
    skipped = sum(1 for result in results if result.status == "SKIP")
    print(f"\nContract check completed: {passed} passed, {skipped} skipped.")


if __name__ == "__main__":
    main()
