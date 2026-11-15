import { Badge, type Tone } from '@/components/ui/Badge'
import { QUOTE_STATUS_LABEL, RFQ_STATUS_LABEL } from './labels'
import type { QuotationStatus, RfqStatus } from './types'

const RFQ_TONE: Record<RfqStatus, Tone> = { draft: 'neutral', issued: 'accent', closed: 'violet', awarded: 'ok', cancelled: 'bad' }
const Q_TONE: Record<QuotationStatus, Tone> = { draft: 'neutral', submitted: 'accent', selected: 'ok', not_selected: 'neutral' }
export const RfqStatusBadge = ({ status }: { status: RfqStatus }) => <Badge tone={RFQ_TONE[status]}>{RFQ_STATUS_LABEL[status]}</Badge>
export const QuotationStatusBadge = ({ status }: { status: QuotationStatus }) => <Badge tone={Q_TONE[status]}>{QUOTE_STATUS_LABEL[status]}</Badge>
