# SAFE v4.0 Participation Interpretive Audit

## Scope
This audit covers the current participation / activity / volume-based indicators:

- `volume_log1p`
- `relative_volume_20`
- `volume_z`

These are the direct “how much market is involved” features in the current SAFE price-feature contract.

This is an interpretive audit, not a pruning pass.

## Repository context

All three indicators are computed in [price_features.py](/home/mihai/Documents/BTC_pulse/statistics/src/features/price_features.py) inside `_compute_volume_features(...)`.

Current direct productive / validation usage:

- `relative_volume_20`
  - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
  - [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py)
  - [hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py)
- `volume_z`
  - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
- `volume_log1p`
  - currently descriptive / feature-store only

Current descriptive / research usage:

- `relative_volume_20` and `volume_z` appear in:
  - [safe_interpreter.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/research_archive/safe_interpreter.py)
  - [safe_interpreter_v2.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/research_active/safe_interpreter_v2.py)
- `volume_log1p` is also available in the feature store, but the research layer mostly reasons with the normalized participation measures instead.

## Family overview

### 1. Raw participation scale
- `volume_log1p`

This is the absolute level of market activity, compressed for heavy tails.

It answers:

- is raw activity high or low in absolute terms?

### 2. Short-horizon relative participation
- `relative_volume_20`

This answers:

- is today’s activity above or below recent normal?

It is a local participation confirmation metric.

### 3. Adaptive unusualness
- `volume_z`

This answers:

- is activity unusual relative to its longer-run history?

It is the most normalized and regime-aware participation feature in this family.

## Observed overlap patterns

Based on current `features.csv`:

- `volume_log1p` vs `volume_z`: strong overlap, about `0.89`
- `relative_volume_20` vs `volume_z`: moderate overlap, about `0.54`
- `volume_log1p` vs `relative_volume_20`: modest overlap, about `0.35`

Interpretation:

- `volume_log1p` and `volume_z` overlap because both are influenced by absolute activity level.
- `relative_volume_20` is more local and multiplicative.
- The overlap is partly useful:
  - `relative_volume_20` says “participation vs recent normal”
  - `volume_z` says “participation vs longer-run adaptive normal”
- `volume_log1p` is the weakest conceptually because raw level is more exposed to secular market-scale drift.

## Per-indicator audit

### `volume_log1p`
- Measures:
  - log-scaled absolute volume.
- Market story:
  - raw activity intensity.
- Overlap:
  - overlaps strongly with `volume_z`.
- Overlap quality:
  - partly useful, partly questionable.
  - useful as a raw scale descriptor
  - questionable as a decision feature because raw volume is structurally nonstationary across long BTC history
- Assessment:
  - interpretable, but less robust than normalized participation measures.
  - likely better as descriptive context than as a productive signal.
- Classification:
  - `research_context`

### `relative_volume_20`
- Measures:
  - current volume divided by its recent 20-day average.
- Market story:
  - local participation confirmation.
- Overlap:
  - overlaps with `volume_z`, but keeps a cleaner and more direct interpretation.
- Overlap quality:
  - useful overlap.
- Assessment:
  - operationally valuable because it directly answers whether the move is happening on above-normal local participation.
  - likely better for confirming trend strength or bounce quality than for predicting on its own.
- Classification:
  - `productive_core`

### `volume_z`
- Measures:
  - adaptive z-score of log-scaled volume.
- Market story:
  - unusual participation intensity relative to longer-run history.
- Overlap:
  - overlaps with `relative_volume_20` and `volume_log1p`, but is the most statistically normalized.
- Overlap quality:
  - useful overlap.
- Assessment:
  - strongest empirical feature in this family.
  - caution: it has fewer usable rows because of the longer adaptive normalization window.
- Classification:
  - `productive_context`

## Story-quality assessment

### Best participation confirmation feature
- `relative_volume_20`

Why:

- clearest operational interpretation
- already used in productive models
- directly expresses whether the current move is locally supported

### Strongest empirical participation signal
- `volume_z`

Why:

- strongest reliability ranking in this family
- best at identifying unusual activity rather than just raw activity level

### Weakest decision-oriented feature
- `volume_log1p`

Why:

- more exposed to long-run market growth and structural shifts
- weaker normalization than the other two

## Initial classification summary

### Productive core
- `relative_volume_20`

### Productive context
- `volume_z`

### Research context
- `volume_log1p`

### Redundant alias
- none in this family

### Suspect or misleading
- none yet, but `volume_log1p` should be challenged because raw activity level may look informative while partly reflecting market maturation rather than actionable participation

## Guidance for future walk-forward use

- Use `relative_volume_20` as the default participation confirmation feature.
- Use `volume_z` when the question is whether participation is statistically unusual, not just above local average.
- Treat `volume_log1p` as descriptive context unless later tests prove it adds distinct walk-forward value beyond the normalized participation measures.
- Participation likely adds value mainly in interaction with:
  - trend quality
  - rebound attempts
  - noisy vs clean continuation logic
