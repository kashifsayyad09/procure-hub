import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from '@/routes/AppRoutes'
import { NAV } from '@/components/layout/navConfig'
import { centsText, isPrice, lineCents } from '@/features/rfqs/money'
import { fromLocalInput, timeLeft, toLocalInput, unitPrice } from '@/features/rfqs/labels'
import { problemsFor } from '@/pages/vendor/QuotationFormPage'
import type { CompareQuotation, Comparison, Quotation, Rfq, RfqAction, RfqSummary, VendorRfq } from '@/features/rfqs/types'
import { mockApi, signIn, type Reply, type Req } from './helpers'

const FUTURE = new Date(Date.now() + 3 * 86_400_000).toISOString()
const PAST = new Date(Date.now() - 86_400_000).toISOString()
const summary = (over: Partial<RfqSummary> = {}): RfqSummary => ({
  id: 'r1', number: 'RFQ-2026-000001', title: 'Design team laptops', purchase_request_id: 'pr1', purchase_request_number: 'PR-2026-000001', department: 'Design', status: 'issued',
  currency: 'INR', deadline: FUTURE, deadline_passed: false, invited: 3, submitted: 1, created_by_name: 'Pat Procurement', created_at: '2026-03-01T10:00:00Z', ...over,
})
const rfq = (over: Partial<Rfq> = {}, actions: RfqAction[] = []): Rfq => ({
  ...summary(), description: 'Laptops for the team.', requirements: 'Three year warranty.', needed_by: '2026-06-01', budget_amount: '99002.00', version: 2, issued_at: '2026-03-01T10:00:00Z', closed_at: null,
  cancel_reason: null, updated_at: '2026-03-01T10:00:00Z',
  items: [{ id: 'i1', line_no: 1, description: '14-inch laptop', specification: '16 GB memory', quantity: '4.000', unit: 'each', estimated_unit_price: '24000.00' },
          { id: 'i2', line_no: 2, description: 'Laptop sleeve', specification: null, quantity: '4.000', unit: 'each', estimated_unit_price: '750.50' }],
  invitations: [{ id: 'n1', vendor_id: 'v-a', vendor_number: 'VND-1', vendor_name: 'Acme Supplies', status: 'invited', invited_by_name: 'Pat', invited_at: '2026-03-01T10:00:00Z', sent_at: '2026-03-01T10:00:00Z', responded_at: null, withdrawn_at: null, quotation_status: null },
                { id: 'n2', vendor_id: 'v-b', vendor_number: 'VND-2', vendor_name: 'Bravo Traders', status: 'invited', invited_by_name: 'Pat', invited_at: '2026-03-01T10:00:00Z', sent_at: '2026-03-01T10:00:00Z', responded_at: null, withdrawn_at: null, quotation_status: 'submitted' }],
  history: [{ id: 'h1', seq: 1, action: 'created', from_status: null, to_status: 'draft', actor_name: 'Pat Procurement', note: 'Created from PR-2026-000001', created_at: '2026-03-01T10:00:00Z' }],
  quotations_open: false, selection: null, actions, ...over,
})
const vendorRfq = (over: Partial<VendorRfq> = {}): VendorRfq => ({
  id: 'r1', number: 'RFQ-2026-000001', title: 'Design team laptops', status: 'issued', currency: 'INR', deadline: FUTURE, deadline_passed: false, invitation_status: 'invited', can_quote: true, quotation: null,
  description: 'Laptops for the team.', requirements: 'Three year warranty.', needed_by: '2026-06-01', blocked_reason: null, issued_at: '2026-03-01T10:00:00Z',
  items: [{ id: 'i1', line_no: 1, description: '14-inch laptop', specification: '16 GB memory', quantity: '4.000', unit: 'each' }, { id: 'i2', line_no: 2, description: 'Laptop sleeve', specification: null, quantity: '3.000', unit: 'each' }], ...over,
})
const quotation = (over: Partial<Quotation> = {}): Quotation => ({
  id: 'q1', number: 'QTN-2026-000001', rfq_id: 'r1', rfq_number: 'RFQ-2026-000001', rfq_title: 'Design team laptops', vendor_id: 'v-a', vendor_name: 'Acme Supplies', currency: 'INR', lead_time_days: 14,
  valid_until: '2099-01-01', payment_terms_days: 30, terms: 'Delivery included.', total_amount: '94800.00', status: 'draft', revision: 1, version: 3, submitted_at: null, updated_at: '2026-03-01T10:00:00Z',
  items: [{ rfq_item_id: 'i1', line_no: 1, quantity: '4.000', unit_price: '23000.0000', line_total: '92000.00', note: null }, { rfq_item_id: 'i2', line_no: 2, quantity: '3.000', unit_price: '700.0000', line_total: '2100.00', note: null }],
  complete: true, missing_items: [], problems: [], can_edit: true, can_submit: true, can_withdraw: false, ...over,
})
const cq = (over: Partial<CompareQuotation> = {}): CompareQuotation => ({
  id: 'q1', number: 'QTN-1', vendor_id: 'v-a', vendor_number: 'VND-1', vendor_name: 'Acme Supplies', vendor_status: 'verified', currency: 'INR', status: 'submitted', total_amount: '94800.00',
  lead_time_days: 14, valid_until: '2099-01-01', payment_terms_days: 30, terms: 'Delivery included.', submitted_at: '2026-03-02T10:00:00Z', complete: true, missing_items: [],
  lines: [{ rfq_item_id: 'i1', line_no: 1, unit_price: '23000.0000', line_total: '92000.00' }, { rfq_item_id: 'i2', line_no: 2, unit_price: '700.0000', line_total: '2800.00' }],
  scores: { price: '95.57', delivery: '100.00', compliance: null, terms: null, total: null, missing: ['compliance score', 'terms score'] }, rank: null, lowest_price: false, fastest: true,
  within_budget: true, evaluation: null, ...over,
})
const comparison = (qs: CompareQuotation[], over: Partial<Comparison> = {}): Comparison => ({
  rfq: { id: 'r1', number: 'RFQ-2026-000001', title: 'Design team laptops', status: 'closed', currency: 'INR', deadline: PAST, budget_amount: '99002.00', version: 4,
         items: rfq().items },
  currencies: [...new Set(qs.map((q) => q.currency))].sort(), mixed_currencies: false, note: null, weights: { price: 40, delivery: 20, compliance: 25, terms: 15 }, vendor_info_available: true,
  quotations: qs, selection: null, can_select: true, can_revoke: false, ...over,
})
const page = <T,>(items: T[], total = items.length) => ({ items, total, page: 1, page_size: 10 })
const COUNTS = { counts: { draft: 2, issued: 3, closed: 1, awarded: 4, cancelled: 1 }, awaiting_comparison: 2 }

