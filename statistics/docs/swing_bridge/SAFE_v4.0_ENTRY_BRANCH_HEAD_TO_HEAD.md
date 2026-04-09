# SAFE v4.0 Entry Branch Head To Head

## Section 1 — Why This Pass Is Being Run

- the prior pass produced one active execution-quality candidate: `low_risk_base_volatility_sanity_ts20_confirm`
- this pass checks whether a small reclaim layer improves that winner and whether `squeeze_release_up` can beat it as a rival execution branch
- the comparison is path-quality first, upside retention second, sample viability third

## Section 2 — Low-Risk Branch Timing Refinements Tested

- baseline winner: `low_risk_base_volatility_sanity_ts20_confirm`
- `low_risk_reclaim_close`: require close above prior close
- `low_risk_reclaim_high`: require close above prior high
- `low_risk_wait1_persist_reclaim`: require one-day persistence plus close above prior close

## Section 3 — Squeeze-Release Rival Variants Tested

- `squeeze_release_up_raw`
- `squeeze_release_up_confirm_close`
- `squeeze_release_up_reclaim_high`
- `squeeze_release_up_wait1_persist_close`

## Section 4 — Head-To-Head Execution-Quality Comparison

- low-risk winner baseline: n=`71`, ret_10d mean `5.04%`, max_down_10d `-4.46%`, touch_down `52.11%`, `-2% before +2%` `42.25%`

| Variant | Branch | n | ret_10d mean | max_up_10d | max_down_10d | touch_up | touch_down | -2% before +2% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `low_risk_base_volatility_sanity_ts20_confirm` | `low_risk_base` | 71 | 5.04% | 10.07% | -4.46% | 71.83% | 52.11% | 42.25% |
| `low_risk_reclaim_close` | `low_risk_base` | 45 | 6.36% | 10.94% | -3.50% | 77.78% | 44.44% | 37.78% |
| `low_risk_reclaim_high` | `low_risk_base` | 26 | 6.44% | 10.52% | -2.59% | 80.77% | 38.46% | 34.62% |
| `low_risk_wait1_persist_reclaim` | `low_risk_base` | 28 | 8.16% | 13.00% | -3.15% | 85.71% | 39.29% | 35.71% |
| `squeeze_release_up_confirm_close` | `squeeze_release_up` | 34 | 2.79% | 7.65% | -4.58% | 85.29% | 76.47% | 50.00% |
| `squeeze_release_up_raw` | `squeeze_release_up` | 49 | 3.08% | 7.75% | -3.98% | 85.71% | 69.39% | 44.90% |
| `squeeze_release_up_reclaim_high` | `squeeze_release_up` | 24 | 1.33% | 6.58% | -5.35% | 79.17% | 79.17% | 54.17% |
| `squeeze_release_up_wait1_persist_close` | `squeeze_release_up` | 17 | 4.73% | 8.62% | -3.65% | 88.24% | 70.59% | 47.06% |

Low-risk refinements vs current winner:

- `low_risk_wait1_persist_reclaim`: delta ret_10d `3.12%`, delta max_down `1.31%`, delta touch_down `-12.83%`, delta `-2% before +2%` `-6.54%`, n=`28`
- `low_risk_reclaim_close`: delta ret_10d `1.32%`, delta max_down `0.96%`, delta touch_down `-7.67%`, delta `-2% before +2%` `-4.48%`, n=`45`
- `low_risk_reclaim_high`: delta ret_10d `1.40%`, delta max_down `1.87%`, delta touch_down `-13.65%`, delta `-2% before +2%` `-7.64%`, n=`26`

Squeeze-release rivals vs current winner:

- `squeeze_release_up_wait1_persist_close`: delta ret_10d `-0.32%`, delta max_down `0.80%`, delta touch_down `18.48%`, delta `-2% before +2%` `4.81%`, n=`17`
- `squeeze_release_up_raw`: delta ret_10d `-1.97%`, delta max_down `0.47%`, delta touch_down `17.28%`, delta `-2% before +2%` `2.64%`, n=`49`
- `squeeze_release_up_reclaim_high`: delta ret_10d `-3.72%`, delta max_down `-0.90%`, delta touch_down `27.05%`, delta `-2% before +2%` `11.91%`, n=`24`
- `squeeze_release_up_confirm_close`: delta ret_10d `-2.25%`, delta max_down `-0.13%`, delta touch_down `24.36%`, delta `-2% before +2%` `7.75%`, n=`34`

## Section 5 — Clear Conclusion

- the current leader is now `low_risk_wait1_persist_reclaim` from `low_risk_base`.
- best low-risk variant: `low_risk_wait1_persist_reclaim` with ret_10d mean `8.16%`, touch_down `39.29%`, `-2% before +2%` `35.71%`, n=`28`
- best squeeze-release variant: `squeeze_release_up_wait1_persist_close` with ret_10d mean `4.73%`, touch_down `70.59%`, `-2% before +2%` `47.06%`, n=`17`
- further refinement should continue on one branch only, and that branch should be the current head-to-head winner.
