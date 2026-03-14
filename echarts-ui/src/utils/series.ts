import type { ChartType, EditorOption } from '../types/echarts';
import { cloneValue } from './value';

export type EditorSeries = Record<string, unknown>;

const asRecord = (value: unknown): EditorSeries => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as EditorSeries;
  }
  return {};
};

const asSeriesArray = (value: unknown): EditorSeries[] => {
  if (Array.isArray(value)) {
    return value.map((item) => asRecord(item));
  }

  if (value && typeof value === 'object') {
    return [asRecord(value)];
  }

  return [];
};

const getCoordinateSystem = (series: EditorSeries | undefined): string | null => {
  if (!series) {
    return null;
  }

  return typeof series.coordinateSystem === 'string' ? series.coordinateSystem : null;
};

export const getSeriesList = (option: EditorOption): EditorSeries[] => asSeriesArray(option.series);

export const getSeriesType = (series: EditorSeries | undefined): ChartType | null => {
  if (!series) {
    return null;
  }

  const type = series.type;
  return type === 'line' ||
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
    ? type
    : null;
};

const getSeriesChartFamily = (series: EditorSeries | undefined): ChartType | null => {
  const type = getSeriesType(series);
  if (!type) {
    return null;
  }

  const coordinateSystem = getCoordinateSystem(series);

  if ((type === 'line' || type === 'bar' || type === 'scatter' || type === 'effectScatter') && coordinateSystem === 'polar') {
    return 'polar';
  }

  if ((type === 'heatmap' || type === 'scatter' || type === 'effectScatter') && coordinateSystem === 'calendar') {
    return 'calendar';
  }

  if ((type === 'scatter' || type === 'effectScatter') && coordinateSystem === 'geo') {
    return 'geo';
  }

  if ((type === 'scatter' || type === 'effectScatter') && coordinateSystem === 'singleAxis') {
    return 'singleAxis';
  }

  return type;
};

export const getCurrentChartType = (option: EditorOption, selectedSeriesIndex: number): ChartType => {
  const seriesList = getSeriesList(option);
  const selected = seriesList[selectedSeriesIndex];
  return getSeriesChartFamily(selected) ?? getSeriesChartFamily(seriesList[0]) ?? 'line';
};

export const ensureSeriesArray = (option: EditorOption): EditorOption => {
  const normalizedSeries = getSeriesList(option);
  if (Array.isArray(option.series) && option.series.length === normalizedSeries.length) {
    return option;
  }

  return {
    ...cloneValue(option),
    series: normalizedSeries,
  };
};

