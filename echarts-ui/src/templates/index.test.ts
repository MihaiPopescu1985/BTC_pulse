import { describe, expect, it } from 'vitest';
import { chartTemplates } from './index';

describe('templates', () => {
  it('includes a scatter starter template with numeric relationship dataset', () => {
    const scatterTemplate = chartTemplates.find((template) => template.chartType === 'scatter');

    expect(scatterTemplate).toBeDefined();
    expect(scatterTemplate?.label).toBe('Relationship between two measures');
    expect(scatterTemplate?.starterDataset).toEqual([
      ['X', 'Y'],
      [12, 20],
      [18, 35],
      [25, 28],
      [32, 42],
    ]);
    expect(scatterTemplate?.starterOption).toMatchObject({
      xAxis: { type: 'value' },
      yAxis: { type: 'value' },
      series: [{ type: 'scatter' }],
    });
  });

  it('includes radar, heatmap, funnel, and gauge starter templates', () => {
    const radarTemplate = chartTemplates.find((template) => template.chartType === 'radar');
    const heatmapTemplate = chartTemplates.find((template) => template.chartType === 'heatmap');
    const funnelTemplate = chartTemplates.find((template) => template.chartType === 'funnel');
    const gaugeTemplate = chartTemplates.find((template) => template.chartType === 'gauge');

    expect(radarTemplate).toBeDefined();
    expect(heatmapTemplate).toBeDefined();
    expect(funnelTemplate).toBeDefined();
    expect(gaugeTemplate).toBeDefined();

    expect(radarTemplate?.starterOption).toMatchObject({
      radar: { indicator: expect.any(Array) },
      series: [{ type: 'radar' }],
    });
    expect(heatmapTemplate?.starterOption).toMatchObject({
      visualMap: { show: true },
      series: [{ type: 'heatmap' }],
    });
    expect(funnelTemplate?.starterOption).toMatchObject({
      tooltip: { trigger: 'item' },
      series: [{ type: 'funnel' }],
    });
    expect(gaugeTemplate?.starterOption).toMatchObject({
      series: [{ type: 'gauge' }],
    });
  });

  it('includes polar, calendar, parallel, geo, and map starter templates', () => {
    const polarTemplate = chartTemplates.find((template) => template.id === 'template-polar-bar');
    const calendarTemplate = chartTemplates.find((template) => template.id === 'template-calendar-heatmap');
    const parallelTemplate = chartTemplates.find((template) => template.id === 'template-parallel-coordinates');
    const geoTemplate = chartTemplates.find((template) => template.id === 'template-geo-scatter');
    const mapTemplate = chartTemplates.find((template) => template.chartType === 'map');

    expect(polarTemplate).toBeDefined();
    expect(calendarTemplate).toBeDefined();
    expect(parallelTemplate).toBeDefined();
    expect(geoTemplate).toBeDefined();
    expect(mapTemplate).toBeDefined();

    expect(polarTemplate?.starterOption).toMatchObject({
      polar: { center: ['50%', '55%'] },
      series: [{ coordinateSystem: 'polar' }],
    });
    expect(calendarTemplate?.starterOption).toMatchObject({
      calendar: { range: '2026' },
      series: [{ coordinateSystem: 'calendar' }],
    });
    expect(parallelTemplate?.starterOption).toMatchObject({
      parallelAxis: expect.any(Array),
      series: [{ type: 'parallel' }],
    });
    expect(geoTemplate?.starterOption).toMatchObject({
      geo: { map: 'world-lite' },
      series: [{ coordinateSystem: 'geo' }],
    });
    expect(mapTemplate?.starterOption).toMatchObject({
      series: [{ type: 'map', map: 'world-lite' }],
    });
  });
});
