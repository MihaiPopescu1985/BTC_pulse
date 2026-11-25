# SAFE v4.0 Buy-Side Narrow Hybrid Pass

## Purpose

- narrow follow-up pass using only the fixed baseline, redesigned exhaustion, and ordinal ranking scores
- no new indicator families, trade rules, execution logic, capital management, or backtesting are introduced
- objective: decide whether a simple hybrid materially improves buy-side swing-low timing

## Inputs And Split

- source surface: direct rebuild from `out/swing_bottom/reversal_zone_dataset.csv` via retained signal-owned helpers
- test down swings evaluated: `47`
- test date range: `2025-07-05` to `2026-11-25`

## References

- `baseline_fixed_weight`: current fixed phase/analog/exhaustion reference
- `approach_b_exhaustion_redesign`: best local best-pick selector from sprint
- `approach_c_ordinal_ranking`: best global top-decile ranker from sprint

## Hybrid Candidates

- `hybrid_weighted_balanced`: `0.40 fixed + 0.30 exhaustion + 0.30 ordinal`
- `hybrid_rank_local_weighted`: `0.25 fixed + 0.35 exhaustion + 0.40 ordinal`
- `hybrid_learned_three_score`: logistic combiner trained on train+validation using only the three reference scores
- learned-combiner coefficients: `buy_fixed_extreme_timing_score` `0.618`, `buy_exhaustion_redesign_score` `-0.004`, `buy_ordinal_ranking_score` `1.356`
- `hybrid_two_stage_shortlist_rerank`: ordinal shortlists the top 40% of rows inside each test down swing, then exhaustion picks the local best row
- two-stage shortlist/rerank is a swing-level diagnostic; the exported date-aligned two-stage score is still causal and does not use confirmed swing membership

## Primary Swing-Level Best-Pick Results

- `baseline_fixed_weight`: avg / median distance `0.042` / `0.022`, within 5% / 3% `0.830` / `0.681`
- `approach_b_exhaustion_redesign`: avg / median distance `0.033` / `0.019`, within 5% / 3% `0.872` / `0.787`
- `approach_c_ordinal_ranking`: avg / median distance `0.040` / `0.022`, within 5% / 3% `0.851` / `0.681`
- `hybrid_weighted_balanced`: avg / median distance `0.035` / `0.017`, within 5% / 3% `0.872` / `0.787`
- `hybrid_rank_local_weighted`: avg / median distance `0.035` / `0.017`, within 5% / 3% `0.872` / `0.787`
- `hybrid_learned_three_score`: avg / median distance `0.043` / `0.022`, within 5% / 3% `0.830` / `0.660`
- `hybrid_two_stage_shortlist_rerank`: avg / median distance `0.036` / `0.017`, within 5% / 3% `0.851` / `0.745`

## Ranking By Average Best-Picked Distance

- `approach_b_exhaustion_redesign`: avg best distance `0.033`
- `hybrid_rank_local_weighted`: avg best distance `0.035`
- `hybrid_weighted_balanced`: avg best distance `0.035`
- `hybrid_two_stage_shortlist_rerank`: avg best distance `0.036`
- `approach_c_ordinal_ranking`: avg best distance `0.040`
- `baseline_fixed_weight`: avg best distance `0.042`
- `hybrid_learned_three_score`: avg best distance `0.043`

## Top-Decile Quality

- `baseline_fixed_weight`: hit 5% / 3% `0.490` / `0.353`, avg distance `0.094`, swings touched `22`
- `approach_b_exhaustion_redesign`: hit 5% / 3% `0.235` / `0.098`, avg distance `0.160`, swings touched `9`
- `approach_c_ordinal_ranking`: hit 5% / 3% `0.529` / `0.333`, avg distance `0.074`, swings touched `23`
- `hybrid_weighted_balanced`: hit 5% / 3% `0.412` / `0.255`, avg distance `0.096`, swings touched `17`
- `hybrid_rank_local_weighted`: hit 5% / 3% `0.412` / `0.255`, avg distance `0.103`, swings touched `16`
- `hybrid_learned_three_score`: hit 5% / 3% `0.529` / `0.333`, avg distance `0.067`, swings touched `21`
- `hybrid_two_stage_shortlist_rerank`: hit 5% / 3% `0.431` / `0.235`, avg distance `0.101`, swings touched `17`

## Decision

- recommendation: **Continue cautiously**
- Best hybrid by average best-picked distance: `hybrid_rank_local_weighted`.
- Fixed baseline avg best distance `0.042` vs candidate `0.035`; 5% hit `0.830` vs `0.872`, 3% hit `0.681` vs `0.787`.
- Hybrid improves one core dimension, but the gain is not dominant across all reference checks.

## Interpretation

- the hybrid result directly tests whether buy-side timing needs both global ranking and local bottom refinement
- a useful hybrid must beat the fixed baseline on best-pick proximity without giving back top-decile quality
- if this pass failed, the current buy-side framing would be near a practical dead end; if it succeeds, the next step should be validation rather than another broad idea sprint
