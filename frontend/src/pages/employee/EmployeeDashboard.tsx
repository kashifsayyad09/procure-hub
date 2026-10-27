import { useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { ApiError, purchaseRequestsApi } from '@/services/api'
import { useGsap } from '@/animations/gsap/useGsap'
import { staggerIn } from '@/animations/gsap/presets'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { StatCard } from '@/components/ui/StatCard'
import { ApprovalTimeline } from '@/components/ui/ApprovalTimeline'
import { TrendChart } from '@/components/charts/TrendChart'
import { RequestStatusBadge } from '@/features/purchase-requests/RequestStatusBadge'
import { monthLabel, money } from '@/features/purchase-requests/format'
import { timelineFor } from '@/features/purchase-requests/timeline'

export default function EmployeeDashboard() {
  const navigate = useNavigate()
  const root = useRef<HTMLDivElement>(null)
  const summary = useQuery({ queryKey: ['requests-summary'], queryFn: purchaseRequestsApi.summary })
  const recent = useQuery({ queryKey: ['requests', 'recent'], queryFn: () => purchaseRequestsApi.list({ page: 1, page_size: 5, sort: 'updated_at', order: 'desc' }) })
  const ready = !!summary.data && !!recent.data
  useGsap(root, () => { staggerIn('[data-reveal]', { y: 20, stagger: 0.08 }) }, [ready])

  if (summary.isLoading || recent.isLoading) {
    return (
      <div aria-busy="true" role="status" className="flex flex-col gap-u10">
        <span className="sr-only">Loading dashboard</span>
        <Skeleton className="h-24 w-2/3" />
        <div className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36 rounded-card" />)}</div>
        <Skeleton className="h-80 rounded-card" />
      </div>
    )
  }
  if (summary.isError || recent.isError || !summary.data || !recent.data) {
    const e = summary.error ?? recent.error
    return <ErrorState description={e instanceof ApiError ? e.message : 'Try again in a moment.'} onRetry={() => { void summary.refetch(); void recent.refetch() }} />
  }

  const { counts, open_value: openValue, monthly } = summary.data
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  const currencies = Object.keys(openValue)
  const mainCurrency = currencies.includes('INR') ? 'INR' : currencies[0]
  const latest = recent.data.items.find((r) => r.status !== 'draft') ?? recent.data.items[0]

  return (
    <div ref={root} className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">Your requests</h1><p className="mt-u4 max-w-xl text-muted">See where each purchase stands and what happens next.</p></div>
        <Link to="/app/employee/requests/new"><Button><Plus className="h-4 w-4" aria-hidden /> New purchase request</Button></Link>
      </header>

      {total === 0 ? (
        <Card><EmptyState title="No requests yet" description="Start a request for something you need. You can save it as a draft and finish later."
          action={<Link to="/app/employee/requests/new"><Button>Create your first request</Button></Link>} /></Card>
      ) : (
        <>
          <section aria-label="Key figures" className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard stat={{ id: 'drafts', label: 'Drafts', value: counts.draft, note: 'Not submitted yet' }} />
            <StatCard stat={{ id: 'waiting', label: 'Waiting for approval', value: counts.submitted, note: 'With a manager' }} />
            <StatCard stat={{ id: 'approved', label: 'Approved', value: counts.approved, note: 'Ready for sourcing' }} />
            <StatCard stat={{ id: 'value', label: 'Value awaiting approval', value: mainCurrency ? Math.round(Number(openValue[mainCurrency])) : 0, prefix: mainCurrency ? `${mainCurrency} ` : '',
              note: currencies.length > 1 ? `Also in ${currencies.filter((c) => c !== mainCurrency).join(', ')}` : 'Across waiting requests' }} />
          </section>

          <div className="grid gap-u8 lg:grid-cols-3">
            <Card data-reveal className="lg:col-span-2">
              <h2 className="mb-u8 text-2xl">Requests per month</h2>
              <TrendChart kind="bar" label="Requests" data={monthly.map((m) => ({ name: monthLabel(m.month), value: m.count }))} />
            </Card>
            {latest && (
              <Card data-reveal>
                <h2 className="mb-u2 text-2xl">{latest.number}</h2>
                <p className="mb-u8 text-sm text-muted">{latest.title}</p>
                <ApprovalTimeline steps={timelineFor(latest)} />
              </Card>
            )}
          </div>

          <Card data-reveal>
            <div className="mb-u6 flex items-center justify-between"><h2 className="text-2xl">Recent activity</h2><Link to="/app/employee/requests" className="underline-offset-4 hover:underline">See all requests</Link></div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[34rem] border-collapse text-left">
                <caption className="sr-only">Recently updated requests</caption>
                <thead><tr className="border-b border-line text-sm text-muted"><th scope="col" className="px-u4 py-u4 font-medium">Request</th><th scope="col" className="px-u4 py-u4 text-right font-medium">Total</th><th scope="col" className="px-u4 py-u4 font-medium">Status</th></tr></thead>
                <tbody>
                  {recent.data.items.map((r) => (
                    <tr key={r.id} className="border-b border-line last:border-0">
                      <td className="px-u4 py-u4"><button onClick={() => navigate(`/app/employee/requests/${r.id}`)} className="min-h-[44px] text-left underline-offset-4 hover:underline"><span className="block font-medium">{r.title}</span><span className="block text-sm text-muted">{r.number}</span></button></td>
                      <td className="px-u4 py-u4 text-right tabular-nums">{money(r.total_amount, r.currency)}</td>
                      <td className="px-u4 py-u4"><RequestStatusBadge status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
