import { useAuthStore } from '@/stores/authStore'

/** Procurement and administrators share the vendor screens; each reaches them under their own area. */
export function useVendorsBase(): string {
  const role = useAuthStore((s) => s.user?.role)
  return role === 'admin' ? '/app/admin/vendors' : '/app/procurement/vendors'
}
