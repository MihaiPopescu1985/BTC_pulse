import type { SectionSchema } from '../../types/editor';
import type { EditorContext } from '../../types/editor';
import { usesCartesianAxes } from '../helpers/fieldBuilders';

const asRecord = (value: unknown): Record<string, unknown> | undefined => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  return undefined;
};

const getAxisPointerType = (context: EditorContext): string => {
  const axisPointer = asRecord(context.option.axisPointer);
  const type = axisPointer?.type;

  if (typeof type === 'string') {
    return type;
  }

  return 'line';
};

const isLineOrCross = (context: EditorContext): boolean => {
  if (!usesCartesianAxes(context)) {
    return false;
  }

  const type = getAxisPointerType(context);
  return type === 'line' || type === 'cross';
};

const isCross = (context: EditorContext): boolean => {
  if (!usesCartesianAxes(context)) {
    return false;
  }

  return getAxisPointerType(context) === 'cross';
};

const isShadow = (context: EditorContext): boolean => {
  if (!usesCartesianAxes(context)) {
    return false;
  }

  return getAxisPointerType(context) === 'shadow';
};

export const axisPointerSection: SectionSchema = {
  id: 'axisPointer',
  title: 'Axis Pointer',
  fields: [
    {
      key: 'axisPointer.show',
      label: 'Show',
      path: 'axisPointer.show',
      control: 'checkbox',
      defaultValue: false,
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Show global axis pointer interaction hints.',
    },
    {
      key: 'axisPointer.type',
      label: 'Type',
      path: 'axisPointer.type',
      control: 'select',
      defaultValue: 'line',
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Pointer shape for axis interactions.',
      options: [
        { label: 'Line', value: 'line' },
        { label: 'Shadow', value: 'shadow' },
        { label: 'Cross', value: 'cross' },
      ],
    },
    {
      key: 'axisPointer.snap',
      label: 'Snap',
      path: 'axisPointer.snap',
      control: 'checkbox',
      defaultValue: false,
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Snap axis pointer to nearest data point.',
    },
    {
      key: 'axisPointer.triggerTooltip',
      label: 'Trigger Tooltip',
      path: 'axisPointer.triggerTooltip',
      control: 'checkbox',
      defaultValue: true,
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Show tooltip when axis pointer is active.',
    },
    {
      key: 'axisPointer.triggerEmphasis',
      label: 'Trigger Emphasis',
      path: 'axisPointer.triggerEmphasis',
      control: 'checkbox',
      defaultValue: true,
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Apply emphasis states while axis pointer is active.',
    },
    {
      key: 'axisPointer.value',
      label: 'Value',
      path: 'axisPointer.value',
      control: 'text',
      defaultValue: '',
      complexity: 'advanced',
      placeholder: '120 / Jan / 2026-03-01',
      visibleWhen: usesCartesianAxes,
      helpText: 'Set a fixed axis pointer value.',
    },
    {
      key: 'axisPointer.status',
      label: 'Status',
      path: 'axisPointer.status',
      control: 'select',
      defaultValue: 'show',
      complexity: 'advanced',
      visibleWhen: usesCartesianAxes,
      helpText: 'Initial axis pointer visibility status.',
      options: [
        { label: 'Show', value: 'show' },
        { label: 'Hide', value: 'hide' },
      ],
    },
    {
      key: 'axisPointer.handle.show',
      label: 'Handle Show',
      path: 'axisPointer.handle.show',
      control: 'checkbox',
      defaultValue: false,
      complexity: 'advanced',
      group: 'Handle',
      visibleWhen: usesCartesianAxes,
      helpText: 'Show draggable handle for touch interactions.',
    },
    {
      key: 'axisPointer.handle.size',
      label: 'Handle Size',
      path: 'axisPointer.handle.size',
      control: 'text',
      defaultValue: 45,
      complexity: 'advanced',
      group: 'Handle',
      visibleWhen: usesCartesianAxes,
      placeholder: '45 / 120%',
      helpText: 'Handle size in pixels or percent.',
    },
    {
      key: 'axisPointer.handle.margin',
      label: 'Handle Margin',
      path: 'axisPointer.handle.margin',
      control: 'number',
      defaultValue: 40,
      complexity: 'advanced',
      group: 'Handle',
      visibleWhen: usesCartesianAxes,
      helpText: 'Distance between handle and axis line in pixels.',
    },
    {
      key: 'axisPointer.handle.color',
      label: 'Handle Color',
      path: 'axisPointer.handle.color',
      control: 'text',
      defaultValue: '#9ca3af',
      complexity: 'advanced',
      group: 'Handle',
      visibleWhen: usesCartesianAxes,
      placeholder: '#9ca3af / rgba(...)',
      helpText: 'Handle color.',
    },
    {
      key: 'axisPointer.handle.throttle',
      label: 'Handle Throttle',
      path: 'axisPointer.handle.throttle',
      control: 'number',
      defaultValue: 40,
      complexity: 'expert',
      group: 'Handle',
      visibleWhen: usesCartesianAxes,
      helpText: 'Throttle drag updates in milliseconds.',
    },
    {
      key: 'axisPointer.label.show',
      label: 'Label Show',
      path: 'axisPointer.label.show',
      control: 'checkbox',
      defaultValue: true,
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      helpText: 'Show pointer label with current axis value.',
    },
    {
      key: 'axisPointer.label.formatter',
      label: 'Label Formatter',
      path: 'axisPointer.label.formatter',
      control: 'textarea',
      textareaMode: 'plain',
      defaultValue: '',
      placeholder: '{value}',
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      helpText: 'Optional formatter for axis pointer label text.',
    },
    {
      key: 'axisPointer.label.margin',
      label: 'Label Margin',
      path: 'axisPointer.label.margin',
      control: 'number',
      defaultValue: 8,
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      helpText: 'Margin between label and pointer line.',
    },
    {
      key: 'axisPointer.label.precision',
      label: 'Label Precision',
      path: 'axisPointer.label.precision',
      control: 'number',
      defaultValue: 2,
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      helpText: 'Decimal precision for numeric pointer labels.',
    },
    {
      key: 'axisPointer.label.backgroundColor',
      label: 'Label Background Color',
      path: 'axisPointer.label.backgroundColor',
      control: 'text',
      defaultValue: '#111827',
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      placeholder: '#111827 / rgba(...)',
      helpText: 'Pointer label background color.',
    },
    {
      key: 'axisPointer.label.color',
      label: 'Label Color',
      path: 'axisPointer.label.color',
      control: 'text',
      defaultValue: '#f8fafc',
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      placeholder: '#f8fafc / rgba(...)',
      helpText: 'Pointer label text color.',
    },
    {
      key: 'axisPointer.label.fontSize',
      label: 'Label Font Size',
      path: 'axisPointer.label.fontSize',
      control: 'number',
      defaultValue: 12,
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      helpText: 'Pointer label font size in pixels.',
    },
    {
      key: 'axisPointer.label.padding',
      label: 'Label Padding',
      path: 'axisPointer.label.padding',
      control: 'number',
      defaultValue: 6,
      complexity: 'advanced',
      group: 'Label',
      visibleWhen: usesCartesianAxes,
      helpText: 'Inner padding for pointer label.',
    },
    {
      key: 'axisPointer.lineStyle.color',
      label: 'Line Color',
      path: 'axisPointer.lineStyle.color',
      control: 'text',
      defaultValue: '#94a3b8',
      complexity: 'advanced',
      group: 'Line Style',
      visibleWhen: isLineOrCross,
      placeholder: '#94a3b8 / rgba(...)',
      helpText: 'Axis pointer line color.',
    },
    {
      key: 'axisPointer.lineStyle.width',
      label: 'Line Width',
      path: 'axisPointer.lineStyle.width',
      control: 'number',
      defaultValue: 1,
      complexity: 'advanced',
      group: 'Line Style',
      visibleWhen: isLineOrCross,
      helpText: 'Axis pointer line width.',
    },
    {
      key: 'axisPointer.lineStyle.type',
      label: 'Line Type',
      path: 'axisPointer.lineStyle.type',
      control: 'select',
      defaultValue: 'solid',
      complexity: 'advanced',
      group: 'Line Style',
      visibleWhen: isLineOrCross,
      helpText: 'Axis pointer line dash style.',
      options: [
        { label: 'Solid', value: 'solid' },
        { label: 'Dashed', value: 'dashed' },
        { label: 'Dotted', value: 'dotted' },
      ],
    },
    {
      key: 'axisPointer.crossStyle.color',
      label: 'Cross Color',
      path: 'axisPointer.crossStyle.color',
      control: 'text',
      defaultValue: '#f59e0b',
      complexity: 'advanced',
      group: 'Cross Style',
      visibleWhen: isCross,
      placeholder: '#f59e0b / rgba(...)',
      helpText: 'Crosshair color when using cross type.',
    },
    {
      key: 'axisPointer.crossStyle.width',
      label: 'Cross Width',
      path: 'axisPointer.crossStyle.width',
      control: 'number',
      defaultValue: 1,
      complexity: 'advanced',
      group: 'Cross Style',
      visibleWhen: isCross,
      helpText: 'Crosshair width when using cross type.',
    },
    {
      key: 'axisPointer.crossStyle.type',
      label: 'Cross Type',
      path: 'axisPointer.crossStyle.type',
      control: 'select',
      defaultValue: 'dashed',
      complexity: 'advanced',
      group: 'Cross Style',
      visibleWhen: isCross,
      helpText: 'Crosshair dash style.',
      options: [
        { label: 'Solid', value: 'solid' },
        { label: 'Dashed', value: 'dashed' },
        { label: 'Dotted', value: 'dotted' },
      ],
    },
    {
      key: 'axisPointer.shadowStyle.color',
      label: 'Shadow Color',
      path: 'axisPointer.shadowStyle.color',
      control: 'text',
      defaultValue: 'rgba(148, 163, 184, 0.2)',
      complexity: 'advanced',
      group: 'Shadow Style',
      visibleWhen: isShadow,
      placeholder: 'rgba(148,163,184,0.2)',
      helpText: 'Shadow fill color when using shadow type.',
    },
    {
      key: 'axisPointer.shadowStyle.opacity',
      label: 'Shadow Opacity',
      path: 'axisPointer.shadowStyle.opacity',
      control: 'number',
      defaultValue: 0.2,
      complexity: 'advanced',
      group: 'Shadow Style',
      visibleWhen: isShadow,
      helpText: 'Shadow fill opacity when using shadow type.',
    },
    {
      key: 'axisPointer.link',
      label: 'Link (JSON)',
      path: 'axisPointer.link',
      control: 'textarea',
      textareaMode: 'json',
      defaultValue: [],
      complexity: 'expert',
      visibleWhen: usesCartesianAxes,
      placeholder: '[{ "xAxisIndex": "all" }]',
      helpText: 'Advanced axisPointer linking rules between coordinate systems.',
    },
  ],
};
