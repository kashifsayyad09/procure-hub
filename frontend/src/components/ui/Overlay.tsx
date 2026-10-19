import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import clsx from 'clsx'
import { gsap } from '@/animations/gsap'
import { prefersReducedMotion } from '@/hooks/useReducedMotion'

interface OverlayProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  /** 'modal' centres the panel; 'drawer' slides in from the right. */
  variant?: 'modal' | 'drawer'
}

const FOCUSABLE = 'a[href],button:not([disabled]),textarea,input,select,[tabindex]:not([tabindex="-1"])'

/** Accessible dialog: focus moves in, Tab is trapped, Escape closes, focus returns to the trigger. */
function Overlay({ open, onClose, title, children, footer, variant = 'modal' }: OverlayProps) {
  const [mounted, setMounted] = useState(open)
  const panel = useRef<HTMLDivElement>(null)
  const backdrop = useRef<HTMLDivElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  const titleId = useId()

  useEffect(() => {
    if (open) setMounted(true)
  }, [open])

  // enter / exit animation
  useEffect(() => {
    if (!mounted || !panel.current || !backdrop.current) return
    const reduce = prefersReducedMotion()
    const fromVars = variant === 'drawer' ? { x: 48 } : { y: 16, scale: 0.97 }
    const p = panel.current
    const b = backdrop.current
    if (open) {
      returnFocus.current = document.activeElement as HTMLElement | null
      if (!reduce) {
        gsap.fromTo(b, { opacity: 0 }, { opacity: 1, duration: 0.2 })
        gsap.fromTo(p, { opacity: 0, ...fromVars }, { opacity: 1, x: 0, y: 0, scale: 1, duration: 0.35, ease: 'power3.out' })
      }
      p.querySelector<HTMLElement>(FOCUSABLE)?.focus()
    } else if (reduce) {
      setMounted(false)
    } else {
      gsap.to(b, { opacity: 0, duration: 0.2 })
      gsap.to(p, { opacity: 0, ...fromVars, duration: 0.2, onComplete: () => setMounted(false) })
    }
    return () => {
      gsap.killTweensOf([p, b])
    }
  }, [open, mounted, variant])

  useEffect(() => {
    if (!open && !mounted) returnFocus.current?.focus?.()
  }, [open, mounted])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') return onClose()
      if (e.key !== 'Tab' || !panel.current) return
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!mounted) return null
  return createPortal(
    <div className={clsx('fixed inset-0 z-50 flex', variant === 'drawer' ? 'justify-end' : 'items-center justify-center p-u8')}>
      <div ref={backdrop} className="absolute inset-0 bg-ink/40" onClick={onClose} aria-hidden />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={clsx(
          'relative flex max-h-full flex-col bg-surface text-ink shadow-card',
          variant === 'drawer' ? 'h-full w-full max-w-md rounded-l-card border-l border-line' : 'w-full max-w-lg rounded-card border border-line',
        )}
      >
        <header className="flex items-start justify-between gap-u8 border-b border-line p-u12">
          <h2 id={titleId} className="text-2xl">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="grid h-11 w-11 shrink-0 place-items-center rounded-full hover:bg-pill">
            <X className="h-5 w-5" aria-hidden />
          </button>
        </header>
        <div className="overflow-y-auto p-u12">{children}</div>
        {footer && <footer className="flex justify-end gap-u4 border-t border-line p-u8">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}

export const Modal = (p: Omit<OverlayProps, 'variant'>) => <Overlay {...p} variant="modal" />
export const Drawer = (p: Omit<OverlayProps, 'variant'>) => <Overlay {...p} variant="drawer" />
