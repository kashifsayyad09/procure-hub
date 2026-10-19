import type { Stat } from '@/components/ui/StatCard'
import type { TimelineStep } from '@/components/ui/ApprovalTimeline'
import type { TrendPoint } from '@/components/charts/TrendChart'
import type { Row } from '@/components/tables/DataTable'
import type { Role } from '@/types/roles'

/** SAMPLE DATA ONLY. Replaced by real service APIs in Phases 2-10. */

export const NOTIFICATIONS = [
  { id: 'n1', title: 'Request PR-2041 needs a decision', body: 'Laptops for the design team are waiting for approval.', time: '10 minutes ago', unread: true },
  { id: 'n2', title: 'Quotation received', body: 'Northwind Supplies answered RFQ-118.', time: '1 hour ago', unread: true },
  { id: 'n3', title: 'Goods received', body: 'PO-7782 was delivered in full.', time: 'Yesterday', unread: false },
]

export interface DashboardData {
  headline: string
  intro: string
  stats: Stat[]
  trend: { title: string; kind: 'bar' | 'area'; unit?: string; label: string; points: TrendPoint[] }
  table: { title: string; columns: { key: string; header: string; status?: boolean; right?: boolean }[]; rows: Row[]; filterKey?: string }
  timeline: { title: string; steps: TimelineStep[] }
  actions: { label: string; phase: number }[]
}

const months = ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']
const series = (values: number[]): TrendPoint[] => values.map((value, i) => ({ name: months[i], value }))
const done = (label: string, detail: string): TimelineStep => ({ label, detail, state: 'done' })
const now = (label: string, detail: string): TimelineStep => ({ label, detail, state: 'current' })
const next = (label: string, detail: string): TimelineStep => ({ label, detail, state: 'pending' })

