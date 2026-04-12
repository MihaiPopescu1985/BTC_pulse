# SAFE v4.0 Long Signal Refinement

## Purpose

This pass analyzes only `LONG_SIGNAL_NEW` events to determine whether the current structural stack can separate better and worse long-side entry-quality zones. It does not define execution, entries, exits, stops, position sizing, portfolio logic, PnL, or backtests.

## Refinement Logic

A compact structural score is built from high buy timing, strong timing spread, high clarity, low conflict, low sell timing, and proximity to the current down-swing low. Penalties are applied for far-from-low structure, high conflict, weak spread, and elevated sell timing.

- `LONG_QUALITY_HIGH`: refinement score >= 3
- `LONG_QUALITY_MEDIUM`: refinement score between 1 and 2
- `LONG_QUALITY_LOW`: refinement score <= 0

## Outcome Comparison

| bucket | event_count | event_share | mean_return_5d | median_return_5d | mean_return_10d | median_return_10d | mean_favorable_excursion_10d | mean_adverse_excursion_10d | touch_favorable_2pct_10d_rate | touch_adverse_2pct_10d_rate | favorable_2pct_before_adverse_2pct_10d_rate | adverse_2pct_before_favorable_2pct_10d_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LONG_QUALITY_HIGH | 50.000 | 31.4% | 3.1% | 2.4% | 3.2% | 2.2% | 10.5% | -5.5% | 84.0% | 68.0% | 46.0% | 44.0% |
| LONG_QUALITY_MEDIUM | 40.000 | 25.2% | -0.5% | 0.5% | 0.7% | 0.6% | 8.6% | -9.0% | 77.5% | 85.0% | 27.5% | 47.5% |
| LONG_QUALITY_LOW | 69.000 | 43.4% | -0.9% | -0.2% | 0.3% | 1.4% | 8.0% | -8.9% | 81.2% | 78.3% | 47.8% | 44.9% |

## Structural Profile

| bucket | mean_buy_score | mean_sell_score | mean_spread | mean_clarity | mean_conflict | mean_dist_to_low |
| --- | --- | --- | --- | --- | --- | --- |
| LONG_QUALITY_HIGH | 0.691 | 0.198 | 0.493 | 0.418 | 0.137 | 0.056 |
| LONG_QUALITY_MEDIUM | 0.659 | 0.214 | 0.445 | 0.370 | 0.142 | 0.111 |
| LONG_QUALITY_LOW | 0.666 | 0.264 | 0.402 | 0.335 | 0.177 | 0.101 |

## Final Read

Partially - small improvement only. Refinement helps one dimension, but noise remains material.

The result is diagnostic only. Any later strategy work should treat these buckets as entry-quality context, not as direct order rules.

## Output Files

- `out/swing_bottom/long_signal_refinement.csv`
- `out/swing_bottom/long_signal_refinement_summary.csv`
