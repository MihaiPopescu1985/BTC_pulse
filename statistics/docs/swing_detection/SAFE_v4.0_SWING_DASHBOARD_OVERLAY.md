# SAFE v4.0 Swing Dashboard Overlay

This adds an optional swing overlay to the SAFE dashboard candlestick chart.

Files:

- dashboard:
  - [dashboard.html](/home/mihai/Documents/BTC_pulse/statistics/viewer/dashboard.html)
- swing input:
- [swings.csv](/home/mihai/Documents/BTC_pulse/statistics/out/swing_detection/swings.csv)

## What Was Added

- default optional load of `../out/swing_detection/swings.csv` when SAFE data is loaded
- sidebar toggle:
  - `Show swings overlay`
- optional sidebar toggle:
  - `Show pivot markers`
- overlay rendering on top of the OHLC candlestick chart only

The raw-data tab is unchanged.

## Pivot Price Mapping

`swings.csv` stores only dates and swing direction, so the overlay recovers y-values from the loaded OHLC series:

- up swing:
  - `start_date -> low`
  - `end_date -> high`
- down swing:
  - `start_date -> high`
  - `end_date -> low`

This mapping is deterministic and uses the same OHLC data already shown on the chart.

## Display Rules

The swing overlay appears only when:

- the SAFE tab is active
- `Candlestick (OHLC)` is selected
- `swings.csv` loaded successfully
- `Show swings overlay` is enabled

If `swings.csv` is missing, the dashboard still works normally without the overlay.

## Visual Treatment

- up swings: green pivot-to-pivot line segments
- down swings: red pivot-to-pivot line segments
- optional pivot markers:
  - green circles for up-swing pivots
  - red diamonds for down-swing pivots

The overlay is meant for structural inspection, not for dense annotation.

## Known Limitations

- pivot prices are reconstructed from daily OHLC, not from stored pivot prices
- the overlay reflects confirmed swings from the exported `swings.csv`, not unfinished current legs
- on crowded date ranges, pivot markers can add clutter, so they are optional
