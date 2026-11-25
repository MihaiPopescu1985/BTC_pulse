#!/usr/bin/env python3
"""Refresh ``frontend/_data`` from the canonical statistics artifacts.

Jekyll serves every chart from ``frontend/_data``, which is a *copy*: the
retrieval pipeline in ``statistics/src/data/query.py`` writes only into
``statistics/data`` by design, and nothing else propagates those files here.
Without this step the dashboard keeps rendering whatever copy was committed
last, which is how the on-chain charts ended up months behind the data.

Run it after a statistics refresh:

    .venv/bin/python frontend/sync_data.py

Raw inputs are copied verbatim. ``features.json`` and ``onchain_features.json``
are rebuilt from the CSV feature stores into the ``{dates, series, meta}`` shape
that ``assets/scripts/charts/daily_safe.js`` expects.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = FRONTEND_DIR.parent
STATISTICS_DIR = REPO_ROOT / "statistics"
DATA_OUT = FRONTEND_DIR / "_data"

if str(STATISTICS_DIR) not in sys.path:
    sys.path.insert(0, str(STATISTICS_DIR))

from src.data.feature_store import load_feature_series  # noqa: E402

# Copied as-is: the frontend reads these in exactly the shape query.py writes.
RAW_COPIES: tuple[str, ...] = (
    "daily_amounts.json",
    "daily_price.json",
    "daily_tx_size.json",
)


def _json_safe(value: object) -> object:
    """Replace non-finite floats with None so the payload stays valid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _clean_series(series: dict[str, list]) -> dict[str, list]:
    return {name: [_json_safe(v) for v in values] for name, values in series.items()}


def _hmm_meta() -> dict:
    """Read the state->label mapping from the saved HMM pack.

    daily_safe.js looks for ``meta.hmm.labels_by_state`` as a 4-element array and
    falls back to R0..R3 when it is missing. The mapping is not stable across
    retrains, so it has to be exported alongside the HMM_STATE_* columns rather
    than assumed.
    """
    pack_path = STATISTICS_DIR / "out" / "models" / "hmm_pack.joblib"
    if not pack_path.is_file():
        return {}
    try:
        import warnings

        import joblib

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pack = joblib.load(pack_path)
    except Exception as exc:  # pragma: no cover - diagnostic path
        print(f"  ! could not read {pack_path.name}: {exc}")
        return {}

    semantic_to_state = pack.get("semantic_to_state") if isinstance(pack, dict) else None
    if not isinstance(semantic_to_state, dict):
        return {}

    labels_by_state = [None] * len(semantic_to_state)
    for label, state in semantic_to_state.items():
        if isinstance(state, int) and 0 <= state < len(labels_by_state):
            labels_by_state[state] = label
    if any(label is None for label in labels_by_state):
        return {"semantic_to_state": semantic_to_state}

    return {
        "labels_by_state": labels_by_state,
        "semantic_to_state": semantic_to_state,
        "mode": (pack.get("cfg") or {}).get("mode") if isinstance(pack.get("cfg"), dict) else None,
    }


def _build_payload(csv_path: Path, *, extra_meta: dict | None = None) -> dict:
    dates, series = load_feature_series(csv_path)
    date_list = list(dates)
    meta = {
        "asset": "BTC",
        "rows": len(date_list),
        "start": date_list[0] if date_list else None,
        "end": date_list[-1] if date_list else None,
        "source": str(csv_path.relative_to(REPO_ROOT)),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra_meta:
        meta.update(extra_meta)
    return {"dates": date_list, "series": _clean_series(series), "meta": meta}


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def _describe(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "dates" in payload:
        dates = payload["dates"]
        return f"{len(dates)} rows, through {dates[-1] if dates else 'n/a'}"
    if isinstance(payload, dict):
        keys = sorted(payload)
        return f"{len(keys)} entries, through {keys[-1] if keys else 'n/a'}"
    if payload and isinstance(payload[0], dict):
        return f"{len(payload)} rows, through {payload[-1].get('timestamp', 'n/a')}"
    if payload:
        return f"{len(payload) - 1} rows, through {payload[-1][0]}"
    return "empty"


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    missing: list[Path] = []

    print(f"Refreshing {DATA_OUT.relative_to(REPO_ROOT)} from {STATISTICS_DIR.name}/")

    for name in RAW_COPIES:
        source = STATISTICS_DIR / "data" / name
        if not source.is_file():
            missing.append(source)
            continue
        shutil.copyfile(source, DATA_OUT / name)
        print(f"  {name:24s} {_describe(DATA_OUT / name)}")

    builds = (
        ("features.json", STATISTICS_DIR / "out" / "features.csv", {"hmm": _hmm_meta()}),
        ("onchain_features.json", STATISTICS_DIR / "out" / "onchain_features.csv", None),
    )
    for name, csv_path, extra_meta in builds:
        if not csv_path.is_file():
            missing.append(csv_path)
            continue
        _write_json(DATA_OUT / name, _build_payload(csv_path, extra_meta=extra_meta))
        print(f"  {name:24s} {_describe(DATA_OUT / name)}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_json(DATA_OUT / "last_update.json", {"iso": stamp})
    print(f"  {'last_update.json':24s} {stamp}")

    if missing:
        print("\nMissing inputs - run the statistics pipeline first:")
        for path in missing:
            print(f"  - {path.relative_to(REPO_ROOT)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
