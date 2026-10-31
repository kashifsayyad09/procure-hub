import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import clsx from 'clsx'
import { ApiError, approvalsApi } from '@/services/api'
import { useDebounced } from '@/hooks/useDebounced'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { ApprovalStatusBadge, APPROVAL_LABEL } from '@/features/approvals/ApprovalStatusBadge'
import { APPROVAL_STATUSES, type ApprovalStatus, type ApprovalView } from '@/features/approvals/types'
import { dateOnly, money } from '@/features/purchase-requests/format'
import { PRIORITIES, type Priority } from '@/features/purchase-requests/types'

const PAGE_SIZE = 10
const VIEWS: { id: ApprovalView; label: string }[] = [{ id: 'queue', label: 'Waiting for me' }, { id: 'mine', label: 'My decisions' }, { id: 'all', label: 'All approvals' }]
const SORTS: Record<string, { label: string; sort: string; order: 'asc' | 'desc' }> = {
  oldest: { label: 'Longest waiting', sort: 'created_at', order: 'asc' }, newest: { label: 'Newest first', sort: 'created_at', order: 'desc' },
  highest: { label: 'Highest value', sort: 'total_amount', order: 'desc' }, soonest: { label: 'Needed soonest', sort: 'needed_by', order: 'asc' },
}
const sel = 'h-11 rounded-ctl border border-line bg-surface px-u6'

export default function ApprovalsPage() {
  const [view, setView] = useState<ApprovalView>('queue')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<ApprovalStatus | ''>('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const [sortKey, setSortKey] = useState('oldest')
  const [page, setPage] = useState(1)
  const q = useDebounced(search.trim(), 300)
  const query = { view, q: q || undefined, status, priority, sort: SORTS[sortKey].sort, order: SORTS[sortKey].order, page, page_size: PAGE_SIZE }
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['approvals', query], queryFn: () => approvalsApi.list(query), placeholderData: (prev) => prev })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const filtered = !!(q || status || priority)
  const change = (fn: () => void) => { fn(); setPage(1) }

  return (
    <div className="flex flex-col gap-u12">
      <header><h1 className="display-lg">Approvals</h1><p className="mt-u4 max-w-xl text-muted">Review requests, decide, or hand a decision to another manager.</p></header>
      <Card>
        <div role="tablist" aria-label="Approval views" className="mb-u8 flex flex-wrap gap-u3">
          {VIEWS.map((v) => (
            <button key={v.id} role="tab" aria-selected={view === v.id} onClick={() => change(() => setView(v.id))}
              className={clsx('min-h-[44px] rounded-full px-u9', view === v.id ? 'bg-accent text-on-accent' : 'bg-pill hover:bg-panel')}>{v.label}</button>
          ))}
        </div>
        <div className="mb-u8 flex flex-wrap gap-u4">
          <label className="relative min-w-[12rem] flex-1"><span className="sr-only">Search approvals</span>
            <Search className="pointer-events-none absolute left-u7 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
            <input type="search" placeholder="Search number, title or requester" value={search} onChange={(e) => change(() => setSearch(e.target.value))} className="h-11 w-full rounded-ctl border border-line bg-surface pl-u17 pr-u6 placeholder:text-muted" /></label>
          {view !== 'queue' && <label><span className="sr-only">Filter by status</span>
            <select className={sel} value={status} onChange={(e) => change(() => setStatus(e.target.value as ApprovalStatus | ''))}><option value="">Any status</option>{APPROVAL_STATUSES.map((s) => <option key={s} value={s}>{APPROVAL_LABEL[s]}</option>)}</select></label>}
          <label><span className="sr-only">Filter by priority</span>
            <select className={sel} value={priority} onChange={(e) => change(() => setPriority(e.target.value as Priority | ''))}><option value="">Any priority</option>{PRIORITIES.map((p) => <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>)}</select></label>
          <label><span className="sr-only">Sort by</span>
            <select className={sel} value={sortKey} onChange={(e) => change(() => setSortKey(e.target.value))}>{Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
        </div>

        {isLoading ? <div aria-busy="true" className="flex flex-col gap-u4"><span className="sr-only">Loading approvals</span>{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          : isError ? <ErrorState description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
          : !data || data.items.length === 0 ? (
            filtered ? <EmptyState title="No matching approvals" description="Change the search or filters to see more." />
              : view === 'queue' ? <EmptyState title="Nothing is waiting for you" description="New requests appear here as soon as employees submit them." />
              : <EmptyState title="No approvals yet" description="Approvals you decide or are given will be listed here." />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[46rem] border-collapse text-left">
                  <caption className="sr-only">Approvals</caption>
                  <thead><tr className="border-b border-line text-sm text-muted">
                    <th scope="col" className="px-u4 py-u5 font-medium">Request</th><th scope="col" className="px-u4 py-u5 font-medium">Requested by</th>
                    <th scope="col" className="px-u4 py-u5 text-right font-medium">Total</th><th scope="col" className="px-u4 py-u5 font-medium">Needed by</th><th scope="col" className="px-u4 py-u5 font-medium">Status</th>
                  </tr></thead>
                  <tbody>
                    {data.items.map((a) => (
                      <tr key={a.id} className="border-b border-line last:border-0">
                        <td className="px-u4 py-u4"><Link to={`/app/manager/approvals/${a.id}`} className="inline-flex min-h-[44px] flex-col justify-center underline-offset-4 hover:underline"><span className="font-medium">{a.title}</span><span className="text-sm text-muted">{a.request_number}</span></Link></td>
                        <td className="px-u4 py-u4">{a.requester_name}<span className="block text-sm text-muted">{a.department}</span></td>
                        <td className="px-u4 py-u4 text-right tabular-nums">{money(a.total_amount, a.currency)}</td>
                        <td className="px-u4 py-u4">{dateOnly(a.needed_by)}</td>
                        <td className="px-u4 py-u4">
                          <ApprovalStatusBadge status={a.status} />
                          {a.status === 'pending' && <span className="mt-u2 block text-sm text-muted">Level {a.current_level} of {a.total_levels}{a.waiting_for ? `, ${a.waiting_for}` : ''}</span>}
                          {a.overdue && <Badge tone="bad" className="mt-u2">Overdue</Badge>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <nav aria-label="Pagination" className="mt-u8 flex items-center justify-between gap-u4">
                <p className="text-sm text-muted">{data.total} {data.total === 1 ? 'approval' : 'approvals'}, page {data.page} of {pages}</p>
                <div className="flex gap-u3"><Button variant="soft" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="soft" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
              </nav>
            </>
          )}
      </Card>
    </div>
  )
}
