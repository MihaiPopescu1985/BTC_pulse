# SAFE v4.0 Entry Logic Research

Chosen swing granularity: `medium_atr10_k1.5`
- ATR window: `10`
- reversal multiplier: `1.50`

This is a small research-stage entry pass. It does not define a full strategy or any exits.

Important alignment rule:
- this pass uses strict `next swing` semantics
- because of that, long-entry templates are filtered toward live legs that are still in a reversal window (`down` or `unknown`), not already-established upswings

## Section 1 — Tested Entry Templates

- `entry_pullback_reversal_window` (filtered_entry): next up `100.00%` | next down `0.00%` | ret_10d mean `-2.36%` | n=`4`
- `entry_bearish_contrarian_not_late` (filtered_entry): next up `61.54%` | next down `38.46%` | ret_10d mean `3.21%` | n=`39`
- `entry_stress_rebound_reversal_window` (filtered_entry): next up `nan%` | next down `nan%` | ret_10d mean `nan%` | n=`0`
- `low_risk_pullback` (raw_reference): next up `63.89%` | next down `36.11%` | ret_10d mean `0.02%` | n=`72`
- `shock_whale_risk` (raw_reference): next up `63.54%` | next down `36.46%` | ret_10d mean `-1.12%` | n=`96`
- `bearish_risk_regime` (raw_reference): next up `59.10%` | next down `40.90%` | ret_10d mean `0.10%` | n=`357`
- `upside_probability_stack` (warning_reference): next up `29.41%` | next down `70.59%` | ret_10d mean `5.16%` | n=`85`
- `rebound_skew_low_shock` (warning_reference): next up `29.39%` | next down `70.61%` | ret_10d mean `4.74%` | n=`347`
- `extended_noisy_chase` (warning_reference): next up `27.45%` | next down `72.55%` | ret_10d mean `6.07%` | n=`51`

## Section 2 — Raw Precursor vs Filtered Entry-Template Comparison

- `entry_pullback_reversal_window` vs `low_risk_pullback`: delta next-up `+36.11%`, delta next-down `-36.11%`, delta ret_10d mean `-2.38%`, delta touch_up_2pct_10d `-41.67%`, delta touch_down_2pct_10d `+13.89%`
- `entry_bearish_contrarian_not_late` vs `bearish_risk_regime`: delta next-up `+2.43%`, delta next-down `-2.43%`, delta ret_10d mean `+3.12%`, delta touch_up_2pct_10d `-1.98%`, delta touch_down_2pct_10d `+3.23%`
- `entry_stress_rebound_reversal_window` vs `shock_whale_risk`: delta next-up `+nan%`, delta next-down `+nan%`, delta ret_10d mean `+nan%`, delta touch_up_2pct_10d `+nan%`, delta touch_down_2pct_10d `+nan%`

## Section 3 — Best Long-Entry Research Candidates

- `entry_bearish_contrarian_not_late`: next up `61.54%`, next down `38.46%`, median next swing amplitude `14.71%`, ret_10d mean `3.21%`, n=`39`

## Section 4 — Which Warning States Should Veto Long Entries

- `extended_noisy_chase`: next down `72.55%`, touch_down_2pct_10d `66.67%`, ret_10d mean `6.07%`, n=`51`
- `rebound_skew_low_shock`: next down `70.61%`, touch_down_2pct_10d `82.42%`, ret_10d mean `4.74%`, n=`347`
- `upside_probability_stack`: next down `70.59%`, touch_down_2pct_10d `88.24%`, ret_10d mean `5.16%`, n=`85`

Interpretation note:
- a strong `next down` warning can still show positive `ret_10d` if the current live leg keeps rising before the next confirmed downswing begins
- that is why next-swing direction and fixed-horizon return should be read together, not treated as interchangeable

## Section 5 — Clear Conclusion

- the relevant question is not whether a precursor is good alone, but whether it improves after live swing phase filtering
- `entry_pullback_reversal_window` is too sparse to trust yet: it improved next-up alignment by `+36.11%` but only on `4` rows.
- `entry_bearish_contrarian_not_late` deserves next-step refinement: it improved next-up alignment by `+2.43%` while reducing next-down leakage by `2.43%`.
- `entry_stress_rebound_reversal_window` should be discarded in its current form: the filter stack produced no usable rows.
- warning states remain useful as long-entry vetoes when they preserve high next-down alignment after the live-state split
- this pass supports further refinement of a small entry layer, not a full strategy or execution rule set
