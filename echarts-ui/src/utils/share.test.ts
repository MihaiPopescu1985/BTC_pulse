import { describe, expect, it } from 'vitest';
import type { EditorOption } from '../types/echarts';
import {
  buildSharedState,
  decodeSharedStateFromHash,
  encodeSharedStateToHash,
  SHARE_HASH_PARAM,
} from './share';

const encodeRawHashValue = (value: unknown): string => {
  const json = JSON.stringify(value);
  return btoa(json).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

describe('share utils', () => {
  it('encodes and decodes shared state roundtrip', () => {
    const state = buildSharedState({
      option: {
        series: [{ type: 'line', data: [1, 2, 3] }],
      } as EditorOption,
      selectedSeriesIndex: 0,
      lastPreset: 'basic-line',
    });

    const hash = encodeSharedStateToHash(state);
    expect(hash).not.toBeNull();

    const decoded = decodeSharedStateFromHash(hash!);
    expect(decoded.ok).toBe(true);
    if (decoded.ok) {
      expect(decoded.state.selectedSeriesIndex).toBe(0);
      expect(decoded.state.lastPreset).toBe('basic-line');
      expect(decoded.state.option).toMatchObject({
        series: [{ type: 'line', data: [1, 2, 3] }],
      });
    }
  });

  it('returns useful failure reasons for missing/invalid hash data', () => {
    expect(decodeSharedStateFromHash('#')).toEqual({ ok: false, reason: 'not_found' });
    expect(decodeSharedStateFromHash(`#${SHARE_HASH_PARAM}=%%%`)).toEqual({ ok: false, reason: 'decode_failed' });

    const invalidShapeHash = `#${SHARE_HASH_PARAM}=${encodeRawHashValue({ version: 1 })}`;
    expect(decodeSharedStateFromHash(invalidShapeHash)).toEqual({ ok: false, reason: 'invalid_shape' });
  });
});
