import type { ChartType, EditorOption } from '../types/echarts';
import type { DatasetCell, DatasetSource } from './dataset';
import { cloneValue } from './value';

export type InferenceKind =
  | 'single-series'
  | 'multi-series'
  | 'pie-candidate'
  | 'candlestick-candidate'
  | 'scatter-candidate'
  | 'effectscatter-candidate'
  | 'radar-candidate'
  | 'heatmap-candidate'
  | 'funnel-candidate'
  | 'gauge-candidate'
  | 'parallel-candidate'
  | 'calendar-candidate'
  | 'geo-candidate'
  | 'map-candidate'
  | 'polar-candidate'
  | 'unknown';

export type InferenceConfidence = 'low' | 'medium' | 'high';

export interface DatasetInference {
  kind: InferenceKind;
  suggestedChartTypes: ChartType[];
  categoryColumnIndex: number;
  valueColumnIndexes: number[];
  ohlcColumnIndexes?: [number, number, number, number];
  scatterXColumnIndex?: number;
  scatterYColumnIndex?: number;
  scatterLabelColumnIndex?: number;
  heatmapXColumnIndex?: number;
  heatmapYColumnIndex?: number;
  heatmapValueColumnIndex?: number;
  heatmapUsesMatrix?: boolean;
  funnelStageColumnIndex?: number;
  funnelValueColumnIndex?: number;
  gaugeValueColumnIndex?: number;
  parallelValueColumnIndexes?: number[];
  calendarDateColumnIndex?: number;
  calendarValueColumnIndex?: number;
  geoNameColumnIndex?: number;
  geoLngColumnIndex?: number;
  geoLatColumnIndex?: number;
  geoValueColumnIndex?: number;
  confidence: InferenceConfidence;
  reason: string;
  previewLabels: string[];
  categoryColumnLabel: string;
  valueColumnLabels: string[];
  hasTimeLikeCategory: boolean;
}

export interface ApplySuggestionOptions {
  chartType: ChartType;
  inference: DatasetInference;
  source: DatasetSource;
}

const MONTH_NAMES = new Set([
  'jan',
  'january',
  'feb',
  'february',
  'mar',
  'march',
  'apr',
  'april',
  'may',
  'jun',
  'june',
  'jul',
  'july',
  'aug',
  'august',
  'sep',
  'sept',
  'september',
  'oct',
  'october',
  'nov',
  'november',
  'dec',
  'december',
]);

const GEO_NAME_HINTS = ['country', 'city', 'state', 'region', 'province', 'name', 'location'];
const FUNNEL_STAGE_HINTS = ['stage', 'step', 'phase', 'funnel'];

const isNonEmpty = (value: unknown): boolean => value !== '' && value !== null && value !== undefined;

const cellAsString = (value: DatasetCell): string => {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
};

const toNumeric = (value: DatasetCell): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }

    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
};

const isTimeLikeValue = (rawValue: string): boolean => {
  const value = rawValue.trim().toLowerCase();
  if (!value) {
    return false;
  }

  if (MONTH_NAMES.has(value)) {
    return true;
  }

  if (/^(19|20)\d{2}$/.test(value)) {
    return true;
  }

  if (/^\d{4}[-/]\d{1,2}([-/]\d{1,2})?$/.test(value)) {
    return true;
  }

  if (/^\d{1,2}[./-]\d{1,2}([./-]\d{2,4})?$/.test(value)) {
    return true;
  }

  return false;
};

const isCalendarDateLikeValue = (rawValue: string): boolean => {
  const value = rawValue.trim().toLowerCase();
  if (!value) {
    return false;
  }

  if (/^\d{4}[-/]\d{1,2}([-/]\d{1,2})?$/.test(value)) {
    return true;
  }

  if (/^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$/.test(value)) {
    return true;
  }

  return false;
};

const getColumn = (rows: DatasetCell[][], columnIndex: number): DatasetCell[] => {
  return rows.map((row) => row[columnIndex]).filter((value) => value !== undefined);
};

const numericRatio = (values: DatasetCell[]): number => {
  const nonEmpty = values.filter((value) => isNonEmpty(value));
  if (nonEmpty.length === 0) {
    return 0;
  }

  const numericCount = nonEmpty.filter((value) => toNumeric(value) !== null).length;
  return numericCount / nonEmpty.length;
};

const timeLikeRatio = (values: DatasetCell[]): number => {
  const nonEmpty = values.filter((value) => isNonEmpty(value));
  if (nonEmpty.length === 0) {
    return 0;
  }

  const timeLikeCount = nonEmpty.filter((value) => isTimeLikeValue(cellAsString(value))).length;
  return timeLikeCount / nonEmpty.length;
};

