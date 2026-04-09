# SAFE v4.0 Position / Mean-Reversion Interpretive Audit

## Scope
This audit covers the current position / mean-reversion family:

- `band_pos`
- `band_w`
- `dist_from_mean_vol_units`
- `time_since_local_high`
- `time_since_local_low`

These indicators all describe where price sits relative to recent structure.

They do not primarily describe:

- directional trend
- total volatility magnitude

`range_score` is not present in the current repository.

## Repository context

All five indicators are computed in [price_features.py](/home/mihai/Documents/BTC_pulse/statistics/src/features/price_features.py).

Current direct productive / validation usage:

- `band_pos`
  - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
  - [run_decision_analysis_walkforward.py](/home/mihai/Documents/BTC_pulse/statistics/src/walkforward/run_decision_analysis_walkforward.py)
  - [exposure.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/exposure.py)
  - [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py)
  - [hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py)
- `band_w`
  - [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py)
  - [hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py)
- `dist_from_mean_vol_units`
  - [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py)
  - [hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py)

Current descriptive / research usage:

- all five appear in:
  - [safe_interpreter.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/research_archive/safe_interpreter.py)
  - [safe_interpreter_v2.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/research_active/safe_interpreter_v2.py)

## Family overview

### 1. Envelope position
- `band_pos`

This is the direct answer to:

- where is the close inside the recent high-low envelope?

It is the cleanest “upper band vs lower band” indicator in the repository.

### 2. Envelope width / structural expansion
- `band_w`

This is not pure position. It is structural width:

- how wide is the recent price envelope relative to current price?

It belongs in this family because it describes the state of the surrounding structure that gives `band_pos` its meaning.

### 3. Mean-reversion stretch
- `dist_from_mean_vol_units`

This is the cleanest normalized stretch feature in the repository:

- how far is price from its rolling equilibrium, measured in volatility units?

This is more mean-reversion oriented than `band_pos`.

### 4. Time-since-extreme proxies
- `time_since_local_high`
- `time_since_local_low`

These do not say where price is now. They say how recently an important local extreme occurred.

They are weaker and more indirect, but still belong to the position / structure family because they describe location relative to recent path history.

## Observed overlap patterns

Based on current `features.csv`:

- `band_pos` vs `dist_from_mean_vol_units`: strong overlap, about `0.81`
- `band_pos` vs `time_since_local_high`: strong negative overlap, about `-0.68`
- `band_pos` vs `time_since_local_low`: moderate positive overlap, about `0.56`
- `dist_from_mean_vol_units` vs `time_since_local_high`: strong negative overlap, about `-0.70`
- `dist_from_mean_vol_units` vs `time_since_local_low`: moderate positive overlap, about `0.63`
- `band_w` is materially less overlapping with the others

Interpretation:

- `band_pos`, `dist_from_mean_vol_units`, and the time-since-extreme features are all telling related location stories.
- The overlap is partly useful:
  - `band_pos` = envelope location
  - `dist_from_mean_vol_units` = normalized stretch versus equilibrium
  - `time_since_local_high/low` = recency of extreme
- `band_w` stands apart because it describes the surrounding structural container, not just location inside it.

## Per-indicator audit

### `band_pos`
- Measures:
  - close location inside the rolling high-low band.
- Market story:
  - lower band, mid-range, or upper band.
- Overlap:
  - overlaps with `dist_from_mean_vol_units` and time-since-extreme proxies.
- Overlap quality:
  - useful overlap.
  - `band_pos` is the cleanest direct envelope-location feature.
- Assessment:
  - robust and interpretable.
  - likely more useful in interaction than as a standalone predictor.
- Classification:
  - `productive_core`

### `band_w`
- Measures:
  - normalized width of the rolling price band.
- Market story:
  - compression vs expansion.
- Overlap:
  - overlaps partly with volatility features, but here it acts as structural width.
- Overlap quality:
  - useful overlap.
  - it complements `band_pos` by saying whether “upper band” or “lower band” exists inside a tight or wide structure.
- Assessment:
  - especially informative and likely underappreciated.
  - strongest empirical indicator in this family.
- Classification:
  - `productive_core`

### `dist_from_mean_vol_units`
- Measures:
  - distance from rolling mean in volatility units.
- Market story:
  - normalized stretch away from equilibrium.
- Overlap:
  - overlaps strongly with `band_pos`, but the story is different.
- Overlap quality:
  - useful overlap.
  - `band_pos` is envelope-relative
  - `dist_from_mean_vol_units` is equilibrium-relative
- Assessment:
  - best true mean-reversion-style feature in this family.
  - useful for pullback / stretch logic.
- Classification:
  - `productive_context`

### `time_since_local_high`
- Measures:
  - number of days since the latest local high in the lookback window.
- Market story:
  - how recently the market last printed a meaningful local top.
- Overlap:
  - overlaps with `band_pos` and `dist_from_mean_vol_units`.
- Overlap quality:
  - partially useful, but indirect.
- Assessment:
  - interpretable, but weak as a standalone signal.
  - likely more useful inside interaction logic than alone.
- Classification:
  - `research_context`

### `time_since_local_low`
- Measures:
  - number of days since the latest local low in the lookback window.
- Market story:
  - how recently the market last printed a meaningful local bottom.
- Overlap:
  - overlaps with `band_pos` and `dist_from_mean_vol_units`.
- Overlap quality:
  - partially useful, but indirect.
- Assessment:
  - somewhat more intuitive for rebound / basing narratives than `time_since_local_high`
  - still weak as a standalone feature
- Classification:
  - `research_context`

## Story-quality assessment

### Strongest state descriptors
- `band_pos`
- `band_w`
- `dist_from_mean_vol_units`

These are the core interpretable structure-location indicators.

### Best pullback / stretch descriptor
- `dist_from_mean_vol_units`

This is the cleanest “stretched away from equilibrium” feature.

### Best structural-width descriptor
- `band_w`

This is the best feature for distinguishing compression from wide, already-expanded structure.

### Weakest standalone descriptors
- `time_since_local_high`
- `time_since_local_low`

These are still useful as supporting context, but they do not look strong enough to stand alone.

## Initial classification summary

### Productive core
- `band_pos`
- `band_w`

### Productive context
- `dist_from_mean_vol_units`

### Research context
- `time_since_local_high`
- `time_since_local_low`

### Redundant alias
- none in this family

### Suspect or misleading
- none in this family

## Guidance for future walk-forward use

- Use `band_pos` to describe simple lower/mid/upper envelope location.
- Use `band_w` to distinguish compressed setups from already-wide structures.
- Use `dist_from_mean_vol_units` when the question is pullback, stretch, or mean-reversion opportunity.
- Use `time_since_local_high` and `time_since_local_low` only as supporting context unless later tests show stronger interaction value.
