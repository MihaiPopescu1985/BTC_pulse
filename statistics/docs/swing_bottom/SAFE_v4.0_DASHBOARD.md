# SAFE v4.0 Dashboard

## Purpose

This is the single reusable research dashboard for SAFE v4.0. It is meant to inspect date-aligned research outputs against BTC price without building a separate visualization for each script.

## Run

Default view:

```bash
python statistics/src/research/v4_iteration/dashboard/run_dashboard.py
```

Specific registered view:

```bash
python statistics/src/research/v4_iteration/dashboard/run_dashboard.py --view swing_extreme_timing
```

Custom dataset:

```bash
python statistics/src/research/v4_iteration/dashboard/run_dashboard.py --dataset statistics/out/swing_bottom/reversal_zone_dataset.csv
```

Validation without starting the server:

```bash
python statistics/src/research/v4_iteration/dashboard/run_dashboard.py --check
```

## Supported Views

The registry currently includes:

- `swing_extreme_timing`
- `buy_side_hybrid`
- `swing_decision_layer`
- `swing_playbook_layer`
- `reversal_zone_dataset`
- `strategy_translation_layer`
- `rule_layer`
- `signal_layer`

Each view declares:

- dataset path
- score columns
- component columns
- label columns
- diagnostics columns
- default visible columns

## Panels

The dashboard provides:

- price panel with BTC candlesticks and swing overlays
- score panel for top-level scores
- component panel for sub-scores or diagnostics
- label panel for truth/zone columns
- diagnostics panel for hovered values

## Adding New Datasets

Add a new entry in [view_registry.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/dashboard/view_registry.py).

Provide:

- `path`
- `label`
- `description`
- `scores`
- `components`
- `labels`
- `diagnostics`
- optional defaults

If a dataset is not registered, the dashboard can still load it through `--dataset` and will infer groups heuristically from column names.

## Notes

- data is joined to `data/daily_price.json` on `date`
- swings are loaded from `out/swing_detection/swings.csv` when available
- all research outputs should remain date-aligned and CSV-based so they can plug into this dashboard without extra visualization code
