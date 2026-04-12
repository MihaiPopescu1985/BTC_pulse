# SAFE v4.0 Buy-Side Exploration Sprint

## Purpose

- bounded sprint focused only on buy-side swing-low timing
- no trade rules, execution logic, capital management, or backtest logic are introduced
- all approaches are compared on the same chronological held-out test split

## Inputs And Split

- source dataset: `out/swing_bottom/reversal_zone_dataset.csv`
- retained phase-model causal feature count: `90`
- test down swings evaluated: `45`
- test date range: `2024-12-22` to `2026-04-09`

## Approaches Tested

- `baseline_phase_only`: corrected buy-zone phase model probability
- `baseline_fixed_weight`: current fixed phase/analog/exhaustion reference
- `baseline_learned_combiner`: current learned buy combiner
- `approach_a_analog_overhaul`: 7-candle, 50-neighbor, direction-restricted, similarity-weighted, multi-horizon analog memory
- `approach_b_exhaustion_redesign`: deterministic late-down-swing washout, rejection, stretch, regime, and on-chain accumulation score
- `approach_c_ordinal_ranking`: simple 0/1/2 logistic ranking proxy for rest / 5% zone / 3% zone
- `approach_d_candle_pattern_memory`: outside-the-box candle-geometry-only historical memory
- `approach_e_consensus_phase_any`: phase support multiplied by best agreement from analog, exhaustion, or candle memory

## Primary Swing-Level Best-Pick Results

- `baseline_phase_only`: avg / median distance `0.049` / `0.028`, within 5% / 3% `0.733` / `0.556`
- `baseline_fixed_weight`: avg / median distance `0.047` / `0.026`, within 5% / 3% `0.733` / `0.578`
- `baseline_learned_combiner`: avg / median distance `0.049` / `0.028`, within 5% / 3% `0.733` / `0.556`
- `approach_a_analog_overhaul`: avg / median distance `0.059` / `0.036`, within 5% / 3% `0.600` / `0.422`
- `approach_b_exhaustion_redesign`: avg / median distance `0.040` / `0.025`, within 5% / 3% `0.778` / `0.667`
- `approach_c_ordinal_ranking`: avg / median distance `0.041` / `0.029`, within 5% / 3% `0.756` / `0.556`
- `approach_d_candle_pattern_memory`: avg / median distance `0.050` / `0.029`, within 5% / 3% `0.622` / `0.511`
- `approach_e_consensus_phase_any`: avg / median distance `0.044` / `0.029`, within 5% / 3% `0.733` / `0.578`

## Ranking By Average Best-Picked Distance

- `approach_b_exhaustion_redesign`: avg best distance `0.040`
- `approach_c_ordinal_ranking`: avg best distance `0.041`
- `approach_e_consensus_phase_any`: avg best distance `0.044`
- `baseline_fixed_weight`: avg best distance `0.047`
- `baseline_phase_only`: avg best distance `0.049`
- `baseline_learned_combiner`: avg best distance `0.049`
- `approach_d_candle_pattern_memory`: avg best distance `0.050`
- `approach_a_analog_overhaul`: avg best distance `0.059`

## Top-Decile Quality

- `baseline_phase_only`: hit 5% / 3% `0.438` / `0.292`, avg distance `0.070`, swings touched `24`
- `baseline_fixed_weight`: hit 5% / 3% `0.562` / `0.438`, avg distance `0.051`, swings touched `26`
- `baseline_learned_combiner`: hit 5% / 3% `0.458` / `0.312`, avg distance `0.071`, swings touched `23`
- `approach_a_analog_overhaul`: hit 5% / 3% `0.396` / `0.271`, avg distance `0.052`, swings touched `24`
- `approach_b_exhaustion_redesign`: hit 5% / 3% `0.229` / `0.167`, avg distance `0.114`, swings touched `13`
- `approach_c_ordinal_ranking`: hit 5% / 3% `0.646` / `0.438`, avg distance `0.054`, swings touched `26`
- `approach_d_candle_pattern_memory`: hit 5% / 3% `0.479` / `0.396`, avg distance `0.047`, swings touched `25`
- `approach_e_consensus_phase_any`: hit 5% / 3% `0.458` / `0.333`, avg distance `0.066`, swings touched `25`

## Decision

- recommendation: **Continue cautiously**
- Best non-baseline by average distance: `approach_b_exhaustion_redesign` distance `0.040` vs fixed baseline `0.047`.
- Zone hit changes vs fixed baseline: 5% `+0.044`, 3% `+0.089`.
- Top-decile 5% hit rate for `approach_b_exhaustion_redesign` is `0.229` vs fixed baseline `0.562`.
- Top-decile average distance for `approach_b_exhaustion_redesign` is `0.114` vs fixed baseline `0.051`.

## Interpretation

- the fixed-weight baseline remains the buy-side reference unless a new approach improves proximity without materially weakening 5% / 3% hit rates
- if the best experimental approach improves only one dimension, the next pass should be tightly scoped rather than open-ended
- if no approach beats the fixed-weight baseline, the current buy-side framing is likely near diminishing returns with the present feature surface
