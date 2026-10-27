import { Badge, type Tone } from '@/components/ui/Badge'
import type { RequestStatus } from './types'

export const STATUS_LABEL: Record<RequestStatus, string> = {
  draft: 'Draft', submitted: 'Waiting for approval', approved: 'Approved', rejected: 'Rejected', cancelled: 'Cancelled',
}
const TONE: Record<RequestStatus, Tone> = { draft: 'neutral', submitted: 'accent', approved: 'ok', rejected: 'bad', cancelled: 'neutral' }

export const RequestStatusBadge = ({ status }: { status: RequestStatus }) => <Badge tone={TONE[status]}>{STATUS_LABEL[status]}</Badge>
