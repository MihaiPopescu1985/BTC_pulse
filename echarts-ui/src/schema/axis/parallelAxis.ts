import type { SectionSchema } from '../../types/editor';
import { isParallelSeries } from '../helpers/fieldBuilders';

export const defaultParallelAxisItem = {
  dim: 0,
  name: 'Dimension',
  type: 'value',
  min: '',
  max: '',
  inverse: false,
};

export const parallelAxisSection: SectionSchema = {
  id: 'parallelAxis',
  title: 'Parallel Axis',
  arrayBinding: {
    id: 'parallelAxis',
    path: 'parallelAxis',
    indexToken: '$parallelAxisIndex',
    itemLabel: 'Parallel Axis',
    defaultItem: defaultParallelAxisItem,
    minItems: 0,
  },
  fields: [
    {
      key: 'parallelAxis.dim',
      label: 'Dim',
      path: 'parallelAxis.$parallelAxisIndex.dim',
      control: 'number',
      defaultValue: 0,
      visibleWhen: isParallelSeries,
      helpText: 'Dimension index bound to this parallel axis.',
    },
    {
      key: 'parallelAxis.name',
      label: 'Name',
      path: 'parallelAxis.$parallelAxisIndex.name',
      control: 'text',
      defaultValue: 'Dimension',
      visibleWhen: isParallelSeries,
      helpText: 'Display name for this parallel axis.',
    },
    {
      key: 'parallelAxis.type',
      label: 'Type',
      path: 'parallelAxis.$parallelAxisIndex.type',
      control: 'select',
      defaultValue: 'value',
      visibleWhen: isParallelSeries,
      helpText: 'Scale type for this dimension axis.',
      options: [
        { label: 'Value', value: 'value' },
        { label: 'Category', value: 'category' },
        { label: 'Time', value: 'time' },
        { label: 'Log', value: 'log' },
      ],
    },
    {
      key: 'parallelAxis.min',
      label: 'Min',
      path: 'parallelAxis.$parallelAxisIndex.min',
      control: 'text',
      defaultValue: '',
      visibleWhen: isParallelSeries,
      complexity: 'advanced',
      helpText: 'Optional minimum bound for this axis.',
    },
    {
      key: 'parallelAxis.max',
      label: 'Max',
      path: 'parallelAxis.$parallelAxisIndex.max',
      control: 'text',
      defaultValue: '',
      visibleWhen: isParallelSeries,
      complexity: 'advanced',
      helpText: 'Optional maximum bound for this axis.',
    },
    {
      key: 'parallelAxis.inverse',
      label: 'Inverse',
      path: 'parallelAxis.$parallelAxisIndex.inverse',
      control: 'checkbox',
      defaultValue: false,
      visibleWhen: isParallelSeries,
      complexity: 'advanced',
      helpText: 'Reverse axis direction.',
    },
  ],
};
