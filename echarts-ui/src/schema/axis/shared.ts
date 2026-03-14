import type { EditorContext, SectionSchema } from '../../types/editor';
import {
  createAxisLabelFields,
  createAxisLineFields,
  createAxisTickFields,
  createShowField,
  createSplitLineFields,
  usesCartesianAxes,
} from '../helpers/fieldBuilders';

interface AxisSectionOptions {
  id: string;
  title: string;
  keyPrefix: 'xAxis' | 'yAxis';
  pathPrefix: string;
  arrayBindingId: 'xAxis' | 'yAxis';
  selectedIndexFromContext: (context: EditorContext) => number;
  itemLabel: string;
  defaultItem: Record<string, unknown>;
  defaultType: 'category' | 'value';
  defaultBoundaryGap: boolean;
}

const asRecord = (value: unknown): Record<string, unknown> | undefined => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
};

const getAxisType = (
  axisSource: unknown,
  selectedIndex: number,
  fallbackType: 'category' | 'value',
): string => {
  const axis = Array.isArray(axisSource) ? asRecord(axisSource[selectedIndex]) : asRecord(axisSource);
  const axisType = axis?.type;
  return typeof axisType === 'string' ? axisType : fallbackType;
};

export const createAxisSection = ({
  id,
  title,
  keyPrefix,
  pathPrefix,
  arrayBindingId,
  selectedIndexFromContext,
  itemLabel,
  defaultItem,
  defaultType,
  defaultBoundaryGap,
}: AxisSectionOptions): SectionSchema => {
  const isCategoryLikeAxis = (context: EditorContext): boolean => {
    if (!usesCartesianAxes(context)) {
      return false;
    }

    const axisSource = (context.option as Record<string, unknown>)[keyPrefix];
    const axisType = getAxisType(axisSource, selectedIndexFromContext(context), defaultType);
    return axisType === 'category';
  };

  return {
    id,
    title,
    arrayBinding: {
      id: arrayBindingId,
      path: keyPrefix,
      indexToken: `$${arrayBindingId}Index`,
      itemLabel,
      defaultItem,
      minItems: 1,
    },
    fields: [
      createShowField({
        key: `${keyPrefix}.show`,
        path: `${pathPrefix}.show`,
        defaultValue: true,
        visibleWhen: usesCartesianAxes,
        helpText: `${title} visibility (used by cartesian chart families).`,
      }),
      {
        key: `${keyPrefix}.type`,
        label: 'Type',
        path: `${pathPrefix}.type`,
        control: 'select',
        defaultValue: defaultType,
        visibleWhen: usesCartesianAxes,
        helpText: `Set ${title.toLowerCase()} scale type.`,
        options: [
          { label: 'Category', value: 'category' },
          { label: 'Value', value: 'value' },
          { label: 'Time', value: 'time' },
          { label: 'Log', value: 'log' },
        ],
      },
      {
        key: `${keyPrefix}.name`,
        label: 'Name',
        path: `${pathPrefix}.name`,
        control: 'text',
        defaultValue: '',
        visibleWhen: usesCartesianAxes,
        helpText: `Optional ${title.toLowerCase()} title.`,
      },
      {
        key: `${keyPrefix}.min`,
        label: 'Min',
        path: `${pathPrefix}.min`,
        control: 'text',
        defaultValue: '',
        visibleWhen: usesCartesianAxes,
        complexity: 'advanced',
        helpText: 'Set minimum bound (number, dataMin, etc.).',
      },
      {
        key: `${keyPrefix}.max`,
        label: 'Max',
        path: `${pathPrefix}.max`,
        control: 'text',
        defaultValue: '',
        visibleWhen: usesCartesianAxes,
        complexity: 'advanced',
        helpText: 'Set maximum bound (number, dataMax, etc.).',
      },
      {
        key: `${keyPrefix}.inverse`,
        label: 'Inverse',
        path: `${pathPrefix}.inverse`,
        control: 'checkbox',
        defaultValue: false,
        visibleWhen: usesCartesianAxes,
        complexity: 'advanced',
        helpText: `Reverse ${title.toLowerCase()} direction.`,
      },
      {
        key: `${keyPrefix}.boundaryGap`,
        label: 'Boundary Gap',
        path: `${pathPrefix}.boundaryGap`,
        control: 'checkbox',
        defaultValue: defaultBoundaryGap,
        visibleWhen: usesCartesianAxes,
        complexity: 'advanced',
        helpText: 'Add/remove edge spacing around data.',
      },
      ...createAxisLabelFields({
        keyPrefix: `${keyPrefix}.axisLabel`,
        pathPrefix: `${pathPrefix}.axisLabel`,
        visibleWhen: usesCartesianAxes,
      }),
      ...createAxisLineFields({
        keyPrefix: `${keyPrefix}.axisLine`,
        pathPrefix: `${pathPrefix}.axisLine`,
        visibleWhen: usesCartesianAxes,
      }),
      ...createAxisTickFields({
        keyPrefix: `${keyPrefix}.axisTick`,
        pathPrefix: `${pathPrefix}.axisTick`,
        visibleWhen: usesCartesianAxes,
        alignWithLabelVisibleWhen: isCategoryLikeAxis,
      }),
      ...createSplitLineFields({
        keyPrefix: `${keyPrefix}.splitLine`,
        pathPrefix: `${pathPrefix}.splitLine`,
        visibleWhen: usesCartesianAxes,
      }),
    ],
  };
};
