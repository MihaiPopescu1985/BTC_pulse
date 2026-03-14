import type { EditorContext, FieldSchema } from '../../types/editor';

export type VisibilityRule = (context: EditorContext) => boolean;

type PositionKey = 'left' | 'right' | 'top' | 'bottom';

interface ShowFieldOptions {
  key: string;
  path: string;
  label?: string;
  defaultValue?: boolean;
  helpText: string;
  visibleWhen?: VisibilityRule;
}

interface PositionFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  defaultValues?: Partial<Record<PositionKey, string>>;
  include?: PositionKey[];
  visibleWhen?: VisibilityRule;
  helpText?: string;
}

interface TextStyleFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  labelPrefix: string;
  defaultColor: string;
  defaultFontSize: number;
  includeTypography?: boolean;
  defaultFontStyle?: string;
  defaultFontWeight?: string;
  defaultFontFamily?: string;
  defaultLineHeight?: number;
  defaultAlign?: string;
  typographyComplexity?: 'basic' | 'advanced' | 'expert';
  visibleWhen?: VisibilityRule;
}

interface LineStyleFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultColor?: string;
  defaultWidth?: number;
  defaultType?: 'solid' | 'dashed' | 'dotted';
  defaultOpacity?: number;
}

interface AreaStyleFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultColor?: string;
  defaultOpacity?: number;
}

interface LabelFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultShow?: boolean;
  defaultPosition?: string;
  defaultFormatter?: string;
  defaultColor?: string;
  defaultFontSize?: number;
  defaultDistance?: number;
}

interface BoxModelFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  defaultBackgroundColor?: string;
  defaultBorderColor?: string;
  defaultBorderWidth?: number;
  defaultBorderRadius?: number;
  defaultPadding?: number;
  includePadding?: boolean;
  includeBorderRadius?: boolean;
  visibleWhen?: VisibilityRule;
  backgroundLabel?: string;
}

interface AxisLabelFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultShow?: boolean;
  defaultRotate?: number;
  defaultMargin?: number;
  defaultColor?: string;
  defaultFontSize?: number;
  defaultFormatter?: string;
  defaultHideOverlap?: boolean;
}

interface AxisLineFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultShow?: boolean;
  defaultSymbol?: string;
  defaultColor?: string;
  defaultWidth?: number;
  defaultType?: 'solid' | 'dashed' | 'dotted';
}

interface AxisTickFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  alignWithLabelVisibleWhen?: VisibilityRule;
  defaultShow?: boolean;
  defaultAlignWithLabel?: boolean;
  defaultLength?: number;
  defaultColor?: string;
  defaultWidth?: number;
}

interface SplitLineFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultShow?: boolean;
  defaultColor?: string;
  defaultWidth?: number;
  defaultType?: 'solid' | 'dashed' | 'dotted';
}

interface SeriesItemStyleFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultColor?: string;
  defaultOpacity?: number;
  defaultBorderColor?: string;
  defaultBorderWidth?: number;
  defaultBorderType?: 'solid' | 'dashed' | 'dotted';
  defaultBorderRadius?: number | number[];
}

interface SeriesInteractionStateFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultEmphasisDisabled?: boolean;
  defaultEmphasisFocus?: string;
  defaultEmphasisScale?: boolean;
  defaultBlurItemStyleOpacity?: number;
  defaultSelectDisabled?: boolean;
}

interface SeriesRenderAnimationFieldsOptions {
  keyPrefix: string;
  pathPrefix: string;
  visibleWhen?: VisibilityRule;
  defaultZ?: number;
  defaultZLevel?: number;
  defaultAnimation?: boolean;
  defaultAnimationDuration?: number;
  defaultAnimationEasing?: string;
}

const withVisibility = (field: FieldSchema, visibleWhen?: VisibilityRule): FieldSchema => {
  if (!visibleWhen) {
    return field;
  }

  return {
    ...field,
    visibleWhen,
  };
};

const combineVisibilityRules = (left?: VisibilityRule, right?: VisibilityRule): VisibilityRule | undefined => {
  if (!left && !right) {
    return undefined;
  }

  if (!left) {
    return right;
  }

  if (!right) {
    return left;
  }

  return (context: EditorContext) => left(context) && right(context);
};

const asRecord = (value: unknown): Record<string, unknown> | undefined => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
};

