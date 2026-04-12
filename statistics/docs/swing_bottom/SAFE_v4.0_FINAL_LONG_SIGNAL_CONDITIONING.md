# SAFE v4.0 Final Long Signal Conditioning

## Purpose

This final narrow pass tests whether stricter conditioning of the already-best long subset can materially clean up forward paths. It does not define execution, entries, exits, stops, position sizing, portfolio logic, PnL, or backtests.

## Variants

- `all_long_signal_new`: all long signal events.
- `long_quality_high`: prior best long-quality bucket.
- `high_strongest_spread`: high-quality events with strongest timing spread.
- `high_lowest_conflict`: high-quality events with lowest conflict.
- `high_closest_to_low`: high-quality events closest to the current down-swing low.
- `high_clean_near_combo`: compact combined clean/strong subset.

## Conditioning Results

| variant | event_count | share_of_all_long_signal_new | mean_return_5d | mean_return_10d | mean_favorable_excursion_10d | mean_adverse_excursion_10d | touch_favorable_2pct_10d_rate | touch_adverse_2pct_10d_rate | favorable_2pct_before_adverse_2pct_10d_rate | adverse_2pct_before_favorable_2pct_10d_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_long_signal_new | 159.000 | 100.0% | 0.5% | 1.3% | 8.9% | -7.9% | 81.1% | 76.7% | 42.1% | 45.3% |
| long_quality_high | 50.000 | 31.4% | 3.1% | 3.2% | 10.5% | -5.5% | 84.0% | 68.0% | 46.0% | 44.0% |
| high_strongest_spread | 17.000 | 10.7% | 2.0% | 1.9% | 8.7% | -6.1% | 76.5% | 76.5% | 29.4% | 70.6% |
| high_lowest_conflict | 17.000 | 10.7% | 2.1% | 2.0% | 10.3% | -7.4% | 70.6% | 76.5% | 35.3% | 58.8% |
| high_closest_to_low | 16.000 | 10.1% | 5.8% | 5.6% | 13.1% | -2.7% | 100.0% | 25.0% | 100.0% | 0.0% |
| high_clean_near_combo | 8.000 | 5.0% | 3.0% | 3.0% | 10.3% | -5.9% | 75.0% | 75.0% | 25.0% | 75.0% |

## Delta Versus `LONG_QUALITY_HIGH`

| variant | event_delta_vs_high | return_10d_delta_vs_high | adverse_excursion_delta_vs_high | favorable_first_delta_vs_high | adverse_first_delta_vs_high |
| --- | --- | --- | --- | --- | --- |
| all_long_signal_new | 109.000 | -0.019 | -0.024 | -0.039 | 0.013 |
| long_quality_high | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| high_strongest_spread | -33.000 | -0.013 | -0.006 | -0.166 | 0.266 |
| high_lowest_conflict | -33.000 | -0.012 | -0.019 | -0.107 | 0.148 |
| high_closest_to_low | -34.000 | 0.024 | 0.028 | 0.540 | -0.440 |
| high_clean_near_combo | -42.000 | -0.002 | -0.004 | -0.210 | 0.310 |

## Final Conclusion

**Continue worth it.** `high_closest_to_low` materially improves return, adverse excursion, and favorable-first ordering with 16 events.

The strongest subset is small, so this does not justify execution logic. It only justifies one future validation-oriented step if the project continues: confirm whether closest-to-low conditioning remains stable outside this sample.

## Cleanup Readiness Note

Current keeper chain for arrangement: swing detection, reversal-zone dataset/models as label foundation, swing extreme timing, buy-side hybrid validation, decision layer, playbook layer, strategy translation layer, calibrated rule layer, signal layer, signal outcomes, long signal refinement, and this final conditioning report.

Exploratory-only candidates for later cleanup: broad buy-side exploration variants, intermediate low-risk/bearish branch artifacts, early uncalibrated rule outputs, and any report whose only purpose was branch selection rather than retained structural interpretation.

No files are deleted in this pass.

## Output Files

- `out/swing_bottom/final_long_signal_conditioning.csv`
- `out/swing_bottom/final_long_signal_conditioning_summary.csv`
