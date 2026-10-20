import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from '@/routes/AppRoutes'
import { ROLES } from '@/types/roles'
import { dashboardRequest } from '@/services/mockData'
import { mockMatchMedia } from './setup'
import { mockApi, signIn } from './helpers'
import { useAuthStore } from '@/stores/authStore'

const renderAt = (path: string) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>
    </QueryClientProvider>,
  )

describe('routing', () => {
  it('renders the landing page with a sign-in link', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(/every purchase/i)
    expect(screen.getAllByRole('link', { name: /sign in/i }).length).toBeGreaterThan(0)
  })

  it('shows validation errors on the login form', async () => {
    renderAt('/login')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter your work email')).toBeInTheDocument()
  })

  it('keeps anonymous visitors out of every workspace', async () => {
    useAuthStore.setState({ status: 'anonymous', user: null })
    for (const role of ROLES) {
      const { unmount } = renderAt(role.path)
      expect(await screen.findByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument()
      unmount()
    }
  })

  it('does not show another role\'s workspace', async () => {
    signIn('employee')
    renderAt('/app/admin')
    expect(await screen.findByRole('heading', { level: 1, name: 'Your requests' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users and roles' })).not.toBeInTheDocument()
  })

  it('only administrators reach the users page, and the sidebar links to it', async () => {
    signIn('admin')
    mockApi(() => ({ body: { items: [], total: 0, page: 1, page_size: 10 } }))
    renderAt('/app/admin/users')
    expect(await screen.findByRole('heading', { level: 1, name: 'Users and roles' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Users and roles' })).toHaveAttribute('href', '/app/admin/users')
  })

  it('landing page offers sign-in only, with no workspace shortcuts', async () => {
    renderAt('/')
    await screen.findByRole('heading', { level: 1 })
    expect(document.querySelectorAll('a[href^="/app"]')).toHaveLength(0)
  })

  it('renders a not-found page for unknown routes', async () => {
    renderAt('/nope')
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
  })

  it.each(ROLES)('renders the $label dashboard', async (role) => {
    mockMatchMedia(true)
    signIn(role.id)
    renderAt(role.path)
    expect(await screen.findByRole('region', { name: 'Key figures' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: `${role.label} navigation` })).toBeInTheDocument()
    expect(screen.getAllByRole('table').length).toBe(1)
    mockMatchMedia(false)
  })

  it('shows an error state with retry when data fails to load', async () => {
    signIn('employee')
    dashboardRequest.failNext = true
    renderAt('/app/employee')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this data')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('region', { name: 'Key figures' })).toBeInTheDocument()
  })
})
