import { describe, expect, it } from 'vitest';
import type { EditorContext } from '../types/editor';
import type { EditorOption } from '../types/echarts';
import { validateOption } from './validation';

const buildContext = (
  option: EditorOption,
  chartType:
    | 'line'
    | 'bar'
    | 'pie'
    | 'candlestick'
    | 'scatter'
    | 'effectScatter'
    | 'radar'
    | 'heatmap'
    | 'funnel'
    | 'gauge'
    | 'parallel'
    | 'polar'
    | 'calendar'
    | 'geo'
    | 'singleAxis'
    | 'map',
): EditorContext => ({
  currentChartType: chartType,
  option,
  selectedSeriesIndex: 0,
  selectedDataZoomIndex: 0,
  selectedXAxisIndex: 0,
  selectedYAxisIndex: 0,
  selectedGridIndex: 0,
  selectedVisualMapIndex: 0,
  selectedTitleIndex: 0,
  selectedDatasetIndex: 0,
  selectedRadarIndex: 0,
  selectedPolarIndex: 0,
  selectedSingleAxisIndex: 0,
  selectedParallelIndex: 0,
  selectedParallelAxisIndex: 0,
  selectedCalendarIndex: 0,
  selectedGeoIndex: 0,
  selectedAngleAxisIndex: 0,
  selectedRadiusAxisIndex: 0,
});

