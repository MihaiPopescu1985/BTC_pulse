# SAFE v4.0 Causal Bottom-Proximity Proxy

## Purpose

This pass tests whether the oracle `high_closest_to_low` condition can be approximated using only signal-time causal fields. It does not add execution logic, stops, position sizing, portfolio logic, broad model search, or production backtesting.

## Leakage Rule

Proxy definitions use only promoted buy timing, promoted sell timing, timing spread, edge clarity, and conflict score. `dist_to_current_down_swing_low_pct` and `high_closest_to_low` are used only for evaluation and oracle comparison.

## Proxy Comparison

| proxy | uses_future_low_label | event_count | share_of_all_long_signal_new | oracle_precision | oracle_coverage | mean_return_10d | mean_adverse_excursion_10d | favorable_2pct_before_adverse_2pct_10d_rate | adverse_2pct_before_favorable_2pct_10d_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| proxy_all_long_signal_new | 0 | 159 | 100.0% | 10.1% | 100.0% | 1.3% | -7.9% | 42.1% | 45.3% |
| proxy_mixed_long_quality_high_reference | 1 | 50 | 31.4% | 32.0% | 100.0% | 3.2% | -5.5% | 46.0% | 44.0% |
| proxy_oracle_high_closest_to_low | 1 | 16 | 10.1% | 100.0% | 100.0% | 5.6% | -2.7% | 100.0% | 0.0% |
| proxy_causal_score_ge3 | 0 | 39 | 24.5% | 25.6% | 62.5% | 3.1% | -6.8% | 35.9% | 59.0% |
| proxy_causal_score_ge4 | 0 | 26 | 16.4% | 30.8% | 50.0% | 1.3% | -7.2% | 38.5% | 61.5% |
| proxy_strong_spread_clarity | 0 | 53 | 33.3% | 24.5% | 81.2% | 3.2% | -6.0% | 35.8% | 56.6% |
| proxy_buy_extreme_sell_suppressed | 0 | 17 | 10.7% | 23.5% | 25.0% | 5.9% | -6.3% | 29.4% | 64.7% |
| proxy_low_conflict_sell_suppressed | 0 | 46 | 28.9% | 15.2% | 43.8% | -1.7% | -11.1% | 28.3% | 52.2% |
| proxy_compact_causal_confluence | 0 | 32 | 20.1% | 31.2% | 62.5% | 2.3% | -6.2% | 40.6% | 56.2% |

## Gap Versus Causal Reference And Oracle

| proxy | return_10d_delta_vs_quality_high | adverse_excursion_delta_vs_quality_high | favorable_first_delta_vs_quality_high | return_10d_gap_to_oracle | adverse_excursion_gap_to_oracle | favorable_first_gap_to_oracle |
| --- | --- | --- | --- | --- | --- | --- |
| proxy_all_long_signal_new | -0.019 | -0.024 | -0.039 | -0.043 | -0.052 | -0.579 |
| proxy_mixed_long_quality_high_reference | 0.000 | 0.000 | 0.000 | -0.024 | -0.028 | -0.540 |
| proxy_oracle_high_closest_to_low | 0.024 | 0.028 | 0.540 | 0.000 | 0.000 | 0.000 |
| proxy_causal_score_ge3 | -0.001 | -0.013 | -0.101 | -0.026 | -0.041 | -0.641 |
| proxy_causal_score_ge4 | -0.019 | -0.017 | -0.075 | -0.044 | -0.045 | -0.615 |
| proxy_strong_spread_clarity | 0.001 | -0.005 | -0.102 | -0.024 | -0.033 | -0.642 |
| proxy_buy_extreme_sell_suppressed | 0.027 | -0.008 | -0.166 | 0.002 | -0.036 | -0.706 |
| proxy_low_conflict_sell_suppressed | -0.049 | -0.056 | -0.177 | -0.074 | -0.084 | -0.717 |
| proxy_compact_causal_confluence | -0.009 | -0.007 | -0.054 | -0.034 | -0.035 | -0.594 |

## Final Conclusion

**Partial proxy only.** `proxy_buy_extreme_sell_suppressed` improves at least one dimension, but remains materially weaker than the oracle subset.

## Next-Step Note

The system should remain primarily a structural/oracle interpreter until a stronger causal bottom-proximity approximation is found.

## Output Files

- `out/swing_bottom/causal_bottom_proxy_comparison.csv`
- `out/swing_bottom/causal_bottom_proxy_membership.csv`
