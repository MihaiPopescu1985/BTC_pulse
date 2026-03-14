# Charts Dev

This is a small static dashboard for rendering ECharts charts from Jekyll data.

## Structure
- `assets/scripts/dashboard.js` renders charts and handles navigation.
- `assets/scripts/chart-utils.js` holds shared helpers.
- `assets/scripts/charts/*.js` defines each chart (options + data mapping).
- `_data/*.json` contains chart data.

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
