# SAFE v4.0 Signal Outcome Evaluation

## Purpose

This pass measures what happens after discrete structural signal events. It is event-based forward-path analysis only: no execution, entries/exits, stops, position sizing, portfolio logic, PnL, or backtests.

## Event Selection

- Primary events: `LONG_SIGNAL_NEW`, `SELL_SIGNAL_NEW`
- Fixed-horizon close-to-close returns: 1d, 3d, 5d, 10d
- Path metrics: 5d and 10d favorable/adverse excursions
- Touch metrics: +/-2% and +/-5%, plus 2% favorable/adverse ordering inside 10d

## Signal Outcome Summary

| group | event_count | mean_return_5d | median_return_5d | mean_return_10d | median_return_10d | mean_favorable_excursion_10d | mean_adverse_excursion_10d | touch_favorable_2pct_10d_rate | touch_adverse_2pct_10d_rate | favorable_2pct_before_adverse_2pct_10d_rate | adverse_2pct_before_favorable_2pct_10d_rate | median_time_to_favorable_2pct_10d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LONG_SIGNAL_NEW | 159.000 | 0.5% | 0.8% | 1.3% | 1.6% | 8.9% | -7.9% | 81.1% | 76.7% | 42.1% | 45.3% | 2.000 |
| SELL_SIGNAL_NEW | 307.000 | -0.2% | 0.2% | -0.8% | 0.5% | 7.2% | -7.8% | 77.5% | 77.9% | 45.6% | 42.7% | 1.000 |

## Interpretation Questions

1. Directional correctness: summarized by side-adjusted mean/median returns.
2. Path cleanliness: summarized by favorable versus adverse excursion and 2% ordering.
3. Adverse movement before favorable movement: summarized by adverse-before-favorable 2% rate.
4. Signal speed: summarized by median time to favorable 2% touch.
5. Long versus sell difference: shown in the side-by-side signal summary.

## Decision Framing

`LONG_SIGNAL_NEW` has positive average outcome but path ordering is mixed. `SELL_SIGNAL_NEW` does not show a clean positive forward-path edge.

These results describe forward behavior after structural signals. They do not define a strategy or prove tradability.

## Output Files

- `out/swing_bottom/signal_outcomes.csv`
- `out/swing_bottom/signal_outcomes_summary.csv`