const calendarDateRatio = (values: DatasetCell[]): number => {
  const nonEmpty = values.filter((value) => isNonEmpty(value));
  if (nonEmpty.length === 0) {
    return 0;
  }

  const dateLikeCount = nonEmpty.filter((value) => isCalendarDateLikeValue(cellAsString(value))).length;
  return dateLikeCount / nonEmpty.length;
};

const normalizeHeaderName = (headerRow: DatasetCell[], columnIndex: number): string => {
  const raw = cellAsString(headerRow[columnIndex]).trim();
  return raw || `Column ${columnIndex + 1}`;
};

const dedupe = (values: string[]): string[] => {
  const seen = new Set<string>();
  const output: string[] = [];

  values.forEach((item) => {
    if (seen.has(item)) {
      return;
    }
    seen.add(item);
    output.push(item);
  });

  return output;
};

const buildLabelLikeRating = (rows: DatasetCell[][], columnIndex: number): boolean => {
  const values = getColumn(rows, columnIndex);
  return numericRatio(values) < 0.5;
};

const headerLooksGeoName = (header: string): boolean => {
  const normalized = header.trim().toLowerCase();
  return GEO_NAME_HINTS.some((token) => normalized.includes(token));
};

const headerLooksFunnelStage = (header: string): boolean => {
  const normalized = header.trim().toLowerCase();
  return FUNNEL_STAGE_HINTS.some((token) => normalized.includes(token));
};

