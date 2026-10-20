import type { SessionUser, TokenResponse, UserPage, UserRecord } from '@/types/auth'
import type { Role } from '@/types/roles'

const BASE = '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, message: string, public retryAfter?: number) {
    super(message)
  }
}

// The access token lives only in memory. The refresh token is an httpOnly cookie the page cannot read.
let accessToken: string | null = null
let onSession: ((t: TokenResponse) => void) | null = null
let onAuthFailure: (() => void) | null = null

export const setAccessToken = (t: string | null) => { accessToken = t }
export const registerSessionHandlers = (session: (t: TokenResponse) => void, failure: () => void) => { onSession = session; onAuthFailure = failure }

function messageFrom(body: unknown, status: number): string {
  const d = (body as { detail?: unknown } | null)?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x) => (typeof x === 'string' ? x : (x as { msg?: string }).msg ?? 'Invalid value')).join(' ')
  return status >= 500 ? 'The server had a problem. Try again in a moment.' : 'Something went wrong. Try again.'
}

async function send<T>(path: string, init: RequestInit = {}, token: string | null = accessToken): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let res: Response
  try {
    res = await fetch(BASE + path, { ...init, headers, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.')
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, messageFrom(body, res.status), Number(res.headers.get('Retry-After')) || undefined)
  return body as T
}

let inflight: Promise<TokenResponse | null> | null = null

/** One refresh at a time: parallel callers (React StrictMode, several 401s at once) share the same request. */
export function refreshSession(): Promise<TokenResponse | null> {
  inflight ??= (async () => {
    try {
      const t = await send<TokenResponse>('/auth/refresh', { method: 'POST' }, null)
      accessToken = t.access_token
      onSession?.(t)
      return t
    } catch (e) {
      if (e instanceof ApiError) return null
      throw e
    } finally {
      inflight = null
    }
  })()
  return inflight
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  try {
    return await send<T>(path, init)
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 401) throw e
    const fresh = await refreshSession() // one silent retry, never a loop
    if (!fresh) {
      accessToken = null
      onAuthFailure?.()
      throw e
    }
    return send<T>(path, init, fresh.access_token)
  }
}

export const authApi = {
  async login(email: string, password: string) {
    const t = await send<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }, null)
    accessToken = t.access_token
    return t
  },
  async logout() {
    try { await send<void>('/auth/logout', { method: 'POST' }, null) } finally { accessToken = null }
  },
  me: () => request<SessionUser>('/auth/me'),
}

export interface UserQuery { q?: string; role?: Role | ''; is_active?: '' | 'true' | 'false'; page: number; page_size: number }

export const usersApi = {
  list(query: UserQuery) {
    const p = new URLSearchParams({ page: String(query.page), page_size: String(query.page_size) })
    if (query.q) p.set('q', query.q)
    if (query.role) p.set('role', query.role)
    if (query.is_active) p.set('is_active', query.is_active)
    return request<UserPage>(`/users?${p}`)
  },
  create: (body: { email: string; full_name: string; role: Role; password: string }) => request<UserRecord>('/users', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: Partial<{ full_name: string; role: Role; is_active: boolean }>) => request<UserRecord>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
}