const getSelectedSeries = (context: EditorContext): Record<string, unknown> | undefined => {
  const source = context.option.series;

  if (Array.isArray(source)) {
    return asRecord(source[context.selectedSeriesIndex]);
  }

  return asRecord(source);
};

const getSelectedCoordinateSystem = (context: EditorContext): string | null => {
  const series = getSelectedSeries(context);
  const coordinateSystem = series?.coordinateSystem;
  return typeof coordinateSystem === 'string' ? coordinateSystem : null;
};

export const isPieSeries = (context: EditorContext): boolean => context.currentChartType === 'pie';
export const isLineSeries = (context: EditorContext): boolean => context.currentChartType === 'line';
export const isBarSeries = (context: EditorContext): boolean => context.currentChartType === 'bar';
export const isCandlestickSeries = (context: EditorContext): boolean => context.currentChartType === 'candlestick';
export const isScatterSeries = (context: EditorContext): boolean => context.currentChartType === 'scatter';
export const isEffectScatterSeries = (context: EditorContext): boolean => context.currentChartType === 'effectScatter';
export const isRadarSeries = (context: EditorContext): boolean => context.currentChartType === 'radar';
export const isHeatmapSeries = (context: EditorContext): boolean => context.currentChartType === 'heatmap';
export const isFunnelSeries = (context: EditorContext): boolean => context.currentChartType === 'funnel';
export const isGaugeSeries = (context: EditorContext): boolean => context.currentChartType === 'gauge';
export const isParallelSeries = (context: EditorContext): boolean => context.currentChartType === 'parallel';
export const isMapSeries = (context: EditorContext): boolean => context.currentChartType === 'map';
export const isNotCandlestickSeries = (context: EditorContext): boolean => context.currentChartType !== 'candlestick';
export const isNotScatterSeries = (context: EditorContext): boolean => context.currentChartType !== 'scatter';
export const isNotCandlestickOrScatterSeries = (context: EditorContext): boolean =>
  context.currentChartType !== 'candlestick' && context.currentChartType !== 'scatter';
export const isNotPieSeries = (context: EditorContext): boolean => context.currentChartType !== 'pie';
export const supportsCommonSeriesLineStyle = (context: EditorContext): boolean =>
  context.currentChartType === 'line' || context.currentChartType === 'radar' || context.currentChartType === 'parallel';
export const supportsCommonSeriesAreaStyle = (context: EditorContext): boolean =>
  context.currentChartType === 'line' || context.currentChartType === 'radar';
export const supportsCommonSeriesInteractionStates = (context: EditorContext): boolean => context.currentChartType !== 'gauge';
export const supportsCommonSeriesItemStyle = (context: EditorContext): boolean => context.currentChartType !== 'gauge';
export const supportsCommonEncode = (context: EditorContext): boolean =>
  context.currentChartType === 'line' ||
  context.currentChartType === 'bar' ||
  context.currentChartType === 'pie' ||
  context.currentChartType === 'radar' ||
  context.currentChartType === 'effectScatter' ||
  context.currentChartType === 'singleAxis';

export const usesCartesianAxes = (context: EditorContext): boolean => {
  const coordinateSystem = getSelectedCoordinateSystem(context);

  if (context.currentChartType === 'line' || context.currentChartType === 'bar' || context.currentChartType === 'candlestick') {
    return coordinateSystem !== 'polar';
  }

  if (context.currentChartType === 'scatter' || context.currentChartType === 'effectScatter') {
    return coordinateSystem !== 'geo' && coordinateSystem !== 'calendar' && coordinateSystem !== 'polar' && coordinateSystem !== 'singleAxis';
  }

  if (context.currentChartType === 'heatmap') {
    return coordinateSystem === null || coordinateSystem === 'cartesian2d';
  }

  return false;
};

export const usesPolarCoordinates = (context: EditorContext): boolean => {
  return context.currentChartType === 'polar' || getSelectedCoordinateSystem(context) === 'polar';
};

export const usesCalendarCoordinates = (context: EditorContext): boolean => {
  return context.currentChartType === 'calendar' || getSelectedCoordinateSystem(context) === 'calendar';
};

export const usesGeoCoordinates = (context: EditorContext): boolean => {
  return context.currentChartType === 'geo' || getSelectedCoordinateSystem(context) === 'geo';
};

