import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { ApiError, rfqsApi } from '@/services/api'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { dateOnly, dateTime, money } from '@/features/purchase-requests/format'
import { EvaluateDialog, RevokeDialog, SelectDialog } from '@/features/rfqs/CompareDialogs'
import { QuotationStatusBadge, RfqStatusBadge } from '@/features/rfqs/RfqStatusBadge'
import { CRITERIA, VENDOR_STATUS_LABEL, unitPrice } from '@/features/rfqs/labels'
import type { CompareQuotation, Comparison } from '@/features/rfqs/types'

const SORTS: Record<string, { label: string; fn: (a: CompareQuotation, b: CompareQuotation) => number }> = {
  best: { label: 'Best overall score', fn: (a, b) => (a.rank ?? 99) - (b.rank ?? 99) || Number(a.total_amount) - Number(b.total_amount) },
  price: { label: 'Lowest price', fn: (a, b) => Number(a.total_amount) - Number(b.total_amount) },
  delivery: { label: 'Fastest delivery', fn: (a, b) => (a.lead_time_days ?? 9999) - (b.lead_time_days ?? 9999) },
  name: { label: 'Vendor name', fn: (a, b) => a.vendor_name.localeCompare(b.vendor_name) },
}
const dash = <span className="text-muted">Not available</span>
const score = (v: string | null) => (v === null ? dash : Number(v).toFixed(2))

