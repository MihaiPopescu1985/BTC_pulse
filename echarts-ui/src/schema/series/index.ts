import type { SectionSchema } from '../../types/editor';
import { barSeriesFields } from './bar';
import { candlestickSeriesFields } from './candlestick';
import { seriesCommonFields } from './common';
import { seriesEncodeFields } from './encode';
import { effectScatterSeriesFields } from './effectScatter';
import { funnelSeriesFields } from './funnel';
import { gaugeSeriesFields } from './gauge';
import { heatmapSeriesFields } from './heatmap';
import { lineSeriesFields } from './line';
import { mapSeriesFields } from './map';
import { parallelSeriesFields } from './parallel';
import { pieSeriesFields } from './pie';
import { radarSeriesFields } from './radar';
import { scatterSeriesFields } from './scatter';

export const seriesSection: SectionSchema = {
  id: 'series',
  title: 'Selected Series',
  fields: [
    ...seriesCommonFields,
    ...seriesEncodeFields,
    ...lineSeriesFields,
    ...barSeriesFields,
    ...pieSeriesFields,
    ...candlestickSeriesFields,
    ...scatterSeriesFields,
    ...effectScatterSeriesFields,
    ...radarSeriesFields,
    ...heatmapSeriesFields,
    ...funnelSeriesFields,
    ...gaugeSeriesFields,
    ...parallelSeriesFields,
    ...mapSeriesFields,
  ],
};
