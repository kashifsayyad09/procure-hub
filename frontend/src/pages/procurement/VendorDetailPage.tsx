import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ApiError, vendorsApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { VendorActions } from '@/features/vendors/VendorActions'
import { VendorProfileView } from '@/features/vendors/VendorProfileView'
import { useVendorsBase } from '@/features/vendors/useVendorsBase'

export default function VendorDetailPage() {
  const { id = '' } = useParams()
  const base = useVendorsBase()
  const { data: v, isLoading, isError, error, refetch } = useQuery({ queryKey: ['vendor', id], queryFn: () => vendorsApi.get(id) })
  const cats = useQuery({ queryKey: ['vendor-categories'], queryFn: vendorsApi.categories, staleTime: Infinity })
  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading vendor</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (isError || !v) return <ErrorState title="Could not open this vendor" description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to={base} className="text-sm text-muted underline-offset-4 hover:underline">Back to vendors</Link>
        <h1 className="display-lg mt-u3">{v.legal_name}</h1>
        <p className="mt-u4 text-muted">{v.number}{v.has_account ? '' : ', no vendor account is linked yet'}</p>
      </header>
      <VendorActions vendor={v} editTo={`${base}/${v.id}/edit`} />
      <VendorProfileView vendor={v} categories={cats.data ?? []} audience="staff" />
    </div>
  )
}
