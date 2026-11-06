import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from '@/routes/AppRoutes'
import { NAV } from '@/components/layout/navConfig'
import { formSchema, submitProblems, toInput, fromDetail } from '@/features/vendors/VendorForm'
import type { VendorAction, VendorDetail, VendorSummary, VendorsSummary } from '@/features/vendors/types'
import { mockApi, signIn, type Reply, type Req } from './helpers'

const CATS = [{ id: 'it_hardware', label: 'IT hardware' }, { id: 'software', label: 'Software and licences' }, { id: 'furniture', label: 'Furniture' }]
const summary = (over: Partial<VendorSummary> = {}): VendorSummary => ({
  id: 'v1', number: 'VND-2026-000001', legal_name: 'Acme Supplies Pvt Ltd', trade_name: 'Acme', status: 'pending', country: 'IN', city: 'Bengaluru', categories: ['it_hardware'],
  primary_contact_name: 'Vera Vendor', primary_contact_email: 'vera@acme.example', has_account: true, created_at: '2026-03-01T10:00:00', submitted_at: '2026-03-02T10:00:00', verified_at: null, ...over,
})
const detail = (over: Partial<VendorDetail> = {}, actions: VendorAction[] = ['edit']): VendorDetail => ({
  ...summary(), tax_id: '29ABCDE1234F1Z5', registration_number: null, website: 'https://acme.example', description: 'Office and IT supplies.', address_line1: '12 Industrial Layout', address_line2: null,
  state: 'Karnataka', postal_code: '560058', payment_terms_days: 30, currency: 'INR', status_note: null, verified_by_name: null, created_by_name: 'Vera Vendor', version: 3, updated_at: '2026-03-02T10:00:00',
  contacts: [{ id: 'c1', name: 'Vera Vendor', job_title: 'Sales lead', email: 'vera@acme.example', phone: null, is_primary: true }],
  history: [{ id: 'h1', seq: 1, action: 'created', from_status: null, to_status: 'draft', actor_name: 'Vera Vendor', note: 'Registered by the vendor', created_at: '2026-03-01T10:00:00' }],
  completeness: { percent: 100, missing: [] }, actions, blocked_reason: null, ...over,
})
const SUMMARY: VendorsSummary = { counts: { draft: 2, pending: 3, verified: 9, rejected: 1, suspended: 1 }, verified_by_category: [{ category: 'it_hardware', count: 4 }], monthly: [{ month: '2026-03', count: 5 }] }
const page = (items: VendorSummary[], total = items.length) => ({ items, total, page: 1, page_size: 10 })

const renderAt = (path: string) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>
  </QueryClientProvider>,
)
const api = (extra: (r: Req) => Reply | undefined) => mockApi((r) => extra(r) ?? (r.path === '/vendors/categories' ? { body: CATS } : r.path === '/vendors/summary' ? { body: SUMMARY } : { status: 404, body: { detail: 'Not found' } }))

describe('navigation', () => {
  it('links the vendor, procurement and admin menus to the real vendor screens', () => {
    expect(NAV.vendor.find((n) => n.label === 'Profile')?.to).toBe('/app/vendor/profile')
    expect(NAV.procurement.find((n) => n.label === 'Vendors')?.to).toBe('/app/procurement/vendors')
    expect(NAV.admin.find((n) => n.label === 'Vendors')?.to).toBe('/app/admin/vendors')
  })
})

describe('form rules', () => {
  const base = fromDetail(detail())
  it('accepts a complete profile and builds the request with exactly one primary contact', () => {
    expect(formSchema.safeParse(base).success).toBe(true)
    const two = { ...base, contacts: [...base.contacts, { name: 'Second', job_title: '', email: 'second@acme.example', phone: '' }], primary: 1 }
    const input = toInput(two)
    expect(input.contacts.map((c) => c.is_primary)).toEqual([false, true])
    expect(input.registration_number).toBeNull()
    expect(input.contacts[1].phone).toBeNull()
  })
  it.each([
    ['legal_name', 'A'], ['tax_id', 'ab'], ['website', 'acme.example'], ['website', 'javascript:alert(1)'],
  ])('rejects a bad %s (%s)', (field, value) => {
    expect(formSchema.safeParse({ ...base, [field]: value }).success).toBe(false)
  })
  it('rejects bad contact details', () => {
    const bad = (c: Partial<(typeof base.contacts)[0]>) => formSchema.safeParse({ ...base, contacts: [{ ...base.contacts[0], ...c }] }).success
    expect(bad({ email: 'nope' })).toBe(false); expect(bad({ phone: 'abc' })).toBe(false); expect(bad({ name: ' ' })).toBe(false); expect(bad({})).toBe(true)
  })
  it('lists what is missing before submission, like the server does', () => {
    expect(submitProblems(base)).toEqual([])
    expect(submitProblems({ ...base, tax_id: '', city: '', categories: [], contacts: [] })).toEqual(['Enter the tax ID.', 'Enter the city.', 'Choose at least one category.', 'Add a contact person with an email address.'])
  })
})

