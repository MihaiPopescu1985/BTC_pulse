from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipelines.common import SRC_DIR, run_step


SIGNAL_STEPS: tuple[tuple[str, str], ...] = (
    ("signals:reversal_zone_dataset", "reversal_zone_dataset.py"),
    ("signals:reversal_zone_models", "reversal_zone_models.py"),
    ("signals:swing_extreme_timing", "swing_extreme_timing.py"),
    ("signals:buy_side_hybrid", "buy_side_hybrid.py"),
    ("signals:swing_decision_layer", "swing_decision_layer.py"),
    ("signals:swing_playbook_layer", "swing_playbook_layer.py"),
    ("signals:strategy_translation_layer", "strategy_translation_layer.py"),
    ("signals:rule_layer", "rule_layer.py"),
    ("signals:signal_layer", "signal_layer.py"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the retained SAFE signal pipeline.")
    parser.add_argument(
        "--with-contracts",
        action="store_true",
        help="Run strict signal contract checks after generation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    signals_dir = SRC_DIR / "signals"
    for label, script_name in SIGNAL_STEPS:
        run_step(label, str(signals_dir / script_name))
    if args.with_contracts:
        run_step(
            "contracts:signals",
            str(SRC_DIR / "contracts" / "run_contract_checks.py"),
            "--group",
            "signals",
        )


if __name__ == "__main__":
    main()
