export type Role = 'employee' | 'manager' | 'procurement' | 'vendor' | 'finance' | 'admin'

export interface RoleInfo {
  id: Role
  label: string
  path: string
  summary: string
}

export const ROLES: RoleInfo[] = [
  { id: 'employee', label: 'Employee', path: '/app/employee', summary: 'Raise purchase requests and follow them to delivery.' },
  { id: 'manager', label: 'Manager', path: '/app/manager', summary: 'Approve or reject requests and watch department spend.' },
  { id: 'procurement', label: 'Procurement officer', path: '/app/procurement', summary: 'Run RFQs, compare quotations and issue purchase orders.' },
  { id: 'vendor', label: 'Vendor', path: '/app/vendor', summary: 'Answer RFQs, confirm orders and submit invoices.' },
  { id: 'finance', label: 'Finance officer', path: '/app/finance', summary: 'Match invoices to orders and receipts, then track payment.' },
  { id: 'admin', label: 'Administrator', path: '/app/admin', summary: 'Manage users, roles, settings and the audit trail.' },
]

export const roleById = (id: string | undefined): RoleInfo | undefined => ROLES.find((r) => r.id === id)
