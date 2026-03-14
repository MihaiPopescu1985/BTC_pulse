import type { ChartType } from '../types/echarts';
import type { EditorSeries } from '../utils/series';
import { getChartTypeLabel } from '../utils/chartTypes';
import { getSeriesDisplayName } from '../utils/series';

interface SeriesPanelProps {
  series: EditorSeries[];
  selectedIndex: number;
  chartType: ChartType;
  onSelect: (index: number) => void;
  onAddSeries: () => void;
  onRemoveSelected: () => void;
}

export const SeriesPanel = ({
  series,
  selectedIndex,
  chartType,
  onSelect,
  onAddSeries,
  onRemoveSelected,
}: SeriesPanelProps) => {
  return (
    <section className="section-card series-panel" data-editor-path="series">
      <h3>Series</h3>
      <div className="series-toolbar">
        <button type="button" onClick={onAddSeries}>
          Add {getChartTypeLabel(chartType)} series
        </button>
        <button type="button" onClick={onRemoveSelected} disabled={series.length === 0}>
          Remove selected
        </button>
      </div>

      {series.length === 0 ? <p className="series-empty">No series yet. Add one to start editing.</p> : null}

      <div className="series-list">
        {series.map((item, index) => (
          <button
            key={`series-${index}`}
            type="button"
            className={index === selectedIndex ? 'series-item active' : 'series-item'}
            onClick={() => onSelect(index)}
          >
            {getSeriesDisplayName(item, index)}
          </button>
        ))}
      </div>
    </section>
  );
};
