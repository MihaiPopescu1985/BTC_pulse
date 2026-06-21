from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipelines.common import SRC_DIR, run_step


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the retained SAFE foundation pipeline.")
    parser.add_argument(
        "--with-contracts",
        action="store_true",
        help="Run strict foundation contract checks after generation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_step("foundation:swing_detection", str(SRC_DIR / "foundation" / "swing_detection.py"))
    run_step("foundation:live_swing_state", str(SRC_DIR / "foundation" / "live_swing_state.py"))
    run_step("foundation:swing_taxonomy", str(SRC_DIR / "foundation" / "swing_taxonomy.py"))
    if args.with_contracts:
        run_step(
            "contracts:foundation",
            str(SRC_DIR / "contracts" / "run_contract_checks.py"),
            "--group",
            "foundation",
        )


if __name__ == "__main__":
    main()
