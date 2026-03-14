import type { DatasetSource } from '../utils/dataset';
import type { ChartType, EditorOption } from '../types/echarts';

export type TemplateGoal =
  | 'trend-over-time'
  | 'category-comparison'
  | 'part-to-whole'
  | 'two-series-comparison'
  | 'relationship-between-two-measures'
  | 'multi-metric-comparison'
  | 'matrix-intensity'
  | 'staged-conversion'
  | 'kpi-score'
  | 'cyclical-comparison'
  | 'calendar-activity'
  | 'multi-dimensional-analysis'
  | 'geo-distribution';

export interface ChartTemplate {
  id: string;
  label: string;
  goal: TemplateGoal;
  description: string;
  chartType: ChartType;
  starterOption: EditorOption;
  starterDataset: DatasetSource;
  selectedSeriesIndex: number;
}

export interface TemplateGoalOption {
  id: TemplateGoal;
  label: string;
  description: string;
  chartTypes: ChartType[];
  defaultChartType: ChartType;
}

const cloneOption = (option: EditorOption): EditorOption => JSON.parse(JSON.stringify(option));
const cloneDataset = (dataset: DatasetSource): DatasetSource => JSON.parse(JSON.stringify(dataset));

const trendDataset: DatasetSource = [
  ['Date', 'Sales'],
  ['Jan', 120],
  ['Feb', 132],
  ['Mar', 101],
  ['Apr', 134],
];

const categoryDataset: DatasetSource = [
  ['Category', 'Value'],
  ['A', 23],
  ['B', 45],
  ['C', 31],
];

const partToWholeDataset: DatasetSource = [
  ['Category', 'Value'],
  ['Product A', 335],
  ['Product B', 310],
  ['Product C', 234],
  ['Product D', 135],
  ['Product E', 1548],
];

const twoSeriesDataset: DatasetSource = [
  ['Month', 'Product A', 'Product B'],
  ['Jan', 120, 90],
  ['Feb', 132, 101],
  ['Mar', 101, 110],
];

const candlestickDataset: DatasetSource = [
  ['Date', 'Open', 'Close', 'Low', 'High'],
  ['2026-03-01', 120, 132, 115, 135],
  ['2026-03-02', 132, 128, 125, 136],
  ['2026-03-03', 128, 140, 127, 142],
];

const scatterDataset: DatasetSource = [
  ['X', 'Y'],
  [12, 20],
  [18, 35],
  [25, 28],
  [32, 42],
];

const radarDataset: DatasetSource = [
  ['Team', 'Quality', 'Speed', 'Reliability', 'Coverage'],
  ['Alpha', 82, 90, 76, 88],
  ['Beta', 74, 86, 80, 79],
  ['Gamma', 91, 72, 84, 93],
];

const heatmapDataset: DatasetSource = [
  ['X', 'Y', 'Value'],
  ['Mon', 'Morning', 12],
  ['Mon', 'Afternoon', 20],
  ['Tue', 'Morning', 18],
  ['Tue', 'Afternoon', 26],
  ['Wed', 'Morning', 15],
  ['Wed', 'Afternoon', 22],
];

const funnelDataset: DatasetSource = [
  ['Stage', 'Value'],
  ['Visit', 1000],
  ['Signup', 650],
  ['Qualified', 420],
  ['Purchase', 240],
];

const gaugeDataset: DatasetSource = [
  ['Metric', 'Value'],
  ['Completion', 72],
];

const polarDataset: DatasetSource = [
  ['Category', 'Value'],
  ['Q1', 2.4],
  ['Q2', 3.1],
  ['Q3', 2.7],
  ['Q4', 3.6],
  ['Q5', 2.2],
];

const calendarDataset: DatasetSource = [
  ['Date', 'Value'],
  ['2026-03-01', 12],
  ['2026-03-02', 20],
  ['2026-03-03', 15],
  ['2026-03-04', 28],
  ['2026-03-05', 18],
  ['2026-03-06', 23],
];

const parallelDataset: DatasetSource = [
  ['Item', 'Revenue', 'Cost', 'Growth', 'Satisfaction'],
  ['A', 120, 80, 15, 70],
  ['B', 140, 95, 12, 75],
  ['C', 160, 110, 18, 82],
  ['D', 130, 90, 10, 68],
];

