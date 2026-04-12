# SAFE v4.0 Rule Layer Calibration

## Purpose

This pass calibrates the first explicit rule layer. It only tests compact eligibility-rule variations; it does not add execution, PnL, stops, position sizing, portfolio logic, or backtests.

## Variants Tested

- `current_age2_symmetric`: current reference, buy and sell require active context age >= 2.
- `age1_symmetric`: buy and sell eligible immediately when active context is ready.
- `buy_age1_sell_age2`: buy eligible immediately, sell keeps age >= 2.
- `buy_age1_sell_age2_strong_first_day`: asymmetric persistence plus strong first-day promotion.
- `age2_with_strong_first_day`: current age-2 rule plus strong first-day promotion.

Strong first-day promotion requires clarity >= 0.40, conflict <= 0.16, and absolute score spread >= 0.35.

## Permission / Contamination Tradeoff

| variant | long_eligible_share | long_buy_zone_5_rate | long_sell_zone_5_contamination | sell_eligible_share | sell_sell_zone_5_rate | sell_buy_zone_5_contamination | await_confirmation_share | blocked_share | invalidated_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current_age2_symmetric | 1.6% | 49.0% | 2.0% | 9.1% | 51.0% | 3.1% | 58.0% | 31.3% | 12.5% |
| age1_symmetric | 6.6% | 50.2% | 1.0% | 18.4% | 51.6% | 2.6% | 43.7% | 31.3% | 12.5% |
| buy_age1_sell_age2 | 6.6% | 50.2% | 1.0% | 9.1% | 51.0% | 3.1% | 53.0% | 31.3% | 12.5% |
| buy_age1_sell_age2_strong_first_day | 6.6% | 50.2% | 1.0% | 11.8% | 51.2% | 2.4% | 50.3% | 31.3% | 12.5% |
| age2_with_strong_first_day | 2.5% | 50.0% | 1.3% | 11.8% | 51.2% | 2.4% | 54.4% | 31.3% | 12.5% |

## Delta Versus Current Reference

| variant | long_coverage_delta_vs_current | long_quality_delta_vs_current | long_contamination_delta_vs_current | sell_coverage_delta_vs_current | sell_quality_delta_vs_current | sell_contamination_delta_vs_current | await_delta_vs_current |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current_age2_symmetric | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| age1_symmetric | 0.049 | 0.012 | -0.010 | 0.093 | 0.006 | -0.006 | -0.143 |
| buy_age1_sell_age2 | 0.049 | 0.012 | -0.010 | 0.000 | 0.000 | 0.000 | -0.049 |
| buy_age1_sell_age2_strong_first_day | 0.049 | 0.012 | -0.010 | 0.028 | 0.002 | -0.007 | -0.077 |
| age2_with_strong_first_day | 0.009 | 0.010 | -0.007 | 0.028 | 0.002 | -0.007 | -0.036 |

## Recommendation

**Promote calibrated rule layer: `age1_symmetric`.** The recommended variant expands permissions while preserving directional cleanliness within the calibration tolerance band.

The recommended variant has long eligible share 6.6%, long buy-zone 5% rate 50.2%, long sell-zone contamination 1.0%, sell eligible share 18.4%, and sell sell-zone 5% rate 51.6%.

## Interpretation

The current layer is structurally correct but over-gated. The calibration mainly shows whether first-day active contexts should be permitted instead of held in confirmation. This remains a structural permission layer only: eligibility means a later strategy may evaluate that side, not that an order should be placed.

## Output Files

- `out/swing_bottom/rule_layer_calibration.csv`
- `out/swing_bottom/rule_layer_calibration_detail.csv`
