import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFieldArray, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { ApiError, rfqsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field } from '@/components/forms/Field'
import { TextAreaField } from '@/components/forms/Controls'
import { fromLocalInput, toLocalInput } from './labels'
import type { Rfq } from './types'

const schema = z.object({
  title: z.string().trim().min(3, 'Enter a title of at least 3 characters').max(150, 'Keep it under 150 characters'),
  description: z.string().trim().max(4000, 'Keep it under 4,000 characters'),
  requirements: z.string().trim().max(4000, 'Keep it under 4,000 characters'),
  deadline: z.string().min(1, 'Choose the deadline').refine((v) => !Number.isNaN(new Date(v).getTime()), 'Choose a valid date and time')
    .refine((v) => new Date(v).getTime() > Date.now() + 3_600_000, 'The deadline must be at least one hour from now'),
  items: z.array(z.object({ line_no: z.number(), description: z.string().trim().min(1, 'Describe the item').max(300, 'Keep it under 300 characters'), specification: z.string().trim().max(1000, 'Keep it under 1,000 characters') })),
})
export type RfqFormValues = z.infer<typeof schema>
const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')

interface Props { mode: 'create' | 'edit'; purchaseRequestId?: string; defaultTitle?: string; existing?: Rfq }

/** Creates an RFQ from an approved request, or edits a draft. Quantities and units come from the approved request and are not editable. */
export function RfqForm({ mode, purchaseRequestId, defaultTitle, existing }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { register, control, handleSubmit, formState: { errors } } = useForm<RfqFormValues>({
    resolver: zodResolver(schema),
    defaultValues: existing
      ? { title: existing.title, description: existing.description, requirements: existing.requirements, deadline: toLocalInput(existing.deadline),
          items: existing.items.map((i) => ({ line_no: i.line_no, description: i.description, specification: i.specification ?? '' })) }
      : { title: defaultTitle ?? '', description: '', requirements: '', deadline: '', items: [] },
  })
  const { fields } = useFieldArray({ control, name: 'items' })

  const onSubmit = handleSubmit(async (v) => {
    setError(''); setBusy(true)
    try {
      const items = v.items.map((i) => ({ line_no: i.line_no, description: i.description, specification: i.specification || null }))
      const saved = existing
        ? await rfqsApi.update(existing.id, { version: existing.version, title: v.title, description: v.description, requirements: v.requirements, deadline: fromLocalInput(v.deadline), items })
        : await rfqsApi.create({ purchase_request_id: purchaseRequestId!, title: v.title, description: v.description, requirements: v.requirements, deadline: fromLocalInput(v.deadline), items })
      void qc.invalidateQueries({ queryKey: ['rfq'] }); void qc.invalidateQueries({ queryKey: ['rfqs'] }); void qc.invalidateQueries({ queryKey: ['rfq-eligible'] })
      navigate(`/app/procurement/rfqs/${saved.id}`)
    } catch (e) {
      setError(messageFor(e))
    } finally {
      setBusy(false)
    }
  })

  return (
    <form noValidate onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-u10">
      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">RFQ details</h2>
        <Field label="Title" error={errors.title?.message} {...register('title')} />
        <TextAreaField label="Description (optional)" hint="What vendors are being asked to supply and why." error={errors.description?.message} {...register('description')} />
        <TextAreaField label="Requirements (optional)" hint="Warranty, standards, delivery conditions. Vendors see this." error={errors.requirements?.message} {...register('requirements')} />
        <Field label="Quotation deadline" type="datetime-local" hint="In your local time. Prices stay sealed until this passes or you close the RFQ." error={errors.deadline?.message} {...register('deadline')} />
      </Card>
      {fields.length > 0 && (
        <Card className="flex flex-col gap-u8">
          <h2 className="text-2xl">Items</h2>
          <p className="text-muted">Quantities and units come from the approved request. You can clarify what is being asked for.</p>
          {fields.map((f, i) => {
            const base = existing?.items[i]
            return (
              <div key={f.id} role="group" aria-label={`Item ${f.line_no}`} className="flex flex-col gap-u6 rounded-ctl border border-line p-u7">
                <p className="text-sm text-muted">Item {f.line_no}: {base?.quantity} {base?.unit}</p>
                <Field label={`Item ${f.line_no} description`} error={errors.items?.[i]?.description?.message} {...register(`items.${i}.description`)} />
                <TextAreaField label={`Item ${f.line_no} specification (optional)`} error={errors.items?.[i]?.specification?.message} {...register(`items.${i}.specification`)} />
              </div>
            )
          })}
        </Card>
      )}
      {error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}
      <div className="flex flex-wrap gap-u4">
        <Button type="submit" loading={busy}>{mode === 'create' ? 'Create draft RFQ' : 'Save changes'}</Button>
        <Button type="button" variant="soft" onClick={() => navigate(existing ? `/app/procurement/rfqs/${existing.id}` : '/app/procurement/rfqs')}>Cancel</Button>
      </div>
    </form>
  )
}
