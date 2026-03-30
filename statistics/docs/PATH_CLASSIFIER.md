# SAFE Supervised Path Classifier

## Why add a supervised path classifier?

The regime-only path simulator conditions mostly on semantic HMM probabilities
and regime-calibrated return moments. That is useful as a structural baseline,
but it is too coarse for sequence-sensitive path classes such as:

- `UP_THEN_DOWN`
- `DOWN_THEN_UP`

The supervised path classifier upgrades that layer from:

- regime probabilities -> simulated path labels

to:

- full SAFE state at `t` -> multiclass path probabilities over `t+1 ... t+H`

This lets the model use trend, volatility, positioning, candle structure,
participation, HMM, hazard, SAFE outputs, and on-chain context jointly.

## Path classes

The classifier predicts the same 5-class taxonomy used by the explicit path
simulation layer:

- `RANGE`
- `UP_FIRST_ONLY`
- `DOWN_FIRST_ONLY`
- `UP_THEN_DOWN`
- `DOWN_THEN_UP`

Anchor state:
- features on date `t`

Target:
- realized path label from future OHLC on `t+1 ... t+H`

## Label generation

For each anchor date `t`:

- anchor close = `close_t`
- upper barrier = `close_t * (1 + up_pct)`
- lower barrier = `close_t * (1 - down_pct)`
- scan future daily `high` / `low` over the next `H` days
- assign the realized path label based on first-touch ordering

Ambiguity handling:
- `skip_ambiguous` (default)
- `optimistic`
- `pessimistic`
- `label_as_both_same_day`

Default for supervised training and evaluation is `skip_ambiguous`.

## Feature set

The first implementation uses an explicit wide SAFE state vector. Candidate
features include:

- trend:
  `TS_*`, `LR_*`, `ER_*`, `RVR_*`
- volatility:
  `vol_20`, `atr_pct`, `parkinson_vol`, `garman_klass_vol`, `ewma_vol`,
  `upside_semi_vol`, `downside_semi_vol`
- positioning:
  `band_w`, `band_pos`, `dist_from_mean_vol_units`,
  `time_since_local_high`, `time_since_local_low`
- candle structure:
  `body_to_range_ratio`, `upper_wick_ratio`, `lower_wick_ratio`, `close_in_range`
- recent movement:
  `R_3`, `R_7`, `R_14`, `run_length_*`, `run_magnitude_*`, `return_accel`
- participation:
  `relative_volume_20`, `volume_z`
- HMM:
  `P_CORE_HMM`, `P_DRIFT_HMM`, `P_SHOCK_HMM`, `P_SURGE_HMM`, `HMM_CONF`
- hazard:
  `P_CORRECTION_10D_CAL`, `P_REBOUND_10D_CAL`
- SAFE outputs:
  `direction_safe`, `E_target_safe`, `entry_step_safe`, `conviction_safe`,
  `D_score_safe`, `hard_risk_off_flag_safe`
- on-chain:
  `ONCHAIN_VOL_Z`, `ONCHAIN_DOM_Z`, `ONCHAIN_WHALE_SHARE_Z`,
  `ONCHAIN_AMOUNT_PCT`, `ONCHAIN_WHALE_TX_PCT`, `ONCHAIN_DOM_PCT`

Missing columns are handled gracefully. If the default BTC
`../out/onchain_features.json` exists, it is merged automatically.

## Model types

Supported model types:

- `gbt`
  `GradientBoostingClassifier`
- `rf`
  `RandomForestClassifier`
- `logreg`
  multinomial logistic regression baseline

Each model uses a simple numeric preprocessing pipeline. A small time-ordered
calibration split is used when the training window is large enough; otherwise
the classifier falls back to native `predict_proba`.

## Time-series leakage prevention

Walk-forward evaluation is strictly time ordered:

- features are from anchor date `t`
- labels come only from future OHLC after `t`
- each evaluation fold trains only on dates strictly before the test fold
- no random train/test shuffling is used

Supported evaluation styles:

- expanding window
- rolling window (using the most recent `min_train_rows` before each fold)

## Outputs

Training/evaluation writes:

- `predictions.csv`
- `report.json`
- `confusion_matrix.csv`
- `feature_importance.csv`
- `fold_summary.csv`

Optional saved model:

- `../out/path_classifier/model.joblib`

## Feature importance

Global feature importance is exported after a full refit:

- tree models: native impurity importance
- logistic regression: mean absolute coefficient magnitude

The CSV also includes a coarse feature family tag:

- trend
- volatility
- positioning
- candles
- recent_movement
- participation
- hmm
- hazard
- safe
- onchain

## Training / evaluation example

```bash
PYTHONPATH=statistics python statistics/src/run_path_classifier_train_eval.py \
  --days 10 \
  --up-pct 0.02 \
  --down-pct 0.02 \
  --ambiguity-mode skip_ambiguous \
  --eval-start-date 2024-01-01 \
  --eval-end-date 2026-03-01 \
  --min-train-rows 250 \
  --fold-size-days 30 \
  --model-type gbt \
  --save-model
```

## Prediction example

```bash
PYTHONPATH=statistics python statistics/src/run_path_classifier_predict.py \
  --date 2026-03-29 \
  --model-path statistics/out/path_classifier/model.joblib
```

## Interpretation examples

- High `DOWN_FIRST_ONLY`
  Direct downside continuation risk dominates.
- High `DOWN_THEN_UP`
  Flush-first then rebound behavior is favored.
- High `UP_THEN_DOWN`
  Rally-first but fragile path profile.
- High `RANGE`
  No strong excursion edge over the chosen horizon.

## Caveats

- The classifier can overfit if the evaluation window is too short.
- Rare path classes may stay difficult to predict well.
- Same-day dual-barrier touches remain ambiguous under daily OHLC data.
- Native or lightly calibrated classifier probabilities should still be checked
  against walk-forward log loss and per-class Brier scores before relying on
  them operationally.