export const usesSingleAxisCoordinates = (context: EditorContext): boolean => {
  return context.currentChartType === 'singleAxis' || getSelectedCoordinateSystem(context) === 'singleAxis';
};

export const isNotGaugeOrFunnelSeries = (context: EditorContext): boolean =>
  context.currentChartType !== 'gauge' && context.currentChartType !== 'funnel';

export const supportsVisualMap = (context: EditorContext): boolean =>
  context.currentChartType !== 'pie' && context.currentChartType !== 'funnel' && context.currentChartType !== 'gauge';

export const createShowField = ({
  key,
  path,
  label = 'Show',
  defaultValue = true,
  helpText,
  visibleWhen,
}: ShowFieldOptions): FieldSchema => {
  return withVisibility(
    {
      key,
      label,
      path,
      control: 'checkbox',
      defaultValue,
      helpText,
    },
    visibleWhen,
  );
};

export const createPositionFields = ({
  keyPrefix,
  pathPrefix,
  defaultValues,
  include,
  visibleWhen,
  helpText,
}: PositionFieldsOptions): FieldSchema[] => {
  const keys: PositionKey[] = include ?? ['left', 'right', 'top', 'bottom'];

  return keys.map((positionKey) =>
    withVisibility(
      {
        key: `${keyPrefix}.${positionKey}`,
        label: positionKey.charAt(0).toUpperCase() + positionKey.slice(1),
        path: `${pathPrefix}.${positionKey}`,
        control: 'text',
        defaultValue: defaultValues?.[positionKey] ?? '',
        placeholder: 'auto / center / 20 / 10%',
        helpText: helpText ?? `Adjust ${positionKey} positioning for this component.`,
      },
      visibleWhen,
    ),
  );
};

