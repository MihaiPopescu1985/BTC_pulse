import type { ChartType } from '../types/echarts';
import type { DatasetInference } from '../utils/inference';
import { getChartTypeLabel } from '../utils/chartTypes';

interface DataSuggestionsCardProps {
  inference: DatasetInference | null;
  onApplySuggestion: (chartType: ChartType) => void;
}

const confidenceLabel = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
} as const;

export const DataSuggestionsCard = ({ inference, onApplySuggestion }: DataSuggestionsCardProps) => {
  if (!inference) {
    return (
      <section className="section-card data-suggestions-card">
        <h3>Data Suggestions</h3>
        <p className="data-suggestions-empty">
          No strong mapping suggestion yet. Add a label/category column and at least one numeric value column.
        </p>
      </section>
    );
  }

  return (
    <section className="section-card data-suggestions-card">
      <h3>Data Suggestions</h3>
      <p className="data-suggestions-summary">
        Detected {inference.valueColumnIndexes.length} value column
        {inference.valueColumnIndexes.length > 1 ? 's' : ''} mapped by {inference.categoryColumnLabel}.
      </p>
      <p className="data-suggestions-meta">Confidence: {confidenceLabel[inference.confidence]}</p>
      <p className="data-suggestions-meta">Label column: {inference.categoryColumnLabel} (#{inference.categoryColumnIndex + 1})</p>
      <p className="data-suggestions-meta">
        Value columns: {inference.valueColumnLabels.length > 0 ? inference.valueColumnLabels.join(', ') : 'None detected'}
      </p>
      {inference.previewLabels.length > 0 ? (
        <p className="data-suggestions-meta">Preview labels: {inference.previewLabels.join(', ')}</p>
      ) : null}
      <p className="data-suggestions-reason">{inference.reason}</p>

      <div className="data-suggestions-actions">
        {inference.suggestedChartTypes.map((chartType) => (
          <button key={`suggest-${chartType}`} type="button" onClick={() => onApplySuggestion(chartType)}>
            Apply as {getChartTypeLabel(chartType)}
          </button>
        ))}
      </div>
    </section>
  );
};
