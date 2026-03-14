import { useMemo, useState } from 'react';
import { editorSchema } from '../schema/editorSchema';
import type { ArrayBindingState, EditorContext, EditorMode, FieldSchema } from '../types/editor';
import type { EditorOption } from '../types/echarts';
import { getByPath } from '../utils/path';
import {
  buildSchemaSearchIndex,
  filterSchemaSearchIndex,
  makeSchemaFieldSearchId,
} from '../utils/schemaSearch';
import { SchemaField } from './SchemaField';

interface PropertyEditorProps {
  option: EditorOption;
  context: EditorContext;
  manualTestMode?: boolean;
  onValueChange: (path: string, value: unknown) => void;
  onResetToDefault: (path: string, defaultValue: unknown) => void;
  arrayBindingStates?: Record<string, ArrayBindingState>;
}

const complexityRank: Record<EditorMode, number> = {
  basic: 0,
  advanced: 1,
  expert: 2,
};

const schemaSearchIndex = buildSchemaSearchIndex(editorSchema);
const displayPathById = new Map(schemaSearchIndex.map((entry) => [entry.id, entry.displayPath]));

const resolvePath = (path: string, context: EditorContext): string => {
  return path
    .replace(/\$seriesIndex/g, String(context.selectedSeriesIndex))
    .replace(/\$dataZoomIndex/g, String(context.selectedDataZoomIndex))
    .replace(/\$xAxisIndex/g, String(context.selectedXAxisIndex))
    .replace(/\$yAxisIndex/g, String(context.selectedYAxisIndex))
    .replace(/\$gridIndex/g, String(context.selectedGridIndex))
    .replace(/\$visualMapIndex/g, String(context.selectedVisualMapIndex))
    .replace(/\$titleIndex/g, String(context.selectedTitleIndex))
    .replace(/\$datasetIndex/g, String(context.selectedDatasetIndex))
    .replace(/\$radarIndex/g, String(context.selectedRadarIndex))
    .replace(/\$polarIndex/g, String(context.selectedPolarIndex))
    .replace(/\$singleAxisIndex/g, String(context.selectedSingleAxisIndex))
    .replace(/\$parallelIndex/g, String(context.selectedParallelIndex))
    .replace(/\$parallelAxisIndex/g, String(context.selectedParallelAxisIndex))
    .replace(/\$calendarIndex/g, String(context.selectedCalendarIndex))
    .replace(/\$geoIndex/g, String(context.selectedGeoIndex))
    .replace(/\$angleAxisIndex/g, String(context.selectedAngleAxisIndex))
    .replace(/\$radiusAxisIndex/g, String(context.selectedRadiusAxisIndex));
};

interface FieldBlock {
  group?: string;
  fields: FieldSchema[];
}

const toFieldBlocks = (fields: FieldSchema[]): FieldBlock[] => {
  const blocks: FieldBlock[] = [];

  fields.forEach((field) => {
    const last = blocks[blocks.length - 1];

    if (field.group && last && last.group === field.group) {
      last.fields.push(field);
      return;
    }

    blocks.push({ group: field.group, fields: [field] });
  });

  return blocks;
};

const isModeVisible = (field: FieldSchema, mode: EditorMode): boolean => {
  const level = field.complexity ?? 'basic';
  return complexityRank[level] <= complexityRank[mode];
};