describe('validation utils', () => {
  it('returns advisory warnings/errors for common pie misconfiguration risks', () => {
    const option = {
      dataset: { source: 'invalid-shape' },
      xAxis: { show: true, data: ['A', 'B'] },
      yAxis: { show: true },
      tooltip: { trigger: 'axis' },
      legend: { show: true },
      title: { show: true, text: '' },
      series: [{ type: 'pie', data: [10, 20] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'pie'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('dataset-invalid-shape');
    expect(ids).toContain('pie-uses-xaxis');
    expect(ids).toContain('pie-uses-yaxis');
    expect(ids).toContain('pie-tooltip-trigger');
    expect(ids).toContain('pie-primitive-data-0');
    expect(ids).toContain('legend-no-series-names');
    expect(ids).toContain('title-shown-empty-text');

    const pieTooltipMessage = result.messages.find((item) => item.id === 'pie-tooltip-trigger');
    expect(pieTooltipMessage?.fixes?.[0]).toMatchObject({
      kind: 'set_path',
      label: "Set tooltip.trigger to 'item'",
    });

    const pieAxisMessage = result.messages.find((item) => item.id === 'pie-uses-xaxis');
    expect(pieAxisMessage?.fixes?.[0]).toMatchObject({
      kind: 'batch_set_paths',
      label: 'Hide xAxis and yAxis',
    });
  });

  it('reports selected series missing type', () => {
    const option = {
      series: [{}],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'line'));
    const missingType = result.messages.find((item) => item.id === 'selected-series-missing-type');

    expect(missingType?.severity).toBe('error');
    expect(missingType?.path).toBe('series.0.type');
    expect(missingType?.fixes?.[0]).toMatchObject({
      kind: 'set_selected_series_type',
    });
  });

  it('warns for invalid candlestick axis/tooltip/mapping config', () => {
    const option = {
      dataset: { source: [['Date', 'Value'], ['2026-03-01', 120]] },
      xAxis: { show: true, type: 'value' },
      yAxis: { show: true, type: 'value' },
      tooltip: { trigger: 'item' },
      series: [{ type: 'candlestick' }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'candlestick'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('candlestick-xaxis-type-0');
    expect(ids).toContain('candlestick-tooltip-axis-0');
    expect(ids).toContain('candlestick-missing-ohlc-mapping-0');

    const tooltipFix = result.messages.find((item) => item.id === 'candlestick-tooltip-axis-0')?.fixes?.[0];
    expect(tooltipFix).toMatchObject({
      kind: 'set_path',
      label: "Set tooltip.trigger to 'axis'",
    });
  });

  it('warns for invalid scatter axis types and missing encode mapping', () => {
    const option = {
      dataset: { source: [['X', 'Y'], [12, 20], [18, 35]] },
      xAxis: { show: true, type: 'category' },
      yAxis: { show: true, type: 'category' },
      series: [{ type: 'scatter' }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'scatter'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('scatter-xaxis-value-0');
    expect(ids).toContain('scatter-yaxis-value-0');
    expect(ids).toContain('scatter-missing-encode-0');

    const fix = result.messages.find((item) => item.id === 'scatter-xaxis-value-0')?.fixes?.[0];
    expect(fix).toMatchObject({
      kind: 'batch_set_paths',
      label: 'Set xAxis.type to value',
    });
  });

  it('warns when radar is missing indicators and dataset dimensions are insufficient', () => {
    const option = {
      dataset: { source: [['Team', 'Value'], ['Alpha', 82]] },
      radar: [{ indicator: [] }],
      series: [{ type: 'radar', data: [{ name: 'Alpha', value: [82] }] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'radar'));
    const message = result.messages.find((item) => item.id === 'radar-missing-indicators-0');

    expect(message?.severity).toBe('warning');
    expect(message?.fixes?.[0]).toMatchObject({
      kind: 'set_path',
      label: 'Set default radar indicators',
    });
  });

  it('warns for heatmap without encode mappings', () => {
    const option = {
      dataset: { source: [['X', 'Y', 'Value'], ['Mon', 'AM', 12]] },
      xAxis: { show: true, type: 'category' },
      yAxis: { show: true, type: 'category' },
      series: [{ type: 'heatmap' }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'heatmap'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('heatmap-missing-encode-0');
  });

  it('warns for funnel tooltip trigger and primitive funnel data', () => {
    const option = {
      tooltip: { trigger: 'axis' },
      series: [{ type: 'funnel', data: [1000, 650, 240] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'funnel'));
    const ids = result.messages.map((item) => item.id);
    expect(ids).toContain('funnel-tooltip-item-0');
    expect(ids).toContain('funnel-primitive-data-0');
  });

  it('warns for invalid gauge range and missing gauge value', () => {
    const option = {
      series: [{ type: 'gauge', min: 80, max: 60, data: [] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'gauge'));
    const ids = result.messages.map((item) => item.id);
    expect(ids).toContain('gauge-invalid-range-0');
    expect(ids).toContain('gauge-missing-value-0');

    const rangeFix = result.messages.find((item) => item.id === 'gauge-invalid-range-0')?.fixes?.[0];
    expect(rangeFix).toMatchObject({
      kind: 'batch_set_paths',
      label: 'Set min/max to 0/100',
    });
  });

  it('warns when polar series misses required polar/angle/radius components', () => {
    const option = {
      series: [{ type: 'bar', coordinateSystem: 'polar', data: [1, 2, 3] }],
      polar: [],
      angleAxis: [],
      radiusAxis: [],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'polar'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('polar-missing-component');
    expect(ids).toContain('polar-missing-angle-axis');
    expect(ids).toContain('polar-missing-radius-axis');
  });

  it('warns when parallel series has missing axes or too few dimensions', () => {
    const option = {
      parallel: [{}],
      parallelAxis: [{ dim: 0, type: 'value' }],
      series: [{ type: 'parallel', data: [[12], [15]] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'parallel'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('parallel-missing-axes');
    expect(ids).toContain('parallel-too-few-dimensions-0');
  });

  it('warns when calendar heatmap is missing range/date-value mapping', () => {
    const option = {
      calendar: [{ range: '' }],
      series: [{ type: 'heatmap', coordinateSystem: 'calendar', data: [[1, 2, 3]] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'calendar'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('calendar-missing-range');
    expect(ids).toContain('calendar-heatmap-invalid-shape-0');
  });

  it('warns when geo/effectScatter is missing geo.map', () => {
    const option = {
      geo: [{ map: '' }],
      series: [{ type: 'effectScatter', coordinateSystem: 'geo' }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'geo'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('geo-missing-map');
    expect(ids).toContain('geo-series-missing-map-0');
  });

  it('warns when map series is missing a map name', () => {
    const option = {
      series: [{ type: 'map', map: '' }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'map'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('map-series-missing-map-0');
  });

  it('warns for dataZoom missing axis target and invalid start/end range', () => {
    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataZoom: [{ type: 'slider', start: 80, end: 20 }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'line'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('datazoom-missing-axis-target-0');
    expect(ids).toContain('datazoom-invalid-range-0');

    const missingTargetFix = result.messages.find((item) => item.id === 'datazoom-missing-axis-target-0')?.fixes?.[0];
    expect(missingTargetFix).toMatchObject({
      kind: 'set_path',
      label: 'Set xAxisIndex to 0',
    });

    const rangeFix = result.messages.find((item) => item.id === 'datazoom-invalid-range-0')?.fixes?.[0];
    expect(rangeFix).toMatchObject({
      kind: 'batch_set_paths',
      label: 'Reset start/end to 0/100',
    });
  });

  it('warns for over-constrained grid width/height layout', () => {
    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      grid: [{ left: '10%', right: '10%', width: '70%', top: '12%', bottom: '12%', height: '60%' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    const result = validateOption(option, buildContext(option, 'line'));
    const ids = result.messages.map((item) => item.id);

    expect(ids).toContain('grid-horizontal-overconstrained-0');
    expect(ids).toContain('grid-vertical-overconstrained-0');
  });
});
