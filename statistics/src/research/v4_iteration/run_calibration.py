from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.feature_store import load_feature_csv
from src.path_config import DEFAULT_CALIBRATION_CSV_PATH, DEFAULT_FEATURES_CSV_PATH, DEFAULT_TARGETS_CSV_PATH, OUT_DIR


PRIMARY_SPECS: tuple[tuple[str, str], ...] = (
    ("P_CORRECTION_10D_CAL", "touch_down_2pct_10d"),
    ("P_REBOUND_10D_CAL", "touch_up_2pct_10d"),
)
EPS = 1e-12


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the calibration analysis stage."""
    parser = argparse.ArgumentParser(
        description="Evaluate whether SAFE BTC probability outputs are calibrated against realized future events.",
    )
    parser.add_argument("--features-csv", default=str(DEFAULT_FEATURES_CSV_PATH), help="Default: ../out/features.csv")
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV_PATH), help="Default: ../out/targets.csv")
    parser.add_argument("--out-csv", default=str(DEFAULT_CALIBRATION_CSV_PATH), help="Default: ../out/calibration.csv")
    parser.add_argument("--out-md", default=str(OUT_DIR / "calibration.md"), help="Default: ../out/calibration.md")
    parser.add_argument("--bins", type=int, default=10, help="Equal-width probability bin count over [0,1]. Default: 10")
    return parser.parse_args()


def _validate_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a SAFE CSV table before date-aligned calibration analysis."""
    if frame.empty:
        raise ValueError(f"{name} input is empty.")
    if "date" not in frame.columns:
        raise ValueError(f"{name} input must contain a 'date' column.")
    if frame["date"].duplicated().any():
        duplicates = frame.loc[frame["date"].duplicated(), "date"].dt.strftime("%Y-%m-%d").head(5).tolist()
        raise ValueError(f"{name} input has duplicate dates: {duplicates}")

    validated = frame.copy()
    validated["date"] = pd.to_datetime(validated["date"], errors="raise")
    validated = validated.sort_values("date").reset_index(drop=True)
    return validated


def load_aligned_inputs(features_path: str | Path, targets_path: str | Path) -> pd.DataFrame:
    """Load features and targets and align them by anchor date."""
    features = _validate_frame("features", load_feature_csv(features_path))
    targets = _validate_frame("targets", load_feature_csv(targets_path))

    required_feature_columns = [probability_col for probability_col, _ in PRIMARY_SPECS]
    required_target_columns = [target_col for _, target_col in PRIMARY_SPECS]

    missing_feature_columns = [column for column in required_feature_columns if column not in features.columns]
    if missing_feature_columns:
        raise ValueError(f"features.csv is missing required probability columns: {missing_feature_columns}")

    missing_target_columns = [column for column in required_target_columns if column not in targets.columns]
    if missing_target_columns:
        raise ValueError(f"targets.csv is missing required realized-event columns: {missing_target_columns}")

    feature_dates = set(features["date"])
    target_dates = set(targets["date"])
    if feature_dates != target_dates:
        raise ValueError("features.csv and targets.csv must contain the same anchor-date set for calibration analysis.")

    merged = features.merge(targets, on="date", how="inner", validate="one_to_one", suffixes=("", "_target"))
    if merged.empty:
        raise ValueError("Calibration dataset is empty after joining features and targets.")
    return merged.sort_values("date").reset_index(drop=True)


