import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Building2, CheckCircle2, Circle } from 'lucide-react'
import { ApiError, vendorsApi } from '@/services/api'
import { useGsap } from '@/animations/gsap/useGsap'
import { staggerIn } from '@/animations/gsap/presets'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { VendorStatusBadge } from '@/features/vendors/VendorStatusBadge'
import { STATUS_HELP } from '@/features/vendors/labels'

const NEXT_STEPS = [
  'Quotations arrive in Phase 6: you will answer requests for quotation here.',
  'Purchase orders arrive in Phase 7: confirm orders here.',
]

export default function VendorDashboard() {
  const root = useRef<HTMLDivElement>(null)
  const mine = useQuery({ queryKey: ['vendor', 'me'], queryFn: vendorsApi.mine, retry: false })
  useGsap(root, () => { staggerIn('[data-reveal]', { y: 20, stagger: 0.08 }) }, [mine.isSuccess, mine.isError])

  if (mine.isLoading) return <div aria-busy="true" role="status" className="flex flex-col gap-u10"><span className="sr-only">Loading dashboard</span><Skeleton className="h-24 w-2/3" /><Skeleton className="h-64 rounded-card" /></div>
  const notRegistered = mine.error instanceof ApiError && mine.error.status === 404
  if (mine.isError && !notRegistered) return <ErrorState description={mine.error instanceof ApiError ? mine.error.message : 'Try again in a moment.'} onRetry={() => void mine.refetch()} />

  if (notRegistered || !mine.data) {
    return (
      <div ref={root} className="flex flex-col gap-u12">
        <header><h1 className="display-lg">Welcome</h1><p className="mt-u4 max-w-xl text-muted">Register your company to start working with buyers on ProcureHub.</p></header>
        <Card data-reveal className="flex flex-col items-start gap-u6">
          <Building2 className="h-8 w-8 text-muted" aria-hidden />
          <h2 className="text-2xl">You have not registered yet</h2>
          <p className="max-w-xl text-muted">It takes a few minutes. You can save a draft and finish later.</p>
          <Link to="/app/vendor/profile/edit"><Button>Register your company</Button></Link>
        </Card>
      </div>
    )
  }

  const v = mine.data
  const steps = [
    { done: true, text: 'Company registered' },
    { done: v.completeness.percent === 100, text: v.completeness.percent === 100 ? 'Profile complete' : `Still missing: ${v.completeness.missing.join(', ')}` },
    { done: v.status === 'pending' || v.status === 'verified' || v.status === 'suspended', text: 'Submitted for verification' },
    { done: v.status === 'verified', text: 'Verified by procurement' },
  ]
  return (
    <div ref={root} className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">{v.trade_name || v.legal_name}</h1><p className="mt-u4 max-w-xl text-muted">{STATUS_HELP[v.status]}</p></div>
        <Link to="/app/vendor/profile"><Button>Open your profile</Button></Link>
      </header>
      <div className="grid gap-u8 lg:grid-cols-3">
        <Card data-reveal className="lg:col-span-2">
          <div className="mb-u8 flex flex-wrap items-center gap-u5"><h2 className="text-2xl">Getting verified</h2><VendorStatusBadge status={v.status} /></div>
          <div className="mb-u8">
            <div className="mb-u3 flex justify-between text-sm"><span>Profile completeness</span><span>{v.completeness.percent}%</span></div>
            <div role="progressbar" aria-label="Profile completeness" aria-valuemin={0} aria-valuemax={100} aria-valuenow={v.completeness.percent} className="h-3 overflow-hidden rounded-full bg-pill">
              <div className="h-full rounded-full bg-accent" style={{ width: `${v.completeness.percent}%` }} />
            </div>
          </div>
          <ul className="flex flex-col gap-u5">
            {steps.map((s) => (
              <li key={s.text} className="flex items-start gap-u5">
                {s.done ? <CheckCircle2 className="mt-[2px] h-5 w-5 text-ok" aria-label="Done" /> : <Circle className="mt-[2px] h-5 w-5 text-muted" aria-label="Not done" />}
                <span>{s.text}</span>
              </li>
            ))}
          </ul>
          {v.status_note && (v.status === 'rejected' || v.status === 'suspended') && <p role="note" className="mt-u8 rounded-ctl bg-bad/15 p-u7 text-bad">{v.status_note}</p>}
        </Card>
        <Card data-reveal>
          <h2 className="mb-u6 text-2xl">Coming next</h2>
          <ul className="flex flex-col gap-u5 text-muted">{NEXT_STEPS.map((t) => <li key={t}>{t}</li>)}</ul>
        </Card>
      </div>
    </div>
  )
}
