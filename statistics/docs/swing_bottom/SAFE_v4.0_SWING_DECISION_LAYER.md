# SAFE v4.0 Swing Decision Layer

## Purpose

- first structural decision layer on top of the validated swing timing scores
- outputs categorical market/playbook states plus continuous buy/sell support and clarity scores
- no trade rules, execution logic, position sizing, or backtesting are introduced

## Score References

- promoted buy score: `buy_hybrid_weighted_balanced_score` from the validated buy-side hybrid pass
- promoted sell score: `sell_fixed_extreme_timing_score`, retained as the strongest sell-side timing reference
- diagnostic sell score retained: `sell_extreme_timing_score`

## Threshold Calibration

- thresholds are calibrated from train+validation rows only
- buy high / moderate: `0.580` / `0.424`
- sell high / moderate: `0.639` / `0.536`
- directional spread minimum: `0.100`

## State Definitions

- `BUY_SETUP`: buy timing high, sell timing below moderate, and buy score leads by at least the spread threshold
- `SELL_SETUP`: sell timing high, buy timing below moderate, and sell score leads by at least the spread threshold
- `CONFLICT_OVERLAP`: both buy and sell timing are at least moderate
- `NEUTRAL_NO_EDGE`: neither side is moderate
- `TRANSITION_UNCLEAR`: one side is moderate/high but the separation is not clean enough for setup classification

## Continuous Support Columns

- `timing_score_spread = promoted_buy_timing_score - promoted_sell_timing_score`
- `timing_score_intensity = max(buy, sell)`
- `timing_score_overlap = min(buy, sell)`
- `buy_dominance_score = buy * (1 - sell)`
- `sell_dominance_score = sell * (1 - buy)`
- `edge_clarity_score = abs(spread) * (0.5 + 0.5 * intensity)`
- `conflict_score = overlap * intensity`

## State Prevalence And Quality

- `BUY_SETUP`: share `0.184`, avg run `1.95` days, buy-zone 5% `0.526`, sell-zone 5% `0.040`, clarity `0.279`
- `SELL_SETUP`: share `0.237`, avg run `2.32` days, buy-zone 5% `0.044`, sell-zone 5% `0.487`, clarity `0.387`
- `CONFLICT_OVERLAP`: share `0.083`, avg run `1.51` days, buy-zone 5% `0.373`, sell-zone 5% `0.137`, clarity `0.096`
- `TRANSITION_UNCLEAR`: share `0.277`, avg run `1.55` days, buy-zone 5% `0.154`, sell-zone 5% `0.218`, clarity `0.195`
- `NEUTRAL_NO_EDGE`: share `0.218`, avg run `2.04` days, buy-zone 5% `0.032`, sell-zone 5% `0.129`, clarity `0.101`

## Separation Readout

- `BUY_SETUP` buy-zone 5% rate: `0.526` vs `NEUTRAL_NO_EDGE` `0.032`
- `SELL_SETUP` sell-zone 5% rate: `0.487` vs `NEUTRAL_NO_EDGE` `0.129`
- separation should be read structurally: states are intended to clarify timing context, not prove a tradable rule

## Conflict Analysis

- conflict rows: `263`
- conflict live-swing direction mix: `up` `0.570`, `down` `0.430`
- conflict avg buy score: `0.522`
- conflict avg sell score: `0.621`
- conflict/overlap should be treated as a mixed timing state, not as a buy or sell trigger

## Interpretation

- the layer turns independent timing scores into a compact structural state taxonomy
- the continuous support columns preserve nuance when a hard state label is too coarse
- the next step should validate whether these decision states help organize later playbook logic; it should not jump directly to trade execution
