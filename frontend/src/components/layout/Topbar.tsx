import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, ChevronDown, LogOut, Menu, Moon, Sun } from 'lucide-react'
import { useThemeStore } from '@/stores/themeStore'
import { useUiStore } from '@/stores/uiStore'
import { ROLES, type RoleInfo } from '@/types/roles'
import { Drawer } from '@/components/ui/Overlay'
import { Badge } from '@/components/ui/Badge'
import { NOTIFICATIONS } from '@/services/mockData'

export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme)
  const toggle = useThemeStore((s) => s.toggle)
  return (
    <button onClick={toggle} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} className="grid h-11 w-11 place-items-center rounded-full hover:bg-pill">
      {theme === 'dark' ? <Sun className="h-5 w-5" aria-hidden /> : <Moon className="h-5 w-5" aria-hidden />}
    </button>
  )
}

function ProfileMenu({ role }: { role: RoleInfo }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="true" className="flex h-11 items-center gap-u4 rounded-full bg-pill pl-u3 pr-u6">
        <span className="grid h-9 w-9 place-items-center rounded-full bg-ink text-sm text-bg" aria-hidden>{role.label[0]}</span>
        <span className="hidden text-sm sm:inline">{role.label}</span>
        <ChevronDown className="h-4 w-4" aria-hidden />
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-u4 w-64 rounded-card border border-line bg-surface p-u4 shadow-card">
          <p className="px-u6 py-u3 text-sm text-muted">Preview another role (Phase 1 only)</p>
          <ul>
            {ROLES.filter((r) => r.id !== role.id).map((r) => (
              <li key={r.id}><Link to={r.path} onClick={() => setOpen(false)} className="flex min-h-[44px] items-center rounded-ctl px-u6 hover:bg-pill">{r.label}</Link></li>
            ))}
          </ul>
          <button onClick={() => navigate('/login')} className="mt-u2 flex min-h-[44px] w-full items-center gap-u4 rounded-ctl border-t border-line px-u6 hover:bg-pill">
            <LogOut className="h-4 w-4" aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}

export function Topbar({ role }: { role: RoleInfo }) {
  const setMobile = useUiStore((s) => s.setMobileNav)
  const [bell, setBell] = useState(false)
  const unread = NOTIFICATIONS.filter((n) => n.unread).length
  return (
    <header className="sticky top-0 z-30 flex items-center gap-u6 border-b border-line bg-bg/90 px-u8 py-u5 backdrop-blur sm:px-u12">
      <button onClick={() => setMobile(true)} aria-label="Open menu" className="grid h-11 w-11 place-items-center rounded-full hover:bg-pill lg:hidden"><Menu className="h-5 w-5" aria-hidden /></button>
      <p className="flex-1 truncate font-display text-xl">{role.label} workspace</p>
      <ThemeToggle />
      <button onClick={() => setBell(true)} aria-label={`Notifications, ${unread} unread`} className="relative grid h-11 w-11 place-items-center rounded-full hover:bg-pill">
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 && <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-accent" aria-hidden />}
      </button>
      <ProfileMenu role={role} />
      <Drawer open={bell} onClose={() => setBell(false)} title="Notifications">
        <ul className="flex flex-col gap-u6">
          {NOTIFICATIONS.map((n) => (
            <li key={n.id} className="rounded-ctl border border-line p-u7">
              <div className="flex items-center justify-between gap-u4"><p className="font-medium">{n.title}</p>{n.unread && <Badge tone="accent">Unread</Badge>}</div>
              <p className="text-sm text-muted">{n.body}</p>
              <p className="mt-u2 text-xs text-muted">{n.time}</p>
            </li>
          ))}
        </ul>
        <p className="mt-u8 text-sm text-muted">Sample notifications. Live notifications arrive in Phase 10.</p>
      </Drawer>
    </header>
  )
}
