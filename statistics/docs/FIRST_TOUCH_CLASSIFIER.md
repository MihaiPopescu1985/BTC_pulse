# SAFE First-Touch Classifier

## Why add a first-touch classifier?

The 10-day 5-class path classifier is a broad path-structure tool. It is useful
for understanding whether price is more likely to range, continue, or reverse
over a wider horizon, but it is still too broad for the actual short-horizon
trade question:

- will price hit my small upside target before it breaks lower?

This first-touch classifier is a narrower execution-oriented model designed for:

- short bounce trades
- short continuation trades
- 1-day to 3-day horizon decisions

## Target classes

For anchor date `t`, using only SAFE state at `t`, the classifier predicts:

- `UP_FIRST`
- `DOWN_FIRST`
- `NONE`

Interpretation:

- `UP_FIRST`
  The upper barrier is touched before the lower barrier within horizon `H`.
- `DOWN_FIRST`
  The lower barrier is touched before the upper barrier within horizon `H`.
- `NONE`
  Neither barrier is touched within horizon `H`.

## Label construction

Given:

- anchor close = `close_t`
- upper barrier = `close_t * (1 + up_pct)`
- lower barrier = `close_t * (1 - down_pct)`

The label scans future OHLC over:

- `t+1 ... t+H`

using:

- future `high` for upper touches
- future `low` for lower touches

## Daily OHLC ambiguity

If on the same future candle both upper and lower barriers are touched before
either had been touched previously, daily data cannot determine intraday order.

Supported ambiguity modes:

- `skip_ambiguous` (default)
- `optimistic`
- `pessimistic`

Definitions:

- `optimistic`
  Resolve ambiguous same-day first touch as `UP_FIRST`.
- `pessimistic`
  Resolve ambiguous same-day first touch as `DOWN_FIRST`.
- `skip_ambiguous`
  Exclude that row from training and evaluation.

## Feature set

The model uses the same wide SAFE state vector as the supervised path
classifier, including when available:

- recent movement
- trend
- volatility
- positioning
- candle structure
- participation
- HMM semantic probabilities
- calibrated hazard probabilities
- SAFE outputs
- on-chain features

The first version uses all supported features available in the current SAFE
exports and evaluates their usefulness through feature importance.

## Model types

Supported:

- `gbt`
- `rf`
- `logreg`

Default:

- `gbt`

Each model uses:

- numeric imputation
- native multiclass probability outputs
- optional time-ordered calibration where the training split is large enough

## Leakage prevention

This is a strictly time-series-safe classifier:

- features come only from anchor date `t`
- labels come only from future OHLC after `t`
- each evaluation fold trains only on earlier dates
- no random split is used

Supported evaluation:

- expanding window
- rolling window

## Outputs

Training/evaluation writes:

- `predictions.csv`
- `report.json`
- `confusion_matrix.csv`
- `fold_summary.csv`
- `feature_importance.csv`

Optional saved model:

- `../out/first_touch_classifier/model.joblib`

## Report metrics

The report includes:

- `rows_evaluated`
- `class_distribution_realized`
- `class_distribution_predicted_mean`
- `multiclass_log_loss`
- `per_class_brier`
- `top1_accuracy`
- `top2_coverage`
- `macro_f1`
- `confusion_matrix_summary`
- majority-class baseline accuracy

## Interpretation examples

- High `UP_FIRST`
  Good short-horizon bounce candidate.
- High `DOWN_FIRST`
  Continuation risk dominates.
- High `NONE`
  No strong short-term excursion edge.

## Training / evaluation example

```bash
PYTHONPATH=statistics python statistics/src/run_first_touch_classifier_train_eval.py \
  --days 2 \
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
PYTHONPATH=statistics python statistics/src/run_first_touch_classifier_predict.py \
  --date 2026-03-29 \
  --model-path statistics/out/first_touch_classifier/model.joblib
```

## Caveats

- This is a short-horizon execution model, not a broad path-structure model.
- Same-day dual-barrier touches remain ambiguous under daily OHLC data.
- Rare classes can still be hard to separate cleanly.
- Walk-forward metrics matter more than in-sample fit.