const geoDataset: DatasetSource = [
  ['Name', 'Lng', 'Lat', 'Value'],
  ['Berlin', 13.405, 52.52, 40],
  ['London', -0.1276, 51.5072, 32],
  ['Paris', 2.3522, 48.8566, 28],
  ['Rome', 12.4964, 41.9028, 22],
];

const mapDataset: DatasetSource = [
  ['Region', 'Value'],
  ['World', 72],
];

export const templateGoals: TemplateGoalOption[] = [
  {
    id: 'trend-over-time',
    label: 'Trend over time',
    description: 'Track changes over a sequence (months, dates, periods).',
    chartTypes: ['line', 'bar', 'candlestick'],
    defaultChartType: 'line',
  },
  {
    id: 'category-comparison',
    label: 'Category comparison',
    description: 'Compare values across categories.',
    chartTypes: ['bar', 'line'],
    defaultChartType: 'bar',
  },
  {
    id: 'part-to-whole',
    label: 'Part-to-whole',
    description: 'Show composition of a total.',
    chartTypes: ['pie'],
    defaultChartType: 'pie',
  },
  {
    id: 'two-series-comparison',
    label: 'Two-series comparison',
    description: 'Compare two products/metrics over the same timeline.',
    chartTypes: ['line', 'bar'],
    defaultChartType: 'line',
  },
  {
    id: 'relationship-between-two-measures',
    label: 'Relationship between two measures',
    description: 'Explore numeric x/y relationships with a scatter plot.',
    chartTypes: ['scatter', 'effectScatter'],
    defaultChartType: 'scatter',
  },
  {
    id: 'multi-metric-comparison',
    label: 'Multi-metric comparison',
    description: 'Compare several metrics across the same entities.',
    chartTypes: ['radar', 'parallel'],
    defaultChartType: 'radar',
  },
  {
    id: 'matrix-intensity',
    label: 'Matrix intensity',
    description: 'Show value intensity across two categorical dimensions.',
    chartTypes: ['heatmap', 'calendar'],
    defaultChartType: 'heatmap',
  },
  {
    id: 'staged-conversion',
    label: 'Staged conversion',
    description: 'Visualize drop-off across a conversion funnel.',
    chartTypes: ['funnel'],
    defaultChartType: 'funnel',
  },
  {
    id: 'kpi-score',
    label: 'KPI / score',
    description: 'Display a single KPI value against a target range.',
    chartTypes: ['gauge'],
    defaultChartType: 'gauge',
  },
  {
    id: 'cyclical-comparison',
    label: 'Cyclical comparison',
    description: 'Compare category values in a circular/polar layout.',
    chartTypes: ['polar'],
    defaultChartType: 'polar',
  },
  {
    id: 'calendar-activity',
    label: 'Calendar activity',
    description: 'Track daily intensity over a calendar timeline.',
    chartTypes: ['calendar'],
    defaultChartType: 'calendar',
  },
  {
    id: 'multi-dimensional-analysis',
    label: 'Multi-dimensional analysis',
    description: 'Compare many numeric dimensions at once.',
    chartTypes: ['parallel'],
    defaultChartType: 'parallel',
  },
  {
    id: 'geo-distribution',
    label: 'Geo distribution',
    description: 'Plot geographic points using latitude/longitude.',
    chartTypes: ['geo', 'scatter', 'effectScatter', 'map'],
    defaultChartType: 'geo',
  },
];

const buildTrendTemplate = (chartType: 'line' | 'bar'): ChartTemplate => {
  const isBar = chartType === 'bar';

  return {
    id: `template-trend-over-time-${chartType}`,
    label: 'Trend over time',
    goal: 'trend-over-time',
    description: 'Starter for tracking one metric over time.',
    chartType,
    starterDataset: cloneDataset(trendDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Trend over time' },
      tooltip: { show: true, trigger: 'axis' },
      legend: { show: true },
      xAxis: { show: true, type: 'category', data: ['Jan', 'Feb', 'Mar', 'Apr'] },
      yAxis: { show: true, type: 'value' },
      series: [
        {
          name: 'Sales',
          type: chartType,
          smooth: isBar ? undefined : true,
          data: [120, 132, 101, 134],
        },
      ],
    },
  };
};

