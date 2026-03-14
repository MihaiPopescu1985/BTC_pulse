import type { EditorContext } from '../types/editor';
import type { EditorOption } from '../types/echarts';
import { defaultDatasetItem } from '../schema/common/dataset';
import { setDatasetSourceInOption } from './dataset';
import { addOptionObjectItem, ensureOptionObjectArray, getOptionObjectArray } from './optionArrays';
import { getByPath, setByPath } from './path';
import { ensureSeriesArray, getSeriesList } from './series';
import { cloneValue } from './value';

export type ValidationFixKind =
  | 'set_path'
  | 'batch_set_paths'
  | 'clear_path'
  | 'ensure_default_axis'
  | 'auto_name_series'
  | 'restore_default_dataset'
  | 'set_selected_series_type';

export type SeriesTypeFixValue =
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
  | 'map'
  | 'current_or_line';

export type ValidationFix =
  | {
      id: string;
      label: string;
      kind: 'set_path';
      payload: { path: string; value: unknown };
    }
  | {
      id: string;
      label: string;
      kind: 'batch_set_paths';
      payload: { entries: Array<{ path: string; value: unknown }> };
    }
  | {
      id: string;
      label: string;
      kind: 'clear_path';
      payload: { path: string };
    }
  | {
      id: string;
      label: string;
      kind: 'ensure_default_axis';
      payload: { axis: 'xAxis' | 'yAxis' };
    }
  | {
      id: string;
      label: string;
      kind: 'auto_name_series';
      payload?: undefined;
    }
  | {
      id: string;
      label: string;
      kind: 'restore_default_dataset';
      payload?: { datasetIndex?: number };
    }
  | {
      id: string;
      label: string;
      kind: 'set_selected_series_type';
      payload?: { type?: SeriesTypeFixValue };
    };

export interface ApplyValidationFixResult {
  option: EditorOption;
  selectionUpdates?: Partial<
    Pick<
      EditorContext,
      | 'selectedSeriesIndex'
      | 'selectedDataZoomIndex'
      | 'selectedXAxisIndex'
      | 'selectedYAxisIndex'
      | 'selectedGridIndex'
      | 'selectedVisualMapIndex'
      | 'selectedTitleIndex'
      | 'selectedDatasetIndex'
      | 'selectedRadarIndex'
      | 'selectedPolarIndex'
      | 'selectedSingleAxisIndex'
      | 'selectedParallelIndex'
      | 'selectedParallelAxisIndex'
      | 'selectedCalendarIndex'
      | 'selectedGeoIndex'
      | 'selectedAngleAxisIndex'
      | 'selectedRadiusAxisIndex'
    >
  >;
}

const defaultAxisByType: Record<'xAxis' | 'yAxis', Record<string, unknown>> = {
  xAxis: {
    show: true,
    type: 'category',
    name: '',
    boundaryGap: true,
  },
  yAxis: {
    show: true,
    type: 'value',
    name: '',
    boundaryGap: false,
  },
};

const resolveSeriesTypeFromFix = (
  context: EditorContext,
  type?: SeriesTypeFixValue,
): 'line' | 'bar' | 'pie' | 'candlestick' | 'scatter' | 'effectScatter' | 'radar' | 'heatmap' | 'funnel' | 'gauge' | 'parallel' | 'map' => {
  if (
    type === 'line' ||
    type === 'bar' ||
    type === 'pie' ||
    type === 'candlestick' ||
    type === 'scatter' ||
    type === 'effectScatter' ||
    type === 'radar' ||
    type === 'heatmap' ||
    type === 'funnel' ||
    type === 'gauge' ||
    type === 'parallel' ||
    type === 'map'
  ) {
    return type;
  }

  if (
    context.currentChartType === 'line' ||
    context.currentChartType === 'bar' ||
    context.currentChartType === 'pie' ||
    context.currentChartType === 'candlestick' ||
    context.currentChartType === 'scatter' ||
    context.currentChartType === 'effectScatter' ||
    context.currentChartType === 'radar' ||
    context.currentChartType === 'heatmap' ||
    context.currentChartType === 'funnel' ||
    context.currentChartType === 'gauge' ||
    context.currentChartType === 'parallel' ||
    context.currentChartType === 'map'
  ) {
    return context.currentChartType;
  }

  if (context.currentChartType === 'polar') {
    return 'line';
  }

  if (context.currentChartType === 'calendar') {
    return 'heatmap';
  }

  if (context.currentChartType === 'geo') {
    return 'scatter';
  }

  if (context.currentChartType === 'singleAxis') {
    return 'effectScatter';
  }

  return 'line';
};

