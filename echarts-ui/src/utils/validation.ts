import type { EditorContext } from '../types/editor';
import type { EditorOption } from '../types/echarts';
import { getSeriesList, getSeriesType } from './series';
import type { ValidationFix } from './validationFixes';

export type ValidationSeverity = 'error' | 'warning' | 'info';

export interface ValidationMessage {
  id: string;
  severity: ValidationSeverity;
  message: string;
  path?: string;
  section?: string;
  fixes?: ValidationFix[];
}

export interface ValidationResult {
  messages: ValidationMessage[];
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
};

const getPrimaryObject = (value: unknown): Record<string, unknown> | undefined => {
  if (Array.isArray(value)) {
    const first = value[0];
    return isRecord(first) ? first : undefined;
  }

  return isRecord(value) ? value : undefined;
};

const getIndexedObject = (value: unknown, index: number): Record<string, unknown> | undefined => {
  if (Array.isArray(value)) {
    const item = value[index];
    return isRecord(item) ? item : undefined;
  }

  if (index === 0 && isRecord(value)) {
    return value;
  }

  return undefined;
};

const getRawDatasetSource = (option: EditorOption): unknown => {
  const dataset = option.dataset;

  if (Array.isArray(dataset)) {
    const first = dataset[0];
    return isRecord(first) ? first.source : undefined;
  }

  if (isRecord(dataset)) {
    return dataset.source;
  }

  return undefined;
};

const isValid2DArray = (value: unknown): value is unknown[][] => {
  return Array.isArray(value) && value.every((row) => Array.isArray(row));
};

const axisIsShown = (axis: Record<string, unknown> | undefined): boolean => {
  if (!axis) {
    return false;
  }

  if (typeof axis.show === 'boolean') {
    return axis.show;
  }

  return true;
};

const hasAxisData = (axis: Record<string, unknown> | undefined): boolean => {
  if (!axis) {
    return false;
  }

  return Array.isArray(axis.data) && axis.data.length > 0;
};

const getAxisType = (axis: Record<string, unknown> | undefined): string | null => {
  if (!axis) {
    return null;
  }

  return typeof axis.type === 'string' ? axis.type : null;
};

const hasNonEmptyString = (value: unknown): boolean => {
  return typeof value === 'string' && value.trim().length > 0;
};

const hasLayoutValue = (value: unknown): boolean => {
  return (typeof value === 'string' && value.trim().length > 0) || (typeof value === 'number' && Number.isFinite(value));
};

const isObjectCell = (value: unknown): boolean => {
  return isRecord(value);
};

const isPrimitiveCell = (value: unknown): boolean => {
  return value === null || typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean';
};

const getComponentPathPrefix = (value: unknown, root: string): string => {
  if (Array.isArray(value)) {
    return `${root}.0`;
  }

  return root;
};

const getIndexedComponentPath = (value: unknown, root: string, index: number): string => {
  if (Array.isArray(value)) {
    return `${root}.${index}`;
  }

  return root;
};