const buildCategoryTemplate = (chartType: 'line' | 'bar'): ChartTemplate => {
  return {
    id: `template-category-comparison-${chartType}`,
    label: 'Category comparison',
    goal: 'category-comparison',
    description: 'Starter for comparing values between categories.',
    chartType,
    starterDataset: cloneDataset(categoryDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Category comparison' },
      tooltip: { show: true, trigger: 'axis' },
      legend: { show: true },
      xAxis: { show: true, type: 'category', data: ['A', 'B', 'C'] },
      yAxis: { show: true, type: 'value' },
      series: [
        {
          name: 'Value',
          type: chartType,
          smooth: chartType === 'line' ? true : undefined,
          data: [23, 45, 31],
        },
      ],
    },
  };
};

const buildPartToWholeTemplate = (): ChartTemplate => {
  return {
    id: 'template-part-to-whole-pie',
    label: 'Part-to-whole',
    goal: 'part-to-whole',
    description: 'Starter pie chart for composition of totals.',
    chartType: 'pie',
    starterDataset: cloneDataset(partToWholeDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Part-to-whole breakdown' },
      tooltip: { show: true, trigger: 'item' },
      legend: { show: true, orient: 'vertical', left: 'left' },
      xAxis: { show: false, type: 'category', data: [] },
      yAxis: { show: false, type: 'value' },
      series: [
        {
          name: 'Share',
          type: 'pie',
          radius: '55%',
          data: [
            { value: 335, name: 'Product A' },
            { value: 310, name: 'Product B' },
            { value: 234, name: 'Product C' },
            { value: 135, name: 'Product D' },
            { value: 1548, name: 'Product E' },
          ],
        },
      ],
    },
  };
};

const buildTwoSeriesTemplate = (chartType: 'line' | 'bar'): ChartTemplate => {
  const isLine = chartType === 'line';

  return {
    id: `template-two-series-comparison-${chartType}`,
    label: 'Two-series comparison',
    goal: 'two-series-comparison',
    description: 'Starter comparing Product A and Product B across months.',
    chartType,
    starterDataset: cloneDataset(twoSeriesDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Two-series comparison' },
      tooltip: { show: true, trigger: 'axis' },
      legend: { show: true },
      xAxis: { show: true, type: 'category', data: ['Jan', 'Feb', 'Mar'] },
      yAxis: { show: true, type: 'value' },
      series: [
        {
          name: 'Product A',
          type: chartType,
          smooth: isLine ? true : undefined,
          data: [120, 132, 101],
        },
        {
          name: 'Product B',
          type: chartType,
          smooth: isLine ? true : undefined,
          data: [90, 101, 110],
        },
      ],
    },
  };
};

const buildCandlestickTemplate = (): ChartTemplate => {
  return {
    id: 'template-price-over-time-candlestick',
    label: 'Price over time (candlestick)',
    goal: 'trend-over-time',
    description: 'Starter OHLC candlestick chart (Open, Close, Low, High).',
    chartType: 'candlestick',
    starterDataset: cloneDataset(candlestickDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Price over time' },
      tooltip: { show: true, trigger: 'axis' },
      legend: { show: true },
      xAxis: { show: true, type: 'category' },
      yAxis: { show: true, type: 'value' },
      dataZoom: [{ type: 'inside', start: 0, end: 100 }],
      series: [
        {
          name: 'Price',
          type: 'candlestick',
          encode: {
            x: 0,
            y: [1, 2, 3, 4],
          },
          itemStyle: {
            color: '#26a69a',
            color0: '#ef5350',
            borderColor: '#26a69a',
            borderColor0: '#ef5350',
          },
        },
      ],
    },
  };
};