export const DASHBOARDS: Record<Role, DashboardData> = {
  employee: {
    headline: 'Your requests',
    intro: 'See where each purchase stands and what happens next.',
    stats: [
      { id: 'open', label: 'Open requests', value: 6, note: '2 waiting on a manager' },
      { id: 'approved', label: 'Approved this month', value: 4, note: 'Ready for sourcing' },
      { id: 'spend', label: 'Requested value', value: 184500, prefix: '₹', note: 'Across all open requests' },
      { id: 'deliveries', label: 'Deliveries due', value: 3, note: 'Within 7 days' },
    ],
    trend: { title: 'Requests raised per month', kind: 'bar', label: 'Requests', points: series([3, 5, 4, 7, 6, 9]) },
    table: {
      title: 'Recent requests', filterKey: 'status',
      columns: [{ key: 'id', header: 'Request' }, { key: 'item', header: 'Item' }, { key: 'amount', header: 'Amount (₹)', right: true }, { key: 'status', header: 'Status', status: true }],
      rows: [
        { id: 'PR-2041', item: 'Laptops, design team', amount: 96000, status: 'Pending' },
        { id: 'PR-2038', item: 'Standing desks', amount: 42000, status: 'Approved' },
        { id: 'PR-2033', item: 'Conference licences', amount: 31500, status: 'Draft' },
        { id: 'PR-2027', item: 'Printer toner', amount: 15000, status: 'Rejected' },
      ],
    },
    timeline: { title: 'PR-2041 progress', steps: [done('Submitted', 'You sent it on 12 Oct'), now('Manager review', 'Waiting on Priya Nair'), next('Sourcing', 'Procurement raises an RFQ'), next('Delivery', 'Goods are received')] },
    actions: [{ label: 'New purchase request', phase: 3 }, { label: 'Upload a document', phase: 3 }],
  },
  manager: {
    headline: 'Approvals',
    intro: 'Decide what is waiting and keep an eye on department spend.',
    stats: [
      { id: 'pending', label: 'Waiting for you', value: 5, note: '1 is overdue' },
      { id: 'approved', label: 'Approved this month', value: 18, note: 'Average decision: 6 hours' },
      { id: 'spend', label: 'Department spend', value: 612000, prefix: '₹', note: '74% of quarterly budget' },
      { id: 'delegated', label: 'Delegated', value: 2, note: 'To Arjun Mehta' },
    ],
    trend: { title: 'Department spend (₹ thousand)', kind: 'area', unit: 'k', label: 'Spend', points: series([84, 102, 95, 118, 110, 103]) },
    table: {
      title: 'Approval queue', filterKey: 'status',
      columns: [{ key: 'id', header: 'Request' }, { key: 'requester', header: 'Requester' }, { key: 'amount', header: 'Amount (₹)', right: true }, { key: 'status', header: 'Status', status: true }],
      rows: [
        { id: 'PR-2041', requester: 'Asha Rao', amount: 96000, status: 'Pending' },
        { id: 'PR-2040', requester: 'Dev Patel', amount: 12400, status: 'Pending' },
        { id: 'PR-2036', requester: 'Meera Joshi', amount: 58000, status: 'Approved' },
        { id: 'PR-2029', requester: 'Sam Iyer', amount: 220000, status: 'Rejected' },
      ],
    },
    timeline: { title: 'Approval chain for PR-2041', steps: [done('Line manager', 'Approved on 13 Oct'), now('Department head', 'Waiting on you'), next('Finance check', 'Required above ₹1,00,000')] },
    actions: [{ label: 'Review next request', phase: 4 }, { label: 'Delegate approvals', phase: 4 }],
  },
  procurement: {
    headline: 'Sourcing',
    intro: 'Turn approved requests into RFQs, compare quotations and place orders.',
    stats: [
      { id: 'ready', label: 'Approved, not sourced', value: 7, note: 'Oldest waiting 3 days' },
      { id: 'rfqs', label: 'Open RFQs', value: 9, note: '14 quotations received' },
      { id: 'pos', label: 'Orders in flight', value: 12, note: '3 awaiting vendor confirmation' },
      { id: 'savings', label: 'Savings vs. first quote', value: 8, suffix: '%', note: 'Across closed RFQs' },
    ],
    trend: { title: 'Purchase orders issued', kind: 'bar', label: 'Orders', points: series([8, 11, 9, 14, 13, 16]) },
    table: {
      title: 'RFQ tracker', filterKey: 'status',
      columns: [{ key: 'id', header: 'RFQ' }, { key: 'item', header: 'Item' }, { key: 'quotes', header: 'Quotes', right: true }, { key: 'status', header: 'Status', status: true }],
      rows: [
        { id: 'RFQ-118', item: 'Laptops, design team', quotes: 4, status: 'Open' },
        { id: 'RFQ-116', item: 'Standing desks', quotes: 3, status: 'In review' },
        { id: 'RFQ-112', item: 'Network switches', quotes: 5, status: 'Done' },
      ],
    },
    timeline: { title: 'RFQ-118 progress', steps: [done('RFQ created', 'Sent to 5 vendors'), done('Quotations in', '4 of 5 vendors answered'), now('Compare and select', 'Evaluate price and delivery'), next('Purchase order', 'Issued to the chosen vendor')] },
    actions: [{ label: 'Create an RFQ', phase: 6 }, { label: 'Compare quotations', phase: 6 }],
  },
  vendor: {
    headline: 'Your business with us',
    intro: 'Answer RFQs, confirm orders and keep your invoices moving.',
    stats: [
      { id: 'rfqs', label: 'RFQs to answer', value: 3, note: 'Closest closes in 2 days' },
      { id: 'quotes', label: 'Quotations submitted', value: 11, note: '4 accepted' },
      { id: 'orders', label: 'Orders to confirm', value: 2, note: 'Confirm within 48 hours' },
      { id: 'invoices', label: 'Invoices unpaid', value: 5, note: '₹2,31,000 outstanding' },
    ],
    trend: { title: 'Quotations accepted', kind: 'bar', label: 'Accepted', points: series([1, 2, 1, 3, 2, 4]) },
    table: {
      title: 'Invitations and orders', filterKey: 'status',
      columns: [{ key: 'id', header: 'Reference' }, { key: 'item', header: 'Item' }, { key: 'due', header: 'Due' }, { key: 'status', header: 'Status', status: true }],
      rows: [
        { id: 'RFQ-118', item: 'Laptops, design team', due: '21 Oct', status: 'Invited' },
        { id: 'RFQ-121', item: 'Ergonomic chairs', due: '24 Oct', status: 'Invited' },
        { id: 'PO-7782', item: 'Network switches', due: '28 Oct', status: 'Shipped' },
        { id: 'PO-7790', item: 'Cabling', due: '02 Nov', status: 'Confirmed' },
      ],
    },
    timeline: { title: 'PO-7782 fulfilment', steps: [done('Order confirmed', 'You confirmed on 14 Oct'), done('Shipped', 'Dispatched on 17 Oct'), now('Delivery', 'Expected 28 Oct'), next('Invoice', 'Submit after goods receipt')] },
    actions: [{ label: 'Submit a quotation', phase: 6 }, { label: 'Update profile', phase: 5 }],
  },
  finance: {
    headline: 'Invoices and payments',
    intro: 'Match every invoice to its order and receipt before you pay.',
    stats: [
      { id: 'review', label: 'Invoices to review', value: 9, note: '3 arrived today' },
      { id: 'mismatch', label: 'Mismatches', value: 2, note: 'Quantity and price' },
      { id: 'due', label: 'Due this week', value: 348000, prefix: '₹', note: 'Across 6 invoices' },
      { id: 'matched', label: 'Matched first time', value: 91, suffix: '%', note: 'Last 30 days' },
    ],
    trend: { title: 'Payments released (₹ thousand)', kind: 'area', unit: 'k', label: 'Paid', points: series([210, 260, 240, 310, 295, 340]) },
    table: {
      title: 'Invoice queue', filterKey: 'status',
      columns: [{ key: 'id', header: 'Invoice' }, { key: 'vendor', header: 'Vendor' }, { key: 'amount', header: 'Amount (₹)', right: true }, { key: 'status', header: 'Status', status: true }],
      rows: [
        { id: 'INV-5531', vendor: 'Northwind Supplies', amount: 96000, status: 'Pending' },
        { id: 'INV-5528', vendor: 'Kestrel Office', amount: 42000, status: 'Matched' },
        { id: 'INV-5524', vendor: 'Brightline IT', amount: 128500, status: 'Mismatch' },
        { id: 'INV-5519', vendor: 'Kestrel Office', amount: 18200, status: 'Paid' },
      ],
    },
    timeline: { title: 'Three-way match for INV-5531', steps: [done('Purchase order', 'PO-7782 found'), done('Goods receipt', 'GR-3310 found'), now('Invoice check', 'Comparing quantities and prices'), next('Payment', 'Released after a clean match')] },
    actions: [{ label: 'Review next invoice', phase: 9 }, { label: 'Export a report', phase: 9 }],
  },
  admin: {
    headline: 'Administration',
    intro: 'Manage who can do what, and see what happened.',
    stats: [
      { id: 'users', label: 'Active users', value: 128, note: '6 roles in use' },
      { id: 'invites', label: 'Pending invitations', value: 4, note: 'Sent this week' },
      { id: 'events', label: 'Audit events today', value: 1342, note: 'No security alerts' },
      { id: 'services', label: 'Services healthy', value: 11, suffix: ' of 11', note: 'Sample figure' },
    ],
    trend: { title: 'Sign-ins per month', kind: 'area', label: 'Sign-ins', points: series([820, 910, 980, 1100, 1180, 1260]) },
    table: {
      title: 'Users', filterKey: 'status',
      columns: [{ key: 'name', header: 'Name' }, { key: 'role', header: 'Role' }, { key: 'last', header: 'Last active' }, { key: 'status', header: 'Status', status: true }],
      rows: [
        { name: 'Asha Rao', role: 'Employee', last: 'Today', status: 'Active' },
        { name: 'Priya Nair', role: 'Manager', last: 'Today', status: 'Active' },
        { name: 'Kabir Shah', role: 'Finance officer', last: '3 days ago', status: 'Active' },
        { name: 'Lena Fox', role: 'Vendor', last: 'Never', status: 'Invited' },
        { name: 'Tom Bell', role: 'Employee', last: '60 days ago', status: 'Suspended' },
      ],
    },
    timeline: { title: 'Recent system events', steps: [done('Role changed', 'Arjun Mehta became Manager'), done('Vendor verified', 'Northwind Supplies'), now('Invitation sent', 'Lena Fox, Vendor'), next('Review access', 'Quarterly review due 1 Nov')] },
    actions: [{ label: 'Invite a user', phase: 2 }, { label: 'Open audit log', phase: 10 }],
  },
}

const LATENCY = import.meta.env.MODE === 'test' ? 0 : 450

export const dashboardRequest = { failNext: false }

export async function fetchDashboard(role: Role): Promise<DashboardData> {
  await new Promise((r) => setTimeout(r, LATENCY))
  if (dashboardRequest.failNext) {
    dashboardRequest.failNext = false
    throw new Error('The sample service did not respond.')
  }
  return DASHBOARDS[role]
}
