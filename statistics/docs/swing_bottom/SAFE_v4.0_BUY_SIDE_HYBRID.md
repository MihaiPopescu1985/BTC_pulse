# SAFE v4.0 Buy-Side Narrow Hybrid Pass

## Purpose

- narrow follow-up pass using only the fixed baseline, redesigned exhaustion, and ordinal ranking scores
- no new indicator families, trade rules, execution logic, capital management, or backtesting are introduced
- objective: decide whether a simple hybrid materially improves buy-side swing-low timing

## Inputs And Split

- source surface: direct rebuild from `out/swing_bottom/reversal_zone_dataset.csv` via retained signal-owned helpers
- test down swings evaluated: `45`
- test date range: `2024-12-22` to `2026-04-09`

## References

- `baseline_fixed_weight`: current fixed phase/analog/exhaustion reference
- `approach_b_exhaustion_redesign`: best local best-pick selector from sprint
- `approach_c_ordinal_ranking`: best global top-decile ranker from sprint

## Hybrid Candidates

- `hybrid_weighted_balanced`: `0.40 fixed + 0.30 exhaustion + 0.30 ordinal`
- `hybrid_rank_local_weighted`: `0.25 fixed + 0.35 exhaustion + 0.40 ordinal`
- `hybrid_learned_three_score`: logistic combiner trained on train+validation using only the three reference scores
- learned-combiner coefficients: `buy_fixed_extreme_timing_score` `0.627`, `buy_exhaustion_redesign_score` `-0.017`, `buy_ordinal_ranking_score` `1.386`
- `hybrid_two_stage_shortlist_rerank`: ordinal shortlists the top 40% of rows inside each test down swing, then exhaustion picks the local best row
- two-stage shortlist/rerank is a swing-level diagnostic; the exported date-aligned two-stage score is still causal and does not use confirmed swing membership

## Primary Swing-Level Best-Pick Results

- `baseline_fixed_weight`: avg / median distance `0.047` / `0.026`, within 5% / 3% `0.733` / `0.578`
- `approach_b_exhaustion_redesign`: avg / median distance `0.040` / `0.025`, within 5% / 3% `0.778` / `0.667`
- `approach_c_ordinal_ranking`: avg / median distance `0.041` / `0.029`, within 5% / 3% `0.756` / `0.556`
- `hybrid_weighted_balanced`: avg / median distance `0.035` / `0.025`, within 5% / 3% `0.822` / `0.667`
- `hybrid_rank_local_weighted`: avg / median distance `0.035` / `0.025`, within 5% / 3% `0.822` / `0.667`
- `hybrid_learned_three_score`: avg / median distance `0.047` / `0.028`, within 5% / 3% `0.778` / `0.578`
- `hybrid_two_stage_shortlist_rerank`: avg / median distance `0.039` / `0.024`, within 5% / 3% `0.800` / `0.711`

## Ranking By Average Best-Picked Distance

- `hybrid_weighted_balanced`: avg best distance `0.035`
- `hybrid_rank_local_weighted`: avg best distance `0.035`
- `hybrid_two_stage_shortlist_rerank`: avg best distance `0.039`
- `approach_b_exhaustion_redesign`: avg best distance `0.040`
- `approach_c_ordinal_ranking`: avg best distance `0.041`
- `hybrid_learned_three_score`: avg best distance `0.047`
- `baseline_fixed_weight`: avg best distance `0.047`

## Top-Decile Quality

- `baseline_fixed_weight`: hit 5% / 3% `0.562` / `0.438`, avg distance `0.051`, swings touched `26`
- `approach_b_exhaustion_redesign`: hit 5% / 3% `0.229` / `0.167`, avg distance `0.114`, swings touched `13`
- `approach_c_ordinal_ranking`: hit 5% / 3% `0.646` / `0.438`, avg distance `0.054`, swings touched `26`
- `hybrid_weighted_balanced`: hit 5% / 3% `0.667` / `0.500`, avg distance `0.042`, swings touched `25`
- `hybrid_rank_local_weighted`: hit 5% / 3% `0.625` / `0.458`, avg distance `0.044`, swings touched `25`
- `hybrid_learned_three_score`: hit 5% / 3% `0.646` / `0.458`, avg distance `0.046`, swings touched `28`
- `hybrid_two_stage_shortlist_rerank`: hit 5% / 3% `0.625` / `0.479`, avg distance `0.051`, swings touched `25`

## Decision

- recommendation: **Continue**
- Best hybrid by average best-picked distance: `hybrid_weighted_balanced`.
- Fixed baseline avg best distance `0.047` vs candidate `0.035`; 5% hit `0.733` vs `0.822`, 3% hit `0.578` vs `0.667`.
- Hybrid materially improves best-pick proximity without giving back top-decile quality.

## Interpretation

- the hybrid result directly tests whether buy-side timing needs both global ranking and local bottom refinement
- a useful hybrid must beat the fixed baseline on best-pick proximity without giving back top-decile quality
- if this pass failed, the current buy-side framing would be near a practical dead end; if it succeeds, the next step should be validation rather than another broad idea sprint
