# SAFE v4.0 Entry Logic Low Risk Base

## Section 1 — Why This Branch Is Being Treated As An Execution-Quality Candidate

- `low_risk_base` is not being treated as a next-swing-purity branch in this pass
- the purpose here is execution quality: lower downside pain, acceptable upside participation, and enough sample size to matter
- all variants are compared directly against raw `low_risk_base`

## Section 2 — Timing / Filter Variants Tested

- baseline: `raw_low_risk_base`
- favorable position thresholds: `band_pos <= 0.710`, `dist_from_mean_vol_units <= 0.075`
- volatility sanity thresholds: `atr_pct <= 0.0329`, `ewma_vol <= 0.0214`, `downside_semi_vol <= 0.0141`
- short-trend confirmation threshold: `TS_20 >= -0.0126`
- mild confirmation means `close > prior close`

## Section 3 — Variant Comparison Vs Raw `low_risk_base`

| Variant | n | ret_10d mean | max_up_10d | max_down_10d | touch_up | touch_down | -2% before +2% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `low_risk_base_position_favorable` | 101 | 1.93% | 6.57% | -5.31% | 72.28% | 69.31% | 54.46% |
| `low_risk_base_position_favorable_confirm` | 58 | 2.55% | 6.93% | -5.10% | 72.41% | 67.24% | 53.45% |
| `low_risk_base_volatility_sanity` | 134 | 2.22% | 7.08% | -4.83% | 67.91% | 64.18% | 52.99% |
| `low_risk_base_volatility_sanity_confirm` | 81 | 3.09% | 7.77% | -4.48% | 71.60% | 60.49% | 50.62% |
| `low_risk_base_volatility_sanity_ts20_confirm` | 71 | 5.04% | 10.07% | -4.46% | 71.83% | 52.11% | 42.25% |
| `raw_low_risk_base` | 209 | 2.07% | 6.71% | -4.69% | 73.21% | 68.42% | 53.59% |

## Section 4 — Which Variants Improve Path Quality And Which Do Not

- raw baseline: ret_10d mean `2.07%`, max_down_10d `-4.69%`, touch_down_2pct_10d `68.42%`, `-2% before +2%` `53.59%`
- best current variant: `low_risk_base_volatility_sanity_ts20_confirm` with ret_10d mean `5.04%`, max_down_10d `-4.46%`, touch_down_2pct_10d `52.11%`, `-2% before +2%` `42.25%`, n=`71`

- `low_risk_base_volatility_sanity_confirm`: delta ret_10d `1.02%`, delta max_down `0.21%`, delta touch_down `-7.93%`, delta `-2% before +2%` `-2.97%`, n=`81`
- `low_risk_base_volatility_sanity`: delta ret_10d `0.14%`, delta max_down `-0.14%`, delta touch_down `-4.24%`, delta `-2% before +2%` `-0.60%`, n=`134`
- `low_risk_base_position_favorable_confirm`: delta ret_10d `0.47%`, delta max_down `-0.41%`, delta touch_down `-1.18%`, delta `-2% before +2%` `-0.14%`, n=`58`
- `low_risk_base_position_favorable`: delta ret_10d `-0.15%`, delta max_down `-0.62%`, delta touch_down `0.89%`, delta `-2% before +2%` `0.87%`, n=`101`

## Section 5 — Clear Conclusion

- yes, this branch supports a plausible entry candidate: `low_risk_base_volatility_sanity_ts20_confirm` is materially cleaner than raw `low_risk_base` without collapsing the sample.
- best variant in this pass: `low_risk_base_volatility_sanity_ts20_confirm`
- operationally, this branch remains worth refining because it starts from a materially safer path profile than the bearish watchlist branch.
