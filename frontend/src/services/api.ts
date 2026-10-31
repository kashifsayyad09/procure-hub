import type { SessionUser, TokenResponse, UserPage, UserRecord } from '@/types/auth'
import type { Role } from '@/types/roles'
import type { ApprovalDetail, ApprovalPage, ApprovalQuery, ApprovalsSummary, Delegate } from '@/features/approvals/types'
import type { RequestDetail, RequestInput, RequestPage, RequestQuery, RequestsSummary, RequestDocument } from '@/features/purchase-requests/types'

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
  if (Array.isArray(d)) {
    return d.map((x) => {
      if (typeof x === 'string') return x
      const e = x as { msg?: string; loc?: unknown[] }
      const field = e.loc?.filter((l) => typeof l === 'string' && l !== 'body').pop()
      return field ? `${String(field).replace(/_/g, ' ')}: ${e.msg ?? 'invalid'}` : e.msg ?? 'Invalid value'
    }).join(' ')
  }
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

export const purchaseRequestsApi = {
  list(query: RequestQuery) {
    const p = new URLSearchParams({ page: String(query.page), page_size: String(query.page_size) })
    if (query.q) p.set('q', query.q)
    if (query.status) p.set('status', query.status)
    if (query.priority) p.set('priority', query.priority)
    if (query.sort) p.set('sort', query.sort)
    if (query.order) p.set('order', query.order)
    return request<RequestPage>(`/purchase-requests?${p}`)
  },
  summary: () => request<RequestsSummary>('/purchase-requests/summary'),
  get: (id: string) => request<RequestDetail>(`/purchase-requests/${id}`),
  create: (body: RequestInput) => request<RequestDetail>('/purchase-requests', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: RequestInput & { version: number }) => request<RequestDetail>(`/purchase-requests/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  submit: (id: string) => request<RequestDetail>(`/purchase-requests/${id}/submit`, { method: 'POST' }),
  cancel: (id: string, reason: string) => request<RequestDetail>(`/purchase-requests/${id}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) }),
  remove: (id: string) => request<void>(`/purchase-requests/${id}`, { method: 'DELETE' }),
  addDocument: (id: string, doc: { file_name: string; content_type: string; size_bytes: number }) =>
    request<RequestDocument>(`/purchase-requests/${id}/documents`, { method: 'POST', body: JSON.stringify(doc) }),
  removeDocument: (id: string, docId: string) => request<void>(`/purchase-requests/${id}/documents/${docId}`, { method: 'DELETE' }),
}

export const approvalsApi = {
  list(query: ApprovalQuery) {
    const p = new URLSearchParams({ view: query.view, page: String(query.page), page_size: String(query.page_size) })
    if (query.q) p.set('q', query.q)
    if (query.status) p.set('status', query.status)
    if (query.priority) p.set('priority', query.priority)
    if (query.sort) p.set('sort', query.sort)
    if (query.order) p.set('order', query.order)
    return request<ApprovalPage>(`/approvals?${p}`)
  },
  summary: () => request<ApprovalsSummary>('/approvals/summary'),
  get: (id: string) => request<ApprovalDetail>(`/approvals/${id}`),
  approve: (id: string, comment?: string) => request<ApprovalDetail>(`/approvals/${id}/approve`, { method: 'POST', body: JSON.stringify({ comment: comment || null }) }),
  reject: (id: string, reason: string) => request<ApprovalDetail>(`/approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }),
  delegate: (id: string, userId: string, note?: string) => request<ApprovalDetail>(`/approvals/${id}/delegate`, { method: 'POST', body: JSON.stringify({ user_id: userId, note: note || null }) }),
  delegates: () => request<Delegate[]>('/approvals/delegates'),
}
