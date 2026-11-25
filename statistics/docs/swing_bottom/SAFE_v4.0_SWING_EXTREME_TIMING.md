# SAFE v4.0 Swing Extreme Timing

## Purpose

- this layer combines a causal phase model, strictly historical analogs, and a deterministic exhaustion score
- the goal is to estimate how near price is to a usable swing low or swing high, not to predict exact pivots

## Inputs Used

- source dataset: `out/swing_bottom/reversal_zone_dataset.csv`
- feature families: retained causal price, volatility, participation, regime/hazard, on-chain, and live swing-state fields
- retained phase-model feature count: `90`

## Phase Component

- model: class-balanced logistic regression reused from the corrected reversal-zone baseline
- leakage exclusions match the corrected baseline; no future-derived columns enter the phase input matrix
- outputs: `buy_phase_prob`, `sell_phase_prob`

## Analog Component

- recent candle window: `5` bars
- similarity method: cosine similarity on normalized candle-shape and compact causal state vectors
- prior analog count: top `40` only
- forward analog horizon: `5` days
- refinement pass: analog aggregation is similarity-weighted instead of equal-weighted
- refinement pass: buy analogs are restricted to prior down-swing context and sell analogs to prior up-swing context
- outputs: analog probability of reaching the 5% and 3% zone soon, median days, and match count

## Exhaustion Component

- deterministic bounded score in `[0,1]`
- buy exhaustion combines: down-direction bias, swing age, swing size, downside stretch, volatility cooling, and correction/rebound regime pressure
- sell exhaustion combines: up-direction bias, swing age, swing size, upside stretch, volatility cooling, and correction/surge regime pressure

## Combined Score

- fixed-weight reference formula: `0.45 * phase_prob + 0.30 * analog_prob + 0.25 * exhaustion_score`
- corrected combined score: class-balanced logistic regression trained on train+validation rows only
- learned-combiner inputs: phase probability, analog probability, exhaustion score
- higher learned score means stronger evidence that price is near a usable swing extreme

## Learned Combiner Coefficients

- `buy_full`: `buy_phase_prob` `1.789`, `buy_analog_prob` `0.067`, `buy_exhaustion_score` `0.026`
- `sell_full`: `sell_phase_prob` `1.207`, `sell_analog_prob` `0.280`, `sell_exhaustion_score` `0.113`

## Evaluation Summary

- buy unconditional 5% zone prevalence on test: `0.289`
- buy learned-full top 10% zone 5% / 3% hit rate: `0.471` / `0.314`
- buy fixed-weight top 10% zone 5% / 3% hit rate: `0.490` / `0.353`
- buy phase-only top 10% zone 5% / 3% hit rate: `0.431` / `0.275`
- sell unconditional 5% zone prevalence on test: `0.299`
- sell learned-full top 10% zone 5% / 3% hit rate: `0.765` / `0.608`
- sell fixed-weight top 10% zone 5% / 3% hit rate: `0.725` / `0.529`
- sell phase-only top 10% zone 5% / 3% hit rate: `0.686` / `0.510`

## Swing-Level Summary

- buy test down swings: `47`
- buy learned-full best-row avg / median distance: `0.045` / `0.023`
- buy learned-full best-row within 5% / 3%: `0.787` / `0.638`
- buy fixed-weight best-row within 5% / 3%: `0.830` / `0.681`
- sell test up swings: `48`
- sell learned-full best-row avg / median distance: `0.030` / `0.017`
- sell learned-full best-row within 5% / 3%: `0.875` / `0.792`
- sell fixed-weight best-row within 5% / 3%: `0.958` / `0.854`

## Coverage Thresholds

- buy `learned_full` threshold `0.70`: coverage `0.872`, within 5% / 3% `0.518` / `0.362`, avg distance `0.112`, rows `141`
- buy `learned_full` threshold `0.80`: coverage `0.787`, within 5% / 3% `0.514` / `0.360`, avg distance `0.109`, rows `111`
- sell `learned_full` threshold `0.70`: coverage `1.000`, within 5% / 3% `0.642` / `0.463`, avg distance `0.047`, rows `190`
- sell `learned_full` threshold `0.80`: coverage `0.979`, within 5% / 3% `0.678` / `0.514`, avg distance `0.043`, rows `146`

## Ablation Readout

- buy phase+analog best-row within 5% / 3%: `0.787` / `0.638`
- buy phase+exhaustion best-row within 5% / 3%: `0.787` / `0.660`
- sell phase+analog best-row within 5% / 3%: `0.833` / `0.729`
- sell phase+exhaustion best-row within 5% / 3%: `0.854` / `0.750`

## Interpretation

- this refinement is judged primarily by swing-level best-pick quality and threshold coverage, not generic row classification
- the learned combiner improves materially over phase-only on sell-side ranking, but it does not yet dominate the fixed-weight reference on best-pick quality
- fixed-weight score remains exported because it is still a strong robustness comparator and currently remains competitive, especially on buy-side proximity
- buy-side analog contribution is weak in the learned combiner; sell-side analog and exhaustion contributions are directionally useful
- analog probabilities now test whether direction-restricted historical memory adds useful ranking information beyond phase and exhaustion
- no trade logic, capital management, or backtest is introduced here
