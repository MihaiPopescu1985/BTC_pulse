# SAFE v4.0 Low Risk Strategy Sanity

## Section 1 — Why This Pass Is Being Run

- this is a first strategy-layer sanity test on one already-selected entry template
- it is not a walk-forward validation and not a production-readiness claim
- the purpose is to see whether the template still looks reasonable once converted into simple trades

## Section 2 — Frozen Entry Rule

- exact entry template: `low_risk_wait2_persist_reclaim`
- implementation: low-risk base branch + volatility sanity + TS_20 confirmation + two-day persistence + close above prior close
- trade handling rule: one position at a time; overlapping signals are ignored until the active trade exits
- entry assumption: signal-day close

## Section 3 — Exit Policies Tested

- `fixed_horizon_5d`
- `fixed_horizon_10d`
- `tp5_sl2_h10`
- `tp8_sl3_h10`
- for TP/SL policies, if both TP and SL are touched on the same bar, the stop is assumed to hit first (conservative rule)

## Section 4 — Trade-Level Comparison Table

| Policy | Trades | Win rate | Mean return | Median return | Avg hold | TP hit | SL hit | Compounded return | Max DD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fixed_horizon_5d` | 8 | 87.50% | 6.28% | 5.97% | 5.00 | 0.00% | 0.00% | 60.82% | -2.21% |
| `fixed_horizon_10d` | 6 | 66.67% | 6.00% | 7.15% | 10.00 | 0.00% | 0.00% | 38.30% | -6.86% |
| `tp8_sl3_h10` | 6 | 66.67% | 3.91% | 6.73% | 6.00 | 50.00% | 33.33% | 25.00% | -3.00% |
| `tp5_sl2_h10` | 7 | 71.43% | 3.00% | 5.00% | 4.57 | 71.43% | 28.57% | 22.57% | -2.00% |

## Section 5 — What Survives First Strategy-Layer Testing And What Does Not

- `fixed_horizon_5d`: mean return `6.28%`, median `5.97%`, mean MFE `8.21%`, mean MAE `-0.95%`, winner avg `7.49%`, loser avg `-2.21%`, trades=`8`
- `fixed_horizon_10d`: mean return `6.00%`, median `7.15%`, mean MFE `10.80%`, mean MAE `-2.82%`, winner avg `12.09%`, loser avg `-6.19%`, trades=`6`
- `tp8_sl3_h10`: mean return `3.91%`, median `6.73%`, mean MFE `6.58%`, mean MAE `-1.58%`, winner avg `7.37%`, loser avg `-3.00%`, trades=`6`
- `tp5_sl2_h10`: mean return `3.00%`, median `5.00%`, mean MFE `6.76%`, mean MAE `-1.43%`, winner avg `5.00%`, loser avg `-2.00%`, trades=`7`

## Section 6 — Clear Conclusion

- yes, the template still looks sane under simple trade logic: best current exit style is `fixed_horizon_5d`
- this is still only a first event-level sanity check, not a formal walk-forward or production proof
- the next step should move to a more formal event-based backtest / walk-forward style test for this single entry template
