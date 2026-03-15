import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import type { FieldSchema } from '../types/editor';
import { SchemaField } from './SchemaField';

const textField: FieldSchema = {
  key: 'title.text',
  label: 'Text',
  path: 'title.0.text',
  control: 'text',
  defaultValue: '',
};

const checkboxField: FieldSchema = {
  key: 'legend.show',
  label: 'Show Legend',
  path: 'legend.show',
  control: 'checkbox',
  defaultValue: false,
  description: 'Display legend entries in the chart.',
  helpText: 'Useful for multi-series charts.',
};

describe('SchemaField', () => {
  it('shows debug row only in manual test mode', () => {
    const { rerender } = render(
      <SchemaField
        field={textField}
        path="title.0.text"
        value="Sales"
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    expect(screen.queryByText('Path: title.0.text')).not.toBeInTheDocument();
    expect(screen.queryByText('Value: "Sales"')).not.toBeInTheDocument();

    rerender(
      <SchemaField
        field={textField}
        path="title.0.text"
        manualTestMode
        value="Sales"
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    expect(screen.getByText('Path: title.0.text')).toBeInTheDocument();
    expect(screen.getByText('Value: "Sales"')).toBeInTheDocument();
  });

  it('applies a temporary changed highlight class after value update', async () => {
    const Harness = () => {
      const [value, setValue] = useState('Initial');
      return (
        <SchemaField
          field={textField}
          path="title.0.text"
          value={value}
          onValueChange={(_, next) => setValue(String(next))}
          onResetToDefault={vi.fn()}
        />
      );
    };

    const { container } = render(<Harness />);
    const input = screen.getByRole('textbox', { name: 'Text' });
    fireEvent.change(input, { target: { value: 'Updated' } });

    await waitFor(() => {
      const fieldContainer = container.querySelector('[data-editor-path="title.0.text"]');
      expect(fieldContainer?.classList.contains('field-changed')).toBe(true);
    });
  });

  it('renders checkbox fields with dedicated checkbox layout classes', () => {
    const { container } = render(
      <SchemaField
        field={checkboxField}
        path="legend.show"
        value={true}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    const fieldContainer = container.querySelector('[data-editor-path="legend.show"]');
    expect(fieldContainer?.classList.contains('field-checkbox')).toBe(true);
    expect(container.querySelector('.field-checkbox-main')).toBeTruthy();
    expect(container.querySelector('.field-checkbox-control')).toBeTruthy();
  });

  it('toggles checkbox when the label is clicked', () => {
    const onValueChange = vi.fn();

    render(
      <SchemaField
        field={checkboxField}
        path="legend.show"
        value={false}
        onValueChange={onValueChange}
        onResetToDefault={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText('Show Legend'));

    expect(onValueChange).toHaveBeenCalledWith('legend.show', true);
  });

  it('renders description, help text, search path, and debug metadata for checkbox fields', () => {
    render(
      <SchemaField
        field={checkboxField}
        path="legend.show"
        searchQuery="legend"
        manualTestMode
        value={true}
        onValueChange={vi.fn()}
        onResetToDefault={vi.fn()}
      />,
    );

    expect(screen.getByText((_, element) => element?.textContent === 'Display legend entries in the chart.')).toBeInTheDocument();
    expect(screen.getByText('Useful for multi-series charts.')).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === 'legend.show')).toBeInTheDocument();
    expect(screen.getByText('Path: legend.show')).toBeInTheDocument();
    expect(screen.getByText('Value: true')).toBeInTheDocument();
  });

  it('shows reset button and resets checkbox fields', () => {
    const onResetToDefault = vi.fn();

    render(
      <SchemaField
        field={checkboxField}
        path="legend.show"
        value={true}
        onValueChange={vi.fn()}
        onResetToDefault={onResetToDefault}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));

    expect(onResetToDefault).toHaveBeenCalledWith('legend.show', false);
  });
});
