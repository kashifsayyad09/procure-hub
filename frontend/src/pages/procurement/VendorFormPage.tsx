import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ApiError, vendorsApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { VendorForm } from '@/features/vendors/VendorForm'
import { useVendorsBase } from '@/features/vendors/useVendorsBase'

/** Staff registering a vendor that has no account yet (`/new`), or correcting any vendor's profile (`/:id/edit`). */
export default function VendorFormPage() {
  const { id } = useParams()
  const base = useVendorsBase()
  const existing = useQuery({ queryKey: ['vendor', id], queryFn: () => vendorsApi.get(id!), enabled: !!id })
  if (id && existing.isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading vendor</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (id && (existing.isError || !existing.data)) return <ErrorState title="Could not open this vendor" description={existing.error instanceof ApiError ? existing.error.message : 'Try again in a moment.'} onRetry={() => void existing.refetch()} />
  if (existing.data && !existing.data.actions.includes('edit')) return <ErrorState title="You cannot edit this vendor" description="Your role does not allow changes to this profile." />
  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to={id ? `${base}/${id}` : base} className="text-sm text-muted underline-offset-4 hover:underline">{id ? 'Back to the vendor' : 'Back to vendors'}</Link>
        <h1 className="display-lg mt-u3">{id ? 'Edit vendor' : 'Register a vendor'}</h1>
        {!id && <p className="mt-u4 max-w-xl text-muted">For a vendor that has no ProcureHub account yet. Another reviewer must verify it after you submit.</p>}
      </header>
      <VendorForm key={existing.data?.id ?? 'new'} mode={id ? 'edit' : 'onboard'} existing={existing.data} after={(v) => `${base}/${v.id}`} />
    </div>
  )
}
