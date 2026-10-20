import { ApiError, authApi, usersApi } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { mockApi, tokenFor } from './helpers'

const unauth = { status: 401, body: { detail: 'Sign in to continue.' } }

describe('auth store and API client', () => {
  it('login keeps the user in memory, sends the bearer token afterwards, and writes nothing to browser storage', async () => {
    const { calls } = mockApi((r) => (r.path === '/auth/login' ? { body: tokenFor('manager', 'SECRET-TOKEN') } : { body: { items: [], total: 0, page: 1, page_size: 10 } }))
    const user = await useAuthStore.getState().login('m@example.com', 'a-long-password-1')
    expect(user.role).toBe('manager')
    expect(useAuthStore.getState().status).toBe('authenticated')
    await usersApi.list({ page: 1, page_size: 10 })
    expect(calls.at(-1)?.auth).toBe('Bearer SECRET-TOKEN')
    const stored = JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage })
    expect(stored).not.toContain('SECRET-TOKEN')
  })

  it('failed login surfaces the server message and stays signed out', async () => {
    mockApi(() => ({ status: 401, body: { detail: 'Incorrect email or password.' } }))
    await expect(useAuthStore.getState().login('a@b.co', 'wrong-wrong')).rejects.toMatchObject({ status: 401, message: 'Incorrect email or password.' })
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('reports an unreachable server in plain language', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(authApi.login('a@b.co', 'x'.repeat(10))).rejects.toThrow(/Could not reach the server/)
  })

  it('bootstrap restores the session from the cookie, or ends anonymous', async () => {
    mockApi(() => ({ body: tokenFor('finance') }))
    await useAuthStore.getState().bootstrap()
    expect(useAuthStore.getState()).toMatchObject({ status: 'authenticated', user: { role: 'finance' } })
    useAuthStore.setState({ status: 'loading', user: null })
    mockApi(() => unauth)
    await useAuthStore.getState().bootstrap()
    expect(useAuthStore.getState().status).toBe('anonymous')
    useAuthStore.setState({ status: 'loading' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await useAuthStore.getState().bootstrap()
    expect(useAuthStore.getState().status).toBe('anonymous')
  })

  it('shares one refresh request between simultaneous callers (StrictMode, parallel tabs of work)', async () => {
    const { calls } = mockApi(() => ({ body: tokenFor('employee') }))
    await Promise.all([useAuthStore.getState().bootstrap(), useAuthStore.getState().bootstrap()])
    expect(calls.filter((c) => c.path === '/auth/refresh')).toHaveLength(1)
  })

  it('a 401 triggers one silent refresh and a retry with the new token', async () => {
    let first = true
    const { calls } = mockApi((r) => {
      if (r.path === '/auth/refresh') return { body: tokenFor('admin', 'fresh') }
      if (first) { first = false; return unauth }
      return { body: { items: [], total: 0, page: 1, page_size: 10 } }
    })
    await usersApi.list({ page: 1, page_size: 10 })
    expect(calls.map((c) => c.path)).toEqual(['/users?page=1&page_size=10', '/auth/refresh', '/users?page=1&page_size=10'])
    expect(calls[2].auth).toBe('Bearer fresh')
    expect(useAuthStore.getState().status).toBe('authenticated')
  })

  it('does not loop when the refresh fails: it signs the user out after exactly one attempt', async () => {
    useAuthStore.setState({ status: 'authenticated', user: tokenFor('admin').user })
    const { calls } = mockApi(() => unauth)
    await expect(usersApi.list({ page: 1, page_size: 10 })).rejects.toBeInstanceOf(ApiError)
    expect(calls).toHaveLength(2)
    expect(useAuthStore.getState()).toMatchObject({ status: 'anonymous', user: null })
  })

  it('parallel 401s share a single refresh', async () => {
    let n = 0
    const { calls } = mockApi((r) => {
      if (r.path === '/auth/refresh') return { body: tokenFor('admin', 'fresh') }
      return r.auth === 'Bearer fresh' || ++n > 2 ? { body: { items: [], total: 0, page: 1, page_size: 10 } } : unauth
    })
    await Promise.all([usersApi.list({ page: 1, page_size: 10 }), usersApi.list({ page: 2, page_size: 10 })])
    expect(calls.filter((c) => c.path === '/auth/refresh')).toHaveLength(1)
  })

  it('forbidden responses are not treated as an expired session', async () => {
    useAuthStore.setState({ status: 'authenticated', user: tokenFor('employee').user })
    const { calls } = mockApi(() => ({ status: 403, body: { detail: 'You do not have permission to do this.' } }))
    await expect(usersApi.list({ page: 1, page_size: 10 })).rejects.toMatchObject({ status: 403 })
    expect(calls).toHaveLength(1)
    expect(useAuthStore.getState().status).toBe('authenticated')
  })

  it('logout clears the session even if the server call fails', async () => {
    useAuthStore.setState({ status: 'authenticated', user: tokenFor('employee').user })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await useAuthStore.getState().logout().catch(() => {})
    expect(useAuthStore.getState()).toMatchObject({ status: 'anonymous', user: null })
  })

  it('can() reads permissions from the signed-in user', () => {
    useAuthStore.setState({ status: 'authenticated', user: tokenFor('admin').user })
    useAuthStore.setState((s) => ({ user: { ...s.user!, permissions: ['user:manage'] } }))
    expect(useAuthStore.getState().can('user:manage')).toBe(true)
    expect(useAuthStore.getState().can('invoice:match')).toBe(false)
  })
})
