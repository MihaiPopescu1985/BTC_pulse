# SAFE v4.0 Entry Logic Bearish Refinement

## Section 1 — Refinement Grid Tested

- base branch: `bearish_risk_regime` in a live reversal window
- age filters: `<= 0.50`, `<= 0.75`, `<= 1.00` of median swing age
- size filters: `<= 0.75`, `<= 1.00`, `<= 1.25` of median swing size
- warning veto comparison: on/off for the no-confirmation grid
- one-at-a-time confirmations on the current baseline shape:
  - `ONCHAIN_DOM_Z` supportive
  - `P_REBOUND_10D_CAL` upper-half
  - `TS_20` not strongly negative
  - `ER_50` not weak

## Section 2 — Variant Ranking Table

- `bearish_age0_75_size1_25_with_veto`: rank `0.252`, next up `86.21%`, next down `13.79%`, ret_10d mean `0.86%`, touch_up `79.31%`, touch_down `93.10%`, n=`29`
- `bearish_age0_75_size1_25_no_veto`: rank `0.252`, next up `86.21%`, next down `13.79%`, ret_10d mean `0.86%`, touch_up `79.31%`, touch_down `93.10%`, n=`29`
- `bearish_age1_0_size1_25_with_veto`: rank `0.239`, next up `69.23%`, next down `30.77%`, ret_10d mean `2.35%`, touch_up `80.77%`, touch_down `92.31%`, n=`52`
- `bearish_age1_0_size1_25_no_veto`: rank `0.239`, next up `69.23%`, next down `30.77%`, ret_10d mean `2.35%`, touch_up `80.77%`, touch_down `92.31%`, n=`52`
- `bearish_age0_75_size1_0_with_veto`: rank `0.159`, next up `84.21%`, next down `15.79%`, ret_10d mean `2.38%`, touch_up `84.21%`, touch_down `94.74%`, n=`19`
- `bearish_age0_75_size1_0_no_veto`: rank `0.159`, next up `84.21%`, next down `15.79%`, ret_10d mean `2.38%`, touch_up `84.21%`, touch_down `94.74%`, n=`19`
- `bearish_age0_5_size1_25_with_veto`: rank `0.123`, next up `81.25%`, next down `18.75%`, ret_10d mean `0.63%`, touch_up `87.50%`, touch_down `93.75%`, n=`16`
- `bearish_age0_5_size1_25_no_veto`: rank `0.123`, next up `81.25%`, next down `18.75%`, ret_10d mean `0.63%`, touch_up `87.50%`, touch_down `93.75%`, n=`16`

## Section 3 — Best Variants vs Baseline

- `bearish_age0_75_size1_25_with_veto` vs raw: delta next-up `+27.10%`, delta next-down `-27.10%`, delta ret_10d mean `+0.77%`
- `bearish_age0_75_size1_25_with_veto` vs current filtered: delta next-up `+24.67%`, delta next-down `-24.67%`, delta ret_10d mean `-2.35%`
- `bearish_age0_75_size1_25_no_veto` vs raw: delta next-up `+27.10%`, delta next-down `-27.10%`, delta ret_10d mean `+0.77%`
- `bearish_age0_75_size1_25_no_veto` vs current filtered: delta next-up `+24.67%`, delta next-down `-24.67%`, delta ret_10d mean `-2.35%`
- `bearish_age1_0_size1_25_with_veto` vs raw: delta next-up `+10.13%`, delta next-down `-10.13%`, delta ret_10d mean `+2.26%`
- `bearish_age1_0_size1_25_with_veto` vs current filtered: delta next-up `+7.69%`, delta next-down `-7.69%`, delta ret_10d mean `-0.86%`

## Section 4 — Which Refinements Help, Which Do Not

- `bearish_age0_5_size0_75_with_veto` is too sparse to trust: n=`8`, next up `75.00%`.
- `bearish_age0_5_size0_75_no_veto` is too sparse to trust: n=`8`, next up `75.00%`.
- `bearish_age0_75_size1_25_with_veto` helps: it improved next-up purity by `+24.67%` and reduced next-down leakage by `24.67%`.
- `bearish_age0_75_size1_25_no_veto` helps: it improved next-up purity by `+24.67%` and reduced next-down leakage by `24.67%`.
- `bearish_age1_0_size1_25_with_veto` helps: it improved next-up purity by `+7.69%` and reduced next-down leakage by `7.69%`.
- `bearish_age1_0_size1_25_no_veto` helps: it improved next-up purity by `+7.69%` and reduced next-down leakage by `7.69%`.
- `bearish_age0_75_size1_0_with_veto` helps: it improved next-up purity by `+22.67%` and reduced next-down leakage by `22.67%`.
- `bearish_age1_0_size1_0_with_veto` does not clearly help: delta next-up `+0.00%`, delta next-down `+0.00%`.
- `bearish_age1_0_size1_0_no_veto` does not clearly help: delta next-up `+0.00%`, delta next-down `+0.00%`.
- `bearish_baseline_with_veto_rebound_upper_half` does not clearly help: delta next-up `-0.43%`, delta next-down `+0.43%`.
- `bearish_baseline_with_veto_onchain_dom_supportive` does not clearly help: delta next-up `-3.85%`, delta next-down `+3.85%`.
- `bearish_age1_0_size0_75_with_veto` does not clearly help: delta next-up `-6.54%`, delta next-down `+6.54%`.

## Section 5 — Clear Conclusion

- Best current candidate: `bearish_age0_75_size1_25_with_veto` with next up `86.21%`, next down `13.79%`, ret_10d mean `0.86%`, n=`29`.
- This bearish-contrarian branch should remain alive for one more focused research step.
- Variants that improve purity only by collapsing sample size should not be promoted.
