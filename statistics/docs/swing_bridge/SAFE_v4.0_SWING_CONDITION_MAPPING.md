# SAFE v4.0 Swing Condition Mapping

Chosen swing granularity: `medium_atr10_k1.5`
- ATR window: `10`
- reversal multiplier: `1.50`

This report separates two different swing-mapping questions:

- `containing` mapping: which confirmed swing currently contains the date
- `next` mapping: which confirmed swing starts strictly after the date

Why the split matters:
- containing-swing analysis is descriptive of current swing maturity
- next-swing analysis is the predictive bridge to what swing comes next

## Containing-Swing Analysis

These rows describe where a condition tends to appear inside the swing that currently contains the date.

### Which Conditions Align With Early Up-Swing Stages?

- `shock_whale_risk`: early-in-up rate `39.29%`, current up-swing rate `29.17%`, n=`96`
- `bearish_risk_regime`: early-in-up rate `32.54%`, current up-swing rate `35.29%`, n=`357`
- `extended_noisy_chase`: early-in-up rate `30.77%`, current up-swing rate `76.47%`, n=`51`
- `weak_mixed_high_noise`: early-in-up rate `28.07%`, current up-swing rate `64.77%`, n=`88`
- `low_risk_base`: early-in-up rate `27.50%`, current up-swing rate `57.42%`, n=`209`

### Which Conditions Align With Mid Up-Swing Stages?

- `weak_mixed_high_noise`: mid-in-up rate `42.11%`, current up-swing rate `64.77%`, n=`88`
- `low_risk_pullback`: mid-in-up rate `35.71%`, current up-swing rate `38.89%`, n=`72`
- `low_risk_base`: mid-in-up rate `34.17%`, current up-swing rate `57.42%`, n=`209`
- `extended_noisy_chase`: mid-in-up rate `33.33%`, current up-swing rate `76.47%`, n=`51`
- `bearish_risk_regime`: mid-in-up rate `33.33%`, current up-swing rate `35.29%`, n=`357`

### Which Conditions Align With Late Up-Swing Stages?

- `expansion_with_participation`: late-in-up rate `66.67%`, current up-swing rate `73.47%`, n=`49`
- `upside_probability_stack`: late-in-up rate `60.29%`, current up-swing rate `80.00%`, n=`85`
- `rebound_skew_low_shock`: late-in-up rate `51.11%`, current up-swing rate `77.81%`, n=`347`
- `structural_onchain_tailwind`: late-in-up rate `50.00%`, current up-swing rate `69.66%`, n=`89`
- `trend_backdrop_constructive`: late-in-up rate `43.88%`, current up-swing rate `67.03%`, n=`731`

## Next-Swing Analysis


These rows ask what confirmed swing most often starts after a date where the condition is active.


### Which Conditions Most Often Precede The Next Upward Swing?

- `low_risk_pullback`: next up-swing rate `63.89%`, median amplitude `9.35%`, median duration `4`d, n=`72`
- `shock_whale_risk`: next up-swing rate `63.54%`, median amplitude `19.87%`, median duration `4`d, n=`96`
- `bearish_risk_regime`: next up-swing rate `59.10%`, median amplitude `16.75%`, median duration `4`d, n=`357`
- `low_risk_base`: next up-swing rate `46.41%`, median amplitude `7.87%`, median duration `4`d, n=`209`
- `onchain_dominance_support`: next up-swing rate `45.14%`, median amplitude `14.59%`, median duration `4`d, n=`669`

### Which Conditions Most Often Precede The Next Downward Swing?

- `extended_noisy_chase`: next down-swing rate `72.55%`, median amplitude `12.88%`, median duration `3`d, n=`51`
- `rebound_skew_low_shock`: next down-swing rate `70.61%`, median amplitude `14.65%`, median duration `4`d, n=`347`
- `upside_probability_stack`: next down-swing rate `70.59%`, median amplitude `17.62%`, median duration `3`d, n=`85`
- `structural_onchain_tailwind`: next down-swing rate `69.66%`, median amplitude `18.09%`, median duration `4`d, n=`89`
- `trend_backdrop_constructive`: next down-swing rate `64.57%`, median amplitude `11.28%`, median duration `4`d, n=`731`

### Which Conditions Mainly Describe Current Swing Maturity Rather Than Predict The Next Swing?

- `expansion_with_participation`: strongest containing up-stage signal is `late`, but next-swing direction gap is only 26.53%, n=`49`
- `low_risk_base`: strongest containing up-stage signal is `late`, but next-swing direction gap is only 7.18%, n=`209`
- `onchain_dominance_support`: strongest containing up-stage signal is `late`, but next-swing direction gap is only 9.72%, n=`669`
- `upside_probability_stack`: strongest containing up-stage signal is `late`, but next-swing direction gap is only 41.18%, n=`85`
- `weak_mixed_high_noise`: strongest containing up-stage signal is `mid`, but next-swing direction gap is only 25.00%, n=`88`

### Which Conditions Mostly Describe Movement Without Directional Clarity?

- `low_risk_base`: next up `46.41%`, next down `53.59%`, large swing rate `11.96%`, n=`209`
- `onchain_dominance_support`: next up `45.14%`, next down `54.86%`, large swing rate `39.46%`, n=`669`
- `bearish_risk_regime`: next up `59.10%`, next down `40.90%`, large swing rate `50.14%`, n=`357`
- `weak_mixed_high_noise`: next up `37.50%`, next down `62.50%`, large swing rate `43.18%`, n=`88`
- `expansion_with_participation`: next up `36.73%`, next down `63.27%`, large swing rate `83.67%`, n=`49`

## Large-Swing Alignment

- `expansion_with_participation`: next large-swing rate `83.67%`, up `36.73%`, down `63.27%`, n=`49`
- `shock_whale_risk`: next large-swing rate `69.79%`, up `63.54%`, down `36.46%`, n=`96`
- `structural_onchain_tailwind`: next large-swing rate `68.54%`, up `30.34%`, down `69.66%`, n=`89`
- `upside_probability_stack`: next large-swing rate `60.00%`, up `29.41%`, down `70.59%`, n=`85`
- `bearish_risk_regime`: next large-swing rate `50.14%`, up `59.10%`, down `40.90%`, n=`357`

## What This Bridge Says

- containing-swing and next-swing results must be read separately
- some conditions are mainly descriptive of current swing maturity
- some conditions align cleanly with next-swing direction
- others mainly describe movement intensity or fragile regimes without clear next-swing direction
- this is the first bridge layer from indicator conditions to market-defined swings, not a final trading rule set
