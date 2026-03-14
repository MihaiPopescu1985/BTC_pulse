import type { ChartType, EditorOption } from './echarts';

export type ControlType = 'text' | 'number' | 'checkbox' | 'select' | 'textarea';
export type EditorMode = 'basic' | 'advanced' | 'expert';
export type ComplexValueEditor = 'string-array' | 'number-array' | 'tuple' | 'color-array' | 'object-array';

export interface SelectOption {
  label: string;
  value: string;
}

export interface EditorContext {
  currentChartType: ChartType;
  option: EditorOption;
  selectedSeriesIndex: number;
  selectedDataZoomIndex: number;
  selectedXAxisIndex: number;
  selectedYAxisIndex: number;
  selectedGridIndex: number;
  selectedVisualMapIndex: number;
  selectedTitleIndex: number;
  selectedDatasetIndex: number;
  selectedRadarIndex: number;
  selectedPolarIndex: number;
  selectedSingleAxisIndex: number;
  selectedParallelIndex: number;
  selectedParallelAxisIndex: number;
  selectedCalendarIndex: number;
  selectedGeoIndex: number;
  selectedAngleAxisIndex: number;
  selectedRadiusAxisIndex: number;
}

export interface FieldSchema {
  key: string;
  label: string;
  path: string;
  control: ControlType;
  keywords?: string[];
  description?: string;
  group?: string;
  complexity?: EditorMode;
  valueEditor?: ComplexValueEditor;
  tupleLabels?: [string, string];
  placeholder?: string;
  options?: SelectOption[];
  textareaMode?: 'plain' | 'json';
  helpText?: string;
  defaultValue?: unknown;
  visibleWhen?: (context: EditorContext) => boolean;
}

export interface ArrayBindingSchema {
  id: string;
  path: string;
  indexToken: string;
  itemLabel: string;
  defaultItem: Record<string, unknown>;
  minItems?: number;
}

export interface SectionSchema {
  id: string;
  title: string;
  fields: FieldSchema[];
  arrayBinding?: ArrayBindingSchema;
}

export interface ArrayBindingState {
  selectedIndex: number;
  itemCount: number;
  minItems?: number;
  onSelect: (index: number) => void;
  onAdd: () => void;
  onRemove: () => void;
}
