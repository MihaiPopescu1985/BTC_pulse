# ECharts UI - Schema-Driven Visual Editor

A React + TypeScript + Vite app for editing Apache ECharts options through a typed schema-driven UI, with live preview.

## Supported Chart Families

- line
- bar
- pie
- candlestick
- scatter
- effectScatter
- radar
- heatmap
- funnel
- gauge
- parallel
- polar
- calendar (heatmap coordinate system)
- geo (scatter/effectScatter coordinate system)
- singleAxis (scatter/effectScatter coordinate system family)
- map (scaffolded v1)

## Current V1 Feature Set

- Two-column layout:
  - Left: editor cards (templates/wizard, dataset editor, property editor, validation, export/share)
  - Right: live ECharts preview
- One canonical ECharts `option` object in local React state
- Schema-driven property editor with:
  - conditional visibility by chart type
  - Basic / Advanced / Expert modes
  - help text and per-field reset to default
  - section/field search
  - expanded practical title/subtitle coverage (layout offsets, box styling, richer text/subtext typography, and clickable links/targets)
  - expanded practical axisPointer coverage (trigger/snap/status/handle controls, label polish, and type-specific line/cross/shadow styling)
  - expanded practical brush coverage (brush type/link/mode/throttling plus in/out selection alpha controls)
  - expanded practical coverage for tooltip and legend behavior/styling (trigger, formatters, axis pointer, ordering, icon/layout/text/box style)
  - expanded practical axis presentation/styling coverage for `xAxis`/`yAxis`/`angleAxis`/`radiusAxis` (axisLabel, axisLine, axisTick, splitLine)
  - expanded practical series annotation coverage for `markLine` / `markPoint` / `markArea` (label/style controls plus JSON data editors)
  - expanded practical common series styling/state coverage (label text style/distance, itemStyle, shared line/area style, emphasis/blur/select states, z-order/animation basics)
  - expanded practical dataZoom coverage (range/axis targeting/interaction plus slider styling options like handle, shadow, labels, formatter)
  - expanded practical grid coverage (layout bounds, explicit width/height, containLabel, and frame/shadow styling)
  - expanded practical toolbox coverage (visibility/layout/icon styling and common feature configuration for save image/data view/magic type/data zoom/restore)
  - expanded practical visualMap coverage (continuous/piecewise controls, in/out-of-range mapping, layout/text styling, and series/dimension targeting)
- Multi-instance editing for major array components (`series`, `xAxis`, `yAxis`, `grid`, `visualMap`, `dataZoom`, `title`, `dataset`, `radar`)
- Multi-instance editing for coordinate-system components (`polar`, `angleAxis`, `radiusAxis`, `singleAxis`, `parallel`, `parallelAxis`, `calendar`, `geo`)
- Dataset table editor with CSV/TSV paste and JSON fallback
- Data Suggestions (inference) with one-click apply
- Validation panel with advisory messages + one-click fixes
- Autosave/restore (`localStorage`), share URL state, JSON import/export, PNG/SVG export
- Templates + “Start from goal” wizard

## Templates Included

- Trend over time
- Category comparison
- Part-to-whole
- Two-series comparison
- Price over time (candlestick)
- Relationship between two measures (scatter)
- Relationship between two measures (effect scatter)
- Multi-metric comparison (radar)
- Matrix/category intensity (heatmap)
- Staged conversion (funnel)
- KPI/progress gauge
- Polar bar / Polar line
- Calendar heatmap
- Parallel coordinates
- Geo scatter / Geo effect scatter
- Map choropleth (lite scaffold)

## Setup

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## Tests

```bash
npm test
```

## Practical Limitations (Current Scope)

- The editor prioritizes common/high-value options; it does not cover every ECharts field yet.
- Some complex nested structures use JSON fallback editors by design.
- Dataset inference uses lightweight heuristics; suggestions are advisory and not auto-applied.
- Heatmap matrix-vs-triplet interpretation may need manual adjustment for edge datasets.
- Gauge/funnel/radar defaults are practical starters, not domain-specific “best” configs.
- `map` support is intentionally lightweight in this batch:
  - a built-in `world-lite` map scaffold is registered for no-backend usage
  - full production map workflows (external topojson/geojson packs, region-name reconciliation, large map libraries) are not fully modeled yet
- Single-axis support is currently focused on coordinate-system editing with scatter/effectScatter; a full theme-river editor flow is out of scope for this batch.

## Project Structure (High Level)

```text
src/
  components/        # UI cards and editor components
  schema/            # modular schema definitions (common/axis/series/helpers)
  templates/         # chart templates + goal wizard mappings
  types/             # editor and ECharts types
  utils/             # path updates, dataset, inference, validation, persistence, share, export helpers
  App.tsx            # app composition + canonical state management
```
