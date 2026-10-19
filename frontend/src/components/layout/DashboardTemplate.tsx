import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { gsap } from '@/animations/gsap'
import { useGsap } from '@/animations/gsap/useGsap'
import { staggerIn } from '@/animations/gsap/presets'
import { fetchDashboard } from '@/services/mockData'
import { roleById, type Role } from '@/types/roles'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/Badge'
import { ApprovalTimeline } from '@/components/ui/ApprovalTimeline'
import { Drawer, Modal } from '@/components/ui/Overlay'
import { DataTable, type Row } from '@/components/tables/DataTable'
import { TrendChart } from '@/components/charts/TrendChart'

function Loading() {
  return (
    <div aria-busy="true" aria-live="polite" className="flex flex-col gap-u10">
      <span className="sr-only">Loading dashboard</span>
      <Skeleton className="h-24 w-2/3" />
      <div className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36 rounded-card" />)}</div>
      <div className="grid gap-u8 lg:grid-cols-3"><Skeleton className="h-80 rounded-card lg:col-span-2" /><Skeleton className="h-80 rounded-card" /></div>
    </div>
  )
}

export function DashboardTemplate({ role }: { role: Role }) {
  const info = roleById(role)!
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['dashboard', role], queryFn: () => fetchDashboard(role) })
  const root = useRef<HTMLDivElement>(null)
  const [selected, setSelected] = useState<Row | null>(null)
  const [action, setAction] = useState<{ label: string; phase: number } | null>(null)

  useGsap(root, () => {
    staggerIn('[data-reveal]', { y: 20, stagger: 0.08 })
    gsap.from('[data-headline]', { opacity: 0, y: 12, duration: 0.5, ease: 'power3.out' })
  }, [data?.headline])

  if (isLoading) return <Loading />
  if (isError || !data) return <ErrorState description={(error as Error | null)?.message ?? 'Try again in a moment.'} onRetry={() => void refetch()} />

  const statusKey = data.table.columns.find((c) => c.status)?.key
  const columns = data.table.columns.map((c) => ({
    key: c.key,
    header: c.header,
    align: c.right ? ('right' as const) : undefined,
    render: c.status ? (r: Row) => <StatusBadge status={String(r[c.key])} /> : undefined,
  }))

  return (
    <div ref={root} className="flex flex-col gap-u12">
      <header data-headline className="flex flex-wrap items-end justify-between gap-u8">
        <div>
          <h1 className="display-lg">{data.headline}</h1>
          <p className="mt-u4 max-w-xl text-muted">{data.intro}</p>
        </div>
        <div className="flex flex-wrap gap-u4">
          {data.actions.map((a, i) => <Button key={a.label} variant={i === 0 ? 'primary' : 'soft'} onClick={() => setAction(a)}>{a.label}</Button>)}
        </div>
      </header>

      <section aria-label="Key figures" className="grid gap-u8 sm:grid-cols-2 xl:grid-cols-4">
        {data.stats.map((s) => <StatCard key={s.id} stat={s} />)}
      </section>

      <div className="grid gap-u8 lg:grid-cols-3">
        <Card data-reveal className="lg:col-span-2">
          <h2 className="mb-u8 text-2xl">{data.trend.title}</h2>
          <TrendChart kind={data.trend.kind} data={data.trend.points} unit={data.trend.unit} label={data.trend.label} />
        </Card>
        <Card data-reveal>
          <h2 className="mb-u10 text-2xl">{data.timeline.title}</h2>
          <ApprovalTimeline steps={data.timeline.steps} />
        </Card>
      </div>

      <Card data-reveal>
        <h2 className="mb-u8 text-2xl">{data.table.title}</h2>
        <DataTable caption={data.table.title} columns={columns} rows={data.table.rows} filterKey={statusKey} onRowClick={setSelected} />
      </Card>
      <p className="text-sm text-muted">Figures on this page are sample data for the {info.label.toLowerCase()} layout.</p>

      <Drawer open={!!selected} onClose={() => setSelected(null)} title={selected ? String(selected[data.table.columns[0].key]) : 'Details'}>
        <dl className="flex flex-col gap-u6">
          {selected && data.table.columns.map((c) => (
            <div key={c.key}><dt className="text-sm text-muted">{c.header}</dt><dd className="font-medium">{c.status ? <StatusBadge status={String(selected[c.key])} /> : selected[c.key]}</dd></div>
          ))}
        </dl>
      </Drawer>

      <Modal open={!!action} onClose={() => setAction(null)} title={action?.label ?? ''} footer={<Button onClick={() => setAction(null)}>Got it</Button>}>
        <p>This workflow is built in Phase {action?.phase}. The dashboard layout is ready for it, so nothing here will move when it arrives.</p>
      </Modal>
    </div>
  )
}
