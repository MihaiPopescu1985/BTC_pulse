import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { SESSION_VERSION, STORAGE_KEYS } from './utils/persistence';

const getJsonPanelTextarea = (): HTMLTextAreaElement => {
  const importButtons = screen.getAllByRole('button', { name: 'Import JSON' });
  const jsonSection = importButtons[0]?.closest('section');
  if (!jsonSection) {
    throw new Error('Could not locate JSON panel section.');
  }

  return within(jsonSection).getByRole('textbox') as HTMLTextAreaElement;
};

vi.mock('./components/ChartPreview', () => {
  const MockPreview = React.forwardRef((_props: unknown, ref: React.ForwardedRef<{ exportImage: () => string | null }>) => {
    React.useImperativeHandle(ref, () => ({
      exportImage: () => null,
    }));
    return <div data-testid="chart-preview" />;
  });

  return {
    ChartPreview: MockPreview,
  };
});

describe('App integration', () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState(null, '', '/');
  });

  it('adds/selects a second xAxis and edits the selected axis path', async () => {
    const user = userEvent.setup();
    render(<App />);

    const xAxisSection = screen.getByRole('heading', { name: 'X Axis' }).closest('section');
    expect(xAxisSection).toBeTruthy();
    const section = xAxisSection as HTMLElement;

    await user.click(within(section).getByRole('button', { name: 'Add X Axis' }));
    await user.selectOptions(within(section).getByRole('combobox', { name: 'X Axis' }), '1');

    const nameInput = within(section).getByRole('textbox', { name: 'Name' });
    await user.clear(nameInput);
    await user.type(nameInput, 'Secondary Axis');

    const jsonTextarea = getJsonPanelTextarea();

    await waitFor(() => {
      const parsed = JSON.parse(jsonTextarea.value) as {
        xAxis: Array<{ name?: string }>;
      };

      expect(Array.isArray(parsed.xAxis)).toBe(true);
      expect(parsed.xAxis).toHaveLength(2);
      expect(parsed.xAxis[1]?.name).toBe('Secondary Axis');
      expect(parsed.xAxis[0]?.name ?? '').not.toBe('Secondary Axis');
    });
  }, 10000);

  it('renders manual test mode toggle and updates last changed path/value after property edit', async () => {
    const user = userEvent.setup();
    render(<App />);

    const toggle = screen.getByRole('checkbox', { name: 'Manual test mode' });
    expect(toggle).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Last Change' })).not.toBeInTheDocument();

    await user.click(toggle);
    const lastChangeCard = screen.getByRole('heading', { name: 'Last Change' }).closest('section');
    expect(lastChangeCard).toBeTruthy();
    expect(within(lastChangeCard as HTMLElement).getByText('No property edit yet')).toBeInTheDocument();

    const titleSection = screen.getByRole('heading', { name: 'Title' }).closest('section');
    expect(titleSection).toBeTruthy();
    const titleInput = within(titleSection as HTMLElement).getByRole('textbox', { name: 'Text' });
    await user.clear(titleInput);
    await user.type(titleInput, 'Manual QA Title');

    await waitFor(() => {
      expect(within(lastChangeCard as HTMLElement).getByText('title.0.text')).toBeInTheDocument();
      expect(within(lastChangeCard as HTMLElement).getByText('"Manual QA Title"')).toBeInTheDocument();
    });
  });

  it('applies a validation one-click fix to restore empty title text', async () => {
    const user = userEvent.setup();

    localStorage.setItem(
      STORAGE_KEYS.session,
      JSON.stringify({
        version: SESSION_VERSION,
        option: {
          title: [{ show: true, text: '' }],
          tooltip: { show: true, trigger: 'axis' },
          legend: { show: true },
          dataset: [{ source: [['Day', 'Value'], ['Mon', 120]] }],
          xAxis: [{ show: true, type: 'category' }],
          yAxis: [{ show: true, type: 'value' }],
          series: [{ name: 'Sales', type: 'line', data: [120] }],
        },
        selectedSeriesIndex: 0,
        lastPreset: 'basic-line',
        savedAt: Date.now(),
      }),
    );

    render(<App />);

    await screen.findByText('title.show is true, but title.text is empty.');
    await user.click(screen.getByRole('button', { name: "Set title.text to 'Chart Title'" }));

    const jsonTextarea = getJsonPanelTextarea();
    await user.click(screen.getAllByRole('button', { name: 'Export JSON' })[0]);

    await waitFor(() => {
      const parsed = JSON.parse(jsonTextarea.value) as {
        title: Array<{ text?: string }>;
      };
      expect(parsed.title[0]?.text).toBe('Chart Title');
    });
  }, 10000);

  it('adds/selects a new parallelAxis and edits only that selected axis entry', async () => {
    const user = userEvent.setup();
    render(<App />);

    const parallelTemplateCard = screen.getByRole('heading', { name: 'Parallel coordinates' }).closest('article');
    expect(parallelTemplateCard).toBeTruthy();
    await user.click(within(parallelTemplateCard as HTMLElement).getByRole('button', { name: 'Apply' }));

    const parallelAxisSection = await screen.findByRole('heading', { name: 'Parallel Axis' });
    const section = parallelAxisSection.closest('section') as HTMLElement;

    await user.click(within(section).getByRole('button', { name: 'Add Parallel Axis' }));
    await user.selectOptions(within(section).getByRole('combobox', { name: 'Parallel Axis' }), '4');

    const nameInput = within(section).getByRole('textbox', { name: 'Name' });
    await user.clear(nameInput);
    await user.type(nameInput, 'New Dimension');

    const jsonTextarea = getJsonPanelTextarea();
    await user.click(screen.getAllByRole('button', { name: 'Export JSON' })[0]);

    await waitFor(() => {
      const parsed = JSON.parse(jsonTextarea.value) as {
        parallelAxis: Array<{ name?: string }>;
      };

      expect(Array.isArray(parsed.parallelAxis)).toBe(true);
      expect(parsed.parallelAxis).toHaveLength(5);
      expect(parsed.parallelAxis[4]?.name).toBe('New Dimension');
      expect(parsed.parallelAxis[0]?.name ?? '').not.toBe('New Dimension');
    });
  });
});