def _binary_event_values(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    values = values.where(values.isin([0.0, 1.0]))
    return values


def _probability_values(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where((values >= 0.0) & (values <= 1.0))


def _assign_bins(probabilities: pd.Series, bin_count: int) -> pd.Series:
    clipped = probabilities.clip(lower=0.0, upper=1.0)
    bin_index = np.floor(clipped * bin_count).astype(int)
    bin_index = bin_index.clip(upper=bin_count - 1)
    return pd.Series(bin_index, index=probabilities.index)


def brier_score(probabilities: pd.Series, realized: pd.Series) -> float:
    """Compute the Brier score for binary probabilistic forecasts."""
    return float(np.mean((probabilities - realized) ** 2))


def binary_log_loss(probabilities: pd.Series, realized: pd.Series, eps: float = EPS) -> float:
    """Compute binary log loss with explicit clipping to avoid log(0)."""
    p = probabilities.clip(lower=eps, upper=1.0 - eps)
    y = realized
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def compute_calibration_rows(
    data: pd.DataFrame,
    probability_col: str,
    target_col: str,
    event_name: str,
    bin_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compute equal-width calibration bins and summary metrics for one probability/event pair."""
    pair = data.loc[:, ["date", probability_col, target_col]].copy()
    pair["predicted_prob"] = _probability_values(pair[probability_col])
    pair["realized_event"] = _binary_event_values(pair[target_col])
    pair = pair.dropna(subset=["predicted_prob", "realized_event"]).reset_index(drop=True)

    usable_rows = int(len(pair))
    if usable_rows == 0:
        empty_summary = {
            "model_name": probability_col,
            "event_name": event_name,
            "bin_index": "summary",
            "bin_lower": np.nan,
            "bin_upper": np.nan,
            "sample_count": 0,
            "mean_predicted_prob": np.nan,
            "realized_event_rate": np.nan,
            "absolute_gap": np.nan,
            "brier_score": np.nan,
            "log_loss": np.nan,
            "ece": np.nan,
            "max_gap": np.nan,
            "usable_rows": 0,
            "realized_base_rate": np.nan,
            "prediction_range_min": np.nan,
            "prediction_range_max": np.nan,
            "top_bottom_realized_gap": np.nan,
            "spearman_event_corr": np.nan,
        }
        return [empty_summary], empty_summary

    pair["bin_index"] = _assign_bins(pair["predicted_prob"], bin_count)

    rows: list[dict[str, Any]] = []
    bin_gap_values: list[float] = []
    weighted_abs_gap = 0.0
    bin_realized_rates: dict[int, float] = {}

    overall_brier = brier_score(pair["predicted_prob"], pair["realized_event"])
    overall_log_loss = binary_log_loss(pair["predicted_prob"], pair["realized_event"])
    realized_base_rate = float(pair["realized_event"].mean())
    prediction_range_min = float(pair["predicted_prob"].min())
    prediction_range_max = float(pair["predicted_prob"].max())
    spearman_event_corr = float(pair["predicted_prob"].corr(pair["realized_event"], method="spearman"))

    for bin_index in range(bin_count):
        lower = bin_index / bin_count
        upper = (bin_index + 1) / bin_count
        group = pair.loc[pair["bin_index"] == bin_index]
        sample_count = int(len(group))
        if sample_count == 0:
            row = {
                "model_name": probability_col,
                "event_name": event_name,
                "bin_index": int(bin_index),
                "bin_lower": float(lower),
                "bin_upper": float(upper),
                "sample_count": 0,
                "mean_predicted_prob": np.nan,
                "realized_event_rate": np.nan,
                "absolute_gap": np.nan,
                "brier_score": overall_brier,
                "log_loss": overall_log_loss,
                "ece": np.nan,
                "max_gap": np.nan,
                "usable_rows": usable_rows,
                "realized_base_rate": realized_base_rate,
                "prediction_range_min": prediction_range_min,
                "prediction_range_max": prediction_range_max,
                "top_bottom_realized_gap": np.nan,
                "spearman_event_corr": spearman_event_corr,
            }
            rows.append(row)
            continue

        mean_pred = float(group["predicted_prob"].mean())
        realized_rate = float(group["realized_event"].mean())
        abs_gap = float(abs(mean_pred - realized_rate))
        bin_gap_values.append(abs_gap)
        weighted_abs_gap += abs_gap * sample_count
        bin_realized_rates[bin_index] = realized_rate

        rows.append(
            {
                "model_name": probability_col,
                "event_name": event_name,
                "bin_index": int(bin_index),
                "bin_lower": float(lower),
                "bin_upper": float(upper),
                "sample_count": sample_count,
                "mean_predicted_prob": mean_pred,
                "realized_event_rate": realized_rate,
                "absolute_gap": abs_gap,
                "brier_score": overall_brier,
                "log_loss": overall_log_loss,
                "ece": np.nan,
                "max_gap": np.nan,
                "usable_rows": usable_rows,
                "realized_base_rate": realized_base_rate,
                "prediction_range_min": prediction_range_min,
                "prediction_range_max": prediction_range_max,
                "top_bottom_realized_gap": np.nan,
                "spearman_event_corr": spearman_event_corr,
            }
        )

    ece = float(weighted_abs_gap / usable_rows)
    max_gap = float(max(bin_gap_values)) if bin_gap_values else float("nan")
    populated_rates = pd.Series(bin_realized_rates).sort_index()
    top_bottom_realized_gap = (
        float(populated_rates.iloc[-1] - populated_rates.iloc[0])
        if len(populated_rates) >= 2
        else float("nan")
    )

    for row in rows:
        row["ece"] = ece
        row["max_gap"] = max_gap
        row["top_bottom_realized_gap"] = top_bottom_realized_gap
        row["spearman_event_corr"] = spearman_event_corr

    summary = {
        "model_name": probability_col,
        "event_name": event_name,
        "bin_index": "summary",
        "bin_lower": np.nan,
        "bin_upper": np.nan,
        "sample_count": usable_rows,
        "mean_predicted_prob": float(pair["predicted_prob"].mean()),
        "realized_event_rate": realized_base_rate,
        "absolute_gap": float(abs(float(pair["predicted_prob"].mean()) - realized_base_rate)),
        "brier_score": overall_brier,
        "log_loss": overall_log_loss,
        "ece": ece,
        "max_gap": max_gap,
        "usable_rows": usable_rows,
        "realized_base_rate": realized_base_rate,
        "prediction_range_min": prediction_range_min,
        "prediction_range_max": prediction_range_max,
        "top_bottom_realized_gap": top_bottom_realized_gap,
        "spearman_event_corr": spearman_event_corr,
    }
    rows.append(summary)
    return rows, summary


def build_calibration_table(data: pd.DataFrame, bin_count: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the tidy calibration table plus summary rows."""
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for probability_col, target_col in PRIMARY_SPECS:
        pair_rows, summary = compute_calibration_rows(data, probability_col, target_col, target_col, bin_count)
        rows.extend(pair_rows)
        summaries.append(summary)

    calibration = pd.DataFrame(rows)
    summary_frame = pd.DataFrame(summaries)
    return calibration, summary_frame


def export_csv(frame: pd.DataFrame, path: str | Path) -> None:
    """Write a plain CSV artifact for calibration outputs."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False, float_format="%.8f")


def _fmt_pct(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.4f}"


def _range_note(row: pd.Series) -> str:
    low = row.get("prediction_range_min", np.nan)
    high = row.get("prediction_range_max", np.nan)
    if pd.isna(low) or pd.isna(high):
        return "Prediction range unavailable."
    spread = float(high - low)
    if spread < 0.10:
        return f"Probabilities are tightly clustered in a narrow {100.0 * spread:.1f} point band."
    if spread < 0.25:
        return f"Probabilities vary, but only across a moderate {100.0 * spread:.1f} point band."
    return f"Probabilities span a fairly wide {100.0 * spread:.1f} point range."


def _calibration_tone(row: pd.Series) -> str:
    ece = row.get("ece", np.nan)
    max_gap = row.get("max_gap", np.nan)
    if pd.isna(ece):
        return "Calibration could not be evaluated."
    if ece <= 0.03 and (pd.isna(max_gap) or max_gap <= 0.08):
        return "Calibration looks reasonably honest at the aggregate level."
    if ece <= 0.07:
        return "Calibration is usable, though bin-level gaps remain noticeable."
    return "Calibration is loose; the probabilities look more useful for ranking than for literal interpretation."


def _bias_tone(row: pd.Series) -> str:
    gap = row.get("absolute_gap", np.nan)
    predicted = row.get("mean_predicted_prob", np.nan)
    realized = row.get("realized_event_rate", np.nan)
    if pd.isna(gap) or pd.isna(predicted) or pd.isna(realized):
        return "Bias direction is unclear."
    if abs(predicted - realized) < 0.01:
        return "Average predicted probability is close to the realized base rate."
    if predicted > realized:
        return "On average it overstates the event rate."
    return "On average it understates the event rate."


def _ranking_tone(row: pd.Series) -> str:
    realized_gap = row.get("top_bottom_realized_gap", np.nan)
    spearman_corr = row.get("spearman_event_corr", np.nan)
    if pd.isna(realized_gap):
        return "Ranking separation is not measurable from the populated bins."
    corr_note = f"Spearman={_fmt_num(spearman_corr)}. " if pd.notna(spearman_corr) else ""
    if abs(realized_gap) >= 0.20:
        return f"{corr_note}Bucket ordering still separates outcomes meaningfully, with a top-vs-bottom realized gap of {_fmt_pct(realized_gap)}."
    if abs(realized_gap) >= 0.08:
        return f"{corr_note}Ranking separation is present but moderate, with a top-vs-bottom realized gap of {_fmt_pct(realized_gap)}."
    return f"{corr_note}Ranking separation is weak, with only {_fmt_pct(realized_gap)} between top and bottom populated bins."


def _proxy_note(row: pd.Series) -> str:
    predicted = row.get("mean_predicted_prob", np.nan)
    realized = row.get("realized_base_rate", np.nan)
    if pd.isna(predicted) or pd.isna(realized):
        return ""
    if realized >= 0.70 and predicted <= 0.35:
        return "The chosen touch-event proxy is much easier to trigger than the modeled hazard concept, so literal probability levels are expected to look understated."
    return ""


def render_markdown(summary_frame: pd.DataFrame) -> str:
    """Render a compact human-readable calibration summary."""
    lines = [
        "# Calibration",
        "",
        "This report checks whether SAFE probability outputs are honest as probabilities, not just useful for ranking.",
        "",
        "Event proxies used here:",
        "- `P_CORRECTION_10D_CAL` vs `touch_down_2pct_10d`",
        "- `P_REBOUND_10D_CAL` vs `touch_up_2pct_10d`",
        "",
        "These event proxies are practical approximations of the hazard meaning, not perfect semantic matches.",
        "",
        "## Summary",
        "",
    ]

    for _, row in summary_frame.iterrows():
        lines.append(f"### {row['model_name']}")
        lines.append("")
        lines.append(f"- event proxy: `{row['event_name']}`")
        lines.append(f"- usable rows: {int(row['usable_rows'])}")
        lines.append(f"- Brier score: {_fmt_num(row['brier_score'])}")
        lines.append(f"- log loss: {_fmt_num(row['log_loss'])}")
        lines.append(f"- ECE: {_fmt_num(row['ece'])}")
        lines.append(f"- max calibration gap: {_fmt_pct(row['max_gap'])}")
        lines.append(f"- mean predicted probability: {_fmt_pct(row['mean_predicted_prob'])}")
        lines.append(f"- realized base rate: {_fmt_pct(row['realized_base_rate'])}")
        lines.append(f"- {_calibration_tone(row)}")
        lines.append(f"- {_bias_tone(row)}")
        lines.append(f"- {_ranking_tone(row)}")
        lines.append(f"- {_range_note(row)}")
        proxy_note = _proxy_note(row)
        if proxy_note:
            lines.append(f"- {proxy_note}")
        lines.append("")

    lines.extend(
        [
            "## Practical Interpretation",
            "",
            "- Midrange bins are usually the most stable; extreme bins should be treated cautiously when sample counts are sparse.",
            "- Even when absolute calibration is imperfect, a model can still be useful if higher-probability bins produce meaningfully higher realized event rates.",
            "- `HMM_CONF` is intentionally not treated as a calibrated event probability here. It is confidence in the dominant latent-state assignment, not a direct event forecast.",
            "",
        ]
    )
    return "\n".join(lines)


def print_summary(summary_frame: pd.DataFrame, out_csv: Path, out_md: Path) -> None:
    """Print a compact CLI summary for the calibration stage."""
    for _, row in summary_frame.iterrows():
        print(
            f"{row['model_name']}: rows={int(row['usable_rows'])} "
            f"Brier={float(row['brier_score']):.6f} ECE={float(row['ece']):.6f}"
        )
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


def main() -> None:
    """Run SAFE v4.0 Phase 6 calibration analysis."""
    try:
        args = parse_args()
        aligned = load_aligned_inputs(args.features_csv, args.targets_csv)
        calibration, summary = build_calibration_table(aligned, args.bins)

        out_csv = Path(args.out_csv)
        out_md = Path(args.out_md)
        export_csv(calibration, out_csv)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(summary), encoding="utf-8")

        print_summary(summary, out_csv, out_md)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required file not found: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Calibration analysis failed: {exc}") from exc


if __name__ == "__main__":
    main()
