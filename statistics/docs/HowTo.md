# State-Aware Feature Engine (SAFE)

## Prepare

Work from the `statistics/` directory.

```bash
cd statistics
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Current Repository Layout

The current retained workflow is organized around:

- `src/foundation/`
  - retained swing-structure foundation
- `src/signals/`
  - retained signal chain
- `src/dashboard/`
  - retained inspection runtime
- `src/pipelines/`
  - orchestration entrypoints
- `src/contracts/`
  - validation guardrails

Supporting lower-level domains remain in place:

- `src/core/`
- `src/data/`
- `src/features/`
- `src/models/`
- `src/util/`

## Current Operational Workflow

### Full retained rebuild

```bash
python src/pipelines/run_full_rebuild.py
```

This is the preferred end-to-end retained workflow. It runs:

1. foundation rebuild
2. retained signal-chain rebuild
3. validation

### Foundation rebuild only

```bash
python src/pipelines/run_foundation_pipeline.py
```

### Signal-chain rebuild only

```bash
python src/pipelines/run_signal_pipeline.py
```

### Validation only

```bash
python src/pipelines/run_validation.py
```

## Dashboard

Run the retained dashboard:

```bash
python src/dashboard/run_dashboard.py
```

Validation-only dashboard check:

```bash
python src/dashboard/run_dashboard.py --check
```

Open a specific retained view:

```bash
python src/dashboard/run_dashboard.py --view swing_extreme_timing
```

Load a custom date-aligned dataset:

```bash
python src/dashboard/run_dashboard.py --dataset out/swing_bottom/reversal_zone_dataset.csv
```

## Retained Outputs

Main retained outputs:

- `out/features.csv`
- `out/onchain_features.csv`
- `out/models/hmm_pack.joblib`
- `out/models/hazard_pack.joblib`
- `out/swing_detection/swings.csv`
- `out/swing_bridge/live_swing_state.csv`
- `out/swing_bridge/swing_taxonomy.csv`
- `out/swing_bottom/reversal_zone_dataset.csv`
- `out/swing_bottom/swing_extreme_timing.csv`
- `out/swing_bottom/buy_side_hybrid_scores.csv`
- `out/swing_bottom/swing_decision_layer.csv`
- `out/swing_bottom/swing_playbook_layer.csv`
- `out/swing_bottom/strategy_translation_layer.csv`
- `out/swing_bottom/rule_layer.csv`
- `out/swing_bottom/signal_layer.csv`

## Lower-Level BTC Surface Refresh

The retained pipelines assume the BTC feature/model surface already exists.

If raw BTC inputs changed and you need to refresh those upstream surfaces first, run the lower-level builders directly:

```bash
python src/core/run_features.py
python src/core/run_regime_hmm.py --retrain-hmm
python src/core/run_hazard_train.py
python src/core/run_exposure.py
python src/core/run_onchain_features.py
python src/core/run_targets.py
python src/core/run_states.py
```

Use this lower-level path only when you actually need to rebuild the upstream BTC surfaces. Day-to-day retained SAFE workflow should go through `src/pipelines/`.

## Research-Only Utilities

These are still available, but they are not the primary workflow:

```bash
python src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py
python src/research/v4_iteration/core/interaction_discovery/run_interaction_discovery.py
python src/research/v4_iteration/core/swing_detection/run_swing_sensitivity.py
python src/research/v4_iteration/core/swing_bridge/run_swing_condition_mapping.py
python src/research/v4_iteration/productive/run_buy_side_exploration.py
```

