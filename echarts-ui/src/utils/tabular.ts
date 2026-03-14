export type TabularDelimiter = ',' | '\t';

export const detectTabularDelimiter = (text: string): TabularDelimiter => {
  return text.includes('\t') ? '\t' : ',';
};

const parseDelimitedLine = (line: string, delimiter: TabularDelimiter): string[] => {
  const values: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];

    if (char === '"') {
      const nextChar = line[index + 1];
      if (inQuotes && nextChar === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (!inQuotes && char === delimiter) {
      values.push(current);
      current = '';
      continue;
    }

    current += char;
  }

  values.push(current);
  return values;
};

export const parseTabularText = (input: string): string[][] => {
  const normalized = input.replace(/\r\n?/g, '\n').trim();
  if (!normalized) {
    return [];
  }

  const lines = normalized.split('\n').filter((line) => line.length > 0);
  if (lines.length === 0) {
    return [];
  }

  const delimiter = detectTabularDelimiter(lines[0]);
  const rows = lines.map((line) => parseDelimitedLine(line, delimiter));

  const columnCount = rows.reduce((max, row) => Math.max(max, row.length), 1);
  return rows.map((row) => {
    const padded = [...row];
    while (padded.length < columnCount) {
      padded.push('');
    }
    return padded;
  });
};
