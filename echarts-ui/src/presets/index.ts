import type { EditorOption } from '../types/echarts';

const clone = (option: EditorOption): EditorOption => JSON.parse(JSON.stringify(option));

const linePreset: EditorOption = {
  title: { show: true, text: 'Basic Line' },
  tooltip: { show: true, trigger: 'axis' },
  legend: { show: true },
  dataset: {
    source: [
      ['Day', 'Sales'],
      ['Mon', 120],
      ['Tue', 200],
      ['Wed', 150],
      ['Thu', 80],
      ['Fri', 70],
      ['Sat', 110],
      ['Sun', 130],
    ],
  },
  xAxis: { show: true, type: 'category', data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] },
  yAxis: { show: true, type: 'value' },
  series: [
    {
      name: 'Sales',
      type: 'line',
      smooth: true,
      data: [120, 200, 150, 80, 70, 110, 130],
    },
  ],
};

const barPreset: EditorOption = {
  title: { show: true, text: 'Basic Bar' },
  tooltip: { show: true, trigger: 'axis' },
  legend: { show: true },
  dataset: {
    source: [
      ['Product', '2015', '2016'],
      ['Matcha Latte', 43.3, 85.8],
      ['Milk Tea', 83.1, 73.4],
      ['Cheese Cocoa', 86.4, 65.2],
      ['Walnut Brownie', 72.4, 53.9],
    ],
  },
  xAxis: { show: true, type: 'category', data: ['Matcha Latte', 'Milk Tea', 'Cheese Cocoa', 'Walnut Brownie'] },
  yAxis: { show: true, type: 'value' },
  series: [
    {
      name: '2016',
      type: 'bar',
      data: [85.8, 73.4, 65.2, 53.9],
    },
  ],
};

const piePreset: EditorOption = {
  title: { show: true, text: 'Basic Pie' },
  tooltip: { show: true, trigger: 'item' },
  legend: { show: true, orient: 'vertical', left: 'left' },
  dataset: {
    source: [
      ['Source', 'Traffic'],
      ['Search Engine', 1048],
      ['Direct', 735],
      ['Email', 580],
      ['Union Ads', 484],
      ['Video Ads', 300],
    ],
  },
  xAxis: { show: false, type: 'category', data: [] },
  yAxis: { show: false, type: 'value' },
  series: [
    {
      name: 'Traffic Source',
      type: 'pie',
      radius: '50%',
      data: [
        { value: 1048, name: 'Search Engine' },
        { value: 735, name: 'Direct' },
        { value: 580, name: 'Email' },
        { value: 484, name: 'Union Ads' },
        { value: 300, name: 'Video Ads' },
      ],
    },
  ],
};

export type PresetName = 'basic-line' | 'basic-bar' | 'basic-pie';

export const presets: Record<PresetName, EditorOption> = {
  'basic-line': linePreset,
  'basic-bar': barPreset,
  'basic-pie': piePreset,
};

export const getPreset = (name: PresetName): EditorOption => clone(presets[name]);
