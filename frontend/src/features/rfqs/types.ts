export type RfqStatus = 'draft' | 'issued' | 'closed' | 'awarded' | 'cancelled'
export const RFQ_STATUSES: RfqStatus[] = ['draft', 'issued', 'closed', 'awarded', 'cancelled']
export type RfqAction = 'edit' | 'invite' | 'publish' | 'extend' | 'close' | 'cancel' | 'compare' | 'select' | 'revoke'
export type QuotationStatus = 'draft' | 'submitted' | 'selected' | 'not_selected'
export type Currency = 'INR' | 'USD' | 'EUR' | 'GBP'
export const CURRENCIES: Currency[] = ['INR', 'USD', 'EUR', 'GBP']

export interface RfqItem { id: string; line_no: number; description: string; specification: string | null; quantity: string; unit: string; estimated_unit_price?: string }
export interface Invitation {
  id: string; vendor_id: string; vendor_number: string; vendor_name: string; status: 'invited' | 'declined' | 'withdrawn'; invited_by_name: string
  invited_at: string; sent_at: string | null; responded_at: string | null; withdrawn_at: string | null; quotation_status: QuotationStatus | null
}
export interface RfqHistoryEntry { id: string; seq: number; action: string; from_status: string | null; to_status: string; actor_name: string; note: string | null; created_at: string }
export interface Selection {
  id: string; seq: number; quotation_id: string; vendor_id: string; vendor_name: string; status: 'awarded' | 'revoked'; justification: string; acknowledged_missing_items: boolean
  currency: string; total_amount: string; selected_by_name: string; selected_at: string; revoked_by_name: string | null; revoked_at: string | null; revoke_reason: string | null
}
export interface RfqSummary {
  id: string; number: string; title: string; purchase_request_id: string; purchase_request_number: string; department: string; status: RfqStatus; currency: Currency
  deadline: string; deadline_passed: boolean; invited: number; submitted: number; created_by_name: string; created_at: string
}
export interface Rfq extends RfqSummary {
  description: string; requirements: string; needed_by: string | null; budget_amount: string; version: number; issued_at: string | null; closed_at: string | null
  cancel_reason: string | null; updated_at: string; items: RfqItem[]; invitations: Invitation[]; history: RfqHistoryEntry[]; quotations_open: boolean
  selection: Selection | null; actions: RfqAction[]
}
export interface RfqPage { items: RfqSummary[]; total: number; page: number; page_size: number }
export interface RfqCounts { counts: Record<RfqStatus, number>; awaiting_comparison: number }
export interface EligibleRequest {
  id: string; number: string; title: string; department: string; priority: string; currency: Currency; total_amount: string; needed_by: string | null
  decided_at: string | null; decided_by_name: string | null; item_count: number; rfq_id: string | null; rfq_number: string | null
}
export interface EligiblePage { items: EligibleRequest[]; total: number; page: number; page_size: number }
export interface RfqQuery { q?: string; status?: RfqStatus | ''; sort?: string; order?: 'asc' | 'desc'; page: number; page_size: number }

export interface QuotationRow {
  id: string | null; number: string | null; vendor_id: string; vendor_name: string; invitation_status: string; status: QuotationStatus | null
  submitted_at: string | null; currency: string | null; total_amount: string | null; lead_time_days: number | null
}
export interface QuotationList { quotations_open: boolean; rows: QuotationRow[] }

export interface QuoteLine { rfq_item_id: string; line_no: number; quantity: string; unit_price: string | null; line_total: string | null; note: string | null }
export interface Quotation {
  id: string; number: string; rfq_id: string; rfq_number: string; rfq_title: string; vendor_id: string; vendor_name: string; currency: Currency; lead_time_days: number | null
  valid_until: string | null; payment_terms_days: number | null; terms: string; total_amount: string; status: QuotationStatus; revision: number; version: number
  submitted_at: string | null; updated_at: string; items: QuoteLine[]; complete: boolean; missing_items: number[]; problems: string[]
  can_edit: boolean; can_submit: boolean; can_withdraw: boolean
}
export interface QuotationInput {
  currency: Currency; lead_time_days: number | null; valid_until: string | null; payment_terms_days: number | null; terms: string
  items: { rfq_item_id: string; unit_price: string | null; note: string | null }[]
}
export interface MyQuotationRow { id: string; number: string; rfq_id: string; rfq_number: string; rfq_title: string; status: QuotationStatus; currency: string; total_amount: string; deadline: string; updated_at: string }
export interface MyQuotationPage { items: MyQuotationRow[]; total: number; page: number; page_size: number }

export interface VendorRfqSummary {
  id: string; number: string; title: string; status: RfqStatus; currency: Currency; deadline: string; deadline_passed: boolean
  invitation_status: 'invited' | 'declined' | 'withdrawn'; can_quote: boolean
  quotation: { id: string; number: string; status: QuotationStatus; total_amount: string; currency: string; updated_at: string } | null
}
export interface VendorRfq extends VendorRfqSummary {
  description: string; requirements: string; needed_by: string | null; items: RfqItem[]; blocked_reason: string | null; issued_at: string | null
}
export interface VendorRfqPage { items: VendorRfqSummary[]; total: number; page: number; page_size: number }

export interface Scores { price: string | null; delivery: string | null; compliance: string | null; terms: string | null; total: string | null; missing: string[] }
export interface Evaluation { compliance_score: number | null; compliance_note: string | null; terms_score: number | null; terms_note: string | null; evaluator_name: string; version: number; updated_at: string }
export interface CompareQuotation {
  id: string; number: string; vendor_id: string; vendor_number: string; vendor_name: string; vendor_status: string | null; currency: string; status: QuotationStatus
  total_amount: string; lead_time_days: number | null; valid_until: string | null; payment_terms_days: number | null; terms: string; submitted_at: string | null
  complete: boolean; missing_items: number[]; lines: { rfq_item_id: string; line_no: number; unit_price: string | null; line_total: string | null }[]
  scores: Scores; rank: number | null; lowest_price: boolean; fastest: boolean; within_budget: boolean | null; evaluation: Evaluation | null
}
export interface Comparison {
  rfq: { id: string; number: string; title: string; status: RfqStatus; currency: Currency; deadline: string; budget_amount: string; version: number; items: RfqItem[] }
  currencies: string[]; mixed_currencies: boolean; note: string | null; weights: Record<string, number>; vendor_info_available: boolean
  quotations: CompareQuotation[]; selection: Selection | null; can_select: boolean; can_revoke: boolean
}
export interface EvaluationInput { compliance_score: number | null; compliance_note: string | null; terms_score: number | null; terms_note: string | null; version?: number }