const renderAt = (path: string) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>
  </QueryClientProvider>,
)
const api = (extra: (r: Req) => Reply | undefined) => mockApi((r) => extra(r) ?? (r.path === '/rfqs/summary' ? { body: COUNTS } : { status: 404, body: { detail: 'Not found' } }))

describe('helpers', () => {
  it('adds up money exactly, rounding half up to the cent', () => {
    expect(centsText(lineCents('4.000', '0.1')!)).toBe('0.40')
    expect(centsText(lineCents('3.000', '0.835')!)).toBe('2.51') // 2.505, half up
    expect(centsText(lineCents('4.000', '23000.0000')!)).toBe('92000.00')
    expect(centsText(lineCents('4.000', '33.3333')!)).toBe('133.33')
    expect(centsText(lineCents('1.500', '19.99')!)).toBe('29.99') // 29.985
    expect(lineCents('4.000', 'abc')).toBeNull()
    expect(lineCents('4.000', '1.23456')).toBeNull()
    expect(lineCents('4.000', '-1')).toBeNull()
  })
  it('accepts only well-formed prices', () => {
    for (const ok of ['0', '1', '1250.50', '0.0005', '99999999.9999']) expect(isPrice(ok)).toBe(true)
    for (const bad of ['', 'x', '1.', '.5', '1,000', '-1', '1e3', '1.23456', '123456789012']) expect(isPrice(bad)).toBe(false)
  })
  it('describes time left and converts deadlines between local and UTC', () => {
    const now = Date.parse('2026-03-01T10:00:00Z')
    expect(timeLeft('2026-03-01T09:00:00Z', now)).toBe('Deadline passed')
    expect(timeLeft('2026-03-01T10:30:00Z', now)).toBe('30 minutes left')
    expect(timeLeft('2026-03-01T13:00:00Z', now)).toBe('3 hours left')
    expect(timeLeft('2026-03-06T10:00:00Z', now)).toBe('5 days left')
    const iso = '2026-03-05T12:30:00.000Z'
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso)
    expect(unitPrice('23000.0000')).toBe('23000.00')
    expect(unitPrice('33.3333')).toBe('33.3333')
    expect(unitPrice(null)).toBe('')
  })
  it('lists what stops a quotation being submitted, like the server does', () => {
    const rfq = vendorRfq()
    const base = { currency: 'INR', lead_time_days: '14', valid_until: '2099-01-01', payment_terms_days: '', terms: '', lines: [{ rfq_item_id: 'i1', price: '5', note: '' }] }
    expect(problemsFor(base, rfq)).toEqual([])
    expect(problemsFor({ ...base, lead_time_days: '', valid_until: '', lines: [{ rfq_item_id: 'i1', price: '', note: '' }] }, rfq))
      .toEqual(['Enter the delivery lead time in days.', 'Enter how long the quotation is valid.', 'Price at least one item.'])
    expect(problemsFor({ ...base, valid_until: '2000-01-01' }, rfq)).toEqual(['The quotation must stay valid at least until the RFQ deadline.'])
  })
  it('links the menus to the real screens', () => {
    expect(NAV.procurement.find((n) => n.label === 'RFQs')?.to).toBe('/app/procurement/rfqs')
    expect(NAV.vendor.find((n) => n.label === 'RFQs and quotations')?.to).toBe('/app/vendor/rfqs')
  })
})

