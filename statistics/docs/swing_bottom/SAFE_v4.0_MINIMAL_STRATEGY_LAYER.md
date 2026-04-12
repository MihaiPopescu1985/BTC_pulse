# SAFE v4.0 Minimal Strategy Layer

## Purpose

This is the first minimal long-only strategy simulation layer. It is intentionally simple and transparent. It does not add stops, take-profit rules, position sizing, leverage, portfolio logic, or optimization.

## Rules

- Position model: binary long or flat, one position at a time.
- Entry: `LONG_SIGNAL_NEW` inside `LONG_QUALITY_HIGH` and `high_closest_to_low` conditioning.
- Exit: first of `SELL_SIGNAL_NEW`, `SIGNAL_INVALIDATED`, max hold of 10 trading days, or end of data.
- Sell signals are used only as exit/risk control, never as standalone short entries.
- Prices use close-to-close accounting for research measurement; this is not an execution model.

## Causality Caveat

`strict_closest_to_low` uses the final conditioning subset based on proximity to the eventual confirmed swing low. That field is future-derived. Therefore this pass is an oracle/feasibility check for whether the cleanest structural subset behaves like a real strategy object, not a deployable causal strategy.

## Baseline

`baseline_all_long_signals` uses every `LONG_SIGNAL_NEW` event with the same exits and one-position-at-a-time handling.

## Summary

| strategy_name | trade_count | win_rate | mean_return | median_return | mean_max_favorable_excursion | mean_max_adverse_excursion | max_drawdown_per_trade | average_duration_days | adverse_first_rate | clean_follow_through_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_all_long_signals | 118.000 | 65.3% | 0.6% | 2.0% | 5.0% | -6.6% | -52.9% | 5.246 | 45.8% | 41.5% |
| strict_closest_to_low | 16.000 | 100.0% | 5.2% | 5.0% | 7.3% | -1.1% | -1.9% | 3.062 | 0.0% | 100.0% |

## Final Conclusion

**Viable minimal strategy as an oracle feasibility check.** The strict subset improves realized outcomes and path quality versus all long signals, but it uses the future-derived closest-to-low conditioning label. It is not deployable until that condition is replaced by a causal proxy.

This result answers whether the strict structural subset behaves like a plausible strategy object. It is not production-ready and should not be read as deployable.

## Output Files

- `out/swing_bottom/minimal_strategy_trades.csv`
- `out/swing_bottom/minimal_strategy_summary.csv`
