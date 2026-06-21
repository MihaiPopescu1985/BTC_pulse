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

- `buy_full`: `buy_phase_prob` `1.880`, `buy_analog_prob` `-0.046`, `buy_exhaustion_score` `0.002`
- `sell_full`: `sell_phase_prob` `1.151`, `sell_analog_prob` `0.271`, `sell_exhaustion_score` `0.132`

## Evaluation Summary

- buy unconditional 5% zone prevalence on test: `0.247`
- buy learned-full top 10% zone 5% / 3% hit rate: `0.458` / `0.312`
- buy fixed-weight top 10% zone 5% / 3% hit rate: `0.562` / `0.438`
- buy phase-only top 10% zone 5% / 3% hit rate: `0.479` / `0.333`
- sell unconditional 5% zone prevalence on test: `0.287`
- sell learned-full top 10% zone 5% / 3% hit rate: `0.792` / `0.542`
- sell fixed-weight top 10% zone 5% / 3% hit rate: `0.812` / `0.521`
- sell phase-only top 10% zone 5% / 3% hit rate: `0.625` / `0.438`

## Swing-Level Summary

- buy test down swings: `45`
- buy learned-full best-row avg / median distance: `0.049` / `0.028`
- buy learned-full best-row within 5% / 3%: `0.733` / `0.556`
- buy fixed-weight best-row within 5% / 3%: `0.733` / `0.578`
- sell test up swings: `44`
- sell learned-full best-row avg / median distance: `0.027` / `0.020`
- sell learned-full best-row within 5% / 3%: `0.909` / `0.727`
- sell fixed-weight best-row within 5% / 3%: `0.932` / `0.750`

## Coverage Thresholds

- buy `learned_full` threshold `0.70`: coverage `0.800`, within 5% / 3% `0.589` / `0.421`, avg distance `0.062`, rows `107`
- buy `learned_full` threshold `0.80`: coverage `0.733`, within 5% / 3% `0.565` / `0.435`, avg distance `0.065`, rows `69`
- sell `learned_full` threshold `0.70`: coverage `1.000`, within 5% / 3% `0.604` / `0.359`, avg distance `0.051`, rows `217`
- sell `learned_full` threshold `0.80`: coverage `0.932`, within 5% / 3% `0.617` / `0.383`, avg distance `0.049`, rows `193`

## Ablation Readout

- buy phase+analog best-row within 5% / 3%: `0.733` / `0.556`
- buy phase+exhaustion best-row within 5% / 3%: `0.733` / `0.556`
- sell phase+analog best-row within 5% / 3%: `0.864` / `0.682`
- sell phase+exhaustion best-row within 5% / 3%: `0.932` / `0.750`

## Interpretation

- this refinement is judged primarily by swing-level best-pick quality and threshold coverage, not generic row classification
- the learned combiner improves materially over phase-only on sell-side ranking, but it does not yet dominate the fixed-weight reference on best-pick quality
- fixed-weight score remains exported because it is still a strong robustness comparator and currently remains competitive, especially on buy-side proximity
- buy-side analog contribution is weak in the learned combiner; sell-side analog and exhaustion contributions are directionally useful
- analog probabilities now test whether direction-restricted historical memory adds useful ranking information beyond phase and exhaustion
- no trade logic, capital management, or backtest is introduced here
