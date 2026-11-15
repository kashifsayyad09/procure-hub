import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { ApiError, quotationsApi, rfqsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { Field } from '@/components/forms/Field'
import { SelectField, TextAreaField } from '@/components/forms/Controls'
import { dateOnly, money } from '@/features/purchase-requests/format'
import { centsText, isPrice, lineCents } from '@/features/rfqs/money'
import { QuotationStatusBadge } from '@/features/rfqs/RfqStatusBadge'
import { unitPrice } from '@/features/rfqs/labels'
import { CURRENCIES, type Quotation, type QuotationInput, type VendorRfq } from '@/features/rfqs/types'

const schema = z.object({
  currency: z.enum(CURRENCIES as [string, ...string[]]),
  lead_time_days: z.string().trim().refine((v) => v === '' || (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 730), 'Enter a whole number of days from 1 to 730'),
  valid_until: z.string().refine((v) => v === '' || !Number.isNaN(new Date(v).getTime()), 'Choose a valid date'),
  payment_terms_days: z.string().trim().refine((v) => v === '' || (/^\d+$/.test(v) && Number(v) <= 365), 'Enter a whole number of days from 0 to 365'),
  terms: z.string().trim().max(4000, 'Keep it under 4,000 characters'),
  lines: z.array(z.object({ rfq_item_id: z.string(), price: z.string().trim().refine((v) => v === '' || isPrice(v), 'Enter a price with up to 4 decimals, for example 1250.50'), note: z.string().trim().max(300, 'Keep it under 300 characters') })),
})
type Values = z.infer<typeof schema>

const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')
const today = () => new Date().toISOString().slice(0, 10)

/** What still stops this quotation being submitted, using the server's rules. The server checks them again. */
export function problemsFor(v: Values, rfq: VendorRfq): string[] {
  const out: string[] = []
  if (!v.lead_time_days) out.push('Enter the delivery lead time in days.')
  if (!v.valid_until) out.push('Enter how long the quotation is valid.')
  else if (v.valid_until < today() || v.valid_until < rfq.deadline.slice(0, 10)) out.push('The quotation must stay valid at least until the RFQ deadline.')
  if (!v.lines.some((l) => l.price !== '')) out.push('Price at least one item.')
  return out
}

function ReadOnly({ q, rfq }: { q: Quotation; rfq: VendorRfq }) {
  return (
    <Card className="flex flex-col gap-u8">
      <div className="flex flex-wrap items-center gap-u5"><h2 className="text-2xl">{q.number}</h2><QuotationStatusBadge status={q.status} /></div>
      <dl className="grid gap-u6 sm:grid-cols-2">
        <div><dt className="text-sm text-muted">Total</dt><dd className="font-medium">{money(unitPrice(q.total_amount), q.currency)}</dd></div>
        <div><dt className="text-sm text-muted">Delivery lead time</dt><dd>{q.lead_time_days} days</dd></div>
        <div><dt className="text-sm text-muted">Valid until</dt><dd>{q.valid_until ? dateOnly(q.valid_until) : 'Not set'}</dd></div>
        <div><dt className="text-sm text-muted">Payment terms</dt><dd>{q.payment_terms_days === null ? 'Not set' : `Net ${q.payment_terms_days} days`}</dd></div>
        <div className="sm:col-span-2"><dt className="text-sm text-muted">Commercial terms</dt><dd className="whitespace-pre-wrap">{q.terms || 'None'}</dd></div>
      </dl>
      <div className="overflow-x-auto"><table className="w-full min-w-[30rem] border-collapse text-left"><caption className="sr-only">Quoted items</caption>
        <thead><tr className="border-b border-line text-sm text-muted"><th scope="col" className="px-u4 py-u3 font-medium">Item</th><th scope="col" className="px-u4 py-u3 font-medium">Unit price</th><th scope="col" className="px-u4 py-u3 font-medium">Line total</th></tr></thead>
        <tbody>{q.items.map((l) => (<tr key={l.rfq_item_id} className="border-b border-line last:border-0"><td className="px-u4 py-u3">{rfq.items.find((i) => i.id === l.rfq_item_id)?.description ?? `Item ${l.line_no}`}</td>
          <td className="px-u4 py-u3">{l.unit_price === null ? <span className="text-muted">Not quoted</span> : money(unitPrice(l.unit_price), q.currency)}</td><td className="px-u4 py-u3">{l.line_total === null ? '' : money(l.line_total, q.currency)}</td></tr>))}</tbody></table></div>
    </Card>
  )
}

function Form({ rfq, existing }: { rfq: VendorRfq; existing?: Quotation }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { register, handleSubmit, watch, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      currency: existing?.currency ?? rfq.currency, lead_time_days: existing?.lead_time_days?.toString() ?? '', valid_until: existing?.valid_until ?? '',
      payment_terms_days: existing?.payment_terms_days?.toString() ?? '', terms: existing?.terms ?? '',
      lines: rfq.items.map((i) => { const l = existing?.items.find((x) => x.rfq_item_id === i.id); return { rfq_item_id: i.id, price: l?.unit_price ? unitPrice(l.unit_price) : '', note: l?.note ?? '' } }),
    },
  })
  const v = watch()
  const problems = problemsFor(v, rfq)
  let cents = 0n
  const lineTexts = rfq.items.map((it, i) => { const c = v.lines?.[i]?.price ? lineCents(it.quantity, v.lines[i].price) : null; if (c !== null) cents += c; return c === null ? null : centsText(c) })

  const toInput = (x: Values): QuotationInput => ({
    currency: x.currency as QuotationInput['currency'], lead_time_days: x.lead_time_days ? Number(x.lead_time_days) : null, valid_until: x.valid_until || null,
    payment_terms_days: x.payment_terms_days ? Number(x.payment_terms_days) : null, terms: x.terms,
    items: x.lines.map((l) => ({ rfq_item_id: l.rfq_item_id, unit_price: l.price || null, note: l.note || null })),
  })
  const save = (thenSubmit: boolean) => handleSubmit(async (x) => {
    setError('')
    if (thenSubmit && problemsFor(x, rfq).length) { setError(problemsFor(x, rfq).join(' ')); return }
    setBusy(true)
    try {
      const saved = existing ? await quotationsApi.update(existing.id, existing.version, toInput(x)) : await quotationsApi.create(rfq.id, toInput(x))
      if (thenSubmit) await quotationsApi.submit(saved.id)
      void qc.invalidateQueries({ queryKey: ['rfq'] }); void qc.invalidateQueries({ queryKey: ['quotation'] })
      navigate(`/app/vendor/rfqs/${rfq.id}`)
    } catch (e) {
      setError(messageFor(e))
    } finally {
      setBusy(false)
    }
  }, () => setError('Fix the highlighted fields first.'))()

  return (
    <form noValidate onSubmit={(e) => e.preventDefault()} className="flex flex-col gap-u10">
      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">Prices</h2>
        <p className="text-muted">Enter your price for each unit. Leave an item empty if you cannot supply it: buyers will see it as not quoted.</p>
        <div className="overflow-x-auto"><table className="w-full min-w-[36rem] border-collapse text-left"><caption className="sr-only">Prices for each item</caption>
          <thead><tr className="border-b border-line text-sm text-muted"><th scope="col" className="px-u4 py-u3 font-medium">Item</th><th scope="col" className="px-u4 py-u3 font-medium">Quantity</th>
            <th scope="col" className="px-u4 py-u3 font-medium">Unit price ({v.currency})</th><th scope="col" className="px-u4 py-u3 font-medium">Line total</th></tr></thead>
          <tbody>{rfq.items.map((it, i) => (
            <tr key={it.id} className="border-b border-line align-top last:border-0">
              <td className="px-u4 py-u4">{it.description}{it.specification && <span className="block text-sm text-muted">{it.specification}</span>}</td>
              <td className="px-u4 py-u4">{it.quantity.replace(/\.?0+$/, '')} {it.unit}</td>
              <td className="px-u4 py-u4"><Field label={`Unit price for item ${it.line_no}`} inputMode="decimal" error={errors.lines?.[i]?.price?.message} {...register(`lines.${i}.price`)} /></td>
              <td className="px-u4 py-u4">{lineTexts[i] ? money(lineTexts[i]!, v.currency) : <span className="text-muted">Not quoted</span>}</td>
            </tr>))}</tbody></table></div>
        <p className="text-lg font-medium" aria-live="polite">Total: {money(centsText(cents), v.currency)}</p>
        <p className="text-sm text-muted">This total is a preview. The server calculates the official total when you save.</p>
      </Card>
      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">Terms</h2>
        <div className="grid gap-u8 sm:grid-cols-2">
          <SelectField label="Currency" hint="You can quote in a currency other than the buyer's." {...register('currency')}>{CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}</SelectField>
          <Field label="Delivery lead time (days)" inputMode="numeric" error={errors.lead_time_days?.message} {...register('lead_time_days')} />
          <Field label="Quotation valid until" type="date" hint={`At least until the deadline, ${dateOnly(rfq.deadline)}.`} error={errors.valid_until?.message} {...register('valid_until')} />
          <Field label="Payment terms (days)" inputMode="numeric" hint="Days after invoice. Leave empty if not specified." error={errors.payment_terms_days?.message} {...register('payment_terms_days')} />
        </div>
        <TextAreaField label="Commercial terms (optional)" hint="Warranty, delivery, packaging, anything the buyer should know." error={errors.terms?.message} {...register('terms')} />
      </Card>
      {problems.length > 0 && <div role="status" className="rounded-ctl bg-accent/20 p-u7"><p className="font-medium">Before you can submit:</p><ul className="list-disc pl-u10">{problems.map((p) => <li key={p}>{p}</li>)}</ul><p className="mt-u3 text-sm text-muted">You can still save a draft and come back.</p></div>}
      {error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}
      <div className="flex flex-wrap gap-u4">
        <Button variant="soft" loading={busy} onClick={() => void save(false)}>Save draft</Button>
        <Button loading={busy} disabled={problems.length > 0} onClick={() => void save(true)}>Submit quotation</Button>
        <Link to={`/app/vendor/rfqs/${rfq.id}`}><Button variant="ghost">Cancel</Button></Link>
      </div>
    </form>
  )
}

