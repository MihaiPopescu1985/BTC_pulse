# SAFE v4.0 Low Risk Walkforward Style

## Section 1 — Why This Pass Is Being Run

- this is a fixed-rule chronological walk-forward-style evaluation of one frozen template
- no thresholds are re-fit by fold and no branch design is changed
- the purpose is to see whether the same rule remains acceptable across sequential test blocks

## Section 2 — Frozen Template And Frozen Exit Rule

- entry: `low_risk_wait2_persist_reclaim`
- exit: `fixed_horizon_5d`
- trade handling: one position at a time, overlapping signals skipped until active trade exits

## Section 3 — Chronological Fold Design

- fold design: expanding-history train, next-2-trade test block
- fold 1: train first 2 trades, test trades 3-4
- fold 2: train first 4 trades, test trades 5-6
- fold 3: train first 6 trades, test trades 7-8
- because the event count is small, folds are intentionally few and each test block is reported honestly

## Section 4 — Fold-By-Fold Results

- full sample: trades `8`, win rate `87.50%`, mean return `6.28%`, compounded `60.82%`, max drawdown `-2.21%`

| Fold | Train end | Test range | Test trades | Win rate | Mean return | Median return | Compounded | Max DD | Mean MFE | Mean MAE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fold_1` | 2020-07-30 | 2020-10-10 -> 2020-10-22 | 2 | 100.00% | 8.02% | 8.02% | 16.30% | 0.00% | 10.06% | -0.60% |
| `fold_2` | 2020-10-22 | 2024-02-08 -> 2024-06-10 | 2 | 50.00% | 3.77% | 3.77% | 7.32% | -2.21% | 6.23% | -1.94% |
| `fold_3` | 2024-06-10 | 2025-07-05 -> 2025-09-20 | 2 | 100.00% | 3.76% | 3.76% | 7.53% | 0.00% | 5.11% | -0.63% |

## Section 5 — Stability / Concentration Interpretation

- `fold_1`: mean return `8.02%`, compounded `16.30%`, max drawdown `0.00%`, test trades=`2`
- `fold_2`: mean return `3.77%`, compounded `7.32%`, max drawdown `-2.21%`, test trades=`2`
- `fold_3`: mean return `3.76%`, compounded `7.53%`, max drawdown `0.00%`, test trades=`2`
- best-performing test fold: `fold_1` with compounded `16.30%`
- share of total gross profits contributed by the best test fold: `30.58%`
- no test fold is negative on mean return, but the sample is very small.

## Section 6 — Clear Conclusion

- the template survives this walk-forward-style test well enough for continued research.
- it remains the primary active template because no fold fully invalidates it, but confidence should stay moderate given the tiny test blocks.
- recency note: the latest fold `fold_3` had 2 trades with mean return `3.76%`.
- the next justified step is a more formal template-specific walk-forward implementation with the same frozen rule, not a return to branch exploration.