describe('vendor dashboard and profile', () => {
  it('invites an unregistered vendor to register', async () => {
    signIn('vendor')
    api((r) => (r.path === '/vendors/me' ? { status: 404, body: { detail: 'You have not registered a vendor profile yet.' } } : undefined))
    renderAt('/app/vendor')
    expect(await screen.findByRole('link', { name: 'Register your company' })).toHaveAttribute('href', '/app/vendor/profile/edit')
  })

  it('shows status, completeness and what is still missing', async () => {
    signIn('vendor')
    api((r) => (r.path === '/vendors/me' ? { body: detail({ status: 'draft', completeness: { percent: 71, missing: ['Tax ID', 'City'] } }) } : undefined))
    renderAt('/app/vendor')
    expect(await screen.findByRole('heading', { level: 1, name: 'Acme' })).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Profile completeness' })).toHaveAttribute('aria-valuenow', '71')
    expect(screen.getByText('Still missing: Tax ID, City')).toBeInTheDocument()
  })

  it('shows an error state with retry when the profile cannot load', async () => {
    signIn('vendor')
    api((r) => (r.path === '/vendors/me' ? { status: 500, body: {} } : undefined))
    renderAt('/app/vendor')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server had a problem')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows the profile with the reason it was sent back, and only the actions the server offers', async () => {
    signIn('vendor')
    api((r) => (r.path === '/vendors/me' ? { body: detail({ status: 'rejected', status_note: 'Tax ID does not match.' }, ['edit', 'submit']) } : undefined))
    renderAt('/app/vendor/profile')
    expect(await screen.findByRole('note')).toHaveTextContent('Tax ID does not match.')
    expect(screen.getByRole('link', { name: /Edit profile/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Submit for verification/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verify' })).toBeNull()
    expect(screen.getByText('IT hardware')).toBeInTheDocument()
  })

  it('submits a draft for verification and shows a server problem if refused', async () => {
    signIn('vendor')
    const { calls } = api((r) => {
      if (r.path === '/vendors/me') return { body: detail({ status: 'draft' }, ['edit', 'submit']) }
      if (r.path === '/vendors/v1/submit') return { status: 422, body: { detail: ['Missing: Tax ID.'] } }
    })
    renderAt('/app/vendor/profile')
    await userEvent.click(await screen.findByRole('button', { name: /Submit for verification/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Missing: Tax ID.')
    expect(calls.filter((c) => c.path === '/vendors/v1/submit')).toHaveLength(1)
  })

  it('registers a new company through the steps and sends the right body', async () => {
    signIn('vendor')
    const saved = detail({ status: 'draft' })
    const { calls } = api((r) => {
      if (r.path === '/vendors/me') return r.method === 'GET' && calls.some((c) => c.method === 'POST' && c.path === '/vendors') ? { body: saved } : { status: 404, body: { detail: 'none' } }
      if (r.path === '/vendors' && r.method === 'POST') return { status: 201, body: saved }
    })
    renderAt('/app/vendor/profile/edit')
    await userEvent.type(await screen.findByLabelText('Registered company name'), 'Acme Supplies Pvt Ltd')
    await userEvent.type(screen.getByLabelText('Tax ID'), '29ABCDE1234F1Z5')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.type(screen.getByLabelText('Street address'), '12 Industrial Layout')
    await userEvent.type(screen.getByLabelText('City'), 'Bengaluru')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(await screen.findByLabelText('IT hardware'))
    await userEvent.click(screen.getByRole('button', { name: /Add contact/ }))
    await userEvent.type(screen.getByLabelText('Contact 1 name'), 'Vera Vendor')
    await userEvent.type(screen.getByLabelText('Contact 1 email'), 'vera@acme.example')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByText('Everything needed for verification is filled in.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/vendors')).toBe(true))
    const body = calls.find((c) => c.method === 'POST' && c.path === '/vendors')!.body as Record<string, unknown>
    expect(body).toMatchObject({ legal_name: 'Acme Supplies Pvt Ltd', tax_id: '29ABCDE1234F1Z5', city: 'Bengaluru', categories: ['it_hardware'], country: 'IN', payment_terms_days: 30,
      contacts: [{ name: 'Vera Vendor', email: 'vera@acme.example', is_primary: true, phone: null }] })
    expect(await screen.findByRole('heading', { level: 1, name: 'Acme' })).toBeInTheDocument()
    expect(calls.some((c) => c.path.endsWith('/submit'))).toBe(false)
  })

  it('blocks a step with invalid fields and says what to fix', async () => {
    signIn('vendor')
    api((r) => (r.path === '/vendors/me' ? { status: 404, body: { detail: 'none' } } : undefined))
    renderAt('/app/vendor/profile/edit')
    await userEvent.type(await screen.findByLabelText('Registered company name'), 'Acme Ltd')
    await userEvent.type(screen.getByLabelText('Website (optional)'), 'acme.example')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Enter a web address starting with http:// or https://')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Fix the highlighted fields')
  })

  it('does not offer the form to a suspended vendor', async () => {
    signIn('vendor')
    api((r) => (r.path === '/vendors/me' ? { body: detail({ status: 'suspended', status_note: 'Audit' }, []) } : undefined))
    renderAt('/app/vendor/profile/edit')
    expect(await screen.findByRole('alert')).toHaveTextContent('A suspended vendor cannot change its profile')
  })
})

describe('vendor directory (staff)', () => {
  it('lists vendors with figures, and filters, searches and pages on the server', async () => {
    signIn('procurement')
    const { calls } = api((r) => (r.path.startsWith('/vendors?') ? { body: page([summary(), summary({ id: 'v2', legal_name: 'Bravo LLP', number: 'VND-2026-000002', status: 'verified', has_account: false })], 23) } : undefined))
    renderAt('/app/procurement/vendors')
    const figures = await screen.findByRole('region', { name: 'Vendor figures' })
    expect(within(figures).getByLabelText(/Waiting for review: 3/)).toBeInTheDocument()
    expect(within(figures).getByLabelText(/Verified: 9/)).toBeInTheDocument()
    expect(await screen.findByText('Bravo LLP')).toBeInTheDocument()
    expect(screen.getByText('No account yet')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3, 23 vendors')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'pending')
    await waitFor(() => expect(calls.some((c) => c.path.includes('status=pending') && c.path.includes('page=1'))).toBe(true))
    await userEvent.selectOptions(screen.getByLabelText('Filter by category'), 'software')
    await waitFor(() => expect(calls.some((c) => c.path.includes('category=software'))).toBe(true))
    await userEvent.type(screen.getByLabelText('Search vendors'), 'bravo')
    await waitFor(() => expect(calls.some((c) => c.path.includes('q=bravo'))).toBe(true))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(calls.some((c) => c.path.includes('page=2'))).toBe(true))
  })

  it('explains an empty directory and an empty search differently', async () => {
    signIn('admin')
    api((r) => (r.path.startsWith('/vendors?') ? { body: page([]) } : undefined))
    renderAt('/app/admin/vendors')
    expect(await screen.findByText('No vendors yet')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Search vendors'), 'zzz')
    expect(await screen.findByText('No vendors match')).toBeInTheDocument()
  })

  it('shows an error state with retry', async () => {
    signIn('procurement')
    api((r) => (r.path.startsWith('/vendors?') ? { status: 500, body: {} } : undefined))
    renderAt('/app/procurement/vendors')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server had a problem')
  })

  it('opens a vendor from the list under the right area for each role', async () => {
    signIn('admin')
    api((r) => (r.path.startsWith('/vendors?') ? { body: page([summary()]) } : r.path === '/vendors/v1' ? { body: detail({}, ['edit', 'verify', 'reject']) } : undefined))
    renderAt('/app/admin/vendors')
    await userEvent.click(await screen.findByRole('button', { name: /Acme Supplies Pvt Ltd/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Acme Supplies Pvt Ltd' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to vendors' })).toHaveAttribute('href', '/app/admin/vendors')
  })
})

describe('vendor review (staff)', () => {
  const open = (d: VendorDetail, acts?: Reply) => {
    signIn('procurement')
    return api((r) => {
      if (r.path === '/vendors/v1' && r.method === 'GET') return { body: d }
      if (r.path.startsWith('/vendors/v1/')) return acts ?? { body: detail({ status: 'verified' }) }
    })
  }

  it('verifies with the version that was reviewed and an optional note', async () => {
    const { calls } = open(detail({}, ['edit', 'verify', 'reject']))
    renderAt('/app/procurement/vendors/v1')
    await userEvent.click(await screen.findByRole('button', { name: /^Verify$/ }))
    const dlg = await screen.findByRole('dialog')
    await userEvent.type(within(dlg).getByLabelText('Note (optional)'), 'Documents checked')
    await userEvent.click(within(dlg).getByRole('button', { name: 'Verify vendor' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/vendors/v1/verify')?.body).toEqual({ version: 3, note: 'Documents checked' }))
  })

  it('needs a reason to send a profile back or suspend a vendor', async () => {
    const { calls } = open(detail({}, ['edit', 'verify', 'reject']))
    renderAt('/app/procurement/vendors/v1')
    await userEvent.click(await screen.findByRole('button', { name: 'Send back' }))
    const dlg = await screen.findByRole('dialog')
    const confirm = within(dlg).getByRole('button', { name: 'Send back' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dlg).getByLabelText('Reason'), 'Wrong tax ID')
    expect(confirm).toBeEnabled()
    await userEvent.click(confirm)
    await waitFor(() => expect(calls.find((c) => c.path === '/vendors/v1/reject')?.body).toEqual({ version: 3, reason: 'Wrong tax ID' }))
  })

  it('offers suspend for verified vendors and reinstate for suspended ones', async () => {
    open(detail({ status: 'verified' }, ['edit', 'suspend']))
    const first = renderAt('/app/procurement/vendors/v1')
    expect(await screen.findByRole('button', { name: 'Suspend' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reinstate' })).toBeNull()
    first.unmount()
    open(detail({ status: 'suspended', status_note: 'Audit failed' }, ['edit', 'reinstate']))
    renderAt('/app/procurement/vendors/v1')
    expect(await screen.findByRole('button', { name: 'Reinstate' })).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('Audit failed')
  })

  it('explains why a reviewer cannot decide on their own submission', async () => {
    open(detail({ blocked_reason: 'Another reviewer must decide on a profile you submitted.' }, ['edit']))
    renderAt('/app/procurement/vendors/v1')
    expect(await screen.findByText('Another reviewer must decide on a profile you submitted.')).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('button', { name: /^Verify$/ })).toBeNull()
  })

  it('shows the server message when the profile changed since it was opened', async () => {
    open(detail({}, ['edit', 'verify', 'reject']), { status: 409, body: { detail: 'This vendor was changed somewhere else. Reload it and try again.' } })
    renderAt('/app/procurement/vendors/v1')
    await userEvent.click(await screen.findByRole('button', { name: /^Verify$/ }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Verify vendor' }))
    expect(await screen.findByText(/changed somewhere else/)).toBeInTheDocument()
  })

  it('registers a vendor for staff through the onboarding endpoint', async () => {
    signIn('procurement')
    const { calls } = api((r) => {
      if (r.path === '/vendors/onboard') return { status: 201, body: detail({ id: 'v9', has_account: false }) }
      if (r.path === '/vendors/v9') return { body: detail({ id: 'v9', has_account: false }) }
    })
    renderAt('/app/procurement/vendors/new')
    await userEvent.type(await screen.findByLabelText('Registered company name'), 'Walk-in Supplies')
    for (let i = 0; i < 3; i++) await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/vendors/onboard')?.body).toMatchObject({ legal_name: 'Walk-in Supplies', contacts: [] }))
    expect(await screen.findByText(/no vendor account is linked yet/)).toBeInTheDocument()
  })
})

describe('access', () => {
  it.each(['employee', 'manager', 'finance', 'vendor'] as const)('keeps %s out of the staff vendor pages', async (role) => {
    signIn(role)
    api(() => ({ status: 404, body: { detail: 'none' } }))
    renderAt('/app/procurement/vendors')
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Vendor figures' })).toBeNull())
    expect(screen.queryByLabelText('Search vendors')).toBeNull()
  })

  it('keeps procurement out of the vendor-only profile pages and admin out of the procurement area', async () => {
    signIn('procurement')
    api(() => ({ status: 404, body: { detail: 'none' } }))
    renderAt('/app/vendor/profile')
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Your company profile' })).toBeNull())
    signIn('admin')
    renderAt('/app/procurement/vendors')
    await waitFor(() => expect(screen.queryByLabelText('Search vendors')).toBeNull())
  })
})
