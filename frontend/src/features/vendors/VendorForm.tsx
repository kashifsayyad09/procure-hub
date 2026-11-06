import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFieldArray, useForm, type FieldErrors } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { Plus, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import { ApiError, vendorsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field } from '@/components/forms/Field'
import { SelectField, TextAreaField } from '@/components/forms/Controls'
import { COUNTRIES, PAYMENT_TERMS, paymentTerms } from './labels'
import type { Currency, VendorDetail, VendorInput } from './types'

const CURRENCIES: Currency[] = ['INR', 'USD', 'EUR', 'GBP']
const EMAIL = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/
const PHONE = /^\+?[0-9][0-9 ()\-.]{4,28}$/

const contactSchema = z.object({
  name: z.string().trim().min(1, 'Enter the contact’s name').max(120, 'Keep it under 120 characters'),
  job_title: z.string().trim().max(80, 'Keep it under 80 characters'),
  email: z.string().trim().max(254).regex(EMAIL, 'Enter a valid email address'),
  phone: z.string().trim().refine((v) => v === '' || PHONE.test(v), 'Enter a valid phone number, for example +91 98765 43210'),
})

export const formSchema = z.object({
  legal_name: z.string().trim().min(2, 'Enter the registered company name').max(200, 'Keep it under 200 characters'),
  trade_name: z.string().trim().max(200, 'Keep it under 200 characters'),
  tax_id: z.string().trim().refine((v) => v === '' || /^[A-Za-z0-9 -]{5,40}$/.test(v) && v.replace(/[^A-Za-z0-9]/g, '').length >= 5, 'Enter a tax ID of 5 to 30 letters and digits'),
  registration_number: z.string().trim().max(50, 'Keep it under 50 characters'),
  website: z.string().trim().refine((v) => v === '' || /^https?:\/\/\S+$/i.test(v), 'Enter a web address starting with http:// or https://'),
  description: z.string().trim().max(2000, 'Keep it under 2,000 characters'),
  address_line1: z.string().trim().max(150), address_line2: z.string().trim().max(150),
  city: z.string().trim().max(80), state: z.string().trim().max(80), postal_code: z.string().trim().max(20),
  country: z.string().min(2).max(2),
  payment_terms_days: z.coerce.number().int().min(0).max(365),
  currency: z.enum(CURRENCIES as [Currency, ...Currency[]]),
  categories: z.array(z.string()).max(10, 'Choose at most 10 categories'),
  contacts: z.array(contactSchema).max(10, 'Add at most 10 contacts'),
  primary: z.coerce.number().int().min(0),
})
export type FormValues = z.infer<typeof formSchema>

/** What is still missing before the profile can be submitted for verification (the server checks the same rules). */
export function submitProblems(v: FormValues): string[] {
  const out: string[] = []
  if (!v.tax_id.trim()) out.push('Enter the tax ID.')
  if (!v.address_line1.trim()) out.push('Enter the street address.')
  if (!v.city.trim()) out.push('Enter the city.')
  if (v.categories.length === 0) out.push('Choose at least one category.')
  if (v.contacts.length === 0) out.push('Add a contact person with an email address.')
  return out
}

const BLANK: FormValues = {
  legal_name: '', trade_name: '', tax_id: '', registration_number: '', website: '', description: '', address_line1: '', address_line2: '', city: '', state: '', postal_code: '',
  country: 'IN', payment_terms_days: 30, currency: 'INR', categories: [], contacts: [], primary: 0,
}
const blankContact = { name: '', job_title: '', email: '', phone: '' }
const STEPS = ['Company', 'Address and terms', 'Categories and contacts', 'Review']
const STEP_FIELDS: (keyof FormValues)[][] = [['legal_name', 'trade_name', 'tax_id', 'registration_number', 'website', 'description'],
  ['address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country', 'payment_terms_days', 'currency'], ['categories', 'contacts'], []]

const orNull = (s: string) => s.trim() || null
export function toInput(v: FormValues): VendorInput {
  return {
    legal_name: v.legal_name.trim(), trade_name: orNull(v.trade_name), tax_id: orNull(v.tax_id), registration_number: orNull(v.registration_number), website: orNull(v.website),
    description: v.description.trim(), address_line1: v.address_line1.trim(), address_line2: orNull(v.address_line2), city: v.city.trim(), state: v.state.trim(),
    postal_code: v.postal_code.trim(), country: v.country, payment_terms_days: Number(v.payment_terms_days), currency: v.currency, categories: v.categories,
    contacts: v.contacts.map((c, i) => ({ name: c.name.trim(), job_title: orNull(c.job_title), email: c.email.trim(), phone: orNull(c.phone), is_primary: i === Number(v.primary) })),
  }
}
export const fromDetail = (d: VendorDetail): FormValues => ({
  legal_name: d.legal_name, trade_name: d.trade_name ?? '', tax_id: d.tax_id ?? '', registration_number: d.registration_number ?? '', website: d.website ?? '', description: d.description,
  address_line1: d.address_line1, address_line2: d.address_line2 ?? '', city: d.city, state: d.state, postal_code: d.postal_code, country: d.country,
  payment_terms_days: d.payment_terms_days, currency: d.currency, categories: d.categories,
  contacts: d.contacts.map((c) => ({ name: c.name, job_title: c.job_title ?? '', email: c.email, phone: c.phone ?? '' })), primary: Math.max(0, d.contacts.findIndex((c) => c.is_primary)),
})
const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')

interface Props {
  /** `register` is a vendor user creating their own record; `onboard` is staff creating one for a vendor without an account. */
  mode: 'register' | 'onboard' | 'edit'
  existing?: VendorDetail
  /** Where to go after saving, given the saved vendor. */
  after: (v: VendorDetail) => string
}

export function VendorForm({ mode, existing, after }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const cats = useQuery({ queryKey: ['vendor-categories'], queryFn: vendorsApi.categories, staleTime: Infinity })
  const { register, control, handleSubmit, trigger, watch, setValue, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as never, defaultValues: existing ? fromDetail(existing) : BLANK, mode: 'onTouched',
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'contacts' })
  const values = watch()
  const problems = submitProblems(values)

  const invalid = (errs: FieldErrors<FormValues>) => {
    setError('Fix the highlighted fields before continuing.')
    const at = STEP_FIELDS.findIndex((fs) => fs.some((f) => errs[f]))
    setStep(at < 0 ? 0 : at)
  }

  const save = (thenSubmit: boolean) => handleSubmit(async (v) => {
    setError('')
    if (thenSubmit && submitProblems(v).length) { setError(submitProblems(v).join(' ')); return }
    setBusy(true)
    try {
      const body = toInput(v)
      let saved = existing ? await vendorsApi.update(existing.id, { ...body, version: existing.version }) : mode === 'onboard' ? await vendorsApi.onboard(body) : await vendorsApi.register(body)
      if (thenSubmit) saved = await vendorsApi.submit(saved.id)
      void qc.invalidateQueries({ queryKey: ['vendor'] }); void qc.invalidateQueries({ queryKey: ['vendors'] }); void qc.invalidateQueries({ queryKey: ['vendors-summary'] })
      navigate(after(saved))
    } catch (e) {
      setError(messageFor(e))
    } finally {
      setBusy(false)
    }
  }, invalid)()

  const next = async () => {
    setError('')
    if (await trigger(STEP_FIELDS[step])) setStep((s) => s + 1)
    else setError('Fix the highlighted fields before continuing.')
  }
  const toggleCategory = (id: string) => setValue('categories', values.categories.includes(id) ? values.categories.filter((c) => c !== id) : [...values.categories, id], { shouldDirty: true, shouldValidate: true })
  const removeContact = (i: number) => { remove(i); const p = Number(values.primary); setValue('primary', i < p ? p - 1 : i === p ? 0 : p) }
  const label = (id: string) => cats.data?.find((c) => c.id === id)?.label ?? id

  return (
    <div className="flex flex-col gap-u12">
      <nav aria-label="Progress">
        <ol className="flex flex-wrap gap-u4">
          {STEPS.map((l, i) => (
            <li key={l} aria-current={i === step ? 'step' : undefined}
              className={clsx('flex min-h-[44px] items-center gap-u4 rounded-full px-u8', i === step ? 'bg-accent text-on-accent' : i < step ? 'bg-pill' : 'border border-line text-muted')}>
              <span className="font-medium">{i + 1}</span><span>{l}</span>
            </li>
          ))}
        </ol>
      </nav>

      <form noValidate onSubmit={(e) => e.preventDefault()} className="flex flex-col gap-u10">
        <Card className={clsx('flex flex-col gap-u8', step !== 0 && 'hidden')} aria-label="Company">
          <Field label="Registered company name" error={errors.legal_name?.message} {...register('legal_name')} />
          <div className="grid gap-u8 sm:grid-cols-2">
            <Field label="Trading name (optional)" hint="If customers know you by another name." error={errors.trade_name?.message} {...register('trade_name')} />
            <Field label="Tax ID" hint="GSTIN, VAT or equivalent. Needed before you can submit." error={errors.tax_id?.message} {...register('tax_id')} />
            <Field label="Company registration number (optional)" error={errors.registration_number?.message} {...register('registration_number')} />
            <Field label="Website (optional)" type="url" placeholder="https://" error={errors.website?.message} {...register('website')} />
          </div>
          <TextAreaField label="About the company (optional)" hint="What you sell and who you serve." error={errors.description?.message} {...register('description')} />
        </Card>

        <Card className={clsx('flex flex-col gap-u8', step !== 1 && 'hidden')} aria-label="Address and terms">
          <Field label="Street address" error={errors.address_line1?.message} {...register('address_line1')} />
          <Field label="Address line 2 (optional)" error={errors.address_line2?.message} {...register('address_line2')} />
          <div className="grid gap-u8 sm:grid-cols-2">
            <Field label="City" error={errors.city?.message} {...register('city')} />
            <Field label="State or region" error={errors.state?.message} {...register('state')} />
            <Field label="Postal code" error={errors.postal_code?.message} {...register('postal_code')} />
            <SelectField label="Country" {...register('country')}>{Object.entries(COUNTRIES).map(([c, n]) => <option key={c} value={c}>{n}</option>)}</SelectField>
            <SelectField label="Payment terms" hint="How long buyers have to pay after an invoice." {...register('payment_terms_days')}>{PAYMENT_TERMS.map((d) => <option key={d} value={d}>{paymentTerms(d)}</option>)}</SelectField>
            <SelectField label="Invoice currency" {...register('currency')}>{CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}</SelectField>
          </div>
        </Card>

        <div className={clsx('flex flex-col gap-u8', step !== 2 && 'hidden')} aria-label="Categories and contacts">
          <Card className="flex flex-col gap-u6">
            <fieldset><legend className="mb-u4 text-xl">What do you supply?</legend>
              <div className="grid gap-u3 sm:grid-cols-2">
                {cats.data?.map((c) => (
                  <label key={c.id} className="flex min-h-[44px] items-center gap-u5 rounded-ctl border border-line px-u7">
                    <input type="checkbox" checked={values.categories.includes(c.id)} onChange={() => toggleCategory(c.id)} className="h-5 w-5" /><span>{c.label}</span>
                  </label>
                ))}
              </div>
              {cats.isError && <p role="alert" className="mt-u4 text-bad">Could not load the categories. Reload the page to try again.</p>}
              {typeof errors.categories?.message === 'string' && <p role="alert" className="mt-u4 text-bad">{errors.categories.message}</p>}
            </fieldset>
          </Card>
          <h2 className="text-xl">Contacts</h2>
          {fields.length === 0 && <Card className="text-center text-muted">No contacts yet. Add the person buyers should reach.</Card>}
          {fields.map((f, i) => {
            const e = errors.contacts?.[i]
            return (
              <Card key={f.id} className="flex flex-col gap-u6" role="group" aria-label={`Contact ${i + 1}`}>
                <div className="grid gap-u6 sm:grid-cols-2">
                  <Field label={`Contact ${i + 1} name`} error={e?.name?.message} {...register(`contacts.${i}.name`)} />
                  <Field label={`Contact ${i + 1} job title (optional)`} error={e?.job_title?.message} {...register(`contacts.${i}.job_title`)} />
                  <Field label={`Contact ${i + 1} email`} type="email" error={e?.email?.message} {...register(`contacts.${i}.email`)} />
                  <Field label={`Contact ${i + 1} phone (optional)`} type="tel" error={e?.phone?.message} {...register(`contacts.${i}.phone`)} />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-u4">
                  <label className="flex min-h-[44px] items-center gap-u4"><input type="radio" name="primary-contact" checked={Number(values.primary) === i} onChange={() => setValue('primary', i)} className="h-5 w-5" />Primary contact</label>
                  <Button variant="ghost" size="sm" onClick={() => removeContact(i)} aria-label={`Remove contact ${i + 1}`}><Trash2 className="h-4 w-4" aria-hidden /> Remove</Button>
                </div>
              </Card>
            )
          })}
          {typeof errors.contacts?.message === 'string' && <p role="alert" className="text-bad">{errors.contacts.message}</p>}
          <div><Button variant="soft" disabled={fields.length >= 10} onClick={() => append(blankContact)}><Plus className="h-4 w-4" aria-hidden /> Add contact</Button></div>
        </div>

        <Card className={clsx('flex flex-col gap-u8', step !== 3 && 'hidden')} aria-label="Review">
          <h2 className="text-2xl">Review</h2>
          <dl className="grid gap-u6 sm:grid-cols-2">
            <div><dt className="text-sm text-muted">Company</dt><dd className="font-medium">{values.legal_name || 'Not set'}</dd></div>
            <div><dt className="text-sm text-muted">Tax ID</dt><dd>{values.tax_id || 'Not set'}</dd></div>
            <div><dt className="text-sm text-muted">City</dt><dd>{[values.city, COUNTRIES[values.country] ?? values.country].filter(Boolean).join(', ')}</dd></div>
            <div><dt className="text-sm text-muted">Payment terms</dt><dd>{paymentTerms(Number(values.payment_terms_days))}, {values.currency}</dd></div>
            <div><dt className="text-sm text-muted">Categories</dt><dd>{values.categories.map(label).join(', ') || 'None'}</dd></div>
            <div><dt className="text-sm text-muted">Contacts</dt><dd>{values.contacts.length}</dd></div>
          </dl>
          {problems.length > 0 ? (
            <div role="status" className="rounded-ctl bg-accent/20 p-u7">
              <p className="font-medium">Before you can submit for verification:</p>
              <ul className="list-disc pl-u10">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
              <p className="mt-u3 text-sm text-muted">You can still save now and finish later.</p>
            </div>
          ) : <p className="text-muted">Everything needed for verification is filled in.</p>}
        </Card>

        {error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}
        <div className="flex flex-wrap justify-between gap-u6">
          <Button variant="soft" disabled={step === 0} onClick={() => { setError(''); setStep((s) => s - 1) }}>Back</Button>
          <div className="flex flex-wrap gap-u4">
            {step < STEPS.length - 1 ? <Button onClick={() => void next()}>Next</Button> : (
              <>
                <Button variant="soft" loading={busy} onClick={() => void save(false)}>{mode === 'edit' ? 'Save changes' : 'Save draft'}</Button>
                {(mode !== 'edit' || existing?.actions.includes('submit')) && <Button loading={busy} disabled={problems.length > 0} onClick={() => void save(true)}>{mode === 'edit' ? 'Save and submit' : 'Save and submit for verification'}</Button>}
              </>
            )}
          </div>
        </div>
      </form>
    </div>
  )
}
