import { describe, expect, it } from 'vitest';
import type { EditorOption } from '../types/echarts';
import {
  addOptionObjectItem,
  ensureOptionObjectArray,
  getOptionObjectArray,
  removeOptionObjectItem,
} from './optionArrays';

describe('optionArrays utils', () => {
  it('converts object-backed option fields into object arrays', () => {
    const option = {
      xAxis: { type: 'category', name: 'Primary' },
    } as EditorOption;

    const normalized = ensureOptionObjectArray(option, 'xAxis');
    const xAxisItems = getOptionObjectArray(normalized, 'xAxis');

    expect(xAxisItems).toHaveLength(1);
    expect(xAxisItems[0]).toMatchObject({ type: 'category', name: 'Primary' });
  });

  it('adds and removes array items while honoring minItems', () => {
    const start = ensureOptionObjectArray(
      {
        xAxis: [{ name: 'Axis 1' }],
      } as EditorOption,
      'xAxis',
    );

    const added = addOptionObjectItem(start, 'xAxis', { name: 'Axis 2' });
    expect(added.nextIndex).toBe(1);
    expect(getOptionObjectArray(added.option, 'xAxis')).toHaveLength(2);

    const removed = removeOptionObjectItem(added.option, 'xAxis', 1, 1);
    expect(getOptionObjectArray(removed.option, 'xAxis')).toHaveLength(1);

    const blocked = removeOptionObjectItem(removed.option, 'xAxis', 0, 1);
    expect(getOptionObjectArray(blocked.option, 'xAxis')).toHaveLength(1);
    expect(blocked.nextIndex).toBe(0);
  });

  it('supports new coordinate-system component arrays', () => {
    const option = {
      polar: { center: ['50%', '55%'], radius: '70%' },
      parallelAxis: [{ dim: 0, type: 'value' }],
      calendar: [],
    } as EditorOption;

    const normalizedPolar = ensureOptionObjectArray(option, 'polar');
    expect(getOptionObjectArray(normalizedPolar, 'polar')).toHaveLength(1);

    const addedCalendar = addOptionObjectItem(normalizedPolar, 'calendar', { range: '2026' });
    expect(getOptionObjectArray(addedCalendar.option, 'calendar')).toHaveLength(1);
    expect(addedCalendar.nextIndex).toBe(0);

    const addedParallelAxis = addOptionObjectItem(addedCalendar.option, 'parallelAxis', { dim: 1, type: 'value' });
    expect(getOptionObjectArray(addedParallelAxis.option, 'parallelAxis')).toHaveLength(2);
  });
});
