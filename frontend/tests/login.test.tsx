import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import LoginPage from '@/pages/auth/LoginPage'
import { useAuthStore } from '@/stores/authStore'
import { mockApi, signIn, tokenFor } from './helpers'

const renderLogin = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app/procurement" element={<p>procurement home</p>} />
        <Route path="/app/finance" element={<p>finance home</p>} />
      </Routes>
    </MemoryRouter>,
  )

async function fill() {
  await userEvent.type(screen.getByLabelText('Work email'), 'person@example.com')
  await userEvent.type(screen.getByLabelText('Password'), 'a-long-password-1')
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('login page', () => {
  it('signs in and opens the dashboard for the role the server returns', async () => {
    const { calls } = mockApi(() => ({ body: tokenFor('procurement') }))
    renderLogin()
    await fill()
    expect(await screen.findByText('procurement home')).toBeInTheDocument()
    expect(calls[0]).toMatchObject({ path: '/auth/login', method: 'POST', body: { email: 'person@example.com', password: 'a-long-password-1' } })
  })
  it('shows the server message for wrong credentials', async () => {
    mockApi(() => ({ status: 401, body: { detail: 'Incorrect email or password.' } }))
    renderLogin()
    await fill()
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
    expect(useAuthStore.getState().user).toBeNull()
  })
  it('explains a lockout and a suspension', async () => {
    mockApi(() => ({ status: 429, body: { detail: 'x' }, headers: { 'Retry-After': '600' } }))
    renderLogin()
    await fill()
    expect(await screen.findByRole('alert')).toHaveTextContent(/too many failed attempts/i)
  })
  it('does not call the server when the form is invalid', async () => {
    const { fn } = mockApi(() => ({ body: tokenFor('finance') }))
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter your work email')).toBeInTheDocument()
    expect(fn).not.toHaveBeenCalled()
  })
  it('has no role-preview shortcuts any more', () => {
    renderLogin()
    expect(screen.queryByText(/preview/i)).not.toBeInTheDocument()
    expect(screen.queryAllByRole('link', { name: /employee|manager|administrator/i })).toHaveLength(0)
  })
  it('redirects an already signed-in user to their dashboard', () => {
    signIn('finance')
    renderLogin()
    expect(screen.getByText('finance home')).toBeInTheDocument()
  })
})
