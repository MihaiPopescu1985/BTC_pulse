import type { SectionSchema } from '../../types/editor';
import { createPositionFields, isParallelSeries } from '../helpers/fieldBuilders';

export const defaultParallelItem = {
  left: '8%',
  right: '10%',
  top: '15%',
  bottom: '15%',
  parallelAxisDefault: {
    type: 'value',
    nameLocation: 'end',
  },
};

export const parallelSection: SectionSchema = {
  id: 'parallel',
  title: 'Parallel',
  arrayBinding: {
    id: 'parallel',
    path: 'parallel',
    indexToken: '$parallelIndex',
    itemLabel: 'Parallel',
    defaultItem: defaultParallelItem,
    minItems: 0,
  },
  fields: [
    ...createPositionFields({
      keyPrefix: 'parallel',
      pathPrefix: 'parallel.$parallelIndex',
      include: ['left', 'right', 'top', 'bottom'],
      defaultValues: { left: '8%', right: '10%', top: '15%', bottom: '15%' },
      visibleWhen: isParallelSeries,
      helpText: 'Adjust the selected parallel coordinate container bounds.',
    }),
    {
      key: 'parallel.parallelAxisDefault',
      label: 'Axis Default (JSON)',
      path: 'parallel.$parallelIndex.parallelAxisDefault',
      control: 'textarea',
      textareaMode: 'json',
      defaultValue: defaultParallelItem.parallelAxisDefault,
      visibleWhen: isParallelSeries,
      complexity: 'advanced',
      helpText: 'Fallback defaults for parallel axes.',
      placeholder: '{"type":"value","nameLocation":"end"}',
    },
  ],
};
