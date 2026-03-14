import type { ChartType } from '../types/echarts';

export const chartTypeLabels: Record<ChartType, string> = {
  line: 'Line',
  bar: 'Bar',
  pie: 'Pie',
  candlestick: 'Candlestick',
  scatter: 'Scatter',
  effectScatter: 'Effect Scatter',
  radar: 'Radar',
  heatmap: 'Heatmap',
  funnel: 'Funnel',
  gauge: 'Gauge',
  parallel: 'Parallel',
  polar: 'Polar',
  singleAxis: 'Single Axis',
  calendar: 'Calendar',
  geo: 'Geo',
  map: 'Map',
};

export const getChartTypeLabel = (chartType: ChartType): string => {
  return chartTypeLabels[chartType];
};
