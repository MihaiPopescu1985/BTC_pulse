import type { SectionSchema } from '../../types/editor';
import { usesCartesianAxes } from '../helpers/fieldBuilders';
import { createAxisSection } from './shared';

export const defaultXAxisItem = {
  show: true,
  type: 'category',
  name: '',
  boundaryGap: true,
};

const baseSection = createAxisSection({
  id: 'xAxis',
  title: 'X Axis',
  keyPrefix: 'xAxis',
  pathPrefix: 'xAxis.$xAxisIndex',
  arrayBindingId: 'xAxis',
  selectedIndexFromContext: (context) => context.selectedXAxisIndex,
  itemLabel: 'X Axis',
  defaultItem: defaultXAxisItem,
  defaultType: 'category',
  defaultBoundaryGap: true,
});

export const xAxisSection: SectionSchema = {
  ...baseSection,
  fields: [
    ...baseSection.fields,
    {
      key: 'xAxis.data',
      label: 'Data (JSON)',
      path: 'xAxis.$xAxisIndex.data',
      control: 'textarea',
      textareaMode: 'json',
      defaultValue: ['Jan', 'Feb', 'Mar'],
      placeholder: '["Jan", "Feb", "Mar"]',
      visibleWhen: usesCartesianAxes,
      complexity: 'advanced',
      helpText: 'Optional explicit category values if not relying on dataset mapping.',
    },
  ],
};
