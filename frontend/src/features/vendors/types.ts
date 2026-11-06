export type VendorStatus = 'draft' | 'pending' | 'verified' | 'rejected' | 'suspended'
export const VENDOR_STATUSES: VendorStatus[] = ['draft', 'pending', 'verified', 'rejected', 'suspended']
export type Currency = 'INR' | 'USD' | 'EUR' | 'GBP'
export type VendorAction = 'edit' | 'submit' | 'verify' | 'reject' | 'suspend' | 'reinstate'

export interface VendorCategory { id: string; label: string }
export interface VendorContact { id: string; name: string; job_title: string | null; email: string; phone: string | null; is_primary: boolean }
export interface VendorHistoryEntry { id: string; seq: number; action: string; from_status: string | null; to_status: string; actor_name: string; note: string | null; created_at: string }

export interface VendorSummary {
  id: string; number: string; legal_name: string; trade_name: string | null; status: VendorStatus; country: string; city: string; categories: string[]
  primary_contact_name: string | null; primary_contact_email: string | null; has_account: boolean
  created_at: string; submitted_at: string | null; verified_at: string | null
}
export interface VendorDetail extends VendorSummary {
  tax_id: string | null; registration_number: string | null; website: string | null; description: string
  address_line1: string; address_line2: string | null; state: string; postal_code: string; payment_terms_days: number; currency: Currency
  status_note: string | null; verified_by_name: string | null; created_by_name: string; version: number; updated_at: string
  contacts: VendorContact[]; history: VendorHistoryEntry[]
  completeness: { percent: number; missing: string[] }; actions: VendorAction[]; blocked_reason: string | null
}
export interface VendorPage { items: VendorSummary[]; total: number; page: number; page_size: number }
export interface VendorsSummary { counts: Record<VendorStatus, number>; verified_by_category: { category: string; count: number }[]; monthly: { month: string; count: number }[] }

export interface VendorInput {
  legal_name: string; trade_name: string | null; tax_id: string | null; registration_number: string | null; website: string | null; description: string
  address_line1: string; address_line2: string | null; city: string; state: string; postal_code: string; country: string
  payment_terms_days: number; currency: Currency; categories: string[]
  contacts: { name: string; job_title: string | null; email: string; phone: string | null; is_primary: boolean }[]
}
export interface VendorQuery { q?: string; status?: VendorStatus | ''; category?: string; sort?: string; order?: 'asc' | 'desc'; page: number; page_size: number }
