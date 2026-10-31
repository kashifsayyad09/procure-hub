import type { Currency, Priority } from '@/features/purchase-requests/types'

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'
export type StepStatus = 'waiting' | 'pending' | 'approved' | 'rejected' | 'skipped'
export type ApprovalView = 'queue' | 'mine' | 'all'
export const APPROVAL_STATUSES: ApprovalStatus[] = ['pending', 'approved', 'rejected', 'cancelled']

export interface ApprovalSummary {
  id: string; request_id: string; request_number: string; title: string; requester_name: string; department: string; priority: Priority; currency: Currency
  total_amount: string; needed_by: string | null; status: ApprovalStatus; current_level: number; total_levels: number
  waiting_for: string | null; overdue: boolean; created_at: string; decided_at: string | null
}
export interface ApprovalStep {
  id: string; level: number; status: StepStatus; assigned_to_id: string | null; assigned_to_name: string | null; decided_by_name: string | null
  decided_at: string | null; comment: string | null; activated_at: string | null; escalated_at: string | null
}
export interface ApprovalHistoryEntry { id: string; seq: number; action: string; level: number | null; actor_name: string; note: string | null; created_at: string }
export interface ApprovalItem { line_no: number; description: string; quantity: string; unit: string; unit_price: string; line_total: string }
export interface ApprovalDetail extends ApprovalSummary {
  justification: string; requester_id: string; requester_email: string; items: ApprovalItem[]; steps: ApprovalStep[]; history: ApprovalHistoryEntry[]
  can_decide: boolean; blocked_reason: string | null; decision_sync: 'not_needed' | 'pending' | 'synced' | 'conflict'; last_sync_error: string | null
}
export interface ApprovalPage { items: ApprovalSummary[]; total: number; page: number; page_size: number }
export interface ApprovalsSummary {
  waiting_for_me: number; overdue_for_me: number; delegated_to_me: number; decided_by_me_30d: number; approved_30d: number; rejected_30d: number
  approved_value_30d: Record<string, string>; avg_decision_hours_30d: number | null; monthly: { month: string; count: number }[]
}
export interface Delegate { id: string; full_name: string; email: string }
export interface ApprovalQuery { view: ApprovalView; q?: string; status?: ApprovalStatus | ''; priority?: Priority | ''; sort?: string; order?: 'asc' | 'desc'; page: number; page_size: number }