export const inferDataset = (source: DatasetSource): DatasetInference | null => {
  if (!Array.isArray(source) || source.length < 1) {
    return null;
  }

  const headerRow = source[0] ?? [];
  const dataRows = source.slice(1);
  const columnCount = headerRow.length;

  if (columnCount < 1 || dataRows.length === 0) {
    return null;
  }

  const categoryColumnIndex = 0;
  const firstColumnValues = getColumn(dataRows, categoryColumnIndex);
  const firstColumnNumericRatio = numericRatio(firstColumnValues);
  const firstColumnTimeRatio = timeLikeRatio(firstColumnValues);
  const firstColumnCalendarDateRatio = calendarDateRatio(firstColumnValues);
  const hasTimeLikeCategory = firstColumnTimeRatio >= 0.5;
  const labelLikeFirstColumn = hasTimeLikeCategory || firstColumnNumericRatio < 0.5;

  const numericColumnIndexes: number[] = [];
  for (let index = 0; index < columnCount; index += 1) {
    if (numericRatio(getColumn(dataRows, index)) >= 0.7) {
      numericColumnIndexes.push(index);
    }
  }

  const valueColumnIndexes: number[] = [];
  for (let index = 1; index < columnCount; index += 1) {
    if (numericRatio(getColumn(dataRows, index)) >= 0.7) {
      valueColumnIndexes.push(index);
    }
  }

  const scatterTwoNumericColumns = columnCount === 2 && numericColumnIndexes.includes(0) && numericColumnIndexes.includes(1);
  const scatterLabelPlusTwoNumeric = labelLikeFirstColumn && valueColumnIndexes.length === 2;
  const scatterEligible = scatterTwoNumericColumns || scatterLabelPlusTwoNumeric;

  const scatterXColumnIndex = scatterTwoNumericColumns ? 0 : scatterLabelPlusTwoNumeric ? valueColumnIndexes[0] : undefined;
  const scatterYColumnIndex = scatterTwoNumericColumns ? 1 : scatterLabelPlusTwoNumeric ? valueColumnIndexes[1] : undefined;
  const scatterLabelColumnIndex = scatterLabelPlusTwoNumeric ? 0 : undefined;

  const candlestickEligible =
    columnCount === 5 &&
    valueColumnIndexes.length === 4 &&
    valueColumnIndexes.every((index, order) => index === order + 1);

  const heatmapTripletEligible =
    columnCount === 3 &&
    numericRatio(getColumn(dataRows, 2)) >= 0.7 &&
    buildLabelLikeRating(dataRows, 0) &&
    buildLabelLikeRating(dataRows, 1);

  const heatmapMatrixEligible =
    columnCount >= 3 &&
    dataRows.length >= 2 &&
    labelLikeFirstColumn &&
    valueColumnIndexes.length >= 2;

  const radarEligible = labelLikeFirstColumn && valueColumnIndexes.length >= 3;
  const parallelEligible = valueColumnIndexes.length >= 3 && dataRows.length >= 3;
  const funnelEligible =
    labelLikeFirstColumn &&
    !hasTimeLikeCategory &&
    columnCount === 2 &&
    valueColumnIndexes.length === 1 &&
    headerLooksFunnelStage(normalizeHeaderName(headerRow, 0));
  const polarEligible = labelLikeFirstColumn && !hasTimeLikeCategory && columnCount === 2 && valueColumnIndexes.length === 1;

  const calendarEligible = firstColumnCalendarDateRatio >= 0.5 && columnCount === 2 && valueColumnIndexes.length === 1;

  const singleNumericColumn = columnCount === 1 && numericColumnIndexes[0] === 0;
  const singleRowLabelPlusValue =
    columnCount === 2 && dataRows.length === 1 && labelLikeFirstColumn && valueColumnIndexes.length === 1;
  const gaugeEligible = singleNumericColumn || singleRowLabelPlusValue;

  const geoLngLatEligible =
    columnCount >= 3 &&
    numericRatio(getColumn(dataRows, 0)) >= 0.8 &&
    numericRatio(getColumn(dataRows, 1)) >= 0.8 &&
    numericRatio(getColumn(dataRows, 2)) >= 0.7;

  const geoNameValueEligible =
    columnCount === 2 &&
    labelLikeFirstColumn &&
    valueColumnIndexes.length === 1 &&
    headerLooksGeoName(normalizeHeaderName(headerRow, 0));

  const pieEligible = columnCount === 2 && valueColumnIndexes.length === 1;

  if (
    !candlestickEligible &&
    !scatterEligible &&
    !heatmapTripletEligible &&
    !heatmapMatrixEligible &&
    !radarEligible &&
    !parallelEligible &&
    !funnelEligible &&
    !gaugeEligible &&
    !calendarEligible &&
    !geoLngLatEligible &&
    !geoNameValueEligible &&
    !polarEligible &&
    !pieEligible &&
    !(labelLikeFirstColumn && valueColumnIndexes.length > 0)
  ) {
    return null;
  }

  let kind: InferenceKind = 'unknown';
  let suggestedChartTypes: ChartType[] = [];
  let reason = '';

  if (candlestickEligible) {
    kind = 'candlestick-candidate';
    suggestedChartTypes = hasTimeLikeCategory ? ['candlestick', 'line', 'bar'] : ['candlestick', 'bar', 'line'];
    reason = 'Detected OHLC structure (Open, Close, Low, High) after a date/category column.';
  } else if (geoLngLatEligible) {
    kind = 'geo-candidate';
    suggestedChartTypes = ['geo', 'effectScatter', 'scatter'];
    reason = 'Detected lng/lat/value columns suitable for geo scatter plotting.';
  } else if (geoNameValueEligible) {
    kind = 'map-candidate';
    suggestedChartTypes = ['map', 'bar', 'pie'];
    reason = 'Detected name + value columns suitable for a map choropleth when region names match the selected map.';
  } else if (calendarEligible) {
    kind = 'calendar-candidate';
    suggestedChartTypes = ['calendar', 'line'];
    reason = 'Detected date + value structure suitable for calendar activity heatmaps.';
  } else if (gaugeEligible) {
    kind = 'gauge-candidate';
    suggestedChartTypes = ['gauge'];
    reason = 'Detected a single KPI-style numeric value. Gauge is a strong fit.';
  } else if (heatmapTripletEligible) {
    kind = 'heatmap-candidate';
    suggestedChartTypes = ['heatmap', 'scatter'];
    reason = 'Detected [x, y, value] triplets suitable for a category heatmap.';
  } else if (scatterEligible) {
    kind = 'scatter-candidate';
    suggestedChartTypes = ['scatter', 'effectScatter'];
    reason = scatterTwoNumericColumns
      ? 'Detected two numeric columns. Scatter/effectScatter are good for numeric X/Y relationships.'
      : 'Detected label + two numeric columns suitable for scatter/effectScatter with tooltip labels.';
  } else if (parallelEligible) {
    kind = 'parallel-candidate';
    suggestedChartTypes = ['parallel', 'radar'];
    reason = 'Detected many numeric dimensions suitable for parallel coordinates.';
  } else if (radarEligible) {
    kind = 'radar-candidate';
    suggestedChartTypes = ['radar', 'parallel', 'heatmap'];
    reason = 'Detected one label column plus multiple numeric metrics, suitable for radar comparison.';
  } else if (heatmapMatrixEligible) {
    kind = 'heatmap-candidate';
    suggestedChartTypes = ['heatmap', 'bar', 'line'];
    reason = 'Detected matrix-style categories with numeric body values, suitable for heatmap.';
  } else if (funnelEligible) {
    kind = 'funnel-candidate';
    suggestedChartTypes = ['funnel', 'bar', 'pie'];
    reason = 'Detected stage + value data, which maps naturally to a conversion funnel.';
  } else if (polarEligible) {
    kind = 'polar-candidate';
    suggestedChartTypes = ['polar', 'bar', 'line'];
    reason = 'Detected category + value data suitable for a radial polar chart.';
  } else if (pieEligible) {
    kind = 'pie-candidate';
    suggestedChartTypes = hasTimeLikeCategory ? ['line', 'bar', 'pie'] : ['bar', 'line', 'pie'];
    reason = hasTimeLikeCategory
      ? 'First column appears time-like, so line is preferred for trends.'
      : 'Detected one numeric value column with category labels.';
  } else if (valueColumnIndexes.length >= 2) {
    kind = 'multi-series';
    suggestedChartTypes = hasTimeLikeCategory ? ['line', 'bar'] : ['bar', 'line'];
    reason = 'Detected multiple numeric value columns for side-by-side comparison.';
  } else {
    kind = 'single-series';
    suggestedChartTypes = hasTimeLikeCategory ? ['line', 'bar'] : ['bar', 'line'];
    reason = hasTimeLikeCategory
      ? 'First column appears time-like, so a line chart is preferred for trends.'
      : 'Detected category labels with one numeric value column.';
  }

  const confidence: InferenceConfidence =
    kind === 'candlestick-candidate' || kind === 'gauge-candidate' || kind === 'geo-candidate' || kind === 'map-candidate'
      ? 'high'
      : kind === 'calendar-candidate' || kind === 'parallel-candidate' || kind === 'scatter-candidate'
        ? 'high'
        : kind === 'heatmap-candidate' || kind === 'radar-candidate' || kind === 'funnel-candidate' || kind === 'polar-candidate'
          ? 'medium'
          : firstColumnNumericRatio < 0.3
            ? 'high'
            : firstColumnNumericRatio < 0.45
              ? 'medium'
              : 'low';

  const categoryColumnLabel = normalizeHeaderName(headerRow, categoryColumnIndex);

  let valueColumnsForSummary = valueColumnIndexes;
  if (scatterEligible && scatterXColumnIndex !== undefined && scatterYColumnIndex !== undefined) {
    valueColumnsForSummary = [scatterXColumnIndex, scatterYColumnIndex];
  }
  if (singleNumericColumn) {
    valueColumnsForSummary = [0];
  }

  const valueColumnLabels = valueColumnsForSummary.map((index) => normalizeHeaderName(headerRow, index));
  const previewLabels = dataRows
    .slice(0, 4)
    .map((row) => cellAsString(row[categoryColumnIndex]))
    .filter(Boolean);

  return {
    kind,
    suggestedChartTypes,
    categoryColumnIndex,
    valueColumnIndexes: valueColumnsForSummary,
    ohlcColumnIndexes: candlestickEligible ? [1, 2, 3, 4] : undefined,
    scatterXColumnIndex,
    scatterYColumnIndex,
    scatterLabelColumnIndex,
    heatmapXColumnIndex: heatmapTripletEligible ? 0 : undefined,
    heatmapYColumnIndex: heatmapTripletEligible ? 1 : undefined,
    heatmapValueColumnIndex: heatmapTripletEligible ? 2 : undefined,
    heatmapUsesMatrix: heatmapTripletEligible ? false : heatmapMatrixEligible ? true : undefined,
    funnelStageColumnIndex: funnelEligible ? 0 : undefined,
    funnelValueColumnIndex: funnelEligible ? 1 : undefined,
    gaugeValueColumnIndex: singleNumericColumn ? 0 : singleRowLabelPlusValue ? 1 : undefined,
    parallelValueColumnIndexes: parallelEligible ? valueColumnIndexes : undefined,
    calendarDateColumnIndex: calendarEligible ? 0 : undefined,
    calendarValueColumnIndex: calendarEligible ? 1 : undefined,
    geoNameColumnIndex: geoLngLatEligible ? (columnCount > 3 ? 3 : undefined) : geoNameValueEligible ? 0 : undefined,
    geoLngColumnIndex: geoLngLatEligible ? 0 : undefined,
    geoLatColumnIndex: geoLngLatEligible ? 1 : undefined,
    geoValueColumnIndex: geoLngLatEligible ? 2 : geoNameValueEligible ? 1 : undefined,
    confidence,
    reason,
    previewLabels,
    categoryColumnLabel,
    valueColumnLabels,
    hasTimeLikeCategory,
  };
};

