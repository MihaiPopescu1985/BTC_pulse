import type { SectionSchema } from '../../types/editor';

export const defaultDatasetItem = {
  sourceHeader: true,
  source: [
    ['category', 'value'],
    ['A', 120],
  ],
};

export const datasetSection: SectionSchema = {
  id: 'dataset',
  title: 'Dataset Config',
  arrayBinding: {
    id: 'dataset',
    path: 'dataset',
    indexToken: '$datasetIndex',
    itemLabel: 'Dataset',
    defaultItem: defaultDatasetItem,
    minItems: 1,
  },
  fields: [
    {
      key: 'dataset.sourceHeader',
      label: 'Source Header',
      path: 'dataset.$datasetIndex.sourceHeader',
      control: 'checkbox',
      defaultValue: true,
      helpText: 'Whether first dataset row should be treated as headers.',
    },
    {
      key: 'dataset.source',
      label: 'Source (JSON Fallback)',
      path: 'dataset.$datasetIndex.source',
      control: 'textarea',
      textareaMode: 'json',
      defaultValue: defaultDatasetItem.source,
      complexity: 'expert',
      placeholder: '[["category","value"],["A",120]]',
      helpText: 'Raw dataset source fallback for complex structures.',
    },
  ],
};
