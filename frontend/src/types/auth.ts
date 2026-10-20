import type { Role } from './roles'

export interface UserRecord {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  last_login_at: string | null
  created_at: string
}
export interface SessionUser extends UserRecord { permissions: string[] }
export interface TokenResponse { access_token: string; token_type: string; expires_in: number; user: SessionUser }
export interface UserPage { items: UserRecord[]; total: number; page: number; page_size: number }
