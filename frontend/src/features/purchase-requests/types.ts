export type RequestStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'cancelled'
export type Priority = 'low' | 'normal' | 'high' | 'urgent'
export type Currency = 'INR' | 'USD' | 'EUR' | 'GBP'

export const STATUSES: RequestStatus[] = ['draft', 'submitted', 'approved', 'rejected', 'cancelled']
export const PRIORITIES: Priority[] = ['low', 'normal', 'high', 'urgent']
export const CURRENCIES: Currency[] = ['INR', 'USD', 'EUR', 'GBP']
export const ALLOWED_DOCUMENT_TYPES: Record<string, string> = {
  'application/pdf': 'PDF', 'image/png': 'PNG', 'image/jpeg': 'JPEG', 'text/plain': 'TXT', 'text/csv': 'CSV',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
}
export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024

// Money and quantities travel as strings so no precision is lost; the server does all arithmetic.
export interface RequestItem { id: string; line_no: number; description: string; quantity: string; unit: string; unit_price: string; notes: string | null; line_total: string }
export interface RequestDocument { id: string; file_name: string; content_type: string; size_bytes: number; content_stored: boolean; created_at: string }
export interface HistoryEntry { id: string; from_status: RequestStatus | null; to_status: RequestStatus; actor_name: string; note: string | null; created_at: string }

export interface RequestSummary {
  id: string; number: string; title: string; department: string; priority: Priority; status: RequestStatus; currency: Currency
  total_amount: string; needed_by: string | null; requester_name: string; item_count: number
  created_at: string; submitted_at: string | null; updated_at: string
}
export interface RequestDetail extends RequestSummary {
  justification: string; requester_id: string; requester_email: string; cancel_reason: string | null; version: number
  decided_at: string | null; decided_by_name: string | null; decision_note: string | null
  items: RequestItem[]; documents: RequestDocument[]; history: HistoryEntry[]
}
export interface RequestPage { items: RequestSummary[]; total: number; page: number; page_size: number }
export interface RequestsSummary { counts: Record<RequestStatus, number>; open_value: Record<string, string>; monthly: { month: string; count: number }[] }

export interface ItemInput { description: string; quantity: string; unit: string; unit_price: string; notes?: string | null }
export interface RequestInput {
  title: string; justification: string; department: string; priority: Priority; needed_by: string | null; currency: Currency; items: ItemInput[]
}
export interface RequestQuery {
  q?: string; status?: RequestStatus | ''; priority?: Priority | ''; sort?: string; order?: 'asc' | 'desc'; page: number; page_size: number
}
