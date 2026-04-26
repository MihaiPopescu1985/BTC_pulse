# SAFE Layer Contracts

## Purpose

This note records the first lightweight contract checks for the retained SAFE stack. The checks are intentionally small: they define expected CSV shapes, required columns, date behavior, and dashboard compatibility before deeper restructuring begins.

This is not a schema framework and does not change pipeline behavior.

## Contract Groups

### Feature Surface

Defined in `src/contracts/safe_v4.py`.

Checks:

- `out/features.csv`
- `out/onchain_features.csv`
- optional generated `out/targets.csv`
- optional generated `out/states.csv`

Expectations:

- one row per date where a `date` column exists
- no duplicate dates
- ascending dates
- required core columns exist
- future-derived swing/zone columns are not present in causal feature surfaces

### Swing / Structure Foundation

Checks:

- `out/swing_detection/swings.csv`
- optional `out/swing_detection/swing_sensitivity_summary.csv`
- `out/swing_bridge/live_swing_state.csv`
- `out/swing_bridge/swing_taxonomy.csv`
- `out/swing_bridge/swing_condition_mapping.csv`

Expectations:

- required swing/taxonomy/mapping columns exist
- live swing state remains daily and causal
- containing-swing and next-swing mapping semantics stay explicit

### Retained Signal Stack

Checks:

- `out/swing_bottom/reversal_zone_dataset.csv`
- `out/swing_bottom/swing_extreme_timing.csv`
- `out/swing_bottom/buy_side_hybrid_scores.csv`
- `out/swing_bottom/swing_decision_layer.csv`
- `out/swing_bottom/swing_playbook_layer.csv`
- `out/swing_bottom/strategy_translation_layer.csv`
- `out/swing_bottom/rule_layer.csv`
- `out/swing_bottom/signal_layer.csv`

Expectations:

- daily outputs have a `date` column
- no duplicate dates
- ascending dates
- retained score/state columns exist
- downstream layers can rely on stable names such as `promoted_buy_timing_score`, `promoted_sell_timing_score`, `decision_state`, `playbook_label`, `operational_state`, `rule_state`, and `signal_state`

### Dashboard-Facing Views

Checks every registered view in `src/research/v4_iteration/dashboard/view_registry.py`.

Expectations:

- registered CSV exists unless missing outputs are explicitly allowed
- `date` and `close` exist
- all registered score/component/label/diagnostic columns exist
- no duplicate dates
- ascending dates

## How To Run

Strict mode:

```bash
python statistics/src/contracts/run_contract_checks.py
```

Preparation mode when retained outputs have not all been regenerated yet:

```bash
python statistics/src/contracts/run_contract_checks.py --allow-missing
```

Specific group:

```bash
python statistics/src/contracts/run_contract_checks.py --group features
python statistics/src/contracts/run_contract_checks.py --group dashboard --allow-missing
```

## Intended Use During Restructuring

Before moving modules:

1. Run the contract checks.
2. Move or refactor one small area.
3. Regenerate any affected retained outputs if needed.
4. Run the contract checks again.
5. Run the dashboard check.

The goal is to make later restructuring verifiable without relying on memory of the v4.0 iteration history.
