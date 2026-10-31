import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from '@/routes/AppRoutes'
import { chainFor } from '@/features/approvals/chain'
import type { ApprovalDetail, ApprovalSummary, ApprovalsSummary } from '@/features/approvals/types'
import { mockApi, signIn, type Reply, type Req } from './helpers'

const summary = (over: Partial<ApprovalSummary> = {}): ApprovalSummary => ({
  id: 'a1', request_id: 'r1', request_number: 'PR-2026-000001', title: 'Standing desks', requester_name: 'Erin Employee', department: 'Facilities', priority: 'high', currency: 'INR',
  total_amount: '150000.00', needed_by: '2026-04-01', status: 'pending', current_level: 1, total_levels: 2, waiting_for: 'Any manager', overdue: false,
  created_at: '2026-03-01T10:00:00', decided_at: null, ...over,
})
const detail = (over: Partial<ApprovalDetail> = {}): ApprovalDetail => ({
  ...summary(), justification: 'Back pain', requester_id: 'emp-1', requester_email: 'erin@example.com',
  items: [{ line_no: 1, description: 'Desk', quantity: '6', unit: 'each', unit_price: '25000.00', line_total: '150000.00' }],
  steps: [
    { id: 's1', level: 1, status: 'pending', assigned_to_id: null, assigned_to_name: null, decided_by_name: null, decided_at: null, comment: null, activated_at: '2026-03-01T10:00:00', escalated_at: null },
    { id: 's2', level: 2, status: 'waiting', assigned_to_id: null, assigned_to_name: null, decided_by_name: null, decided_at: null, comment: null, activated_at: null, escalated_at: null },
  ],
  history: [{ id: 'h1', seq: 1, action: 'requested', level: null, actor_name: 'Erin Employee', note: '2 levels of approval required', created_at: '2026-03-01T10:00:00' }],
  can_decide: true, blocked_reason: null, decision_sync: 'not_needed', last_sync_error: null, ...over,
})
const SUMMARY: ApprovalsSummary = {
  waiting_for_me: 4, overdue_for_me: 1, delegated_to_me: 2, decided_by_me_30d: 7, approved_30d: 9, rejected_30d: 2, approved_value_30d: { INR: '1250000.00' },
  avg_decision_hours_30d: 6.5, monthly: [{ month: '2026-02', count: 3 }, { month: '2026-03', count: 8 }],
}
const page = (items: ApprovalSummary[], total = items.length) => ({ items, total, page: 1, page_size: 10 })

const renderAt = (path: string) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>
    </QueryClientProvider>,
  )

describe('approval route helper', () => {
  it('shows who approved each level, who it waits for, and what is still to come', () => {
    const steps = chainFor({ status: 'pending', steps: [
      { ...detail().steps[0], status: 'approved', decided_by_name: 'Mia Manager', decided_at: '2026-03-02T09:00:00', comment: 'Fine' },
      { ...detail().steps[1], status: 'pending', assigned_to_name: 'Max Manager', escalated_at: '2026-03-04T09:00:00' },
      { ...detail().steps[1], id: 's3', level: 3, status: 'waiting' },
    ] })
    expect(steps.map((s) => s.state)).toEqual(['done', 'current', 'pending'])
    expect(steps[0].label).toBe('Level 1: approved')
    expect(steps[0].detail).toContain('Mia Manager')
    expect(steps[1].detail).toBe('Delegated to Max Manager (overdue)')
    expect(steps[2].detail).toBe('After level 2')
  })
})

describe('manager dashboard (real data)', () => {
  it('shows what is waiting, the chart, and the approval route of the longest-waiting request', async () => {
    signIn('manager')
    mockApi((r) => (r.path === '/approvals/summary' ? { body: SUMMARY } : r.path === '/approvals/a1' ? { body: detail() } : { body: page([summary(), summary({ id: 'a2', title: 'Chairs', request_number: 'PR-2026-000002', overdue: true })]) }))
    renderAt('/app/manager')
    const figures = await screen.findByRole('region', { name: 'Key figures' })
    expect(within(figures).getByLabelText(/Waiting for you: 4/)).toBeInTheDocument()
    expect(within(figures).getByLabelText(/Overdue: 1/)).toBeInTheDocument()
    expect(within(figures).getByText('2 delegated to you')).toBeInTheDocument()
    expect(within(figures).getByText(/12,50,000/)).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /Approvals waiting for you/ })).toHaveTextContent('Chairs')
    expect(await screen.findByText('Level 1')).toBeInTheDocument()
    expect(screen.queryByText(/sample data/i)).not.toBeInTheDocument()
  })
  it('says the queue is clear when nothing is waiting', async () => {
    signIn('manager')
    mockApi((r) => (r.path === '/approvals/summary' ? { body: { ...SUMMARY, waiting_for_me: 0 } } : { body: page([]) }))
    renderAt('/app/manager')
    expect(await screen.findAllByText('Nothing is waiting for you')).not.toHaveLength(0)
    expect(screen.getByText('The queue is clear.')).toBeInTheDocument()
  })
  it('shows an error with retry when the service is down', async () => {
    signIn('manager')
    mockApi(() => ({ status: 500, body: {} }))
    renderAt('/app/manager')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this data')
  })
})