const buildCategoryValues = (rows: DatasetCell[][], categoryColumnIndex: number): string[] => {
  return rows.map((row) => cellAsString(row[categoryColumnIndex]));
};

const buildSeriesData = (rows: DatasetCell[][], valueColumnIndex: number): Array<number | null> => {
  return rows.map((row) => toNumeric(row[valueColumnIndex]));
};

const buildPieData = (
  rows: DatasetCell[][],
  categoryColumnIndex: number,
  valueColumnIndex: number,
): Array<{ name: string; value: number }> => {
  return rows
    .map((row) => {
      const name = cellAsString(row[categoryColumnIndex]);
      const value = toNumeric(row[valueColumnIndex]);
      if (!name || value === null) {
        return null;
      }

      return { name, value };
    })
    .filter((item): item is { name: string; value: number } => item !== null);
};

const roundIndicatorMax = (value: number): number => {
  if (!Number.isFinite(value) || value <= 0) {
    return 100;
  }

  if (value <= 10) {
    return Math.ceil(value);
  }

  const step = value <= 50 ? 5 : 10;
  return Math.ceil(value / step) * step;
};

const buildRadarIndicators = (rows: DatasetCell[][], headers: DatasetCell[], valueColumns: number[]) => {
  return valueColumns.map((columnIndex) => {
    const maxValue = rows.reduce((max, row) => {
      const numeric = toNumeric(row[columnIndex]);
      return numeric === null ? max : Math.max(max, numeric);
    }, 0);

    return {
      name: normalizeHeaderName(headers, columnIndex),
      max: roundIndicatorMax(maxValue),
    };
  });
};

