import { describe, expect, it } from 'vitest';
import type { SectionSchema } from '../types/editor';
import {
  buildSchemaSearchIndex,
  filterSchemaSearchIndex,
  makeSchemaFieldSearchId,
  normalizeFieldPathForSearch,
} from './schemaSearch';

const mockSchema: SectionSchema[] = [
  {
    id: 'series',
    title: 'Series',
    fields: [
      {
        key: 'series.lineStyle.width',
        label: 'Line Width',
        path: 'series.$seriesIndex.lineStyle.width',
        control: 'number',
        keywords: ['stroke', 'thickness'],
        description: 'Controls rendered line stroke thickness.',
        helpText: 'Line width in pixels.',
      },
    ],
  },
  {
    id: 'tooltip',
    title: 'Tooltip',
    fields: [
      {
        key: 'tooltip.trigger',
        label: 'Trigger',
        path: 'tooltip.trigger',
        control: 'select',
        description: 'How tooltip is triggered.',
      },
    ],
  },
];

describe('schemaSearch utils', () => {
  it('builds flattened search index entries for all schema fields', () => {
    const index = buildSchemaSearchIndex(mockSchema);

    expect(index).toHaveLength(2);
    expect(index[0]).toMatchObject({
      id: makeSchemaFieldSearchId('series', 'series.lineStyle.width'),
      sectionId: 'series',
      sectionTitle: 'Series',
      displayPath: 'series.lineStyle.width',
    });
  });

  it('filters case-insensitively by label/path/description text', () => {
    const index = buildSchemaSearchIndex(mockSchema);
    const byLabel = filterSchemaSearchIndex(index, 'line width');
    const byPath = filterSchemaSearchIndex(index, 'SERIES.LINESTYLE.WIDTH');
    const byDescription = filterSchemaSearchIndex(index, 'rendered line stroke');

    expect(byLabel).toHaveLength(1);
    expect(byPath).toHaveLength(1);
    expect(byDescription).toHaveLength(1);
    expect(byPath[0].field.key).toBe('series.lineStyle.width');
  });

  it('matches keyword metadata', () => {
    const index = buildSchemaSearchIndex(mockSchema);
    const matches = filterSchemaSearchIndex(index, 'thickness');

    expect(matches).toHaveLength(1);
    expect(matches[0].field.key).toBe('series.lineStyle.width');
  });

  it('normalizes tokenized schema paths for discoverable path search', () => {
    expect(normalizeFieldPathForSearch('series.$seriesIndex.lineStyle.width')).toBe('series.lineStyle.width');
    expect(normalizeFieldPathForSearch('xAxis.$xAxisIndex.axisLabel.rotate')).toBe('xAxis.axisLabel.rotate');
  });
});

