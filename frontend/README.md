# Charts Dev

This is a small static dashboard for rendering ECharts charts from Jekyll data.

## Structure
- `assets/scripts/dashboard.js` renders charts and handles navigation.
- `assets/scripts/chart-utils.js` holds shared helpers.
- `assets/scripts/charts/*.js` defines each chart (options + data mapping).
- `_data/*.json` contains chart data. These are **copies**, see Chart Data below.
- `sync_data.py` refreshes those copies from the statistics artifacts.

## Add a new chart
1) Add a data file to `_data`, for example `_data/daily_new.json`.
2) Register the data in `assets/scripts/dashboard.js`:
```js
const dataFiles = {
  // ...
  dailyNew: {{ site.data.daily_new | jsonify }}
};
```
3) Create a chart file in `assets/scripts/charts/`, for example `assets/scripts/charts/daily_new.js`:
```js
---
layout: null
---
(function (global) {
    'use strict';

    const baseOption = {
        // ECharts options here
        series: []
    };

    function buildOption(rawData) {
        const option = global.ChartUtils.clone(baseOption);
        // Map rawData into option
        return option;
    }

    global.chartRegistry = global.chartRegistry || {};
    global.chartRegistry.dailyNew = {
        buildOption: buildOption
    };
})(window);
```
4) Add the script tag in `index.md` (before `dashboard.js`):
```html
<script src="{{ site.baseurl }}/assets/scripts/charts/daily_new.js"></script>
```
5) Add a navigation button in `index.md`:
```html
<button class="nav-btn" data-key="dailyNew">Daily New</button>
```

## Notes
- Keep chart-specific logic in the chart file.
- Keep shared helpers in `assets/scripts/chart-utils.js`.
- `dashboard.js` should remain generic (no chart-specific logic).

## Chart Data

`_data/*.json` is a committed copy, not a live view. The retrieval pipeline
(`statistics/src/data/query.py`) writes only into `statistics/data`, and nothing
propagates from there to here on its own, so the charts render whatever copy was
synced last. Refresh them from the repository root with:

```
.venv/bin/python frontend/sync_data.py
```

`Frontend - serve` in `simple-runner.yml` runs this first, so serving cannot show
a stale chart; `Frontend - synchronize chart data` runs it on its own, which is
what you want before committing the refreshed data.

What the script produces:

| `_data` file | Source | How |
| --- | --- | --- |
| `daily_amounts.json` | `statistics/data/daily_amounts.json` | copied verbatim |
| `daily_price.json` | `statistics/data/daily_price.json` | copied verbatim |
| `daily_tx_size.json` | `statistics/data/daily_tx_size.json` | copied verbatim |
| `features.json` | `statistics/out/features.csv` | converted to `{dates, series, meta}` |
| `onchain_features.json` | `statistics/out/onchain_features.csv` | converted to `{dates, series, meta}` |
| `last_update.json` | — | current UTC timestamp |

The two converted files carry a `meta.hmm.labels_by_state` array that
`charts/daily_safe.js` uses to name the four regime bands. That mapping changes
whenever the HMM is retrained, so it is exported from `out/models/hmm_pack.joblib`
rather than hardcoded; without it the chart falls back to `R0`..`R3`.

If an input is missing the script lists it and exits non-zero, rather than
writing a half-updated `_data`.

## Build & Run
```
# https://jekyllrb.com/docs/installation/
apt-get install ruby-full build-essential
gem install jekyll bundler

bundle install
bundle exec jekyll serve
```
