import type { TimelineStep } from '@/components/ui/ApprovalTimeline'
import { dateTime } from './format'
import type { RequestSummary } from './types'

/** Where a request is on its way to delivery. Later steps light up as the approval, sourcing and receiving phases land. */
export function timelineFor(r: Pick<RequestSummary, 'status' | 'submitted_at'>): TimelineStep[] {
  const sent: TimelineStep = { label: 'Submitted', detail: r.submitted_at ? dateTime(r.submitted_at) : 'Sent for approval', state: 'done' }
  switch (r.status) {
    case 'draft':
      return [{ label: 'Draft', detail: 'Not submitted yet', state: 'current' }, { label: 'Manager review', detail: 'After you submit', state: 'pending' }, { label: 'Sourcing', detail: 'Procurement finds a vendor', state: 'pending' }, { label: 'Delivery', detail: 'Goods are received', state: 'pending' }]
    case 'submitted':
      return [sent, { label: 'Manager review', detail: 'Waiting for a decision', state: 'current' }, { label: 'Sourcing', detail: 'Procurement finds a vendor', state: 'pending' }, { label: 'Delivery', detail: 'Goods are received', state: 'pending' }]
    case 'approved':
      return [sent, { label: 'Approved', detail: 'A manager approved this request', state: 'done' }, { label: 'Sourcing', detail: 'Procurement is finding a vendor', state: 'current' }, { label: 'Delivery', detail: 'Goods are received', state: 'pending' }]
    case 'rejected':
      return [sent, { label: 'Rejected', detail: 'A manager declined this request', state: 'done' }]
    case 'cancelled':
      return [sent, { label: 'Cancelled', detail: 'You cancelled this request', state: 'done' }]
  }
}