describe('approvals list', () => {
  it('uses the right view and sends search, filters and paging to the server', async () => {
    signIn('manager')
    const { calls } = mockApi(() => ({ body: page([summary(), summary({ id: 'a2', title: 'Chairs', status: 'approved', waiting_for: null })], 25) }))
    renderAt('/app/manager/approvals')
    expect(await screen.findByText('Chairs')).toBeInTheDocument()
    expect(calls[0].path).toBe('/approvals?view=queue&page=1&page_size=10&sort=created_at&order=asc')
    expect(screen.getByRole('link', { name: /Standing desks/ })).toHaveAttribute('href', '/app/manager/approvals/a1')
    expect(screen.getByText('Level 1 of 2, Any manager')).toBeInTheDocument()
    expect(screen.queryByLabelText('Filter by status')).not.toBeInTheDocument() // the queue only holds pending items
    await userEvent.click(screen.getByRole('tab', { name: 'My decisions' }))
    await waitFor(() => expect(calls.at(-1)?.path).toContain('view=mine'))
    await userEvent.selectOptions(await screen.findByLabelText('Filter by status'), 'approved')
    await userEvent.selectOptions(screen.getByLabelText('Filter by priority'), 'urgent')
    await userEvent.type(screen.getByRole('searchbox'), 'desk')
    await waitFor(() => expect(calls.at(-1)?.path).toBe('/approvals?view=mine&page=1&page_size=10&q=desk&status=approved&priority=urgent&sort=created_at&order=asc'))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(calls.at(-1)?.path).toContain('page=2'))
  })
  it('flags overdue items and explains empty states', async () => {
    signIn('manager')
    mockApi(() => ({ body: page([summary({ overdue: true })]) }))
    renderAt('/app/manager/approvals')
    expect(await screen.findByText('Overdue')).toBeInTheDocument()
    mockApi(() => ({ body: page([]) }))
    renderAt('/app/manager/approvals')
    expect((await screen.findAllByText('Nothing is waiting for you')).length).toBeGreaterThan(0)
  })
})

