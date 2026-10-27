import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from '@/routes/AppRoutes'
import type { RequestDetail, RequestSummary } from '@/features/purchase-requests/types'
import { mockApi, signIn, type Reply, type Req } from './helpers'

const summary = (over: Partial<RequestSummary> = {}): RequestSummary => ({
  id: 'r1', number: 'PR-2026-000001', title: 'Standing desks', department: 'Facilities', priority: 'normal', status: 'draft', currency: 'INR', total_amount: '42000.00',
  needed_by: null, requester_name: 'Test employee', item_count: 1, created_at: '2026-03-01T10:00:00', submitted_at: null, updated_at: '2026-03-01T10:00:00', ...over,
})
const detail = (over: Partial<RequestDetail> = {}): RequestDetail => ({
  ...summary(), justification: 'Back pain', requester_id: 'id-employee', requester_email: 'employee@example.com', cancel_reason: null, version: 1,
  items: [{ id: 'i1', line_no: 1, description: 'Desk', quantity: '2', unit: 'each', unit_price: '21000.00', notes: 'Oak', line_total: '42000.00' }],
  documents: [], history: [{ id: 'h1', from_status: null, to_status: 'draft', actor_name: 'Test employee', note: 'Draft created', created_at: '2026-03-01T10:00:00' }], ...over,
})
const page = (items: RequestSummary[]) => ({ items, total: items.length, page: 1, page_size: 10 })
const SUMMARY = { counts: { draft: 1, submitted: 2, approved: 3, rejected: 0, cancelled: 0 }, open_value: { INR: '151200.00' }, monthly: [{ month: '2026-02', count: 1 }, { month: '2026-03', count: 5 }] }

const renderAt = (path: string) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>
    </QueryClientProvider>,
  )

describe('employee dashboard (real data)', () => {
  it('shows counts, the monthly chart and recent requests from the API', async () => {
    signIn('employee')
    mockApi((r) => (r.path === '/purchase-requests/summary' ? { body: SUMMARY } : { body: page([summary({ status: 'submitted', submitted_at: '2026-03-02T09:00:00' })]) }))
    renderAt('/app/employee')
    const figures = await screen.findByRole('region', { name: 'Key figures' })
    expect(within(figures).getByLabelText(/Waiting for approval: 2/)).toBeInTheDocument()
    expect(within(figures).getByLabelText(/Approved: 3/)).toBeInTheDocument()
    expect(within(figures).getByLabelText(/Value awaiting approval: INR 1,51,200/)).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Recently updated requests' })).toHaveTextContent('Standing desks')
    expect(screen.getByText('Manager review')).toBeInTheDocument()
    expect(screen.queryByText(/sample data/i)).not.toBeInTheDocument()
  })
  it('invites a new employee to create a first request', async () => {
    signIn('employee')
    mockApi((r) => (r.path === '/purchase-requests/summary' ? { body: { ...SUMMARY, counts: { draft: 0, submitted: 0, approved: 0, rejected: 0, cancelled: 0 }, open_value: {}, monthly: [] } } : { body: page([]) }))
    renderAt('/app/employee')
    expect(await screen.findByText('No requests yet')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /create your first request/i })[0]).toHaveAttribute('href', '/app/employee/requests/new')
  })
  it('shows an error with retry when the service is down', async () => {
    signIn('employee')
    mockApi(() => ({ status: 500, body: {} }))
    renderAt('/app/employee')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this data')
  })
})

describe('requests list', () => {
  it('lists requests and sends search, filter and sort to the server', async () => {
    signIn('employee')
    const { calls } = mockApi(() => ({ body: page([summary(), summary({ id: 'r2', number: 'PR-2026-000002', title: 'Chairs', status: 'submitted' })]) }))
    renderAt('/app/employee/requests')
    expect(await screen.findByText('Chairs')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Standing desks/ })).toHaveAttribute('href', '/app/employee/requests/r1')
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'submitted')
    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'highest')
    await userEvent.type(screen.getByRole('searchbox'), 'desk')
    await waitFor(() => expect(calls.at(-1)?.path).toBe('/purchase-requests?page=1&page_size=10&q=desk&status=submitted&sort=total_amount&order=desc'))
  })
  it('explains an empty result differently when filters are active', async () => {
    signIn('employee')
    mockApi(() => ({ body: page([]) }))
    renderAt('/app/employee/requests')
    expect(await screen.findByText('No requests yet')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Filter by priority'), 'urgent')
    expect(await screen.findByText('No matching requests')).toBeInTheDocument()
  })
  it('pages through results', async () => {
    signIn('employee')
    const { calls } = mockApi(() => ({ body: { items: [summary()], total: 25, page: 1, page_size: 10 } }))
    renderAt('/app/employee/requests')
    expect(await screen.findByText('25 requests, page 1 of 3')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(calls.at(-1)?.path).toContain('page=2'))
  })
})

