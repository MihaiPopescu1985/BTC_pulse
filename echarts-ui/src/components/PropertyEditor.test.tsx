import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PropertyEditor } from './PropertyEditor';
import type { EditorContext } from '../types/editor';
import type { EditorOption } from '../types/echarts';

const createContext = (option: EditorOption): EditorContext => ({
  currentChartType: 'line',
  option,
  selectedSeriesIndex: 0,
  selectedDataZoomIndex: 0,
  selectedXAxisIndex: 1,
  selectedYAxisIndex: 0,
  selectedGridIndex: 0,
  selectedVisualMapIndex: 0,
  selectedTitleIndex: 0,
  selectedDatasetIndex: 0,
  selectedRadarIndex: 0,
  selectedPolarIndex: 0,
  selectedSingleAxisIndex: 0,
  selectedParallelIndex: 0,
  selectedParallelAxisIndex: 0,
  selectedCalendarIndex: 0,
  selectedGeoIndex: 0,
  selectedAngleAxisIndex: 0,
  selectedRadiusAxisIndex: 0,
});

describe('PropertyEditor', () => {
  it('wires xAxis array-binding selector/add/remove actions', async () => {
    const user = userEvent.setup();

    const option = {
      series: [{ type: 'line' }],
      xAxis: [{ name: 'Axis 1', type: 'category' }, { name: 'Axis 2', type: 'category' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['category', 'value'], ['A', 120]] }],
    } as EditorOption;

    const onSelect = vi.fn();
    const onAdd = vi.fn();
    const onRemove = vi.fn();

    render(
      <PropertyEditor
        option={option}
        context={createContext(option)}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
        arrayBindingStates={{
          xAxis: {
            selectedIndex: 1,
            itemCount: 2,
            minItems: 1,
            onSelect,
            onAdd,
            onRemove,
          },
        }}
      />,
    );

    const xAxisSection = screen.getByRole('heading', { name: 'X Axis' }).closest('section');
    expect(xAxisSection).toBeTruthy();

    const section = xAxisSection as HTMLElement;
    const selector = within(section).getByRole('combobox', { name: 'X Axis' });

    await user.selectOptions(selector, '0');
    expect(onSelect).toHaveBeenCalledWith(0);

    await user.click(within(section).getByRole('button', { name: 'Add X Axis' }));
    expect(onAdd).toHaveBeenCalledTimes(1);

    await user.click(within(section).getByRole('button', { name: 'Remove Selected' }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('binds selected series encode fields to the resolved series path', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line' }],
      xAxis: [{ type: 'category' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Month', 'Sales'], ['Jan', 120]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const encodeXInput = screen.getByRole('textbox', { name: 'Encode X' });
    fireEvent.change(encodeXInput, { target: { value: 'Month' } });

    expect(onValueChange).toHaveBeenCalledWith('series.0.encode.x', 'Month');
  });

  it('binds line label.formatter field for common series options', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', label: { formatter: '' } }],
      xAxis: [{ type: 'category' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Month', 'Sales'], ['Jan', 120]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    fireEvent.change(screen.getByRole('textbox', { name: 'Label Formatter' }), {
      target: { value: '{b}: {c} units' },
    });

    expect(onValueChange).toHaveBeenCalledWith('series.0.label.formatter', '{b}: {c} units');
  });

  it('binds bar itemStyle.borderRadius JSON fallback field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'bar', itemStyle: { borderRadius: 0 }, data: [12, 18, 10] }],
      xAxis: [{ type: 'category', data: ['A', 'B', 'C'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Category', 'Value'], ['A', 12], ['B', 18], ['C', 10]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), currentChartType: 'bar', selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'expert');

    const radiusTextarea = screen.getByRole('textbox', { name: 'Item Border Radius (JSON)' });
    fireEvent.change(radiusTextarea, { target: { value: '[4, 4, 0, 0]' } });
    fireEvent.blur(radiusTextarea);

    expect(onValueChange).toHaveBeenCalledWith('series.0.itemStyle.borderRadius', [4, 4, 0, 0]);
  });

  it('binds scatter emphasis.focus field for common interaction states', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'scatter', emphasis: { focus: 'none' } }],
      xAxis: [{ type: 'value' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['X', 'Y'], [12, 20], [18, 35]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'scatter',
          selectedXAxisIndex: 0,
          selectedYAxisIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Emphasis Focus' }), 'self');

    expect(onValueChange).toHaveBeenCalledWith('series.0.emphasis.focus', 'self');
  });

  it('binds line areaStyle.opacity field for common area style options', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', areaStyle: { opacity: 0.15 } }],
      xAxis: [{ type: 'category', data: ['Jan', 'Feb', 'Mar'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Month', 'Sales'], ['Jan', 120], ['Feb', 132], ['Mar', 101]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Area Opacity' }), {
      target: { value: '0.35' },
    });

    expect(onValueChange).toHaveBeenCalledWith('series.0.areaStyle.opacity', 0.35);
  });

  it('binds dataZoom.start field', () => {
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataZoom: [{ type: 'slider', start: 10, end: 90 }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedDataZoomIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const dataZoomSection = screen.getByRole('heading', { name: 'DataZoom' }).closest('section') as HTMLElement;
    fireEvent.change(within(dataZoomSection).getByRole('spinbutton', { name: 'Start' }), {
      target: { value: '25' },
    });

    expect(onValueChange).toHaveBeenCalledWith('dataZoom.0.start', 25);
  });

  it('binds dataZoom.filterMode field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataZoom: [{ type: 'slider', start: 10, end: 90, filterMode: 'filter' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedDataZoomIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    const dataZoomSection = screen.getByRole('heading', { name: 'DataZoom' }).closest('section') as HTMLElement;
    await user.selectOptions(within(dataZoomSection).getByRole('combobox', { name: 'Filter Mode' }), 'weakFilter');

    expect(onValueChange).toHaveBeenCalledWith('dataZoom.0.filterMode', 'weakFilter');
  });

  it('binds dataZoom.zoomLock field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataZoom: [{ type: 'slider', zoomLock: false }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedDataZoomIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    const dataZoomSection = screen.getByRole('heading', { name: 'DataZoom' }).closest('section') as HTMLElement;
    fireEvent.click(within(dataZoomSection).getByRole('checkbox', { name: 'Zoom Lock' }));

    expect(onValueChange).toHaveBeenCalledWith('dataZoom.0.zoomLock', true);
  });

  it('shows slider-only dataZoom fields only when selected type is slider', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const sliderOption = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataZoom: [{ type: 'slider', handleSize: '100%' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    const { rerender } = render(
      <PropertyEditor
        option={sliderOption}
        context={{ ...createContext(sliderOption), selectedXAxisIndex: 0, selectedDataZoomIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    expect(screen.getByRole('textbox', { name: 'Handle Size' })).toBeInTheDocument();

    const insideOption = {
      ...sliderOption,
      dataZoom: [{ type: 'inside', handleSize: '100%' }],
    } as EditorOption;

    rerender(
      <PropertyEditor
        option={insideOption}
        context={{ ...createContext(insideOption), selectedXAxisIndex: 0, selectedDataZoomIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    expect(screen.queryByRole('textbox', { name: 'Handle Size' })).not.toBeInTheDocument();
  });

  it('binds grid.left field', () => {
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      grid: [{ left: '10%', right: '10%', top: '14%', bottom: '12%' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedGridIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const gridSection = screen.getByRole('heading', { name: 'Grid' }).closest('section') as HTMLElement;
    fireEvent.change(within(gridSection).getByRole('textbox', { name: 'Left' }), {
      target: { value: '8%' },
    });

    expect(onValueChange).toHaveBeenCalledWith('grid.0.left', '8%');
  });

  it('binds grid.containLabel field', () => {
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      grid: [{ containLabel: true }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedGridIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const gridSection = screen.getByRole('heading', { name: 'Grid' }).closest('section') as HTMLElement;
    fireEvent.click(within(gridSection).getByRole('checkbox', { name: 'Contain Label' }));

    expect(onValueChange).toHaveBeenCalledWith('grid.0.containLabel', false);
  });

  it('binds grid.backgroundColor field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      grid: [{ backgroundColor: 'transparent' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedGridIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const gridSection = screen.getByRole('heading', { name: 'Grid' }).closest('section') as HTMLElement;
    fireEvent.change(within(gridSection).getByRole('textbox', { name: 'Background Color' }), {
      target: { value: 'rgba(15,23,42,0.05)' },
    });

    expect(onValueChange).toHaveBeenCalledWith('grid.0.backgroundColor', 'rgba(15,23,42,0.05)');
  });

  it('binds grid.borderWidth field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      grid: [{ borderWidth: 0 }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedGridIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const gridSection = screen.getByRole('heading', { name: 'Grid' }).closest('section') as HTMLElement;
    fireEvent.change(within(gridSection).getByRole('spinbutton', { name: 'Border Width' }), {
      target: { value: '2' },
    });

    expect(onValueChange).toHaveBeenCalledWith('grid.0.borderWidth', 2);
  });

  it('binds visualMap.min field', () => {
    const onValueChange = vi.fn();

    const option = {
      visualMap: [{ show: true, type: 'continuous', min: 0, max: 100 }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedVisualMapIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const visualMapSection = screen.getByRole('heading', { name: 'VisualMap' }).closest('section') as HTMLElement;
    fireEvent.change(within(visualMapSection).getByRole('spinbutton', { name: 'Min' }), {
      target: { value: '5' },
    });

    expect(onValueChange).toHaveBeenCalledWith('visualMap.0.min', 5);
  });

  it('binds visualMap.type field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      visualMap: [{ show: true, type: 'continuous', min: 0, max: 100 }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedVisualMapIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const visualMapSection = screen.getByRole('heading', { name: 'VisualMap' }).closest('section') as HTMLElement;
    await user.selectOptions(within(visualMapSection).getByRole('combobox', { name: 'Type' }), 'piecewise');

    expect(onValueChange).toHaveBeenCalledWith('visualMap.0.type', 'piecewise');
  });

  it('shows piecewise-only visualMap fields only when selected type is piecewise', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const continuousOption = {
      visualMap: [{ show: true, type: 'continuous', min: 0, max: 100 }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    const { rerender } = render(
      <PropertyEditor
        option={continuousOption}
        context={{ ...createContext(continuousOption), selectedXAxisIndex: 0, selectedVisualMapIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    expect(screen.queryByRole('spinbutton', { name: 'Split Number' })).not.toBeInTheDocument();

    const piecewiseOption = {
      ...continuousOption,
      visualMap: [{ show: true, type: 'piecewise', min: 0, max: 100, splitNumber: 5 }],
    } as EditorOption;

    rerender(
      <PropertyEditor
        option={piecewiseOption}
        context={{ ...createContext(piecewiseOption), selectedXAxisIndex: 0, selectedVisualMapIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    expect(screen.getByRole('spinbutton', { name: 'Split Number' })).toBeInTheDocument();
  });

  it('binds visualMap.inRange.color field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      visualMap: [{ show: true, type: 'continuous', inRange: { color: ['#50a3ba', '#eac736', '#d94e5d'] } }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedVisualMapIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const visualMapSection = screen.getByRole('heading', { name: 'VisualMap' }).closest('section') as HTMLElement;
    const colorTextarea = within(visualMapSection).getByRole('textbox', { name: 'In Range Colors' });
    fireEvent.change(colorTextarea, { target: { value: '#2563eb\n#f59e0b' } });
    fireEvent.blur(colorTextarea);

    expect(onValueChange).toHaveBeenCalledWith('visualMap.0.inRange.color', ['#2563eb', '#f59e0b']);
  });

  it('binds visualMap.textStyle.color field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      visualMap: [{ show: true, type: 'continuous', textStyle: { color: '#e2e8f0' } }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedVisualMapIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const visualMapSection = screen.getByRole('heading', { name: 'VisualMap' }).closest('section') as HTMLElement;
    fireEvent.change(within(visualMapSection).getByRole('textbox', { name: 'Text Color' }), {
      target: { value: '#0f172a' },
    });

    expect(onValueChange).toHaveBeenCalledWith('visualMap.0.textStyle.color', '#0f172a');
  });

  it('binds title.right field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      title: [{ show: true, text: 'Revenue', right: '' }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedTitleIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const titleSection = screen.getByRole('heading', { name: 'Title' }).closest('section') as HTMLElement;
    fireEvent.change(within(titleSection).getByRole('textbox', { name: 'Right' }), {
      target: { value: '5%' },
    });

    expect(onValueChange).toHaveBeenCalledWith('title.0.right', '5%');
  });

  it('binds title.padding field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      title: [{ show: true, text: 'Revenue', padding: 5 }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedTitleIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const titleSection = screen.getByRole('heading', { name: 'Title' }).closest('section') as HTMLElement;
    fireEvent.change(within(titleSection).getByRole('spinbutton', { name: 'Padding' }), {
      target: { value: '16' },
    });

    expect(onValueChange).toHaveBeenCalledWith('title.0.padding', 16);
  });

  it('binds title.backgroundColor field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      title: [{ show: true, text: 'Revenue', backgroundColor: 'transparent' }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedTitleIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const titleSection = screen.getByRole('heading', { name: 'Title' }).closest('section') as HTMLElement;
    fireEvent.change(within(titleSection).getByRole('textbox', { name: 'Background Color' }), {
      target: { value: '#0f172a' },
    });

    expect(onValueChange).toHaveBeenCalledWith('title.0.backgroundColor', '#0f172a');
  });

  it('binds title.textStyle.fontWeight field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      title: [{ show: true, text: 'Revenue', textStyle: { fontWeight: 'normal' } }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedTitleIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const titleSection = screen.getByRole('heading', { name: 'Title' }).closest('section') as HTMLElement;
    await user.selectOptions(within(titleSection).getByRole('combobox', { name: 'Title Font Weight' }), '600');

    expect(onValueChange).toHaveBeenCalledWith('title.0.textStyle.fontWeight', '600');
  });

  it('binds title.subtextStyle.align field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      title: [{ show: true, text: 'Revenue', subtext: 'FY 2026', subtextStyle: { align: 'auto' } }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedTitleIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const titleSection = screen.getByRole('heading', { name: 'Title' }).closest('section') as HTMLElement;
    await user.selectOptions(within(titleSection).getByRole('combobox', { name: 'Subtext Align' }), 'center');

    expect(onValueChange).toHaveBeenCalledWith('title.0.subtextStyle.align', 'center');
  });

  it('binds title.link field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      title: [{ show: true, text: 'Revenue', link: '' }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedTitleIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const titleSection = screen.getByRole('heading', { name: 'Title' }).closest('section') as HTMLElement;
    fireEvent.change(within(titleSection).getByRole('textbox', { name: 'Link' }), {
      target: { value: 'https://example.com/report' },
    });

    expect(onValueChange).toHaveBeenCalledWith('title.0.link', 'https://example.com/report');
  });

  it('binds markLine.label.formatter field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', markLine: { label: { formatter: '' } } }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedSeriesIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const annotationsSection = screen.getByRole('heading', { name: 'Series Annotations' }).closest('section') as HTMLElement;
    fireEvent.change(within(annotationsSection).getByRole('textbox', { name: 'MarkLine Label Formatter' }), {
      target: { value: 'Target: {c}' },
    });

    expect(onValueChange).toHaveBeenCalledWith('series.0.markLine.label.formatter', 'Target: {c}');
  });

  it('binds markLine.lineStyle.color field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', markLine: { lineStyle: { color: '#f59e0b' } } }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedSeriesIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const annotationsSection = screen.getByRole('heading', { name: 'Series Annotations' }).closest('section') as HTMLElement;
    fireEvent.change(within(annotationsSection).getByRole('textbox', { name: 'MarkLine Line Color' }), {
      target: { value: '#22c55e' },
    });

    expect(onValueChange).toHaveBeenCalledWith('series.0.markLine.lineStyle.color', '#22c55e');
  });

  it('binds markPoint.symbolSize field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', markPoint: { symbolSize: 50 } }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedSeriesIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const annotationsSection = screen.getByRole('heading', { name: 'Series Annotations' }).closest('section') as HTMLElement;
    fireEvent.change(within(annotationsSection).getByRole('spinbutton', { name: 'MarkPoint Symbol Size' }), {
      target: { value: '72' },
    });

    expect(onValueChange).toHaveBeenCalledWith('series.0.markPoint.symbolSize', 72);
  });

  it('binds markArea.itemStyle.opacity field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', markArea: { itemStyle: { opacity: 0.2 } } }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedSeriesIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const annotationsSection = screen.getByRole('heading', { name: 'Series Annotations' }).closest('section') as HTMLElement;
    fireEvent.change(within(annotationsSection).getByRole('spinbutton', { name: 'MarkArea Opacity' }), {
      target: { value: '0.35' },
    });

    expect(onValueChange).toHaveBeenCalledWith('series.0.markArea.itemStyle.opacity', 0.35);
  });

  it('binds markLine.data JSON fallback field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line', markLine: { data: [] } }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedSeriesIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const annotationsSection = screen.getByRole('heading', { name: 'Series Annotations' }).closest('section') as HTMLElement;
    const dataInput = within(annotationsSection).getByRole('textbox', { name: 'MarkLine Data (JSON)' });
    fireEvent.change(dataInput, { target: { value: '[{\"yAxis\":180}]' } });
    fireEvent.blur(dataInput);

    expect(onValueChange).toHaveBeenCalledWith('series.0.markLine.data', [{ yAxis: 180 }]);
  });

  it('binds xAxis axisLabel.rotate field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line' }],
      xAxis: [{ type: 'category', axisLabel: { rotate: 0 } }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Month', 'Sales'], ['Jan', 120]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const xAxisSection = screen.getByRole('heading', { name: 'X Axis' }).closest('section') as HTMLElement;
    fireEvent.change(within(xAxisSection).getByRole('spinbutton', { name: 'Axis Label Rotate' }), {
      target: { value: '30' },
    });

    expect(onValueChange).toHaveBeenCalledWith('xAxis.0.axisLabel.rotate', 30);
  });

  it('binds xAxis axisLine.lineStyle.color field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line' }],
      xAxis: [{ type: 'category', axisLine: { lineStyle: { color: '#64748b' } } }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Month', 'Sales'], ['Jan', 120]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const xAxisSection = screen.getByRole('heading', { name: 'X Axis' }).closest('section') as HTMLElement;
    fireEvent.change(within(xAxisSection).getByRole('textbox', { name: 'Axis Line Color' }), {
      target: { value: '#22c55e' },
    });

    expect(onValueChange).toHaveBeenCalledWith('xAxis.0.axisLine.lineStyle.color', '#22c55e');
  });

  it('binds yAxis splitLine.show field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line' }],
      xAxis: [{ type: 'category' }],
      yAxis: [{ type: 'value', splitLine: { show: true } }],
      dataset: [{ source: [['Month', 'Sales'], ['Jan', 120]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedYAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const yAxisSection = screen.getByRole('heading', { name: 'Y Axis' }).closest('section') as HTMLElement;
    fireEvent.click(within(yAxisSection).getByRole('checkbox', { name: 'Split Line Show' }));

    expect(onValueChange).toHaveBeenCalledWith('yAxis.0.splitLine.show', false);
  });

  it('binds angleAxis axisTick.length field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      polar: [{ center: ['50%', '55%'], radius: '70%' }],
      angleAxis: [{ type: 'category', axisTick: { length: 5 } }],
      radiusAxis: [{ type: 'value' }],
      series: [{ type: 'bar', coordinateSystem: 'polar', data: [1, 2, 3] }],
      dataset: [{ source: [['Category', 'Value'], ['A', 1]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'polar',
          selectedAngleAxisIndex: 0,
          selectedRadiusAxisIndex: 0,
          selectedPolarIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const angleAxisSection = screen.getByRole('heading', { name: 'Angle Axis' }).closest('section') as HTMLElement;
    fireEvent.change(within(angleAxisSection).getByRole('spinbutton', { name: 'Axis Tick Length' }), {
      target: { value: '9' },
    });

    expect(onValueChange).toHaveBeenCalledWith('angleAxis.0.axisTick.length', 9);
  });

  it('binds radiusAxis axisLabel.formatter field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      polar: [{ center: ['50%', '55%'], radius: '70%' }],
      angleAxis: [{ type: 'category' }],
      radiusAxis: [{ type: 'value', axisLabel: { formatter: '' } }],
      series: [{ type: 'bar', coordinateSystem: 'polar', data: [1, 2, 3] }],
      dataset: [{ source: [['Category', 'Value'], ['A', 1]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'polar',
          selectedAngleAxisIndex: 0,
          selectedRadiusAxisIndex: 0,
          selectedPolarIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'expert');

    const radiusAxisSection = screen.getByRole('heading', { name: 'Radius Axis' }).closest('section') as HTMLElement;
    fireEvent.change(within(radiusAxisSection).getByRole('textbox', { name: 'Axis Label Formatter' }), {
      target: { value: '{value} km' },
    });

    expect(onValueChange).toHaveBeenCalledWith('radiusAxis.0.axisLabel.formatter', '{value} km');
  });

  it('binds dataset dimensions field to selected dataset path', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'line' }],
      xAxis: [{ type: 'category' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ dimensions: [], source: [['Month', 'Sales'], ['Jan', 120]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedDatasetIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const dimensionsTextarea = screen.getByRole('textbox', { name: 'Dataset Dimension Names' });
    fireEvent.change(dimensionsTextarea, { target: { value: 'Month\nSales' } });
    fireEvent.blur(dimensionsTextarea);

    expect(onValueChange).toHaveBeenCalledWith('dataset.0.dimensions', ['Month', 'Sales']);
  });

  it('binds candlestick style field for selected candlestick series', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'candlestick', itemStyle: { color0: '#ef5350' } }],
      xAxis: [{ type: 'category' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Date', 'Open', 'Close', 'Low', 'High'], ['2026-03-01', 120, 132, 115, 135]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'candlestick',
          selectedXAxisIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const downColorInput = screen.getByRole('textbox', { name: 'Down Color' });
    fireEvent.change(downColorInput, { target: { value: '#d32f2f' } });

    expect(onValueChange).toHaveBeenCalledWith('series.0.itemStyle.color0', '#d32f2f');
  });

  it('binds scatter symbol size field for selected scatter series', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'scatter', symbolSize: 10 }],
      xAxis: [{ type: 'value' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['X', 'Y'], [12, 20], [18, 35]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'scatter',
          selectedXAxisIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const symbolSizeInput = screen.getByRole('spinbutton', { name: 'Symbol Size' });
    fireEvent.change(symbolSizeInput, { target: { value: '18' } });

    expect(onValueChange).toHaveBeenCalledWith('series.0.symbolSize', 18);
  });

  it('binds radar symbol size field for selected radar series', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      radar: [{ indicator: [{ name: 'A', max: 100 }, { name: 'B', max: 100 }, { name: 'C', max: 100 }] }],
      series: [{ type: 'radar', symbolSize: 6 }],
      dataset: [{ source: [['Team', 'A', 'B', 'C'], ['Alpha', 80, 70, 90]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'radar',
          selectedRadarIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const symbolSizeInput = screen.getByRole('spinbutton', { name: 'Symbol Size' });
    fireEvent.change(symbolSizeInput, { target: { value: '10' } });

    expect(onValueChange).toHaveBeenCalledWith('series.0.symbolSize', 10);
  });

  it('binds heatmap encode value field for selected heatmap series', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'heatmap', encode: { value: [2] } }],
      xAxis: [{ type: 'category' }],
      yAxis: [{ type: 'category' }],
      dataset: [{ source: [['X', 'Y', 'Value'], ['Mon', 'AM', 12]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'heatmap',
          selectedXAxisIndex: 0,
          selectedYAxisIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const encodeValueInput = screen.getByRole('textbox', { name: 'Encode Value' });
    fireEvent.change(encodeValueInput, { target: { value: '2\n3' } });
    fireEvent.blur(encodeValueInput);

    expect(onValueChange).toHaveBeenCalledWith('series.0.encode.value', ['2', '3']);
  });

  it('binds funnel sort field for selected funnel series', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'funnel', sort: 'descending' }],
      dataset: [{ source: [['Stage', 'Value'], ['Visit', 100]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'funnel',
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const sortSelect = screen.getByRole('combobox', { name: 'Sort' });
    await user.selectOptions(sortSelect, 'ascending');

    expect(onValueChange).toHaveBeenCalledWith('series.0.sort', 'ascending');
  });

  it('binds gauge max field for selected gauge series', async () => {
    const onValueChange = vi.fn();

    const option = {
      series: [{ type: 'gauge', min: 0, max: 100, data: [{ value: 72, name: 'Completion' }] }],
      dataset: [{ source: [['Metric', 'Value'], ['Completion', 72]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'gauge',
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const maxInput = screen.getByRole('spinbutton', { name: 'Max' });
    fireEvent.change(maxInput, { target: { value: '120' } });

    expect(onValueChange).toHaveBeenCalledWith('series.0.max', 120);
  });

  it('binds polar angle-axis field for selected polar component index', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      polar: [{ center: ['50%', '55%'], radius: '70%' }],
      angleAxis: [{ type: 'category', startAngle: 90 }],
      radiusAxis: [{ type: 'value' }],
      series: [{ type: 'bar', coordinateSystem: 'polar', data: [1, 2, 3] }],
      dataset: [{ source: [['Category', 'Value'], ['A', 1]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'polar',
          selectedAngleAxisIndex: 0,
          selectedRadiusAxisIndex: 0,
          selectedPolarIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const startAngleInput = screen.getByRole('spinbutton', { name: 'Start Angle' });
    fireEvent.change(startAngleInput, { target: { value: '120' } });

    expect(onValueChange).toHaveBeenCalledWith('angleAxis.0.startAngle', 120);
  });

  it('binds parallel-axis dim field for selected parallelAxis index', () => {
    const onValueChange = vi.fn();

    const option = {
      parallel: [{ left: '8%', right: '10%', top: '15%', bottom: '15%' }],
      parallelAxis: [{ dim: 0, type: 'value' }, { dim: 1, type: 'value' }],
      series: [{ type: 'parallel', data: [[10, 20], [15, 25]] }],
      dataset: [{ source: [['Item', 'A', 'B'], ['One', 10, 20]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'parallel',
          selectedParallelIndex: 0,
          selectedParallelAxisIndex: 1,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const dimInput = screen.getByRole('spinbutton', { name: 'Dim' });
    fireEvent.change(dimInput, { target: { value: '3' } });

    expect(onValueChange).toHaveBeenCalledWith('parallelAxis.1.dim', 3);
  });

  it('binds geo map field for selected geo index', () => {
    const onValueChange = vi.fn();

    const option = {
      geo: [{ map: 'world-lite', roam: true }],
      series: [{ type: 'effectScatter', coordinateSystem: 'geo' }],
      dataset: [{ source: [['Name', 'Lng', 'Lat', 'Value'], ['Berlin', 13.405, 52.52, 40]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'geo',
          selectedGeoIndex: 0,
        }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const mapInput = screen.getByRole('textbox', { name: 'Map' });
    fireEvent.change(mapInput, { target: { value: 'custom-map' } });

    expect(onValueChange).toHaveBeenCalledWith('geo.0.map', 'custom-map');
  });

  it('binds tooltip formatter/valueFormatter/axisPointer.type fields', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      tooltip: { show: true, trigger: 'axis', formatter: '', valueFormatter: '', axisPointer: { type: 'line' } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as unknown as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const tooltipSection = screen.getByRole('heading', { name: 'Tooltip' }).closest('section');
    expect(tooltipSection).toBeTruthy();
    const section = tooltipSection as HTMLElement;

    fireEvent.change(within(section).getByRole('textbox', { name: 'Formatter' }), {
      target: { value: '{b}: {c}' },
    });
    expect(onValueChange).toHaveBeenCalledWith('tooltip.formatter', '{b}: {c}');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    fireEvent.change(within(section).getByRole('textbox', { name: 'Value Formatter' }), {
      target: { value: '(value) => `${value} ms`' },
    });
    expect(onValueChange).toHaveBeenCalledWith('tooltip.valueFormatter', '(value) => `${value} ms`');

    await user.selectOptions(within(section).getByRole('combobox', { name: 'Axis Pointer Type' }), 'cross');
    expect(onValueChange).toHaveBeenCalledWith('tooltip.axisPointer.type', 'cross');
  });

  it('binds axisPointer.triggerTooltip field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      axisPointer: { show: true, type: 'line', triggerTooltip: true },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const axisPointerSection = screen.getByRole('heading', { name: 'Axis Pointer' }).closest('section') as HTMLElement;
    fireEvent.click(within(axisPointerSection).getByRole('checkbox', { name: 'Trigger Tooltip' }));

    expect(onValueChange).toHaveBeenCalledWith('axisPointer.triggerTooltip', false);
  });

  it('binds axisPointer.handle.show field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      axisPointer: { show: true, type: 'line', handle: { show: false } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const axisPointerSection = screen.getByRole('heading', { name: 'Axis Pointer' }).closest('section') as HTMLElement;
    fireEvent.click(within(axisPointerSection).getByRole('checkbox', { name: 'Handle Show' }));

    expect(onValueChange).toHaveBeenCalledWith('axisPointer.handle.show', true);
  });

  it('binds axisPointer.label.formatter field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      axisPointer: { show: true, type: 'line', label: { formatter: '' } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const axisPointerSection = screen.getByRole('heading', { name: 'Axis Pointer' }).closest('section') as HTMLElement;
    fireEvent.change(within(axisPointerSection).getByRole('textbox', { name: 'Label Formatter' }), {
      target: { value: '{value} units' },
    });

    expect(onValueChange).toHaveBeenCalledWith('axisPointer.label.formatter', '{value} units');
  });

  it('binds axisPointer.lineStyle.color field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      axisPointer: { show: true, type: 'line', lineStyle: { color: '#94a3b8' } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const axisPointerSection = screen.getByRole('heading', { name: 'Axis Pointer' }).closest('section') as HTMLElement;
    fireEvent.change(within(axisPointerSection).getByRole('textbox', { name: 'Line Color' }), {
      target: { value: '#22c55e' },
    });

    expect(onValueChange).toHaveBeenCalledWith('axisPointer.lineStyle.color', '#22c55e');
  });

  it('binds brush.brushType field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      brush: { toolbox: ['rect', 'polygon', 'keep', 'clear'], brushType: 'rect' },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const brushSection = screen.getByRole('heading', { name: 'Brush' }).closest('section') as HTMLElement;
    await user.selectOptions(within(brushSection).getByRole('combobox', { name: 'Brush Type' }), 'polygon');

    expect(onValueChange).toHaveBeenCalledWith('brush.brushType', 'polygon');
  });

  it('binds brush.throttleType field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      brush: { brushType: 'rect', throttleType: 'fixRate' },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    const brushSection = screen.getByRole('heading', { name: 'Brush' }).closest('section') as HTMLElement;
    await user.selectOptions(within(brushSection).getByRole('combobox', { name: 'Throttle Type' }), 'debounce');

    expect(onValueChange).toHaveBeenCalledWith('brush.throttleType', 'debounce');
  });

  it('binds brush.throttleDelay field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      brush: { brushType: 'rect', throttleDelay: 0 },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    const brushSection = screen.getByRole('heading', { name: 'Brush' }).closest('section') as HTMLElement;
    fireEvent.change(within(brushSection).getByRole('spinbutton', { name: 'Throttle Delay' }), {
      target: { value: '120' },
    });

    expect(onValueChange).toHaveBeenCalledWith('brush.throttleDelay', 120);
  });

  it('binds brush.inBrush.colorAlpha field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      brush: { brushType: 'rect', inBrush: { colorAlpha: 1 } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    const brushSection = screen.getByRole('heading', { name: 'Brush' }).closest('section') as HTMLElement;
    fireEvent.change(within(brushSection).getByRole('spinbutton', { name: 'In Brush Alpha' }), {
      target: { value: '0.85' },
    });

    expect(onValueChange).toHaveBeenCalledWith('brush.inBrush.colorAlpha', 0.85);
  });

  it('binds brush.outOfBrush.colorAlpha field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      brush: { brushType: 'rect', outOfBrush: { colorAlpha: 0.1 } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');
    const brushSection = screen.getByRole('heading', { name: 'Brush' }).closest('section') as HTMLElement;
    fireEvent.change(within(brushSection).getByRole('spinbutton', { name: 'Out Of Brush Alpha' }), {
      target: { value: '0.3' },
    });

    expect(onValueChange).toHaveBeenCalledWith('brush.outOfBrush.colorAlpha', 0.3);
  });

  it('shows axisPointer crossStyle vs shadowStyle fields conditionally by type', async () => {
    const user = userEvent.setup();
    const option = {
      axisPointer: { show: true, type: 'cross' },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    const { rerender } = render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const axisPointerSection = screen.getByRole('heading', { name: 'Axis Pointer' }).closest('section') as HTMLElement;
    expect(within(axisPointerSection).getByRole('textbox', { name: 'Cross Color' })).toBeInTheDocument();
    expect(within(axisPointerSection).queryByRole('textbox', { name: 'Shadow Color' })).not.toBeInTheDocument();

    const shadowOption = {
      ...option,
      axisPointer: { ...option.axisPointer, type: 'shadow' },
    } as EditorOption;

    rerender(
      <PropertyEditor
        option={shadowOption}
        context={{ ...createContext(shadowOption), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    const rerenderedAxisPointerSection = screen.getByRole('heading', { name: 'Axis Pointer' }).closest('section') as HTMLElement;
    expect(within(rerenderedAxisPointerSection).getByRole('textbox', { name: 'Shadow Color' })).toBeInTheDocument();
    expect(within(rerenderedAxisPointerSection).queryByRole('textbox', { name: 'Cross Color' })).not.toBeInTheDocument();
  });

  it('binds legend icon/itemGap/textStyle.color fields', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      legend: {
        show: true,
        icon: 'roundRect',
        itemGap: 10,
        textStyle: { color: '#e2e8f0' },
      },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const legendSection = screen.getByRole('heading', { name: 'Legend' }).closest('section');
    expect(legendSection).toBeTruthy();
    const section = legendSection as HTMLElement;

    fireEvent.change(within(section).getByRole('textbox', { name: 'Icon' }), {
      target: { value: 'circle' },
    });
    expect(onValueChange).toHaveBeenCalledWith('legend.icon', 'circle');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    fireEvent.change(within(section).getByRole('spinbutton', { name: 'Item Gap' }), {
      target: { value: '18' },
    });
    expect(onValueChange).toHaveBeenCalledWith('legend.itemGap', 18);

    fireEvent.change(within(section).getByRole('textbox', { name: 'Text Color' }), {
      target: { value: '#94a3b8' },
    });
    expect(onValueChange).toHaveBeenCalledWith('legend.textStyle.color', '#94a3b8');
  });

  it('binds toolbox.show field', () => {
    const onValueChange = vi.fn();

    const option = {
      toolbox: { show: false, feature: { saveAsImage: { show: true } } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    const toolboxSection = screen.getByRole('heading', { name: 'Toolbox' }).closest('section') as HTMLElement;
    const toolboxShowCheckbox = toolboxSection.querySelector('[data-editor-path="toolbox.show"] input[type="checkbox"]');
    expect(toolboxShowCheckbox).toBeTruthy();
    fireEvent.click(toolboxShowCheckbox as HTMLInputElement);

    expect(onValueChange).toHaveBeenCalledWith('toolbox.show', true);
  });

  it('binds toolbox.itemSize field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      toolbox: { show: true, itemSize: 15, feature: { saveAsImage: { show: true } } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const toolboxSection = screen.getByRole('heading', { name: 'Toolbox' }).closest('section') as HTMLElement;
    fireEvent.change(within(toolboxSection).getByRole('spinbutton', { name: 'Item Size' }), {
      target: { value: '22' },
    });

    expect(onValueChange).toHaveBeenCalledWith('toolbox.itemSize', 22);
  });

  it('binds toolbox.feature.saveAsImage.type field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      toolbox: {
        show: true,
        feature: { saveAsImage: { show: true, type: 'png' } },
      },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const toolboxSection = screen.getByRole('heading', { name: 'Toolbox' }).closest('section') as HTMLElement;
    await user.selectOptions(within(toolboxSection).getByRole('combobox', { name: 'Save As Image Type' }), 'svg');

    expect(onValueChange).toHaveBeenCalledWith('toolbox.feature.saveAsImage.type', 'svg');
  });

  it('binds toolbox.feature.magicType.type field', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();

    const option = {
      toolbox: {
        show: true,
        feature: { magicType: { show: true, type: ['line', 'bar'] } },
      },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const toolboxSection = screen.getByRole('heading', { name: 'Toolbox' }).closest('section') as HTMLElement;
    const magicTypeTextarea = within(toolboxSection).getByRole('textbox', { name: 'Magic Type List' });
    fireEvent.change(magicTypeTextarea, { target: { value: 'line\nbar\nstack' } });
    fireEvent.blur(magicTypeTextarea);

    expect(onValueChange).toHaveBeenCalledWith('toolbox.feature.magicType.type', ['line', 'bar', 'stack']);
  });

  it('filters visible fields and sections by global property search', async () => {
    const user = userEvent.setup();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      tooltip: { show: true, trigger: 'axis' },
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Title' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Tooltip' })).toBeInTheDocument();

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'tooltip.trigger' } });

    expect(screen.getByRole('heading', { name: 'Tooltip' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Title' })).not.toBeInTheDocument();
    expect(screen.getByText('tooltip.trigger')).toBeInTheDocument();
    expect(document.querySelectorAll('.field-highlight').length).toBeGreaterThan(0);

    await user.clear(searchInput);
    expect(screen.getByRole('heading', { name: 'Title' })).toBeInTheDocument();
  });

  it('finds newly added tooltip/legend fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      tooltip: { show: true, trigger: 'axis' },
      legend: { show: true },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'tooltip.valueFormatter' } });

    expect(screen.getByRole('heading', { name: 'Tooltip' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Value Formatter' })).toBeInTheDocument();
    expect(screen.getByText('tooltip.valueFormatter')).toBeInTheDocument();
  });

  it('finds newly added axis presentation fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'xAxis.axisLine.lineStyle.color' } });

    expect(screen.getByRole('heading', { name: 'X Axis' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Axis Line Color' })).toBeInTheDocument();
    expect(screen.getByText('xAxis.axisLine.lineStyle.color')).toBeInTheDocument();
  });

  it('finds new common series interaction fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      series: [{ type: 'scatter' }],
      xAxis: [{ type: 'value' }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['X', 'Y'], [12, 20], [18, 35]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{
          ...createContext(option),
          currentChartType: 'scatter',
          selectedXAxisIndex: 0,
          selectedYAxisIndex: 0,
        }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'series.blur.itemStyle.opacity' } });

    expect(screen.getByRole('heading', { name: 'Selected Series' })).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: 'Blur Item Opacity' })).toBeInTheDocument();
    expect(screen.getByText('series.blur.itemStyle.opacity')).toBeInTheDocument();
  });

  it('finds newly added dataZoom fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataZoom: [{ type: 'slider', zoomLock: false }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedDataZoomIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'dataZoom.zoomLock' } });

    expect(screen.getByRole('heading', { name: 'DataZoom' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Zoom Lock' })).toBeInTheDocument();
    expect(screen.getByText('dataZoom.zoomLock')).toBeInTheDocument();
  });

  it('finds newly added visualMap fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      visualMap: [{ show: true, type: 'continuous' }],
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedVisualMapIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'visualMap.outOfRange.symbolSize' } });

    expect(screen.getByRole('heading', { name: 'VisualMap' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Out Of Range Symbol Size' })).toBeInTheDocument();
    expect(screen.getByText('visualMap.outOfRange.symbolSize')).toBeInTheDocument();
  });

  it('finds newly added grid style fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      series: [{ type: 'line', data: [120, 200, 150] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue', 'Wed'] }],
      yAxis: [{ type: 'value' }],
      grid: [{ shadowColor: 'rgba(0,0,0,0.2)' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200], ['Wed', 150]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedGridIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'grid.shadowColor' } });

    expect(screen.getByRole('heading', { name: 'Grid' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Shadow Color' })).toBeInTheDocument();
    expect(screen.getByText('grid.shadowColor')).toBeInTheDocument();
  });

  it('finds newly added toolbox fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      toolbox: { show: true, feature: { saveAsImage: { show: true, type: 'png' } } },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'toolbox.feature.saveAsImage.type' } });

    expect(screen.getByRole('heading', { name: 'Toolbox' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Save As Image Type' })).toBeInTheDocument();
    expect(screen.getByText('toolbox.feature.saveAsImage.type')).toBeInTheDocument();
  });

  it('finds newly added title fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      title: [{ show: true, text: 'Revenue', subtext: 'FY 2026' }],
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedTitleIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'title.subtextStyle.align' } });

    expect(screen.getByRole('heading', { name: 'Title' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Subtext Align' })).toBeInTheDocument();
    expect(screen.getByText('title.subtextStyle.align')).toBeInTheDocument();
  });

  it('finds newly added series annotation fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      series: [{ type: 'line' }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0, selectedSeriesIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'series.markArea.itemStyle.opacity' } });

    expect(screen.getByRole('heading', { name: 'Series Annotations' })).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: 'MarkArea Opacity' })).toBeInTheDocument();
    expect(screen.getByText('series.markArea.itemStyle.opacity')).toBeInTheDocument();
  });

  it('finds newly added axisPointer fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      axisPointer: { show: true, type: 'line' },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'axisPointer.triggerTooltip' } });

    expect(screen.getByRole('heading', { name: 'Axis Pointer' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Trigger Tooltip' })).toBeInTheDocument();
    expect(screen.getByText('axisPointer.triggerTooltip')).toBeInTheDocument();
  });

  it('finds newly added brush fields via global property search', async () => {
    const user = userEvent.setup();

    const option = {
      brush: { brushType: 'rect' },
      series: [{ type: 'line', data: [120, 200] }],
      xAxis: [{ type: 'category', data: ['Mon', 'Tue'] }],
      yAxis: [{ type: 'value' }],
      dataset: [{ source: [['Day', 'Sales'], ['Mon', 120], ['Tue', 200]] }],
    } as EditorOption;

    render(
      <PropertyEditor
        option={option}
        context={{ ...createContext(option), selectedXAxisIndex: 0 }}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), 'advanced');

    const searchInput = screen.getByRole('textbox', { name: 'Global Property Search' });
    fireEvent.change(searchInput, { target: { value: 'brush.throttleDelay' } });

    expect(screen.getByRole('heading', { name: 'Brush' })).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: 'Throttle Delay' })).toBeInTheDocument();
    expect(screen.getByText('brush.throttleDelay')).toBeInTheDocument();
  });
});
