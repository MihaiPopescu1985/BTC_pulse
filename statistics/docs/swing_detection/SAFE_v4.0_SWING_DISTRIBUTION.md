# SAFE v4.0 Swing Distribution

This note summarizes confirmed swings extracted from BTC daily OHLC with a volatility-normalized ZigZag.

Method:
- volatility proxy: ATR percent with `14`-day window
- reversal threshold: `1.50 x ATR%`
- pivots are confirmed only after a reversal threshold breach
- unfinished final leg is not exported as a swing

## Summary

- swings extracted: `590`
- up swings: `295`
- down swings: `295`
- median absolute amplitude: `11.69%`
- median duration: `4` days
- amplitude-duration Spearman: `0.428`

## Amplitude Distribution

- `0-5%`: `38`
- `5-10%`: `196`
- `10-20%`: `220`
- `20-30%`: `79`
- `30%+`: `57`

## Duration Distribution

- `0-6d`: `399`
- `7-13d`: `150`
- `14-29d`: `38`
- `30-59d`: `3`
- `60d+`: `0`

## Joint Stats

- up-swing median amplitude: `12.95%`
- down-swing median amplitude: `-10.64%`
- up-swing median duration: `5` days
- down-swing median duration: `4` days

Interpretation:
- this is a structural market description layer, not a trading rule
- larger reversals are intentionally filtered out until they exceed the ATR-normalized reversal threshold
- changing `k` or the ATR window will change the swing granularity
