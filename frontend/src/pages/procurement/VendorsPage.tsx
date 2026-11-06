import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { ApiError, vendorsApi } from '@/services/api'
import { useDebounced } from '@/hooks/useDebounced'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatCard } from '@/components/ui/StatCard'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { VendorStatusBadge } from '@/features/vendors/VendorStatusBadge'
import { STATUS_LABEL } from '@/features/vendors/labels'
import { useVendorsBase } from '@/features/vendors/useVendorsBase'
import { VENDOR_STATUSES, type VendorStatus } from '@/features/vendors/types'

const PAGE_SIZE = 10
const SORTS: Record<string, { label: string; sort: string; order: 'asc' | 'desc' }> = {
  name: { label: 'Name A to Z', sort: 'legal_name', order: 'asc' }, newest: { label: 'Newest first', sort: 'created_at', order: 'desc' },
  waiting: { label: 'Longest waiting for review', sort: 'submitted_at', order: 'asc' }, verified: { label: 'Recently verified', sort: 'verified_at', order: 'desc' },
}
const sel = 'h-11 rounded-ctl border border-line bg-surface px-u6'

export default function VendorsPage() {
  const base = useVendorsBase()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<VendorStatus | ''>('')
  const [category, setCategory] = useState('')
  const [sortKey, setSortKey] = useState('name')
  const [page, setPage] = useState(1)
  const q = useDebounced(search.trim(), 300)
  const query = { q: q || undefined, status, category: category || undefined, sort: SORTS[sortKey].sort, order: SORTS[sortKey].order, page, page_size: PAGE_SIZE }
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['vendors', query], queryFn: () => vendorsApi.list(query), placeholderData: (prev) => prev })
  const summary = useQuery({ queryKey: ['vendors-summary'], queryFn: vendorsApi.summary })
  const cats = useQuery({ queryKey: ['vendor-categories'], queryFn: vendorsApi.categories, staleTime: Infinity })
  const label = (id: string) => cats.data?.find((c) => c.id === id)?.label ?? id
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const filtered = !!(q || status || category)
  const change = (fn: () => void) => { fn(); setPage(1) }
  const counts = summary.data?.counts

  return (
    <div className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">Vendors</h1><p className="mt-u4 max-w-xl text-muted">Review new vendors, keep the directory current, and see who can take part in requests for quotation.</p></div>
        <Link to={`${base}/new`}><Button><Plus className="h-4 w-4" aria-hidden /> Register a vendor</Button></Link>
      </header>

      {counts && (
        <section aria-label="Vendor figures" className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard stat={{ id: 'pending', label: 'Waiting for review', value: counts.pending, note: 'Submitted by vendors or staff' }} />
          <StatCard stat={{ id: 'verified', label: 'Verified', value: counts.verified, note: 'Can be invited to RFQs' }} />
          <StatCard stat={{ id: 'draft', label: 'Drafts', value: counts.draft + counts.rejected, note: 'Still being completed or sent back' }} />
          <StatCard stat={{ id: 'suspended', label: 'Suspended', value: counts.suspended, note: 'Blocked from new RFQs' }} />
        </section>
      )}

      <Card>
        <div className="mb-u8 flex flex-wrap gap-u4">
          <label className="relative min-w-[12rem] flex-1"><span className="sr-only">Search vendors</span>
            <Search className="pointer-events-none absolute left-u7 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
            <input type="search" placeholder="Search name, vendor number, tax ID or city" value={search} onChange={(e) => change(() => setSearch(e.target.value))}
              className="h-11 w-full rounded-ctl border border-line bg-surface pl-u17 pr-u6 placeholder:text-muted" /></label>
          <label><span className="sr-only">Filter by status</span>
            <select className={sel} value={status} onChange={(e) => change(() => setStatus(e.target.value as VendorStatus | ''))}><option value="">Any status</option>{VENDOR_STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</select></label>
          <label><span className="sr-only">Filter by category</span>
            <select className={sel} value={category} onChange={(e) => change(() => setCategory(e.target.value))}><option value="">Any category</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
          <label><span className="sr-only">Sort by</span>
            <select className={sel} value={sortKey} onChange={(e) => change(() => setSortKey(e.target.value))}>{Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
        </div>

        {isLoading ? (
          <div role="status" aria-busy="true"><span className="sr-only">Loading vendors</span>{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="mb-u4 h-14 w-full" />)}</div>
        ) : isError || !data ? (
          <ErrorState description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
        ) : data.items.length === 0 ? (
          <EmptyState title={filtered ? 'No vendors match' : 'No vendors yet'} description={filtered ? 'Try a different search or clear a filter.' : 'Register a vendor, or wait for vendors to register themselves.'} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] border-collapse text-left">
                <caption className="sr-only">Vendors, {data.total} in total</caption>
                <thead><tr className="border-b border-line text-sm text-muted">
                  <th scope="col" className="px-u4 py-u4 font-medium">Vendor</th><th scope="col" className="px-u4 py-u4 font-medium">Categories</th>
                  <th scope="col" className="px-u4 py-u4 font-medium">Primary contact</th><th scope="col" className="px-u4 py-u4 font-medium">Status</th>
                </tr></thead>
                <tbody>
                  {data.items.map((v) => (
                    <tr key={v.id} className="border-b border-line last:border-0">
                      <td className="px-u4 py-u4"><button onClick={() => navigate(`${base}/${v.id}`)} className="min-h-[44px] text-left underline-offset-4 hover:underline">
                        <span className="block font-medium">{v.legal_name}</span><span className="block text-sm text-muted">{v.number}, {v.city || 'No city'}</span></button></td>
                      <td className="px-u4 py-u4 text-sm">{v.categories.map(label).join(', ') || <span className="text-muted">None</span>}</td>
                      <td className="px-u4 py-u4 text-sm">{v.primary_contact_name ? <>{v.primary_contact_name}<span className="block break-all text-muted">{v.primary_contact_email}</span></> : <span className="text-muted">None</span>}</td>
                      <td className="px-u4 py-u4"><VendorStatusBadge status={v.status} />{!v.has_account && <span className="mt-u1 block text-xs text-muted">No account yet</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav aria-label="Pagination" className="mt-u8 flex items-center justify-between">
              <p className="text-sm text-muted" aria-live="polite">Page {data.page} of {pages}, {data.total} vendors</p>
              <div className="flex gap-u4"><Button variant="soft" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="soft" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
            </nav>
          </>
        )}
      </Card>
    </div>
  )
}
