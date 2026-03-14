import type { SectionSchema } from '../../types/editor';
import {
  createAxisLabelFields,
  createAxisLineFields,
  createAxisTickFields,
  createShowField,
  createSplitLineFields,
  usesPolarCoordinates,
} from '../helpers/fieldBuilders';

export const defaultRadiusAxisItem = {
  show: true,
  type: 'value',
  min: '',
  max: '',
  name: '',
  axisLabel: {
    show: true,
  },
};

export const radiusAxisSection: SectionSchema = {
  id: 'radiusAxis',
  title: 'Radius Axis',
  arrayBinding: {
    id: 'radiusAxis',
    path: 'radiusAxis',
    indexToken: '$radiusAxisIndex',
    itemLabel: 'Radius Axis',
    defaultItem: defaultRadiusAxisItem,
    minItems: 0,
  },
  fields: [
    createShowField({
      key: 'radiusAxis.show',
      path: 'radiusAxis.$radiusAxisIndex.show',
      defaultValue: true,
      visibleWhen: usesPolarCoordinates,
      helpText: 'Toggle radius axis visibility.',
    }),
    {
      key: 'radiusAxis.type',
      label: 'Type',
      path: 'radiusAxis.$radiusAxisIndex.type',
      control: 'select',
      defaultValue: 'value',
      visibleWhen: usesPolarCoordinates,
      helpText: 'Scale type for radius axis.',
      options: [
        { label: 'Value', value: 'value' },
        { label: 'Category', value: 'category' },
        { label: 'Time', value: 'time' },
        { label: 'Log', value: 'log' },
      ],
    },
    {
      key: 'radiusAxis.min',
      label: 'Min',
      path: 'radiusAxis.$radiusAxisIndex.min',
      control: 'text',
      defaultValue: '',
      visibleWhen: usesPolarCoordinates,
      complexity: 'advanced',
      helpText: 'Minimum radius axis value.',
    },
    {
      key: 'radiusAxis.max',
      label: 'Max',
      path: 'radiusAxis.$radiusAxisIndex.max',
      control: 'text',
      defaultValue: '',
      visibleWhen: usesPolarCoordinates,
      complexity: 'advanced',
      helpText: 'Maximum radius axis value.',
    },
    {
      key: 'radiusAxis.name',
      label: 'Name',
      path: 'radiusAxis.$radiusAxisIndex.name',
      control: 'text',
      defaultValue: '',
      visibleWhen: usesPolarCoordinates,
      complexity: 'advanced',
      helpText: 'Optional radius axis name.',
    },
    ...createAxisLabelFields({
      keyPrefix: 'radiusAxis.axisLabel',
      pathPrefix: 'radiusAxis.$radiusAxisIndex.axisLabel',
      visibleWhen: usesPolarCoordinates,
    }),
    ...createAxisLineFields({
      keyPrefix: 'radiusAxis.axisLine',
      pathPrefix: 'radiusAxis.$radiusAxisIndex.axisLine',
      visibleWhen: usesPolarCoordinates,
    }),
    ...createAxisTickFields({
      keyPrefix: 'radiusAxis.axisTick',
      pathPrefix: 'radiusAxis.$radiusAxisIndex.axisTick',
      visibleWhen: usesPolarCoordinates,
      alignWithLabelVisibleWhen: (context) => {
        if (!usesPolarCoordinates(context)) {
          return false;
        }

        const source = context.option.radiusAxis;
        const axis = Array.isArray(source) ? source[context.selectedRadiusAxisIndex] : source;
        const axisType = axis && typeof axis === 'object' ? (axis as Record<string, unknown>).type : undefined;
        return typeof axisType === 'string' ? axisType === 'category' : false;
      },
    }),
    ...createSplitLineFields({
      keyPrefix: 'radiusAxis.splitLine',
      pathPrefix: 'radiusAxis.$radiusAxisIndex.splitLine',
      visibleWhen: usesPolarCoordinates,
    }),
  ],
};
