# SAFE v4.0 Reproducibility

## Scope

This note describes the current retained SAFE workflow.

It covers:

- retained foundation rebuild
- retained signal-chain rebuild
- retained validation
- retained dashboard check

It does not treat research-only scripts as part of the default reproducibility path.

## Working Directory

Run commands from `statistics/`.

## Inputs

- `data/daily_price.json`
- `data/daily_amounts.json`
- `data/daily_tx_size.json`

## Core Date Range

- `2017-08-17` -> `2026-04-02`

## Preferred Retained Rebuild

Run the full retained workflow:

```bash
python src/pipelines/run_full_rebuild.py
```

This runs:

1. `src/pipelines/run_foundation_pipeline.py`
2. `src/pipelines/run_signal_pipeline.py`
3. `src/pipelines/run_validation.py`

## Stepwise Retained Rebuild

If you want the retained workflow in separate stages:

```bash
python src/pipelines/run_foundation_pipeline.py
python src/pipelines/run_signal_pipeline.py
python src/pipelines/run_validation.py
```

## Dashboard Verification

```bash
python src/dashboard/run_dashboard.py --check
```

Optional local run:

```bash
python src/dashboard/run_dashboard.py
```

## Retained Outputs

The retained rebuild is expected to reproduce at least:

### Feature / model surfaces

- `out/features.csv`
- `out/onchain_features.csv`
- `out/models/hmm_pack.joblib`
- `out/models/hazard_pack.joblib`

### Foundation outputs

- `out/swing_detection/swings.csv`
- `out/swing_bridge/live_swing_state.csv`
- `out/swing_bridge/swing_taxonomy.csv`

### Retained signal outputs

- `out/swing_bottom/reversal_zone_dataset.csv`
- `out/swing_bottom/swing_extreme_timing.csv`
- `out/swing_bottom/buy_side_hybrid_scores.csv`
- `out/swing_bottom/swing_decision_layer.csv`
- `out/swing_bottom/swing_playbook_layer.csv`
- `out/swing_bottom/strategy_translation_layer.csv`
- `out/swing_bottom/rule_layer.csv`
- `out/swing_bottom/signal_layer.csv`

## When Upstream BTC Surfaces Must Be Refreshed

The retained pipelines assume the BTC feature/model surface already exists.

If those upstream surfaces are missing or stale, rebuild them first with the lower-level BTC commands:

```bash
python src/core/run_features.py
python src/core/run_regime_hmm.py --retrain-hmm
python src/core/run_hazard_train.py
python src/core/run_exposure.py
python src/core/run_onchain_features.py
python src/core/run_targets.py
python src/core/run_states.py
```

Then run the retained workflow again:

```bash
python src/pipelines/run_full_rebuild.py
```

## Compatibility Note

Old research-path and productive-path entrypoints still exist temporarily as wrappers.

Use `src/pipelines/` and `src/dashboard/` as the default workflow. Wrapper paths should be treated as temporary compatibility only.