export const createTextStyleFields = ({
  keyPrefix,
  pathPrefix,
  labelPrefix,
  defaultColor,
  defaultFontSize,
  includeTypography = false,
  defaultFontStyle = 'normal',
  defaultFontWeight = 'normal',
  defaultFontFamily = 'sans-serif',
  defaultLineHeight = 0,
  defaultAlign = 'auto',
  typographyComplexity = 'advanced',
  visibleWhen,
}: TextStyleFieldsOptions): FieldSchema[] => {
  const fields: FieldSchema[] = [
    withVisibility(
      {
        key: `${keyPrefix}.color`,
        label: `${labelPrefix} Color`,
        path: `${pathPrefix}.color`,
        control: 'text',
        defaultValue: defaultColor,
        placeholder: '#e2e8f0 / rgba(...)',
        helpText: `Set the ${labelPrefix.toLowerCase()} color.`,
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.fontSize`,
        label: `${labelPrefix} Font Size`,
        path: `${pathPrefix}.fontSize`,
        control: 'number',
        defaultValue: defaultFontSize,
        helpText: `Set the ${labelPrefix.toLowerCase()} font size in pixels.`,
      },
      visibleWhen,
    ),
  ];

  if (!includeTypography) {
    return fields;
  }

  fields.push(
    withVisibility(
      {
        key: `${keyPrefix}.fontStyle`,
        label: `${labelPrefix} Font Style`,
        path: `${pathPrefix}.fontStyle`,
        control: 'select',
        defaultValue: defaultFontStyle,
        complexity: typographyComplexity,
        helpText: `Set the ${labelPrefix.toLowerCase()} font style.`,
        options: [
          { label: 'Normal', value: 'normal' },
          { label: 'Italic', value: 'italic' },
          { label: 'Oblique', value: 'oblique' },
        ],
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.fontWeight`,
        label: `${labelPrefix} Font Weight`,
        path: `${pathPrefix}.fontWeight`,
        control: 'select',
        defaultValue: defaultFontWeight,
        complexity: typographyComplexity,
        helpText: `Set the ${labelPrefix.toLowerCase()} font weight.`,
        options: [
          { label: 'Normal', value: 'normal' },
          { label: 'Bold', value: 'bold' },
          { label: 'Bolder', value: 'bolder' },
          { label: 'Lighter', value: 'lighter' },
          { label: '100', value: '100' },
          { label: '200', value: '200' },
          { label: '300', value: '300' },
          { label: '400', value: '400' },
          { label: '500', value: '500' },
          { label: '600', value: '600' },
          { label: '700', value: '700' },
          { label: '800', value: '800' },
          { label: '900', value: '900' },
        ],
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.fontFamily`,
        label: `${labelPrefix} Font Family`,
        path: `${pathPrefix}.fontFamily`,
        control: 'text',
        defaultValue: defaultFontFamily,
        complexity: typographyComplexity,
        placeholder: 'sans-serif / "Open Sans", sans-serif',
        helpText: `Set the ${labelPrefix.toLowerCase()} font family.`,
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineHeight`,
        label: `${labelPrefix} Line Height`,
        path: `${pathPrefix}.lineHeight`,
        control: 'number',
        defaultValue: defaultLineHeight,
        complexity: typographyComplexity,
        helpText: `Set the ${labelPrefix.toLowerCase()} line height in pixels.`,
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.align`,
        label: `${labelPrefix} Align`,
        path: `${pathPrefix}.align`,
        control: 'select',
        defaultValue: defaultAlign,
        complexity: typographyComplexity,
        helpText: `Set ${labelPrefix.toLowerCase()} alignment.`,
        options: [
          { label: 'Auto', value: 'auto' },
          { label: 'Left', value: 'left' },
          { label: 'Center', value: 'center' },
          { label: 'Right', value: 'right' },
        ],
      },
      visibleWhen,
    ),
  );

  return fields;
};

export const createLineStyleFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultColor = '',
  defaultWidth = 2,
  defaultType = 'solid',
  defaultOpacity = 1,
}: LineStyleFieldsOptions): FieldSchema[] => {
  return [
    withVisibility(
      {
        key: `${keyPrefix}.color`,
        label: 'Line Color',
        path: `${pathPrefix}.color`,
        control: 'text',
        defaultValue: defaultColor,
        complexity: 'advanced',
        placeholder: '#3b82f6 / rgba(...)',
        helpText: 'Set line stroke color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.width`,
        label: 'Line Width',
        path: `${pathPrefix}.width`,
        control: 'number',
        defaultValue: defaultWidth,
        helpText: 'Control the line stroke thickness.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.type`,
        label: 'Line Type',
        path: `${pathPrefix}.type`,
        control: 'select',
        defaultValue: defaultType,
        helpText: 'Choose a line dash style.',
        options: [
          { label: 'Solid', value: 'solid' },
          { label: 'Dashed', value: 'dashed' },
          { label: 'Dotted', value: 'dotted' },
        ],
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.opacity`,
        label: 'Line Opacity',
        path: `${pathPrefix}.opacity`,
        control: 'number',
        defaultValue: defaultOpacity,
        complexity: 'advanced',
        helpText: 'Set line stroke opacity (0 to 1).',
      },
      visibleWhen,
    ),
  ];
};

export const createAreaStyleFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultColor = '',
  defaultOpacity = 0.15,
}: AreaStyleFieldsOptions): FieldSchema[] => {
  return [
    withVisibility(
      {
        key: `${keyPrefix}.color`,
        label: 'Area Color',
        path: `${pathPrefix}.color`,
        control: 'text',
        defaultValue: defaultColor,
        complexity: 'advanced',
        placeholder: '#3b82f6 / rgba(...)',
        helpText: 'Set filled area color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.opacity`,
        label: 'Area Opacity',
        path: `${pathPrefix}.opacity`,
        control: 'number',
        defaultValue: defaultOpacity,
        helpText: 'Set fill opacity under/behind the series.',
      },
      visibleWhen,
    ),
  ];
};

