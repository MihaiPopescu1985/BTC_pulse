# SAFE v4.0 Regime / Hazard Interpretive Audit

## Scope
This audit covers the active regime / hazard family:

- `P_CORE_HMM`
- `P_DRIFT_HMM`
- `P_SHOCK_HMM`
- `P_SURGE_HMM`
- `HMM_CONF`
- `HMM_DOM`
- `P_CORRECTION_10D_CAL`
- `P_REBOUND_10D_CAL`

This family is different from trend, volatility, position, and participation because these indicators are model-derived.

They are not raw market descriptors. They are outputs of upstream modeling stages.

That means this pass must separate:

- decision-useful state context
- calibrated ranking context
- diagnostics / internals that should not be treated as independent raw evidence

## Repository context

### HMM outputs
Produced by [regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py) and exported via [run_regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_regime_hmm.py).

Key meanings:

- `P_CORE_HMM`, `P_DRIFT_HMM`, `P_SHOCK_HMM`, `P_SURGE_HMM`
  - semantic regime probabilities
- `HMM_LABEL`
  - semantic label with highest probability
- `HMM_CONF`
  - confidence in the dominant latent-state assignment
- `HMM_DOM`
  - dominant latent state index

### Hazard outputs
Produced by [hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py) and exported via [run_hazard_train.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_hazard_train.py).

Key meanings:

- `P_CORRECTION_10D_CAL`
  - calibrated probability-like score for a correction event over the horizon
- `P_REBOUND_10D_CAL`
  - calibrated probability-like score for a rebound event over the horizon

### Current productive / validation usage

- `P_SHOCK_HMM`
  - used directly in:
    - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
    - [run_decision_analysis_walkforward.py](/home/mihai/Documents/BTC_pulse/statistics/src/walkforward/run_decision_analysis_walkforward.py)
    - [exposure.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/exposure.py)
- `P_CORRECTION_10D_CAL`
  - used directly in:
    - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
    - [run_decision_analysis_walkforward.py](/home/mihai/Documents/BTC_pulse/statistics/src/walkforward/run_decision_analysis_walkforward.py)
    - [exposure.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/exposure.py)
