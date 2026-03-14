import type { FieldSchema } from '../../types/editor';
import { isRadarSeries } from '../helpers/fieldBuilders';

export const radarSeriesFields: FieldSchema[] = [
  {
    key: 'series.radarIndex',
    label: 'Radar Index',
    path: 'series.$seriesIndex.radarIndex',
    control: 'number',
    defaultValue: 0,
    visibleWhen: isRadarSeries,
    complexity: 'advanced',
    group: 'Radar Mapping',
    helpText: 'Select which radar component this series uses when multiple radars exist.',
  },
  {
    key: 'series.symbol.radar',
    label: 'Symbol',
    path: 'series.$seriesIndex.symbol',
    control: 'select',
    defaultValue: 'circle',
    visibleWhen: isRadarSeries,
    group: 'Radar Style',
    helpText: 'Point symbol for each indicator value.',
    options: [
      { label: 'Circle', value: 'circle' },
      { label: 'Rect', value: 'rect' },
      { label: 'Round Rect', value: 'roundRect' },
      { label: 'Triangle', value: 'triangle' },
      { label: 'Diamond', value: 'diamond' },
      { label: 'None', value: 'none' },
    ],
  },
  {
    key: 'series.symbolSize.radar',
    label: 'Symbol Size',
    path: 'series.$seriesIndex.symbolSize',
    control: 'number',
    defaultValue: 6,
    visibleWhen: isRadarSeries,
    group: 'Radar Style',
    helpText: 'Marker size on radar vertices.',
  },
];
