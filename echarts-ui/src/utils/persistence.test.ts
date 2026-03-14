import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { EditorOption } from '../types/echarts';
import {
  buildSavedSession,
  clearSession,
  loadSession,
  saveSession,
  SESSION_VERSION,
  STORAGE_KEYS,
} from './persistence';

describe('persistence utils', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('saves and restores a valid session payload', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);

    const session = buildSavedSession({
      option: {
        series: [{ type: 'bar', data: [10, 20] }],
      } as EditorOption,
      selectedSeriesIndex: 0,
      lastPreset: 'basic-bar',
    });

    expect(session.version).toBe(SESSION_VERSION);
    expect(saveSession(session)).toBe(true);

    const restored = loadSession();
    expect(restored.ok).toBe(true);
    if (restored.ok) {
      expect(restored.session.savedAt).toBe(1700000000000);
      expect(restored.session.lastPreset).toBe('basic-bar');
      expect(restored.session.option).toMatchObject({
        series: [{ type: 'bar', data: [10, 20] }],
      });
    }
  });

  it('returns parse_failed and invalid_shape when storage content is bad', () => {
    localStorage.setItem(STORAGE_KEYS.session, '{invalid');
    expect(loadSession()).toEqual({ ok: false, reason: 'parse_failed' });

    localStorage.setItem(STORAGE_KEYS.session, JSON.stringify({ version: SESSION_VERSION }));
    expect(loadSession()).toEqual({ ok: false, reason: 'invalid_shape' });
  });

  it('clears saved session key', () => {
    localStorage.setItem(STORAGE_KEYS.session, JSON.stringify({ any: 'value' }));
    expect(clearSession()).toBe(true);
    expect(localStorage.getItem(STORAGE_KEYS.session)).toBeNull();
  });
});
