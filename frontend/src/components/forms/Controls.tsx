import { forwardRef, useId, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import clsx from 'clsx'

interface Common { label: string; error?: string; hint?: string }

const box = 'rounded-ctl border bg-surface px-u8 text-ink placeholder:text-muted'

export const TextAreaField = forwardRef<HTMLTextAreaElement, Common & TextareaHTMLAttributes<HTMLTextAreaElement>>(function TextAreaField({ label, error, hint, className, id, ...rest }, ref) {
  const auto = useId()
  const fid = id ?? auto
  const described = error ? `${fid}-err` : hint ? `${fid}-hint` : undefined
  return (
    <div className="flex flex-col gap-u3">
      <label htmlFor={fid} className="text-sm font-medium">{label}</label>
      <textarea ref={ref} id={fid} rows={4} aria-invalid={error ? true : undefined} aria-describedby={described}
        className={clsx(box, 'py-u5', error ? 'border-bad' : 'border-line hover:border-muted', className)} {...rest} />
      {error ? <p id={`${fid}-err`} className="text-sm text-bad">{error}</p> : hint ? <p id={`${fid}-hint`} className="text-sm text-muted">{hint}</p> : null}
    </div>
  )
})

export const SelectField = forwardRef<HTMLSelectElement, Common & SelectHTMLAttributes<HTMLSelectElement>>(function SelectField({ label, error, hint, className, id, children, ...rest }, ref) {
  const auto = useId()
  const fid = id ?? auto
  const described = error ? `${fid}-err` : hint ? `${fid}-hint` : undefined
  return (
    <div className="flex flex-col gap-u3">
      <label htmlFor={fid} className="text-sm font-medium">{label}</label>
      <select ref={ref} id={fid} aria-invalid={error ? true : undefined} aria-describedby={described}
        className={clsx(box, 'h-12', error ? 'border-bad' : 'border-line hover:border-muted', className)} {...rest}>{children}</select>
      {error ? <p id={`${fid}-err`} className="text-sm text-bad">{error}</p> : hint ? <p id={`${fid}-hint`} className="text-sm text-muted">{hint}</p> : null}
    </div>
  )
})
