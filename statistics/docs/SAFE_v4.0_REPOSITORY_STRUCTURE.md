# SAFE v4.0 Repository Structure

## Purpose

This document describes the current repository layout after the architecture migration. The old `src/research/v4_iteration/productive/` path is no longer the entry point for productive work. The retained stack now lives under stable top-level domain directories.

## Current Source Layout

```
statistics/src/
  foundation/      — swing detection, live swing state, swing taxonomy, shared swing helpers
  signals/         — retained signal chain (8 layers)
  pipelines/       — orchestration entrypoints for foundation, signal, and full rebuilds
  dashboard/       — local inspection runtime and view registry
  contracts/       — CSV shape and column validation guardrails
  core/            — lower-level BTC surface builders (features, HMM, hazard, targets, states)
  data/            — raw source loaders and source adapters
  features/        — price feature construction logic
  models/          — HMM and hazard model logic
  util/            — shared helpers
  research/        — opt-in research tools only, not part of the default productive path
```

## Productive Chain

### Default entrypoints

Run from the `statistics/` directory.

Full retained rebuild:

```bash
python src/pipelines/run_full_rebuild.py
```

Foundation rebuild only (swing detection, live state, taxonomy):

```bash
python src/pipelines/run_foundation_pipeline.py
```

Signal-chain rebuild only:

```bash
python src/pipelines/run_signal_pipeline.py
```

Validation only:

```bash
python src/pipelines/run_validation.py
```

### Signal chain layers (under `src/signals/`)

The retained signal chain runs in this order:

```
reversal_zone_dataset
  → reversal_zone_models
  → swing_extreme_timing
  → buy_side_hybrid
  → swing_decision_layer
  → swing_playbook_layer
  → strategy_translation_layer
  → rule_layer
  → signal_layer
```

### Foundation layer (under `src/foundation/`)

The foundation produces the structural inputs consumed by the signal chain:

- `swing_detection.py` → `out/swing_detection/swings.csv`
- `live_swing_state.py` → `out/swing_bridge/live_swing_state.csv`
- `swing_taxonomy.py` → `out/swing_bridge/swing_taxonomy.csv`
- `swing_common.py` — shared swing helpers (not a direct entrypoint)

### Dashboard (under `src/dashboard/`)

```bash
python src/dashboard/run_dashboard.py
python src/dashboard/run_dashboard.py --check
python src/dashboard/run_dashboard.py --view swing_extreme_timing
```

## Lower-Level BTC Surface Refresh

The retained pipelines assume the BTC feature and model surfaces already exist. Rebuild them only when raw inputs change:

```bash
python src/core/run_features.py
python src/core/run_regime_hmm.py --retrain-hmm
python src/core/run_hazard_train.py
python src/core/run_exposure.py
python src/core/run_onchain_features.py
python src/core/run_targets.py
python src/core/run_states.py
```

## Research-Only Scripts

These are available but not part of the default productive path:

```bash
python src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py
python src/research/v4_iteration/core/interaction_discovery/run_interaction_discovery.py
python src/research/v4_iteration/core/swing_detection/run_swing_sensitivity.py
python src/research/v4_iteration/core/swing_bridge/run_swing_condition_mapping.py
python src/research/v4_iteration/productive/run_buy_side_exploration.py
```

## Output Scope

Retained default outputs:

```
out/features.csv
out/onchain_features.csv
out/models/hmm_pack.joblib
out/models/hazard_pack.joblib
out/swing_detection/swings.csv
out/swing_bridge/live_swing_state.csv
out/swing_bridge/swing_taxonomy.csv
out/swing_bottom/reversal_zone_dataset.csv
out/swing_bottom/swing_extreme_timing.csv
out/swing_bottom/buy_side_hybrid_scores.csv
out/swing_bottom/swing_decision_layer.csv
out/swing_bottom/swing_playbook_layer.csv
out/swing_bottom/strategy_translation_layer.csv
out/swing_bottom/rule_layer.csv
out/swing_bottom/signal_layer.csv
```

## Future Direction

The next research branch should focus on transition detection, not further v4.0 threshold refinement. See `docs/swing_bottom/SAFE_v4.0_NEXT_ITERATION_PATH.md` for the full rationale and recommended starting point.
