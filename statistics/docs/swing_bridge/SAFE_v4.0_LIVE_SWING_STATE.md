# SAFE v4.0 Live Swing State

Chosen swing granularity: `medium_atr10_k1.5`
- ATR window: `10`
- reversal multiplier: `1.50`

This table is causal. Each daily row uses only pivots that would already have been confirmed by that date.

Fields:
- `live_swing_direction`: current open leg direction (`up`, `down`, `unknown`)
- `days_since_last_pivot`: calendar days since the last confirmed pivot
- `distance_from_last_pivot_pct`: close relative to the last confirmed pivot price
- `distance_from_last_pivot_atr_units`: same distance measured in current ATR units
- `current_swing_confirmed`: false for the live leg by construction; the active leg is still open
- `swing_confirmed_today`: true on days when a prior leg becomes a confirmed swing and a new live leg begins

## Latest Snapshot

- date: `2026-04-02`
- live_swing_direction: `up`
- days_since_last_pivot: `4`
- distance_from_last_pivot_pct: `3.11%`
- distance_from_last_pivot_atr_units: `0.84`
- last_confirmed_pivot_date: `2026-03-29`