const buildScatterTemplate = (): ChartTemplate => {
  return {
    id: 'template-relationship-two-measures-scatter',
    label: 'Relationship between two measures',
    goal: 'relationship-between-two-measures',
    description: 'Starter scatter chart for numeric X/Y relationships.',
    chartType: 'scatter',
    starterDataset: cloneDataset(scatterDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Relationship between two measures' },
      tooltip: { show: true, trigger: 'item' },
      legend: { show: true },
      xAxis: { show: true, type: 'value' },
      yAxis: { show: true, type: 'value' },
      series: [
        {
          name: 'Points',
          type: 'scatter',
          symbol: 'circle',
          symbolSize: 14,
          encode: {
            x: 0,
            y: 1,
            tooltip: [0, 1],
          },
          itemStyle: {
            color: '#3b82f6',
            opacity: 0.85,
          },
        },
      ],
    },
  };
};

const buildEffectScatterTemplate = (): ChartTemplate => {
  return {
    id: 'template-relationship-two-measures-effect-scatter',
    label: 'Relationship (effect scatter)',
    goal: 'relationship-between-two-measures',
    description: 'Scatter with ripple highlights for emphasis.',
    chartType: 'effectScatter',
    starterDataset: cloneDataset(scatterDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Relationship between two measures' },
      tooltip: { show: true, trigger: 'item' },
      legend: { show: true },
      xAxis: { show: true, type: 'value' },
      yAxis: { show: true, type: 'value' },
      series: [
        {
          name: 'Points',
          type: 'effectScatter',
          coordinateSystem: 'cartesian2d',
          symbol: 'circle',
          symbolSize: 14,
          rippleEffect: { scale: 2.5, brushType: 'stroke' },
          encode: {
            x: 0,
            y: 1,
            tooltip: [0, 1],
          },
          itemStyle: {
            color: '#16a34a',
            opacity: 0.9,
          },
        },
      ],
    },
  };
};

const buildRadarTemplate = (): ChartTemplate => {
  return {
    id: 'template-multi-metric-radar',
    label: 'Multi-metric comparison',
    goal: 'multi-metric-comparison',
    description: 'Starter radar chart for comparing multiple metrics per entity.',
    chartType: 'radar',
    starterDataset: cloneDataset(radarDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Multi-metric comparison' },
      tooltip: { show: true, trigger: 'item' },
      legend: { show: true },
      radar: {
        shape: 'polygon',
        center: ['50%', '55%'],
        radius: '65%',
        indicator: [
          { name: 'Quality', max: 100 },
          { name: 'Speed', max: 100 },
          { name: 'Reliability', max: 100 },
          { name: 'Coverage', max: 100 },
        ],
      },
      series: [
        {
          name: 'Team performance',
          type: 'radar',
          data: [
            { name: 'Alpha', value: [82, 90, 76, 88] },
            { name: 'Beta', value: [74, 86, 80, 79] },
            { name: 'Gamma', value: [91, 72, 84, 93] },
          ],
          symbol: 'circle',
          symbolSize: 6,
          areaStyle: { opacity: 0.18 },
        },
      ],
    },
  };
};

const buildHeatmapTemplate = (): ChartTemplate => {
  return {
    id: 'template-matrix-intensity-heatmap',
    label: 'Matrix/category intensity',
    goal: 'matrix-intensity',
    description: 'Starter heatmap for category-vs-category intensity data.',
    chartType: 'heatmap',
    starterDataset: cloneDataset(heatmapDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Matrix intensity' },
      tooltip: { show: true, trigger: 'item' },
      legend: { show: false },
      grid: { left: '12%', right: '10%', top: '16%', bottom: '12%', containLabel: true },
      xAxis: {
        show: true,
        type: 'category',
        data: ['Mon', 'Tue', 'Wed'],
      },
      yAxis: {
        show: true,
        type: 'category',
        data: ['Morning', 'Afternoon'],
      },
      visualMap: {
        show: true,
        min: 0,
        max: 30,
        left: 'right',
        top: 'middle',
      },
      series: [
        {
          name: 'Intensity',
          type: 'heatmap',
          coordinateSystem: 'cartesian2d',
          encode: {
            x: 0,
            y: 1,
            value: [2],
            tooltip: [0, 1, 2],
          },
          data: [
            ['Mon', 'Morning', 12],
            ['Mon', 'Afternoon', 20],
            ['Tue', 'Morning', 18],
            ['Tue', 'Afternoon', 26],
            ['Wed', 'Morning', 15],
            ['Wed', 'Afternoon', 22],
          ],
          itemStyle: {
            borderColor: '#ffffff',
            borderWidth: 1,
          },
          label: {
            show: false,
          },
        },
      ],
    },
  };
};

