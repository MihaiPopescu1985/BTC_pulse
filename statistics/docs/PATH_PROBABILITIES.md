# SAFE Path Probabilities

## Why add path probabilities?

SAFE already models:
- descriptive market state
- latent HMM regime probabilities
- calibrated 10-day hazard probabilities
- marginal touch probabilities such as `P(+2% within 10d)`

Marginal touch probabilities are useful, but they do not distinguish between
very different path shapes. For example:
- direct downside continuation
- downside first, then recovery
- upside first, then failure
- no meaningful excursion

This layer adds a mechanical path taxonomy on top of the existing
regime-conditioned simulation engine.

## Path taxonomy

The first implementation uses a compact 5-class taxonomy over horizon `H`:

- `RANGE`
  No barrier is touched within the horizon.
- `UP_FIRST_ONLY`
  The upper barrier is touched, the lower barrier is not.
- `DOWN_FIRST_ONLY`
  The lower barrier is touched, the upper barrier is not.
- `UP_THEN_DOWN`
  The upper barrier is touched first, and the lower barrier is touched later.
- `DOWN_THEN_UP`
  The lower barrier is touched first, and the upper barrier is touched later.

Default barriers:
- upper barrier: `+2%`
- lower barrier: `-2%`

These are configurable with:
- `--up-pct`
- `--down-pct`

## Simulation method

Given SAFE state on anchor date `t`, the model:

1. reads semantic regime probabilities on date `t`
2. calibrates daily return moments from historical data weighted by lagged
   regime probabilities
3. simulates forward daily-close paths for `H` steps
4. classifies each path into one of the 5 path labels
5. estimates `P(path_label | X_t)` by simulation frequency

Supported simulation modes:

- `mixture`
  Regime-weighted iid Gaussian daily log returns.
- `markov`
  Markov-switching Gaussian daily log returns using the HMM transition matrix.

## Realized historical labels

Historical evaluation uses real future OHLC data:

- anchor close = close on day `t`
- upper barrier = `close_t * (1 + up_pct)`
- lower barrier = `close_t * (1 - down_pct)`
- scan days `t+1 ... t+H`
- detect first touch using:
  - daily `high` for upper barrier
  - daily `low` for lower barrier

## Ambiguity from daily candles

Daily OHLC cannot reveal intraday ordering when both barriers are touched on the
same future candle before either had been touched previously.

Supported ambiguity modes:

- `skip_ambiguous`
  Skip that historical row from evaluation. This is the default.
- `optimistic`
  Resolve the tie as `UP_THEN_DOWN`.
- `pessimistic`
  Resolve the tie as `DOWN_THEN_UP`.
- `label_as_both_same_day`
  Emit a dedicated realized label `AMBIGUOUS_BOTH_SAME_DAY`.

For research and benchmarking, `skip_ambiguous` is the safest default.

## Interpretation examples

- High `DOWN_FIRST_ONLY`
  Direct downside continuation risk dominates.
- High `DOWN_THEN_UP`
  Oversold or flush-then-bounce setup.
- High `UP_THEN_DOWN`
  Rally-first but fragile continuation profile.
- High `UP_FIRST_ONLY`
  Direct upside continuation dominates.
- High `RANGE`
  No strong short-horizon excursion edge.

## Single-date CLI

Estimate path probabilities for one anchor date:

```bash
PYTHONPATH=statistics python statistics/src/run_path_probabilities.py \
  --date 2026-03-29 \
  --days 10 \
  --up-pct 0.02 \
  --down-pct 0.02 \
  --mode markov \
  --sims 20000
```

Output:
- `statistics/out/path_probabilities/path_probabilities.json`

## Historical evaluation CLI

Evaluate predicted path probabilities against realized future OHLC labels:

```bash
PYTHONPATH=statistics python statistics/src/run_path_pathlabel_eval.py \
  --days 10 \
  --up-pct 0.02 \
  --down-pct 0.02 \
  --mode markov \
  --sims 5000 \
  --ambiguity-mode skip_ambiguous
```

Outputs:
- `statistics/out/path_probabilities_eval/predictions.csv`
- `statistics/out/path_probabilities_eval/report.json`
- `statistics/out/path_probabilities_eval/confusion_matrix.csv`

## Output fields

Single-date path probability output includes:
- anchor date
- anchor close
- simulation mode
- regime probabilities
- barrier levels
- path probabilities
- path counts
- mean / median forward return
- probability of finishing positive or negative
- average max drawdown / run-up

Historical evaluation output includes:
- realized label
- predicted path probabilities
- top-1 and top-2 label coverage
- multiclass log loss
- per-class Brier scores
- confusion matrix

## Caveats

- The simulation engine models daily closes, not intraday paths.
- Realized labels use OHLC highs/lows, so evaluation is stricter than the
  simulated close-path approximation.
- Same-day dual-barrier touches are fundamentally ambiguous under daily data.
- This layer is designed to be explicit and testable, not narrative.
