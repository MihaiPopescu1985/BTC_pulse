from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipelines.common import ROOT as PROJECT_ROOT, SRC_DIR, run_step


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lightweight SAFE validation checks.")
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Skip python -m compileall validation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_compile:
        run_step("validate:compileall", "-m", "compileall", str(SRC_DIR))
    run_step(
        "contracts:foundation",
        str(SRC_DIR / "contracts" / "run_contract_checks.py"),
        "--group",
        "foundation",
    )
    run_step(
        "contracts:signals",
        str(SRC_DIR / "contracts" / "run_contract_checks.py"),
        "--group",
        "signals",
    )
    run_step(
        "contracts:dashboard",
        str(SRC_DIR / "contracts" / "run_contract_checks.py"),
        "--group",
        "dashboard",
    )
    run_step("dashboard:check", str(SRC_DIR / "dashboard" / "run_dashboard.py"), "--check")


if __name__ == "__main__":
    main()
