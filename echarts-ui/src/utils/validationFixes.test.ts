import { describe, expect, it } from 'vitest';
import type { EditorContext } from '../types/editor';
import type { EditorOption } from '../types/echarts';
import { applyValidationFix, type ValidationFix } from './validationFixes';

const buildContext = (option: EditorOption): EditorContext => ({
  currentChartType: 'line',
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

describe('validationFixes utils', () => {
  it('applies set_path, batch_set_paths, and clear_path fixes', () => {
    const option = {
      tooltip: { trigger: 'axis' },
      xAxis: [{ show: true, data: ['A', 'B'] }],
      yAxis: [{ show: true }],
      series: [{ type: 'pie' }],
    } as EditorOption;
    const context = buildContext(option);

    const setTooltipFix: ValidationFix = {
      id: 'set-tooltip',
      label: 'Set tooltip item',
      kind: 'set_path',
      payload: { path: 'tooltip.trigger', value: 'item' },
    };
    const hideAxesFix: ValidationFix = {
      id: 'hide-axes',
      label: 'Hide axes',
      kind: 'batch_set_paths',
      payload: {
        entries: [
          { path: 'xAxis.0.show', value: false },
          { path: 'yAxis.0.show', value: false },
        ],
      },
    };
    const clearXAxisDataFix: ValidationFix = {
      id: 'clear-xaxis-data',
      label: 'Clear xAxis.data',
      kind: 'clear_path',
      payload: { path: 'xAxis.0.data' },
    };

    const afterSet = applyValidationFix(option, context, setTooltipFix).option as Record<string, unknown>;
    const afterBatch = applyValidationFix(afterSet as EditorOption, context, hideAxesFix).option as Record<string, unknown>;
    const afterClear = applyValidationFix(afterBatch as EditorOption, context, clearXAxisDataFix).option as Record<string, unknown>;

    expect((afterSet.tooltip as Record<string, unknown>).trigger).toBe('item');
    expect(((afterBatch.xAxis as Array<Record<string, unknown>>)[0] as Record<string, unknown>).show).toBe(false);
    expect(((afterBatch.yAxis as Array<Record<string, unknown>>)[0] as Record<string, unknown>).show).toBe(false);
    expect(((afterClear.xAxis as Array<Record<string, unknown>>)[0] as Record<string, unknown>).data).toBeUndefined();
  });

  it('ensures default axis when missing', () => {
    const option = {
      series: [{ type: 'line', data: [1, 2, 3] }],
      xAxis: [],
    } as EditorOption;
    const context = buildContext(option);

    const fixed = applyValidationFix(option, context, {
      id: 'ensure-default-xaxis',
      label: 'Create default xAxis',
      kind: 'ensure_default_axis',
      payload: { axis: 'xAxis' },
    }).option as Record<string, unknown>;

    const xAxis = fixed.xAxis as Array<Record<string, unknown>>;
    expect(xAxis).toHaveLength(1);
    expect(xAxis[0].type).toBe('category');
  });

  it('enables existing first axis when ensure_default_axis is applied', () => {
    const option = {
      series: [{ type: 'line', data: [1, 2, 3] }],
      xAxis: [{ show: false, type: '' }],
    } as EditorOption;
    const context = buildContext(option);

    const fixed = applyValidationFix(option, context, {
      id: 'ensure-default-xaxis',
      label: 'Create default xAxis',
      kind: 'ensure_default_axis',
      payload: { axis: 'xAxis' },
    }).option as Record<string, unknown>;

    const xAxis = fixed.xAxis as Array<Record<string, unknown>>;
    expect(xAxis[0].show).toBe(true);
    expect(xAxis[0].type).toBe('category');
  });

  it('auto-names unnamed series and sets selected series type', () => {
    const option = {
      series: [{}, { name: 'Revenue', type: 'bar' }],
    } as EditorOption;
    const context = buildContext(option);

    const autoNamed = applyValidationFix(option, context, {
      id: 'auto-name-series',
      label: 'Auto-name unnamed series',
      kind: 'auto_name_series',
    }).option as Record<string, unknown>;

    expect((autoNamed.series as Array<Record<string, unknown>>)[0].name).toBe('Series 1');

    const withType = applyValidationFix(autoNamed as EditorOption, context, {
      id: 'set-selected-type',
      label: 'Set selected series type',
      kind: 'set_selected_series_type',
      payload: { type: 'current_or_line' },
    }).option as Record<string, unknown>;

    expect((withType.series as Array<Record<string, unknown>>)[0].type).toBe('line');
  });

  it('sets selected series type from current chart type when current_or_line is used', () => {
    const option = {
      series: [{}],
    } as EditorOption;
    const context = { ...buildContext(option), currentChartType: 'gauge' as const };

    const fixed = applyValidationFix(option, context, {
      id: 'set-selected-type',
      label: 'Set selected series type',
      kind: 'set_selected_series_type',
      payload: { type: 'current_or_line' },
    }).option as Record<string, unknown>;

    expect((fixed.series as Array<Record<string, unknown>>)[0].type).toBe('gauge');
  });

  it('restores default dataset source for selected dataset', () => {
    const option = {
      dataset: [{ source: 'invalid' }],
      series: [{ type: 'line' }],
    } as EditorOption;
    const context = buildContext(option);

    const fixed = applyValidationFix(option, context, {
      id: 'restore-default-dataset',
      label: 'Restore default dataset',
      kind: 'restore_default_dataset',
    }).option as Record<string, unknown>;

    const dataset = fixed.dataset as Array<Record<string, unknown>>;
    expect(Array.isArray(dataset[0].source)).toBe(true);
    expect(dataset[0].source).toEqual([
      ['category', 'value'],
      ['A', 120],
    ]);
  });

  it('can apply new coordinate-family fixes through batch and set paths', () => {
    const option = {
      series: [{ type: 'bar', coordinateSystem: 'polar' }, { type: 'map', map: '' }],
    } as EditorOption;
    const context = buildContext(option);

    const withPolar = applyValidationFix(option, context, {
      id: 'create-default-polar',
      label: 'Create default polar',
      kind: 'batch_set_paths',
      payload: {
        entries: [
          { path: 'polar.0.center', value: ['50%', '55%'] },
          { path: 'polar.0.radius', value: '70%' },
          { path: 'angleAxis.0.type', value: 'category' },
          { path: 'radiusAxis.0.type', value: 'value' },
        ],
      },
    }).option as Record<string, unknown>;

    expect(((withPolar.polar as Array<Record<string, unknown>>)[0] as Record<string, unknown>).radius).toBe('70%');
    expect(((withPolar.angleAxis as Array<Record<string, unknown>>)[0] as Record<string, unknown>).type).toBe('category');

    const withMapName = applyValidationFix(withPolar as EditorOption, context, {
      id: 'set-map-name',
      label: 'Set map',
      kind: 'set_path',
      payload: { path: 'series.1.map', value: 'world-lite' },
    }).option as Record<string, unknown>;

    expect((withMapName.series as Array<Record<string, unknown>>)[1].map).toBe('world-lite');
  });
});