- `P_REBOUND_10D_CAL`
  - used directly in:
    - [run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
    - [run_decision_analysis_walkforward.py](/home/mihai/Documents/BTC_pulse/statistics/src/walkforward/run_decision_analysis_walkforward.py)
    - [exposure.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/exposure.py)
- `HMM_CONF`
  - used in [exposure.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/exposure.py) as a confidence modulation term
- `HMM_DOM`
  - mainly exported and carried through; not part of accepted walk-forward scoring

## Family overview

### 1. Semantic regime probabilities
- `P_CORE_HMM`
- `P_DRIFT_HMM`
- `P_SHOCK_HMM`
- `P_SURGE_HMM`

These are a probability simplex over the semantic HMM regimes.

Expected property:

- they must overlap strongly because they are mutually constrained
- this overlap is structural, not automatically a defect

### 2. Regime diagnostics
- `HMM_CONF`
- `HMM_DOM`

These are not independent regime forecasts.

- `HMM_CONF` says how concentrated the latent-state posterior is
- `HMM_DOM` says which latent state index is dominant

### 3. Calibrated hazard scores
- `P_CORRECTION_10D_CAL`
- `P_REBOUND_10D_CAL`

These are already closer to decision-layer ranking features than the raw HMM internals.

Important caution:

- they are still model outputs, not raw evidence
- they should not be treated as if they were independent of the upstream price-feature surface

## Per-indicator audit

### `P_CORE_HMM`
- Represents:
  - probability that the semantic regime is `CORE`, the neutral / central state.
- Market story:
  - calm, non-extreme, non-trending center-of-distribution conditions.
- Overlap:
  - naturally overlaps inversely with the other semantic regime probabilities.
- Overlap quality:
  - expected and useful, not empty.
- Decision usefulness:
  - useful as market-state context
  - not a fresh upstream signal
- Circularity risk:
  - moderate, because it is already a compressed model output from raw features
- Classification:
  - `productive_context`

### `P_DRIFT_HMM`
- Represents:
  - probability of the orderly positive drift regime.
- Market story:
  - favorable but not explosive directional environment.
- Overlap:
  - overlaps with `P_SURGE_HMM` on the positive side and with `P_CORE_HMM` when conditions are calm.
- Overlap quality:
  - expected, but in practice its distinct usefulness appears weaker than `P_SHOCK_HMM` or `P_SURGE_HMM`.
- Decision usefulness:
  - plausible context feature, but weaker than the other semantic probabilities.
- Circularity risk:
  - moderate.
- Classification:
  - `research_context`

### `P_SHOCK_HMM`
- Represents:
  - probability of the semantic shock / stress regime.
- Market story:
  - stressed market state, elevated downside danger, unstable continuation conditions.
- Overlap:
  - overlaps inversely with positive regime probabilities, as expected.
- Overlap quality:
  - useful.
- Decision usefulness:
  - strong risk context feature
  - one of the most directly actionable regime outputs
- Circularity risk:
  - present, but acceptable because this is exactly a compressed state estimate the decision layer is meant to use
- Classification:
  - `productive_core`

### `P_SURGE_HMM`
- Represents:
  - probability of the strong positive expansion regime.
- Market story:
  - powerful upside expansion state.
- Overlap:
  - overlaps with `P_DRIFT_HMM` on the positive side, but tends to represent stronger conditions.
- Overlap quality:
  - useful.
- Decision usefulness:
  - plausible upside opportunity context
  - more tradable than `P_DRIFT_HMM` in current evidence
- Circularity risk:
  - moderate.
- Classification:
  - `productive_context`

### `HMM_CONF`
- Represents:
  - concentration of the dominant latent-state posterior.
- Market story:
  - how confident the HMM is in its current state assignment.
- Overlap:
  - overlaps with regime probabilities indirectly, but not in a simple directional way.
- Overlap quality:
  - useful when used as trust / confidence modulation
  - weak when treated as a directional feature
- Decision usefulness:
  - useful as confidence context
  - not a direct directional market-state forecast
- Circularity risk:
  - low to moderate, but it is clearly a meta-property of the HMM output
- Classification:
  - `productive_context`

### `HMM_DOM`
- Represents:
  - dominant latent state index.
- Market story:
  - latent-state identity before semantic interpretation.
- Overlap:
  - overlaps with `HMM_LABEL`, semantic probabilities, and pack-specific latent numbering.
- Overlap quality:
  - mostly empty for decision use.
- Decision usefulness:
  - weak.
  - much better treated as diagnostic output than as decision evidence.
- Circularity risk:
  - high, because latent numbering is pack-specific and not intrinsically interpretable market meaning.
- Classification:
  - `diagnostic_only`

### `P_CORRECTION_10D_CAL`
- Represents:
  - calibrated probability-like downside hazard output.
- Market story:
  - ranked short-horizon downside risk.
- Overlap:
  - overlaps with `P_SHOCK_HMM` and with its positive-side companion `P_REBOUND_10D_CAL`.
- Overlap quality:
  - useful, expected overlap.
- Decision usefulness:
  - strong.
  - current SAFE already uses it as a ranking feature rather than as a literal probability.
- Circularity risk:
  - real, because it is downstream of the descriptive feature set
  - but acceptable when treated as a decision-layer score, not as raw evidence
- Classification:
  - `productive_core`

### `P_REBOUND_10D_CAL`
- Represents:
  - calibrated probability-like upside hazard output.
- Market story:
  - ranked rebound / upside opportunity over the hazard horizon.
- Overlap:
  - overlaps with `P_CORRECTION_10D_CAL` as the opposite-side hazard companion.
- Overlap quality:
  - useful.
- Decision usefulness:
  - strong.
  - current SAFE uses it directly in ranking logic.
- Circularity risk:
  - real, but acceptable at the decision-layer level if not treated as independent upstream evidence.
- Classification:
  - `productive_core`

## Story-quality assessment

### Strongest decision-layer context features
- `P_CORRECTION_10D_CAL`
- `P_REBOUND_10D_CAL`
- `P_SHOCK_HMM`

These are the most directly useful regime / hazard quantities for actual decision ranking.

### Useful but secondary context
- `P_CORE_HMM`
- `P_SURGE_HMM`
- `HMM_CONF`

These help describe state quality, confidence, and upside regime character.

### Weakest decision-useful field
- `P_DRIFT_HMM`

Not because it is meaningless, but because its distinct edge looks weaker than the shock, surge, and hazard outputs.

### Diagnostic-only field
- `HMM_DOM`

Useful for pack diagnostics and internal inspection, not for front-line decision logic.

## Initial classification summary

### Productive core
- `P_SHOCK_HMM`
- `P_CORRECTION_10D_CAL`
- `P_REBOUND_10D_CAL`

### Productive context
- `P_CORE_HMM`
- `P_SURGE_HMM`
- `HMM_CONF`

### Research context
- `P_DRIFT_HMM`

### Diagnostic only
- `HMM_DOM`

### Redundant alias
- none in this family

### Suspect or misleading
- none yet, but `HMM_DOM` should not be mistaken for stable semantic evidence

## Circularity and double-counting caution

This family is the main place where double-counting risk appears naturally.

Examples:

- using raw trend / volatility / structure features
- and then separately treating regime / hazard outputs as if they were independent evidence

That would overstate signal diversity.

Correct use:

- regime / hazard outputs belong in the decision layer as compressed model context
- they should not be counted as fresh independent upstream evidence in later merged feature reasoning

## Guidance for future walk-forward use

- Keep `P_CORRECTION_10D_CAL` and `P_REBOUND_10D_CAL` as explicit ranking signals.
- Keep `P_SHOCK_HMM` as explicit stress / danger context.
- Use `P_CORE_HMM` and `P_SURGE_HMM` as regime flavor context, not as primary stand-alone triggers.
- Use `HMM_CONF` only as confidence modulation, not as a directional signal.
- Treat `HMM_DOM` as diagnostic only unless a future pass proves a stable semantic use case.
