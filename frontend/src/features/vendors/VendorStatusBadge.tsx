import { Badge, type Tone } from '@/components/ui/Badge'
import { STATUS_LABEL } from './labels'
import type { VendorStatus } from './types'

const TONE: Record<VendorStatus, Tone> = { draft: 'neutral', pending: 'accent', verified: 'ok', rejected: 'bad', suspended: 'bad' }

export const VendorStatusBadge = ({ status }: { status: VendorStatus }) => <Badge tone={TONE[status]}>{STATUS_LABEL[status]}</Badge>
