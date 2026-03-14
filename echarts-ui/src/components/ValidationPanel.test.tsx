import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { ValidationMessage } from '../utils/validation';
import { ValidationPanel } from './ValidationPanel';

describe('ValidationPanel', () => {
  it('renders grouped severity messages and supports jump-to-field', async () => {
    const user = userEvent.setup();
    const onJumpToPath = vi.fn();
    const onApplyFix = vi.fn();

    const messages: ValidationMessage[] = [
      {
        id: 'e1',
        severity: 'error',
        message: 'Missing series type',
        path: 'series.0.type',
        section: 'series',
      },
      {
        id: 'w1',
        severity: 'warning',
        message: 'Pie should use item trigger',
        path: 'tooltip.trigger',
        section: 'tooltip',
        fixes: [
          {
            id: 'fix-tooltip-trigger',
            label: "Set tooltip.trigger to 'item'",
            kind: 'set_path',
            payload: { path: 'tooltip.trigger', value: 'item' },
          },
        ],
      },
      { id: 'i1', severity: 'info', message: 'xAxis.data and dataset both set', section: 'xAxis' },
    ];

    render(<ValidationPanel messages={messages} onJumpToPath={onJumpToPath} onApplyFix={onApplyFix} />);

    expect(screen.getByText('1 errors, 1 warnings, 1 info')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Errors' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Warnings' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Info' })).toBeInTheDocument();

    const jumpButtons = screen.getAllByRole('button', { name: 'Jump to field' });
    await user.click(jumpButtons[0]);
    expect(onJumpToPath).toHaveBeenCalledWith('series.0.type');

    await user.click(screen.getByRole('button', { name: "Set tooltip.trigger to 'item'" }));
    expect(onApplyFix).toHaveBeenCalledTimes(1);
  });

  it('shows empty-state message when there are no validation entries', () => {
    render(<ValidationPanel messages={[]} />);
    expect(screen.getByText('No obvious issues detected.')).toBeInTheDocument();
  });
});
