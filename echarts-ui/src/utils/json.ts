export const toPrettyJson = (value: unknown): string => JSON.stringify(value, null, 2);

export const parseJson = <T = unknown>(input: string): T => JSON.parse(input) as T;
