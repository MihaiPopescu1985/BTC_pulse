# SAFE v4.0 Reversal Zone Dataset

## Swing Granularity

- label: `medium_atr10_k1.5`
- ATR window: `10`
- reversal multiplier: `1.50`

## Dataset Summary

- rows: `3158`
- date range: `2017-08-17` -> `2026-04-09`
- rows in confirmed down swings: `1442`
- rows in confirmed up swings: `1696`

## Label Families

### Range-Based Labels

- `buy_zone_bottom_10pct_of_range`: current close is inside the lowest 10% of the confirmed down-swing range
- `buy_zone_bottom_5pct_of_range`: current close is inside the lowest 5% of the confirmed down-swing range
- `sell_zone_top_10pct_of_range`: current close is inside the highest 10% of the confirmed up-swing range
- `sell_zone_top_5pct_of_range`: current close is inside the highest 5% of the confirmed up-swing range

### Price-Distance Labels

- `buy_zone_within_5pct_above_low`: current close is within 5% above the confirmed down-swing low
- `buy_zone_within_3pct_above_low`: current close is within 3% above the confirmed down-swing low
- `sell_zone_within_5pct_below_high`: current close is within 5% below the confirmed up-swing high
- `sell_zone_within_3pct_below_high`: current close is within 3% below the confirmed up-swing high

## Label Prevalence

### Range-Based

- `buy_zone_bottom_10pct_of_range`: `1.36%`
- `buy_zone_bottom_5pct_of_range`: `0.28%`
- `sell_zone_top_10pct_of_range`: `3.26%`
- `sell_zone_top_5pct_of_range`: `1.01%`

### Price-Distance

- `buy_zone_within_5pct_above_low`: `18.78%`
- `buy_zone_within_3pct_above_low`: `10.77%`
- `sell_zone_within_5pct_below_high`: `22.29%`
- `sell_zone_within_3pct_below_high`: `13.11%`

## Swing Coverage Sanity

- confirmed down swings: `275`
- confirmed up swings: `275`
- median down-swing duration: `4.0` days
- median up-swing duration: `5.0` days
- median down-swing amplitude: `10.83%`
- median up-swing amplitude: `13.50%`

## Zone Width Read

- range-based and price-distance labels are not directly comparable thresholds
- range-based labels depend on the full confirmed swing amplitude
- price-distance labels depend on absolute distance to the eventual low/high
- use prevalence as the first sanity check for whether a zone family is too sparse or too broad

## Interpretation

- this dataset now contains two distinct reversal-zone label families
- range-based labels are stricter structural zone labels tied to the confirmed swing range
- price-distance labels are more directly aligned with good-enough proximity to the eventual low/high
- future modeling can test which family better captures many usable swings without requiring exact pivot prediction
- causal features remain intact; confirmed-swing zone labels are future-derived supervision only
