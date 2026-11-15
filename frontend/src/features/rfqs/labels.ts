import type { QuotationStatus, RfqStatus } from './types'

export const RFQ_STATUS_LABEL: Record<RfqStatus, string> = { draft: 'Draft', issued: 'Open for quotations', closed: 'Closed', awarded: 'Awarded', cancelled: 'Cancelled' }
export const QUOTE_STATUS_LABEL: Record<QuotationStatus, string> = { draft: 'Draft', submitted: 'Submitted', selected: 'Selected', not_selected: 'Not selected' }
export const INVITATION_LABEL: Record<string, string> = { invited: 'Invited', declined: 'Declined', withdrawn: 'Withdrawn' }
export const RFQ_ACTION_LABEL: Record<string, string> = {
  created: 'Created', updated: 'Updated', vendors_invited: 'Vendors invited', issued: 'Issued to vendors', closed: 'Closed', cancelled: 'Cancelled', deadline_extended: 'Deadline extended',
  invitation_withdrawn: 'Invitation withdrawn', evaluated: 'Evaluated a quotation', awarded: 'Supplier selected', award_revoked: 'Award revoked',
}
export const CRITERIA: { key: 'price' | 'delivery' | 'compliance' | 'terms'; label: string; how: string }[] = [
  { key: 'price', label: 'Price', how: 'Calculated: the lowest total in the same currency scores 100, others are scaled down.' },
  { key: 'delivery', label: 'Delivery', how: 'Calculated: the shortest lead time in the same currency scores 100, others are scaled down.' },
  { key: 'compliance', label: 'Compliance', how: 'Entered by the evaluator (0 to 10): does it meet the requirements?' },
  { key: 'terms', label: 'Commercial terms', how: 'Entered by the evaluator (0 to 10): payment terms, warranty, delivery terms.' },
]
export const VENDOR_STATUS_LABEL: Record<string, string> = { verified: 'Verified', pending: 'Not verified', draft: 'Not verified', rejected: 'Not verified', suspended: 'Suspended' }

/** Time left until a deadline, in words. */
export function timeLeft(iso: string, now = Date.now()): string {
  const ms = new Date(iso).getTime() - now
  if (ms <= 0) return 'Deadline passed'
  const h = Math.floor(ms / 3_600_000)
  if (h >= 48) return `${Math.floor(h / 24)} days left`
  if (h >= 1) return `${h} hour${h === 1 ? '' : 's'} left`
  return `${Math.max(1, Math.floor(ms / 60_000))} minutes left`
}
/** `datetime-local` input value for a UTC instant, in the browser's own time zone. */
export function toLocalInput(iso: string): string {
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}
/** A `datetime-local` value (the browser's local time) as an ISO string in UTC. */
export const fromLocalInput = (v: string): string => new Date(v).toISOString()
/** A price with up to 4 decimals, without trailing zeros beyond 2. */
export const unitPrice = (p: string | null): string => (p === null ? '' : p.replace(/(\.\d\d)0+$/, '$1'))
