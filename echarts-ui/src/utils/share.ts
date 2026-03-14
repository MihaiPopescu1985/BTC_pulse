import type { EditorOption } from '../types/echarts';

export const SHARE_VERSION = 1 as const;
export const SHARE_HASH_PARAM = 's';

export interface SharedStateV1 {
  version: typeof SHARE_VERSION;
  option: EditorOption;
  selectedSeriesIndex: number;
  lastPreset: string | null;
}

export type ShareDecodeFailureReason = 'not_found' | 'decode_failed' | 'invalid_shape';

export type ShareDecodeResult =
  | { ok: true; state: SharedStateV1 }
  | { ok: false; reason: ShareDecodeFailureReason };

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
};

const isValidSharedState = (value: unknown): value is SharedStateV1 => {
  if (!isRecord(value)) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  if (candidate.version !== SHARE_VERSION) {
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

  return true;
};

const bytesToBase64Url = (bytes: Uint8Array): string => {
  let binary = '';
  const chunkSize = 0x8000;

  for (let index = 0; index < bytes.length; index += chunkSize) {
    const chunk = bytes.subarray(index, index + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

const base64UrlToBytes = (encoded: string): Uint8Array => {
  const normalized = encoded.replace(/-/g, '+').replace(/_/g, '/');
  const paddingLength = (4 - (normalized.length % 4)) % 4;
  const padded = `${normalized}${'='.repeat(paddingLength)}`;
  const binary = atob(padded);

  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    output[index] = binary.charCodeAt(index);
  }

  return output;
};

const getTokenFromHash = (hash: string): string | null => {
  const trimmed = hash.replace(/^#/, '');
  if (!trimmed) {
    return null;
  }

  const params = new URLSearchParams(trimmed);
  return params.get(SHARE_HASH_PARAM);
};

export const buildSharedState = (payload: {
  option: EditorOption;
  selectedSeriesIndex: number;
  lastPreset: string | null;
}): SharedStateV1 => {
  return {
    version: SHARE_VERSION,
    option: payload.option,
    selectedSeriesIndex: payload.selectedSeriesIndex,
    lastPreset: payload.lastPreset,
  };
};

export const encodeSharedStateToHash = (state: SharedStateV1): string | null => {
  try {
    const json = JSON.stringify(state);
    const bytes = new TextEncoder().encode(json);
    const encoded = bytesToBase64Url(bytes);
    return `#${SHARE_HASH_PARAM}=${encoded}`;
  } catch {
    return null;
  }
};

export const decodeSharedStateFromHash = (hash: string): ShareDecodeResult => {
  const token = getTokenFromHash(hash);
  if (!token) {
    return { ok: false, reason: 'not_found' };
  }

  let parsed: unknown;
  try {
    const bytes = base64UrlToBytes(token);
    const json = new TextDecoder().decode(bytes);
    parsed = JSON.parse(json);
  } catch {
    return { ok: false, reason: 'decode_failed' };
  }

  if (!isValidSharedState(parsed)) {
    return { ok: false, reason: 'invalid_shape' };
  }

  return { ok: true, state: parsed };
};

export const buildShareLink = (hash: string): string => {
  const base = `${window.location.origin}${window.location.pathname}${window.location.search}`;
  return `${base}${hash}`;
};