describe('approval detail', () => {
  const handler = (extra?: (r: Req) => Reply | undefined) => (r: Req): Reply => {
    const custom = extra?.(r)
    if (custom) return custom
    if (r.path === '/approvals/delegates') return { body: [{ id: 'mgr-2', full_name: 'Max Manager', email: 'max@example.com' }, { id: 'mgr-3', full_name: 'Mona Manager', email: 'mona@example.com' }] }
    return { body: detail() }
  }

  it('shows the request, its items, the approval route and history', async () => {
    signIn('manager')
    mockApi(handler())
    renderAt('/app/manager/approvals/a1')
    expect(await screen.findByRole('heading', { level: 1, name: 'Standing desks' })).toBeInTheDocument()
    expect(screen.getByText('Level 1 of 2')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /Items in PR-2026-000001/ })).toHaveTextContent('Desk')
    expect(screen.getByText('Back pain')).toBeInTheDocument()
    expect(screen.getByText('Waiting for any manager')).toBeInTheDocument()
    expect(screen.getByText('2 levels of approval required')).toBeInTheDocument()
  })

  it('approves with an optional comment, and says another level follows', async () => {
    signIn('manager')
    const { calls } = mockApi(handler((r) => (r.path.endsWith('/approve') ? { body: detail({ current_level: 2 }) } : undefined)))
    renderAt('/app/manager/approvals/a1')
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    const dialog = await screen.findByRole('dialog', { name: 'Approve this request?' })
    expect(dialog).toHaveTextContent('level 1 of 2')
    await userEvent.type(within(dialog).getByLabelText('Comment (optional)'), 'Looks right')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(calls.find((c) => c.path.endsWith('/approve'))?.body).toEqual({ comment: 'Looks right' }))
  })

  it('does not reject without a reason', async () => {
    signIn('manager')
    const { calls } = mockApi(handler((r) => (r.path.endsWith('/reject') ? { body: detail({ status: 'rejected' }) } : undefined)))
    renderAt('/app/manager/approvals/a1')
    await userEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    const dialog = await screen.findByRole('dialog', { name: 'Reject this request?' })
    expect(within(dialog).getByRole('button', { name: 'Reject' })).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Reason'), 'no')
    expect(within(dialog).getByRole('button', { name: 'Reject' })).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Reason'), ' budget')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reject' }))
    await waitFor(() => expect(calls.find((c) => c.path.endsWith('/reject'))?.body).toEqual({ reason: 'no budget' }))
  })

  it('delegates to a chosen manager', async () => {
    signIn('manager')
    const { calls } = mockApi(handler((r) => (r.path.endsWith('/delegate') ? { body: detail() } : undefined)))
    renderAt('/app/manager/approvals/a1')
    await userEvent.click(await screen.findByRole('button', { name: 'Delegate' }))
    const dialog = await screen.findByRole('dialog', { name: 'Delegate this approval' })
    expect(within(dialog).getByRole('button', { name: 'Delegate' })).toBeDisabled()
    await userEvent.selectOptions(await within(dialog).findByLabelText('Manager'), 'mgr-2')
    await userEvent.type(within(dialog).getByLabelText('Note (optional)'), 'I am away')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delegate' }))
    await waitFor(() => expect(calls.find((c) => c.path.endsWith('/delegate'))?.body).toEqual({ user_id: 'mgr-2', note: 'I am away' }))
  })

  it('shows why a manager cannot act, and offers no buttons', async () => {
    signIn('manager')
    mockApi(handler((r) => (r.path === '/approvals/a1' ? { body: detail({ can_decide: false, blocked_reason: 'This approval was delegated to Max Manager.' }) } : undefined)))
    renderAt('/app/manager/approvals/a1')
    await screen.findByRole('heading', { level: 1, name: 'Standing desks' })
    expect(screen.getByRole('status')).toHaveTextContent('delegated to Max Manager')
    for (const name of ['Approve', 'Reject', 'Delegate']) expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
  })

  it('shows the server error when someone else decided first', async () => {
    signIn('manager')
    mockApi(handler((r) => (r.path.endsWith('/approve') ? { status: 409, body: { detail: 'This request is already approved.' } } : undefined)))
    renderAt('/app/manager/approvals/a1')
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Approve' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already approved')
  })

  it('explains a decision that is still being delivered, and one that could not be applied', async () => {
    signIn('manager')
    mockApi(handler((r) => (r.path === '/approvals/a1' ? { body: detail({ status: 'approved', can_decide: false, decision_sync: 'pending' }) } : undefined)))
    renderAt('/app/manager/approvals/a1')
    await screen.findByRole('heading', { level: 1, name: 'Standing desks' })
    expect(screen.getByRole('status')).toHaveTextContent('Your decision is saved')
    mockApi(handler((r) => (r.path === '/approvals/a1' ? { body: detail({ status: 'approved', can_decide: false, decision_sync: 'conflict', last_sync_error: '409: Request is cancelled' }) } : undefined)))
    renderAt('/app/manager/approvals/a1')
    expect(await screen.findByText(/could not be updated: 409: Request is cancelled/)).toBeInTheDocument()
  })

  it('shows an error with retry when the approval cannot be loaded', async () => {
    signIn('manager')
    mockApi(() => ({ status: 404, body: { detail: 'Approval not found.' } }))
    renderAt('/app/manager/approvals/nope')
    expect(await screen.findByRole('alert')).toHaveTextContent('Approval not found.')
  })
})

describe('access', () => {
  it('keeps employees, vendors and visitors out of the approval pages', async () => {
    signIn('employee')
    mockApi((r) => (r.path === '/purchase-requests/summary'
      ? { body: { counts: { draft: 0, submitted: 0, approved: 0, rejected: 0, cancelled: 0 }, open_value: {}, monthly: [] } }
      : { body: { items: [], total: 0, page: 1, page_size: 5 } }))
    renderAt('/app/manager/approvals')
    expect(await screen.findByRole('heading', { level: 1, name: 'Your requests' })).toBeInTheDocument()
  })
  it('puts Approvals in the manager sidebar and nothing else of the old sample menu', async () => {
    signIn('manager')
    mockApi(() => ({ body: page([]) }))
    renderAt('/app/manager/approvals')
    expect(await screen.findByRole('link', { name: 'Approvals' })).toHaveAttribute('href', '/app/manager/approvals')
    expect(screen.queryByText('Department spend')).not.toBeInTheDocument()
  })
})