describe('RFQ list (procurement)', () => {
  it('shows figures and filters, searches and pages on the server', async () => {
    signIn('procurement')
    const { calls } = api((r) => (r.path.startsWith('/rfqs?') ? { body: page([summary(), summary({ id: 'r2', number: 'RFQ-2026-000002', title: 'Chairs', status: 'draft' })], 23) } : undefined))
    renderAt('/app/procurement/rfqs')
    const figures = await screen.findByRole('region', { name: 'RFQ figures' })
    expect(within(figures).getByLabelText(/Open for quotations: 3/)).toBeInTheDocument()
    expect(within(figures).getByLabelText(/Ready to compare: 2/)).toBeInTheDocument()
    expect(await screen.findByText('Chairs')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3, 23 RFQs')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'issued')
    await waitFor(() => expect(calls.some((c) => c.path.includes('status=issued') && c.path.includes('page=1'))).toBe(true))
    await userEvent.type(screen.getByLabelText('Search RFQs'), 'chairs')
    await waitFor(() => expect(calls.some((c) => c.path.includes('q=chairs'))).toBe(true))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(calls.some((c) => c.path.includes('page=2'))).toBe(true))
  })
  it('explains an empty list and an empty search differently, and offers retry on errors', async () => {
    signIn('procurement')
    api((r) => (r.path.startsWith('/rfqs?') ? { body: page([]) } : undefined))
    const first = renderAt('/app/procurement/rfqs')
    expect(await screen.findByText('No RFQs yet')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Search RFQs'), 'zzz')
    expect(await screen.findByText('No RFQs match')).toBeInTheDocument()
    first.unmount()
    api((r) => (r.path.startsWith('/rfqs?') ? { status: 500, body: {} } : undefined))
    renderAt('/app/procurement/rfqs')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server had a problem')
  })
})

describe('new RFQ', () => {
  const eligible = { items: [
    { id: 'pr1', number: 'PR-2026-000001', title: 'Design laptops', department: 'Design', priority: 'normal', currency: 'INR', total_amount: '99002.00', needed_by: '2026-06-01', decided_at: '2026-03-01T10:00:00Z', decided_by_name: 'Mia Manager', item_count: 2, rfq_id: null, rfq_number: null },
    { id: 'pr2', number: 'PR-2026-000002', title: 'Chairs', department: 'Facilities', priority: 'low', currency: 'INR', total_amount: '5000.00', needed_by: null, decided_at: null, decided_by_name: null, item_count: 1, rfq_id: 'r9', rfq_number: 'RFQ-2026-000009' }], total: 2, page: 1, page_size: 8 }

  it('offers approved requests, links to an existing RFQ instead of a second one, and creates the draft', async () => {
    signIn('procurement')
    const { calls } = api((r) => {
      if (r.path.startsWith('/rfqs/eligible-requests')) return { body: eligible }
      if (r.path === '/rfqs' && r.method === 'POST') return { status: 201, body: rfq({ status: 'draft' }, ['edit']) }
      if (r.path === '/rfqs/r1') return { body: rfq({ status: 'draft' }, ['edit']) }
    })
    renderAt('/app/procurement/rfqs/new')
    expect(await screen.findByRole('link', { name: 'Already has RFQ-2026-000009' })).toHaveAttribute('href', '/app/procurement/rfqs/r9')
    expect(screen.getAllByRole('button', { name: /Use PR-/ })).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Use PR-2026-000001' }))
    expect(await screen.findByText(/budget .*99,002/)).toBeInTheDocument()
    expect(screen.getByLabelText('Title')).toHaveValue('Design laptops')
    await userEvent.type(screen.getByLabelText('Quotation deadline'), '2099-01-01T10:00')
    await userEvent.type(screen.getByLabelText('Requirements (optional)'), 'Three year warranty.')
    await userEvent.click(screen.getByRole('button', { name: 'Create draft RFQ' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/rfqs')).toBe(true))
    const body = calls.find((c) => c.method === 'POST' && c.path === '/rfqs')!.body as Record<string, unknown>
    expect(body).toMatchObject({ purchase_request_id: 'pr1', title: 'Design laptops', requirements: 'Three year warranty.', items: [] })
    expect(body.deadline).toBe(new Date('2099-01-01T10:00').toISOString())
    expect(await screen.findByRole('heading', { level: 1, name: 'Design team laptops' })).toBeInTheDocument()
  })
  it('refuses a deadline in the past or too close, and a short title', async () => {
    signIn('procurement')
    const { calls } = api((r) => (r.path.startsWith('/rfqs/eligible-requests') ? { body: eligible } : undefined))
    renderAt('/app/procurement/rfqs/new')
    await userEvent.click(await screen.findByRole('button', { name: 'Use PR-2026-000001' }))
    await userEvent.clear(screen.getByLabelText('Title'))
    await userEvent.type(screen.getByLabelText('Title'), 'ab')
    await userEvent.type(screen.getByLabelText('Quotation deadline'), '2000-01-01T10:00')
    await userEvent.click(screen.getByRole('button', { name: 'Create draft RFQ' }))
    expect(await screen.findByText('Enter a title of at least 3 characters')).toBeInTheDocument()
    expect(screen.getByText('The deadline must be at least one hour from now')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })
  it('shows the server message if creation is refused', async () => {
    signIn('procurement')
    api((r) => (r.path.startsWith('/rfqs/eligible-requests') ? { body: eligible } : r.path === '/rfqs' ? { status: 409, body: { detail: 'PR-2026-000001 already has an RFQ in progress.' } } : undefined))
    renderAt('/app/procurement/rfqs/new')
    await userEvent.click(await screen.findByRole('button', { name: 'Use PR-2026-000001' }))
    await userEvent.type(screen.getByLabelText('Quotation deadline'), '2099-01-01T10:00')
    await userEvent.click(screen.getByRole('button', { name: 'Create draft RFQ' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already has an RFQ in progress')
  })
  it('explains when nothing is approved yet', async () => {
    signIn('procurement')
    api((r) => (r.path.startsWith('/rfqs/eligible-requests') ? { body: { items: [], total: 0, page: 1, page_size: 8 } } : undefined))
    renderAt('/app/procurement/rfqs/new')
    expect(await screen.findByText('No approved requests')).toBeInTheDocument()
  })
})

describe('RFQ detail (procurement)', () => {
  const open = (r: Rfq, extra?: (q: Req) => Reply | undefined) => {
    signIn('procurement')
    return api((q) => extra?.(q) ?? (q.path === '/rfqs/r1' ? { body: r } : q.path === '/rfqs/r1/quotations' ? { body: { quotations_open: r.quotations_open, rows: [
      { id: null, number: null, vendor_id: 'v-a', vendor_name: 'Acme Supplies', invitation_status: 'invited', status: null, submitted_at: null, currency: null, total_amount: null, lead_time_days: null },
      { id: null, number: null, vendor_id: 'v-b', vendor_name: 'Bravo Traders', invitation_status: 'invited', status: 'submitted', submitted_at: '2026-03-02T10:00:00Z', currency: null, total_amount: null, lead_time_days: null }] } } : undefined))
  }
  it('shows a sealed quotation list while bidding is open', async () => {
    open(rfq({}, ['invite', 'extend', 'close', 'cancel']))
    renderAt('/app/procurement/rfqs/r1')
    expect(await screen.findByRole('heading', { level: 1, name: 'Design team laptops' })).toBeInTheDocument()
    expect(await screen.findByText(/Prices are sealed until the deadline passes/)).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Quotations by vendor' })
    expect(within(table).getAllByText('Sealed')).toHaveLength(2) // total and lead time, for the one vendor that submitted
    expect(screen.queryByRole('link', { name: /Compare quotations/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Close early' })).toBeInTheDocument()
    expect(screen.getByText(/Budget \(internal\)/)).toBeInTheDocument()
  })
  it('offers only the actions the server allows for a draft', async () => {
    open(rfq({ status: 'draft', invitations: [] }, ['edit', 'invite', 'publish', 'cancel']))
    renderAt('/app/procurement/rfqs/r1')
    expect(await screen.findByRole('link', { name: /Edit/ })).toHaveAttribute('href', '/app/procurement/rfqs/r1/edit')
    expect(screen.getByRole('button', { name: /Issue to vendors/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Close early' })).toBeNull()
    expect(screen.getByText(/No vendors invited yet/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Quotations' })).toBeNull()
  })
  it('issues the RFQ and shows the server message if it is refused', async () => {
    const { calls } = open(rfq({ status: 'draft' }, ['publish']), (q) => (q.path === '/rfqs/r1/publish' ? { status: 422, body: { detail: ['Invite at least one vendor.'] } } : undefined))
    renderAt('/app/procurement/rfqs/r1')
    await userEvent.click(await screen.findByRole('button', { name: /Issue to vendors/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invite at least one vendor.')
    expect(calls.filter((c) => c.path === '/rfqs/r1/publish')).toHaveLength(1)
  })
  it('lets procurement compare once prices are open', async () => {
    open(rfq({ status: 'closed', quotations_open: true }, ['compare', 'select']))
    renderAt('/app/procurement/rfqs/r1')
    expect(await screen.findByRole('link', { name: /Compare quotations/ })).toHaveAttribute('href', '/app/procurement/rfqs/r1/compare')
  })
  it('needs a reason to cancel and sends the version when extending the deadline', async () => {
    const { calls } = open(rfq({}, ['extend', 'cancel']), (q) => (q.path === '/rfqs/r1/cancel' || q.path === '/rfqs/r1/extend' ? { body: rfq({}, []) } : undefined))
    renderAt('/app/procurement/rfqs/r1')
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel RFQ' }))
    const dlg = await screen.findByRole('dialog')
    const confirm = within(dlg).getByRole('button', { name: 'Cancel RFQ' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dlg).getByLabelText('Reason'), 'Scope changed')
    await userEvent.click(confirm)
    await waitFor(() => expect(calls.find((c) => c.path === '/rfqs/r1/cancel')?.body).toEqual({ reason: 'Scope changed' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Extend deadline' }))
    const d2 = await screen.findByRole('dialog')
    expect(within(d2).getByRole('button', { name: 'Extend deadline' })).toBeDisabled()
    await userEvent.type(within(d2).getByLabelText('New deadline'), '2099-02-01T10:00')
    await userEvent.click(within(d2).getByRole('button', { name: 'Extend deadline' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/rfqs/r1/extend')?.body).toEqual({ version: 2, deadline: new Date('2099-02-01T10:00').toISOString() }))
  })
  it('invites verified vendors picked from the directory and withdraws an invitation', async () => {
    const { calls } = open(rfq({ status: 'draft' }, ['invite']), (q) => {
      if (q.path.startsWith('/vendors?')) return { body: { items: [
        { id: 'v-a', number: 'VND-1', legal_name: 'Acme Supplies', trade_name: null, status: 'verified', country: 'IN', city: 'Pune', categories: [], primary_contact_name: null, primary_contact_email: null, has_account: true, created_at: '', submitted_at: null, verified_at: null },
        { id: 'v-c', number: 'VND-3', legal_name: 'Cedar Co', trade_name: null, status: 'verified', country: 'IN', city: 'Delhi', categories: [], primary_contact_name: null, primary_contact_email: null, has_account: true, created_at: '', submitted_at: null, verified_at: null }], total: 2, page: 1, page_size: 50 } }
      if (q.path === '/vendors/categories') return { body: [{ id: 'it_hardware', label: 'IT hardware' }] }
      if (q.path === '/rfqs/r1/invitations') return { status: 201, body: rfq({ status: 'draft' }, ['invite']) }
      if (q.path === '/rfqs/r1/invitations/n1/withdraw') return { body: rfq({ status: 'draft' }, ['invite']) }
    })
    renderAt('/app/procurement/rfqs/r1')
    await userEvent.click(await screen.findByRole('button', { name: /Invite vendors/ }))
    const dlg = await screen.findByRole('dialog')
    expect(await within(dlg).findByLabelText(/Cedar Co/)).toBeInTheDocument()
    expect(within(dlg).queryByLabelText(/Acme Supplies/)).toBeNull() // already invited
    expect(calls.some((c) => c.path.startsWith('/vendors?') && c.path.includes('status=verified'))).toBe(true)
    expect(within(dlg).getByRole('button', { name: /Add 0 vendors/ })).toBeDisabled()
    await userEvent.click(within(dlg).getByLabelText(/Cedar Co/))
    await userEvent.click(within(dlg).getByRole('button', { name: 'Add 1 vendor' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/rfqs/r1/invitations')?.body).toEqual({ vendor_ids: ['v-c'] }))
    await userEvent.click(await screen.findByRole('button', { name: 'Withdraw invitation to Acme Supplies' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/rfqs/r1/invitations/n1/withdraw')).toBe(true))
  })
  it('does not offer to withdraw an invitation after the vendor submitted', async () => {
    open(rfq({ status: 'issued' }, ['invite']))
    renderAt('/app/procurement/rfqs/r1')
    expect(await screen.findByRole('button', { name: 'Withdraw invitation to Acme Supplies' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Withdraw invitation to Bravo Traders' })).toBeNull()
  })
  it('shows the award, and the cancel reason for a cancelled RFQ', async () => {
    open(rfq({ status: 'awarded', selection: { id: 's1', seq: 1, quotation_id: 'q1', vendor_id: 'v-a', vendor_name: 'Acme Supplies', status: 'awarded', justification: 'Best score.', acknowledged_missing_items: false, currency: 'INR', total_amount: '94800.00', selected_by_name: 'Pat Procurement', selected_at: '2026-03-05T10:00:00Z', revoked_by_name: null, revoked_at: null, revoke_reason: null } }, ['compare', 'revoke']))
    renderAt('/app/procurement/rfqs/r1')
    expect(await screen.findByRole('heading', { name: 'Awarded to Acme Supplies' })).toBeInTheDocument()
    expect(screen.getByText('Best score.')).toBeInTheDocument()
  })
  it('shows an error state when the RFQ cannot be opened', async () => {
    signIn('procurement')
    api((q) => (q.path === '/rfqs/r1' ? { status: 404, body: { detail: 'RFQ not found.' } } : undefined))
    renderAt('/app/procurement/rfqs/r1')
    expect(await screen.findByRole('alert')).toHaveTextContent('RFQ not found.')
  })
  it('edits a draft with the version it was loaded at', async () => {
    signIn('procurement')
    const draft = rfq({ status: 'draft', deadline: '2099-03-01T10:00:00Z' }, ['edit'])
    const { calls } = api((q) => (q.path === '/rfqs/r1' && q.method === 'GET' ? { body: draft } : q.path === '/rfqs/r1' && q.method === 'PUT' ? { body: draft } : undefined))
    renderAt('/app/procurement/rfqs/r1/edit')
    const title = await screen.findByLabelText('Title')
    await userEvent.clear(title)
    await userEvent.type(title, 'Revised title')
    await userEvent.type(screen.getByLabelText('Item 2 specification (optional)'), 'Padded')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')!.body).toMatchObject({ version: 2, title: 'Revised title', items: [{ line_no: 1, specification: '16 GB memory' }, { line_no: 2, specification: 'Padded' }] })
  })
  it('does not offer the edit form for an issued RFQ', async () => {
    open(rfq({}, ['close']))
    renderAt('/app/procurement/rfqs/r1/edit')
    expect(await screen.findByRole('alert')).toHaveTextContent('Only a draft RFQ can be edited')
  })
})

describe('comparison (procurement)', () => {
  const A = cq()
  const B = cq({ id: 'q2', vendor_id: 'v-b', vendor_name: 'Bravo Traders', total_amount: '90600.00', lead_time_days: 21, lowest_price: true, fastest: false, scores: { price: '100.00', delivery: '66.67', compliance: null, terms: null, total: null, missing: [] } })
  const C = cq({ id: 'q3', vendor_id: 'v-c', vendor_name: 'Cedar Co', total_amount: '96000.00', lead_time_days: 7, complete: false, missing_items: [2], within_budget: null, vendor_status: 'suspended', fastest: false,
    lines: [{ rfq_item_id: 'i1', line_no: 1, unit_price: '24000.0000', line_total: '96000.00' }, { rfq_item_id: 'i2', line_no: 2, unit_price: null, line_total: null }],
    scores: { price: null, delivery: null, compliance: null, terms: null, total: null, missing: ['Some items are not quoted'] } })
  const open = (c: Comparison, extra?: (q: Req) => Reply | undefined) => {
    signIn('procurement')
    return api((q) => extra?.(q) ?? (q.path === '/rfqs/r1/comparison' ? { body: c } : q.path === '/rfqs/r1/selection/history' ? { body: { items: [] } } : undefined))
  }

  it('compares side by side with exact totals, differences, missing items and vendor status', async () => {
    open(comparison([A, B, C]))
    renderAt('/app/procurement/rfqs/r1/compare')
    const table = await screen.findByRole('table', { name: /comparison of quotations in INR/ })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('Acme Supplies'), expect.stringContaining('Bravo Traders'), expect.stringContaining('Cedar Co')]))
    expect(within(table).getByText(/90,600/)).toBeInTheDocument()
    expect(within(table).getByText('Lowest price')).toBeInTheDocument()
    expect(within(table).getByText('Fastest')).toBeInTheDocument()
    expect(within(table).getByText('Not quoted')).toBeInTheDocument()
    expect(within(table).getByText('Partial: some items not quoted')).toBeInTheDocument()
    expect(within(table).getByText('Suspended')).toBeInTheDocument()
    expect(within(table).getAllByText('Within budget')).toHaveLength(2)
    expect(within(table).getAllByText('Calculated')).toHaveLength(2)
    expect(within(table).getAllByText('Entered by the evaluator')).toHaveLength(2)
    expect(screen.getByText(/The overall score appears once both evaluator scores are entered/)).toBeInTheDocument()
  })
  it('keeps currencies apart and says nothing is converted', async () => {
    const usd = cq({ id: 'q4', vendor_name: 'Delta Inc', currency: 'USD', total_amount: '1032.00', within_budget: null })
    open(comparison([A, usd], { mixed_currencies: true, currencies: ['INR', 'USD'], note: 'These quotations are in more than one currency. Prices are compared only within the same currency; nothing is converted.' }))
    renderAt('/app/procurement/rfqs/r1/compare')
    expect(await screen.findByRole('note')).toHaveTextContent('nothing is converted')
    expect(screen.getByRole('table', { name: /quotations in INR/ })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /quotations in USD/ })).toBeInTheDocument()
    expect(screen.getByText(/not compared with it/)).toBeInTheDocument()
  })
  it('sorts and filters', async () => {
    open(comparison([A, B, C]))
    renderAt('/app/procurement/rfqs/r1/compare')
    const names = () => within(screen.getByRole('table')).getAllByRole('columnheader').slice(1).map((h) => h.querySelector('span')?.textContent)
    await screen.findByRole('table')
    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'price')
    expect(names()).toEqual(['Bravo Traders', 'Acme Supplies', 'Cedar Co'])
    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'delivery')
    expect(names()).toEqual(['Cedar Co', 'Acme Supplies', 'Bravo Traders'])
    await userEvent.click(screen.getByLabelText('Complete quotations only'))
    expect(names()).not.toContain('Cedar Co')
    await userEvent.click(screen.getByLabelText('Verified vendors only'))
    expect(names()).toEqual(['Acme Supplies', 'Bravo Traders'])
  })
  it('explains that prices are sealed instead of showing an empty page', async () => {
    signIn('procurement')
    api((q) => (q.path === '/rfqs/r1/comparison' ? { status: 409, body: { detail: 'Quotations stay sealed until the deadline passes or the RFQ is closed.' } } : undefined))
    renderAt('/app/procurement/rfqs/r1/compare')
    expect(await screen.findByRole('alert')).toHaveTextContent('Quotations are not open yet')
    expect(screen.getByText(/stay sealed until the deadline passes/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
  })
  it('says so when nobody quoted, and warns if vendor status could not be checked', async () => {
    const first = open(comparison([]))
    expect(first.calls).toBeDefined()
    renderAt('/app/procurement/rfqs/r1/compare')
    expect(await screen.findByText('No quotations were submitted for this RFQ.')).toBeInTheDocument()
  })
  it('warns when vendor status could not be checked', async () => {
    open(comparison([cq({ vendor_status: null })], { vendor_info_available: false }))
    renderAt('/app/procurement/rfqs/r1/compare')
    expect(await screen.findByText(/Vendor status could not be checked just now/)).toBeInTheDocument()
    expect(screen.getByText('Could not be checked')).toBeInTheDocument()
  })
  it('records an evaluation with reasons, using the version it was loaded at', async () => {
    const withEval = cq({ evaluation: { compliance_score: 5, compliance_note: 'Mostly meets it.', terms_score: null, terms_note: null, evaluator_name: 'Pat', version: 3, updated_at: '' } })
    const { calls } = open(comparison([withEval]), (q) => (q.path === '/rfqs/r1/evaluations/q1' ? { body: {} } : undefined))
    renderAt('/app/procurement/rfqs/r1/compare')
    await userEvent.click(await screen.findByRole('button', { name: 'Evaluate Acme Supplies' }) )
    const dlg = await screen.findByRole('dialog')
    expect(within(dlg).getByLabelText('Compliance with the requirements')).toHaveValue('5')
    await userEvent.selectOptions(within(dlg).getByLabelText('Commercial terms'), '8')
    const save = within(dlg).getByRole('button', { name: 'Save evaluation' })
    expect(save).toBeDisabled() // a score needs a reason
    expect(within(dlg).getByRole('status')).toHaveTextContent('Say why you gave the commercial terms score.')
    await userEvent.type(within(dlg).getByLabelText('Why this terms score'), 'Net 30, delivery included.')
    await userEvent.click(save)
    await waitFor(() => expect(calls.find((c) => c.path === '/rfqs/r1/evaluations/q1')?.body).toEqual({ compliance_score: 5, compliance_note: 'Mostly meets it.', terms_score: 8, terms_note: 'Net 30, delivery included.', version: 3 }))
  })
  it('does not let an empty evaluation be saved', async () => {
    open(comparison([A]))
    renderAt('/app/procurement/rfqs/r1/compare')
    await userEvent.click(await screen.findByRole('button', { name: 'Evaluate Acme Supplies' }))
    const dlg = await screen.findByRole('dialog')
    expect(within(dlg).getByRole('button', { name: 'Save evaluation' })).toBeDisabled()
    expect(within(dlg).getByRole('status')).toHaveTextContent('Enter at least one score.')
  })
  it('needs a justification to select, and an explicit acknowledgement for missing items', async () => {
    const { calls } = open(comparison([A, C]), (q) => (q.path === '/rfqs/r1/selection' ? { body: {} } : undefined))
    renderAt('/app/procurement/rfqs/r1/compare')
    await userEvent.click(await screen.findByRole('button', { name: 'Select Cedar Co' }))
    let dlg = await screen.findByRole('dialog')
    const confirm = within(dlg).getByRole('button', { name: 'Select supplier' })
    await userEvent.type(within(dlg).getByLabelText('Why this supplier'), 'Fastest delivery by far.')
    expect(confirm).toBeDisabled() // not acknowledged yet
    await userEvent.click(within(dlg).getByLabelText(/I accept that item 2 is not quoted/))
    expect(confirm).toBeEnabled()
    await userEvent.click(confirm)
    await waitFor(() => expect(calls.find((c) => c.path === '/rfqs/r1/selection')?.body).toEqual({ quotation_id: 'q3', justification: 'Fastest delivery by far.', acknowledge_missing_items: true }))
    await userEvent.click(await screen.findByRole('button', { name: 'Select Acme Supplies' }))
    dlg = (await screen.findAllByRole('dialog')).at(-1)!
    expect(within(dlg).queryByLabelText(/I accept that/)).toBeNull()
    await userEvent.type(within(dlg).getByLabelText('Why this supplier'), 'short')
    expect(within(dlg).getByRole('button', { name: 'Select supplier' })).toBeDisabled()
  })
  it('shows the server message if the selection is refused', async () => {
    open(comparison([A]), (q) => (q.path === '/rfqs/r1/selection' ? { status: 409, body: { detail: 'Acme Supplies is suspended in the vendor directory and cannot be awarded an order.' } } : undefined))
    renderAt('/app/procurement/rfqs/r1/compare')
    await userEvent.click(await screen.findByRole('button', { name: 'Select Acme Supplies' }))
    const dlg = await screen.findByRole('dialog')
    await userEvent.type(within(dlg).getByLabelText('Why this supplier'), 'Best overall balance.')
    await userEvent.click(within(dlg).getByRole('button', { name: 'Select supplier' }))
    expect(await within(dlg).findByRole('alert')).toHaveTextContent('cannot be awarded an order')
  })
  it('shows the award, hides select buttons, and revokes with a reason', async () => {
    const sel = { id: 's1', seq: 1, quotation_id: 'q1', vendor_id: 'v-a', vendor_name: 'Acme Supplies', status: 'awarded' as const, justification: 'Best score.', acknowledged_missing_items: false, currency: 'INR', total_amount: '94800.00', selected_by_name: 'Pat Procurement', selected_at: '2026-03-05T10:00:00Z', revoked_by_name: null, revoked_at: null, revoke_reason: null }
    const { calls } = open(comparison([cq({ status: 'selected' })], { selection: sel, can_select: false, can_revoke: true }), (q) => (q.path === '/rfqs/r1/selection/revoke' ? { body: {} } : q.path === '/rfqs/r1/selection/history' ? { body: { items: [{ ...sel, id: 's0', seq: 0, status: 'revoked', revoked_by_name: 'Pat', revoked_at: '2026-03-04T10:00:00Z', revoke_reason: 'Vendor withdrew.' }, sel] } } : undefined))
    renderAt('/app/procurement/rfqs/r1/compare')
    expect(await screen.findByRole('heading', { name: 'Awarded to Acme Supplies' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Select Acme/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Evaluate Acme/ })).toBeNull()
    expect(await screen.findByText(/Revoked by Pat/)).toHaveTextContent('Vendor withdrew.')
    await userEvent.click(screen.getByRole('button', { name: 'Revoke award' }))
    const dlg = await screen.findByRole('dialog')
    const confirm = within(dlg).getByRole('button', { name: 'Revoke award' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dlg).getByLabelText('Reason'), 'Vendor could not confirm stock.')
    await userEvent.click(confirm)
    await waitFor(() => expect(calls.find((c) => c.path === '/rfqs/r1/selection/revoke')?.body).toEqual({ reason: 'Vendor could not confirm stock.' }))
  })
})

describe('vendor: invited RFQs', () => {
  it('invites an unregistered vendor user to register first', async () => {
    signIn('vendor')
    api((q) => (q.path.startsWith('/rfqs/invited') ? { status: 403, body: { detail: 'Register your vendor profile first.' } } : undefined))
    renderAt('/app/vendor/rfqs')
    expect(await screen.findByText('Register your company first')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open your profile' })).toHaveAttribute('href', '/app/vendor/profile')
  })
  it('lists invitations with what to do next', async () => {
    signIn('vendor')
    const base = vendorRfq()
    api((q) => (q.path.startsWith('/rfqs/invited?') ? { body: page([
      { ...base },
      { ...base, id: 'r2', number: 'RFQ-2026-000002', title: 'Chairs', status: 'awarded' as const, can_quote: false, invitation_status: 'invited' as const, quotation: { id: 'q9', number: 'QTN-9', status: 'selected' as const, total_amount: '5000.00', currency: 'INR', updated_at: '' } },
      { ...base, id: 'r3', number: 'RFQ-2026-000003', title: 'Desks', can_quote: false, invitation_status: 'declined' as const }]) } : undefined))
    renderAt('/app/vendor/rfqs')
    expect(await screen.findByRole('link', { name: 'Design team laptops' })).toHaveAttribute('href', '/app/vendor/rfqs/r1')
    expect(screen.getByText('Waiting for your quotation')).toBeInTheDocument()
    expect(screen.getByText('Selected')).toBeInTheDocument()
    expect(screen.getByText('Declined')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open and quote' })).toBeInTheDocument()
  })
  it('explains an empty list and offers retry on errors', async () => {
    signIn('vendor')
    api((q) => (q.path.startsWith('/rfqs/invited?') ? { body: page([]) } : undefined))
    const first = renderAt('/app/vendor/rfqs')
    expect(await screen.findByText('No invitations yet')).toBeInTheDocument()
    first.unmount()
    api((q) => (q.path.startsWith('/rfqs/invited?') ? { status: 500, body: {} } : undefined))
    renderAt('/app/vendor/rfqs')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server had a problem')
  })
})

describe('vendor: RFQ detail', () => {
  const open = (r: VendorRfq, q?: Quotation, extra?: (x: Req) => Reply | undefined) => {
    signIn('vendor')
    return api((x) => extra?.(x) ?? (x.path === '/rfqs/invited/r1' ? { body: r } : x.path === '/quotations/q1' && q ? { body: q } : undefined))
  }
  it('shows what the buyer needs, never the budget, and lets the vendor start or decline', async () => {
    const { calls } = open(vendorRfq(), undefined, (x) => (x.path === '/rfqs/invited/r1/decline' ? { body: vendorRfq({ invitation_status: 'declined', can_quote: false }) } : x.path === '/rfqs/invited/r1' ? { body: vendorRfq() } : undefined))
    renderAt('/app/vendor/rfqs/r1')
    expect(await screen.findByRole('link', { name: 'Start a quotation' })).toHaveAttribute('href', '/app/vendor/rfqs/r1/quote')
    expect(screen.getByText('Three year warranty.')).toBeInTheDocument()
    expect(screen.getByText('16 GB memory')).toBeInTheDocument()
    expect(screen.queryByText(/budget/i)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Decline to quote' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Decline' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/rfqs/invited/r1/decline' && c.method === 'POST')).toBe(true))
  })
  it('shows why a vendor cannot quote', async () => {
    open(vendorRfq({ can_quote: false, deadline_passed: true, blocked_reason: 'The deadline has passed. This RFQ is no longer taking quotations.' }))
    renderAt('/app/vendor/rfqs/r1')
    expect(await screen.findByText('The deadline has passed. This RFQ is no longer taking quotations.')).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('link', { name: 'Start a quotation' })).toBeNull()
  })
  it('shows what is still missing from a draft and lets the vendor continue it', async () => {
    open(vendorRfq({ quotation: { id: 'q1', number: 'QTN-1', status: 'draft', total_amount: '0.00', currency: 'INR', updated_at: '' } }), quotation({ problems: ['Enter the delivery lead time in days.'], can_submit: false }))
    renderAt('/app/vendor/rfqs/r1')
    expect(await screen.findByRole('list', { name: 'Still needed before you can submit' })).toHaveTextContent('Enter the delivery lead time in days.')
    expect(screen.getByRole('link', { name: 'Edit and submit' })).toBeInTheDocument()
  })
  it('lets a vendor withdraw a submitted quotation before the deadline', async () => {
    const { calls } = open(vendorRfq({ quotation: { id: 'q1', number: 'QTN-1', status: 'submitted', total_amount: '94800.00', currency: 'INR', updated_at: '' } }),
      quotation({ status: 'submitted', can_edit: false, can_withdraw: true, submitted_at: '2026-03-02T10:00:00Z' }), (x) => (x.path === '/quotations/q1/withdraw' ? { body: quotation() } : undefined))
    renderAt('/app/vendor/rfqs/r1')
    expect(await screen.findByText(/Buyers cannot see your prices until the deadline passes/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Withdraw to make changes' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/quotations/q1/withdraw' && c.method === 'POST')).toBe(true))
  })
  it('tells the vendor the outcome of their own quotation', async () => {
    open(vendorRfq({ status: 'awarded', can_quote: false, quotation: { id: 'q1', number: 'QTN-1', status: 'selected', total_amount: '94800.00', currency: 'INR', updated_at: '' } }), quotation({ status: 'selected', can_edit: false }))
    renderAt('/app/vendor/rfqs/r1')
    expect(await screen.findByRole('note')).toHaveTextContent('your quotation was selected')
  })
  it('shows the server message when a vendor action is refused', async () => {
    open(vendorRfq({ quotation: { id: 'q1', number: 'QTN-1', status: 'submitted', total_amount: '1.00', currency: 'INR', updated_at: '' } }), quotation({ status: 'submitted', can_edit: false, can_withdraw: true }),
      (x) => (x.path === '/quotations/q1/withdraw' ? { status: 409, body: { detail: 'The deadline has passed. This RFQ is no longer taking quotations.' } } : undefined))
    renderAt('/app/vendor/rfqs/r1')
    await userEvent.click(await screen.findByRole('button', { name: 'Withdraw to make changes' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('deadline has passed')
  })
  it('gives a 404 for an RFQ the vendor was not invited to', async () => {
    signIn('vendor')
    api((x) => (x.path === '/rfqs/invited/r1' ? { status: 404, body: { detail: 'RFQ not found.' } } : undefined))
    renderAt('/app/vendor/rfqs/r1')
    expect(await screen.findByRole('alert')).toHaveTextContent('RFQ not found.')
  })
})

describe('vendor: quotation form', () => {
  const rfq1 = vendorRfq()
  it('previews exact totals while typing and saves a draft with the right body', async () => {
    signIn('vendor')
    const { calls } = api((x) => (x.path === '/rfqs/invited/r1' ? { body: rfq1 } : x.path === '/quotations' && x.method === 'POST' ? { status: 201, body: quotation() } : undefined))
    renderAt('/app/vendor/rfqs/r1/quote')
    await userEvent.type(await screen.findByLabelText('Unit price for item 1'), '23000')
    await userEvent.type(screen.getByLabelText('Unit price for item 2'), '0.835')
    expect(screen.getByText(/Total: .*92,002\.51/)).toBeInTheDocument() // 4 x 23000 + 3 x 0.835 (2.505 rounds half up)
    expect(screen.getByText(/This total is a preview/)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Delivery lead time (days)'), '14')
    await userEvent.type(screen.getByLabelText('Quotation valid until'), '2099-01-01')
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/quotations')).toBe(true))
    expect(calls.find((c) => c.path === '/quotations')!.body).toEqual({
      rfq_id: 'r1', currency: 'INR', lead_time_days: 14, valid_until: '2099-01-01', payment_terms_days: null, terms: '',
      items: [{ rfq_item_id: 'i1', unit_price: '23000', note: null }, { rfq_item_id: 'i2', unit_price: '0.835', note: null }],
    })
    expect(calls.some((c) => c.path.endsWith('/submit'))).toBe(false)
  })
  it('keeps submit disabled until the quotation is complete, and shows what is missing', async () => {
    signIn('vendor')
    api((x) => (x.path === '/rfqs/invited/r1' ? { body: rfq1 } : undefined))
    renderAt('/app/vendor/rfqs/r1/quote')
    const submit = await screen.findByRole('button', { name: 'Submit quotation' })
    expect(submit).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Enter the delivery lead time in days.')
    expect(screen.getByRole('status')).toHaveTextContent('Price at least one item.')
  })
  it('rejects malformed prices, lead times and over-long text', async () => {
    signIn('vendor')
    const { calls } = api((x) => (x.path === '/rfqs/invited/r1' ? { body: rfq1 } : undefined))
    renderAt('/app/vendor/rfqs/r1/quote')
    await userEvent.type(await screen.findByLabelText('Unit price for item 1'), '1.23456')
    await userEvent.type(screen.getByLabelText('Delivery lead time (days)'), '0')
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(await screen.findByText('Enter a price with up to 4 decimals, for example 1250.50')).toBeInTheDocument()
    expect(screen.getByText('Enter a whole number of days from 1 to 730')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Fix the highlighted fields first.')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })
  it('saves and submits in one go for a complete quotation, then returns to the request', async () => {
    signIn('vendor')
    const { calls } = api((x) => {
      if (x.path === '/rfqs/invited/r1') return { body: rfq1 }
      if (x.path === '/quotations' && x.method === 'POST') return { status: 201, body: quotation() }
      if (x.path === '/quotations/q1/submit') return { body: quotation({ status: 'submitted' }) }
    })
    renderAt('/app/vendor/rfqs/r1/quote')
    await userEvent.type(await screen.findByLabelText('Unit price for item 1'), '23000.50')
    await userEvent.type(screen.getByLabelText('Delivery lead time (days)'), '14')
    await userEvent.type(screen.getByLabelText('Quotation valid until'), '2099-01-01')
    await userEvent.click(screen.getByRole('button', { name: 'Submit quotation' }))
    await waitFor(() => expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(expect.arrayContaining(['POST /quotations', 'POST /quotations/q1/submit'])))
    expect(await screen.findByRole('heading', { level: 1, name: 'Design team laptops' })).toBeInTheDocument()
  })
  it('edits an existing draft with its version and leaves an item empty as not quoted', async () => {
    signIn('vendor')
    const withQuote = vendorRfq({ quotation: { id: 'q1', number: 'QTN-1', status: 'draft', total_amount: '94800.00', currency: 'INR', updated_at: '' } })
    const { calls } = api((x) => (x.path === '/rfqs/invited/r1' ? { body: withQuote } : x.path === '/quotations/q1' && x.method === 'GET' ? { body: quotation() } : x.path === '/quotations/q1' && x.method === 'PUT' ? { body: quotation() } : undefined))
    renderAt('/app/vendor/rfqs/r1/quote')
    const price2 = await screen.findByLabelText('Unit price for item 2')
    expect(price2).toHaveValue('700.00')
    await userEvent.clear(price2)
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')!.body).toMatchObject({ version: 3, items: [{ rfq_item_id: 'i1', unit_price: '23000.00' }, { rfq_item_id: 'i2', unit_price: null }] })
  })
  it('shows a submitted quotation read-only and a refused vendor why', async () => {
    signIn('vendor')
    const first = api((x) => (x.path === '/rfqs/invited/r1' ? { body: vendorRfq({ quotation: { id: 'q1', number: 'QTN-1', status: 'submitted', total_amount: '94800.00', currency: 'INR', updated_at: '' } }) } : x.path === '/quotations/q1' ? { body: quotation({ status: 'submitted', can_edit: false, can_withdraw: true }) } : undefined))
    const view = renderAt('/app/vendor/rfqs/r1/quote')
    expect(await screen.findByText(/This quotation is submitted/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save draft' })).toBeNull()
    expect(screen.getByText('Delivery included.')).toBeInTheDocument()
    view.unmount(); first.fn.mockReset()
    api((x) => (x.path === '/rfqs/invited/r1' ? { body: vendorRfq({ can_quote: false, blocked_reason: 'Your vendor profile is not verified, so you cannot send quotations.' }) } : undefined))
    renderAt('/app/vendor/rfqs/r1/quote')
    expect(await screen.findByRole('alert')).toHaveTextContent('not verified')
  })
  it('shows the server message if a save is refused', async () => {
    signIn('vendor')
    api((x) => (x.path === '/rfqs/invited/r1' ? { body: rfq1 } : x.path === '/quotations' ? { status: 409, body: { detail: 'The deadline has passed. This RFQ is no longer taking quotations.' } } : undefined))
    renderAt('/app/vendor/rfqs/r1/quote')
    await userEvent.type(await screen.findByLabelText('Unit price for item 1'), '5')
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('deadline has passed')
  })
})

describe('access', () => {
  it.each(['employee', 'manager', 'finance', 'admin', 'vendor'] as const)('keeps %s out of the procurement RFQ pages', async (role) => {
    signIn(role)
    api(() => ({ status: 404, body: { detail: 'none' } }))
    renderAt('/app/procurement/rfqs')
    await waitFor(() => expect(screen.queryByRole('region', { name: 'RFQ figures' })).toBeNull())
    expect(screen.queryByLabelText('Search RFQs')).toBeNull()
  })
  it.each(['employee', 'manager', 'finance', 'admin', 'procurement'] as const)('keeps %s out of the vendor RFQ pages', async (role) => {
    signIn(role)
    api(() => ({ status: 404, body: { detail: 'none' } }))
    renderAt('/app/vendor/rfqs')
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Requests for quotation' })).toBeNull())
  })
})
