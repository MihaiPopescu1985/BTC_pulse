import { describe, expect, it } from 'vitest';
import { getByPath, setByPath } from './path';

describe('path utils', () => {
  it('sets and gets nested values with array segments', () => {
    const updated = setByPath({} as Record<string, unknown>, 'xAxis.0.name', 'Secondary Axis');

    expect(getByPath(updated, 'xAxis.0.name')).toBe('Secondary Axis');
    expect(getByPath(updated, 'xAxis.0')).toEqual({ name: 'Secondary Axis' });
  });

  it('does not mutate the original object', () => {
    const original = {
      xAxis: [{ name: 'Primary Axis' }],
    };

    const updated = setByPath(original, 'xAxis.0.name', 'Secondary Axis');

    expect(original.xAxis[0].name).toBe('Primary Axis');
    expect(getByPath(updated, 'xAxis.0.name')).toBe('Secondary Axis');
  });

  it('returns undefined for missing paths', () => {
    expect(getByPath({ xAxis: [{ name: 'Axis' }] }, 'xAxis.1.name')).toBeUndefined();
    expect(getByPath({ xAxis: [] }, 'xAxis.invalid')).toBeUndefined();
  });
});