const buildHeatmapDataFromTriples = (
  rows: DatasetCell[][],
  xColumnIndex: number,
  yColumnIndex: number,
  valueColumnIndex: number,
): Array<[string, string, number]> => {
  return rows
    .map((row) => {
      const x = cellAsString(row[xColumnIndex]);
      const y = cellAsString(row[yColumnIndex]);
      const value = toNumeric(row[valueColumnIndex]);
      if (!x || !y || value === null) {
        return null;
      }
      return [x, y, value] as [string, string, number];
    })
    .filter((item): item is [string, string, number] => item !== null);
};

const buildHeatmapDataFromMatrix = (
  headerRow: DatasetCell[],
  rows: DatasetCell[][],
  labelColumnIndex: number,
  valueColumns: number[],
): Array<[string, string, number]> => {
  const output: Array<[string, string, number]> = [];

  rows.forEach((row) => {
    const yLabel = cellAsString(row[labelColumnIndex]);
    if (!yLabel) {
      return;
    }

    valueColumns.forEach((columnIndex) => {
      const xLabel = normalizeHeaderName(headerRow, columnIndex);
      const numericValue = toNumeric(row[columnIndex]);
      if (numericValue === null) {
        return;
      }

      output.push([xLabel, yLabel, numericValue]);
    });
  });

  return output;
};

const parseYearFromDate = (value: string): string => {
  const match = value.match(/^(\d{4})/);
  return match ? match[1] : '2026';
};