const buildCalendarHeatmapTemplate = (): ChartTemplate => {
  return {
    id: 'template-calendar-heatmap',
    label: 'Calendar heatmap',
    goal: 'calendar-activity',
    description: 'Starter calendar heatmap with date-value pairs.',
    chartType: 'calendar',
    starterDataset: cloneDataset(calendarDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Calendar activity' },
      tooltip: { show: true, trigger: 'item' },
      visualMap: {
        min: 0,
        max: 30,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 20,
      },
      calendar: {
        range: '2026',
        orient: 'horizontal',
        cellSize: ['auto', 18],
        left: 'center',
        top: 60,
      },
      series: [
        {
          name: 'Daily value',
          type: 'heatmap',
          coordinateSystem: 'calendar',
          data: [
            ['2026-03-01', 12],
            ['2026-03-02', 20],
            ['2026-03-03', 15],
            ['2026-03-04', 28],
            ['2026-03-05', 18],
            ['2026-03-06', 23],
          ],
        },
      ],
    },
  };
};

const buildFunnelTemplate = (): ChartTemplate => {
  return {
    id: 'template-staged-conversion-funnel',
    label: 'Staged conversion',
    goal: 'staged-conversion',
    description: 'Starter funnel for conversion-stage analysis.',
    chartType: 'funnel',
    starterDataset: cloneDataset(funnelDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Staged conversion' },
      tooltip: { show: true, trigger: 'item' },
      legend: { show: true },
      series: [
        {
          name: 'Conversion',
          type: 'funnel',
          sort: 'descending',
          min: 0,
          max: 1000,
          minSize: '0%',
          maxSize: '100%',
          gap: 2,
          label: {
            show: true,
            position: 'inside',
            formatter: '{b}: {c}',
          },
          labelLine: {
            show: true,
            length: 12,
          },
          data: [
            { name: 'Visit', value: 1000 },
            { name: 'Signup', value: 650 },
            { name: 'Qualified', value: 420 },
            { name: 'Purchase', value: 240 },
          ],
        },
      ],
    },
  };
};

const buildGaugeTemplate = (): ChartTemplate => {
  return {
    id: 'template-kpi-score-gauge',
    label: 'KPI / progress gauge',
    goal: 'kpi-score',
    description: 'Starter gauge chart for a single KPI or score value.',
    chartType: 'gauge',
    starterDataset: cloneDataset(gaugeDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'KPI score' },
      tooltip: { show: true, trigger: 'item' },
      legend: { show: false },
      series: [
        {
          name: 'Completion',
          type: 'gauge',
          min: 0,
          max: 100,
          splitNumber: 10,
          startAngle: 225,
          endAngle: -45,
          progress: {
            show: true,
          },
          pointer: {
            show: true,
          },
          axisLine: {
            lineStyle: {
              width: 12,
            },
          },
          detail: {
            show: true,
            formatter: '{value}%',
            offsetCenter: ['0%', '60%'],
          },
          title: {
            show: true,
            offsetCenter: ['0%', '85%'],
          },
          data: [{ value: 72, name: 'Completion' }],
        },
      ],
    },
  };
};

const buildPolarBarTemplate = (): ChartTemplate => {
  return {
    id: 'template-polar-bar',
    label: 'Polar bar',
    goal: 'cyclical-comparison',
    description: 'Starter polar bar chart for cyclical category comparisons.',
    chartType: 'polar',
    starterDataset: cloneDataset(polarDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Polar bar' },
      tooltip: { show: true, trigger: 'axis' },
      legend: { show: false },
      angleAxis: {
        type: 'category',
        data: ['Q1', 'Q2', 'Q3', 'Q4', 'Q5'],
        startAngle: 90,
        clockwise: true,
      },
      radiusAxis: { type: 'value' },
      polar: { center: ['50%', '55%'], radius: '70%' },
      series: [
        {
          name: 'Value',
          type: 'bar',
          coordinateSystem: 'polar',
          roundCap: true,
          data: [2.4, 3.1, 2.7, 3.6, 2.2],
        },
      ],
    },
  };
};

