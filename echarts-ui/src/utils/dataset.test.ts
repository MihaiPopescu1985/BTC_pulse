import { describe, expect, it } from 'vitest';
import type { EditorOption } from '../types/echarts';
import {
  getDatasetSourceFromOption,
  normalizeDatasetSource,
  setDatasetSourceInOption,
  updateDatasetCell,
} from './dataset';

describe('dataset utils', () => {
  it('normalizes invalid source to a safe default grid', () => {
    const normalized = normalizeDatasetSource(undefined);

    expect(normalized[0]).toEqual(['category', 'value']);
    expect(normalized[1]).toEqual(['A', 120]);
  });

  it('sets and gets dataset source for a selected dataset index', () => {
    const source = [
      ['Month', 'Sales'],
      ['Jan', 120],
      ['Feb', 132],
    ] as const;

    const next = setDatasetSourceInOption({} as EditorOption, source.map((row) => [...row]), 1);

    expect(Array.isArray(next.dataset)).toBe(true);
    expect(getDatasetSourceFromOption(next, 1)).toEqual([
      ['Month', 'Sales'],
      ['Jan', 120],
      ['Feb', 132],
    ]);
  });

  it('parses edited cells as numbers and booleans when possible', () => {
    const start = [
      ['Category', 'Value', 'Enabled'],
      ['A', 120, true],
    ];

    const withNumber = updateDatasetCell(start, 1, 1, '130');
    const withBoolean = updateDatasetCell(withNumber, 1, 2, 'false');

    expect(withNumber[1][1]).toBe(130);
    expect(withBoolean[1][2]).toBe(false);
  });
});
