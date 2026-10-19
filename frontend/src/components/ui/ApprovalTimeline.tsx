import { useRef } from 'react'
import { Check } from 'lucide-react'
import clsx from 'clsx'
import { gsap } from '@/animations/gsap'
import { useGsap } from '@/animations/gsap/useGsap'

export interface TimelineStep { label: string; detail: string; state: 'done' | 'current' | 'pending' }

/** Vertical progress list. The connecting rail fills with GSAP to show how far the item has travelled. */
export function ApprovalTimeline({ steps }: { steps: TimelineStep[] }) {
  const root = useRef<HTMLOListElement>(null)
  const doneCount = steps.filter((s) => s.state === 'done').length
  const pct = steps.length > 1 ? (doneCount / (steps.length - 1)) * 100 : 0

  useGsap(root, () => {
    gsap.fromTo('[data-rail-fill]', { height: '0%' }, { height: `${Math.min(pct, 100)}%`, duration: 0.9, ease: 'power3.out' })
  }, [pct])

  return (
    <ol ref={root} className="relative flex flex-col gap-u10">
      <span aria-hidden className="absolute bottom-3 left-[15px] top-3 w-0.5 bg-line">
        <span data-rail-fill className="block w-full bg-accent" style={{ height: `${Math.min(pct, 100)}%` }} />
      </span>
      {steps.map((s) => (
        <li key={s.label} className="relative flex gap-u8" aria-current={s.state === 'current' ? 'step' : undefined}>
          <span
            className={clsx(
              'z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full border-2 text-xs',
              s.state === 'done' && 'border-accent bg-accent text-on-accent',
              s.state === 'current' && 'border-accent bg-surface',
              s.state === 'pending' && 'border-line bg-surface',
            )}
          >
            {s.state === 'done' ? <Check className="h-4 w-4" aria-hidden /> : s.state === 'current' ? <span className="h-2 w-2 rounded-full bg-accent" /> : null}
          </span>
          <div>
            <p className="font-medium">{s.label} <span className="sr-only">({s.state})</span></p>
            <p className="text-sm text-muted">{s.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
