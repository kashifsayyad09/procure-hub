import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ApiError, rfqsApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { RfqForm } from '@/features/rfqs/RfqForm'

export default function RfqEditPage() {
  const { id = '' } = useParams()
  const { data: rfq, isLoading, isError, error, refetch } = useQuery({ queryKey: ['rfq', id], queryFn: () => rfqsApi.get(id) })
  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading RFQ</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (isError || !rfq) return <ErrorState title="Could not open this RFQ" description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
  if (!rfq.actions.includes('edit')) return <ErrorState title="This RFQ cannot be edited" description="Only a draft RFQ can be edited. Once it is issued, vendors have seen it." />
  return (
    <div className="flex flex-col gap-u12">
      <header><Link to={`/app/procurement/rfqs/${rfq.id}`} className="text-sm text-muted underline-offset-4 hover:underline">Back to the RFQ</Link><h1 className="display-lg mt-u3">Edit {rfq.number}</h1></header>
      <RfqForm key={rfq.version} mode="edit" existing={rfq} />
    </div>
  )
}
