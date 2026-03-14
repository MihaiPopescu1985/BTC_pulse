import { describe, expect, it } from 'vitest';
import type { EditorOption } from '../types/echarts';
import { createDefaultSeries, getCurrentChartType, getSeriesType } from './series';

describe('series utils', () => {
  it('supports candlestick as a valid series type', () => {
    expect(getSeriesType({ type: 'candlestick' })).toBe('candlestick');
  });

  it('creates a practical default candlestick series', () => {
    const series = createDefaultSeries('candlestick', 0);

    expect(series).toMatchObject({
      type: 'candlestick',
      encode: { x: 0, y: [1, 2, 3, 4] },
    });
  });

  it('supports scatter as a valid series type', () => {
    expect(getSeriesType({ type: 'scatter' })).toBe('scatter');
  });

  it('creates a practical default scatter series', () => {
    const series = createDefaultSeries('scatter', 1);

    expect(series).toMatchObject({
      type: 'scatter',
      symbolSize: 14,
      encode: { x: 0, y: 1, tooltip: [0, 1] },
    });
  });

  it('supports radar/heatmap/funnel/gauge as valid series types', () => {
    expect(getSeriesType({ type: 'radar' })).toBe('radar');
    expect(getSeriesType({ type: 'heatmap' })).toBe('heatmap');
    expect(getSeriesType({ type: 'funnel' })).toBe('funnel');
    expect(getSeriesType({ type: 'gauge' })).toBe('gauge');
  });

  it('creates practical defaults for radar/heatmap/funnel/gauge', () => {
    expect(createDefaultSeries('radar', 0)).toMatchObject({
      type: 'radar',
      symbolSize: 6,
    });

    expect(createDefaultSeries('heatmap', 0)).toMatchObject({
      type: 'heatmap',
      coordinateSystem: 'cartesian2d',
      encode: { x: 0, y: 1, value: [2] },
    });

    expect(createDefaultSeries('funnel', 0)).toMatchObject({
      type: 'funnel',
      sort: 'descending',
    });

    expect(createDefaultSeries('gauge', 0)).toMatchObject({
      type: 'gauge',
      min: 0,
      max: 100,
    });
  });

  it('supports map as a valid series type and default factory', () => {
    expect(getSeriesType({ type: 'map' })).toBe('map');
    expect(createDefaultSeries('map', 0)).toMatchObject({
      type: 'map',
      map: 'world-lite',
    });
  });

  it('derives chart family for polar/calendar/geo/singleAxis via coordinate system', () => {
    const polarOption = {
      series: [{ type: 'line', coordinateSystem: 'polar' }],
    } as EditorOption;
    const calendarOption = {
      series: [{ type: 'heatmap', coordinateSystem: 'calendar' }],
    } as EditorOption;
    const geoOption = {
      series: [{ type: 'effectScatter', coordinateSystem: 'geo' }],
    } as EditorOption;
    const singleAxisOption = {
      series: [{ type: 'effectScatter', coordinateSystem: 'singleAxis' }],
    } as EditorOption;

    expect(getCurrentChartType(polarOption, 0)).toBe('polar');
    expect(getCurrentChartType(calendarOption, 0)).toBe('calendar');
    expect(getCurrentChartType(geoOption, 0)).toBe('geo');
    expect(getCurrentChartType(singleAxisOption, 0)).toBe('singleAxis');
  });
});
