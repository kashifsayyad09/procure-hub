import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { ApiError, purchaseRequestsApi } from '@/services/api'
import { useDebounced } from '@/hooks/useDebounced'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { RequestStatusBadge, STATUS_LABEL } from '@/features/purchase-requests/RequestStatusBadge'
import { dateOnly, money } from '@/features/purchase-requests/format'
import { PRIORITIES, STATUSES, type Priority, type RequestStatus } from '@/features/purchase-requests/types'

const PAGE_SIZE = 10
const SORTS: Record<string, { label: string; sort: string; order: 'asc' | 'desc' }> = {
  newest: { label: 'Newest first', sort: 'created_at', order: 'desc' },
  oldest: { label: 'Oldest first', sort: 'created_at', order: 'asc' },
  highest: { label: 'Highest value', sort: 'total_amount', order: 'desc' },
  lowest: { label: 'Lowest value', sort: 'total_amount', order: 'asc' },
  soonest: { label: 'Needed soonest', sort: 'needed_by', order: 'asc' },
}
const sel = 'h-11 rounded-ctl border border-line bg-surface px-u6'

export default function RequestsPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<RequestStatus | ''>('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const [sortKey, setSortKey] = useState('newest')
  const [page, setPage] = useState(1)
  const q = useDebounced(search.trim(), 300)
  const query = { q: q || undefined, status, priority, sort: SORTS[sortKey].sort, order: SORTS[sortKey].order, page, page_size: PAGE_SIZE }
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['requests', query], queryFn: () => purchaseRequestsApi.list(query), placeholderData: (prev) => prev })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const filtered = !!(q || status || priority)
  const change = (fn: () => void) => { fn(); setPage(1) }

  return (
    <div className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">My requests</h1><p className="mt-u4 max-w-xl text-muted">Everything you have asked to buy, and where each request stands.</p></div>
        <Link to="/app/employee/requests/new"><Button><Plus className="h-4 w-4" aria-hidden /> New request</Button></Link>
      </header>
      <Card>
        <div className="mb-u8 flex flex-wrap gap-u4">
          <label className="relative min-w-[12rem] flex-1"><span className="sr-only">Search requests</span>
            <Search className="pointer-events-none absolute left-u7 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
            <input type="search" placeholder="Search number or title" value={search} onChange={(e) => change(() => setSearch(e.target.value))} className="h-11 w-full rounded-ctl border border-line bg-surface pl-u17 pr-u6 placeholder:text-muted" /></label>
          <label><span className="sr-only">Filter by status</span>
            <select className={sel} value={status} onChange={(e) => change(() => setStatus(e.target.value as RequestStatus | ''))}><option value="">Any status</option>{STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</select></label>
          <label><span className="sr-only">Filter by priority</span>
            <select className={sel} value={priority} onChange={(e) => change(() => setPriority(e.target.value as Priority | ''))}><option value="">Any priority</option>{PRIORITIES.map((p) => <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>)}</select></label>
          <label><span className="sr-only">Sort by</span>
            <select className={sel} value={sortKey} onChange={(e) => change(() => setSortKey(e.target.value))}>{Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
        </div>

        {isLoading ? <div aria-busy="true" className="flex flex-col gap-u4"><span className="sr-only">Loading requests</span>{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          : isError ? <ErrorState description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
          : !data || data.items.length === 0 ? (
            filtered ? <EmptyState title="No matching requests" description="Change the search or filters to see more." />
              : <EmptyState title="No requests yet" description="Start a request for something you need. You can save it as a draft first." action={<Link to="/app/employee/requests/new"><Button>Create your first request</Button></Link>} />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[40rem] border-collapse text-left">
                  <caption className="sr-only">Your purchase requests</caption>
                  <thead><tr className="border-b border-line text-sm text-muted">
                    <th scope="col" className="px-u4 py-u5 font-medium">Request</th><th scope="col" className="px-u4 py-u5 font-medium">Needed by</th>
                    <th scope="col" className="px-u4 py-u5 text-right font-medium">Total</th><th scope="col" className="px-u4 py-u5 font-medium">Status</th>
                  </tr></thead>
                  <tbody>
                    {data.items.map((r) => (
                      <tr key={r.id} className="border-b border-line last:border-0">
                        <td className="px-u4 py-u4"><Link to={`/app/employee/requests/${r.id}`} className="inline-flex min-h-[44px] flex-col justify-center underline-offset-4 hover:underline"><span className="font-medium">{r.title}</span><span className="text-sm text-muted">{r.number}</span></Link></td>
                        <td className="px-u4 py-u4">{dateOnly(r.needed_by)}</td>
                        <td className="px-u4 py-u4 text-right tabular-nums">{money(r.total_amount, r.currency)}</td>
                        <td className="px-u4 py-u4"><RequestStatusBadge status={r.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <nav aria-label="Pagination" className="mt-u8 flex items-center justify-between gap-u4">
                <p className="text-sm text-muted">{data.total} {data.total === 1 ? 'request' : 'requests'}, page {data.page} of {pages}</p>
                <div className="flex gap-u3"><Button variant="soft" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="soft" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
              </nav>
            </>
          )}
      </Card>
    </div>
  )
}
