import { forwardRef, type ButtonHTMLAttributes } from 'react'
import clsx from 'clsx'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'dark' | 'soft' | 'outline' | 'ghost'
type Size = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent hover:bg-accent2',
  dark: 'bg-ink text-bg hover:opacity-90',
  soft: 'bg-pill text-ink hover:bg-panel',
  outline: 'border-[1.5px] border-ink text-ink hover:bg-ink hover:text-bg',
  ghost: 'text-ink hover:bg-pill',
}
const sizes: Record<Size, string> = {
  sm: 'h-9 px-u7 text-sm',
  md: 'h-11 px-u8 text-base', // 44px minimum touch target
  lg: 'h-14 px-u12 text-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading, disabled, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-btn font-medium transition-colors duration-200 ease-soft',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
})
