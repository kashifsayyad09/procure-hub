import { Outlet, useLocation } from 'react-router-dom'
import { roleById, ROLES } from '@/types/roles'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

export function AppShell() {
  const { pathname } = useLocation()
  const role = roleById(pathname.split('/')[2]) ?? ROLES[0]
  return (
    <div className="flex min-h-screen">
      <a href="#main" className="skip-link">Skip to content</a>
      <Sidebar role={role} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar role={role} />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1200px] flex-1 px-u8 py-u12 sm:px-u12 lg:py-u20"><Outlet /></main>
      </div>
    </div>
  )
}
