import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { Skeleton } from '@/components/ui/Skeleton'
import { roleById, type Role } from '@/types/roles'

/**
 * Convenience guard only. The backend decides what each role may read or change; this just avoids showing
 * screens the user cannot use.
 */
export function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const location = useLocation()

  if (status === 'loading') {
    return <div role="status" className="p-u12"><span className="sr-only">Checking your session</span><Skeleton className="h-40 w-full rounded-card" /></div>
  }
  if (status === 'anonymous' || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={roleById(user.role)?.path ?? '/login'} replace />
  return <>{children}</>
}