const buildPolarLineTemplate = (): ChartTemplate => {
  return {
    id: 'template-polar-line',
    label: 'Polar line',
    goal: 'cyclical-comparison',
    description: 'Starter polar line chart for cyclical trends.',
    chartType: 'polar',
    starterDataset: cloneDataset(polarDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Polar line' },
      tooltip: { show: true, trigger: 'axis' },
      legend: { show: false },
      angleAxis: {
        type: 'category',
        data: ['Q1', 'Q2', 'Q3', 'Q4', 'Q5'],
        startAngle: 90,
      },
      radiusAxis: { type: 'value' },
      polar: { center: ['50%', '55%'], radius: '70%' },
      series: [
        {
          name: 'Value',
          type: 'line',
          coordinateSystem: 'polar',
          smooth: true,
          data: [2.4, 3.1, 2.7, 3.6, 2.2],
        },
      ],
    },
  };
};

const buildParallelTemplate = (): ChartTemplate => {
  return {
    id: 'template-parallel-coordinates',
    label: 'Parallel coordinates',
    goal: 'multi-dimensional-analysis',
    description: 'Starter parallel coordinates chart for multi-dimensional numeric analysis.',
    chartType: 'parallel',
    starterDataset: cloneDataset(parallelDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Parallel coordinates' },
      tooltip: { show: true, trigger: 'item' },
      parallel: {
        left: '8%',
        right: '10%',
        top: '15%',
        bottom: '15%',
      },
      parallelAxis: [
        { dim: 0, name: 'Revenue', type: 'value' },
        { dim: 1, name: 'Cost', type: 'value' },
        { dim: 2, name: 'Growth', type: 'value' },
        { dim: 3, name: 'Satisfaction', type: 'value' },
      ],
      series: [
        {
          name: 'Profiles',
          type: 'parallel',
          smooth: false,
          progressive: 200,
          data: [
            [120, 80, 15, 70],
            [140, 95, 12, 75],
            [160, 110, 18, 82],
            [130, 90, 10, 68],
          ],
        },
      ],
    },
  };
};

const buildGeoScatterTemplate = (): ChartTemplate => {
  return {
    id: 'template-geo-scatter',
    label: 'Geo scatter',
    goal: 'geo-distribution',
    description: 'Starter geo scatter using lng/lat/value points.',
    chartType: 'geo',
    starterDataset: cloneDataset(geoDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Geo scatter' },
      tooltip: { show: true, trigger: 'item' },
      geo: {
        map: 'world-lite',
        roam: true,
        zoom: 1.1,
        center: [5, 45],
        itemStyle: {
          areaColor: '#f8fafc',
          borderColor: '#64748b',
        },
      },
      series: [
        {
          name: 'Locations',
          type: 'scatter',
          coordinateSystem: 'geo',
          symbolSize: 10,
          data: [
            { name: 'Berlin', value: [13.405, 52.52, 40] },
            { name: 'London', value: [-0.1276, 51.5072, 32] },
            { name: 'Paris', value: [2.3522, 48.8566, 28] },
            { name: 'Rome', value: [12.4964, 41.9028, 22] },
          ],
        },
      ],
    },
  };
};

const buildGeoEffectScatterTemplate = (): ChartTemplate => {
  return {
    id: 'template-geo-effect-scatter',
    label: 'Geo effect scatter',
    goal: 'geo-distribution',
    description: 'Starter geo effect scatter with ripple highlights.',
    chartType: 'geo',
    starterDataset: cloneDataset(geoDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Geo effect scatter' },
      tooltip: { show: true, trigger: 'item' },
      geo: {
        map: 'world-lite',
        roam: true,
        zoom: 1.1,
        center: [5, 45],
        itemStyle: {
          areaColor: '#f8fafc',
          borderColor: '#64748b',
        },
      },
      series: [
        {
          name: 'Locations',
          type: 'effectScatter',
          coordinateSystem: 'geo',
          symbolSize: 10,
          rippleEffect: {
            scale: 3,
            brushType: 'stroke',
          },
          data: [
            { name: 'Berlin', value: [13.405, 52.52, 40] },
            { name: 'London', value: [-0.1276, 51.5072, 32] },
            { name: 'Paris', value: [2.3522, 48.8566, 28] },
            { name: 'Rome', value: [12.4964, 41.9028, 22] },
          ],
        },
      ],
    },
  };
};

