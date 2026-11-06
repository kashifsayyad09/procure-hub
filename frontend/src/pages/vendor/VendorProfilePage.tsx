import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Building2 } from 'lucide-react'
import { ApiError, vendorsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { VendorActions } from '@/features/vendors/VendorActions'
import { VendorProfileView } from '@/features/vendors/VendorProfileView'

export default function VendorProfilePage() {
  const mine = useQuery({ queryKey: ['vendor', 'me'], queryFn: vendorsApi.mine, retry: false })
  const cats = useQuery({ queryKey: ['vendor-categories'], queryFn: vendorsApi.categories, staleTime: Infinity })
  if (mine.isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading your profile</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (mine.error instanceof ApiError && mine.error.status === 404) {
    return (
      <div className="flex flex-col gap-u12">
        <header><h1 className="display-lg">Your company profile</h1></header>
        <Card className="flex flex-col items-start gap-u6">
          <Building2 className="h-8 w-8 text-muted" aria-hidden />
          <h2 className="text-2xl">Register your company</h2>
          <p className="max-w-xl text-muted">Tell buyers who you are and what you supply. A procurement reviewer verifies the profile before you can answer requests for quotation. You can save a draft and come back.</p>
          <Link to="/app/vendor/profile/edit"><Button>Start registration</Button></Link>
        </Card>
      </div>
    )
  }
  if (mine.isError || !mine.data) return <ErrorState description={mine.error instanceof ApiError ? mine.error.message : 'Try again in a moment.'} onRetry={() => void mine.refetch()} />
  const v = mine.data
  return (
    <div className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">{v.trade_name || v.legal_name}</h1><p className="mt-u4 text-muted">{v.number}</p></div>
      </header>
      <VendorActions vendor={v} editTo="/app/vendor/profile/edit" />
      <VendorProfileView vendor={v} categories={cats.data ?? []} audience="vendor" />
    </div>
  )
}
