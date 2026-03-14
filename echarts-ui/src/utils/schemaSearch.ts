import type { FieldSchema, SectionSchema } from '../types/editor';

export interface SchemaSearchIndexEntry {
  id: string;
  sectionId: string;
  sectionTitle: string;
  field: FieldSchema;
  searchableText: string;
  displayPath: string;
}

const normalizeSearch = (value: string): string => value.trim().toLowerCase();

const joinSearchParts = (parts: Array<string | undefined>): string => {
  return parts
    .map((part) => (part ?? '').trim())
    .filter((part) => part.length > 0)
    .join(' ')
    .toLowerCase();
};

export const normalizeFieldPathForSearch = (path: string): string => {
  return path.replace(/\.\$[A-Za-z0-9_]+/g, '');
};

export const makeSchemaFieldSearchId = (sectionId: string, fieldKey: string): string => {
  return `${sectionId}::${fieldKey}`;
};

export const buildSchemaSearchIndex = (schema: SectionSchema[]): SchemaSearchIndexEntry[] => {
  return schema.flatMap((section) =>
    section.fields.map((field) => {
      const displayPath = normalizeFieldPathForSearch(field.path);
      return {
        id: makeSchemaFieldSearchId(section.id, field.key),
        sectionId: section.id,
        sectionTitle: section.title,
        field,
        displayPath,
        searchableText: joinSearchParts([
          section.title,
          field.label,
          field.path,
          displayPath,
          field.helpText,
          field.description,
          field.keywords?.join(' '),
        ]),
      };
    }),
  );
};

export const filterSchemaSearchIndex = (
  index: SchemaSearchIndexEntry[],
  query: string,
): SchemaSearchIndexEntry[] => {
  const normalizedQuery = normalizeSearch(query);
  if (!normalizedQuery) {
    return index;
  }

  return index.filter((entry) => entry.searchableText.includes(normalizedQuery));
};

