# SAFE v4.0 Productive Plan

## A. Goal
Turn SAFE v4.0 from a validated research branch into a productive, maintainable signal engine.

## B. Repository structure after cleanup
Productive execution path:
- `statistics/src/core/`

Research / archived v4 iteration:
- `statistics/src/research/v4_iteration/`

Accepted validation path:
- `statistics/src/walkforward/`

Stable support areas:
- `statistics/src/data/`
- `statistics/src/features/`
- `statistics/src/models/`
- `statistics/src/strategy/`
- `statistics/src/util/`

The productive path is the signal-generation path under `src/core`. The accepted walk-forward branch under `src/walkforward` remains the validation path that must be rerun after any productive feature pruning. The research path remains available for audit context, but it is no longer part of the main execution surface.

## C. Indicator audit plan
The second pass will revisit the full indicator set across these families:
- trend family
- volatility family
- position/stretch family
- participation family
- regime/hazard outputs
- SAFE meta outputs
- on-chain features

Each indicator will be classified into one of:
- `productive_keep`
- `research_only`
- `likely_remove`

## D. Audit questions
For every indicator, the second pass should ask:
- does it add distinct information?
- is it redundant with another indicator?
- was it actually tested in the accepted walk-forward path?
- does removing it degrade the productive walk-forward result?
- is it only historically interesting, or actually useful?

## E. Productive subset criteria
An indicator stays in the productive set only if it contributes to the accepted path on these grounds:
- distinct information
- walk-forward usefulness
- robustness contribution
- interpretability
- maintainability

Indicators that are only descriptive, weakly tested, or redundant should not remain in the productive subset by default.

## F. Revalidation order
The next pass must follow this order:
1. indicator audit
2. feature pruning / classification
3. rebuild productive feature set
4. rerun walk-forward decision analysis
5. rerun walk-forward backtest
6. rerun refinement
7. rerun stress test
8. relock productive v4.0

## G. Non-goals
This next pass is not for:
- new model families
- broad optimization
- intraday redesign
- portfolio sizing work
