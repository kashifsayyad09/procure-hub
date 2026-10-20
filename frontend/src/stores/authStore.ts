import { create } from 'zustand'
import { authApi, refreshSession, registerSessionHandlers, setAccessToken } from '@/services/api'
import type { SessionUser, TokenResponse } from '@/types/auth'

type Status = 'loading' | 'authenticated' | 'anonymous'

interface AuthState {
  status: Status
  user: SessionUser | null
  bootstrap: () => Promise<void>
  login: (email: string, password: string) => Promise<SessionUser>
  logout: () => Promise<void>
  can: (permission: string) => boolean
}

/** Tokens are never written to localStorage or sessionStorage: a page reload re-establishes the session from the httpOnly cookie. */
export const useAuthStore = create<AuthState>((set, get) => ({
  status: 'loading',
  user: null,
  async bootstrap() {
    try {
      const t = await refreshSession()
      if (!t) set({ status: 'anonymous', user: null })
    } catch {
      set({ status: 'anonymous', user: null })
    }
  },
  async login(email, password) {
    const t = await authApi.login(email, password)
    set({ status: 'authenticated', user: t.user })
    return t.user
  },
  async logout() {
    try { await authApi.logout() } finally { setAccessToken(null); set({ status: 'anonymous', user: null }) }
  },
  can: (permission) => !!get().user?.permissions.includes(permission),
}))

registerSessionHandlers(
  (t: TokenResponse) => useAuthStore.setState({ status: 'authenticated', user: t.user }),
  () => useAuthStore.setState({ status: 'anonymous', user: null }),
)