function Group({ data, currency, list, onEvaluate, onSelect }: { data: Comparison; currency: string; list: CompareQuotation[]; onEvaluate: (q: CompareQuotation) => void; onSelect: (q: CompareQuotation) => void }) {
  const rfqCurrency = data.rfq.currency
  const cell = 'px-u5 py-u4 align-top border-b border-line'
  const head = 'px-u5 py-u4 text-left align-top font-medium text-sm text-muted border-b border-line sticky left-0 bg-surface'
  return (
    <Card className="flex flex-col gap-u6" aria-label={`Quotations in ${currency}`}>
      <h2 className="text-2xl">Quotations in {currency}</h2>
      {currency !== rfqCurrency && <p className="text-sm text-muted">The RFQ budget is in {rfqCurrency}, so these are not compared with it.</p>}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left" style={{ minWidth: `${14 + list.length * 13}rem` }}>
          <caption className="sr-only">Side-by-side comparison of quotations in {currency}</caption>
          <thead><tr>
            <th scope="col" className={head}><span className="sr-only">Measure</span></th>
            {list.map((q) => (
              <th key={q.id} scope="col" className="px-u5 py-u4 text-left align-top border-b border-line">
                <span className="block text-lg font-medium">{q.vendor_name}</span>
                <span className="mt-u2 flex flex-wrap gap-u2"><QuotationStatusBadge status={q.status} />
                  {q.lowest_price && <Badge tone="ok">Lowest price</Badge>}{q.fastest && <Badge tone="accent">Fastest</Badge>}</span>
              </th>
            ))}
          </tr></thead>
          <tbody>
            <tr><th scope="row" className={head}>Rank</th>{list.map((q) => <td key={q.id} className={cell}>{q.rank ? `#${q.rank}` : dash}</td>)}</tr>
            <tr><th scope="row" className={head}>Overall score</th>{list.map((q) => <td key={q.id} className={`${cell} text-lg font-medium`}>{score(q.scores.total)}</td>)}</tr>
            <tr><th scope="row" className={head}>Total</th>{list.map((q) => <td key={q.id} className={`${cell} font-medium`}>{money(unitPrice(q.total_amount), q.currency)}{!q.complete && <span className="block text-sm text-muted">Partial: some items not quoted</span>}</td>)}</tr>
            <tr><th scope="row" className={head}>Against budget</th>{list.map((q) => <td key={q.id} className={cell}>{q.within_budget === null ? dash : q.within_budget ? 'Within budget' : <span className="text-bad">Over budget</span>}</td>)}</tr>
            <tr><th scope="row" className={head}>Delivery lead time</th>{list.map((q) => <td key={q.id} className={cell}>{q.lead_time_days ? `${q.lead_time_days} days` : dash}</td>)}</tr>
            <tr><th scope="row" className={head}>Valid until</th>{list.map((q) => <td key={q.id} className={cell}>{q.valid_until ? dateOnly(q.valid_until) : dash}</td>)}</tr>
            <tr><th scope="row" className={head}>Payment terms</th>{list.map((q) => <td key={q.id} className={cell}>{q.payment_terms_days === null ? dash : q.payment_terms_days === 0 ? 'On delivery' : `Net ${q.payment_terms_days} days`}</td>)}</tr>
            <tr><th scope="row" className={head}>Vendor status</th>{list.map((q) => (
              <td key={q.id} className={cell}>{q.vendor_status === null ? <span className="text-muted">Could not be checked</span> : q.vendor_status === 'verified' ? <Badge tone="ok">Verified</Badge> : <Badge tone="bad">{VENDOR_STATUS_LABEL[q.vendor_status] ?? q.vendor_status}</Badge>}</td>))}</tr>
            {data.rfq.items.map((it) => (
              <tr key={it.id}><th scope="row" className={head}>Item {it.line_no}: {it.description}<span className="block font-normal">{it.quantity.replace(/\.?0+$/, '')} {it.unit}</span></th>
                {list.map((q) => {
                  const line = q.lines.find((l) => l.rfq_item_id === it.id)
                  return <td key={q.id} className={cell}>{line?.unit_price == null ? <span className="text-bad">Not quoted</span> : <>{money(unitPrice(line.unit_price), q.currency)} each<span className="block text-sm text-muted">{money(line.line_total ?? '0', q.currency)}</span></>}</td>
                })}</tr>
            ))}
            {CRITERIA.map((c) => (
              <tr key={c.key}><th scope="row" className={head}>{c.label} score<span className="block font-normal">{c.key === 'price' || c.key === 'delivery' ? 'Calculated' : 'Entered by the evaluator'}</span></th>
                {list.map((q) => <td key={q.id} className={cell}>{score(q.scores[c.key])}</td>)}</tr>
            ))}
            <tr><th scope="row" className={head}>Missing from the score</th>{list.map((q) => <td key={q.id} className={`${cell} text-sm`}>{q.scores.missing.length ? q.scores.missing.join(', ') : 'Nothing'}</td>)}</tr>
            <tr><th scope="row" className={head}>Evaluation notes</th>{list.map((q) => (
              <td key={q.id} className={`${cell} text-sm`}>{q.evaluation ? <>{q.evaluation.compliance_note && <p>Compliance: {q.evaluation.compliance_note}</p>}{q.evaluation.terms_note && <p>Terms: {q.evaluation.terms_note}</p>}<p className="text-muted">By {q.evaluation.evaluator_name}</p></> : <span className="text-muted">Not evaluated</span>}</td>))}</tr>
            <tr><th scope="row" className={head}>Vendor's commercial terms</th>{list.map((q) => <td key={q.id} className={`${cell} whitespace-pre-wrap text-sm`}>{q.terms || <span className="text-muted">None given</span>}</td>)}</tr>
            <tr><th scope="row" className={head}>Actions</th>{list.map((q) => (
              <td key={q.id} className={cell}><div className="flex flex-col gap-u3">
                {!data.selection && <Button variant="soft" size="sm" aria-label={`Evaluate ${q.vendor_name}`} onClick={() => onEvaluate(q)}>{q.evaluation ? 'Change evaluation' : 'Evaluate'}</Button>}
                {data.can_select && <Button size="sm" aria-label={`Select ${q.vendor_name}`} onClick={() => onSelect(q)}>Select this supplier</Button>}
                {data.selection?.quotation_id === q.id && <Badge tone="ok">Selected</Badge>}</div></td>))}</tr>
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export default function RfqComparePage() {
  const { id = '' } = useParams()
  const [sortKey, setSortKey] = useState('best')
  const [completeOnly, setCompleteOnly] = useState(false)
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [evaluating, setEvaluating] = useState<CompareQuotation | null>(null)
  const [selecting, setSelecting] = useState<CompareQuotation | null>(null)
  const [revoking, setRevoking] = useState(false)
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['comparison', id], queryFn: () => rfqsApi.comparison(id), retry: false })
  const history = useQuery({ queryKey: ['comparison', id, 'history'], queryFn: () => rfqsApi.selectionHistory(id), enabled: !!data })

  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading comparison</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (isError || !data) {
    const sealed = error instanceof ApiError && error.status === 409
    return <ErrorState title={sealed ? 'Quotations are not open yet' : 'Could not load the comparison'} description={error instanceof ApiError ? error.message : 'Try again in a moment.'} onRetry={sealed ? undefined : () => void refetch()} />
  }
  const visible = data.quotations.filter((q) => (!completeOnly || q.complete) && (!verifiedOnly || q.vendor_status === 'verified'))
  const sel = data.selection

  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to={`/app/procurement/rfqs/${data.rfq.id}`} className="text-sm text-muted underline-offset-4 hover:underline">Back to the RFQ</Link>
        <div className="mt-u3 flex flex-wrap items-center gap-u5"><h1 className="display-lg">Compare quotations</h1><RfqStatusBadge status={data.rfq.status} /></div>
        <p className="mt-u4 text-muted">{data.rfq.number}, {data.rfq.title}. Budget {money(data.rfq.budget_amount, data.rfq.currency)}. Deadline {dateTime(data.rfq.deadline)}.</p>
      </header>

      {data.note && <p role="note" className="flex gap-u4 rounded-ctl bg-accent/20 p-u7"><AlertTriangle className="mt-[2px] h-5 w-5 shrink-0" aria-hidden />{data.note}</p>}
      {!data.vendor_info_available && data.quotations.length > 0 && <p role="note" className="rounded-ctl bg-bad/15 p-u7 text-bad">Vendor status could not be checked just now. You can still compare, but selecting a supplier needs the check, so try again in a moment.</p>}

      {sel && (
        <Card aria-label="Award" className="flex flex-col gap-u4">
          <div className="flex flex-wrap items-center justify-between gap-u5"><h2 className="text-2xl">Awarded to {sel.vendor_name}</h2>{data.can_revoke && <Button variant="outline" onClick={() => setRevoking(true)}>Revoke award</Button>}</div>
          <p>{money(unitPrice(sel.total_amount), sel.currency)}. Selected by {sel.selected_by_name} on {dateTime(sel.selected_at)}.</p>
          <p className="text-muted">{sel.justification}</p>
        </Card>
      )}

      <Card className="flex flex-col gap-u5">
        <h2 className="text-xl">How the score works</h2>
        <ul className="grid gap-u4 sm:grid-cols-2">{CRITERIA.map((c) => <li key={c.key}><p className="font-medium">{c.label}, {data.weights[c.key]}%</p><p className="text-sm text-muted">{c.how}</p></li>)}</ul>
        <p className="text-sm text-muted">The overall score appears once both evaluator scores are entered. Only complete quotations are scored on price and delivery, and quotations are only compared within the same currency. Nothing is converted.</p>
      </Card>

      {data.quotations.length === 0 ? <Card className="text-center text-muted">No quotations were submitted for this RFQ.</Card> : (
        <>
          <div className="flex flex-wrap items-center gap-u6" role="group" aria-label="Comparison options">
            <label><span className="sr-only">Sort by</span><select className="h-11 rounded-ctl border border-line bg-surface px-u6" value={sortKey} onChange={(e) => setSortKey(e.target.value)}>{Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
            <label className="flex min-h-[44px] items-center gap-u4"><input type="checkbox" className="h-5 w-5" checked={completeOnly} onChange={(e) => setCompleteOnly(e.target.checked)} />Complete quotations only</label>
            <label className="flex min-h-[44px] items-center gap-u4"><input type="checkbox" className="h-5 w-5" checked={verifiedOnly} onChange={(e) => setVerifiedOnly(e.target.checked)} />Verified vendors only</label>
          </div>
          {visible.length === 0 ? <Card className="text-center text-muted">No quotations match these options.</Card>
            : data.currencies.map((cur) => {
              const list = visible.filter((q) => q.currency === cur).sort(SORTS[sortKey].fn)
              return list.length ? <Group key={cur} data={data} currency={cur} list={list} onEvaluate={setEvaluating} onSelect={setSelecting} /> : null
            })}
        </>
      )}

      {history.data && history.data.items.length > 0 && (
        <Card className="flex flex-col gap-u6" aria-label="Selection history">
          <h2 className="text-2xl">Selection history</h2>
          <ol className="flex flex-col gap-u6">{history.data.items.map((h) => (
            <li key={h.id} className="border-l-2 border-line pl-u7"><p className="font-medium">{h.vendor_name}: {h.status === 'awarded' ? 'awarded' : 'award revoked'}</p>
              <p className="text-sm text-muted">Selected by {h.selected_by_name}, {dateTime(h.selected_at)}</p><p>{h.justification}</p>
              {h.status === 'revoked' && <p className="text-sm text-muted">Revoked by {h.revoked_by_name}{h.revoked_at ? `, ${dateTime(h.revoked_at)}` : ''}: {h.revoke_reason}</p>}</li>
          ))}</ol>
        </Card>
      )}

      <EvaluateDialog key={evaluating?.id ?? 'none'} rfqId={id} q={evaluating} onClose={() => setEvaluating(null)} />
      <SelectDialog key={`s-${selecting?.id ?? 'none'}`} rfqId={id} q={selecting} onClose={() => setSelecting(null)} />
      <RevokeDialog rfqId={id} open={revoking} vendorName={sel?.vendor_name ?? ''} onClose={() => setRevoking(false)} />
    </div>
  )
}
