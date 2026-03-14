import { useEffect, useState } from 'react';
import type { EditorOption } from '../types/echarts';
import { parseJson, toPrettyJson } from '../utils/json';

interface JsonPanelProps {
  option: EditorOption;
  onImport: (nextOption: EditorOption) => void;
}

export const JsonPanel = ({ option, onImport }: JsonPanelProps) => {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setValue(toPrettyJson(option));
  }, [option]);

  const handleImport = () => {
    try {
      const parsed = parseJson<EditorOption>(value);
      onImport(parsed);
      setError(null);
    } catch {
      setError('Invalid JSON input for ECharts option.');
    }
  };

  const handleExport = () => {
    setValue(toPrettyJson(option));
    setError(null);
  };

  return (
    <section className="section-card json-panel">
      <h3>JSON Import / Export</h3>
      <textarea value={value} onChange={(event) => setValue(event.target.value)} spellCheck={false} />
      <div className="field-actions">
        <button type="button" onClick={handleImport}>
          Import JSON
        </button>
        <button type="button" onClick={handleExport}>
          Export JSON
        </button>
        {error ? <span className="field-error">{error}</span> : null}
      </div>
    </section>
  );
};
