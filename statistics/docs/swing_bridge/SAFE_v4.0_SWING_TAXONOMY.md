# SAFE v4.0 Swing Taxonomy

Chosen swing granularity: `medium_atr10_k1.5`
- ATR window: `10`
- reversal multiplier: `1.50`

Taxonomy method:
- size classes use absolute swing amplitude quantiles
- duration classes use swing duration quantiles
- quantile splits are `q33` and `q67`

## Thresholds

- size q33: `8.79%`
- size q67: `15.89%`
- duration q33: `3.0` days
- duration q67: `7.0` days

## Counts

- total swings: `591`
- small / medium / large: `197` / `197` / `197`
- short / medium / long: `215` / `226` / `150`

Interpretation:
- this taxonomy is market-defined from confirmed swings, not from arbitrary fixed thresholds
- size and duration are separated so later condition mapping can distinguish fast small moves from slower large moves
