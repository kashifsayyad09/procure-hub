import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { ApiError, rfqsApi } from '@/services/api'
import { useDebounced } from '@/hooks/useDebounced'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatCard } from '@/components/ui/StatCard'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { dateTime } from '@/features/purchase-requests/format'
import { RfqStatusBadge } from '@/features/rfqs/RfqStatusBadge'
import { RFQ_STATUS_LABEL, timeLeft } from '@/features/rfqs/labels'
import { RFQ_STATUSES, type RfqStatus } from '@/features/rfqs/types'

const PAGE_SIZE = 10
const SORTS: Record<string, { label: string; sort: string; order: 'asc' | 'desc' }> = {
  newest: { label: 'Newest first', sort: 'created_at', order: 'desc' }, deadline: { label: 'Deadline, soonest first', sort: 'deadline', order: 'asc' }, title: { label: 'Title A to Z', sort: 'title', order: 'asc' },
}
const sel = 'h-11 rounded-ctl border border-line bg-surface px-u6'

export default function RfqsPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<RfqStatus | ''>('')
  const [sortKey, setSortKey] = useState('newest')
  const [page, setPage] = useState(1)
  const q = useDebounced(search.trim(), 300)
  const query = { q: q || undefined, status, sort: SORTS[sortKey].sort, order: SORTS[sortKey].order, page, page_size: PAGE_SIZE }
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['rfqs', query], queryFn: () => rfqsApi.list(query), placeholderData: (prev) => prev })
  const summary = useQuery({ queryKey: ['rfqs-summary'], queryFn: rfqsApi.summary })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const filtered = !!(q || status)
  const change = (fn: () => void) => { fn(); setPage(1) }
  const c = summary.data?.counts

  return (
    <div className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">Requests for quotation</h1><p className="mt-u4 max-w-xl text-muted">Send approved purchase requests out to verified vendors, compare what they offer, and choose a supplier.</p></div>
        <Link to="/app/procurement/rfqs/new"><Button><Plus className="h-4 w-4" aria-hidden /> New RFQ</Button></Link>
      </header>

      {c && (
        <section aria-label="RFQ figures" className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard stat={{ id: 'open', label: 'Open for quotations', value: c.issued, note: 'Vendors can still respond' }} />
          <StatCard stat={{ id: 'waiting', label: 'Ready to compare', value: summary.data?.awaiting_comparison ?? 0, note: 'Deadline passed or closed' }} />
          <StatCard stat={{ id: 'draft', label: 'Drafts', value: c.draft, note: 'Not sent to vendors yet' }} />
          <StatCard stat={{ id: 'awarded', label: 'Awarded', value: c.awarded, note: 'A supplier is selected' }} />
        </section>
      )}

      <Card>
        <div className="mb-u8 flex flex-wrap gap-u4">
          <label className="relative min-w-[12rem] flex-1"><span className="sr-only">Search RFQs</span>
            <Search className="pointer-events-none absolute left-u7 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
            <input type="search" placeholder="Search title, RFQ number or request number" value={search} onChange={(e) => change(() => setSearch(e.target.value))}
              className="h-11 w-full rounded-ctl border border-line bg-surface pl-u17 pr-u6 placeholder:text-muted" /></label>
          <label><span className="sr-only">Filter by status</span>
            <select className={sel} value={status} onChange={(e) => change(() => setStatus(e.target.value as RfqStatus | ''))}><option value="">Any status</option>{RFQ_STATUSES.map((s) => <option key={s} value={s}>{RFQ_STATUS_LABEL[s]}</option>)}</select></label>
          <label><span className="sr-only">Sort by</span>
            <select className={sel} value={sortKey} onChange={(e) => change(() => setSortKey(e.target.value))}>{Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
        </div>
        {isLoading ? (
          <div role="status" aria-busy="true"><span className="sr-only">Loading RFQs</span>{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="mb-u4 h-14 w-full" />)}</div>
        ) : isError || !data ? (
          <ErrorState description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
        ) : data.items.length === 0 ? (
          <EmptyState title={filtered ? 'No RFQs match' : 'No RFQs yet'} description={filtered ? 'Try a different search or clear a filter.' : 'Start one from an approved purchase request.'} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[46rem] border-collapse text-left">
                <caption className="sr-only">Requests for quotation, {data.total} in total</caption>
                <thead><tr className="border-b border-line text-sm text-muted">
                  <th scope="col" className="px-u4 py-u4 font-medium">RFQ</th><th scope="col" className="px-u4 py-u4 font-medium">Status</th>
                  <th scope="col" className="px-u4 py-u4 font-medium">Deadline</th><th scope="col" className="px-u4 py-u4 font-medium">Vendors</th>
                </tr></thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id} className="border-b border-line last:border-0">
                      <td className="px-u4 py-u4"><button onClick={() => navigate(`/app/procurement/rfqs/${r.id}`)} className="min-h-[44px] text-left underline-offset-4 hover:underline">
                        <span className="block font-medium">{r.title}</span><span className="block text-sm text-muted">{r.number}, from {r.purchase_request_number}</span></button></td>
                      <td className="px-u4 py-u4"><RfqStatusBadge status={r.status} /></td>
                      <td className="px-u4 py-u4 text-sm">{dateTime(r.deadline)}{r.status === 'issued' && <span className="block text-muted">{timeLeft(r.deadline)}</span>}</td>
                      <td className="px-u4 py-u4 text-sm">{r.invited} invited, {r.submitted} submitted</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav aria-label="Pagination" className="mt-u8 flex items-center justify-between">
              <p className="text-sm text-muted" aria-live="polite">Page {data.page} of {pages}, {data.total} RFQs</p>
              <div className="flex gap-u4"><Button variant="soft" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="soft" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
            </nav>
          </>
        )}
      </Card>
    </div>
  )
}