export default function QuotationFormPage() {
  const { id = '' } = useParams()
  const rfqQ = useQuery({ queryKey: ['rfq', 'invited', 'one', id], queryFn: () => rfqsApi.invitedRfq(id), retry: false })
  const qId = rfqQ.data?.quotation?.id
  const quoteQ = useQuery({ queryKey: ['quotation', qId], queryFn: () => quotationsApi.get(qId!), enabled: !!qId })
  if (rfqQ.isLoading || (qId && quoteQ.isLoading)) return <div role="status" aria-busy="true"><span className="sr-only">Loading quotation</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (rfqQ.isError || !rfqQ.data) return <ErrorState title="Could not open this request" description={rfqQ.error instanceof ApiError ? rfqQ.error.message : 'Try again in a moment.'} onRetry={() => void rfqQ.refetch()} />
  if (qId && (quoteQ.isError || !quoteQ.data)) return <ErrorState title="Could not open your quotation" description={quoteQ.error instanceof ApiError ? quoteQ.error.message : 'Try again in a moment.'} onRetry={() => void quoteQ.refetch()} />
  const rfq = rfqQ.data
  const q = quoteQ.data
  const editable = q ? q.can_edit : rfq.can_quote
  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to={`/app/vendor/rfqs/${rfq.id}`} className="text-sm text-muted underline-offset-4 hover:underline">Back to the request</Link>
        <h1 className="display-lg mt-u3">{q ? (editable ? 'Edit your quotation' : 'Your quotation') : 'Your quotation'}</h1>
        <p className="mt-u4 text-muted">{rfq.number}, {rfq.title}</p>
      </header>
      {!editable && !q && <ErrorState title="You cannot send a quotation" description={rfq.blocked_reason ?? 'This request is not taking quotations.'} />}
      {!editable && q && <><p role="status" className="text-muted">{q.status === 'submitted' ? 'This quotation is submitted. Go back and choose Withdraw to make changes before the deadline.' : rfq.blocked_reason ?? 'This quotation can no longer be changed.'}</p><ReadOnly q={q} rfq={rfq} /></>}
      {editable && <Form key={q?.version ?? 'new'} rfq={rfq} existing={q} />}
    </div>
  )
}