export const PropertyEditor = ({
  option,
  context,
  manualTestMode = false,
  onValueChange,
  onResetToDefault,
  arrayBindingStates,
}: PropertyEditorProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editorMode, setEditorMode] = useState<EditorMode>('basic');

  const normalizedQuery = useMemo(() => searchQuery.trim().toLowerCase(), [searchQuery]);
  const filteredSearchEntries = useMemo(
    () => filterSchemaSearchIndex(schemaSearchIndex, normalizedQuery),
    [normalizedQuery],
  );
  const matchingFieldIds = useMemo(() => {
    if (!normalizedQuery) {
      return null;
    }
    return new Set(filteredSearchEntries.map((entry) => entry.id));
  }, [filteredSearchEntries, normalizedQuery]);

  return (
    <div className="property-editor">
      <section className="section-card property-editor-tools">
        <h3>Property Filters</h3>
        <label>
          <span>Global Property Search</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search label, path, keywords, description"
          />
        </label>
        <label>
          <span>Mode</span>
          <select value={editorMode} onChange={(event) => setEditorMode(event.target.value as EditorMode)}>
            <option value="basic">Basic</option>
            <option value="advanced">Advanced</option>
            <option value="expert">Expert</option>
          </select>
        </label>
      </section>

      {editorSchema.map((section) => {
        let visibleFields = section.fields
          .filter((field) => (field.visibleWhen ? field.visibleWhen(context) : true))
          .filter((field) => isModeVisible(field, editorMode));

        if (matchingFieldIds) {
          visibleFields = visibleFields.filter((field) =>
            matchingFieldIds.has(makeSchemaFieldSearchId(section.id, field.key)),
          );
        }

        if (visibleFields.length === 0) {
          return null;
        }

        const fieldBlocks = toFieldBlocks(visibleFields);
        const bindingState = section.arrayBinding ? arrayBindingStates?.[section.arrayBinding.id] : undefined;
        const hasSelectedArrayItem = !section.arrayBinding || !bindingState || bindingState.itemCount > 0;

        return (
          <section className="section-card" key={section.id}>
            <h3>{section.title}</h3>

            {section.arrayBinding && bindingState ? (
              <div className="array-binding-controls">
                <label>
                  <span>{section.arrayBinding.itemLabel}</span>
                  <select
                    value={bindingState.itemCount === 0 ? '' : String(bindingState.selectedIndex)}
                    onChange={(event) => {
                      const next = event.target.value;
                      if (next === '') {
                        return;
                      }
                      bindingState.onSelect(Number(next));
                    }}
                  >
                    {bindingState.itemCount === 0 ? <option value="">No items</option> : null}
                    {Array.from({ length: bindingState.itemCount }).map((_, index) => (
                      <option key={`${section.arrayBinding?.id}-${index}`} value={String(index)}>
                        {section.arrayBinding?.itemLabel} {index + 1}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="array-binding-actions">
                  <button type="button" onClick={bindingState.onAdd}>
                    Add {section.arrayBinding.itemLabel}
                  </button>
                  <button
                    type="button"
                    onClick={bindingState.onRemove}
                    disabled={bindingState.itemCount <= (bindingState.minItems ?? 0)}
                  >
                    Remove Selected
                  </button>
                </div>
              </div>
            ) : null}

            {!hasSelectedArrayItem ? (
              <p className="array-binding-empty">No {section.arrayBinding?.itemLabel.toLowerCase()} selected. Add one to edit.</p>
            ) : (
              <div className="section-fields">
                {fieldBlocks.map((block, blockIndex) => {
                  const content = (
                    <>
                      {block.fields.map((field) => {
                        const resolvedPath = resolvePath(field.path, context);
                        const fieldId = makeSchemaFieldSearchId(section.id, field.key);
                        const displayPath = displayPathById.get(fieldId) ?? field.path;
                        return (
                          <SchemaField
                            key={`${field.key}-${resolvedPath}`}
                            field={field}
                            path={resolvedPath}
                            displayPath={displayPath}
                            searchQuery={normalizedQuery}
                            manualTestMode={manualTestMode}
                            value={getByPath(option, resolvedPath)}
                            onValueChange={onValueChange}
                            onResetToDefault={onResetToDefault}
                          />
                        );
                      })}
                    </>
                  );

                  if (!block.group) {
                    return <div key={`${section.id}-fields-${blockIndex}`}>{content}</div>;
                  }

                  return (
                    <div key={`${section.id}-group-${block.group}-${blockIndex}`} className="field-group">
                      <h4>{block.group}</h4>
                      {content}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
};