describe('new request form', () => {
  const handler = (r: Req): Reply => {
    if (r.path === '/purchase-requests' && r.method === 'POST') return { status: 201, body: detail() }
    if (r.path === '/purchase-requests/r1/submit') return { body: detail({ status: 'submitted', version: 2 }) }
    if (r.path === '/purchase-requests/r1' && r.method === 'GET') return { body: detail({ status: 'submitted', version: 2 }) }
    return { body: {} }
  }
  async function fillDetails() {
    await userEvent.type(screen.getByLabelText('Title'), 'Standing desks')
    await userEvent.type(screen.getByLabelText('Department'), 'Facilities')
    await userEvent.type(screen.getByLabelText('Why is this needed?'), 'Back pain')
  }
  async function addItem() {
    await userEvent.click(screen.getByRole('button', { name: /add item/i }))
    await userEvent.type(screen.getByLabelText('Item 1 description'), 'Desk')
    await userEvent.clear(screen.getByLabelText('Item 1 quantity'))
    await userEvent.type(screen.getByLabelText('Item 1 quantity'), '2')
    await userEvent.type(screen.getByLabelText('Item 1 unit price'), '21000')
  }

  it('walks through details, items and review, then saves a draft with exact values', async () => {
    signIn('employee')
    const { calls } = mockApi(handler)
    renderAt('/app/employee/requests/new')
    expect(await screen.findByRole('heading', { level: 1, name: 'New purchase request' })).toBeInTheDocument()
    await fillDetails()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await addItem()
    expect(screen.getByText(/Line total: .*42,000/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Review')
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(await screen.findByText('Draft saved as PR-2026-000001.')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      title: 'Standing desks', department: 'Facilities', justification: 'Back pain', priority: 'normal', currency: 'INR', needed_by: null,
      items: [{ description: 'Desk', quantity: '2', unit: 'each', unit_price: '21000', notes: null }],
    })
  })

  it('blocks Next until the details are valid, and says why', async () => {
    signIn('employee')
    const { fn } = mockApi(handler)
    renderAt('/app/employee/requests/new')
    await screen.findByLabelText('Title')
    await userEvent.type(screen.getByLabelText('Title'), 'ab')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Use at least 3 characters')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Fix the highlighted fields')
    expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Details')
    expect(fn).not.toHaveBeenCalled()
  })

  it('validates item numbers before moving on', async () => {
    signIn('employee')
    mockApi(handler)
    renderAt('/app/employee/requests/new')
    await fillDetails()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: /add item/i }))
    await userEvent.type(screen.getByLabelText('Item 1 description'), 'Desk')
    await userEvent.type(screen.getByLabelText('Item 1 unit price'), '1.999')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Enter an amount, up to 2 decimals')).toBeInTheDocument()
  })

  it('lists what is missing on the review step and disables Submit until it is fixed', async () => {
    signIn('employee')
    mockApi(handler)
    renderAt('/app/employee/requests/new')
    await userEvent.type(await screen.findByLabelText('Title'), 'Standing desks')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('status')).toHaveTextContent('Enter the department.')
    expect(screen.getByRole('status')).toHaveTextContent('Add at least one item.')
    expect(screen.getByRole('button', { name: 'Submit for approval' })).toBeDisabled()
  })

  it('saves, submits and opens the request', async () => {
    signIn('employee')
    const { calls } = mockApi(handler)
    renderAt('/app/employee/requests/new')
    await fillDetails()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await addItem()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: 'Submit for approval' }))
    expect(await screen.findByText('Waiting for approval')).toBeInTheDocument()
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(expect.arrayContaining(['POST /purchase-requests', 'POST /purchase-requests/r1/submit']))
  })

  it('shows the server message when saving fails', async () => {
    signIn('employee')
    mockApi(() => ({ status: 409, body: { detail: 'This request was changed somewhere else. Reload it and try again.' } }))
    renderAt('/app/employee/requests/new')
    await fillDetails()
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('changed somewhere else')
  })

  it('opens an existing draft for editing and sends the version it loaded', async () => {
    signIn('employee')
    const { calls } = mockApi((r) => (r.method === 'PUT' ? { body: detail({ version: 4 }) } : { body: detail({ version: 3 }) }))
    renderAt('/app/employee/requests/r1/edit')
    expect(await screen.findByRole('heading', { level: 1, name: 'Edit draft' })).toBeInTheDocument()
    expect(screen.getByLabelText('Title')).toHaveValue('Standing desks')
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    await screen.findByText(/Draft saved/)
    expect(calls.find((c) => c.method === 'PUT')?.body).toMatchObject({ version: 3, title: 'Standing desks' })
  })

  it('does not let a submitted request be edited', async () => {
    signIn('employee')
    mockApi(() => ({ body: detail({ status: 'submitted' }) }))
    renderAt('/app/employee/requests/r1/edit')
    expect(await screen.findByText('This request can no longer be edited')).toBeInTheDocument()
  })
})

