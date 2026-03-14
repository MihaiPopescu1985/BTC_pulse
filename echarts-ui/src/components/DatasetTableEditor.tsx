import { useEffect, useMemo, useState } from 'react';
import {
  addDatasetColumn,
  addDatasetRow,
  normalizeDatasetSource,
  removeDatasetColumn,
  removeDatasetRow,
  rowsToDatasetSource,
  type DatasetSource,
  updateDatasetCell,
} from '../utils/dataset';
import { toPrettyJson } from '../utils/json';
import { parseTabularText } from '../utils/tabular';

interface DatasetTableEditorProps {
  source: unknown;
  onSourceChange: (nextSource: DatasetSource) => void;
  editorPath?: string;
}

export const DatasetTableEditor = ({ source, onSourceChange, editorPath }: DatasetTableEditorProps) => {
  const datasetSource = useMemo(() => normalizeDatasetSource(source), [source]);

  const [pasteInput, setPasteInput] = useState('');
  const [advancedJson, setAdvancedJson] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    setAdvancedJson(toPrettyJson(datasetSource));
  }, [datasetSource]);

  const commitSource = (next: DatasetSource) => {
    onSourceChange(normalizeDatasetSource(next));
    setError(null);
  };

  const handleCellEdit = (rowIndex: number, colIndex: number, value: string) => {
    commitSource(updateDatasetCell(datasetSource, rowIndex, colIndex, value));
  };

  const handlePasteTabular = () => {
    const rows = parseTabularText(pasteInput);

    if (rows.length === 0) {
      setError('Paste CSV/TSV text before applying.');
      return;
    }

    commitSource(rowsToDatasetSource(rows));
    setStatus(`Imported ${rows.length} rows.`);
    setPasteInput('');
  };

  const handleCopyJson = async () => {
    const json = toPrettyJson(datasetSource);

    try {
      if (!navigator.clipboard) {
        throw new Error('Clipboard API unavailable.');
      }

      await navigator.clipboard.writeText(json);
      setStatus('Dataset JSON copied to clipboard.');
      setError(null);
    } catch {
      setError('Copy failed. Your browser may block clipboard access.');
    }
  };

  const handleApplyAdvancedJson = () => {
    try {
      const parsed = JSON.parse(advancedJson);
      commitSource(normalizeDatasetSource(parsed));
      setStatus('Advanced JSON applied.');
    } catch {
      setError('Advanced JSON must be a valid 2D array.');
    }
  };

  const columnCount = datasetSource[0]?.length ?? 1;

  return (
    <section className="section-card dataset-editor" data-editor-path={editorPath ?? 'dataset.source'}>
      <h3>Dataset Table Editor</h3>
      <p className="dataset-help">First row is treated as headers. Edit cells directly for quick dataset changes.</p>

      <div className="dataset-toolbar">
        <button type="button" onClick={() => commitSource(addDatasetRow(datasetSource))}>
          Add row
        </button>
        <button type="button" onClick={() => commitSource(addDatasetColumn(datasetSource))}>
          Add column
        </button>
        <button type="button" onClick={() => commitSource(removeDatasetColumn(datasetSource))} disabled={columnCount <= 1}>
          Remove column
        </button>
        <button type="button" onClick={handleCopyJson}>
          Copy dataset as JSON
        </button>
      </div>

      <div className="dataset-table-wrap">
        <table className="dataset-table">
          <thead>
            <tr>
              <th>Row</th>
              {datasetSource[0].map((_, colIndex) => (
                <th key={`col-head-${colIndex}`}>Column {colIndex + 1}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {datasetSource.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`} className={rowIndex === 0 ? 'dataset-header-row' : ''}>
                <td className="dataset-row-action">
                  {rowIndex === 0 ? (
                    <span>Header</span>
                  ) : (
                    <button type="button" onClick={() => commitSource(removeDatasetRow(datasetSource, rowIndex))}>
                      Remove
                    </button>
                  )}
                </td>
                {row.map((cell, colIndex) => (
                  <td key={`cell-${rowIndex}-${colIndex}`}>
                    <input
                      type="text"
                      value={cell === null || cell === undefined ? '' : String(cell)}
                      onChange={(event) => handleCellEdit(rowIndex, colIndex, event.target.value)}
                      className={rowIndex === 0 ? 'dataset-header-input' : ''}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="dataset-paste">
        <label htmlFor="dataset-paste-input">Paste CSV/TSV</label>
        <textarea
          id="dataset-paste-input"
          value={pasteInput}
          onChange={(event) => setPasteInput(event.target.value)}
          placeholder={'category\tvalue\nA\t120\nB\t90'}
        />
        <div className="field-actions">
          <button type="button" onClick={handlePasteTabular}>
            Apply pasted data
          </button>
        </div>
      </div>

      <details className="dataset-advanced">
        <summary>Advanced JSON</summary>
        <textarea
          value={advancedJson}
          onChange={(event) => setAdvancedJson(event.target.value)}
          spellCheck={false}
        />
        <div className="field-actions">
          <button type="button" onClick={handleApplyAdvancedJson}>
            Apply Advanced JSON
          </button>
          <button type="button" onClick={() => setAdvancedJson(toPrettyJson(datasetSource))}>
            Reset to Table
          </button>
        </div>
      </details>

      {status ? <p className="dataset-status">{status}</p> : null}
      {error ? <p className="field-error">{error}</p> : null}
    </section>
  );
};
