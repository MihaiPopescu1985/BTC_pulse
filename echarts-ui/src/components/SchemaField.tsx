import { useEffect, useMemo, useRef, useState } from 'react';
import type { ComplexValueEditor, FieldSchema } from '../types/editor';
import { toPrettyJson } from '../utils/json';

interface SchemaFieldProps {
  field: FieldSchema;
  path: string;
  displayPath?: string;
  searchQuery?: string;
  manualTestMode?: boolean;
  value: unknown;
  onValueChange: (path: string, value: unknown) => void;
  onResetToDefault: (path: string, defaultValue: unknown) => void;
}

const valueAsString = (value: unknown): string => {
  if (value === undefined || value === null) {
    return '';
  }

  if (typeof value === 'object') {
    return toPrettyJson(value);
  }

  return String(value);
};

const tupleAsDraft = (value: unknown): [string, string] => {
  if (Array.isArray(value)) {
    return [value[0] === undefined ? '' : String(value[0]), value[1] === undefined ? '' : String(value[1])];
  }

  if (value !== undefined && value !== null) {
    return [String(value), ''];
  }

  return ['', ''];
};

const formatArrayDraft = (value: unknown, editor: ComplexValueEditor): string => {
  if (value === undefined || value === null) {
    return '';
  }

  if (editor === 'object-array') {
    return Array.isArray(value) ? toPrettyJson(value) : '[]';
  }

  if (!Array.isArray(value)) {
    return '';
  }

  return value.map((item) => String(item ?? '')).join('\n');
};

const parseArrayDraft = (draft: string, editor: ComplexValueEditor): unknown => {
  if (editor === 'object-array') {
    const parsed = JSON.parse(draft || '[]');
    if (!Array.isArray(parsed) || parsed.some((item) => !item || typeof item !== 'object' || Array.isArray(item))) {
      throw new Error('Expected an array of objects.');
    }

    return parsed;
  }

  const lines = draft
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (editor === 'number-array') {
    return lines.map((line) => {
      const parsed = Number(line);
      if (Number.isNaN(parsed)) {
        throw new Error(`Invalid number: ${line}`);
      }
      return parsed;
    });
  }

  return lines;
};

const toComparisonKey = (value: unknown): string => {
  try {
    const serialized = JSON.stringify(value);
    return serialized ?? String(value);
  } catch {
    return String(value);
  }
};

const toDebugValuePreview = (value: unknown, maxLength = 120): string => {
  let raw = '';

  if (value === undefined) {
    raw = 'undefined';
  } else if (typeof value === 'string') {
    raw = `"${value}"`;
  } else if (typeof value === 'number' || typeof value === 'boolean' || value === null) {
    raw = String(value);
  } else {
    raw = toPrettyJson(value).replace(/\s+/g, ' ').trim();
  }

  if (raw.length <= maxLength) {
    return raw;
  }

  return `${raw.slice(0, maxLength - 1)}…`;
};

const escapeRegExp = (value: string): string => {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
};

const renderHighlightedText = (text: string, query: string): JSX.Element | string => {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    return text;
  }

  const matcher = new RegExp(`(${escapeRegExp(normalizedQuery)})`, 'ig');
  const parts = text.split(matcher);
  if (parts.length <= 1) {
    return text;
  }

  return (
    <>
      {parts.map((part, index) => {
        const key = `${part}-${index}`;
        if (part.toLowerCase() === normalizedQuery.toLowerCase()) {
          return (
            <mark key={key} className="field-highlight">
              {part}
            </mark>
          );
        }
        return <span key={key}>{part}</span>;
      })}
    </>
  );
};

