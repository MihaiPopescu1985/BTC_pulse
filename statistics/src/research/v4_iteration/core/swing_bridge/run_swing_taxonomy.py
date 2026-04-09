from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import load_daily_price_json
from src.path_config import DEFAULT_PRICE_JSON_PATH, OUT_DIR, STATISTICS_DIR
from src.research.v4_iteration.core.swing_detection.run_swing_detection import detect_swings
from src.research.v4_iteration.core.swing_bridge.swing_bridge_common import (
    SWING_ATR_WINDOW,
    SWING_GRANULARITY_LABEL,
    SWING_REVERSAL_K,
    compute_swing_taxonomy,
)


DEFAULT_SWING_TAXONOMY_CSV_PATH = OUT_DIR / "swing_bridge" / "swing_taxonomy.csv"
DEFAULT_SWING_TAXONOMY_MD_PATH = STATISTICS_DIR / "docs" / "swing_bridge" / "SAFE_v4.0_SWING_TAXONOMY.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify confirmed BTC swings into size and duration taxonomy buckets.",
    )
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH), help="Default: ../data/daily_price.json")
    parser.add_argument("--out-csv", default=str(DEFAULT_SWING_TAXONOMY_CSV_PATH), help="Default: ../out/swing_bridge/swing_taxonomy.csv")
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_SWING_TAXONOMY_MD_PATH),
        help="Default: ../docs/swing_bridge/SAFE_v4.0_SWING_TAXONOMY.md",
    )
    return parser.parse_args()


def render_markdown(taxonomy, thresholds: dict[str, float]) -> str:
    size_counts = taxonomy["size_class"].value_counts(dropna=False).to_dict()
    duration_counts = taxonomy["duration_class"].value_counts(dropna=False).to_dict()
    lines = [
        "# SAFE v4.0 Swing Taxonomy",
        "",
        f"Chosen swing granularity: `{SWING_GRANULARITY_LABEL}`",
        f"- ATR window: `{SWING_ATR_WINDOW}`",
        f"- reversal multiplier: `{SWING_REVERSAL_K:.2f}`",
        "",
        "Taxonomy method:",
        "- size classes use absolute swing amplitude quantiles",
        "- duration classes use swing duration quantiles",
        "- quantile splits are `q33` and `q67`",
        "",
        "## Thresholds",
        "",
        f"- size q33: `{thresholds['size_q33']:.2%}`",
        f"- size q67: `{thresholds['size_q67']:.2%}`",
        f"- duration q33: `{thresholds['duration_q33']:.1f}` days",
        f"- duration q67: `{thresholds['duration_q67']:.1f}` days",
        "",
        "## Counts",
        "",
        f"- total swings: `{len(taxonomy)}`",
        f"- small / medium / large: `{size_counts.get('small', 0)}` / `{size_counts.get('medium', 0)}` / `{size_counts.get('large', 0)}`",
        f"- short / medium / long: `{duration_counts.get('short', 0)}` / `{duration_counts.get('medium', 0)}` / `{duration_counts.get('long', 0)}`",
        "",
        "Interpretation:",
        "- this taxonomy is market-defined from confirmed swings, not from arbitrary fixed thresholds",
        "- size and duration are separated so later condition mapping can distinguish fast small moves from slower large moves",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    price = load_daily_price_json(args.price_json)
    swings, _ = detect_swings(price, reversal_k=SWING_REVERSAL_K, atr_window=SWING_ATR_WINDOW)
    taxonomy, thresholds = compute_swing_taxonomy(swings)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    taxonomy_export = taxonomy.copy()
    taxonomy_export["start_date"] = taxonomy_export["start_date"].dt.strftime("%Y-%m-%d")
    taxonomy_export["end_date"] = taxonomy_export["end_date"].dt.strftime("%Y-%m-%d")
    taxonomy_export.to_csv(out_csv, index=False, float_format="%.8f")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(taxonomy, thresholds), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Rows written: {len(taxonomy_export)}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
