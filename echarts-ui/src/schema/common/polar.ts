import type { SectionSchema } from '../../types/editor';
import { usesPolarCoordinates } from '../helpers/fieldBuilders';

export const defaultPolarItem = {
  center: ['50%', '55%'],
  radius: '70%',
};

export const polarSection: SectionSchema = {
  id: 'polar',
  title: 'Polar',
  arrayBinding: {
    id: 'polar',
    path: 'polar',
    indexToken: '$polarIndex',
    itemLabel: 'Polar',
    defaultItem: defaultPolarItem,
    minItems: 0,
  },
  fields: [
    {
      key: 'polar.center',
      label: 'Center',
      path: 'polar.$polarIndex.center',
      control: 'text',
      valueEditor: 'tuple',
      tupleLabels: ['Center X', 'Center Y'],
      defaultValue: ['50%', '55%'],
      visibleWhen: usesPolarCoordinates,
      helpText: 'Center position of the selected polar coordinate system.',
    },
    {
      key: 'polar.radius',
      label: 'Radius',
      path: 'polar.$polarIndex.radius',
      control: 'text',
      defaultValue: '70%',
      visibleWhen: usesPolarCoordinates,
      helpText: 'Outer radius for the selected polar coordinate system.',
      placeholder: '70% / ["30%", "70%"]',
    },
  ],
};
