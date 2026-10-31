import { useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ClipboardCheck } from 'lucide-react'
import { ApiError, approvalsApi } from '@/services/api'
import { useGsap } from '@/animations/gsap/useGsap'
import { staggerIn } from '@/animations/gsap/presets'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { StatCard } from '@/components/ui/StatCard'
import { ApprovalTimeline } from '@/components/ui/ApprovalTimeline'
import { TrendChart } from '@/components/charts/TrendChart'
import { chainFor } from '@/features/approvals/chain'
import { dateOnly, monthLabel, money } from '@/features/purchase-requests/format'

export default function ManagerDashboard() {
  const navigate = useNavigate()
  const root = useRef<HTMLDivElement>(null)
  const summary = useQuery({ queryKey: ['approvals-summary'], queryFn: approvalsApi.summary })
  const queue = useQuery({ queryKey: ['approvals', 'dashboard-queue'], queryFn: () => approvalsApi.list({ view: 'queue', sort: 'created_at', order: 'asc', page: 1, page_size: 5 }) })
  const oldest = queue.data?.items[0]
  const chain = useQuery({ queryKey: ['approval', oldest?.id], queryFn: () => approvalsApi.get(oldest!.id), enabled: !!oldest })
  const ready = !!summary.data && !!queue.data
  useGsap(root, () => { staggerIn('[data-reveal]', { y: 20, stagger: 0.08 }) }, [ready])

  if (summary.isLoading || queue.isLoading) {
    return (
      <div aria-busy="true" role="status" className="flex flex-col gap-u10">
        <span className="sr-only">Loading dashboard</span>
        <Skeleton className="h-24 w-2/3" />
        <div className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36 rounded-card" />)}</div>
        <Skeleton className="h-80 rounded-card" />
      </div>
    )
  }
  if (summary.isError || queue.isError || !summary.data || !queue.data) {
    const e = summary.error ?? queue.error
    return <ErrorState description={e instanceof ApiError ? e.message : 'Try again in a moment.'} onRetry={() => { void summary.refetch(); void queue.refetch() }} />
  }

  const s = summary.data
  const currencies = Object.keys(s.approved_value_30d)
  const main = currencies.includes('INR') ? 'INR' : currencies[0]
  const avg = s.avg_decision_hours_30d

  return (
    <div ref={root} className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">Approvals</h1><p className="mt-u4 max-w-xl text-muted">Decide what is waiting and keep an eye on how decisions are going.</p></div>
        <Link to="/app/manager/approvals"><Button><ClipboardCheck className="h-4 w-4" aria-hidden /> Open the approval queue</Button></Link>
      </header>

      <section aria-label="Key figures" className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard stat={{ id: 'waiting', label: 'Waiting for you', value: s.waiting_for_me, note: s.delegated_to_me ? `${s.delegated_to_me} delegated to you` : 'Ready for your decision' }} />
        <StatCard stat={{ id: 'overdue', label: 'Overdue', value: s.overdue_for_me, note: 'Waiting longer than expected' }} />
        <StatCard stat={{ id: 'decided', label: 'Decided by you, 30 days', value: s.decided_by_me_30d, note: avg === null ? 'No decisions yet' : `Team average: ${avg} hours` }} />
        <StatCard stat={{ id: 'approved', label: 'Approved, 30 days', value: s.approved_30d, note: main ? `${money(s.approved_value_30d[main], main)} approved` : `${s.rejected_30d} rejected` }} />
      </section>

      <div className="grid gap-u8 lg:grid-cols-3">
        <Card data-reveal className="lg:col-span-2">
          <h2 className="mb-u8 text-2xl">Decisions per month</h2>
          <TrendChart kind="bar" label="Decisions" data={s.monthly.map((m) => ({ name: monthLabel(m.month), value: m.count }))} />
        </Card>
        <Card data-reveal>
          <h2 className="mb-u2 text-2xl">{oldest ? oldest.request_number : 'Nothing waiting'}</h2>
          {oldest && chain.data ? (
            <>
              <p className="mb-u8 text-sm text-muted">{oldest.title}, longest waiting</p>
              <ApprovalTimeline steps={chainFor(chain.data)} />
            </>
          ) : <p className="text-muted">{oldest ? 'Loading the approval route' : 'The queue is clear.'}</p>}
        </Card>
      </div>

      <Card data-reveal>
        <div className="mb-u6 flex items-center justify-between"><h2 className="text-2xl">Waiting for you</h2><Link to="/app/manager/approvals" className="underline-offset-4 hover:underline">See the whole queue</Link></div>
        {queue.data.items.length === 0 ? <EmptyState title="Nothing is waiting for you" description="New requests appear here as soon as employees submit them." /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] border-collapse text-left">
              <caption className="sr-only">Approvals waiting for you, longest waiting first</caption>
              <thead><tr className="border-b border-line text-sm text-muted">
                <th scope="col" className="px-u4 py-u4 font-medium">Request</th><th scope="col" className="px-u4 py-u4 font-medium">Requested by</th>
                <th scope="col" className="px-u4 py-u4 text-right font-medium">Total</th><th scope="col" className="px-u4 py-u4 font-medium">Needed by</th>
              </tr></thead>
              <tbody>
                {queue.data.items.map((a) => (
                  <tr key={a.id} className="border-b border-line last:border-0">
                    <td className="px-u4 py-u4"><button onClick={() => navigate(`/app/manager/approvals/${a.id}`)} className="min-h-[44px] text-left underline-offset-4 hover:underline"><span className="block font-medium">{a.title}</span><span className="block text-sm text-muted">{a.request_number}</span></button></td>
                    <td className="px-u4 py-u4">{a.requester_name}{a.overdue && <Badge tone="bad" className="ml-u3">Overdue</Badge>}</td>
                    <td className="px-u4 py-u4 text-right tabular-nums">{money(a.total_amount, a.currency)}</td>
                    <td className="px-u4 py-u4">{dateOnly(a.needed_by)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
