import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Overlay'
import { DataTable } from '@/components/tables/DataTable'
import { StatusBadge } from '@/components/ui/Badge'
import { Field } from '@/components/forms/Field'
import { ApprovalTimeline } from '@/components/ui/ApprovalTimeline'
import { mockMatchMedia } from './setup'

describe('Button', () => {
  it('fires onClick and is disabled while loading', async () => {
    const onClick = vi.fn()
    const { rerender } = render(<Button onClick={onClick}>Save</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClick).toHaveBeenCalledTimes(1)
    rerender(<Button loading onClick={onClick}>Save</Button>)
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('aria-busy', 'true')
  })
})

describe('Modal', () => {
  function Harness() {
    const [open, setOpen] = useState(false)
    return (
      <>
        <button onClick={() => setOpen(true)}>Open</button>
        <Modal open={open} onClose={() => setOpen(false)} title="Confirm">Body text</Modal>
      </>
    )
  }
  it('opens as a labelled dialog and closes on Escape (reduced motion)', async () => {
    mockMatchMedia(true)
    render(<Harness />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('Open'))
    const dialog = screen.getByRole('dialog', { name: 'Confirm' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    mockMatchMedia(false)
  })
})

describe('DataTable', () => {
  const columns = [{ key: 'id', header: 'ID' }, { key: 'status', header: 'Status', render: (r: Record<string, string | number>) => <StatusBadge status={String(r.status)} /> }]
  const rows = [{ id: 'A-1', status: 'Pending' }, { id: 'B-2', status: 'Approved' }, { id: 'C-3', status: 'Pending' }]
  it('searches, filters and shows an empty state', async () => {
    render(<DataTable caption="Test rows" columns={columns} rows={rows} filterKey="status" />)
    expect(screen.getAllByRole('row')).toHaveLength(4)
    await userEvent.type(screen.getByRole('searchbox'), 'B-2')
    expect(screen.getAllByRole('row')).toHaveLength(2)
    await userEvent.clear(screen.getByRole('searchbox'))
    await userEvent.selectOptions(screen.getByRole('combobox'), 'Pending')
    expect(screen.getAllByRole('row')).toHaveLength(3)
    await userEvent.type(screen.getByRole('searchbox'), 'zzz')
    expect(screen.getByText('No matching records')).toBeInTheDocument()
  })
  it('sorts by a column and exposes aria-sort', async () => {
    render(<DataTable caption="Test rows" columns={columns} rows={rows} />)
    await userEvent.click(screen.getByRole('button', { name: 'ID' }))
    expect(screen.getByRole('columnheader', { name: 'ID' })).toHaveAttribute('aria-sort', 'ascending')
  })
})

describe('Field', () => {
  it('links the error message to the input', () => {
    render(<Field label="Email" error="Enter a valid email address" />)
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Enter a valid email address')
  })
})

describe('ApprovalTimeline', () => {
  it('marks the current step for assistive tech', () => {
    render(<ApprovalTimeline steps={[{ label: 'A', detail: 'x', state: 'done' }, { label: 'B', detail: 'y', state: 'current' }, { label: 'C', detail: 'z', state: 'pending' }]} />)
    expect(screen.getByText('B').closest('li')).toHaveAttribute('aria-current', 'step')
  })
})
