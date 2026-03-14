import type { SectionSchema } from '../../types/editor';
import type { EditorContext } from '../../types/editor';
import { usesCartesianAxes } from '../helpers/fieldBuilders';

const asRecord = (value: unknown): Record<string, unknown> | undefined => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  return undefined;
};

const getBrushType = (context: EditorContext): string | null => {
  const brush = asRecord(context.option.brush);
  const brushType = brush?.brushType;

  if (typeof brushType === 'string') {
    return brushType;
  }

  return null;
};

const isSelectionBrushType = (context: EditorContext): boolean => {
  if (!usesCartesianAxes(context)) {
    return false;
  }

  const brushType = getBrushType(context);
  if (!brushType) {
    return true;
  }

  return brushType === 'rect' || brushType === 'polygon' || brushType === 'lineX' || brushType === 'lineY';
};

export const brushSection: SectionSchema = {
  id: 'brush',
  title: 'Brush',
  fields: [
    {
      key: 'brush.toolbox',
      label: 'Toolbox Buttons',
      path: 'brush.toolbox',
      control: 'textarea',
      valueEditor: 'string-array',
      defaultValue: ['rect', 'polygon', 'keep', 'clear'],
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Enable brush toolbox controls (one tool per line).',
    },
    {
      key: 'brush.brushType',
      label: 'Brush Type',
      path: 'brush.brushType',
      control: 'select',
      defaultValue: 'rect',
      visibleWhen: usesCartesianAxes,
      helpText: 'Default brush interaction mode.',
      options: [
        { label: 'Rect', value: 'rect' },
        { label: 'Polygon', value: 'polygon' },
        { label: 'Line X', value: 'lineX' },
        { label: 'Line Y', value: 'lineY' },
        { label: 'Keep', value: 'keep' },
        { label: 'Clear', value: 'clear' },
      ],
    },
    {
      key: 'brush.xAxisIndex',
      label: 'X Axis Indexes',
      path: 'brush.xAxisIndex',
      control: 'textarea',
      valueEditor: 'number-array',
      defaultValue: [0],
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Target xAxis indexes for brushing (one number per line).',
    },
    {
      key: 'brush.yAxisIndex',
      label: 'Y Axis Indexes',
      path: 'brush.yAxisIndex',
      control: 'textarea',
      valueEditor: 'number-array',
      defaultValue: [0],
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Target yAxis indexes for brushing (one number per line).',
    },
    {
      key: 'brush.brushLink',
      label: 'Brush Link (JSON)',
      path: 'brush.brushLink',
      control: 'textarea',
      textareaMode: 'json',
      defaultValue: [],
      complexity: 'expert',
      visibleWhen: usesCartesianAxes,
      placeholder: '[0, 1] or "all"',
      helpText: 'Link brush selections across series or coordinate systems.',
    },
    {
      key: 'brush.brushMode',
      label: 'Brush Mode',
      path: 'brush.brushMode',
      control: 'select',
      defaultValue: 'single',
      complexity: 'advanced',
      visibleWhen: isSelectionBrushType,
      helpText: 'Single keeps one selection, multiple allows many selections.',
      options: [
        { label: 'Single', value: 'single' },
        { label: 'Multiple', value: 'multiple' },
      ],
    },
    {
      key: 'brush.transformable',
      label: 'Transformable',
      path: 'brush.transformable',
      control: 'checkbox',
      defaultValue: true,
      complexity: 'advanced',
      visibleWhen: isSelectionBrushType,
      helpText: 'Allow resizing/moving brush areas after selection.',
    },
    {
      key: 'brush.throttleType',
      label: 'Throttle Type',
      path: 'brush.throttleType',
      control: 'select',
      defaultValue: 'fixRate',
      complexity: 'advanced',
      visibleWhen: isSelectionBrushType,
      helpText: 'Choose how brush event throttling is applied.',
      options: [
        { label: 'Fix Rate', value: 'fixRate' },
        { label: 'Debounce', value: 'debounce' },
      ],
    },
    {
      key: 'brush.throttleDelay',
      label: 'Throttle Delay',
      path: 'brush.throttleDelay',
      control: 'number',
      defaultValue: 0,
      complexity: 'advanced',
      visibleWhen: isSelectionBrushType,
      helpText: 'Delay in milliseconds for brush event throttling.',
    },
    {
      key: 'brush.removeOnClick',
      label: 'Remove On Click',
      path: 'brush.removeOnClick',
      control: 'checkbox',
      defaultValue: true,
      complexity: 'advanced',
      visibleWhen: isSelectionBrushType,
      helpText: 'Clear the active brush selection when clicking blank area.',
    },
    {
      key: 'brush.inBrush.colorAlpha',
      label: 'In Brush Alpha',
      path: 'brush.inBrush.colorAlpha',
      control: 'number',
      defaultValue: 1,
      complexity: 'advanced',
      group: 'In/Out Brush',
      visibleWhen: isSelectionBrushType,
      helpText: 'Opacity multiplier for items inside brush selection (0 to 1).',
    },
    {
      key: 'brush.outOfBrush.colorAlpha',
      label: 'Out Of Brush Alpha',
      path: 'brush.outOfBrush.colorAlpha',
      control: 'number',
      defaultValue: 0.1,
      complexity: 'advanced',
      group: 'In/Out Brush',
      visibleWhen: isSelectionBrushType,
      helpText: 'Opacity multiplier for items outside brush selection (0 to 1).',
    },
  ],
};
