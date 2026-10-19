import { Boxes, ClipboardCheck, FilePlus2, FileText, LayoutDashboard, ReceiptText, ScrollText, Settings, ShieldCheck, Sparkles, Truck, Users, Building2, BadgeCheck, type LucideIcon } from 'lucide-react'
import type { Role } from '@/types/roles'

export interface NavItem { label: string; icon: LucideIcon; phase?: number }

const dash: NavItem = { label: 'Dashboard', icon: LayoutDashboard }
const talker: NavItem = { label: 'SI-Talker', icon: Sparkles, phase: 12 }

/** Only Dashboard is routable in Phase 1; other items name the phase that delivers them. */
export const NAV: Record<Role, NavItem[]> = {
  employee: [dash, { label: 'My requests', icon: FilePlus2, phase: 3 }, { label: 'Documents', icon: FileText, phase: 3 }, talker],
  manager: [dash, { label: 'Approvals', icon: ClipboardCheck, phase: 4 }, { label: 'Department spend', icon: Boxes, phase: 4 }, talker],
  procurement: [dash, { label: 'RFQs', icon: FileText, phase: 6 }, { label: 'Purchase orders', icon: Truck, phase: 7 }, { label: 'Vendors', icon: Building2, phase: 5 }, talker],
  vendor: [dash, { label: 'Profile', icon: Building2, phase: 5 }, { label: 'Quotations', icon: FileText, phase: 6 }, { label: 'Orders', icon: Truck, phase: 7 }],
  finance: [dash, { label: 'Invoices', icon: ReceiptText, phase: 9 }, { label: 'Matching', icon: BadgeCheck, phase: 9 }, { label: 'Receipts', icon: Boxes, phase: 8 }],
  admin: [dash, { label: 'Users and roles', icon: Users, phase: 2 }, { label: 'Audit log', icon: ScrollText, phase: 10 }, { label: 'Settings', icon: Settings, phase: 17 }, { label: 'System health', icon: ShieldCheck, phase: 16 }],
}
