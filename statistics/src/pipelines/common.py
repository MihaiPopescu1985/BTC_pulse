from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"


def run_step(label: str, *args: str) -> None:
    command = [sys.executable, *args]
    print(f"[pipeline] {label}")
    print(" ".join(command))
    subprocess.run(command, check=True)

