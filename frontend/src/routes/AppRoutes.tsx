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
const VendorProfile = lazy(() => import('@/pages/vendor/VendorProfilePage'))
const VendorProfileForm = lazy(() => import('@/pages/vendor/VendorProfileFormPage'))
const Rfqs = lazy(() => import('@/pages/procurement/RfqsPage'))
const RfqNew = lazy(() => import('@/pages/procurement/RfqNewPage'))
const RfqDetail = lazy(() => import('@/pages/procurement/RfqDetailPage'))
const RfqEdit = lazy(() => import('@/pages/procurement/RfqEditPage'))
const RfqCompare = lazy(() => import('@/pages/procurement/RfqComparePage'))
const VendorRfqs = lazy(() => import('@/pages/vendor/RfqsPage'))
const VendorRfqDetail = lazy(() => import('@/pages/vendor/RfqDetailPage'))
const QuotationForm = lazy(() => import('@/pages/vendor/QuotationFormPage'))
const Vendors = lazy(() => import('@/pages/procurement/VendorsPage'))
const VendorDetail = lazy(() => import('@/pages/procurement/VendorDetailPage'))
const VendorForm = lazy(() => import('@/pages/procurement/VendorFormPage'))
const Finance = lazy(() => import('@/pages/finance/FinanceDashboard'))
const Admin = lazy(() => import('@/pages/admin/AdminDashboard'))
const Users = lazy(() => import('@/pages/admin/UsersPage'))
const Requests = lazy(() => import('@/pages/employee/RequestsPage'))
const RequestForm = lazy(() => import('@/pages/employee/RequestFormPage'))
const RequestDetail = lazy(() => import('@/pages/employee/RequestDetailPage'))
const Approvals = lazy(() => import('@/pages/manager/ApprovalsPage'))
const ApprovalDetail = lazy(() => import('@/pages/manager/ApprovalDetailPage'))

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
          <Route path="employee/requests" element={only('employee', <Requests />)} />
          <Route path="employee/requests/new" element={only('employee', <RequestForm />)} />
          <Route path="employee/requests/:id" element={only('employee', <RequestDetail />)} />
          <Route path="employee/requests/:id/edit" element={only('employee', <RequestForm />)} />
          <Route path="manager" element={only('manager', <Manager />)} />
          <Route path="manager/approvals" element={only('manager', <Approvals />)} />
          <Route path="manager/approvals/:id" element={only('manager', <ApprovalDetail />)} />
          <Route path="procurement" element={only('procurement', <Procurement />)} />
          <Route path="procurement/vendors" element={only('procurement', <Vendors />)} />
          <Route path="procurement/vendors/new" element={only('procurement', <VendorForm />)} />
          <Route path="procurement/vendors/:id" element={only('procurement', <VendorDetail />)} />
          <Route path="procurement/vendors/:id/edit" element={only('procurement', <VendorForm />)} />
          <Route path="procurement/rfqs" element={only('procurement', <Rfqs />)} />
          <Route path="procurement/rfqs/new" element={only('procurement', <RfqNew />)} />
          <Route path="procurement/rfqs/:id" element={only('procurement', <RfqDetail />)} />
          <Route path="procurement/rfqs/:id/edit" element={only('procurement', <RfqEdit />)} />
          <Route path="procurement/rfqs/:id/compare" element={only('procurement', <RfqCompare />)} />
          <Route path="vendor" element={only('vendor', <Vendor />)} />
          <Route path="vendor/rfqs" element={only('vendor', <VendorRfqs />)} />
          <Route path="vendor/rfqs/:id" element={only('vendor', <VendorRfqDetail />)} />
          <Route path="vendor/rfqs/:id/quote" element={only('vendor', <QuotationForm />)} />
          <Route path="vendor/profile" element={only('vendor', <VendorProfile />)} />
          <Route path="vendor/profile/edit" element={only('vendor', <VendorProfileForm />)} />
          <Route path="finance" element={only('finance', <Finance />)} />
          <Route path="admin" element={only('admin', <Admin />)} />
          <Route path="admin/users" element={only('admin', <Users />)} />
          <Route path="admin/vendors" element={only('admin', <Vendors />)} />
          <Route path="admin/vendors/new" element={only('admin', <VendorForm />)} />
          <Route path="admin/vendors/:id" element={only('admin', <VendorDetail />)} />
          <Route path="admin/vendors/:id/edit" element={only('admin', <VendorForm />)} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
