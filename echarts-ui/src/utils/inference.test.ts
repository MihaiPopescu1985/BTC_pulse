import { describe, expect, it } from 'vitest';
import type { EditorOption } from '../types/echarts';
import { applySuggestionToOption, inferDataset } from './inference';

describe('inference utils', () => {
  it('infers time-like two-column dataset as line-first with pie eligibility', () => {
    const source = [
      ['Month', 'Sales'],
      ['Jan', 120],
      ['Feb', 132],
      ['Mar', 101],
    ];

    const inference = inferDataset(source);

    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('pie-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('line');
    expect(inference?.valueColumnIndexes).toEqual([1]);
  });

  it('applies pie suggestion with pie data and hidden axes', () => {
    const source = [
      ['Category', 'Value'],
      ['A', 23],
      ['B', 45],
    ];
    const inference = inferDataset(source);

    expect(inference).not.toBeNull();

    const next = applySuggestionToOption(
      {
        title: { text: 'Keep me' },
      } as EditorOption,
      {
        chartType: 'pie',
        inference: inference!,
        source,
      },
    ) as Record<string, unknown>;

    const series = next.series as Array<Record<string, unknown>>;
    const xAxis = next.xAxis as Record<string, unknown>;
    const yAxis = next.yAxis as Record<string, unknown>;
    const tooltip = next.tooltip as Record<string, unknown>;

    expect(series[0].type).toBe('pie');
    expect(series[0].data).toEqual([
      { name: 'A', value: 23 },
      { name: 'B', value: 45 },
    ]);
    expect(xAxis.show).toBe(false);
    expect(yAxis.show).toBe(false);
    expect(tooltip.trigger).toBe('item');
  });

  it('applies line suggestion with xAxis categories and one series per numeric column', () => {
    const source = [
      ['Month', 'Product A', 'Product B'],
      ['Jan', 120, 90],
      ['Feb', 132, 101],
      ['Mar', 101, 110],
    ];
    const inference = inferDataset(source);

    expect(inference).not.toBeNull();

    const next = applySuggestionToOption({} as EditorOption, {
      chartType: 'line',
      inference: inference!,
      source,
    }) as Record<string, unknown>;

    const xAxis = next.xAxis as Record<string, unknown>;
    const series = next.series as Array<Record<string, unknown>>;

    expect(xAxis.data).toEqual(['Jan', 'Feb', 'Mar']);
    expect(series).toHaveLength(2);
    expect(series[0].name).toBe('Product A');
    expect(series[1].name).toBe('Product B');
    expect(series[0].type).toBe('line');
  });

  it('detects OHLC dataset and applies candlestick suggestion', () => {
    const source = [
      ['Date', 'Open', 'Close', 'Low', 'High'],
      ['2026-03-01', 120, 132, 115, 135],
      ['2026-03-02', 132, 128, 125, 136],
      ['2026-03-03', 128, 140, 127, 142],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('candlestick-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('candlestick');
    expect(inference?.ohlcColumnIndexes).toEqual([1, 2, 3, 4]);

    const next = applySuggestionToOption({} as EditorOption, {
      chartType: 'candlestick',
      inference: inference!,
      source,
    }) as Record<string, unknown>;

    const series = next.series as Array<Record<string, unknown>>;
    const tooltip = next.tooltip as Record<string, unknown>;
    const xAxis = next.xAxis as Record<string, unknown>;

    expect(series).toHaveLength(1);
    expect(series[0].type).toBe('candlestick');
    expect(series[0].encode).toEqual({ x: 0, y: [1, 2, 3, 4] });
    expect(tooltip.trigger).toBe('axis');
    expect(xAxis.type).toBe('category');
  });

  it('detects two numeric columns and suggests scatter', () => {
    const source = [
      ['X', 'Y'],
      [12, 20],
      [18, 35],
      [25, 28],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('scatter-candidate');
    expect(inference?.suggestedChartTypes).toContain('scatter');
    expect(inference?.scatterXColumnIndex).toBe(0);
    expect(inference?.scatterYColumnIndex).toBe(1);
  });

  it('detects label plus two numeric columns and maps scatter dimensions', () => {
    const source = [
      ['Label', 'X', 'Y'],
      ['A', 12, 20],
      ['B', 18, 35],
      ['C', 25, 28],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('scatter-candidate');
    expect(inference?.scatterXColumnIndex).toBe(1);
    expect(inference?.scatterYColumnIndex).toBe(2);
    expect(inference?.scatterLabelColumnIndex).toBe(0);

    const next = applySuggestionToOption({} as EditorOption, {
      chartType: 'scatter',
      inference: inference!,
      source,
    }) as Record<string, unknown>;

    const series = next.series as Array<Record<string, unknown>>;
    const xAxis = next.xAxis as Record<string, unknown>;
    const yAxis = next.yAxis as Record<string, unknown>;

    expect(series[0].type).toBe('scatter');
    expect(series[0].encode).toEqual({
      x: 1,
      y: 2,
      tooltip: [0, 1, 2],
      itemName: 0,
    });
    expect(xAxis.type).toBe('value');
    expect(yAxis.type).toBe('value');
  });

  it('detects radar candidate from label plus multiple numeric columns', () => {
    const source = [
      ['Team', 'Quality', 'Speed', 'Reliability'],
      ['Alpha', 82, 90, 76],
      ['Beta', 74, 86, 80],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('radar-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('radar');

    const next = applySuggestionToOption({} as EditorOption, {
      chartType: 'radar',
      inference: inference!,
      source,
    }) as Record<string, unknown>;

    const series = next.series as Array<Record<string, unknown>>;
    const radar = next.radar as Record<string, unknown>;
    expect(series[0].type).toBe('radar');
    expect(Array.isArray((series[0] as Record<string, unknown>).data)).toBe(true);
    expect(Array.isArray(radar.indicator)).toBe(true);
  });

  it('detects heatmap candidate from x/y/value triplets', () => {
    const source = [
      ['X', 'Y', 'Value'],
      ['Mon', 'AM', 12],
      ['Mon', 'PM', 20],
      ['Tue', 'AM', 18],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('heatmap-candidate');
    expect(inference?.suggestedChartTypes).toContain('heatmap');

    const next = applySuggestionToOption({} as EditorOption, {
      chartType: 'heatmap',
      inference: inference!,
      source,
    }) as Record<string, unknown>;

    const series = next.series as Array<Record<string, unknown>>;
    const xAxis = next.xAxis as Record<string, unknown>;
    const yAxis = next.yAxis as Record<string, unknown>;

    expect(series[0].type).toBe('heatmap');
    expect(xAxis.type).toBe('category');
    expect(yAxis.type).toBe('category');
  });

  it('detects funnel candidate from stage/value data', () => {
    const source = [
      ['Stage', 'Value'],
      ['Visit', 1000],
      ['Signup', 650],
      ['Purchase', 240],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('funnel-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('funnel');

    const next = applySuggestionToOption({} as EditorOption, {
      chartType: 'funnel',
      inference: inference!,
      source,
    }) as Record<string, unknown>;

    const series = next.series as Array<Record<string, unknown>>;
    const tooltip = next.tooltip as Record<string, unknown>;
    expect(series[0].type).toBe('funnel');
    expect(tooltip.trigger).toBe('item');
  });

  it('detects gauge candidate from a single KPI row', () => {
    const source = [
      ['Metric', 'Value'],
      ['Completion', 72],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('gauge-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('gauge');

    const next = applySuggestionToOption({} as EditorOption, {
      chartType: 'gauge',
      inference: inference!,
      source,
    }) as Record<string, unknown>;

    const series = next.series as Array<Record<string, unknown>>;
    expect(series[0].type).toBe('gauge');
    expect((series[0].data as Array<Record<string, unknown>>)[0].value).toBe(72);
  });

  it('detects parallel candidate from multi-dimensional numeric data', () => {
    const source = [
      ['Item', 'A', 'B', 'C'],
      ['One', 12, 30, 18],
      ['Two', 15, 28, 22],
      ['Three', 19, 34, 25],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('parallel-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('parallel');
  });

  it('detects calendar candidate from date + value data', () => {
    const source = [
      ['Date', 'Value'],
      ['2026-03-01', 12],
      ['2026-03-02', 20],
      ['2026-03-03', 15],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('calendar-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('calendar');
  });

  it('detects geo candidate from lng/lat/value columns', () => {
    const source = [
      ['Lng', 'Lat', 'Value'],
      [13.405, 52.52, 40],
      [-0.1276, 51.5072, 32],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('geo-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('geo');
  });

  it('detects map candidate from name + value geographic table', () => {
    const source = [
      ['Country', 'Value'],
      ['World', 72],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('map-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('map');
  });

  it('detects polar candidate from category + value non-time data', () => {
    const source = [
      ['Category', 'Value'],
      ['Q1', 2.4],
      ['Q2', 3.1],
      ['Q3', 2.7],
    ];

    const inference = inferDataset(source);
    expect(inference).not.toBeNull();
    expect(inference?.kind).toBe('polar-candidate');
    expect(inference?.suggestedChartTypes[0]).toBe('polar');
  });
});
