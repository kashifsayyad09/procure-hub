import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useForm, useFieldArray, type FieldErrors } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { Plus, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import { ApiError, purchaseRequestsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { Field } from '@/components/forms/Field'
import { SelectField, TextAreaField } from '@/components/forms/Controls'
import { centsToString, lineTotalCents, money } from '@/features/purchase-requests/format'
import { CURRENCIES, PRIORITIES, type Currency, type Priority, type RequestDetail, type RequestInput } from '@/features/purchase-requests/types'

const localToday = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
const decimal = (places: number) => z.string().trim().regex(new RegExp(`^\\d+(\\.\\d{1,${places}})?$`), places === 3 ? 'Enter a number, up to 3 decimals' : 'Enter an amount, up to 2 decimals')

const itemSchema = z.object({
  description: z.string().trim().min(1, 'Describe the item').max(300, 'Keep it under 300 characters'),
  quantity: decimal(3).refine((v) => Number(v) > 0 && Number(v) <= 1_000_000, 'Must be above zero'),
  unit: z.string().trim().min(1, 'Add a unit').max(20),
  unit_price: decimal(2).refine((v) => Number(v) <= 100_000_000, 'Too large'),
  notes: z.string().max(500, 'Keep it under 500 characters'),
})

export const formSchema = z.object({
  title: z.string().trim().min(3, 'Use at least 3 characters').max(150, 'Keep it under 150 characters'),
  department: z.string().trim().max(80, 'Keep it under 80 characters'),
  priority: z.enum(PRIORITIES as [Priority, ...Priority[]]),
  needed_by: z.string().refine((v) => v === '' || v >= localToday(), 'The date cannot be in the past'),
  currency: z.enum(CURRENCIES as [Currency, ...Currency[]]),
  justification: z.string().trim().max(2000, 'Keep it under 2,000 characters'),
  items: z.array(itemSchema).max(100, 'A request can have at most 100 items'),
})
export type FormValues = z.infer<typeof formSchema>

export const totalCents = (items: FormValues['items']): bigint => items.reduce((sum, i) => sum + (lineTotalCents(i.quantity, i.unit_price) ?? 0n), 0n)

/** What must be fixed before a draft can be submitted (the server checks the same rules). */
export function submitProblems(v: FormValues): string[] {
  const out: string[] = []
  if (!v.department.trim()) out.push('Enter the department.')
  if (!v.justification.trim()) out.push('Explain why this purchase is needed.')
  if (v.items.length === 0) out.push('Add at least one item.')
  else if (totalCents(v.items) <= 0n) out.push('The total must be greater than zero.')
  return out
}

const BLANK: FormValues = { title: '', department: '', priority: 'normal', needed_by: '', currency: 'INR', justification: '', items: [] }
const blankItem = { description: '', quantity: '1', unit: 'each', unit_price: '', notes: '' }
const STEPS = ['Details', 'Items', 'Review']

function toInput(v: FormValues): RequestInput {
  return {
    title: v.title.trim(), department: v.department.trim(), justification: v.justification.trim(), priority: v.priority, currency: v.currency,
    needed_by: v.needed_by || null,
    items: v.items.map((i) => ({ description: i.description.trim(), quantity: i.quantity.trim(), unit: i.unit.trim(), unit_price: i.unit_price.trim(), notes: i.notes.trim() || null })),
  }
}
const fromDetail = (d: RequestDetail): FormValues => ({
  title: d.title, department: d.department, priority: d.priority, needed_by: d.needed_by ?? '', currency: d.currency, justification: d.justification,
  items: d.items.map((i) => ({ description: i.description, quantity: i.quantity, unit: i.unit, unit_price: i.unit_price, notes: i.notes ?? '' })),
})
const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')

function RequestForm({ initial, initialId, initialVersion }: { initial: FormValues; initialId?: string; initialVersion?: number }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [step, setStep] = useState(0)
  const [savedId, setSavedId] = useState(initialId)
  const [version, setVersion] = useState(initialVersion ?? 1)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const { register, control, handleSubmit, trigger, watch, formState: { errors } } = useForm<FormValues>({ resolver: zodResolver(formSchema), defaultValues: initial, mode: 'onTouched' })
  const { fields, append, remove } = useFieldArray({ control, name: 'items' })
  const values = watch()
  const total = totalCents(values.items)
  const problems = submitProblems(values)

  const invalid = (errs: FieldErrors<FormValues>) => {
    setMessage('')
    setError('Fix the highlighted fields before continuing.')
    setStep(errs.items ? 1 : 0)
  }

  const persist = (thenSubmit: boolean) => handleSubmit(async (v) => {
    setError(''); setMessage('')
    if (thenSubmit && submitProblems(v).length) { setError(submitProblems(v).join(' ')); return }
    setBusy(true)
    try {
      const body = toInput(v)
      const saved = savedId ? await purchaseRequestsApi.update(savedId, { ...body, version }) : await purchaseRequestsApi.create(body)
      setSavedId(saved.id); setVersion(saved.version)
      void qc.invalidateQueries({ queryKey: ['requests'] }); void qc.invalidateQueries({ queryKey: ['requests-summary'] }); void qc.invalidateQueries({ queryKey: ['request', saved.id] })
      if (thenSubmit) {
        const sent = await purchaseRequestsApi.submit(saved.id)
        void qc.invalidateQueries({ queryKey: ['request', sent.id] })
        navigate(`/app/employee/requests/${sent.id}`)
        return
      }
      setMessage(`Draft saved as ${saved.number}.`)
    } catch (e) {
      setError(messageFor(e))
    } finally {
      setBusy(false)
    }
  }, invalid)()

  const next = async () => {
    setError(''); setMessage('')
    const ok = step === 0 ? await trigger(['title', 'department', 'priority', 'needed_by', 'currency', 'justification']) : await trigger('items')
    if (ok) setStep((s) => s + 1)
    else setError('Fix the highlighted fields before continuing.')
  }

  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to="/app/employee/requests" className="text-sm text-muted underline-offset-4 hover:underline">Back to my requests</Link>
        <h1 className="display-lg mt-u3">{initialId ? 'Edit draft' : 'New purchase request'}</h1>
      </header>

      <nav aria-label="Progress">
        <ol className="flex flex-wrap gap-u4">
          {STEPS.map((label, i) => (
            <li key={label} aria-current={i === step ? 'step' : undefined}
              className={clsx('flex min-h-[44px] items-center gap-u4 rounded-full px-u8', i === step ? 'bg-accent text-on-accent' : i < step ? 'bg-pill' : 'border border-line text-muted')}>
              <span className="font-medium">{i + 1}</span><span>{label}</span>
            </li>
          ))}
        </ol>
      </nav>

      <form noValidate onSubmit={(e) => e.preventDefault()} className="flex flex-col gap-u10">
        <Card className={clsx('flex flex-col gap-u8', step !== 0 && 'hidden')} aria-label="Details">
          <Field label="Title" placeholder="What do you need?" error={errors.title?.message} {...register('title')} />
          <div className="grid gap-u8 sm:grid-cols-2">
            <Field label="Department" error={errors.department?.message} {...register('department')} />
            <SelectField label="Priority" {...register('priority')}>{PRIORITIES.map((p) => <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>)}</SelectField>
            <Field label="Needed by" type="date" min={localToday()} error={errors.needed_by?.message} {...register('needed_by')} />
            <SelectField label="Currency" {...register('currency')}>{CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}</SelectField>
          </div>
          <TextAreaField label="Why is this needed?" hint="Your manager reads this when deciding." error={errors.justification?.message} {...register('justification')} />
        </Card>

        <div className={clsx('flex flex-col gap-u8', step !== 1 && 'hidden')} aria-label="Items">
          {fields.length === 0 && <Card className="text-center text-muted">No items yet. Add what you need to buy.</Card>}
          {fields.map((f, i) => {
            const e = errors.items?.[i]
            const cents = lineTotalCents(values.items[i]?.quantity ?? '', values.items[i]?.unit_price ?? '')
            return (
              <Card key={f.id} className="flex flex-col gap-u6" role="group" aria-label={`Item ${i + 1}`}>
                <Field label={`Item ${i + 1} description`} error={e?.description?.message} {...register(`items.${i}.description`)} />
                <div className="grid gap-u6 sm:grid-cols-3">
                  <Field label={`Item ${i + 1} quantity`} inputMode="decimal" error={e?.quantity?.message} {...register(`items.${i}.quantity`)} />
                  <Field label={`Item ${i + 1} unit`} error={e?.unit?.message} {...register(`items.${i}.unit`)} />
                  <Field label={`Item ${i + 1} unit price`} inputMode="decimal" error={e?.unit_price?.message} {...register(`items.${i}.unit_price`)} />
                </div>
                <Field label={`Item ${i + 1} notes (optional)`} error={e?.notes?.message} {...register(`items.${i}.notes`)} />
                <div className="flex items-center justify-between">
                  <p className="font-medium" aria-live="polite">Line total: {cents === null ? 'Enter quantity and price' : money(centsToString(cents), values.currency)}</p>
                  <Button variant="ghost" size="sm" onClick={() => remove(i)} aria-label={`Remove item ${i + 1}`}><Trash2 className="h-4 w-4" aria-hidden /> Remove</Button>
                </div>
              </Card>
            )
          })}
          {typeof errors.items?.message === 'string' && <p role="alert" className="text-bad">{errors.items.message}</p>}
          <div className="flex flex-wrap items-center justify-between gap-u6">
            <Button variant="soft" onClick={() => append(blankItem)}><Plus className="h-4 w-4" aria-hidden /> Add item</Button>
            <p className="font-display text-2xl" aria-live="polite">Total {money(centsToString(total), values.currency)}</p>
          </div>
        </div>

        <Card className={clsx('flex flex-col gap-u8', step !== 2 && 'hidden')} aria-label="Review">
          <h2 className="text-2xl">Review</h2>
          <dl className="grid gap-u6 sm:grid-cols-2">
            <div><dt className="text-sm text-muted">Title</dt><dd className="font-medium">{values.title || 'Not set'}</dd></div>
            <div><dt className="text-sm text-muted">Department</dt><dd>{values.department || 'Not set'}</dd></div>
            <div><dt className="text-sm text-muted">Priority</dt><dd className="capitalize">{values.priority}</dd></div>
            <div><dt className="text-sm text-muted">Needed by</dt><dd>{values.needed_by || 'Not set'}</dd></div>
            <div className="sm:col-span-2"><dt className="text-sm text-muted">Reason</dt><dd className="whitespace-pre-wrap">{values.justification || 'Not set'}</dd></div>
            <div><dt className="text-sm text-muted">Items</dt><dd>{values.items.length}</dd></div>
            <div><dt className="text-sm text-muted">Total</dt><dd className="font-medium">{money(centsToString(total), values.currency)}</dd></div>
          </dl>
          {problems.length > 0 ? (
            <div role="status" className="rounded-ctl bg-accent/20 p-u7">
              <p className="font-medium">Before you can submit:</p>
              <ul className="list-disc pl-u10">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          ) : <p className="text-muted">Everything needed to submit is filled in.</p>}
          <p className="text-sm text-muted">You can attach supporting documents on the request page after saving the draft.</p>
        </Card>

        {error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}
        {message && <p role="status" className="rounded-ctl bg-ok/15 p-u7 text-ok">{message}</p>}

        <div className="flex flex-wrap items-center justify-between gap-u6">
          <Button variant="soft" disabled={step === 0 || busy} onClick={() => setStep((s) => s - 1)}>Back</Button>
          <div className="flex flex-wrap gap-u4">
            <Button variant="outline" loading={busy} onClick={() => void persist(false)}>Save draft</Button>
            {step < 2
              ? <Button onClick={() => void next()} disabled={busy}>Next</Button>
              : <Button onClick={() => void persist(true)} loading={busy} disabled={problems.length > 0}>Submit for approval</Button>}
          </div>
        </div>
      </form>
    </div>
  )
}

export default function RequestFormPage() {
  const { id } = useParams()
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['request', id], queryFn: () => purchaseRequestsApi.get(id!), enabled: !!id })
  if (!id) return <RequestForm initial={BLANK} />
  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading request</span><Skeleton className="h-96 rounded-card" /></div>
  if (isError || !data) return <ErrorState title="Could not open this request" description={messageFor(error)} onRetry={() => void refetch()} />
  if (data.status !== 'draft') {
    return (
      <ErrorState title="This request can no longer be edited" description={`Only drafts can be edited. This request is ${data.status}.`} onRetry={undefined} />
    )
  }
  return <RequestForm key={data.id} initial={fromDetail(data)} initialId={data.id} initialVersion={data.version} />
}