export const createLabelFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultShow = false,
  defaultPosition = 'top',
  defaultFormatter = '',
  defaultColor = '',
  defaultFontSize = 12,
  defaultDistance = 5,
}: LabelFieldsOptions): FieldSchema[] => {
  return [
    createShowField({
      key: `${keyPrefix}.show`,
      path: `${pathPrefix}.show`,
      defaultValue: defaultShow,
      helpText: 'Toggle value labels for this series.',
      visibleWhen,
    }),
    withVisibility(
      {
        key: `${keyPrefix}.position`,
        label: 'Label Position',
        path: `${pathPrefix}.position`,
        control: 'select',
        defaultValue: defaultPosition,
        helpText: 'Choose where labels are placed.',
        options: [
          { label: 'Top', value: 'top' },
          { label: 'Bottom', value: 'bottom' },
          { label: 'Left', value: 'left' },
          { label: 'Right', value: 'right' },
          { label: 'Center', value: 'center' },
          { label: 'Inside', value: 'inside' },
          { label: 'Outside', value: 'outside' },
        ],
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.formatter`,
        label: 'Label Formatter',
        path: `${pathPrefix}.formatter`,
        control: 'textarea',
        textareaMode: 'plain',
        defaultValue: defaultFormatter,
        complexity: 'advanced',
        placeholder: '{b}: {c}',
        helpText: 'Optional formatter pattern for label text.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.color`,
        label: 'Label Color',
        path: `${pathPrefix}.color`,
        control: 'text',
        defaultValue: defaultColor,
        complexity: 'advanced',
        placeholder: '#e2e8f0 / rgba(...)',
        helpText: 'Set label text color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.fontSize`,
        label: 'Label Font Size',
        path: `${pathPrefix}.fontSize`,
        control: 'number',
        defaultValue: defaultFontSize,
        complexity: 'advanced',
        helpText: 'Set label font size in pixels.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.distance`,
        label: 'Label Distance',
        path: `${pathPrefix}.distance`,
        control: 'number',
        defaultValue: defaultDistance,
        complexity: 'advanced',
        helpText: 'Distance between label and symbol/shape in pixels.',
      },
      visibleWhen,
    ),
  ];
};

export const createBoxModelFields = ({
  keyPrefix,
  pathPrefix,
  defaultBackgroundColor = 'transparent',
  defaultBorderColor = '#000000',
  defaultBorderWidth = 0,
  defaultBorderRadius = 0,
  defaultPadding = 5,
  includePadding = true,
  includeBorderRadius = false,
  visibleWhen,
  backgroundLabel = 'Background Color',
}: BoxModelFieldsOptions): FieldSchema[] => {
  const fields: FieldSchema[] = [
    withVisibility(
      {
        key: `${keyPrefix}.backgroundColor`,
        label: backgroundLabel,
        path: `${pathPrefix}.backgroundColor`,
        control: 'text',
        defaultValue: defaultBackgroundColor,
        placeholder: '#1f2937 / rgba(...)',
        helpText: 'Background fill color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.borderColor`,
        label: 'Border Color',
        path: `${pathPrefix}.borderColor`,
        control: 'text',
        defaultValue: defaultBorderColor,
        helpText: 'Border color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.borderWidth`,
        label: 'Border Width',
        path: `${pathPrefix}.borderWidth`,
        control: 'number',
        defaultValue: defaultBorderWidth,
        helpText: 'Border width in pixels.',
      },
      visibleWhen,
    ),
  ];

  if (includePadding) {
    fields.push(
      withVisibility(
        {
          key: `${keyPrefix}.padding`,
          label: 'Padding',
          path: `${pathPrefix}.padding`,
          control: 'number',
          defaultValue: defaultPadding,
          helpText: 'Inner spacing for the component box.',
        },
        visibleWhen,
      ),
    );
  }

  if (includeBorderRadius) {
    fields.push(
      withVisibility(
        {
          key: `${keyPrefix}.borderRadius`,
          label: 'Border Radius',
          path: `${pathPrefix}.borderRadius`,
          control: 'number',
          defaultValue: defaultBorderRadius,
          helpText: 'Corner radius in pixels.',
        },
        visibleWhen,
      ),
    );
  }

  return fields;
};

