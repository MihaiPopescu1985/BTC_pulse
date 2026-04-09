# SAFE v4.0 Swing Distribution

This note summarizes confirmed swings extracted from BTC daily OHLC with a volatility-normalized ZigZag.

Method:
- volatility proxy: ATR percent with `14`-day window
- reversal threshold: `1.50 x ATR%`
- pivots are confirmed only after a reversal threshold breach
- unfinished final leg is not exported as a swing

## Summary

- swings extracted: `549`
- up swings: `274`
- down swings: `275`
- median absolute amplitude: `12.23%`
- median duration: `4` days
- amplitude-duration Spearman: `0.429`

## Amplitude Distribution

- `0-5%`: `27`
- `5-10%`: `176`
- `10-20%`: `214`
- `20-30%`: `76`
- `30%+`: `56`

## Duration Distribution

- `0-6d`: `372`
- `7-13d`: `139`
- `14-29d`: `36`
- `30-59d`: `2`
- `60d+`: `0`

## Joint Stats

- up-swing median amplitude: `13.60%`
- down-swing median amplitude: `-10.88%`
- up-swing median duration: `5` days
- down-swing median duration: `4` days

Interpretation:
- this is a structural market description layer, not a trading rule
- larger reversals are intentionally filtered out until they exceed the ATR-normalized reversal threshold
- changing `k` or the ATR window will change the swing granularity
