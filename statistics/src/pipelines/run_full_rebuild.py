from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipelines.common import SRC_DIR, run_step


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full retained SAFE rebuild and validation flow.")
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Skip compileall inside the validation phase.",
    )
    return parser.parse_args()


def main() -> None:
    run_step("pipeline:foundation", str(SRC_DIR / "pipelines" / "run_foundation_pipeline.py"))
    run_step("pipeline:signals", str(SRC_DIR / "pipelines" / "run_signal_pipeline.py"))
    validation_args = [str(SRC_DIR / "pipelines" / "run_validation.py")]
    args = parse_args()
    if args.skip_compile:
        validation_args.append("--skip-compile")
    run_step("pipeline:validation", *validation_args)


if __name__ == "__main__":
    main()
