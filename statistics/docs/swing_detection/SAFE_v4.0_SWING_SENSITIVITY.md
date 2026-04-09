# SAFE v4.0 Swing Sensitivity

This note tests whether the ATR-normalized ZigZag swing layer is structurally stable across a small parameter grid.

Grid tested:
- ATR window: `10`, `14`, `20`
- reversal multiplier `k`: `1.00`, `1.25`, `1.50`, `2.00`, `2.50`

## Compact Results

| atr_window | reversal_k | swing_count | median_abs_amplitude | median_duration_days | amplitude_duration_spearman |
| --- | --- | --- | --- | --- | --- |
| 10.0 | 1.00 | 991.0 | 0.0864 | 3.0 | 0.4815 |
| 10.0 | 1.25 | 733.0 | 0.1014 | 3.0 | 0.4426 |
| 10.0 | 1.50 | 550.0 | 0.1188 | 5.0 | 0.4546 |
| 10.0 | 2.00 | 329.0 | 0.1582 | 7.0 | 0.4273 |
| 10.0 | 2.50 | 209.0 | 0.1937 | 11.0 | 0.5048 |
| 14.0 | 1.00 | 977.0 | 0.0876 | 3.0 | 0.4575 |
| 14.0 | 1.25 | 725.0 | 0.1028 | 3.0 | 0.4265 |
| 14.0 | 1.50 | 549.0 | 0.1223 | 4.0 | 0.4285 |
| 14.0 | 2.00 | 338.0 | 0.1641 | 7.0 | 0.4310 |
| 14.0 | 2.50 | 208.0 | 0.2070 | 13.0 | 0.4797 |
| 20.0 | 1.00 | 951.0 | 0.0898 | 3.0 | 0.4454 |
| 20.0 | 1.25 | 737.0 | 0.1012 | 3.0 | 0.4527 |
| 20.0 | 1.50 | 549.0 | 0.1207 | 4.0 | 0.4631 |
| 20.0 | 2.00 | 326.0 | 0.1677 | 7.0 | 0.4942 |
| 20.0 | 2.50 | 208.0 | 0.2049 | 13.0 | 0.4691 |

## What Changed When `k` Changed

- `k=1.00`: swings `951-991`, median amplitude `8.64%-8.98%`, median duration `3-3` days
- `k=1.25`: swings `725-737`, median amplitude `10.12%-10.28%`, median duration `3-3` days
- `k=1.50`: swings `549-550`, median amplitude `11.88%-12.23%`, median duration `4-5` days
- `k=2.00`: swings `326-338`, median amplitude `15.82%-16.77%`, median duration `7-7` days
- `k=2.50`: swings `208-209`, median amplitude `19.37%-20.70%`, median duration `11-13` days

## What Changed When ATR Window Changed

- `ATR 10`: swings `209-991`, median amplitude `8.64%-19.37%`, median duration `3-11` days
- `ATR 14`: swings `208-977`, median amplitude `8.76%-20.70%`, median duration `3-13` days
- `ATR 20`: swings `208-951`, median amplitude `8.98%-20.49%`, median duration `3-13` days

## Stability Readout

- swing count is much more sensitive to `reversal_k` than to ATR window
- `k=1.00`, `ATR 10` is the finest slice here with `991` swings
- `k=2.50`, `ATR 14` is the coarsest slice here with `208` swings
- median amplitude rises as `k` rises, while median duration also tends to lengthen
- ATR window changes the structure, but less dramatically than `k`
- the most stable middle zone is around `k=1.25` to `k=2.00`, where swing count and median structure change gradually rather than collapsing

## Too Fine vs Too Coarse

- too fine: `ATR 10`, `k=1.00` with `991` swings and median duration `3` days
- too coarse: `ATR 14`, `k=2.50` with `208` swings and median duration `13` days

## Recommended Configurations

- fine-grained: `ATR 14`, `k=1.25`
  - swings: `725`
  - median amplitude: `10.28%`
  - median duration: `3` days
- medium-grained: `ATR 10`, `k=1.50`
  - swings: `550`
  - median amplitude: `11.88%`
  - median duration: `5` days

## Final Conclusion

- the swing detector is stable enough for the next phase
- parameter changes do alter granularity, but the structural relationship is orderly rather than chaotic
- `reversal_k` is the main granularity lever
- ATR window matters, but mostly as a secondary smoothing choice
- the detector is therefore usable as a market-structure layer, as long as later work is explicit about whether it wants a fine or medium swing definition