export const createAxisLabelFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultShow = true,
  defaultRotate = 0,
  defaultMargin = 8,
  defaultColor = '',
  defaultFontSize = 12,
  defaultFormatter = '',
  defaultHideOverlap = false,
}: AxisLabelFieldsOptions): FieldSchema[] => {
  return [
    createShowField({
      key: `${keyPrefix}.show`,
      label: 'Axis Label Show',
      path: `${pathPrefix}.show`,
      defaultValue: defaultShow,
      helpText: 'Toggle axis labels.',
      visibleWhen,
    }),
    withVisibility(
      {
        key: `${keyPrefix}.rotate`,
        label: 'Axis Label Rotate',
        path: `${pathPrefix}.rotate`,
        control: 'number',
        defaultValue: defaultRotate,
        complexity: 'advanced',
        helpText: 'Rotate axis labels in degrees.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.margin`,
        label: 'Axis Label Margin',
        path: `${pathPrefix}.margin`,
        control: 'number',
        defaultValue: defaultMargin,
        complexity: 'advanced',
        helpText: 'Distance between axis line and labels (px).',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.color`,
        label: 'Axis Label Color',
        path: `${pathPrefix}.color`,
        control: 'text',
        defaultValue: defaultColor,
        complexity: 'advanced',
        placeholder: '#94a3b8 / rgba(...)',
        helpText: 'Set axis label text color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.fontSize`,
        label: 'Axis Label Font Size',
        path: `${pathPrefix}.fontSize`,
        control: 'number',
        defaultValue: defaultFontSize,
        complexity: 'advanced',
        helpText: 'Set axis label font size in pixels.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.formatter`,
        label: 'Axis Label Formatter',
        path: `${pathPrefix}.formatter`,
        control: 'textarea',
        textareaMode: 'plain',
        defaultValue: defaultFormatter,
        complexity: 'expert',
        placeholder: '{value}',
        helpText: 'Optional axis label formatter pattern/function text.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.hideOverlap`,
        label: 'Axis Label Hide Overlap',
        path: `${pathPrefix}.hideOverlap`,
        control: 'checkbox',
        defaultValue: defaultHideOverlap,
        complexity: 'advanced',
        helpText: 'Hide overlapping labels automatically.',
      },
      visibleWhen,
    ),
  ];
};

export const createAxisLineFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultShow = true,
  defaultSymbol = 'none',
  defaultColor = '#64748b',
  defaultWidth = 1,
  defaultType = 'solid',
}: AxisLineFieldsOptions): FieldSchema[] => {
  return [
    createShowField({
      key: `${keyPrefix}.show`,
      label: 'Axis Line Show',
      path: `${pathPrefix}.show`,
      defaultValue: defaultShow,
      helpText: 'Toggle the main axis line.',
      visibleWhen,
    }),
    withVisibility(
      {
        key: `${keyPrefix}.symbol`,
        label: 'Axis Line Symbol',
        path: `${pathPrefix}.symbol`,
        control: 'text',
        defaultValue: defaultSymbol,
        complexity: 'advanced',
        placeholder: 'none / arrow',
        helpText: 'Line end symbol (e.g. none, arrow).',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.color`,
        label: 'Axis Line Color',
        path: `${pathPrefix}.lineStyle.color`,
        control: 'text',
        defaultValue: defaultColor,
        complexity: 'advanced',
        placeholder: '#64748b / rgba(...)',
        helpText: 'Axis line stroke color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.width`,
        label: 'Axis Line Width',
        path: `${pathPrefix}.lineStyle.width`,
        control: 'number',
        defaultValue: defaultWidth,
        complexity: 'advanced',
        helpText: 'Axis line stroke width in pixels.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.type`,
        label: 'Axis Line Type',
        path: `${pathPrefix}.lineStyle.type`,
        control: 'select',
        defaultValue: defaultType,
        complexity: 'advanced',
        helpText: 'Axis line dash style.',
        options: [
          { label: 'Solid', value: 'solid' },
          { label: 'Dashed', value: 'dashed' },
          { label: 'Dotted', value: 'dotted' },
        ],
      },
      visibleWhen,
    ),
  ];
};

export const createAxisTickFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  alignWithLabelVisibleWhen,
  defaultShow = true,
  defaultAlignWithLabel = true,
  defaultLength = 5,
  defaultColor = '#64748b',
  defaultWidth = 1,
}: AxisTickFieldsOptions): FieldSchema[] => {
  return [
    createShowField({
      key: `${keyPrefix}.show`,
      label: 'Axis Tick Show',
      path: `${pathPrefix}.show`,
      defaultValue: defaultShow,
      helpText: 'Toggle axis tick marks.',
      visibleWhen,
    }),
    withVisibility(
      {
        key: `${keyPrefix}.alignWithLabel`,
        label: 'Axis Tick Align With Label',
        path: `${pathPrefix}.alignWithLabel`,
        control: 'checkbox',
        defaultValue: defaultAlignWithLabel,
        complexity: 'advanced',
        helpText: 'Align ticks with category labels.',
      },
      combineVisibilityRules(visibleWhen, alignWithLabelVisibleWhen),
    ),
    withVisibility(
      {
        key: `${keyPrefix}.length`,
        label: 'Axis Tick Length',
        path: `${pathPrefix}.length`,
        control: 'number',
        defaultValue: defaultLength,
        complexity: 'advanced',
        helpText: 'Tick length in pixels.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.color`,
        label: 'Axis Tick Color',
        path: `${pathPrefix}.lineStyle.color`,
        control: 'text',
        defaultValue: defaultColor,
        complexity: 'advanced',
        placeholder: '#64748b / rgba(...)',
        helpText: 'Axis tick color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.width`,
        label: 'Axis Tick Width',
        path: `${pathPrefix}.lineStyle.width`,
        control: 'number',
        defaultValue: defaultWidth,
        complexity: 'advanced',
        helpText: 'Axis tick stroke width in pixels.',
      },
      visibleWhen,
    ),
  ];
};

