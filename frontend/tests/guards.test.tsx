import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { useAuthStore } from '@/stores/authStore'
import { signIn } from './helpers'

const tree = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<p>login page</p>} />
        <Route path="/app/manager" element={<p>manager home</p>} />
        <Route path="/app/admin" element={<RequireAuth roles={['admin']}><p>admin secret</p></RequireAuth>} />
        <Route path="/app/any" element={<RequireAuth><p>any user</p></RequireAuth>} />
      </Routes>
    </MemoryRouter>,
  )

describe('RequireAuth', () => {
  it('shows a status message while the session is being restored', () => {
    tree('/app/any')
    expect(screen.getByRole('status')).toHaveTextContent('Checking your session')
    expect(screen.queryByText('any user')).not.toBeInTheDocument()
  })
  it('sends anonymous visitors to the login page without rendering the content', () => {
    useAuthStore.setState({ status: 'anonymous', user: null })
    tree('/app/admin')
    expect(screen.getByText('login page')).toBeInTheDocument()
    expect(screen.queryByText('admin secret')).not.toBeInTheDocument()
  })
  it('sends a user with the wrong role to their own dashboard', () => {
    signIn('manager')
    tree('/app/admin')
    expect(screen.getByText('manager home')).toBeInTheDocument()
    expect(screen.queryByText('admin secret')).not.toBeInTheDocument()
  })
  it('renders for the right role and for role-less guards', () => {
    signIn('admin')
    tree('/app/admin')
    expect(screen.getByText('admin secret')).toBeInTheDocument()
    tree('/app/any')
    expect(screen.getByText('any user')).toBeInTheDocument()
  })
})