export const createDefaultSeries = (chartType: ChartType, index: number): EditorSeries => {
  if (chartType === 'pie') {
    return {
      name: `Series ${index + 1}`,
      type: 'pie',
      radius: '50%',
      data: [
        { value: 40, name: 'A' },
        { value: 32, name: 'B' },
        { value: 28, name: 'C' },
      ],
    };
  }

  if (chartType === 'bar') {
    return {
      name: `Series ${index + 1}`,
      type: 'bar',
      barWidth: 24,
      data: [120, 200, 150, 80],
    };
  }

  if (chartType === 'candlestick') {
    return {
      name: `Series ${index + 1}`,
      type: 'candlestick',
      encode: {
        x: 0,
        y: [1, 2, 3, 4],
      },
      itemStyle: {
        color: '#26a69a',
        color0: '#ef5350',
        borderColor: '#26a69a',
        borderColor0: '#ef5350',
      },
    };
  }

  if (chartType === 'scatter') {
    return {
      name: `Series ${index + 1}`,
      type: 'scatter',
      symbol: 'circle',
      symbolSize: 14,
      encode: {
        x: 0,
        y: 1,
        tooltip: [0, 1],
      },
      itemStyle: {
        color: '#3b82f6',
        opacity: 0.85,
      },
    };
  }

  if (chartType === 'effectScatter') {
    return {
      name: `Series ${index + 1}`,
      type: 'effectScatter',
      coordinateSystem: 'cartesian2d',
      symbol: 'circle',
      symbolSize: 14,
      rippleEffect: {
        scale: 2.5,
        brushType: 'stroke',
      },
      encode: {
        x: 0,
        y: 1,
        tooltip: [0, 1],
      },
      itemStyle: {
        color: '#16a34a',
        opacity: 0.9,
      },
    };
  }

  if (chartType === 'radar') {
    return {
      name: `Series ${index + 1}`,
      type: 'radar',
      symbol: 'circle',
      symbolSize: 6,
      data: [
        {
          name: `Series ${index + 1}`,
          value: [72, 88, 64],
        },
      ],
      areaStyle: {
        opacity: 0.18,
      },
      lineStyle: {
        width: 2,
        type: 'solid',
      },
    };
  }

  if (chartType === 'heatmap') {
    return {
      name: `Series ${index + 1}`,
      type: 'heatmap',
      coordinateSystem: 'cartesian2d',
      encode: {
        x: 0,
        y: 1,
        value: [2],
      },
      data: [
        [0, 0, 5],
        [0, 1, 3],
        [1, 0, 4],
        [1, 1, 8],
      ],
    };
  }

  if (chartType === 'funnel') {
    return {
      name: `Series ${index + 1}`,
      type: 'funnel',
      sort: 'descending',
      min: 0,
      max: 100,
      minSize: '0%',
      maxSize: '100%',
      gap: 2,
      label: {
        show: true,
        position: 'inside',
      },
      data: [
        { name: 'Visit', value: 100 },
        { name: 'Signup', value: 70 },
        { name: 'Purchase', value: 35 },
      ],
    };
  }

  if (chartType === 'gauge') {
    return {
      name: `Series ${index + 1}`,
      type: 'gauge',
      min: 0,
      max: 100,
      splitNumber: 10,
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
      data: [{ value: 68, name: `Series ${index + 1}` }],
    };
  }

  if (chartType === 'parallel') {
    return {
      name: `Series ${index + 1}`,
      type: 'parallel',
      smooth: false,
      progressive: 200,
      lineStyle: {
        width: 1,
      },
      data: [
        [12, 55, 89, 33],
        [18, 61, 72, 48],
        [24, 68, 91, 54],
      ],
    };
  }

  if (chartType === 'polar') {
    return {
      name: `Series ${index + 1}`,
      type: 'bar',
      coordinateSystem: 'polar',
      data: [1.2, 2.1, 3.3, 2.5, 1.9],
      roundCap: true,
    };
  }

  if (chartType === 'calendar') {
    return {
      name: `Series ${index + 1}`,
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: [
        ['2026-03-01', 12],
        ['2026-03-02', 20],
        ['2026-03-03', 15],
      ],
    };
  }

  if (chartType === 'geo') {
    return {
      name: `Series ${index + 1}`,
      type: 'effectScatter',
      coordinateSystem: 'geo',
      symbolSize: 10,
      rippleEffect: {
        scale: 3,
        brushType: 'stroke',
      },
      data: [
        { name: 'Point 1', value: [13.405, 52.52, 40] },
        { name: 'Point 2', value: [-0.1276, 51.5072, 32] },
      ],
    };
  }

  if (chartType === 'singleAxis') {
    return {
      name: `Series ${index + 1}`,
      type: 'effectScatter',
      coordinateSystem: 'singleAxis',
      symbol: 'circle',
      symbolSize: 14,
      rippleEffect: {
        scale: 2.5,
        brushType: 'stroke',
      },
      encode: {
        x: 0,
        y: 1,
        tooltip: [0, 1],
      },
      data: [
        [0, 12],
        [1, 20],
        [2, 15],
      ],
    };
  }

  if (chartType === 'map') {
    return {
      name: `Series ${index + 1}`,
      type: 'map',
      map: 'world-lite',
      roam: true,
      label: {
        show: false,
      },
      itemStyle: {
        areaColor: '#dbeafe',
        borderColor: '#64748b',
      },
      data: [{ name: 'World', value: 72 }],
    };
  }

  return {
    name: `Series ${index + 1}`,
    type: 'line',
    smooth: false,
    data: [120, 200, 150, 80],
  };
};

export const getSeriesDisplayName = (series: EditorSeries, index: number): string => {
  const name = typeof series.name === 'string' && series.name.trim() ? series.name : `Series ${index + 1}`;
  const type = getSeriesType(series) ?? 'unknown';
  return `${name} (${type})`;
};