export const createSplitLineFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultShow = true,
  defaultColor = '#334155',
  defaultWidth = 1,
  defaultType = 'solid',
}: SplitLineFieldsOptions): FieldSchema[] => {
  return [
    createShowField({
      key: `${keyPrefix}.show`,
      label: 'Split Line Show',
      path: `${pathPrefix}.show`,
      defaultValue: defaultShow,
      helpText: 'Toggle split/grid lines.',
      visibleWhen,
    }),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.color`,
        label: 'Split Line Color',
        path: `${pathPrefix}.lineStyle.color`,
        control: 'text',
        defaultValue: defaultColor,
        complexity: 'advanced',
        placeholder: '#334155 / rgba(...)',
        helpText: 'Split line color.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.width`,
        label: 'Split Line Width',
        path: `${pathPrefix}.lineStyle.width`,
        control: 'number',
        defaultValue: defaultWidth,
        complexity: 'advanced',
        helpText: 'Split line width in pixels.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.lineStyle.type`,
        label: 'Split Line Type',
        path: `${pathPrefix}.lineStyle.type`,
        control: 'select',
        defaultValue: defaultType,
        complexity: 'advanced',
        helpText: 'Split line dash style.',
        options: [
          { label: 'Solid', value: 'solid' },
          { label: 'Dashed', value: 'dashed' },
          { label: 'Dotted', value: 'dotted' },
        ],
      },
      visibleWhen,
    ),
  ];
};

