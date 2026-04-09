# SAFE v4.0 Low Risk Event Backtest

## Section 1 — Why This Pass Is Being Run

- this is a stricter chronological event-based test on one frozen entry/exit template
- it is not a production backtest and not a full walk-forward proof
- the purpose is to see whether the candidate remains sane when viewed as a dated event sequence through time

## Section 2 — Frozen Entry And Exit Rules

- entry: `low_risk_wait2_persist_reclaim`
- exit: `fixed_horizon_5d`
- trade handling rule: one position at a time; overlapping signals are skipped until the active trade exits
- entry assumption: signal-day close

## Section 3 — Chronological Event Summary

- trade count: `8`
- win rate: `87.50%`
- mean return per trade: `6.28%`
- median return per trade: `5.97%`
- compounded return: `60.82%`
- max drawdown: `-2.21%`
- average holding time: `5.00` days
- mean MFE: `8.21%`
- mean MAE: `-0.95%`

| Seq | Entry | Exit | Return | MFE | MAE | Equity | Drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2020-07-18 | 2020-07-23 | 4.72% | 5.38% | -0.75% | 4.72% | 0.00% |
| 2 | 2020-07-25 | 2020-07-30 | 14.42% | 17.47% | -0.52% | 19.83% | 0.00% |
| 3 | 2020-10-10 | 2020-10-15 | 1.88% | 3.78% | -1.07% | 22.08% | 0.00% |
| 4 | 2020-10-17 | 2020-10-22 | 14.16% | 16.35% | -0.12% | 39.36% | 0.00% |
| 5 | 2024-02-08 | 2024-02-13 | 9.74% | 11.22% | -0.10% | 52.93% | 0.00% |
| 6 | 2024-06-05 | 2024-06-10 | -2.21% | 1.25% | -3.78% | 49.56% | -2.21% |
| 7 | 2025-07-05 | 2025-07-10 | 7.22% | 8.01% | -0.71% | 60.36% | 0.00% |
| 8 | 2025-09-15 | 2025-09-20 | 0.29% | 2.21% | -0.55% | 60.82% | 0.00% |

## Section 4 — Era / Period Breakdown

| Era | Date range | Trades | Win rate | Mean return | Compounded return | Max drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| `early` | 2020-07-18 -> 2020-07-30 | 2 | 100.00% | 9.57% | 19.83% | 0.00% |
| `middle` | 2020-10-10 -> 2024-02-13 | 3 | 100.00% | 8.59% | 27.63% | 0.00% |
| `late` | 2024-06-05 -> 2025-09-20 | 3 | 66.67% | 1.77% | 5.16% | 0.00% |

## Section 5 — Concentration / Clustering Readout

- best trade: `2020-07-25` to `2020-07-30`, return `14.42%`
- worst trade: `2024-06-05` to `2024-06-10`, return `-2.21%`
- share of positive profits from top 2 trades: `54.51%`
- share of total losses from worst 2 trades: `100.00%`
- mean days since previous entry: `269.3`
- median days since previous entry: `77.0`
- trades by entry year:
  - `2020`: `4`
  - `2024`: `2`
  - `2025`: `2`

## Section 6 — Clear Conclusion

- yes, the template still looks sane under stricter chronological testing.
- results are not dominated by only one or two trades.
- the signal appears episodic rather than evenly distributed, but not limited to a single isolated era.
- this is good enough to justify a later formal walk-forward-style implementation on this single frozen template.
