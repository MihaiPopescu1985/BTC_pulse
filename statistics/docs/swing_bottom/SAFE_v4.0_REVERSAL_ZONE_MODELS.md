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

- train: `2210` rows, `2017-08-17` -> `2023-09-04`
- validation: `474` rows, `2023-09-05` -> `2024-12-21`
- test: `474` rows, `2024-12-22` -> `2026-04-09`

## Buy Model Row Metrics

- validation ROC AUC: `0.829`
- validation PR AUC: `0.396`
- validation Brier: `0.186`
- validation Log loss: `0.545`
- validation Precision / Recall / F1: `0.378` / `0.866` / `0.526`
- test ROC AUC: `0.782`
- test PR AUC: `0.469`
- test Brier: `0.195`
- test Log loss: `0.576`
- test Precision / Recall / F1: `0.452` / `0.718` / `0.554`

## Sell Model Row Metrics

- validation ROC AUC: `0.719`
- validation PR AUC: `0.435`
- validation Brier: `0.369`
- validation Log loss: `1.076`
- validation Precision / Recall / F1: `0.317` / `0.927` / `0.472`
- test ROC AUC: `0.799`
- test PR AUC: `0.557`
- test Brier: `0.478`
- test Log loss: `1.589`
- test Precision / Recall / F1: `0.320` / `1.000` / `0.485`

## Top-Bucket Quality

- buy test top 10% primary / strict hit rate: `0.438` / `0.292`
- buy test top 10% avg distance to low: `0.070`
- sell test top 10% primary / strict hit rate: `0.625` / `0.438`
- sell test top 10% avg distance to high: `0.039`

## Swing-Level Capture

- buy threshold swing count / captured / rate: `45.000` / `42.000` / `0.933`
- buy top-decile captured / rate: `16.000` / `0.356`
- buy avg first-signal distance to low: `0.072`
- sell threshold swing count / captured / rate: `44.000` / `44.000` / `1.000`
- sell top-decile captured / rate: `13.000` / `0.295`
- sell avg first-signal distance to high: `0.058`

## Most Important Coefficients

### Buy

- `numeric__run_magnitude_up`: `-2.2038`
- `numeric__ONCHAIN_DOMINANCE`: `-1.4581`
- `numeric__r1`: `-1.3160`
- `numeric__atr`: `1.1484`
- `numeric__ONCHAIN_TX_MID`: `1.1286`
- `numeric__HMM_DOM`: `1.0887`
- `numeric__atr_pct`: `-0.9575`
- `numeric__E_target_safe`: `-0.9567`

### Sell

- `numeric__r1`: `1.2745`
- `numeric__band_w`: `1.0090`
- `numeric__P_REBOUND_10D_CAL`: `-0.8535`
- `categorical__live_swing_direction_up`: `0.7446`
- `numeric__return_accel`: `-0.7433`
- `numeric__dist_from_mean_vol_units`: `-0.6662`
- `numeric__ewma_vol`: `-0.6299`
- `numeric__P_CORE_HMM`: `0.5551`

## Interpretation

- the baseline asks whether the retained causal feature surface can score good-enough reversal zones rather than exact pivots
- buy and sell should be read separately because late-down-swing and late-up-swing structure are not symmetric in BTC
- the 5% primary targets are the operational training targets; the 3% labels are stricter alignment checks on the same scored rows
- swing capture rate matters more than row-level classification alone because later use will care about capturing many swings, not every row inside a zone
- this corrected baseline should be judged more on whether swing capture and top-bucket quality remain useful after the leakage fix than on matching the earlier raw scores
