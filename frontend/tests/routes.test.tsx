import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from '@/routes/AppRoutes'
import { ROLES } from '@/types/roles'
import { dashboardRequest } from '@/services/mockData'
import { mockMatchMedia } from './setup'

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

  it('shows validation errors on the login form and does not pretend to sign in', async () => {
    renderAt('/login')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter your work email')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('renders a not-found page for unknown routes', async () => {
    renderAt('/nope')
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
  })

  it.each(ROLES)('renders the $label dashboard', async (role) => {
    mockMatchMedia(true)
    renderAt(role.path)
    expect(await screen.findByRole('region', { name: 'Key figures' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: `${role.label} navigation` })).toBeInTheDocument()
    expect(screen.getAllByRole('table').length).toBe(1)
    mockMatchMedia(false)
  })

  it('shows an error state with retry when data fails to load', async () => {
    dashboardRequest.failNext = true
    renderAt('/app/employee')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this data')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('region', { name: 'Key figures' })).toBeInTheDocument()
  })
})
