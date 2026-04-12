# SAFE v4.0 Bottom Model Baseline

## Target

- default target: `bottom_zone_time_20pct`
- baseline variant: all eligible rows, strict chronological split, no shuffle
- model: class-balanced logistic regression

## Feature Set

- causal price, volatility, participation, regime, hazard, on-chain, and live swing-state fields
- categorical handling: one-hot encoding for non-numeric causal fields such as `live_swing_direction`
- numeric handling: median imputation plus standardization
- retained feature columns: `95`
- excluded columns by leakage rule or identifier handling: `30`
- additional columns dropped as constant / empty in train: `3`

Leakage exclusion rule:
- drop all `next_*` columns
- drop all `containing_*` columns
- drop all bottom-label / future-bottom target columns
- drop raw date-like helper columns and constant granularity identifiers

## Row Counts And Splits

- total eligible rows: `3158`
- train: `2210` rows, `2017-08-17` -> `2023-09-04`
- validation: `474` rows, `2023-09-05` -> `2024-12-21`
- test: `474` rows, `2024-12-22` -> `2026-04-09`

## Classifier Metrics

| Split | ROC AUC | PR AUC | Brier | Log loss | Precision | Recall | F1 | Positive rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `validation` | 0.913 | 0.600 | 0.1433 | 0.4335 | 0.348 | 0.931 | 0.507 | 12.24% |
| `test` | 0.894 | 0.576 | 0.1045 | 0.3248 | 0.479 | 0.652 | 0.552 | 14.56% |

## Top-Bucket Quality On Test

| Bucket | Rows | Hit rate | Avg near low 2% | Avg near low 3% | Avg dist to next low | Avg days to next low |
| --- | --- | --- | --- | --- | --- | --- |
| top `5`% | 24 | 58.33% | 0.00% | 16.67% | -6.82% | 20.6 |
| top `10`% | 48 | 60.42% | 6.25% | 22.92% | -6.67% | 21.5 |
| top `20`% | 95 | 48.42% | 15.79% | 29.47% | -6.29% | 14.0 |

## Most Important Coefficients

| Rank | Feature | Coefficient |
| --- | --- | --- |
| 1 | `numeric__HMM_DOM` | 1.4747 |
| 2 | `categorical__live_swing_direction_down` | 1.4211 |
| 3 | `numeric__distance_from_last_pivot_pct` | -1.4119 |
| 4 | `categorical__live_swing_direction_up` | -1.3652 |
| 5 | `numeric__dist_from_mean_vol_units` | 1.1776 |
| 6 | `categorical__HMM_LABEL_SHOCK` | -1.1570 |
| 7 | `numeric__band_pos` | -0.9753 |
| 8 | `categorical__HMM_LABEL_SURGE` | 0.8914 |
| 9 | `numeric__atr` | 0.8350 |
| 10 | `numeric__ONCHAIN_WHALE_SHARE` | 0.7454 |
| 11 | `numeric__ewma_vol` | -0.7042 |
| 12 | `numeric__HMM_STATE_3` | -0.6920 |

## Interpretation

- the first leakage-safe baseline shows usable signal on the held-out test segment.
- the current 0.5 threshold behaves more like a broad detector than a precise late-stage bottom selector.
- this is still a baseline modeling pass only: no trade rules, exits, or backtests are implied here.
