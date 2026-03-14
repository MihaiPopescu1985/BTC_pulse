const isArrayIndex = (segment: string): boolean => /^\d+$/.test(segment);

const toPath = (path: string): string[] => path.split('.').filter(Boolean);

export const getByPath = (target: unknown, path: string): unknown => {
  const segments = toPath(path);
  let current: unknown = target;

  for (const segment of segments) {
    if (current === null || current === undefined) {
      return undefined;
    }

    if (isArrayIndex(segment)) {
      const index = Number(segment);
      if (!Array.isArray(current)) {
        return undefined;
      }
      current = current[index];
      continue;
    }

    if (typeof current !== 'object') {
      return undefined;
    }

    current = (current as Record<string, unknown>)[segment];
  }

  return current;
};

const cloneBranch = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return [...value];
  }

  if (value && typeof value === 'object') {
    return { ...(value as Record<string, unknown>) };
  }

  return value;
};

export const setByPath = <T extends object>(target: T, path: string, value: unknown): T => {
  const segments = toPath(path);
  if (segments.length === 0) {
    return target;
  }

  const root = cloneBranch(target) as Record<string, unknown>;
  let cursor: unknown = root;

  segments.forEach((segment, index) => {
    const isLast = index === segments.length - 1;
    const next = segments[index + 1];

    if (isArrayIndex(segment)) {
      const idx = Number(segment);
      if (!Array.isArray(cursor)) {
        throw new Error(`Invalid path '${path}': '${segment}' expects array context.`);
      }

      if (isLast) {
        cursor[idx] = value;
      } else {
        const existing = cursor[idx];
        const fallback = isArrayIndex(next) ? [] : {};
        const cloned = cloneBranch(existing) ?? fallback;
        cursor[idx] = cloned;
        cursor = cloned;
      }
      return;
    }

    const record = cursor as Record<string, unknown>;

    if (isLast) {
      record[segment] = value;
      return;
    }

    const existing = record[segment];
    const fallback = isArrayIndex(next) ? [] : {};
    const cloned = cloneBranch(existing) ?? fallback;
    record[segment] = cloned;
    cursor = cloned;
  });

  return root as T;
};
