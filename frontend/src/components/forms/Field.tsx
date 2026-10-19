import { forwardRef, useId, type InputHTMLAttributes } from 'react'
import clsx from 'clsx'

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
}

/** Labelled input. Works with react-hook-form's register() because it forwards the ref. */
export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field({ label, error, hint, className, id, ...rest }, ref) {
  const auto = useId()
  const inputId = id ?? auto
  const describedBy = error ? `${inputId}-err` : hint ? `${inputId}-hint` : undefined
  return (
    <div className="flex flex-col gap-u3">
      <label htmlFor={inputId} className="text-sm font-medium">{label}</label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={clsx(
          'h-12 rounded-ctl border bg-surface px-u8 text-ink placeholder:text-muted',
          error ? 'border-bad' : 'border-line hover:border-muted',
          className,
        )}
        {...rest}
      />
      {error ? <p id={`${inputId}-err`} className="text-sm text-bad">{error}</p>
        : hint ? <p id={`${inputId}-hint`} className="text-sm text-muted">{hint}</p> : null}
    </div>
  )
})
