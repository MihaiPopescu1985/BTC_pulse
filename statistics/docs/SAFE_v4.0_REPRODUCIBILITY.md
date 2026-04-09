# SAFE v4.0 Reproducibility

## Current retained scope

This note covers only the retained repository scope after cleanup:

- productive BTC feature and model pipeline
- retained indicator-audit foundation
- retained swing-detection foundation
- retained swing-bridge foundation

It does not cover deleted branch-hunting, walkforward-policy, or strategy-layer experiments.

## Inputs

- `statistics/data/daily_price.json`
- `statistics/data/daily_amounts.json`
- `statistics/data/daily_tx_size.json`

## Core date range

- `2017-08-17` -> `2026-04-02`

## Productive rebuild

```bash
PYTHONPATH=statistics python statistics/src/core/run_features.py
PYTHONPATH=statistics python statistics/src/core/run_regime_hmm.py --retrain-hmm
PYTHONPATH=statistics python statistics/src/core/run_hazard_train.py
PYTHONPATH=statistics python statistics/src/core/run_exposure.py
PYTHONPATH=statistics python statistics/src/core/run_onchain_features.py
PYTHONPATH=statistics python statistics/src/core/run_targets.py
PYTHONPATH=statistics python statistics/src/core/run_states.py
```

Outputs:

- `statistics/out/features.csv`
- `statistics/out/onchain_features.csv`
- `statistics/out/targets.csv`
- `statistics/out/states.csv`
- `statistics/out/models/hmm_pack.joblib`
- `statistics/out/models/hazard_pack.joblib`

## Indicator audit foundation

```bash
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py
```

Retained output:

- `statistics/out/indicator_audit/indicator_reliability.csv`

## Swing foundation

```bash
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_detection/run_swing_detection.py
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_detection/run_swing_sensitivity.py
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_bridge/run_live_swing_state.py
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_bridge/run_swing_taxonomy.py
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_bridge/run_swing_condition_mapping.py
```

Outputs:

- `statistics/out/swing_detection/swings.csv`
- `statistics/out/swing_detection/swing_sensitivity_summary.csv`
- `statistics/out/swing_bridge/live_swing_state.csv`
- `statistics/out/swing_bridge/swing_taxonomy.csv`
- `statistics/out/swing_bridge/swing_condition_mapping.csv`

## Notes

- This is a retained-scope reproducibility note, not a frozen record of deleted experiments.
- The repository is now centered on the productive BTC pipeline plus swing-structure research needed for the reset toward swing-phase and bottom modeling.