const buildMapTemplate = (): ChartTemplate => {
  return {
    id: 'template-map-choropleth-lite',
    label: 'Map choropleth (lite)',
    goal: 'geo-distribution',
    description: 'Starter map template using the built-in world-lite map scaffold.',
    chartType: 'map',
    starterDataset: cloneDataset(mapDataset),
    selectedSeriesIndex: 0,
    starterOption: {
      title: { show: true, text: 'Map choropleth (lite)' },
      tooltip: { show: true, trigger: 'item' },
      visualMap: {
        show: true,
        min: 0,
        max: 100,
        left: 'right',
        top: 'middle',
      },
      series: [
        {
          name: 'Coverage',
          type: 'map',
          map: 'world-lite',
          roam: true,
          label: { show: false },
          itemStyle: {
            areaColor: '#dbeafe',
            borderColor: '#64748b',
          },
          data: [{ name: 'World', value: 72 }],
        },
      ],
    },
  };
};

const asCartesianSeriesType = (chartType: ChartType, fallback: 'line' | 'bar'): 'line' | 'bar' => {
  return chartType === 'line' || chartType === 'bar' ? chartType : fallback;
};

export const buildTemplateFromGoal = (goal: TemplateGoal, chartType: ChartType): ChartTemplate => {
  if (goal === 'trend-over-time') {
    if (chartType === 'candlestick') {
      return buildCandlestickTemplate();
    }
    return buildTrendTemplate(asCartesianSeriesType(chartType, 'line'));
  }

  if (goal === 'category-comparison') {
    return buildCategoryTemplate(asCartesianSeriesType(chartType, 'bar'));
  }

  if (goal === 'part-to-whole') {
    return buildPartToWholeTemplate();
  }

  if (goal === 'relationship-between-two-measures') {
    return chartType === 'effectScatter' ? buildEffectScatterTemplate() : buildScatterTemplate();
  }

  if (goal === 'multi-metric-comparison') {
    return chartType === 'parallel' ? buildParallelTemplate() : buildRadarTemplate();
  }

  if (goal === 'matrix-intensity') {
    return chartType === 'calendar' ? buildCalendarHeatmapTemplate() : buildHeatmapTemplate();
  }

  if (goal === 'staged-conversion') {
    return buildFunnelTemplate();
  }

  if (goal === 'kpi-score') {
    return buildGaugeTemplate();
  }

  if (goal === 'cyclical-comparison') {
    return buildPolarBarTemplate();
  }

  if (goal === 'calendar-activity') {
    return buildCalendarHeatmapTemplate();
  }

  if (goal === 'multi-dimensional-analysis') {
    return buildParallelTemplate();
  }

  if (goal === 'geo-distribution') {
    if (chartType === 'scatter') {
      return buildGeoScatterTemplate();
    }
    if (chartType === 'map') {
      return buildMapTemplate();
    }
    return buildGeoEffectScatterTemplate();
  }

  return buildTwoSeriesTemplate(asCartesianSeriesType(chartType, 'line'));
};

export const chartTemplates: ChartTemplate[] = [
  buildTrendTemplate('line'),
  buildCategoryTemplate('bar'),
  buildPartToWholeTemplate(),
  buildTwoSeriesTemplate('line'),
  buildCandlestickTemplate(),
  buildScatterTemplate(),
  buildEffectScatterTemplate(),
  buildRadarTemplate(),
  buildHeatmapTemplate(),
  buildCalendarHeatmapTemplate(),
  buildFunnelTemplate(),
  buildGaugeTemplate(),
  buildPolarBarTemplate(),
  buildPolarLineTemplate(),
  buildParallelTemplate(),
  buildGeoScatterTemplate(),
  buildGeoEffectScatterTemplate(),
  buildMapTemplate(),
];

export const cloneTemplate = (template: ChartTemplate): ChartTemplate => ({
  ...template,
  starterOption: cloneOption(template.starterOption),
  starterDataset: cloneDataset(template.starterDataset),
});
