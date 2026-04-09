# SAFE v4.0 Volatility Interpretive Audit

## Scope
This audit covers the current volatility-family indicators:

- `vol_20`
- `atr_pct`
- `parkinson_vol`
- `garman_klass_vol`
- `ewma_vol`
- `upside_semi_vol`
- `downside_semi_vol`

This is an interpretive audit, not a pruning pass. The purpose is to clarify what each volatility indicator is saying, where overlap is useful, where overlap is empty, and which indicators look strongest for later walk-forward refinement.

## Repository context

All seven indicators are computed in [price_features.py](/home/mihai/Documents/BTC_pulse/statistics/src/features/price_features.py) inside `_compute_volatility_features(...)`.

Current direct productive / validation usage:

- `atr_pct`
  - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
  - [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py)
  - [hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py)
- `vol_20`
  - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
  - [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py) as part of state signatures / diagnostics
- `ewma_vol`
  - [hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py)
  - [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py) state signature diagnostics

Current descriptive / research usage:

- all seven remain available in the retained research feature surface

## Family overview

### 1. Close-to-close volatility backbone
- `vol_20`
- `ewma_vol`

These describe volatility from daily returns only.

- `vol_20`: stable rolling volatility baseline
- `ewma_vol`: faster, recency-weighted volatility reaction

### 2. Range-based / bar-based volatility
- `atr_pct`
- `parkinson_vol`
- `garman_klass_vol`

These use more of the daily bar geometry than close-to-close returns.

- `atr_pct`: practical daily movement scale, including gap sensitivity through true range
- `parkinson_vol`: high-low range intensity, efficient but gap-insensitive
- `garman_klass_vol`: fuller OHLC estimator, intended to be richer than Parkinson

### 3. Directional volatility asymmetry
- `upside_semi_vol`
- `downside_semi_vol`

These separate positive-path volatility from negative-path volatility.

They are not just “how much volatility.” They say which side of the tape has been carrying more of the movement.

## Observed overlap patterns

Based on current `features.csv`:

- `parkinson_vol` vs `garman_klass_vol`: extremely high overlap, around `0.995`
- `vol_20` vs `ewma_vol`: very high overlap, around `0.949`
- `vol_20` vs `parkinson_vol`: very high overlap, around `0.948`
- `atr_pct` vs `parkinson_vol`: very high overlap, around `0.942`
- `atr_pct` vs `garman_klass_vol`: very high overlap, around `0.941`
- `upside_semi_vol` vs `downside_semi_vol`: much lower overlap, around `0.43`

Interpretation:

- Most of the family is detecting the same broad volatility regime, but not in exactly the same language.
- The overlap is useful when the indicators differ conceptually:
  - close-to-close volatility
  - range volatility
  - gap-aware practical movement
  - directional volatility asymmetry
- The most suspicious overlap is `parkinson_vol` vs `garman_klass_vol`, because the empirical distinction is tiny relative to the apparent conceptual distinction.

## Per-indicator audit

### `vol_20`
- Measures:
  - rolling 20-day close-to-close realized volatility.
- Market story:
  - baseline volatility regime from daily returns.
- Overlap:
  - strong overlap with `ewma_vol`, `atr_pct`, `parkinson_vol`, `garman_klass_vol`.
- Overlap quality:
  - useful. This is the simplest anchor against which the others can be compared.
- Assessment:
  - robust, interpretable, and a good baseline volatility state variable.
- Classification:
  - `productive_core`

### `atr_pct`
- Measures:
  - average true range scaled by close.
- Market story:
  - practical daily movement size, with gap sensitivity.
- Overlap:
  - overlaps strongly with every broad volatility measure.
- Overlap quality:
  - useful. It is more execution-relevant than pure close-to-close volatility.
- Assessment:
  - especially informative for downside-risk context and daily movement scale.
- Classification:
  - `productive_core`

### `parkinson_vol`
- Measures:
  - high-low volatility estimator.
- Market story:
  - intraday range intensity.
