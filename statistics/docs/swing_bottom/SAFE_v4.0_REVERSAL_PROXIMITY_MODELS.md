# SAFE v4.0 Reversal Proximity Models

## Targets

- buy target: `dist_to_current_down_swing_low_pct`
- sell target: `dist_to_current_up_swing_high_pct`

## Leakage Exclusions

- excluded all columns with prefixes: `next_`, `containing_`, `buy_zone_`, `sell_zone_`, `dist_to_current_`, `current_confirmed_`
- excluded confirmed-pivot helpers: `current_leg_start_price`, `last_confirmed_pivot_price`, `last_confirmed_pivot_date`, `current_leg_start_date`
- retained only causal price, on-chain, regime/hazard, and live swing-state fields

## Filtered Sample Sizes

- buy rows: `1442`
- buy train: `1009` rows, `2017-09-03` -> `2023-08-03`
- buy validation: `216` rows, `2023-08-04` -> `2025-01-10`
- buy test: `217` rows, `2025-01-11` -> `2026-03-29`
- sell rows: `1696`
- sell train: `1187` rows, `2017-08-26` -> `2023-10-12`
- sell validation: `254` rows, `2023-10-13` -> `2024-11-22`
- sell test: `255` rows, `2024-11-27` -> `2026-03-25`
- buy retained causal feature count: `90`
- sell retained causal feature count: `90`

## Regression Metrics

- buy validation MAE / RMSE / R² / Spearman / Pearson: `0.096` / `0.126` / `-3.620` / `0.126` / `0.100`
- buy test MAE / RMSE / R² / Spearman / Pearson: `0.383` / `0.406` / `-36.135` / `-0.092` / `0.068`
- sell validation MAE / RMSE / R² / Spearman / Pearson: `0.138` / `0.170` / `-3.002` / `0.105` / `0.093`
- sell test MAE / RMSE / R² / Spearman / Pearson: `0.264` / `0.280` / `-42.008` / `0.214` / `0.190`

## Top-Bucket Ranking Quality

- buy test top 10% avg / median distance: `0.069` / `0.068`
- buy test top 10% zone 5% / 3% hit rate: `0.318` / `0.227`
- sell test top 10% avg / median distance: `0.051` / `0.045`
- sell test top 10% zone 5% / 3% hit rate: `0.577` / `0.308`

## Per-Swing Best Pick

- buy swings in test: `43.000`
- buy best-pick avg / median distance: `0.056` / `0.045`
- buy best-pick within 5% / 3%: `0.512` / `0.395`
- sell swings in test: `47.000`
- sell best-pick avg / median distance: `0.040` / `0.027`
- sell best-pick within 5% / 3%: `0.702` / `0.553`

## Most Important Coefficients

### Buy

- `numeric__atr_pct`: `0.1055`
- `numeric__atr`: `-0.0897`
- `numeric__P_DRIFT_HMM`: `0.0870`
- `numeric__HMM_STATE_0`: `0.0870`
- `numeric__volume_z`: `0.0804`
- `numeric__HMM_STATE_1`: `0.0790`
- `numeric__P_SHOCK_HMM`: `0.0790`
- `numeric__volume_log1p`: `-0.0738`

### Sell

- `numeric__band_hi`: `-0.0815`
- `categorical__live_swing_direction_unknown`: `-0.0703`
- `numeric__atr`: `0.0635`
- `numeric__parkinson_vol`: `-0.0611`
- `numeric__ewma_vol`: `0.0592`
- `numeric__ONCHAIN_AMOUNT_LOG`: `0.0589`
- `numeric__ONCHAIN_DOMINANCE`: `-0.0586`
- `numeric__ONCHAIN_TX_MID`: `0.0519`

## Interpretation

- this step asks whether continuous distance targets improve point selection inside already-known swing types
- better top-bucket distance and better best-per-swing picks matter more than broad row coverage here
- if best-per-swing distance improves materially relative to the binary zone baseline, the system is learning intra-swing ranking rather than only broad phase detection
- the next step should depend on whether ranking quality is limited mainly by the objective, the feature surface, or the simple linear model
