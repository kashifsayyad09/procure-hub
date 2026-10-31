import { Badge, type Tone } from '@/components/ui/Badge'
import type { ApprovalStatus } from './types'

export const APPROVAL_LABEL: Record<ApprovalStatus, string> = { pending: 'Waiting for a decision', approved: 'Approved', rejected: 'Rejected', cancelled: 'Cancelled' }
const TONE: Record<ApprovalStatus, Tone> = { pending: 'accent', approved: 'ok', rejected: 'bad', cancelled: 'neutral' }

export const ApprovalStatusBadge = ({ status }: { status: ApprovalStatus }) => <Badge tone={TONE[status]}>{APPROVAL_LABEL[status]}</Badge>
