import type { TimelineStep } from '@/components/ui/ApprovalTimeline'
import { dateTime } from '@/features/purchase-requests/format'
import type { ApprovalDetail } from './types'

/** The approval route as a timeline: who approved each level, who it is waiting for, what is still to come. */
export function chainFor(a: Pick<ApprovalDetail, 'steps' | 'status'>): TimelineStep[] {
  return a.steps.map((s) => {
    const who = s.decided_by_name ?? ''
    const when = s.decided_at ? `, ${dateTime(s.decided_at)}` : ''
    switch (s.status) {
      case 'approved': return { label: `Level ${s.level}: approved`, detail: `${who}${when}${s.comment ? `. ${s.comment}` : ''}`, state: 'done' as const }
      case 'rejected': return { label: `Level ${s.level}: rejected`, detail: `${who}${when}${s.comment ? `. ${s.comment}` : ''}`, state: 'done' as const }
      case 'pending': return { label: `Level ${s.level}`, detail: `${s.assigned_to_name ? `Delegated to ${s.assigned_to_name}` : 'Waiting for any manager'}${s.escalated_at ? ' (overdue)' : ''}`, state: 'current' as const }
      case 'skipped': return { label: `Level ${s.level}`, detail: a.status === 'cancelled' ? 'Cancelled' : 'Not needed', state: 'pending' as const }
      default: return { label: `Level ${s.level}`, detail: `After level ${s.level - 1}`, state: 'pending' as const }
    }
  })
}