const applySetPath = (option: EditorOption, fix: Extract<ValidationFix, { kind: 'set_path' }>): EditorOption => {
  return setByPath(option, fix.payload.path, cloneValue(fix.payload.value));
};

const applyBatchSetPaths = (
  option: EditorOption,
  fix: Extract<ValidationFix, { kind: 'batch_set_paths' }>,
): EditorOption => {
  return fix.payload.entries.reduce((nextOption, entry) => {
    return setByPath(nextOption, entry.path, cloneValue(entry.value));
  }, option);
};

const applyClearPath = (option: EditorOption, fix: Extract<ValidationFix, { kind: 'clear_path' }>): EditorOption => {
  return setByPath(option, fix.payload.path, undefined);
};

const applyEnsureDefaultAxis = (
  option: EditorOption,
  fix: Extract<ValidationFix, { kind: 'ensure_default_axis' }>,
): EditorOption => {
  const axisPath = fix.payload.axis;
  const normalized = ensureOptionObjectArray(option, axisPath);
  const axisItems = getOptionObjectArray(normalized, axisPath);

  if (axisItems.length > 0) {
    let next = setByPath(normalized, `${axisPath}.0.show`, true);
    const typePath = `${axisPath}.0.type`;
    const currentType = getByPath(next, typePath);
    if (typeof currentType !== 'string' || currentType.trim().length === 0) {
      next = setByPath(next, typePath, defaultAxisByType[fix.payload.axis].type);
    }
    return next;
  }

  const next = addOptionObjectItem(normalized, axisPath, defaultAxisByType[fix.payload.axis]);
  return next.option;
};

const applyAutoNameSeries = (option: EditorOption): EditorOption => {
  const normalized = ensureSeriesArray(option);
  const nextSeries = getSeriesList(normalized).map((series, index) => {
    const rawName = typeof series.name === 'string' ? series.name.trim() : '';
    if (rawName.length > 0) {
      return series;
    }

    return {
      ...series,
      name: `Series ${index + 1}`,
    };
  });

  return {
    ...normalized,
    series: nextSeries,
  };
};

const applyRestoreDefaultDataset = (
  option: EditorOption,
  context: EditorContext,
  fix: Extract<ValidationFix, { kind: 'restore_default_dataset' }>,
): EditorOption => {
  const datasetIndex = fix.payload?.datasetIndex ?? context.selectedDatasetIndex ?? 0;
  return setDatasetSourceInOption(option, cloneValue(defaultDatasetItem.source), datasetIndex);
};

const applySetSelectedSeriesType = (
  option: EditorOption,
  context: EditorContext,
  fix: Extract<ValidationFix, { kind: 'set_selected_series_type' }>,
): EditorOption => {
  const normalized = ensureSeriesArray(option);
  const seriesList = getSeriesList(normalized);
  const selectedIndex = context.selectedSeriesIndex;

  if (selectedIndex < 0 || selectedIndex >= seriesList.length) {
    return normalized;
  }

  const nextType = resolveSeriesTypeFromFix(context, fix.payload?.type);
  return setByPath(normalized, `series.${selectedIndex}.type`, nextType);
};

export const applyValidationFix = (
  option: EditorOption,
  context: EditorContext,
  fix: ValidationFix,
): ApplyValidationFixResult => {
  switch (fix.kind) {
    case 'set_path':
      return { option: applySetPath(option, fix) };
    case 'batch_set_paths':
      return { option: applyBatchSetPaths(option, fix) };
    case 'clear_path':
      return { option: applyClearPath(option, fix) };
    case 'ensure_default_axis':
      return { option: applyEnsureDefaultAxis(option, fix) };
    case 'auto_name_series':
      return { option: applyAutoNameSeries(option) };
    case 'restore_default_dataset':
      return { option: applyRestoreDefaultDataset(option, context, fix) };
    case 'set_selected_series_type':
      return { option: applySetSelectedSeriesType(option, context, fix) };
    default:
      return { option };
  }
};
