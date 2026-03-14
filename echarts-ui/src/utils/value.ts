export const cloneValue = <T>(value: T): T => {
  if (value === null || value === undefined) {
    return value;
  }

  if (typeof value === 'object') {
    return JSON.parse(JSON.stringify(value)) as T;
  }

  return value;
};
