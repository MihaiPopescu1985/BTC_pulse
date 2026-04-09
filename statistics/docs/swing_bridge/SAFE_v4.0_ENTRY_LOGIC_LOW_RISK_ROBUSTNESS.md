# SAFE v4.0 Entry Logic Low Risk Robustness

## Section 1 — Why This Pass Is Being Run

- `low_risk_wait1_persist_reclaim` is the current best entry candidate
- this pass tests whether its quality survives small local rule changes
- the purpose is structural stability, not new idea generation

## Section 2 — Baseline Template

- exact baseline: low-risk base branch + volatility sanity + TS_20 confirmation + one-day persistence + reclaim via close above prior close

## Section 3 — Local Perturbations Tested

- `low_risk_sameday_reclaim_close`
- `low_risk_wait1_persist_reclaim`
- `low_risk_wait2_persist_reclaim`
- `low_risk_wait1_persist_reclaim_high`

## Section 4 — Robustness Comparison Table

| Variant | n | ret_5d | ret_10d | max_down_5d | max_down_10d | touch_down_5d | touch_down_10d | -2% before +2% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `low_risk_sameday_reclaim_close` | 45 | 3.88% | 6.36% | -2.40% | -3.50% | 35.56% | 44.44% | 37.78% |
| `low_risk_wait1_persist_reclaim` | 28 | 4.33% | 8.16% | -2.43% | -3.15% | 32.14% | 39.29% | 35.71% |
| `low_risk_wait1_persist_reclaim_high` | 16 | 5.84% | 7.92% | -1.61% | -2.52% | 31.25% | 37.50% | 37.50% |
| `low_risk_wait2_persist_reclaim` | 16 | 5.72% | 9.84% | -1.15% | -2.10% | 12.50% | 25.00% | 18.75% |

## Section 5 — Whether The Candidate Is Stable Or Fragile

- frozen baseline: n=`28`, ret_5d `4.33%`, ret_10d `8.16%`, max_down_10d `-3.15%`, touch_down_10d `39.29%`, `-2% before +2%` `35.71%`

- `low_risk_wait2_persist_reclaim`: delta ret_5d `1.39%`, delta ret_10d `1.68%`, delta max_down_10d `1.04%`, delta touch_down_10d `-14.29%`, delta `-2% before +2%` `-16.96%`, n=`16`
- `low_risk_wait1_persist_reclaim_high`: delta ret_5d `1.51%`, delta ret_10d `-0.24%`, delta max_down_10d `0.62%`, delta touch_down_10d `-1.79%`, delta `-2% before +2%` `1.79%`, n=`16`
- `low_risk_sameday_reclaim_close`: delta ret_5d `-0.45%`, delta ret_10d `-1.80%`, delta max_down_10d `-0.35%`, delta touch_down_10d `5.16%`, delta `-2% before +2%` `2.06%`, n=`45`

## Section 6 — Clear Conclusion

- the candidate looks structurally stable rather than narrowly fragile. Small nearby rule changes mostly preserve the improvement direction.
- this template reads better as a 5d-to-10d execution setup than as a longer-hold idea. The short-horizon profile is cleaner.
- active version after this pass: `low_risk_wait2_persist_reclaim`
- promote `low_risk_wait2_persist_reclaim` as the new active variant. It improves the frozen baseline without collapsing the sample.
- the next step can move closer to strategy-layer testing, but only for this single low-risk branch.