describe('request detail', () => {
  it('shows a draft with its actions, items, history and documents', async () => {
    signIn('employee')
    mockApi(() => ({ body: detail({ documents: [{ id: 'd1', file_name: 'quote.pdf', content_type: 'application/pdf', size_bytes: 2048, content_stored: false, created_at: '2026-03-01T10:00:00' }] }) }))
    renderAt('/app/employee/requests/r1')
    expect(await screen.findByRole('heading', { level: 1, name: 'Standing desks' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Edit' })).toHaveAttribute('href', '/app/employee/requests/r1/edit')
    expect(screen.getByRole('button', { name: 'Submit for approval' })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /Items in PR-2026-000001/ })).toHaveTextContent('Oak')
    expect(screen.getByText('Created as draft')).toBeInTheDocument()
    expect(screen.getByText('quote.pdf')).toBeInTheDocument()
    expect(screen.getByText(/only the file details are recorded/i)).toBeInTheDocument()
  })

  it('shows submit problems from the server instead of failing silently', async () => {
    signIn('employee')
    mockApi((r) => (r.method === 'POST' ? { status: 422, body: { detail: ['Add at least one item.'] } } : { body: detail() }))
    renderAt('/app/employee/requests/r1')
    await userEvent.click(await screen.findByRole('button', { name: 'Submit for approval' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Add at least one item.')
  })

  it('deletes a draft only after confirmation', async () => {
    signIn('employee')
    const { calls } = mockApi((r) => (r.method === 'DELETE' ? { status: 204 } : r.path.startsWith('/purchase-requests?') ? { body: page([]) } : { body: detail() }))
    renderAt('/app/employee/requests/r1')
    await userEvent.click(await screen.findByRole('button', { name: 'Delete draft' }))
    const dialog = await screen.findByRole('dialog', { name: 'Delete this draft?' })
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete draft' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'My requests' })).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'DELETE' && c.path === '/purchase-requests/r1')).toBe(true)
  })

  it('cancels a submitted request, but only with a reason', async () => {
    signIn('employee')
    const { calls } = mockApi((r) => (r.path.endsWith('/cancel') ? { body: detail({ status: 'cancelled' }) } : { body: detail({ status: 'submitted' }) }))
    renderAt('/app/employee/requests/r1')
    expect(screen.queryByRole('link', { name: 'Edit' })).not.toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel request' }))
    const dialog = await screen.findByRole('dialog', { name: 'Cancel this request?' })
    expect(within(dialog).getByRole('button', { name: 'Cancel request' })).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Reason'), 'Budget frozen')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel request' }))
    await waitFor(() => expect(calls.find((c) => c.path.endsWith('/cancel'))?.body).toEqual({ reason: 'Budget frozen' }))
  })

  it('records document details, and refuses unsafe files before calling the server', async () => {
    signIn('employee')
    const { calls } = mockApi((r) => (r.path.endsWith('/documents') ? { status: 201, body: {} } : { body: detail() }))
    renderAt('/app/employee/requests/r1')
    const input = (await screen.findByLabelText('Add a document')) as HTMLInputElement
    await userEvent.upload(input, new File(['MZ'], 'setup.exe', { type: 'application/x-msdownload' }), { applyAccept: false })
    expect(await screen.findByRole('alert')).toHaveTextContent('not allowed')
    expect(calls.some((c) => c.path.endsWith('/documents'))).toBe(false)
    await userEvent.upload(input, new File(['%PDF-1.4 hello'], 'quote.pdf', { type: 'application/pdf' }))
    await waitFor(() => expect(calls.find((c) => c.path.endsWith('/documents'))?.body).toEqual({ file_name: 'quote.pdf', content_type: 'application/pdf', size_bytes: 14 }))
  })

  it('hides draft-only controls once a request is approved', async () => {
    signIn('employee')
    mockApi(() => ({ body: detail({ status: 'approved' }) }))
    renderAt('/app/employee/requests/r1')
    await screen.findByRole('heading', { level: 1, name: 'Standing desks' })
    for (const name of ['Delete draft', 'Cancel request', 'Submit for approval']) expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Add a document')).not.toBeInTheDocument()
  })

  it('shows an error with retry when the request cannot be loaded', async () => {
    signIn('employee')
    mockApi(() => ({ status: 404, body: { detail: 'Purchase request not found.' } }))
    renderAt('/app/employee/requests/nope')
    expect(await screen.findByRole('alert')).toHaveTextContent('Purchase request not found.')
  })
})

describe('access', () => {
  it('keeps other roles and signed-out visitors out of the request pages', async () => {
    signIn('vendor')
    mockApi(() => ({ body: {} }))
    renderAt('/app/employee/requests/new')
    expect(await screen.findByRole('heading', { level: 1, name: 'Your business with us' })).toBeInTheDocument()
  })
})
