# SAFE v4.0 Reversal Zone Models

## Targets

- buy primary target: `buy_zone_within_5pct_above_low`
- buy stricter target: `buy_zone_within_3pct_above_low`
- sell primary target: `sell_zone_within_5pct_below_high`
- sell stricter target: `sell_zone_within_3pct_below_high`

## Leakage Exclusions

- excluded all columns with prefixes: `next_`, `containing_`, `buy_zone_`, `sell_zone_`, `dist_to_current_`, `current_confirmed_`
- excluded exact label/bookkeeping columns: `date`, `row_is_in_confirmed_down_swing`, `row_is_in_confirmed_up_swing`
- excluded raw date helpers: `last_confirmed_pivot_date`, `current_leg_start_date`
- excluded confirmed-pivot price helpers: `current_leg_start_price`, `last_confirmed_pivot_price`
- retained causal feature count: `90`
- raw causal candidate count before train-constant filtering: `93`

## Leakage Fix Pass

- removed `current_leg_start_price` and `last_confirmed_pivot_price` from the model inputs
- these fields are too close to confirmed-swing bookkeeping and make the baseline less trustworthy as a causal reversal detector
- the results below should be treated as the corrected baseline for the current reversal-zone pipeline

## Chronological Split

- train: `2371` rows, `2017-08-17` -> `2024-02-12`
- validation: `508` rows, `2024-02-13` -> `2025-07-04`
- test: `509` rows, `2025-07-05` -> `2026-11-25`

## Buy Model Row Metrics

- validation ROC AUC: `0.805`
- validation PR AUC: `0.373`
- validation Brier: `0.203`
- validation Log loss: `0.601`
- validation Precision / Recall / F1: `0.351` / `0.813` / `0.490`
- test ROC AUC: `0.717`
- test PR AUC: `0.422`
- test Brier: `0.238`
- test Log loss: `0.705`
- test Precision / Recall / F1: `0.427` / `0.680` / `0.525`

## Sell Model Row Metrics

- validation ROC AUC: `0.773`
- validation PR AUC: `0.512`
- validation Brier: `0.293`
- validation Log loss: `0.830`
- validation Precision / Recall / F1: `0.372` / `0.935` / `0.533`
- test ROC AUC: `0.788`
- test PR AUC: `0.570`
- test Brier: `0.311`
- test Log loss: `0.900`
- test Precision / Recall / F1: `0.392` / `0.967` / `0.558`

## Top-Bucket Quality

- buy test top 10% primary / strict hit rate: `0.431` / `0.275`
- buy test top 10% avg distance to low: `0.121`
- sell test top 10% primary / strict hit rate: `0.686` / `0.510`
- sell test top 10% avg distance to high: `0.042`

## Swing-Level Capture

- buy threshold swing count / captured / rate: `47.000` / `44.000` / `0.936`
- buy top-decile captured / rate: `12.000` / `0.255`
- buy avg first-signal distance to low: `0.072`
- sell threshold swing count / captured / rate: `48.000` / `48.000` / `1.000`
- sell top-decile captured / rate: `17.000` / `0.354`
- sell avg first-signal distance to high: `0.055`

## Most Important Coefficients

### Buy

- `numeric__run_magnitude_up`: `-2.4195`
- `numeric__r1`: `-1.3139`
- `numeric__ONCHAIN_DOMINANCE`: `-1.2929`
- `numeric__atr`: `1.2157`
- `numeric__atr_pct`: `-1.1847`
- `numeric__conviction_safe`: `1.0782`
- `categorical__HMM_LABEL_CORE`: `1.0039`
- `numeric__ONCHAIN_TX_MID`: `0.9162`

### Sell

- `numeric__r1`: `1.0980`
- `numeric__band_w`: `0.8055`
- `numeric__P_REBOUND_10D_CAL`: `-0.6945`
- `categorical__live_swing_direction_up`: `0.6653`
- `numeric__return_accel`: `-0.6566`
- `numeric__downside_semi_vol`: `0.6293`
- `categorical__live_swing_direction_unknown`: `-0.5947`
- `categorical__HMM_LABEL_CORE`: `-0.5856`

## Interpretation

- the baseline asks whether the retained causal feature surface can score good-enough reversal zones rather than exact pivots
- buy and sell should be read separately because late-down-swing and late-up-swing structure are not symmetric in BTC
- the 5% primary targets are the operational training targets; the 3% labels are stricter alignment checks on the same scored rows
- swing capture rate matters more than row-level classification alone because later use will care about capturing many swings, not every row inside a zone
- this corrected baseline should be judged more on whether swing capture and top-bucket quality remain useful after the leakage fix than on matching the earlier raw scores
