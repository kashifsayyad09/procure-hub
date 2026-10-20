import { vi } from 'vitest'
import type { SessionUser, TokenResponse } from '@/types/auth'
import type { Role } from '@/types/roles'
import { useAuthStore } from '@/stores/authStore'

export const sessionUser = (role: Role, over: Partial<SessionUser> = {}): SessionUser => ({
  id: `id-${role}`, email: `${role}@example.com`, full_name: `Test ${role}`, role, is_active: true,
  last_login_at: null, created_at: '2026-01-01T00:00:00', permissions: role === 'admin' ? ['user:read', 'user:manage'] : [], ...over,
})
export const tokenFor = (role: Role, access = 'access-1'): TokenResponse => ({ access_token: access, token_type: 'bearer', expires_in: 900, user: sessionUser(role) })
export const signIn = (role: Role) => useAuthStore.setState({ status: 'authenticated', user: sessionUser(role) })

export interface Req { path: string; method: string; body: unknown; auth: string | null }
export type Reply = { status?: number; body?: unknown; headers?: Record<string, string> }

/** Stubs fetch. `handler` receives the API path without the /api/v1 prefix. */
export function mockApi(handler: (r: Req) => Reply | Promise<Reply>) {
  const calls: Req[] = []
  const fn = vi.fn(async (url: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers)
    const req: Req = { path: String(url).replace('/api/v1', ''), method: init.method ?? 'GET', body: init.body ? JSON.parse(String(init.body)) : undefined, auth: headers.get('Authorization') }
    calls.push(req)
    const r = await handler(req)
    const status = r.status ?? 200
    return new Response(status === 204 ? null : JSON.stringify(r.body ?? {}), { status, headers: r.headers })
  })
  vi.stubGlobal('fetch', fn)
  return { calls, fn }
}
