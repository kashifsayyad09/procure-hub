import type { VendorStatus } from './types'

export const STATUS_LABEL: Record<VendorStatus, string> = { draft: 'Draft', pending: 'Waiting for review', verified: 'Verified', rejected: 'Sent back', suspended: 'Suspended' }
export const STATUS_HELP: Record<VendorStatus, string> = {
  draft: 'Finish the profile, then submit it for verification.',
  pending: 'A procurement reviewer is checking the profile.',
  verified: 'You can be invited to requests for quotation.',
  rejected: 'A reviewer sent the profile back. Fix what they asked for and submit it again.',
  suspended: 'This vendor cannot take part in new requests for quotation. Contact procurement.',
}
export const PAYMENT_TERMS = [0, 15, 30, 45, 60, 90]
export const paymentTerms = (days: number) => (days === 0 ? 'Payment on delivery' : `Net ${days} days`)
export const ACTION_LABEL: Record<string, string> = {
  created: 'Registered', updated: 'Profile updated', submitted: 'Submitted for verification', verified: 'Verified', rejected: 'Sent back',
  suspended: 'Suspended', reinstated: 'Reinstated', reverification_required: 'Needs verification again',
}
export const COUNTRIES: Record<string, string> = { IN: 'India', US: 'United States', GB: 'United Kingdom', DE: 'Germany', FR: 'France', AE: 'United Arab Emirates', SG: 'Singapore', CN: 'China', JP: 'Japan', AU: 'Australia', CA: 'Canada' }
export const countryName = (code: string) => COUNTRIES[code] ?? code
