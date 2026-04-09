# SAFE v4.0 Research Structure Note

This was a structure-only cleanup of `statistics/src/research/v4_iteration/`.

## What Was Moved

### Stable core research layer

These folders are now treated as reusable research building blocks:

- `src/research/v4_iteration/core/indicator_audit/`
- `src/research/v4_iteration/core/interaction_discovery/`
- `src/research/v4_iteration/core/swing_detection/`
- `src/research/v4_iteration/core/swing_bridge/`

### Active research layer

These scripts remain useful for current ongoing research work:

- `src/research/v4_iteration/research_active/run_decision_analysis.py`
- `src/research/v4_iteration/research_active/run_policy_backtest.py`
- `src/research/v4_iteration/research_active/run_state_outcomes.py`
- `src/research/v4_iteration/research_active/safe_interpreter_v2.py`

### Archived research layer

These scripts were kept intact but moved out of the active surface:

- `src/research/v4_iteration/research_archive/run_feature_redundancy.py`
- `src/research/v4_iteration/research_archive/run_calibration.py`
- `src/research/v4_iteration/research_archive/run_decision_validation.py`
- `src/research/v4_iteration/research_archive/safe_interpreter.py`

## Why This Split Was Introduced

- the research area had multiple script lifecycles mixed at one level
- stable research foundations were being mixed with one-off or older descriptive scripts
- the interpreter layer was mixed with both active and older research code

The new split makes it clearer which code is:

- reusable research infrastructure
- currently active research work
- archived but still worth keeping

## What Was Not Changed

- no productive pipeline logic
- no walk-forward logic
- no model logic
- no broad output/doc reorganization
- no deletions

This was a minimal hierarchy cleanup intended to preserve behavior while making the research surface easier to navigate.
