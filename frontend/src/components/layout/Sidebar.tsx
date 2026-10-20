import { useEffect, useRef } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { ChevronsLeft, ChevronsRight } from 'lucide-react'
import clsx from 'clsx'
import { gsap } from '@/animations/gsap'
import { prefersReducedMotion } from '@/hooks/useReducedMotion'
import { useUiStore } from '@/stores/uiStore'
import type { RoleInfo } from '@/types/roles'
import { NAV } from './navConfig'
import { Drawer } from '@/components/ui/Overlay'

export const Logo = ({ collapsed = false }: { collapsed?: boolean }) => (
  <Link to="/" className="flex items-center gap-u5 rounded-ctl" aria-label="ProcureHub home">
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-ctl bg-ink font-display text-xl text-accent">P</span>
    {!collapsed && <span className="font-display text-xl tracking-tight">ProcureHub</span>}
  </Link>
)

function NavList({ role, collapsed }: { role: RoleInfo; collapsed: boolean }) {
  return (
    <nav aria-label={`${role.label} navigation`}>
      <ul className="flex flex-col gap-u2">
        {NAV[role.id].map((item, i) => {
          const Icon = item.icon
          const body = (
            <>
              <Icon className="h-5 w-5 shrink-0" aria-hidden />
              {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
              {!collapsed && item.phase && <span className="text-xs text-muted">Phase {item.phase}</span>}
            </>
          )
          const base = 'flex min-h-[44px] w-full items-center gap-u6 rounded-ctl px-u7 text-left'
          return (
            <li key={item.label}>
              {i === 0 || item.to ? (
                <NavLink to={i === 0 ? role.path : item.to!} end title={collapsed ? item.label : undefined} className={({ isActive }) => clsx(base, isActive ? 'bg-accent text-on-accent' : 'hover:bg-pill')}>{body}</NavLink>
              ) : (
                <span aria-disabled="true" title={`${item.label} arrives in Phase ${item.phase}`} className={clsx(base, 'cursor-not-allowed text-muted')}>{body}</span>
              )}
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

export function Sidebar({ role }: { role: RoleInfo }) {
  const collapsed = useUiStore((s) => s.sidebarCollapsed)
  const toggle = useUiStore((s) => s.toggleSidebar)
  const mobileOpen = useUiStore((s) => s.mobileNavOpen)
  const setMobile = useUiStore((s) => s.setMobileNav)
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const width = collapsed ? 88 : 272
    if (prefersReducedMotion()) el.style.width = `${width}px`
    else gsap.to(el, { width, duration: 0.35, ease: 'power3.out' })
    return () => { gsap.killTweensOf(el) }
  }, [collapsed])

  return (
    <>
      <aside ref={ref} style={{ width: 272 }} className="sticky top-0 hidden h-screen shrink-0 flex-col gap-u12 overflow-hidden border-r border-line bg-surface p-u8 lg:flex">
        <Logo collapsed={collapsed} />
        <div className="flex-1 overflow-y-auto"><NavList role={role} collapsed={collapsed} /></div>
        <button
          onClick={toggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          className="flex min-h-[44px] items-center gap-u6 rounded-ctl px-u7 text-muted hover:bg-pill hover:text-ink"
        >
          {collapsed ? <ChevronsRight className="h-5 w-5" aria-hidden /> : <><ChevronsLeft className="h-5 w-5" aria-hidden /><span>Collapse</span></>}
        </button>
      </aside>
      <div className="lg:hidden">
        <Drawer open={mobileOpen} onClose={() => setMobile(false)} title="Menu">
          <NavList role={role} collapsed={false} />
        </Drawer>
      </div>
    </>
  )
}
