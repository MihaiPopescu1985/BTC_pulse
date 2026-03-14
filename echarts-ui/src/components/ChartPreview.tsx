import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import * as echarts from 'echarts';
import type { EditorOption } from '../types/echarts';
import { registerBuiltinMaps } from '../utils/mapRegistry';

interface ChartPreviewProps {
  option: EditorOption;
}

export interface ChartPreviewHandle {
  exportImage: (type: 'png' | 'svg') => string | null;
}

export const ChartPreview = forwardRef<ChartPreviewHandle, ChartPreviewProps>(({ option }, ref) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const latestOptionRef = useRef<EditorOption>(option);

  useEffect(() => {
    latestOptionRef.current = option;
  }, [option]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    registerBuiltinMaps();
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true, lazyUpdate: true });
  }, [option]);

  useImperativeHandle(ref, () => ({
    exportImage: (type: 'png' | 'svg') => {
      const chart = chartRef.current;
      if (!chart) {
        return null;
      }

      if (type === 'png') {
        return chart.getDataURL({
          type: 'png',
          pixelRatio: 2,
          backgroundColor: '#ffffff',
        });
      }

      const width = Math.max(1, chart.getWidth());
      const height = Math.max(1, chart.getHeight());

      const tempContainer = document.createElement('div');
      tempContainer.style.position = 'fixed';
      tempContainer.style.left = '-99999px';
      tempContainer.style.top = '-99999px';
      tempContainer.style.width = `${width}px`;
      tempContainer.style.height = `${height}px`;
      document.body.appendChild(tempContainer);

      try {
        const svgChart = echarts.init(tempContainer, undefined, { renderer: 'svg' });
        svgChart.setOption(latestOptionRef.current, { notMerge: true, lazyUpdate: false });
        const dataUrl = svgChart.getDataURL({
          type: 'svg',
          pixelRatio: 2,
          backgroundColor: '#ffffff',
        });
        svgChart.dispose();
        return dataUrl;
      } catch {
        return null;
      } finally {
        document.body.removeChild(tempContainer);
      }
    },
  }));

  return <div className="chart-container" ref={containerRef} />;
});

ChartPreview.displayName = 'ChartPreview';
