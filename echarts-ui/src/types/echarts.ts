import type { EChartsOption } from 'echarts';

export type ChartType =
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
  | 'singleAxis'
  | 'calendar'
  | 'geo'
  | 'map';

export type EditorOption = EChartsOption;
