# SAFE v4.0 Playbook Layer Validation

## Purpose

This pass validates the existing playbook layer as a human-facing structural interpretation layer. It does not create entries, exits, position sizing, PnL logic, or backtests.

## Inputs

- Playbook layer: `out/swing_bottom/swing_playbook_layer.csv`
- Regime context merged from: `out/swing_bottom/reversal_zone_dataset.csv`
- Validation focus: chronological test split, time thirds, volatility regime, TS_50 regime, and shock-probability regime.

## Full-Test Label Separation

| playbook_label | row_count | row_share | buy_zone_5_rate | sell_zone_5_rate | avg_clarity | avg_conflict | avg_full_run_length_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DISTRIBUTION_WATCH | 179 | 37.8% | 7.8% | 54.2% | 0.435 | 0.174 | 4.162 |
| TRANSITION_WATCH | 147 | 31.0% | 37.4% | 19.0% | 0.224 | 0.262 | 2.320 |
| HIGH_CONFLICT | 119 | 25.1% | 32.8% | 8.4% | 0.102 | 0.351 | 2.412 |
| NO_ACTION | 15 | 3.2% | 6.7% | 6.7% | 0.076 | 0.146 | 1.000 |
| ACCUMULATION_WATCH | 14 | 3.0% | 57.1% | 0.0% | 0.386 | 0.177 | 1.143 |

## Validation Summary

| validation_setting | row_count | accumulation_minus_no_action_buy5 | distribution_minus_no_action_sell5 | high_conflict_minus_no_action_conflict | transition_row_share | accumulation_separates_from_no_action | distribution_separates_from_no_action | high_conflict_is_mixed | transition_breadth_ok |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_test | 474 | 0.505 | 0.475 | 0.206 | 0.310 | yes | yes | yes | yes |
| test_early_third | 158 | 0.400 | 0.481 | 0.192 | 0.386 | yes | yes | yes | yes |
| test_middle_third | 158 | 0.500 | 0.603 | 0.245 | 0.278 | yes | yes | yes | yes |
| test_late_third | 158 | 0.625 | 0.186 | 0.188 | 0.266 | yes | yes | yes | yes |
| regime_high_vol | 237 | 0.500 | 0.423 | 0.209 | 0.338 | yes | yes | yes | yes |
| regime_low_vol | 237 | 0.250 | 0.570 | 0.215 | 0.283 | yes | yes | yes | yes |
| regime_ts50_positive | 213 | 0.750 | 0.580 | 0.181 | 0.291 | yes | yes | yes | yes |
| regime_ts50_negative | 261 | 0.500 | 0.403 | 0.218 | 0.326 | yes | yes | yes | yes |
| regime_high_shock | 237 | 0.467 | 0.462 | 0.223 | 0.338 | yes | yes | yes | yes |
| regime_low_shock | 237 | 1.000 | 0.548 | 0.147 | 0.283 | yes | yes | yes | yes |

## Stability Readout

- Accumulation-watch separation rate: 100.0%
- Distribution-watch separation rate: 100.0%
- Watch-label contamination check pass rate: 100.0%
- No-action low-edge check pass rate: 77.8%
- High-conflict mixed-structure check pass rate: 100.0%
- Transition breadth check pass rate: 100.0%

## Transition Watch Breadth

`TRANSITION_WATCH` covers 31.0% of full-test rows. This is acceptable as a broad transition bucket: it is intentionally the largest bucket, but it still has lower clarity than watch labels and does not collapse the watch/no-action separation.

`NO_ACTION` is sparse in the test split, so its low-edge check is the least stable validation dimension. This does not break the playbook mapping, but it should be monitored as more data accumulates.

## Mapping Stability

The mapping remains deterministic by design: clear buy/sell decision states map to watch labels only when clarity is sufficient, `CONFLICT_OVERLAP` maps to `HIGH_CONFLICT`, and unclear/moderate states map to `TRANSITION_WATCH`. The detail CSV includes per-subset decision-state shares inside each playbook label.

## Final Decision

**Promote playbook layer.** The labels preserve their intended structural meaning across most time and regime slices.

The layer is suitable as a structural interpretation layer only. It is not a trading system and should not be read as execution logic.

## Output Files

- `out/swing_bottom/swing_playbook_validation.csv`
- `out/swing_bottom/swing_playbook_validation_detail.csv`