export const createSeriesItemStyleFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultColor = '',
  defaultOpacity = 1,
  defaultBorderColor = '#ffffff',
  defaultBorderWidth = 0,
  defaultBorderType = 'solid',
  defaultBorderRadius = 0,
}: SeriesItemStyleFieldsOptions): FieldSchema[] => {
  return [
    withVisibility(
      {
        key: `${keyPrefix}.color`,
        label: 'Item Color',
        path: `${pathPrefix}.color`,
        control: 'text',
        defaultValue: defaultColor,
        placeholder: '#3b82f6 / rgba(...)',
        helpText: 'Base fill color for series items.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.opacity`,
        label: 'Item Opacity',
        path: `${pathPrefix}.opacity`,
        control: 'number',
        defaultValue: defaultOpacity,
        complexity: 'advanced',
        helpText: 'Opacity for series items (0 to 1).',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.borderColor`,
        label: 'Item Border Color',
        path: `${pathPrefix}.borderColor`,
        control: 'text',
        defaultValue: defaultBorderColor,
        complexity: 'advanced',
        helpText: 'Border color for series items.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.borderWidth`,
        label: 'Item Border Width',
        path: `${pathPrefix}.borderWidth`,
        control: 'number',
        defaultValue: defaultBorderWidth,
        complexity: 'advanced',
        helpText: 'Border width in pixels for series items.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.borderType`,
        label: 'Item Border Type',
        path: `${pathPrefix}.borderType`,
        control: 'select',
        defaultValue: defaultBorderType,
        complexity: 'advanced',
        helpText: 'Border stroke type for series items.',
        options: [
          { label: 'Solid', value: 'solid' },
          { label: 'Dashed', value: 'dashed' },
          { label: 'Dotted', value: 'dotted' },
        ],
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.borderRadius`,
        label: 'Item Border Radius (JSON)',
        path: `${pathPrefix}.borderRadius`,
        control: 'textarea',
        textareaMode: 'json',
        defaultValue: defaultBorderRadius,
        complexity: 'expert',
        helpText: 'Corner radius for items (number or array).',
        placeholder: '0 or [4, 4, 0, 0]',
      },
      visibleWhen,
    ),
  ];
};

export const createSeriesInteractionStateFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultEmphasisDisabled = false,
  defaultEmphasisFocus = 'none',
  defaultEmphasisScale = true,
  defaultBlurItemStyleOpacity = 0.3,
  defaultSelectDisabled = false,
}: SeriesInteractionStateFieldsOptions): FieldSchema[] => {
  return [
    createShowField({
      key: `${keyPrefix}.emphasis.disabled`,
      label: 'Emphasis Disabled',
      path: `${pathPrefix}.emphasis.disabled`,
      defaultValue: defaultEmphasisDisabled,
      helpText: 'Disable hover emphasis state.',
      visibleWhen,
    }),
    withVisibility(
      {
        key: `${keyPrefix}.emphasis.focus`,
        label: 'Emphasis Focus',
        path: `${pathPrefix}.emphasis.focus`,
        control: 'select',
        defaultValue: defaultEmphasisFocus,
        complexity: 'advanced',
        helpText: 'Focus strategy on hover/emphasis.',
        options: [
          { label: 'None', value: 'none' },
          { label: 'Self', value: 'self' },
          { label: 'Series', value: 'series' },
          { label: 'Adjacent', value: 'adjacency' },
        ],
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.emphasis.scale`,
        label: 'Emphasis Scale',
        path: `${pathPrefix}.emphasis.scale`,
        control: 'checkbox',
        defaultValue: defaultEmphasisScale,
        complexity: 'advanced',
        helpText: 'Scale elements on emphasis where supported.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.blur.itemStyle.opacity`,
        label: 'Blur Item Opacity',
        path: `${pathPrefix}.blur.itemStyle.opacity`,
        control: 'number',
        defaultValue: defaultBlurItemStyleOpacity,
        complexity: 'advanced',
        helpText: 'Item opacity in blur state (0 to 1).',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.select.disabled`,
        label: 'Select Disabled',
        path: `${pathPrefix}.select.disabled`,
        control: 'checkbox',
        defaultValue: defaultSelectDisabled,
        complexity: 'advanced',
        helpText: 'Disable selected state for this series.',
      },
      visibleWhen,
    ),
  ];
};

export const createSeriesRenderAnimationFields = ({
  keyPrefix,
  pathPrefix,
  visibleWhen,
  defaultZ = 2,
  defaultZLevel = 0,
  defaultAnimation = true,
  defaultAnimationDuration = 1000,
  defaultAnimationEasing = 'cubicOut',
}: SeriesRenderAnimationFieldsOptions): FieldSchema[] => {
  return [
    withVisibility(
      {
        key: `${keyPrefix}.z`,
        label: 'Z',
        path: `${pathPrefix}.z`,
        control: 'number',
        defaultValue: defaultZ,
        complexity: 'advanced',
        helpText: 'Z-order within the same canvas layer.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.zlevel`,
        label: 'Z Level',
        path: `${pathPrefix}.zlevel`,
        control: 'number',
        defaultValue: defaultZLevel,
        complexity: 'advanced',
        helpText: 'Canvas layer index for rendering order.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.animation`,
        label: 'Animation',
        path: `${pathPrefix}.animation`,
        control: 'checkbox',
        defaultValue: defaultAnimation,
        complexity: 'advanced',
        helpText: 'Enable series animation.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.animationDuration`,
        label: 'Animation Duration',
        path: `${pathPrefix}.animationDuration`,
        control: 'number',
        defaultValue: defaultAnimationDuration,
        complexity: 'advanced',
        helpText: 'Initial animation duration in milliseconds.',
      },
      visibleWhen,
    ),
    withVisibility(
      {
        key: `${keyPrefix}.animationEasing`,
        label: 'Animation Easing',
        path: `${pathPrefix}.animationEasing`,
        control: 'select',
        defaultValue: defaultAnimationEasing,
        complexity: 'advanced',
        helpText: 'Easing curve for animation motion.',
        options: [
          { label: 'Linear', value: 'linear' },
          { label: 'Quadratic In', value: 'quadraticIn' },
          { label: 'Quadratic Out', value: 'quadraticOut' },
          { label: 'Cubic Out', value: 'cubicOut' },
          { label: 'Elastic Out', value: 'elasticOut' },
          { label: 'Bounce Out', value: 'bounceOut' },
        ],
      },
      visibleWhen,
    ),
  ];
};
