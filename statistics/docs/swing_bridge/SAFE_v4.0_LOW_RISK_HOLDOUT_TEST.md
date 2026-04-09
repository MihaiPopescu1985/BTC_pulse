# SAFE v4.0 Low Risk Holdout Test

## Section 1 — Why This Holdout Pass Is Being Run

- this is a strict frozen-rule out-of-time credibility test on the single active template
- no branch design, threshold fitting, or rule re-optimization is allowed in this pass
- the purpose is to see whether the same rule still behaves reasonably in a recent untouched holdout segment

## Section 2 — Frozen Rule And Holdout Split

- entry: `low_risk_wait2_persist_reclaim`
- exit: `fixed_horizon_5d`
- handling: one position at a time, overlapping signals skipped while a trade is open
- execution assumption: signal-day close entry, close exit after 5 trading days
- holdout split rule: final 20% of the daily chronology
- pre-holdout period: `2017-08-17` -> `2024-07-10`
- holdout period: `2024-07-11` -> `2026-04-02`
- the split is deterministic and recent; it was chosen for chronology discipline, not for outcome optimization

## Section 3 — Pre-Holdout Vs Holdout Comparison

| Segment | Trade count | Win rate | Mean trade return | Median trade return | Compounded return | Max drawdown | Mean MFE | Mean MAE | Time in market |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `full_sample` | 8 | 87.50% | 6.28% | 5.97% | 60.82% | -2.95% | 8.21% | -0.95% | 1.27% |
| `pre_holdout` | 6 | 83.33% | 7.12% | 7.23% | 49.56% | -2.95% | 9.24% | -1.06% | 1.19% |
| `holdout` | 2 | 100.00% | 3.76% | 3.76% | 7.53% | -1.23% | 5.11% | -0.63% | 1.58% |

## Section 4 — Holdout Friction Sensitivity

| Round-trip friction | Holdout trades | Holdout mean trade return | Holdout compounded return | Holdout max drawdown | Read |
| --- | --- | --- | --- | --- | --- |
| `0` bps | 2 | 3.76% | 7.53% | -1.23% | positive but sparse |
| `10` bps | 2 | 3.65% | 7.32% | -1.23% | positive but sparse |
| `25` bps | 2 | 3.50% | 7.00% | -1.31% | positive but sparse |

## Section 5 — Clear Conclusion

- the rule did fire in holdout, but only `2` times, so evidence remains sparse.
- holdout performance is positive rather than broken, which is the main credibility hurdle for this pass.
- holdout is weaker than pre-holdout, but not obviously dead.
- modest costs do not overturn the holdout read, though the sample is too small for strong claims.
- this is still not production readiness or full walk-forward proof.
- the template survives the holdout well enough to remain the primary active research template.
- the next justified step is a stricter template-specific implementation in the accepted walk-forward path, not more branch exploration.
