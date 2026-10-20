import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import UsersPage, { createUserSchema } from '@/pages/admin/UsersPage'
import { mockApi, sessionUser, signIn } from './helpers'

const rows = [sessionUser('admin', { id: 'id-admin', email: 'admin@example.com', full_name: 'Ada Admin' }), sessionUser('employee', { id: 'u2', email: 'eve@example.com', full_name: 'Eve Employee' })]
const page = { items: rows, total: 2, page: 1, page_size: 10 }

const renderPage = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><UsersPage /></MemoryRouter>
    </QueryClientProvider>,
  )

describe('admin users page', () => {
  it('lists users returned by the API', async () => {
    signIn('admin')
    mockApi(() => ({ body: page }))
    renderPage()
    expect(await screen.findByText('Eve Employee')).toBeInTheDocument()
    expect(screen.getByText('2 users, page 1 of 1')).toBeInTheDocument()
  })

  it('creates a user and sends the typed values', async () => {
    signIn('admin')
    const { calls } = mockApi((r) => (r.method === 'POST' ? { status: 201, body: rows[1] } : { body: page }))
    renderPage()
    await screen.findByText('Eve Employee')
    await userEvent.click(screen.getByRole('button', { name: /add user/i }))
    const dialog = await screen.findByRole('dialog', { name: 'Add a user' })
    await userEvent.type(within(dialog).getByLabelText('Full name'), 'New Person')
    await userEvent.type(within(dialog).getByLabelText('Work email'), 'new@example.com')
    await userEvent.selectOptions(within(dialog).getByLabelText('Role'), 'vendor')
    await userEvent.type(within(dialog).getByLabelText('Initial password'), 'Correct-horse-42')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }))
    await vi.waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')).toMatchObject({ path: '/users', body: { full_name: 'New Person', email: 'new@example.com', role: 'vendor', password: 'Correct-horse-42' } })
  })

  it('shows the server error when the email is taken', async () => {
    signIn('admin')
    mockApi((r) => (r.method === 'POST' ? { status: 409, body: { detail: 'A user with this email already exists.' } } : { body: page }))
    renderPage()
    await screen.findByText('Eve Employee')
    await userEvent.click(screen.getByRole('button', { name: /add user/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Full name'), 'Dup')
    await userEvent.type(within(dialog).getByLabelText('Work email'), 'eve@example.com')
    await userEvent.type(within(dialog).getByLabelText('Initial password'), 'Correct-horse-42')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('already exists')
  })

  it('does not let an administrator edit their own role or suspend themselves', async () => {
    signIn('admin')
    mockApi(() => ({ body: page }))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Ada Admin/ }))
    const drawer = await screen.findByRole('dialog', { name: 'Ada Admin' })
    expect(within(drawer).getByLabelText('Role')).toBeDisabled()
    expect(within(drawer).getByRole('button', { name: 'Suspend account' })).toBeDisabled()
  })

  it('suspends another user', async () => {
    signIn('admin')
    const { calls } = mockApi((r) => (r.method === 'PATCH' ? { body: { ...rows[1], is_active: false } } : { body: page }))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Eve Employee/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Suspend account' }))
    await vi.waitFor(() => expect(calls.find((c) => c.method === 'PATCH')).toMatchObject({ path: '/users/u2', body: { is_active: false } }))
  })

  it('shows an error state with retry when the list cannot be loaded', async () => {
    signIn('admin')
    mockApi(() => ({ status: 500, body: {} }))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this data')
  })

  it('validates the new-user form like the server does', () => {
    const ok = { full_name: 'A', email: 'a@b.co', role: 'vendor', password: 'Correct-horse-42' }
    expect(createUserSchema.safeParse(ok).success).toBe(true)
    for (const bad of [{ ...ok, password: 'short1' }, { ...ok, password: 'onlyletterslong' }, { ...ok, role: 'root' }, { ...ok, email: 'nope' }]) {
      expect(createUserSchema.safeParse(bad).success).toBe(false)
    }
  })
})
