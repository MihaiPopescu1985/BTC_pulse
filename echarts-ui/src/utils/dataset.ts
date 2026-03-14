import type { EditorOption } from '../types/echarts';
import { cloneValue } from './value';

export type DatasetCell = string | number | boolean | null;
export type DatasetRow = DatasetCell[];
export type DatasetSource = DatasetRow[];

const DEFAULT_SOURCE: DatasetSource = [
  ['category', 'value'],
  ['A', 120],
];

const cloneSource = (source: DatasetSource): DatasetSource => source.map((row) => [...row]);

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
};

const parseDataCellInput = (input: string): DatasetCell => {
  const trimmed = input.trim();

  if (trimmed === '') {
    return '';
  }

  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return Number(trimmed);
  }

  if (trimmed.toLowerCase() === 'true') {
    return true;
  }

  if (trimmed.toLowerCase() === 'false') {
    return false;
  }

  if (trimmed.toLowerCase() === 'null') {
    return null;
  }

  return input;
};

const normalizeHeaderCell = (value: unknown, index: number): string => {
  const text = value === null || value === undefined ? '' : String(value);
  const cleaned = text.trim();
  return cleaned || `column_${index + 1}`;
};

const normalizeDataCell = (value: unknown): DatasetCell => {
  if (value === null) {
    return null;
  }

  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'string') {
    return value;
  }

  if (value === undefined) {
    return '';
  }

  return JSON.stringify(value);
};

export const normalizeDatasetSource = (source: unknown): DatasetSource => {
  if (!Array.isArray(source)) {
    return cloneSource(DEFAULT_SOURCE);
  }

  const rows = source
    .filter((row) => Array.isArray(row))
    .map((row) => row as unknown[])
    .map((row, rowIndex) =>
      row.map((cell, colIndex) => (rowIndex === 0 ? normalizeHeaderCell(cell, colIndex) : normalizeDataCell(cell))),
    );

  if (rows.length === 0) {
    return cloneSource(DEFAULT_SOURCE);
  }

  const columnCount = rows.reduce((max, row) => Math.max(max, row.length), 1);

  const normalizedRows = rows.map((row, rowIndex) => {
    const padded = [...row];
    while (padded.length < columnCount) {
      padded.push('');
    }

    if (rowIndex === 0) {
      return padded.map((cell, colIndex) => normalizeHeaderCell(cell, colIndex));
    }

    return padded.map((cell) => normalizeDataCell(cell));
  });

  return normalizedRows as DatasetSource;
};

const getDatasetRecord = (option: EditorOption, datasetIndex = 0): Record<string, unknown> | null => {
  const dataset = option.dataset;

  if (Array.isArray(dataset)) {
    const selected = dataset[datasetIndex];
    return isRecord(selected) ? selected : null;
  }

  if (isRecord(dataset)) {
    if (datasetIndex === 0) {
      return dataset;
    }
    return null;
  }

  return null;
};

export const getDatasetSourceFromOption = (option: EditorOption, datasetIndex = 0): DatasetSource => {
  const datasetRecord = getDatasetRecord(option, datasetIndex);
  return normalizeDatasetSource(datasetRecord?.source);
};

export const setDatasetSourceInOption = (option: EditorOption, source: DatasetSource, datasetIndex = 0): EditorOption => {
  const nextSource = normalizeDatasetSource(source);
  const base = cloneValue(option);

  if (Array.isArray(base.dataset)) {
    const datasets = [...base.dataset];
    while (datasets.length <= datasetIndex) {
      datasets.push({ source: cloneSource(DEFAULT_SOURCE) } as unknown as (typeof datasets)[number]);
    }

    const selected = isRecord(datasets[datasetIndex]) ? datasets[datasetIndex] : {};
    datasets[datasetIndex] = {
      ...selected,
      source: nextSource as unknown,
    } as (typeof datasets)[number];

    return {
      ...base,
      dataset: datasets as unknown as EditorOption['dataset'],
    };
  }

  if (datasetIndex > 0) {
    const first = isRecord(base.dataset) ? base.dataset : { source: cloneSource(DEFAULT_SOURCE) };
    const datasets = [first] as unknown[];

    while (datasets.length <= datasetIndex) {
      datasets.push({ source: cloneSource(DEFAULT_SOURCE) });
    }

    const selected = isRecord(datasets[datasetIndex]) ? (datasets[datasetIndex] as Record<string, unknown>) : {};
    datasets[datasetIndex] = {
      ...selected,
      source: nextSource as unknown,
    };

    return {
      ...base,
      dataset: datasets as unknown as EditorOption['dataset'],
    };
  }

  const datasetObject = isRecord(base.dataset) ? base.dataset : {};
  return {
    ...base,
    dataset: {
      ...datasetObject,
      source: nextSource as unknown,
    } as EditorOption['dataset'],
  };
};

export const updateDatasetCell = (
  source: DatasetSource,
  rowIndex: number,
  colIndex: number,
  input: string,
): DatasetSource => {
  const normalized = normalizeDatasetSource(source);

  return normalized.map((row, currentRowIndex) => {
    if (currentRowIndex !== rowIndex) {
      return [...row];
    }

    return row.map((cell, currentColIndex) => {
      if (currentColIndex !== colIndex) {
        return cell;
      }

      return currentRowIndex === 0 ? normalizeHeaderCell(input, currentColIndex) : parseDataCellInput(input);
    });
  });
};

export const addDatasetRow = (source: DatasetSource): DatasetSource => {
  const normalized = normalizeDatasetSource(source);
  const columnCount = normalized[0]?.length ?? 1;
  const nextRow: DatasetRow = Array(columnCount).fill('');
  return [...normalized.map((row) => [...row]), nextRow];
};

export const removeDatasetRow = (source: DatasetSource, rowIndex: number): DatasetSource => {
  const normalized = normalizeDatasetSource(source);

  if (rowIndex <= 0 || rowIndex >= normalized.length) {
    return normalized;
  }

  const nextRows = normalized.filter((_, index) => index !== rowIndex);
  return nextRows.length > 0 ? nextRows : cloneSource(DEFAULT_SOURCE);
};

export const addDatasetColumn = (source: DatasetSource): DatasetSource => {
  const normalized = normalizeDatasetSource(source);
  const nextColumnIndex = normalized[0].length;

  return normalized.map((row, rowIndex) => {
    const nextRow = [...row];
    nextRow.push(rowIndex === 0 ? `column_${nextColumnIndex + 1}` : '');
    return nextRow;
  });
};

export const removeDatasetColumn = (source: DatasetSource): DatasetSource => {
  const normalized = normalizeDatasetSource(source);
  const columnCount = normalized[0]?.length ?? 1;

  if (columnCount <= 1) {
    return normalized;
  }

  return normalized.map((row) => row.slice(0, row.length - 1));
};

export const rowsToDatasetSource = (rows: string[][]): DatasetSource => {
  if (rows.length === 0) {
    return cloneSource(DEFAULT_SOURCE);
  }

  return normalizeDatasetSource(
    rows.map((row, rowIndex) =>
      row.map((value, colIndex) => (rowIndex === 0 ? normalizeHeaderCell(value, colIndex) : parseDataCellInput(value))),
    ),
  );
};
