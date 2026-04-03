# SAFE v4.0 Report

## 1. Executive Summary
SAFE v4.0 is a BTC-only daily-state signal engine with an explicit walk-forward decision layer. It combines descriptive market features, semantic HMM regime context, hazard-style ranking signals, explicit state definitions, state-to-outcome mappings, and long/flat policy validation.

SAFE v4.0 achieved a strict leakage-free walk-forward policy proof. The first fixed-policy proof remained positive after removing full-sample leakage, and the later ablation and stress phases showed that the strongest edge comes from opportunity ranking rather than from risk filtering alone.

Key conclusions:
- A real walk-forward edge is present.
- The dominant driver is opportunity-led ranking.
- The edge remains positive under multiple stress scenarios, but it is time-sensitive and degrades materially with delay.

## 2. Methodology
The SAFE v4.0 research path was split into two layers:
- A descriptive layer that defines states, outcomes, and ranking signals.
- A strict walk-forward layer that rebuilds daily expectations using only information available before each anchor date.

The walk-forward decision layer used:
- `features.csv`
- `states.csv`
- `targets.csv`
- daily BTC OHLCV from `daily_price.json`

For each anchor date `t`, any state-conditioned expectation used on day `t` was built only from rows strictly earlier than `t`, and only from rows whose 10-day outcomes were already resolved by `t`. Fallback order was:
1. `hybrid` state with at least 30 prior observations
2. `market_regime` with at least 30 prior observations
3. `hmm_label` with at least 50 prior observations
4. otherwise no estimate

Signals formed at the close of day `t` were applied to day `t+1` close-to-close returns. Evaluation used daily bars only, fixed transaction costs, and long/flat policies only. No future target values, future state mappings, or full-sample aggregates were allowed into the walk-forward branch.

Accepted walk-forward decision-layer coverage:
- total rows: `3151`
- usable walk-forward rows: `2886`
- first usable date: `2018-02-04`

This is a leakage-free daily-bar validation path, not an intraday execution model.

## 3. Ablation Findings
The ablation phase tested 42 walk-forward policy variants built only from the accepted walk-forward decision output.

Most important findings:
- `opportunity_only` dominated `risk_only`.
- `opp_only_lb6_ub7` was the strongest variant by Sharpe and total return in the controlled refinement grid.
- `opp_asym_lb6_ub7` remained strong, but did not improve on `opp_only_lb6_ub7`.
- `tilt_only` was useful, but weaker than the best opportunity-led variants.
- `risk_tilt` improved on `tilt_only`, but still did not match the best opportunity-led result.

Key accepted ablation metrics:
- `opp_only_lb6_ub7`: Sharpe `1.286`, total return `4707.34%`, max drawdown `-48.40%`
- `opp_asym_lb6_ub7`: Sharpe `1.256`, total return `2069.62%`, max drawdown `-28.08%`
- best `risk_only` (`risk_only_lb4_ub9`): Sharpe `0.688`
- best baseline (`defensive_trend_following_baseline`): Sharpe `0.811`, max drawdown `-6.92%`

Interpretation:
- Opportunity ranking is the core carrier of the walk-forward edge.
- Risk filtering helps, but does not explain the edge by itself.
- Asymmetry contributes limited incremental value once opportunity ranking is already present.
- Tilt is best understood as a compact execution layer, not as the primary signal source.

## 4. Stress-Test Findings
The strongest accepted variants were stress-tested without re-optimization:
- best `opportunity_only` by Sharpe
- best `opportunity_asym` by Sharpe
- best baseline by Sharpe
- best `risk_only` by Sharpe
- `always_long`
- `always_flat`

Stress dimensions:
- full sample
- early / middle / late subperiods
- bullish / bearish / high-volatility / lower-volatility conditional slices
- transaction costs: `0`, `10`, `25`, `50` bps
- entry delay: `0d`, `1d`

Overall stress findings:
- `opp_only_lb6_ub7` remained the strongest policy by median Sharpe across stress scenarios: `1.230`
- `defensive_trend_following_baseline` had the strongest active worst-case drawdown resilience: `-14.61%`
- Opportunity-led logic remained strong across all three deterministic time subperiods
- Higher costs hurt the opportunity-led variants, but did not eliminate the edge in this first pass
- A 1-day extra delay degraded the active strategies materially

Accepted delay-sensitivity examples:
- `opp_only_lb6_ub7`: Sharpe `1.286` -> `0.788`, total return `4707.34%` -> `678.97%`
- `opp_asym_lb6_ub7`: Sharpe `1.256` -> `0.859`, total return `2069.62%` -> `637.43%`
- `defensive_trend_following_baseline`: Sharpe `0.811` -> `0.268`, total return `71.81%` -> `19.06%`

Key insight:
- The edge survives reasonable stress.
- The edge is time-sensitive.
- Prompt next-day capture matters materially.

## 5. What SAFE IS
SAFE v4.0 is:
- a BTC daily-state signal engine
- a walk-forward validated decision layer
- a ranking system that converts market state into actionable long/flat context
- a framework for measuring expected forward behavior from explicit states

SAFE provides:
- state definitions
- ranking signals
- walk-forward decision outputs
- validated long/flat policy evidence

Capital management is outside SAFE.

## 6. What SAFE IS NOT
SAFE v4.0 is not:
- a portfolio construction system
- a position sizing framework
- a capital allocation engine
- an execution engine
- an intraday model
- a calibrated literal probability engine for all event outputs

SAFE’s hazard-style outputs were useful as ranking signals, but not as honest literal probabilities for simple touch-event proxies.

## 7. Final Conclusions
- A real walk-forward edge is present.
- The edge is primarily driven by opportunity ranking.
- Risk filtering is supportive, but not sufficient on its own.
- Asymmetry adds limited value once opportunity ranking is already present.
- Tilt is useful as an execution layer, not as the core source of edge.
- The strongest walk-forward policy variant is opportunity-led.
- The edge survives multiple robustness checks.
- The signal is time-sensitive and requires timely execution.
- Risk management and capital allocation are external to SAFE.

## 8. Known Limitations
- Daily resolution only. The system is evaluated on daily close-to-close data.
- No intraday ordering truth. SAFE does not validate intraday execution sequencing.
- Simplified cost model. Costs are modeled as fixed basis points per position change.
- No slippage model beyond fixed bps.
- Delay sensitivity is material. The edge decays when execution is delayed.
- Some performance may remain regime-dependent across historical eras and conditional market slices.
- Stress tests were validation-oriented, not production-readiness proof.
- Repeated threshold testing can still overfit if pushed beyond the controlled refinement scope already accepted.
