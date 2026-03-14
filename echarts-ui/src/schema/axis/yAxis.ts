import { createAxisSection } from './shared';

export const defaultYAxisItem = {
  show: true,
  type: 'value',
  name: '',
  boundaryGap: false,
};

export const yAxisSection = createAxisSection({
  id: 'yAxis',
  title: 'Y Axis',
  keyPrefix: 'yAxis',
  pathPrefix: 'yAxis.$yAxisIndex',
  arrayBindingId: 'yAxis',
  selectedIndexFromContext: (context) => context.selectedYAxisIndex,
  itemLabel: 'Y Axis',
  defaultItem: defaultYAxisItem,
  defaultType: 'value',
  defaultBoundaryGap: false,
});
