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
});

