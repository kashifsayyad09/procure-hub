import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { ApiError, rfqsApi } from '@/services/api'
import { useDebounced } from '@/hooks/useDebounced'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { dateOnly, money } from '@/features/purchase-requests/format'
import { RfqForm } from '@/features/rfqs/RfqForm'
import type { EligibleRequest } from '@/features/rfqs/types'

/** Step 1: pick an approved purchase request. Step 2: describe the RFQ. */
export default function RfqNewPage() {
  const [chosen, setChosen] = useState<EligibleRequest | null>(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const q = useDebounced(search.trim(), 300)
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['rfq-eligible', q, page], queryFn: () => rfqsApi.eligible(q, page), placeholderData: (p) => p })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  if (chosen) {
    return (
      <div className="flex flex-col gap-u12">
        <header>
          <button onClick={() => setChosen(null)} className="text-sm text-muted underline-offset-4 hover:underline">Choose a different request</button>
          <h1 className="display-lg mt-u3">New RFQ</h1>
          <p className="mt-u4 text-muted">From {chosen.number}: {chosen.title}. {chosen.item_count} item{chosen.item_count === 1 ? '' : 's'}, budget {money(chosen.total_amount, chosen.currency)} (vendors never see the budget).</p>
        </header>
        <RfqForm mode="create" purchaseRequestId={chosen.id} defaultTitle={chosen.title} />
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to="/app/procurement/rfqs" className="text-sm text-muted underline-offset-4 hover:underline">Back to RFQs</Link>
        <h1 className="display-lg mt-u3">New RFQ</h1>
        <p className="mt-u4 max-w-xl text-muted">Step 1 of 2. Choose the approved purchase request this RFQ is for. A request can have one RFQ in progress at a time.</p>
      </header>
      <Card>
        <label className="relative mb-u8 block"><span className="sr-only">Search approved requests</span>
          <Search className="pointer-events-none absolute left-u7 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
          <input type="search" placeholder="Search by title or request number" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="h-11 w-full rounded-ctl border border-line bg-surface pl-u17 pr-u6 placeholder:text-muted" /></label>
        {isLoading ? <div role="status" aria-busy="true"><span className="sr-only">Loading approved requests</span>{[0, 1, 2].map((i) => <Skeleton key={i} className="mb-u4 h-16 w-full" />)}</div>
          : isError || !data ? <ErrorState title="Could not load approved requests" description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
          : data.items.length === 0 ? <EmptyState title={q ? 'No requests match' : 'No approved requests'} description={q ? 'Try a different search.' : 'Requests appear here once a manager approves them.'} />
          : (
            <>
              <ul className="flex flex-col gap-u5" aria-label="Approved purchase requests">
                {data.items.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-center justify-between gap-u6 rounded-ctl border border-line p-u7">
                    <div><p className="font-medium">{r.title}</p>
                      <p className="text-sm text-muted">{r.number}, {r.department || 'No department'}, {r.item_count} item{r.item_count === 1 ? '' : 's'}, {money(r.total_amount, r.currency)}</p>
                      <p className="text-sm text-muted">Approved {r.decided_at ? dateOnly(r.decided_at) : ''}{r.decided_by_name ? ` by ${r.decided_by_name}` : ''}{r.needed_by ? `, needed by ${dateOnly(r.needed_by)}` : ''}</p></div>
                    {r.rfq_id ? <Link to={`/app/procurement/rfqs/${r.rfq_id}`} className="underline underline-offset-4">Already has {r.rfq_number}</Link>
                      : <Button aria-label={`Use ${r.number}`} onClick={() => setChosen(r)}>Use this request</Button>}
                  </li>
                ))}
              </ul>
              <nav aria-label="Pagination" className="mt-u8 flex items-center justify-between">
                <p className="text-sm text-muted" aria-live="polite">Page {data.page} of {pages}, {data.total} requests</p>
                <div className="flex gap-u4"><Button variant="soft" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="soft" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
              </nav>
            </>
          )}
      </Card>
    </div>
  )
}