export const SchemaField = ({
  field,
  path,
  displayPath,
  searchQuery = '',
  manualTestMode = false,
  value,
  onValueChange,
  onResetToDefault,
}: SchemaFieldProps) => {
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [didChangeFlash, setDidChangeFlash] = useState(false);

  const isJsonTextarea = field.control === 'textarea' && field.textareaMode === 'json';
  const isArrayEditor =
    field.valueEditor === 'string-array' ||
    field.valueEditor === 'number-array' ||
    field.valueEditor === 'color-array' ||
    field.valueEditor === 'object-array';
  const isTupleEditor = field.valueEditor === 'tuple';

  const inputId = `${field.key}-${path.replace(/\./g, '-')}`;
  const hasDefault = field.defaultValue !== undefined;
  const showSearchHints = searchQuery.trim().length > 0;
  const fieldPathLabel = displayPath ?? path;
  const isCheckboxField = !isTupleEditor && !isArrayEditor && field.control === 'checkbox';
  const comparisonKey = useMemo(() => toComparisonKey(value), [value]);
  const debugValuePreview = useMemo(() => toDebugValuePreview(value), [value]);
  const lastValueRef = useRef(comparisonKey);
  const didMountRef = useRef(false);
  const timerRef = useRef<number | null>(null);

  const externalText = useMemo(() => valueAsString(value), [value]);
  const tupleDraft = useMemo(() => tupleAsDraft(value), [value]);

  useEffect(() => {
    if (isJsonTextarea) {
      setDraft(externalText);
      setError(null);
    }
  }, [externalText, isJsonTextarea]);

  useEffect(() => {
    if (isArrayEditor && field.valueEditor) {
      setDraft(formatArrayDraft(value, field.valueEditor));
      setError(null);
    }
  }, [field.valueEditor, isArrayEditor, value]);

  useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      lastValueRef.current = comparisonKey;
      return;
    }

    if (lastValueRef.current !== comparisonKey) {
      setDidChangeFlash(true);
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
      timerRef.current = window.setTimeout(() => {
        setDidChangeFlash(false);
        timerRef.current = null;
      }, 700);
      lastValueRef.current = comparisonKey;
    }
  }, [comparisonKey]);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, []);

  const commitJson = () => {
    try {
      const parsed = JSON.parse(draft);
      onValueChange(path, parsed);
      setError(null);
    } catch {
      setError('Invalid JSON');
    }
  };

  const commitArrayDraft = () => {
    if (!field.valueEditor) {
      return;
    }

    try {
      const parsed = parseArrayDraft(draft, field.valueEditor);
      onValueChange(path, parsed);
      setError(null);
    } catch (commitError) {
      const message = commitError instanceof Error ? commitError.message : 'Invalid value list';
      setError(message);
    }
  };

  const resetButton = hasDefault ? (
    <button
      type="button"
      className="field-reset"
      onClick={() => onResetToDefault(path, field.defaultValue)}
    >
      Reset
    </button>
  ) : null;

  const fieldMeta = (
    <>
      {showSearchHints ? <p className="field-path">{renderHighlightedText(fieldPathLabel, searchQuery)}</p> : null}
      {field.description ? <p className="field-description">{renderHighlightedText(field.description, searchQuery)}</p> : null}
      {field.helpText ? <p className="field-help">{field.helpText}</p> : null}
    </>
  );

  return (
    <div
      className={`field ${isCheckboxField ? 'field-checkbox' : ''} ${didChangeFlash ? 'field-changed' : ''}`}
      data-editor-path={path}
    >
      {isCheckboxField ? (
        <div className="field-checkbox-main">
          <div className="field-checkbox-text">
            <div className="field-header">
              <label className="field-label" htmlFor={inputId}>
                {renderHighlightedText(field.label, searchQuery)}
              </label>
              {resetButton}
            </div>
            {fieldMeta}
          </div>
          <div className="field-checkbox-control">
            <input
              id={inputId}
              type="checkbox"
              checked={Boolean(value)}
              onChange={(event) => onValueChange(path, event.target.checked)}
            />
          </div>
        </div>
      ) : (
        <>
          <div className="field-header">
            <label className="field-label" htmlFor={inputId}>
              {renderHighlightedText(field.label, searchQuery)}
            </label>
            {resetButton}
          </div>

          {fieldMeta}
        </>
      )}

      {isTupleEditor ? (
        <div className="tuple-editor">
          <label>
            <span>{field.tupleLabels?.[0] ?? 'First'}</span>
            <input
              id={`${inputId}-0`}
              type="text"
              value={tupleDraft[0]}
              placeholder={field.placeholder}
              onChange={(event) => onValueChange(path, [event.target.value, tupleDraft[1]])}
            />
          </label>
          <label>
            <span>{field.tupleLabels?.[1] ?? 'Second'}</span>
            <input
              id={`${inputId}-1`}
              type="text"
              value={tupleDraft[1]}
              placeholder={field.placeholder}
              onChange={(event) => onValueChange(path, [tupleDraft[0], event.target.value])}
            />
          </label>
        </div>
      ) : null}

      {isArrayEditor ? (
        <>
          <textarea
            id={inputId}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commitArrayDraft}
            placeholder={
              field.placeholder ??
              (field.valueEditor === 'number-array'
                ? 'One number per line'
                : field.valueEditor === 'object-array'
                  ? '[{"name":"A","value":10}]'
                  : 'One value per line')
            }
          />
          <div className="field-actions">
            <button type="button" onClick={commitArrayDraft}>
              Apply Values
            </button>
            {error ? <span className="field-error">{error}</span> : null}
          </div>
        </>
      ) : null}

      {!isTupleEditor && !isArrayEditor && field.control === 'select' ? (
        <select
          id={inputId}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onValueChange(path, event.target.value)}
        >
          <option value="">Select…</option>
          {field.options?.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : null}

      {!isTupleEditor && !isArrayEditor && field.control === 'number' ? (
        <input
          id={inputId}
          type="number"
          value={typeof value === 'number' ? value : ''}
          placeholder={field.placeholder}
          onChange={(event) => {
            const next = event.target.value;
            if (next.trim() === '') {
              onValueChange(path, undefined);
              return;
            }

            const parsed = Number(next);
            if (!Number.isNaN(parsed)) {
              onValueChange(path, parsed);
            }
          }}
        />
      ) : null}

      {!isTupleEditor && !isArrayEditor && field.control === 'textarea' && !isJsonTextarea ? (
        <textarea
          id={inputId}
          value={valueAsString(value)}
          onChange={(event) => onValueChange(path, event.target.value)}
          placeholder={field.placeholder}
        />
      ) : null}

      {!isTupleEditor && !isArrayEditor && field.control === 'textarea' && isJsonTextarea ? (
        <>
          <textarea
            id={inputId}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commitJson}
            placeholder={field.placeholder}
          />
          <div className="field-actions">
            <button type="button" onClick={commitJson}>
              Apply JSON
            </button>
            {error ? <span className="field-error">{error}</span> : null}
          </div>
        </>
      ) : null}

      {!isTupleEditor && !isArrayEditor && field.control === 'text' ? (
        <input
          id={inputId}
          type="text"
          value={valueAsString(value)}
          placeholder={field.placeholder}
          onChange={(event) => onValueChange(path, event.target.value)}
        />
      ) : null}

      {manualTestMode ? (
        <div className="field-debug-row">
          <code className="field-debug-path">Path: {fieldPathLabel}</code>
          <code className="field-debug-value">Value: {debugValuePreview}</code>
        </div>
      ) : null}
    </div>
  );
};