- Overlap:
  - extremely high overlap with `garman_klass_vol`; strong overlap with `vol_20` and `atr_pct`.
- Overlap quality:
  - partly useful, partly questionable.
  - useful as a range-only comparator to `vol_20`
  - questionable relative to `garman_klass_vol`, because the two behave almost identically in the current data
- Assessment:
  - informative, but likely not needed as a distinct front-line signal unless its specific range-only interpretation proves useful later.
- Classification:
  - `research_context`

### `garman_klass_vol`
- Measures:
  - OHLC volatility estimator.
- Market story:
  - fuller bar-based volatility than Parkinson.
- Overlap:
  - near-duplicate empirical behavior relative to `parkinson_vol`.
- Overlap quality:
  - mostly empty relative to `parkinson_vol` in the current data.
- Assessment:
  - theoretically distinct, empirically very hard to distinguish.
  - deserves to be challenged later, not immediately removed.
- Classification:
  - `research_context`

### `ewma_vol`
- Measures:
  - recency-weighted close-to-close volatility.
- Market story:
  - fast volatility regime shift detector.
- Overlap:
  - strong overlap with `vol_20`, but the intended story is different.
- Overlap quality:
  - useful overlap.
  - `vol_20` says “what regime has prevailed”
  - `ewma_vol` says “how fast recent stress is changing”
- Assessment:
  - strong candidate for productive use because it reacts faster and shows good empirical relation to future excursion / touch outcomes.
- Classification:
  - `productive_core`

### `upside_semi_vol`
- Measures:
  - volatility of positive returns only.
- Market story:
  - upside participation intensity and positive-path movement variability.
- Overlap:
  - overlaps with broad volatility, but with a directional twist.
- Overlap quality:
  - useful overlap.
  - this is not just “more volatility”; it can help distinguish upside expansion from generalized stress.
- Assessment:
  - especially promising for upside opportunity context.
- Classification:
  - `productive_context`

### `downside_semi_vol`
- Measures:
  - volatility of negative returns only.
- Market story:
  - downside stress intensity.
- Overlap:
  - overlaps with broad volatility, but carries clearly different directional meaning from `upside_semi_vol`.
- Overlap quality:
  - useful overlap.
- Assessment:
  - not the strongest standalone downside indicator, but conceptually valuable and likely more useful in interaction with other families than alone.
- Classification:
  - `productive_context`

## Story-quality assessment

### Strongest broad volatility story-tellers
- `atr_pct`
- `vol_20`
- `ewma_vol`

These are the most defensible broad descriptors of volatility state:

- `vol_20`: stable baseline
- `ewma_vol`: fast regime shift
- `atr_pct`: practical movement scale

### Best directional context features
- `upside_semi_vol`
- `downside_semi_vol`

These are the most promising “use volatility more intelligently” features for future walk-forward refinement.

### Most questionable overlap pair
- `parkinson_vol`
- `garman_klass_vol`

This pair does not look empty in theory, but it does look close to empty in current empirical behavior.

## Initial classification summary

### Productive core
- `vol_20`
- `atr_pct`
- `ewma_vol`

### Productive context
- `upside_semi_vol`
- `downside_semi_vol`

### Research context
- `parkinson_vol`
- `garman_klass_vol`

### Redundant alias
- none in this family at current evidence threshold

### Suspect or misleading
- none yet, but `garman_klass_vol` should be challenged if it continues to behave as near-duplicate range volatility

## Guidance for future walk-forward use

- Use `vol_20` as the stable volatility backdrop.
- Use `ewma_vol` to detect recent volatility acceleration and signal decay risk.
- Use `atr_pct` when the question is practical move size or downside excursion risk.
- Use `upside_semi_vol` and `downside_semi_vol` to condition opportunity:
  - upside semi-vol can help distinguish upside expansion from pure stress
  - downside semi-vol can help distinguish bad volatility from tradable volatility
- Treat `parkinson_vol` and `garman_klass_vol` mainly as audit comparators unless later tests prove that one adds unique value in interaction with other families.