export const validateOption = (option: EditorOption, context: EditorContext): ValidationResult => {
  const messages: ValidationMessage[] = [];

  const seriesList = getSeriesList(option);
  const selectedSeries = seriesList[context.selectedSeriesIndex];

  const xAxis = getPrimaryObject(option.xAxis);
  const yAxis = getPrimaryObject(option.yAxis);
  const title = getPrimaryObject(option.title);
  const legend = getPrimaryObject(option.legend);
  const tooltip = getPrimaryObject(option.tooltip);
  const radar = getPrimaryObject(option.radar);
  const polar = getIndexedObject(option.polar, context.selectedPolarIndex);
  const angleAxis = getIndexedObject(option.angleAxis, context.selectedAngleAxisIndex);
  const radiusAxis = getIndexedObject(option.radiusAxis, context.selectedRadiusAxisIndex);
  const parallel = getIndexedObject(option.parallel, context.selectedParallelIndex);
  const parallelAxisItems = Array.isArray(option.parallelAxis)
    ? option.parallelAxis.filter((item) => isRecord(item))
    : isRecord(option.parallelAxis)
      ? [option.parallelAxis]
      : [];
  const dataZoomItems = Array.isArray(option.dataZoom)
    ? option.dataZoom.filter((item) => isRecord(item))
    : isRecord(option.dataZoom)
      ? [option.dataZoom]
      : [];
  const gridItems = Array.isArray(option.grid)
    ? option.grid.filter((item) => isRecord(item))
    : isRecord(option.grid)
      ? [option.grid]
      : [];
  const calendar = getIndexedObject(option.calendar, context.selectedCalendarIndex);
  const geo = getIndexedObject(option.geo, context.selectedGeoIndex);
  const xAxisPathPrefix = getComponentPathPrefix(option.xAxis, 'xAxis');
  const yAxisPathPrefix = getComponentPathPrefix(option.yAxis, 'yAxis');
  const titlePathPrefix = getComponentPathPrefix(option.title, 'title');
  const legendPathPrefix = getComponentPathPrefix(option.legend, 'legend');
  const datasetPathPrefix = getComponentPathPrefix(option.dataset, 'dataset');
  const tooltipPathPrefix = getComponentPathPrefix(option.tooltip, 'tooltip');
  const radarPathPrefix = getComponentPathPrefix(option.radar, 'radar');
  const polarPathPrefix = getComponentPathPrefix(option.polar, 'polar');
  const angleAxisPathPrefix = getComponentPathPrefix(option.angleAxis, 'angleAxis');
  const radiusAxisPathPrefix = getComponentPathPrefix(option.radiusAxis, 'radiusAxis');
  const parallelPathPrefix = getComponentPathPrefix(option.parallel, 'parallel');
  const parallelAxisPathPrefix = getComponentPathPrefix(option.parallelAxis, 'parallelAxis');
  const calendarPathPrefix = getComponentPathPrefix(option.calendar, 'calendar');
  const geoPathPrefix = getComponentPathPrefix(option.geo, 'geo');

  const rawDatasetSource = getRawDatasetSource(option);
  const datasetValid = isValid2DArray(rawDatasetSource);
  const datasetColumnCount = datasetValid ? rawDatasetSource.reduce((max, row) => Math.max(max, row.length), 0) : 0;

  if (rawDatasetSource === undefined || rawDatasetSource === null || rawDatasetSource === '') {
    messages.push({
      id: 'dataset-empty-missing',
      severity: 'warning',
      message: 'dataset.source is empty. Add table data to power dataset-driven charts.',
      path: `${datasetPathPrefix}.source`,
      section: 'dataset',
      fixes: [
        {
          id: 'restore-default-dataset',
          label: 'Restore default dataset',
          kind: 'restore_default_dataset',
        },
      ],
    });
  } else if (!datasetValid) {
    messages.push({
      id: 'dataset-invalid-shape',
      severity: 'error',
      message: 'dataset.source should be a 2D array (rows and columns).',
      path: `${datasetPathPrefix}.source`,
      section: 'dataset',
      fixes: [
        {
          id: 'restore-default-dataset',
          label: 'Restore default dataset',
          kind: 'restore_default_dataset',
        },
      ],
    });
  } else {
    const rowCount = rawDatasetSource.length;
    const maxColumnCount = rawDatasetSource.reduce((max, row) => Math.max(max, row.length), 0);

    if (rowCount === 0 || maxColumnCount === 0) {
      messages.push({
        id: 'dataset-empty-grid',
        severity: 'warning',
        message: 'dataset.source appears empty. Add headers and at least one data row.',
        path: `${datasetPathPrefix}.source`,
        section: 'dataset',
        fixes: [
          {
            id: 'restore-default-dataset',
            label: 'Restore default dataset',
            kind: 'restore_default_dataset',
          },
        ],
      });
    } else if (rowCount === 1) {
      messages.push({
        id: 'dataset-header-only',
        severity: 'info',
        message: 'dataset.source only has a header row. Add data rows to render values.',
        path: 'dataset.source',
        section: 'dataset',
      });
    }
  }

  if (context.currentChartType === 'pie') {
    if (axisIsShown(xAxis) || hasAxisData(xAxis)) {
      messages.push({
        id: 'pie-uses-xaxis',
        severity: 'warning',
        message: 'Pie charts typically do not use xAxis settings.',
        path: `${xAxisPathPrefix}.show`,
        section: 'xAxis',
        fixes: [
          {
            id: 'hide-pie-axes',
            label: 'Hide xAxis and yAxis',
            kind: 'batch_set_paths',
            payload: {
              entries: [
                { path: `${xAxisPathPrefix}.show`, value: false },
                { path: `${yAxisPathPrefix}.show`, value: false },
              ],
            },
          },
        ],
      });
    }

    if (axisIsShown(yAxis)) {
      messages.push({
        id: 'pie-uses-yaxis',
        severity: 'warning',
        message: 'Pie charts typically do not use yAxis settings.',
        path: `${yAxisPathPrefix}.show`,
        section: 'yAxis',
        fixes: [
          {
            id: 'hide-pie-axes',
            label: 'Hide xAxis and yAxis',
            kind: 'batch_set_paths',
            payload: {
              entries: [
                { path: `${xAxisPathPrefix}.show`, value: false },
                { path: `${yAxisPathPrefix}.show`, value: false },
              ],
            },
          },
        ],
      });
    }
  }

  const hasPieSeries = seriesList.some((series) => getSeriesType(series) === 'pie');
  if (hasPieSeries && tooltip?.trigger !== 'item') {
    messages.push({
      id: 'pie-tooltip-trigger',
      severity: 'warning',
      message: "Pie series generally work best with tooltip.trigger = 'item'.",
      path: `${tooltipPathPrefix}.trigger`,
      section: 'tooltip',
      fixes: [
        {
          id: 'set-tooltip-trigger-item',
          label: "Set tooltip.trigger to 'item'",
          kind: 'set_path',
          payload: { path: `${tooltipPathPrefix}.trigger`, value: 'item' },
        },
      ],
    });
  }

  const hasCartesianSeries = seriesList.some((series) => {
    const type = getSeriesType(series);
    const coordinateSystem = typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d';

    if (type === 'line' || type === 'bar' || type === 'candlestick') {
      return coordinateSystem === 'cartesian2d';
    }

    if (type === 'scatter' || type === 'effectScatter' || type === 'heatmap') {
      return coordinateSystem === 'cartesian2d';
    }

    return false;
  });

  if (hasCartesianSeries) {
    if (!axisIsShown(xAxis)) {
      messages.push({
        id: 'cartesian-missing-xaxis',
        severity: 'warning',
        message: 'Line/bar/candlestick/scatter/heatmap series usually require a visible xAxis.',
        path: `${xAxisPathPrefix}.show`,
        section: 'xAxis',
        fixes: [
          {
            id: 'ensure-default-xaxis',
            label: 'Create default xAxis',
            kind: 'ensure_default_axis',
            payload: { axis: 'xAxis' },
          },
        ],
      });
    }

    if (!axisIsShown(yAxis)) {
      messages.push({
        id: 'cartesian-missing-yaxis',
        severity: 'warning',
        message: 'Line/bar/candlestick/scatter/heatmap series usually require a visible yAxis.',
        path: `${yAxisPathPrefix}.show`,
        section: 'yAxis',
        fixes: [
          {
            id: 'ensure-default-yaxis',
            label: 'Create default yAxis',
            kind: 'ensure_default_axis',
            payload: { axis: 'yAxis' },
          },
        ],
      });
    }

    dataZoomItems.forEach((dataZoomItem, dataZoomIndex) => {
      const dataZoomPath = getIndexedComponentPath(option.dataZoom, 'dataZoom', dataZoomIndex);
      const hasXAxisTarget = dataZoomItem.xAxisIndex !== undefined;
      const hasYAxisTarget = dataZoomItem.yAxisIndex !== undefined;

      if (!hasXAxisTarget && !hasYAxisTarget) {
        messages.push({
          id: `datazoom-missing-axis-target-${dataZoomIndex}`,
          severity: 'warning',
          message: 'DataZoom should target xAxisIndex or yAxisIndex for cartesian charts.',
          path: `${dataZoomPath}.xAxisIndex`,
          section: 'dataZoom',
          fixes: [
            {
              id: `set-datazoom-x-axis-target-${dataZoomIndex}`,
              label: 'Set xAxisIndex to 0',
              kind: 'set_path',
              payload: { path: `${dataZoomPath}.xAxisIndex`, value: 0 },
            },
          ],
        });
      }

      const start = dataZoomItem.start;
      const end = dataZoomItem.end;
      const startIsNumber = typeof start === 'number' && Number.isFinite(start);
      const endIsNumber = typeof end === 'number' && Number.isFinite(end);
      const hasInvalidRange =
        startIsNumber &&
        endIsNumber &&
        (start < 0 || start > 100 || end < 0 || end > 100 || start >= end);

      if (hasInvalidRange) {
        messages.push({
          id: `datazoom-invalid-range-${dataZoomIndex}`,
          severity: 'warning',
          message: 'DataZoom start/end should be 0-100 with start less than end.',
          path: `${dataZoomPath}.start`,
          section: 'dataZoom',
          fixes: [
            {
              id: `reset-datazoom-range-${dataZoomIndex}`,
              label: 'Reset start/end to 0/100',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `${dataZoomPath}.start`, value: 0 },
                  { path: `${dataZoomPath}.end`, value: 100 },
                ],
              },
            },
          ],
        });
      }
    });

    gridItems.forEach((gridItem, gridIndex) => {
      const gridPath = getIndexedComponentPath(option.grid, 'grid', gridIndex);
      const hasHorizontalOffsets = hasLayoutValue(gridItem.left) && hasLayoutValue(gridItem.right);
      const hasVerticalOffsets = hasLayoutValue(gridItem.top) && hasLayoutValue(gridItem.bottom);
      const hasExplicitWidth = hasLayoutValue(gridItem.width);
      const hasExplicitHeight = hasLayoutValue(gridItem.height);

      if (hasHorizontalOffsets && hasExplicitWidth) {
        messages.push({
          id: `grid-horizontal-overconstrained-${gridIndex}`,
          severity: 'warning',
          message: 'Grid uses left/right together with width. This may over-constrain horizontal layout.',
          path: `${gridPath}.width`,
          section: 'grid',
        });
      }

      if (hasVerticalOffsets && hasExplicitHeight) {
        messages.push({
          id: `grid-vertical-overconstrained-${gridIndex}`,
          severity: 'warning',
          message: 'Grid uses top/bottom together with height. This may over-constrain vertical layout.',
          path: `${gridPath}.height`,
          section: 'grid',
        });
      }
    });
  }

  const hasPolarSeries = seriesList.some((series) => {
    const coordinateSystem = typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d';
    const seriesType = getSeriesType(series);
    return coordinateSystem === 'polar' && (seriesType === 'line' || seriesType === 'bar' || seriesType === 'scatter' || seriesType === 'effectScatter');
  });

  if (hasPolarSeries) {
    if (!polar) {
      messages.push({
        id: 'polar-missing-component',
        severity: 'warning',
        message: 'Polar series requires option.polar configuration.',
        path: polarPathPrefix,
        section: 'polar',
        fixes: [
          {
            id: 'create-default-polar',
            label: 'Create default polar',
            kind: 'batch_set_paths',
            payload: {
              entries: [
                { path: `${polarPathPrefix}.center`, value: ['50%', '55%'] },
                { path: `${polarPathPrefix}.radius`, value: '70%' },
              ],
            },
          },
        ],
      });
    }

    if (!angleAxis) {
      messages.push({
        id: 'polar-missing-angle-axis',
        severity: 'warning',
        message: 'Polar series requires an angleAxis definition.',
        path: angleAxisPathPrefix,
        section: 'angleAxis',
        fixes: [
          {
            id: 'create-default-angle-axis',
            label: 'Create default angleAxis',
            kind: 'batch_set_paths',
            payload: {
              entries: [
                { path: `${angleAxisPathPrefix}.type`, value: 'category' },
                { path: `${angleAxisPathPrefix}.show`, value: true },
              ],
            },
          },
        ],
      });
    }

    if (!radiusAxis) {
      messages.push({
        id: 'polar-missing-radius-axis',
        severity: 'warning',
        message: 'Polar series requires a radiusAxis definition.',
        path: radiusAxisPathPrefix,
        section: 'radiusAxis',
        fixes: [
          {
            id: 'create-default-radius-axis',
            label: 'Create default radiusAxis',
            kind: 'batch_set_paths',
            payload: {
              entries: [
                { path: `${radiusAxisPathPrefix}.type`, value: 'value' },
                { path: `${radiusAxisPathPrefix}.show`, value: true },
              ],
            },
          },
        ],
      });
    }
  }

  const hasParallelSeries = seriesList.some((series) => getSeriesType(series) === 'parallel');
  if (hasParallelSeries) {
    if (!parallel) {
      messages.push({
        id: 'parallel-missing-component',
        severity: 'warning',
        message: 'Parallel series requires option.parallel configuration.',
        path: parallelPathPrefix,
        section: 'parallel',
        fixes: [
          {
            id: 'create-default-parallel',
            label: 'Create default parallel',
            kind: 'batch_set_paths',
            payload: {
              entries: [
                { path: `${parallelPathPrefix}.left`, value: '8%' },
                { path: `${parallelPathPrefix}.right`, value: '10%' },
                { path: `${parallelPathPrefix}.top`, value: '15%' },
                { path: `${parallelPathPrefix}.bottom`, value: '15%' },
              ],
            },
          },
        ],
      });
    }

    if (parallelAxisItems.length < 2) {
      messages.push({
        id: 'parallel-missing-axes',
        severity: 'warning',
        message: 'Parallel coordinates should define at least two parallelAxis entries.',
        path: parallelAxisPathPrefix,
        section: 'parallelAxis',
        fixes: [
          {
            id: 'create-default-parallel-axes',
            label: 'Create 2 default parallelAxis items',
            kind: 'set_path',
            payload: {
              path: 'parallelAxis',
              value: [
                { dim: 0, name: 'Dimension 1', type: 'value' },
                { dim: 1, name: 'Dimension 2', type: 'value' },
              ],
            },
          },
        ],
      });
    }
  }

  const hasCalendarSeries = seriesList.some(
    (series) =>
      getSeriesType(series) === 'heatmap' &&
      (typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d') === 'calendar',
  );
  if (hasCalendarSeries) {
    const rangeValue = calendar?.range;
    if (!(typeof rangeValue === 'string' && rangeValue.trim().length > 0) && !Array.isArray(rangeValue)) {
      messages.push({
        id: 'calendar-missing-range',
        severity: 'warning',
        message: 'Calendar charts should define calendar.range (for example a year).',
        path: `${calendarPathPrefix}.range`,
        section: 'calendar',
        fixes: [
          {
            id: 'set-calendar-range',
            label: "Set calendar.range to '2026'",
            kind: 'set_path',
            payload: { path: `${calendarPathPrefix}.range`, value: '2026' },
          },
        ],
      });
    }
  }

  const hasGeoSeries = seriesList.some(
    (series) => (typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d') === 'geo',
  );
  if (hasGeoSeries) {
    if (!geo || typeof geo.map !== 'string' || geo.map.trim().length === 0) {
      messages.push({
        id: 'geo-missing-map',
        severity: 'warning',
        message: 'Geo coordinate charts should define geo.map (for example world-lite).',
        path: `${geoPathPrefix}.map`,
        section: 'geo',
        fixes: [
          {
            id: 'set-default-geo-map',
            label: "Set geo.map to 'world-lite'",
            kind: 'set_path',
            payload: { path: `${geoPathPrefix}.map`, value: 'world-lite' },
          },
        ],
      });
    }
  }

  if (selectedSeries && !getSeriesType(selectedSeries)) {
    messages.push({
      id: 'selected-series-missing-type',
      severity: 'error',
      message:
        'Selected series is missing a valid type (line/bar/pie/candlestick/scatter/effectScatter/radar/heatmap/funnel/gauge/parallel/map).',
      path: `series.${context.selectedSeriesIndex}.type`,
      section: 'series',
      fixes: [
        {
          id: 'set-selected-series-type',
          label: 'Set selected series type',
          kind: 'set_selected_series_type',
          payload: { type: 'current_or_line' },
        },
      ],
    });
  }

  seriesList.forEach((series, index) => {
    const seriesType = getSeriesType(series);
    const data = Array.isArray(series.data) ? series.data : [];

    if (seriesType === 'line') {
      const hasPieLikeObjects = data.some((item) => isObjectCell(item));
      if (hasPieLikeObjects) {
        messages.push({
          id: `line-pie-style-data-${index}`,
          severity: 'warning',
          message: 'Line series usually expects primitive values, not pie-style objects.',
          path: `series.${index}.data`,
          section: 'series',
        });
      }
    }

    if (seriesType === 'pie') {
      const hasPrimitiveOnly = data.length > 0 && data.every((item) => isPrimitiveCell(item));
      if (hasPrimitiveOnly) {
        messages.push({
          id: `pie-primitive-data-${index}`,
          severity: 'warning',
          message: 'Pie series data usually needs objects like { value, name }.',
          path: `series.${index}.data`,
          section: 'series',
        });
      }
    }

    if (seriesType === 'candlestick') {
      const axisType = getAxisType(xAxis);
      if (axisType !== 'category' && axisType !== 'time') {
        messages.push({
          id: `candlestick-xaxis-type-${index}`,
          severity: 'warning',
          message: 'Candlestick series works best with xAxis.type = category or time.',
          path: `${xAxisPathPrefix}.type`,
          section: 'xAxis',
          fixes: [
            {
              id: 'set-candlestick-xaxis-category',
              label: 'Set xAxis.type to category',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `${xAxisPathPrefix}.show`, value: true },
                  { path: `${xAxisPathPrefix}.type`, value: 'category' },
                ],
              },
            },
          ],
        });
      }

      if (tooltip?.trigger !== 'axis') {
        messages.push({
          id: `candlestick-tooltip-axis-${index}`,
          severity: 'warning',
          message: "Candlestick series generally works best with tooltip.trigger = 'axis'.",
          path: `${tooltipPathPrefix}.trigger`,
          section: 'tooltip',
          fixes: [
            {
              id: 'set-tooltip-trigger-axis',
              label: "Set tooltip.trigger to 'axis'",
              kind: 'set_path',
              payload: { path: `${tooltipPathPrefix}.trigger`, value: 'axis' },
            },
          ],
        });
      }

      const encode = isRecord(series.encode) ? series.encode : undefined;
      const encodeY = encode?.y;
      const hasValidEncode = Array.isArray(encodeY) && encodeY.length === 4;
      const hasValidSeriesData =
        Array.isArray(series.data) &&
        series.data.some((row) => Array.isArray(row) && row.length >= 4);
      const hasLikelyDatasetOHLC = datasetColumnCount >= 5;

      if (!hasValidEncode && !hasValidSeriesData && !hasLikelyDatasetOHLC) {
        messages.push({
          id: `candlestick-missing-ohlc-mapping-${index}`,
          severity: 'warning',
          message: 'Candlestick series should map four values in Open, Close, Low, High order.',
          path: `series.${index}.encode.y`,
          section: 'series',
          fixes: [
            {
              id: 'set-default-candlestick-encode',
              label: 'Apply default OHLC encode',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `series.${index}.encode.x`, value: 0 },
                  { path: `series.${index}.encode.y`, value: [1, 2, 3, 4] },
                ],
              },
            },
          ],
        });
      }
    }

    if (seriesType === 'scatter' || seriesType === 'effectScatter') {
      const coordinateSystem = typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d';
      const isCartesianScatter = coordinateSystem === 'cartesian2d';

      if (!isCartesianScatter) {
        if (coordinateSystem === 'geo' && (!geo || typeof geo.map !== 'string' || geo.map.trim().length === 0)) {
          messages.push({
            id: `geo-series-missing-map-${index}`,
            severity: 'warning',
            message: 'Geo scatter/effectScatter needs geo.map configured.',
            path: `${geoPathPrefix}.map`,
            section: 'geo',
            fixes: [
              {
                id: 'set-default-geo-map',
                label: "Set geo.map to 'world-lite'",
                kind: 'set_path',
                payload: { path: `${geoPathPrefix}.map`, value: 'world-lite' },
              },
            ],
          });
        }
        return;
      }

      const xType = getAxisType(xAxis);
      const yType = getAxisType(yAxis);

      if (xType !== 'value') {
        messages.push({
          id: `${seriesType}-xaxis-value-${index}`,
          severity: 'warning',
          message: `${seriesType} series typically requires xAxis.type = value in cartesian2d.`,
          path: `${xAxisPathPrefix}.type`,
          section: 'xAxis',
          fixes: [
            {
              id: 'set-scatter-xaxis-value',
              label: 'Set xAxis.type to value',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `${xAxisPathPrefix}.show`, value: true },
                  { path: `${xAxisPathPrefix}.type`, value: 'value' },
                ],
              },
            },
          ],
        });
      }

      if (yType !== 'value') {
        messages.push({
          id: `${seriesType}-yaxis-value-${index}`,
          severity: 'warning',
          message: `${seriesType} series typically requires yAxis.type = value in cartesian2d.`,
          path: `${yAxisPathPrefix}.type`,
          section: 'yAxis',
          fixes: [
            {
              id: 'set-scatter-yaxis-value',
              label: 'Set yAxis.type to value',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `${yAxisPathPrefix}.show`, value: true },
                  { path: `${yAxisPathPrefix}.type`, value: 'value' },
                ],
              },
            },
          ],
        });
      }

      const encode = isRecord(series.encode) ? series.encode : undefined;
      const hasEncodeX = encode?.x !== undefined && encode?.x !== null && String(encode?.x).trim() !== '';
      const hasEncodeY = encode?.y !== undefined && encode?.y !== null && String(encode?.y).trim() !== '';

      const datasetPresent = datasetValid && rawDatasetSource.length > 1;
      if (datasetPresent && (!hasEncodeX || !hasEncodeY)) {
        messages.push({
          id: `${seriesType}-missing-encode-${index}`,
          severity: 'warning',
          message: `Dataset-driven ${seriesType} should define encode.x and encode.y mappings.`,
          path: `series.${index}.encode`,
          section: 'series',
          fixes: [
            {
              id: 'set-default-scatter-encode',
              label: 'Apply default scatter encode',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `series.${index}.encode.x`, value: 0 },
                  { path: `series.${index}.encode.y`, value: 1 },
                  { path: `series.${index}.encode.tooltip`, value: [0, 1] },
                ],
              },
            },
          ],
        });
      }
    }

    if (seriesType === 'radar') {
      const hasRadarIndicators = Array.isArray(radar?.indicator) && radar.indicator.length >= 3;
      const hasEnoughDatasetDimensions = datasetColumnCount >= 4;

      if (!hasRadarIndicators && !hasEnoughDatasetDimensions) {
        messages.push({
          id: `radar-missing-indicators-${index}`,
          severity: 'warning',
          message: 'Radar series should define radar.indicator or provide dataset dimensions to infer them.',
          path: `${radarPathPrefix}.indicator`,
          section: 'radar',
          fixes: [
            {
              id: 'set-default-radar-indicators',
              label: 'Set default radar indicators',
              kind: 'set_path',
              payload: {
                path: `${radarPathPrefix}.indicator`,
                value: [
                  { name: 'Metric 1', max: 100 },
                  { name: 'Metric 2', max: 100 },
                  { name: 'Metric 3', max: 100 },
                ],
              },
            },
          ],
        });
      }
    }

    if (seriesType === 'heatmap') {
      const xType = getAxisType(xAxis);
      const yType = getAxisType(yAxis);
      const coordinateSystem = typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d';

      if (coordinateSystem === 'cartesian2d' && (!axisIsShown(xAxis) || !axisIsShown(yAxis))) {
        messages.push({
          id: `heatmap-hidden-axes-${index}`,
          severity: 'warning',
          message: 'Heatmap with cartesian2d coordinate system should have visible xAxis and yAxis.',
          path: `${xAxisPathPrefix}.show`,
          section: 'xAxis',
          fixes: [
            {
              id: 'show-heatmap-axes',
              label: 'Show xAxis and yAxis',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `${xAxisPathPrefix}.show`, value: true },
                  { path: `${yAxisPathPrefix}.show`, value: true },
                  { path: `${xAxisPathPrefix}.type`, value: 'category' },
                  { path: `${yAxisPathPrefix}.type`, value: 'category' },
                ],
              },
            },
          ],
        });
      }

      if (coordinateSystem === 'cartesian2d' && (!xType || !yType)) {
        messages.push({
          id: `heatmap-axis-types-${index}`,
          severity: 'warning',
          message: 'Heatmap should define axis types for xAxis and yAxis when using cartesian2d.',
          path: `${xAxisPathPrefix}.type`,
          section: 'xAxis',
          fixes: [
            {
              id: 'set-heatmap-axis-types',
              label: 'Set axis types to category',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `${xAxisPathPrefix}.type`, value: 'category' },
                  { path: `${yAxisPathPrefix}.type`, value: 'category' },
                ],
              },
            },
          ],
        });
      }

      const encode = isRecord(series.encode) ? series.encode : undefined;
      const hasEncodeX = encode?.x !== undefined && encode?.x !== null && String(encode?.x).trim() !== '';
      const hasEncodeY = encode?.y !== undefined && encode?.y !== null && String(encode?.y).trim() !== '';
      const hasEncodeValue = encode?.value !== undefined && encode?.value !== null && String(encode?.value).trim() !== '';
      const datasetPresent = datasetValid && rawDatasetSource.length > 1;
      if (datasetPresent && (!hasEncodeX || !hasEncodeY || !hasEncodeValue)) {
        messages.push({
          id: `heatmap-missing-encode-${index}`,
          severity: 'warning',
          message: 'Dataset-driven heatmap should define encode.x, encode.y, and encode.value mappings.',
          path: `series.${index}.encode`,
          section: 'series',
          fixes: [
            {
              id: 'set-default-heatmap-encode',
              label: 'Apply default heatmap encode',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `series.${index}.encode.x`, value: 0 },
                  { path: `series.${index}.encode.y`, value: 1 },
                  { path: `series.${index}.encode.value`, value: [2] },
                  { path: `series.${index}.encode.tooltip`, value: [0, 1, 2] },
                ],
              },
            },
          ],
        });
      }
    }

    if (seriesType === 'funnel') {
      if (tooltip?.trigger !== 'item') {
        messages.push({
          id: `funnel-tooltip-item-${index}`,
          severity: 'warning',
          message: "Funnel series generally works best with tooltip.trigger = 'item'.",
          path: `${tooltipPathPrefix}.trigger`,
          section: 'tooltip',
          fixes: [
            {
              id: 'set-funnel-tooltip-item',
              label: "Set tooltip.trigger to 'item'",
              kind: 'set_path',
              payload: { path: `${tooltipPathPrefix}.trigger`, value: 'item' },
            },
          ],
        });
      }

      const hasPrimitiveOnly = data.length > 0 && data.every((item) => isPrimitiveCell(item));
      if (hasPrimitiveOnly) {
        messages.push({
          id: `funnel-primitive-data-${index}`,
          severity: 'warning',
          message: 'Funnel series data usually needs objects like { name, value }.',
          path: `series.${index}.data`,
          section: 'series',
        });
      }
    }

    if (seriesType === 'gauge') {
      const min = typeof series.min === 'number' ? series.min : 0;
      const max = typeof series.max === 'number' ? series.max : 100;
      if (max <= min) {
        messages.push({
          id: `gauge-invalid-range-${index}`,
          severity: 'warning',
          message: 'Gauge max should be greater than min.',
          path: `series.${index}.max`,
          section: 'series',
          fixes: [
            {
              id: 'set-default-gauge-range',
              label: 'Set min/max to 0/100',
              kind: 'batch_set_paths',
              payload: {
                entries: [
                  { path: `series.${index}.min`, value: 0 },
                  { path: `series.${index}.max`, value: 100 },
                ],
              },
            },
          ],
        });
      }

      const gaugeData = Array.isArray(series.data) ? series.data : [];
      const hasGaugeValue = gaugeData.some((item) => isRecord(item) && typeof item.value === 'number');
      if (!hasGaugeValue) {
        messages.push({
          id: `gauge-missing-value-${index}`,
          severity: 'warning',
          message: 'Gauge series should include a numeric value in series.data.',
          path: `series.${index}.data`,
          section: 'series',
          fixes: [
            {
              id: 'set-default-gauge-value',
              label: 'Set default gauge value',
              kind: 'set_path',
              payload: { path: `series.${index}.data`, value: [{ value: 50, name: 'KPI' }] },
            },
          ],
        });
      }
    }

    if (seriesType === 'parallel') {
      const rows = Array.isArray(series.data) ? series.data : [];
      const longestRow = rows.reduce((max, row) => {
        if (Array.isArray(row)) {
          return Math.max(max, row.length);
        }
        return max;
      }, 0);
      const dimensionCount = Math.max(parallelAxisItems.length, longestRow, datasetColumnCount > 0 ? datasetColumnCount - 1 : 0);

      if (dimensionCount < 2) {
        messages.push({
          id: `parallel-too-few-dimensions-${index}`,
          severity: 'warning',
          message: 'Parallel chart needs at least two numeric dimensions for meaningful rendering.',
          path: `series.${index}.data`,
          section: 'series',
        });
      }
    }

    if (seriesType === 'heatmap') {
      const coordinateSystem = typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d';
      if (coordinateSystem === 'calendar') {
        const heatmapRows = Array.isArray(series.data) ? series.data : [];
        const hasDateValueTuples = heatmapRows.some(
          (entry) =>
            Array.isArray(entry) &&
            entry.length >= 2 &&
            typeof entry[0] === 'string' &&
            (typeof entry[1] === 'number' || (typeof entry[1] === 'string' && entry[1].trim() !== '')),
        );

        if (!hasDateValueTuples && !(datasetValid && rawDatasetSource.length > 1)) {
          messages.push({
            id: `calendar-heatmap-invalid-shape-${index}`,
            severity: 'warning',
            message: 'Calendar heatmap expects [date, value] rows or a matching date/value dataset.',
            path: `series.${index}.data`,
            section: 'series',
          });
        }
      }
    }

    if (seriesType === 'map') {
      const mapName = typeof series.map === 'string' ? series.map.trim() : '';
      if (!mapName) {
        messages.push({
          id: `map-series-missing-map-${index}`,
          severity: 'warning',
          message: 'Map series requires a map name (series.map).',
          path: `series.${index}.map`,
          section: 'series',
          fixes: [
            {
              id: 'set-default-map-series-map',
              label: "Set series.map to 'world-lite'",
              kind: 'set_path',
              payload: { path: `series.${index}.map`, value: 'world-lite' },
            },
          ],
        });
      }
    }
  });

  const legendShown = legend ? legend.show !== false : false;
  if (legendShown) {
    const hasNamedSeries = seriesList.some((series) => hasNonEmptyString(series.name));
    if (!hasNamedSeries) {
      messages.push({
        id: 'legend-no-series-names',
        severity: 'warning',
        message: 'Legend is shown, but series names are empty.',
        path: `${legendPathPrefix}.show`,
        section: 'legend',
        fixes: [
          {
            id: 'auto-name-series',
            label: 'Auto-name unnamed series',
            kind: 'auto_name_series',
          },
        ],
      });
    }
  }

  if (title?.show === true && !hasNonEmptyString(title.text)) {
    messages.push({
      id: 'title-shown-empty-text',
      severity: 'warning',
      message: 'title.show is true, but title.text is empty.',
      path: `${titlePathPrefix}.text`,
      section: 'title',
      fixes: [
        {
          id: 'set-default-title-text',
          label: "Set title.text to 'Chart Title'",
          kind: 'set_path',
          payload: { path: `${titlePathPrefix}.text`, value: 'Chart Title' },
        },
      ],
    });
  }

  const uniqueSeriesTypes = new Set(seriesList.map((series) => getSeriesType(series)).filter(Boolean));
  if (uniqueSeriesTypes.size > 1) {
    messages.push({
      id: 'mixed-series-types',
      severity: 'info',
      message: 'Multiple series types are mixed. Ensure axis/tooltip settings fit all series.',
      path: 'series',
      section: 'series',
    });
  }

  const datasetPresent = datasetValid && rawDatasetSource.length > 0;
  if (datasetPresent && hasAxisData(xAxis)) {
    messages.push({
      id: 'xaxis-data-and-dataset-source',
      severity: 'info',
      message: 'xAxis.data and dataset.source are both set. Confirm which data source should drive the chart.',
      path: `${xAxisPathPrefix}.data`,
      section: 'xAxis',
      fixes: [
        {
          id: 'clear-xaxis-data',
          label: 'Clear xAxis.data',
          kind: 'clear_path',
          payload: { path: `${xAxisPathPrefix}.data` },
        },
      ],
    });
  }

  return { messages };
};