export const applySuggestionToOption = (option: EditorOption, options: ApplySuggestionOptions): EditorOption => {
  const { chartType, inference, source } = options;
  const cloned = cloneValue(option);
  const headerRow = source[0] ?? [];
  const dataRows = source.slice(1);

  if (dataRows.length === 0) {
    return cloned;
  }

  if (chartType === 'pie') {
    const primaryValueIndex = inference.valueColumnIndexes[0] ?? 1;
    const pieData = buildPieData(dataRows, inference.categoryColumnIndex, primaryValueIndex);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: true,
      },
      xAxis: {
        ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
        show: false,
      },
      yAxis: {
        ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
        show: false,
      },
      series: [
        {
          name: normalizeHeaderName(headerRow, primaryValueIndex),
          type: 'pie',
          radius: '55%',
          data: pieData,
        },
      ],
    };
  }

  if (chartType === 'candlestick') {
    const ohlcColumns = inference.ohlcColumnIndexes ?? [1, 2, 3, 4];

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'axis',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: true,
      },
      xAxis: {
        ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
        show: true,
        type: 'category',
      },
      yAxis: {
        ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
        show: true,
        type: 'value',
      },
      series: [
        {
          name: 'Price',
          type: 'candlestick',
          encode: {
            x: inference.categoryColumnIndex,
            y: ohlcColumns,
          },
          itemStyle: {
            color: '#26a69a',
            color0: '#ef5350',
            borderColor: '#26a69a',
            borderColor0: '#ef5350',
          },
        },
      ],
    };
  }

  if (chartType === 'scatter' || chartType === 'effectScatter') {
    const xDimension = inference.scatterXColumnIndex ?? inference.categoryColumnIndex;
    const yDimension = inference.scatterYColumnIndex ?? inference.valueColumnIndexes[0] ?? 1;
    const tooltipDimensions =
      inference.scatterLabelColumnIndex !== undefined
        ? [inference.scatterLabelColumnIndex, xDimension, yDimension]
        : [xDimension, yDimension];

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: true,
      },
      xAxis: {
        ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
        show: true,
        type: 'value',
      },
      yAxis: {
        ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
        show: true,
        type: 'value',
      },
      series: [
        {
          name: 'Relationship',
          type: chartType,
          coordinateSystem: 'cartesian2d',
          symbol: 'circle',
          symbolSize: 14,
          rippleEffect: chartType === 'effectScatter' ? { scale: 2.5, brushType: 'stroke' } : undefined,
          encode: {
            x: xDimension,
            y: yDimension,
            tooltip: tooltipDimensions,
            itemName: inference.scatterLabelColumnIndex,
          },
          itemStyle: {
            color: chartType === 'effectScatter' ? '#16a34a' : '#3b82f6',
            opacity: chartType === 'effectScatter' ? 0.9 : 0.85,
          },
        },
      ],
    };
  }

  if (chartType === 'parallel') {
    const valueColumns = inference.parallelValueColumnIndexes ?? inference.valueColumnIndexes;
    const data = dataRows
      .map((row) => valueColumns.map((columnIndex) => toNumeric(row[columnIndex])))
      .filter((entry) => entry.every((cell) => cell !== null)) as number[][];

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      parallel: {
        left: '8%',
        right: '10%',
        top: '15%',
        bottom: '15%',
      },
      parallelAxis: valueColumns.map((columnIndex, dim) => ({
        dim,
        name: normalizeHeaderName(headerRow, columnIndex),
        type: 'value',
      })),
      series: [
        {
          name: 'Parallel profile',
          type: 'parallel',
          smooth: false,
          progressive: 200,
          data,
        },
      ],
    };
  }

  if (chartType === 'polar') {
    const primaryValueIndex = inference.valueColumnIndexes[0] ?? 1;
    const categories = buildCategoryValues(dataRows, inference.categoryColumnIndex);
    const values = buildSeriesData(dataRows, primaryValueIndex);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'axis',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: false,
      },
      xAxis: { show: false },
      yAxis: { show: false },
      polar: {
        center: ['50%', '55%'],
        radius: '70%',
      },
      angleAxis: {
        type: 'category',
        data: categories,
        startAngle: 90,
        clockwise: true,
      },
      radiusAxis: {
        type: 'value',
      },
      series: [
        {
          name: normalizeHeaderName(headerRow, primaryValueIndex),
          type: 'bar',
          coordinateSystem: 'polar',
          roundCap: true,
          data: values,
        },
      ],
    };
  }

  if (chartType === 'calendar') {
    const dateColumn = inference.calendarDateColumnIndex ?? 0;
    const valueColumn = inference.calendarValueColumnIndex ?? 1;
    const dateValues = dataRows.map((row) => cellAsString(row[dateColumn])).filter(Boolean);
    const calendarData = dataRows
      .map((row) => {
        const date = cellAsString(row[dateColumn]);
        const value = toNumeric(row[valueColumn]);
        if (!date || value === null) {
          return null;
        }
        return [date, value] as [string, number];
      })
      .filter((item): item is [string, number] => item !== null);

    const maxValue = calendarData.reduce((max, row) => Math.max(max, row[1]), 0);
    const year = parseYearFromDate(dateValues[0] ?? '2026');

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      xAxis: { show: false },
      yAxis: { show: false },
      calendar: {
        range: year,
        orient: 'horizontal',
        cellSize: ['auto', 18],
        left: 'center',
        top: 60,
      },
      visualMap: {
        show: true,
        min: 0,
        max: Math.max(1, maxValue),
        orient: 'horizontal',
        left: 'center',
        bottom: 20,
      },
      series: [
        {
          name: normalizeHeaderName(headerRow, valueColumn),
          type: 'heatmap',
          coordinateSystem: 'calendar',
          data: calendarData,
        },
      ],
    };
  }

  if (chartType === 'geo') {
    const lngColumn = inference.geoLngColumnIndex ?? 0;
    const latColumn = inference.geoLatColumnIndex ?? 1;
    const valueColumn = inference.geoValueColumnIndex ?? 2;
    const nameColumn = inference.geoNameColumnIndex;

    const geoData = dataRows
      .map((row, index) => {
        const lng = toNumeric(row[lngColumn]);
        const lat = toNumeric(row[latColumn]);
        const value = toNumeric(row[valueColumn]);
        if (lng === null || lat === null || value === null) {
          return null;
        }

        const name =
          nameColumn !== undefined
            ? cellAsString(row[nameColumn]) || `Point ${index + 1}`
            : `Point ${index + 1}`;

        return {
          name,
          value: [lng, lat, value],
        };
      })
      .filter((item): item is { name: string; value: [number, number, number] } => item !== null);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      xAxis: { show: false },
      yAxis: { show: false },
      geo: {
        map: 'world-lite',
        roam: true,
        zoom: 1.1,
        center: [0, 20],
        itemStyle: {
          areaColor: '#f8fafc',
          borderColor: '#64748b',
        },
      },
      series: [
        {
          name: 'Geo points',
          type: 'effectScatter',
          coordinateSystem: 'geo',
          symbolSize: 10,
          rippleEffect: {
            scale: 3,
            brushType: 'stroke',
          },
          data: geoData,
        },
      ],
    };
  }

  if (chartType === 'map') {
    const nameColumn = inference.geoNameColumnIndex ?? inference.categoryColumnIndex;
    const valueColumn = inference.geoValueColumnIndex ?? inference.valueColumnIndexes[0] ?? 1;
    const mapData = dataRows
      .map((row) => {
        const name = cellAsString(row[nameColumn]);
        const value = toNumeric(row[valueColumn]);
        if (!name || value === null) {
          return null;
        }

        return { name, value };
      })
      .filter((item): item is { name: string; value: number } => item !== null);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      visualMap: {
        show: true,
        min: 0,
        max: Math.max(1, ...mapData.map((entry) => entry.value)),
        left: 'right',
        top: 'middle',
      },
      xAxis: { show: false },
      yAxis: { show: false },
      series: [
        {
          name: 'Map values',
          type: 'map',
          map: 'world-lite',
          roam: true,
          label: { show: false },
          data: mapData,
        },
      ],
    };
  }

  if (chartType === 'radar') {
    const radarValueColumns = inference.valueColumnIndexes.length > 0 ? inference.valueColumnIndexes : [1, 2, 3];
    const indicators = buildRadarIndicators(dataRows, headerRow, radarValueColumns);

    const radarData = dataRows
      .map((row) => {
        const name = cellAsString(row[inference.categoryColumnIndex]) || 'Item';
        const values = radarValueColumns.map((columnIndex) => toNumeric(row[columnIndex]));
        if (values.some((value) => value === null)) {
          return null;
        }

        return {
          name,
          value: values as number[],
        };
      })
      .filter((item): item is { name: string; value: number[] } => item !== null);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: true,
      },
      xAxis: {
        ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
        show: false,
      },
      yAxis: {
        ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
        show: false,
      },
      radar: {
        shape: 'polygon',
        center: ['50%', '55%'],
        radius: '65%',
        indicator: indicators,
      },
      series: [
        {
          name: 'Radar comparison',
          type: 'radar',
          symbol: 'circle',
          symbolSize: 6,
          data: radarData,
          areaStyle: { opacity: 0.18 },
        },
      ],
    };
  }

  if (chartType === 'heatmap') {
    const heatmapData = inference.heatmapUsesMatrix
      ? buildHeatmapDataFromMatrix(headerRow, dataRows, inference.categoryColumnIndex, inference.valueColumnIndexes)
      : buildHeatmapDataFromTriples(
          dataRows,
          inference.heatmapXColumnIndex ?? 0,
          inference.heatmapYColumnIndex ?? 1,
          inference.heatmapValueColumnIndex ?? 2,
        );

    const xCategories = dedupe(heatmapData.map((entry) => entry[0]));
    const yCategories = dedupe(heatmapData.map((entry) => entry[1]));
    const maxValue = heatmapData.reduce((max, entry) => Math.max(max, entry[2]), 0);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: false,
      },
      xAxis: {
        ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
        show: true,
        type: 'category',
        data: xCategories,
      },
      yAxis: {
        ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
        show: true,
        type: 'category',
        data: yCategories,
      },
      visualMap: {
        show: true,
        min: 0,
        max: Math.max(1, maxValue),
        left: 'right',
        top: 'middle',
      },
      series: [
        {
          name: 'Heatmap',
          type: 'heatmap',
          coordinateSystem: 'cartesian2d',
          encode: {
            x: 0,
            y: 1,
            value: [2],
            tooltip: [0, 1, 2],
          },
          data: heatmapData,
          itemStyle: {
            borderColor: '#ffffff',
            borderWidth: 1,
          },
          label: {
            show: false,
          },
        },
      ],
    };
  }

  if (chartType === 'funnel') {
    const stageIndex = inference.funnelStageColumnIndex ?? inference.categoryColumnIndex;
    const valueIndex = inference.funnelValueColumnIndex ?? inference.valueColumnIndexes[0] ?? 1;

    const funnelData = dataRows
      .map((row) => {
        const name = cellAsString(row[stageIndex]);
        const value = toNumeric(row[valueIndex]);
        if (!name || value === null) {
          return null;
        }

        return { name, value };
      })
      .filter((item): item is { name: string; value: number } => item !== null);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: true,
      },
      xAxis: {
        ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
        show: false,
      },
      yAxis: {
        ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
        show: false,
      },
      series: [
        {
          name: 'Conversion',
          type: 'funnel',
          sort: 'descending',
          min: 0,
          max: Math.max(...funnelData.map((item) => item.value), 100),
          minSize: '0%',
          maxSize: '100%',
          gap: 2,
          label: {
            show: true,
            position: 'inside',
            formatter: '{b}: {c}',
          },
          data: funnelData,
        },
      ],
    };
  }

  if (chartType === 'gauge') {
    const valueIndex = inference.gaugeValueColumnIndex ?? inference.valueColumnIndexes[0] ?? 0;
    const firstRow = dataRows[0] ?? [];
    const rawValue = toNumeric(firstRow[valueIndex]) ?? 0;
    const gaugeName =
      firstRow.length > 1
        ? cellAsString(firstRow[inference.categoryColumnIndex]) || normalizeHeaderName(headerRow, valueIndex)
        : normalizeHeaderName(headerRow, valueIndex);

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      legend: {
        ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
        show: false,
      },
      xAxis: {
        ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
        show: false,
      },
      yAxis: {
        ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
        show: false,
      },
      series: [
        {
          name: gaugeName,
          type: 'gauge',
          min: 0,
          max: 100,
          splitNumber: 10,
          startAngle: 225,
          endAngle: -45,
          progress: {
            show: true,
          },
          pointer: {
            show: true,
          },
          axisLine: {
            lineStyle: {
              width: 12,
            },
          },
          detail: {
            show: true,
            formatter: '{value}',
            offsetCenter: ['0%', '60%'],
          },
          title: {
            show: true,
            offsetCenter: ['0%', '85%'],
          },
          data: [{ name: gaugeName, value: rawValue }],
        },
      ],
    };
  }

  if (chartType === 'singleAxis') {
    const xDimension = inference.scatterXColumnIndex ?? 0;
    const yDimension = inference.scatterYColumnIndex ?? inference.valueColumnIndexes[0] ?? 1;

    return {
      ...cloned,
      tooltip: {
        ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
        trigger: 'item',
        show: true,
      },
      xAxis: { show: false },
      yAxis: { show: false },
      singleAxis: {
        type: 'value',
        orient: 'horizontal',
        left: '10%',
        right: '10%',
        top: '50%',
      },
      series: [
        {
          name: 'Single axis points',
          type: 'effectScatter',
          coordinateSystem: 'singleAxis',
          symbolSize: 12,
          encode: {
            x: xDimension,
            y: yDimension,
            tooltip: [xDimension, yDimension],
          },
        },
      ],
    };
  }

  const categories = buildCategoryValues(dataRows, inference.categoryColumnIndex);
  const cartesianSeriesType: 'line' | 'bar' = chartType === 'bar' ? 'bar' : 'line';
  const nextSeries = inference.valueColumnIndexes.map((columnIndex) => ({
    name: normalizeHeaderName(headerRow, columnIndex),
    type: cartesianSeriesType,
    smooth: cartesianSeriesType === 'line' ? true : undefined,
    data: buildSeriesData(dataRows, columnIndex),
  }));

  return {
    ...cloned,
    tooltip: {
      ...(typeof cloned.tooltip === 'object' && cloned.tooltip ? (cloned.tooltip as Record<string, unknown>) : {}),
      trigger: 'axis',
      show: true,
    },
    legend: {
      ...(typeof cloned.legend === 'object' && cloned.legend ? (cloned.legend as Record<string, unknown>) : {}),
      show: true,
    },
    xAxis: {
      ...(typeof cloned.xAxis === 'object' && cloned.xAxis ? (cloned.xAxis as Record<string, unknown>) : {}),
      show: true,
      type: 'category',
      data: categories,
    },
    yAxis: {
      ...(typeof cloned.yAxis === 'object' && cloned.yAxis ? (cloned.yAxis as Record<string, unknown>) : {}),
      show: true,
      type: 'value',
    },
    series: nextSeries,
  };
};
