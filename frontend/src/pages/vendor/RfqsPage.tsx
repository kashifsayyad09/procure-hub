import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ApiError, rfqsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { Badge } from '@/components/ui/Badge'
import { dateTime, money } from '@/features/purchase-requests/format'
import { QuotationStatusBadge, RfqStatusBadge } from '@/features/rfqs/RfqStatusBadge'
import { INVITATION_LABEL, timeLeft, unitPrice } from '@/features/rfqs/labels'

export default function VendorRfqsPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['rfq', 'invited', page], queryFn: () => rfqsApi.invited(page), placeholderData: (p) => p, retry: false })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <div className="flex flex-col gap-u12">
      <header><h1 className="display-lg">Requests for quotation</h1><p className="mt-u4 max-w-xl text-muted">Buyers who have invited you to quote. Open one to read what they need and send your prices.</p></header>
      {isLoading ? <div role="status" aria-busy="true"><span className="sr-only">Loading your RFQs</span>{[0, 1, 2].map((i) => <Skeleton key={i} className="mb-u4 h-20 w-full rounded-card" />)}</div>
        : isError || !data ? (
          error instanceof ApiError && error.status === 403
            ? <EmptyState title="Register your company first" description="You need a verified vendor profile to receive requests for quotation." action={<Link to="/app/vendor/profile"><Button>Open your profile</Button></Link>} />
            : <ErrorState description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />)
        : data.items.length === 0 ? <EmptyState title="No invitations yet" description="When a buyer invites you to quote, the request appears here." />
        : (
          <>
            <ul className="flex flex-col gap-u6" aria-label="Invited requests for quotation">
              {data.items.map((r) => (
                <li key={r.id}>
                  <Card className="flex flex-wrap items-center justify-between gap-u6">
                    <div>
                      <Link to={`/app/vendor/rfqs/${r.id}`} className="text-xl font-medium underline-offset-4 hover:underline">{r.title}</Link>
                      <p className="text-sm text-muted">{r.number}, deadline {dateTime(r.deadline)}{r.status === 'issued' && !r.deadline_passed ? `, ${timeLeft(r.deadline)}` : ''}</p>
                      <div className="mt-u3 flex flex-wrap gap-u3"><RfqStatusBadge status={r.status} />
                        {r.invitation_status !== 'invited' && <Badge>{INVITATION_LABEL[r.invitation_status]}</Badge>}
                        {r.quotation && <QuotationStatusBadge status={r.quotation.status} />}
                        {r.can_quote && !r.quotation && <Badge tone="accent">Waiting for your quotation</Badge>}</div>
                    </div>
                    <div className="text-right">{r.quotation && <p className="mb-u3">{money(unitPrice(r.quotation.total_amount), r.quotation.currency)}</p>}
                      <Link to={`/app/vendor/rfqs/${r.id}`}><Button variant="soft">{r.can_quote ? (r.quotation ? 'Continue' : 'Open and quote') : 'View'}</Button></Link></div>
                  </Card>
                </li>
              ))}
            </ul>
            <nav aria-label="Pagination" className="flex items-center justify-between">
              <p className="text-sm text-muted" aria-live="polite">Page {data.page} of {pages}, {data.total} request{data.total === 1 ? '' : 's'}</p>
              <div className="flex gap-u4"><Button variant="soft" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="soft" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
            </nav>
          </>
        )}
    </div>
  )
}
