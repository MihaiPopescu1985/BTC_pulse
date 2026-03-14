import type { EditorOption } from '../types/echarts';

export const STORAGE_KEYS = {
  session: 'echarts-editor/session-v1',
} as const;

export const SESSION_VERSION = 1 as const;

export interface SavedSessionV1 {
  version: typeof SESSION_VERSION;
  option: EditorOption;
  selectedSeriesIndex: number;
  lastPreset: string | null;
  savedAt: number;
}

export type RestoreFailureReason = 'not_found' | 'parse_failed' | 'invalid_shape' | 'storage_unavailable';

export type RestoreResult =
  | { ok: true; session: SavedSessionV1 }
  | { ok: false; reason: RestoreFailureReason };

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
};

const isValidSessionPayload = (value: unknown): value is SavedSessionV1 => {
  if (!isRecord(value)) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  if (candidate.version !== SESSION_VERSION) {
    return false;
  }

  if (!isRecord(candidate.option)) {
    return false;
  }

  if (!Number.isInteger(candidate.selectedSeriesIndex) || (candidate.selectedSeriesIndex as number) < 0) {
    return false;
  }

  if (candidate.lastPreset !== null && typeof candidate.lastPreset !== 'string') {
    return false;
  }

  if (typeof candidate.savedAt !== 'number') {
    return false;
  }

  return true;
};

export const buildSavedSession = (payload: {
  option: EditorOption;
  selectedSeriesIndex: number;
  lastPreset: string | null;
}): SavedSessionV1 => {
  return {
    version: SESSION_VERSION,
    option: payload.option,
    selectedSeriesIndex: payload.selectedSeriesIndex,
    lastPreset: payload.lastPreset,
    savedAt: Date.now(),
  };
};

export const saveSession = (session: SavedSessionV1): boolean => {
  try {
    localStorage.setItem(STORAGE_KEYS.session, JSON.stringify(session));
    return true;
  } catch {
    return false;
  }
};

export const loadSession = (): RestoreResult => {
  let raw: string | null = null;

  try {
    raw = localStorage.getItem(STORAGE_KEYS.session);
  } catch {
    return { ok: false, reason: 'storage_unavailable' };
  }

  if (!raw) {
    return { ok: false, reason: 'not_found' };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, reason: 'parse_failed' };
  }

  if (!isValidSessionPayload(parsed)) {
    return { ok: false, reason: 'invalid_shape' };
  }

  return { ok: true, session: parsed };
};

export const clearSession = (): boolean => {
  try {
    localStorage.removeItem(STORAGE_KEYS.session);
    return true;
  } catch {
    return false;
  }
};
