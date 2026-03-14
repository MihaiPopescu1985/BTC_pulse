import type { EditorOption } from '../types/echarts';
import { getByPath, setByPath } from './path';
import { cloneValue } from './value';

export type OptionObjectItem = Record<string, unknown>;

const asObjectItem = (value: unknown): OptionObjectItem | null => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as OptionObjectItem;
  }

  return null;
};

export const getOptionObjectArray = (option: EditorOption, path: string): OptionObjectItem[] => {
  const current = getByPath(option, path);

  if (Array.isArray(current)) {
    return current
      .map((item) => asObjectItem(item))
      .filter((item): item is OptionObjectItem => item !== null);
  }

  const asObject = asObjectItem(current);
  if (asObject) {
    return [asObject];
  }

  return [];
};

export const setOptionObjectArray = (option: EditorOption, path: string, items: OptionObjectItem[]): EditorOption => {
  const nextItems = items.map((item) => cloneValue(item));
  return setByPath(option, path, nextItems);
};

export const ensureOptionObjectArray = (option: EditorOption, path: string): EditorOption => {
  const current = getByPath(option, path);

  if (Array.isArray(current)) {
    return option;
  }

  const asObject = asObjectItem(current);
  if (asObject) {
    return setOptionObjectArray(option, path, [asObject]);
  }

  return setOptionObjectArray(option, path, []);
};

export const addOptionObjectItem = (
  option: EditorOption,
  path: string,
  defaultItem: OptionObjectItem,
): { option: EditorOption; nextIndex: number } => {
  const normalized = ensureOptionObjectArray(option, path);
  const items = getOptionObjectArray(normalized, path);
  const nextIndex = items.length;
  const nextItems = [...items, cloneValue(defaultItem)];

  return {
    option: setOptionObjectArray(normalized, path, nextItems),
    nextIndex,
  };
};

export const removeOptionObjectItem = (
  option: EditorOption,
  path: string,
  index: number,
  minItems = 0,
): { option: EditorOption; nextIndex: number } => {
  const normalized = ensureOptionObjectArray(option, path);
  const items = getOptionObjectArray(normalized, path);

  if (items.length <= minItems || index < 0 || index >= items.length) {
    const clamped = Math.max(0, Math.min(index, Math.max(0, items.length - 1)));
    return { option: normalized, nextIndex: clamped };
  }

  const nextItems = items.filter((_, itemIndex) => itemIndex !== index);
  const nextIndex = Math.max(0, Math.min(index, Math.max(0, nextItems.length - 1)));

  return {
    option: setOptionObjectArray(normalized, path, nextItems),
    nextIndex,
  };
};
