import type { SectionSchema } from '../../types/editor';
import {
  createAxisLabelFields,
  createAxisLineFields,
  createAxisTickFields,
  createShowField,
  createSplitLineFields,
  usesPolarCoordinates,
} from '../helpers/fieldBuilders';

export const defaultAngleAxisItem = {
  show: true,
  type: 'category',
  startAngle: 90,
  clockwise: true,
  min: '',
  max: '',
  axisLabel: {
    show: true,
  },
};

export const angleAxisSection: SectionSchema = {
  id: 'angleAxis',
  title: 'Angle Axis',
  arrayBinding: {
    id: 'angleAxis',
    path: 'angleAxis',
    indexToken: '$angleAxisIndex',
    itemLabel: 'Angle Axis',
    defaultItem: defaultAngleAxisItem,
    minItems: 0,
  },
  fields: [
    createShowField({
      key: 'angleAxis.show',
      path: 'angleAxis.$angleAxisIndex.show',
      defaultValue: true,
      visibleWhen: usesPolarCoordinates,
      helpText: 'Toggle angle axis visibility.',
    }),
    {
      key: 'angleAxis.type',
      label: 'Type',
      path: 'angleAxis.$angleAxisIndex.type',
      control: 'select',
      defaultValue: 'category',
      visibleWhen: usesPolarCoordinates,
      helpText: 'Scale type for angle axis.',
      options: [
        { label: 'Category', value: 'category' },
        { label: 'Value', value: 'value' },
        { label: 'Time', value: 'time' },
        { label: 'Log', value: 'log' },
      ],
    },
    {
      key: 'angleAxis.startAngle',
      label: 'Start Angle',
      path: 'angleAxis.$angleAxisIndex.startAngle',
      control: 'number',
      defaultValue: 90,
      visibleWhen: usesPolarCoordinates,
      complexity: 'advanced',
      helpText: 'Angle where the axis starts (degrees).',
    },
    {
      key: 'angleAxis.clockwise',
      label: 'Clockwise',
      path: 'angleAxis.$angleAxisIndex.clockwise',
      control: 'checkbox',
      defaultValue: true,
      visibleWhen: usesPolarCoordinates,
      complexity: 'advanced',
      helpText: 'Whether angle increases clockwise.',
    },
    {
      key: 'angleAxis.min',
      label: 'Min',
      path: 'angleAxis.$angleAxisIndex.min',
      control: 'text',
      defaultValue: '',
      visibleWhen: usesPolarCoordinates,
      complexity: 'advanced',
      helpText: 'Minimum axis value (number or keyword).',
    },
    {
      key: 'angleAxis.max',
      label: 'Max',
      path: 'angleAxis.$angleAxisIndex.max',
      control: 'text',
      defaultValue: '',
      visibleWhen: usesPolarCoordinates,
      complexity: 'advanced',
      helpText: 'Maximum axis value (number or keyword).',
    },
    ...createAxisLabelFields({
      keyPrefix: 'angleAxis.axisLabel',
      pathPrefix: 'angleAxis.$angleAxisIndex.axisLabel',
      visibleWhen: usesPolarCoordinates,
    }),
    ...createAxisLineFields({
      keyPrefix: 'angleAxis.axisLine',
      pathPrefix: 'angleAxis.$angleAxisIndex.axisLine',
      visibleWhen: usesPolarCoordinates,
    }),
    ...createAxisTickFields({
      keyPrefix: 'angleAxis.axisTick',
      pathPrefix: 'angleAxis.$angleAxisIndex.axisTick',
      visibleWhen: usesPolarCoordinates,
      alignWithLabelVisibleWhen: (context) => {
        if (!usesPolarCoordinates(context)) {
          return false;
        }

        const source = context.option.angleAxis;
        const axis = Array.isArray(source) ? source[context.selectedAngleAxisIndex] : source;
        const axisType = axis && typeof axis === 'object' ? (axis as Record<string, unknown>).type : undefined;
        return typeof axisType === 'string' ? axisType === 'category' : true;
      },
    }),
    ...createSplitLineFields({
      keyPrefix: 'angleAxis.splitLine',
      pathPrefix: 'angleAxis.$angleAxisIndex.splitLine',
      visibleWhen: usesPolarCoordinates,
    }),
  ],
};
