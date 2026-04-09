# SAFE v4.0 Low Risk Daily Simulator

## Section 1 — Why This Pass Is Being Run

- this is a stricter calendar-time simulator for one frozen research template
- it is not a production backtest, not a portfolio system, and not a final robustness proof
- the purpose is to see whether the template still looks sane once translated into a daily equity path with simple trading friction

## Section 2 — Frozen Entry / Exit Rules

- entry: `low_risk_wait2_persist_reclaim`
- exit: `fixed_horizon_5d`
- position handling: one position at a time; overlapping signals are skipped while a position is open
- entry assumption: signal-day close
- exit assumption: close after exactly 5 trading days

## Section 3 — Daily Simulator Assumptions

- daily chronology uses close-to-close mark-to-market while the trade is active
- the position becomes active after the entry close and contributes returns from the next close-to-close step through the exit close
- friction assumptions are expressed as round-trip bps and split evenly across entry and exit
- tested round-trip friction assumptions: `0` bps, `10` bps, `25` bps

## Section 4 — Full-Sample Results

- baseline friction: `0` bps round-trip
- trade count: `8`
- win rate: `87.50%`
- mean trade return: `6.28%`
- median trade return: `5.97%`
- compounded return: `60.82%`
- annualized return: `5.66%`
- max drawdown: `-2.95%`
- average holding time: `5.00` trading days
- time in market: `1.27%`
- mean MFE / MAE: `8.21%` / `-0.95%`
- latest daily equity: `60.82%` with running drawdown `-1.19%`

- best trade: `2020-07-25` -> `2020-07-30`, net return `14.42%`
- worst trade: `2024-06-05` -> `2024-06-10`, net return `-2.21%`

## Section 5 — Yearly Breakdown

| Year | Trades | Win rate | Mean trade return | Compounded return | Max drawdown | Time in market |
| --- | --- | --- | --- | --- | --- | --- |
| `2020` | 4 | 100.00% | 8.79% | 39.36% | -1.12% | 5.46% |
| `2024` | 2 | 50.00% | 3.77% | 7.32% | -2.95% | 2.73% |
| `2025` | 2 | 100.00% | 3.76% | 7.53% | -1.23% | 2.74% |

## Section 6 — Friction Sensitivity

| Round-trip friction | Trades | Mean trade return | Compounded return | Max drawdown | Viability read |
| --- | --- | --- | --- | --- | --- |
| `0` bps | 8 | 6.28% | 60.82% | -2.95% | still sane |
| `10` bps | 8 | 6.17% | 59.54% | -3.05% | still sane |
| `25` bps | 8 | 6.01% | 57.64% | -3.20% | still sane |

## Section 7 — Clear Conclusion

- yes, the template still looks sane once translated into a daily chronological simulator.
- modest costs hurt the profile, but they do not erase it in this first calendar-time implementation.
- the event count is still small, so this should be read as calendar-time sanity, not final proof of deployable robustness.
- the template remains strong enough to stay the primary active research template.
- the next justified step would be a more formal template-specific walk-forward implementation or a stricter out-of-time holdout, not renewed branch hunting.
