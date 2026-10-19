import type { HTMLAttributes } from 'react'
import clsx from 'clsx'

export type Tone = 'neutral' | 'accent' | 'ok' | 'bad' | 'violet'

const tones: Record<Tone, string> = {
  neutral: 'bg-pill text-ink',
  accent: 'bg-accent/30 text-ink',
  ok: 'bg-ok/15 text-ok',
  bad: 'bg-bad/15 text-bad',
  violet: 'bg-violet/25 text-violet-ink',
}

/** Status text is always written out so colour is never the only signal. */
export function Badge({ tone = 'neutral', className, ...rest }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={clsx('inline-flex items-center rounded-full px-u5 py-u1 text-xs font-medium', tones[tone], className)}
      {...rest}
    />
  )
}

const STATUS_TONE: Record<string, Tone> = {
  Approved: 'ok', Matched: 'ok', Paid: 'ok', Confirmed: 'ok', Delivered: 'ok', Active: 'ok', Verified: 'ok', Done: 'ok',
  Pending: 'accent', 'In review': 'accent', Open: 'accent', Shipped: 'violet', Invited: 'violet', Submitted: 'violet',
  Rejected: 'bad', Mismatch: 'bad', Overdue: 'bad', Suspended: 'bad', Flagged: 'bad',
  Draft: 'neutral',
}

export const StatusBadge = ({ status }: { status: string }) => <Badge tone={STATUS_TONE[status] ?? 'neutral'}>{status}</Badge>
