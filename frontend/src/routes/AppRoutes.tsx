import { lazy, Suspense } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAuth } from '@/components/auth/RequireAuth'
import type { Role } from '@/types/roles'
import { Skeleton } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'

const Landing = lazy(() => import('@/pages/landing/LandingPage'))
const Login = lazy(() => import('@/pages/auth/LoginPage'))
const Employee = lazy(() => import('@/pages/employee/EmployeeDashboard'))
const Manager = lazy(() => import('@/pages/manager/ManagerDashboard'))
const Procurement = lazy(() => import('@/pages/procurement/ProcurementDashboard'))
const Vendor = lazy(() => import('@/pages/vendor/VendorDashboard'))
const Finance = lazy(() => import('@/pages/finance/FinanceDashboard'))
const Admin = lazy(() => import('@/pages/admin/AdminDashboard'))
const Users = lazy(() => import('@/pages/admin/UsersPage'))

const only = (role: Role, el: JSX.Element) => <RequireAuth roles={[role]}>{el}</RequireAuth>

const Fallback = () => <div className="p-u12" role="status"><span className="sr-only">Loading</span><Skeleton className="h-40 w-full rounded-card" /></div>

function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center p-u12 text-center">
      <div className="flex flex-col items-center gap-u8">
        <h1 className="display-lg">Page not found</h1>
        <p className="text-muted">The address may be mistyped, or the page may have moved.</p>
        <Link to="/"><Button>Back to the home page</Button></Link>
      </div>
    </main>
  )
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Fallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/app" element={<RequireAuth><AppShell /></RequireAuth>}>
          <Route path="employee" element={only('employee', <Employee />)} />
          <Route path="manager" element={only('manager', <Manager />)} />
          <Route path="procurement" element={only('procurement', <Procurement />)} />
          <Route path="vendor" element={only('vendor', <Vendor />)} />
          <Route path="finance" element={only('finance', <Finance />)} />
          <Route path="admin" element={only('admin', <Admin />)} />
          <Route path="admin/users" element={only('admin', <Users />)} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
