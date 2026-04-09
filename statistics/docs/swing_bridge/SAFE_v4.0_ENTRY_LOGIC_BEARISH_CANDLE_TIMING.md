# SAFE v4.0 Entry Logic Bearish Candle Timing

## Section 1 — Candle-Mechanics Features Tested

- candle geometry:
  - total range
  - body size
  - upper/lower wick size
  - body / wick percentages of range
  - close position in range
- reclaim / recovery mechanics:
  - bullish close
  - close above previous close
  - close above previous high
  - low below previous low but close recovers
  - close back inside previous body range
- very short sequence context:
  - prior 2d return
  - prior 3d return
  - current 1d return
  - 2d / 3d momentum shift flags

## Section 2 — Trigger Variants Tested

- triggers:
  - lower_wick_rejection
  - reclaim_trigger
  - failed_breakdown_recovery
  - momentum_turn
- timing modes:
  - same-day trigger on setup start
  - trigger within days 1-3 after setup start

- `bearish_age0_75_size1_25_with_veto_failed_breakdown_recovery_wait3`: timing rank `-0.045`, next up `55.56%`, ret_10d mean `2.13%`, max_down_10d mean `-12.20%`, hit -2% before +2% `77.78%`, n=`9`
- `bearish_age0_75_size1_25_with_veto_lower_wick_rejection_wait3`: timing rank `-0.075`, next up `57.14%`, ret_10d mean `-1.38%`, max_down_10d mean `-13.90%`, hit -2% before +2% `100.00%`, n=`7`
- `bearish_age0_75_size1_25_with_veto_momentum_turn_wait3`: timing rank `-0.098`, next up `33.33%`, ret_10d mean `2.83%`, max_down_10d mean `-7.12%`, hit -2% before +2% `75.00%`, n=`12`
- `bearish_age0_75_size1_25_with_veto_reclaim_trigger_wait3`: timing rank `-0.155`, next up `41.18%`, ret_10d mean `1.51%`, max_down_10d mean `-8.04%`, hit -2% before +2% `82.35%`, n=`17`

## Section 3 — Best Trigger Variants vs Setup-Zone Baseline

- `bearish_age0_75_size1_25_with_veto_failed_breakdown_recovery_wait3` vs setup baseline: delta next-up `-35.75%`, delta ret_10d mean `+1.85%`, delta max_down_10d mean `+0.01%`, delta touch_down `+4.35%`, delta hit -2% before +2% `-0.48%`
- `bearish_age0_75_size1_25_with_veto_lower_wick_rejection_wait3` vs setup baseline: delta next-up `-34.16%`, delta ret_10d mean `-1.66%`, delta max_down_10d mean `-1.69%`, delta touch_down `+4.35%`, delta hit -2% before +2% `+21.74%`
- `bearish_age0_75_size1_25_with_veto_momentum_turn_wait3` vs setup baseline: delta next-up `-57.97%`, delta ret_10d mean `+2.55%`, delta max_down_10d mean `+5.09%`, delta touch_down `+4.35%`, delta hit -2% before +2% `-3.26%`

## Section 4 — Whether Candle Timing Improves Entry Quality

- No trigger clearly improved both return quality and early-pain metrics versus the setup-zone baseline.
- `bearish_age0_75_size1_25_with_veto_failed_breakdown_recovery_wait3` does not justify itself yet: delta ret_10d `+1.85%`, delta max_down `+0.01%`, delta hit -2% before +2% `-0.48%`.
- `bearish_age0_75_size1_25_with_veto_lower_wick_rejection_wait3` does not justify itself yet: delta ret_10d `-1.66%`, delta max_down `-1.69%`, delta hit -2% before +2% `+21.74%`.
- `bearish_age0_75_size1_25_with_veto_momentum_turn_wait3` does not justify itself yet: delta ret_10d `+2.55%`, delta max_down `+5.09%`, delta hit -2% before +2% `-3.26%`.
- `bearish_age0_75_size1_25_with_veto_reclaim_trigger_wait3` does not justify itself yet: delta ret_10d `+1.23%`, delta max_down `+4.17%`, delta hit -2% before +2% `+4.09%`.

## Section 5 — Clear Conclusion

- Best current trigger: `bearish_age0_75_size1_25_with_veto_failed_breakdown_recovery_wait3` with n=`9`, next up `55.56%`, ret_10d mean `2.13%`, max_down_10d mean `-12.20%`, hit -2% before +2% `77.78%`.
- Candle mechanics did not yet cleanly solve the early-pain problem without sacrificing too much next-swing alignment. This remains primarily a setup zone, not a robust entry candidate.
