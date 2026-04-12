# SAFE v4.0 Bottom Dataset

## Swing Granularity

- label: `medium_atr10_k1.5`
- ATR window: `10`
- reversal multiplier: `1.50`

## Dataset Summary

- daily rows: `3158`
- date range: `2017-08-17` -> `2026-04-09`
- rows inside confirmed down swings: `1442`

## Bottom Label Prevalence

- `bottom_zone_time_20pct`: `14.12%`
- `bottom_zone_time_10pct`: `9.72%`
- `bottom_zone_range_20pct`: `6.87%`
- `bottom_zone_range_10pct`: `1.36%`
- `near_current_swing_low_2pct`: `5.29%`
- `near_current_swing_low_3pct`: `10.77%`

## Future Bottom Geometry

- days_to_next_down_swing_low median: `6.0`
- days_to_next_down_swing_low q25 / q75: `3.0` / `11.0`
- dist_to_next_down_swing_low_pct median: `-6.42%`
- dist_to_next_down_swing_low_pct q25 / q75: `-12.12%` / `-3.44%`

## Interpretation

- feature columns remain causal daily state descriptors
- swing-bottom labels are future-derived targets for later supervised modeling
- rows outside confirmed down swings keep the binary bottom-zone labels at `0`, while down-swing progress fields stay `NaN`
- `next_down_swing_*` labels are only defined when a future confirmed down-swing low is at or below the current close
