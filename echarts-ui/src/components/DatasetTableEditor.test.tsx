import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { DatasetTableEditor } from './DatasetTableEditor';
import type { DatasetSource } from '../utils/dataset';

const DatasetHarness = () => {
  const [source, setSource] = useState<DatasetSource>([
    ['Category', 'Value'],
    ['A', 120],
  ]);

  return <DatasetTableEditor source={source} onSourceChange={setSource} />;
};

const getBodyRowCount = (): number => {
  const table = screen.getByRole('table');
  return table.querySelectorAll('tbody tr').length;
};

describe('DatasetTableEditor', () => {
  it('edits cells and supports add/remove row and column operations', async () => {
    const user = userEvent.setup();
    render(<DatasetHarness />);

    const valueInput = screen.getByDisplayValue('120');
    await user.clear(valueInput);
    await user.type(valueInput, '130');
    expect(screen.getByDisplayValue('130')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Add row' }));
    expect(getBodyRowCount()).toBe(3);

    await user.click(screen.getByRole('button', { name: 'Add column' }));
    const headerCells = within(screen.getByRole('table')).getAllByRole('columnheader');
    expect(headerCells).toHaveLength(4); // Row + 3 dataset columns

    await user.click(screen.getByRole('button', { name: 'Remove column' }));
    const headerCellsAfterRemove = within(screen.getByRole('table')).getAllByRole('columnheader');
    expect(headerCellsAfterRemove).toHaveLength(3);

    const removeButtons = screen.getAllByRole('button', { name: 'Remove' });
    await user.click(removeButtons[0]);
    expect(getBodyRowCount()).toBe(2);
  });
});
