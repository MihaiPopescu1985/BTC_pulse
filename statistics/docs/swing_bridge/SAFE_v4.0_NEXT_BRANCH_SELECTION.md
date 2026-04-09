# SAFE v4.0 Next Branch Selection

## Section 1 — What Was Learned From The Bearish Branch

- the bearish-contrarian branch improved next-swing purity in some filtered forms
- it failed as a direct-entry branch because path pain remained too high
- candle-timing work did not repair that weakness enough
- it now remains alive only as a watchlist / alert state, not as the active direct-entry branch

## Section 2 — Shortlisted Next Branches

- `low_risk_base` (trend_regime): ret_10d mean `2.07%`, max_up_10d `6.71%`, max_down_10d `-4.69%`, touch_up `73.21%`, touch_down `68.42%`, n=`209`
- `expansion_with_participation` (trend_volatility_participation): ret_10d mean `11.48%`, max_up_10d `19.12%`, max_down_10d `-9.77%`, touch_up `85.71%`, touch_down `91.84%`, n=`49`
- `squeeze_release_up` (trend_position_participation): ret_10d mean `3.08%`, max_up_10d `7.75%`, max_down_10d `-3.98%`, touch_up `85.71%`, touch_down `69.39%`, n=`49`
- `structural_onchain_tailwind` (trend_regime_onchain): ret_10d mean `4.70%`, max_up_10d `14.54%`, max_down_10d `-9.27%`, touch_up `85.39%`, touch_down `84.27%`, n=`89`
- `clean_breakout_continuation` (trend_volatility): ret_10d mean `15.92%`, max_up_10d `21.56%`, max_down_10d `-2.64%`, touch_up `100.00%`, touch_down `40.00%`, n=`5`

## Section 3 — Branch Suitability Comparison

| Branch | Directional alignment | Practical profile | Path quality | Sample viability | Role fit |
| --- | --- | --- | --- | --- | --- |
| `low_risk_base` | next up 46.41% / next down 53.59% | ret_10d 2.07%, max_up 6.71% | max_down -4.69%, tdn 68.42% | 209 | `direct_entry_candidate` |
| `expansion_with_participation` | next up 36.73% / next down 63.27% | ret_10d 11.48%, max_up 19.12% | max_down -9.77%, tdn 91.84% | 49 | `context_only` |
| `squeeze_release_up` | swing evidence incomplete | ret_10d 3.08%, max_up 7.75% | max_down -3.98%, tdn 69.39% | 49 | `direct_entry_candidate` |
| `structural_onchain_tailwind` | next up 30.34% / next down 69.66% | ret_10d 4.70%, max_up 14.54% | max_down -9.27%, tdn 84.27% | 89 | `context_only` |
| `clean_breakout_continuation` | swing evidence incomplete | ret_10d 15.92%, max_up 21.56% | max_down -2.64%, tdn 40.00% | 5 | `direct_entry_candidate_but_too_sparse` |

## Section 4 — Recommended Next Active Branch

- recommended branch: `low_risk_base`
- reason: it offers the best balance of usable sample, positive forward profile, and materially lower path pain than the bearish watchlist branch
- key numbers: ret_10d mean `2.07%`, max_up_10d `6.71%`, max_down_10d `-4.69%`, touch_up `73.21%`, touch_down `68.42%`, n=`209`
- interpretation: this branch is less exciting on raw next-swing purity than the bearish branch, but it is more likely to support an entry-timing pass because it starts from a safer path profile

## Section 5 — Role Assignment Summary

- direct-entry candidate: `low_risk_base`
- warning / veto only: `upside_probability_stack` (next down 70.59%, touch_down_2pct_10d 88.24%, touch_up_2pct_10d 83.53%)
- watchlist / context only: `bearish_age0_75_size1_25_with_veto` (watchlist next up 91.30%, touch_up_2pct_5d 69.57%, touch_down_2pct_10d 95.65%)

Final decision:
- the next direct-entry research pass should move to `low_risk_base`
- `upside_probability_stack` should remain a warning / veto branch
- `bearish_age0_75_size1_25_with_veto` should remain a watchlist / alert branch
