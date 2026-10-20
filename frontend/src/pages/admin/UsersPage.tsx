import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { ApiError, usersApi } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { ROLES, type Role } from '@/types/roles'
import type { UserRecord } from '@/types/auth'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { Drawer, Modal } from '@/components/ui/Overlay'
import { Field } from '@/components/forms/Field'

const PAGE_SIZE = 10
const roleLabel = (r: string) => ROLES.find((x) => x.id === r)?.label ?? r
const selectCls = 'h-11 rounded-ctl border border-line bg-surface px-u6'

export const createUserSchema = z.object({
  full_name: z.string().trim().min(1, 'Enter a name'),
  email: z.string().min(1, 'Enter an email').email('Enter a valid email address'),
  role: z.enum(['employee', 'manager', 'procurement', 'vendor', 'finance', 'admin']),
  password: z.string().min(12, 'Use at least 12 characters').regex(/[A-Za-z]/, 'Include a letter').regex(/\d/, 'Include a number'),
})
type CreateValues = z.infer<typeof createUserSchema>

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [serverError, setServerError] = useState('')
  const { register, handleSubmit, reset, formState: { errors } } = useForm<CreateValues>({ resolver: zodResolver(createUserSchema), defaultValues: { role: 'employee' } })
  const create = useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['users'] }); reset(); onClose() },
    onError: (e) => setServerError(e instanceof ApiError ? e.message : 'Could not create the user.'),
  })
  const close = () => { setServerError(''); onClose() }
  return (
    <Modal open={open} onClose={close} title="Add a user"
      footer={<><Button variant="soft" onClick={close}>Cancel</Button><Button type="submit" form="create-user" loading={create.isPending}>Create user</Button></>}>
      <form id="create-user" noValidate onSubmit={handleSubmit((v) => { setServerError(''); create.mutate(v) })} className="flex flex-col gap-u8">
        <Field label="Full name" autoComplete="off" error={errors.full_name?.message} {...register('full_name')} />
        <Field label="Work email" type="email" autoComplete="off" error={errors.email?.message} {...register('email')} />
        <label className="flex flex-col gap-u3"><span className="text-sm font-medium">Role</span>
          <select className={selectCls} {...register('role')}>{ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select>
        </label>
        <Field label="Initial password" type="password" autoComplete="new-password" hint="At least 12 characters with a letter and a number. Share it securely." error={errors.password?.message} {...register('password')} />
        {serverError && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{serverError}</p>}
      </form>
    </Modal>
  )
}

function EditUserDrawer({ user, onClose }: { user: UserRecord | null; onClose: () => void }) {
  const qc = useQueryClient()
  const me = useAuthStore((s) => s.user)
  const [role, setRole] = useState<Role | null>(null)
  const [error, setError] = useState('')
  const isSelf = user?.id === me?.id
  const save = useMutation({
    mutationFn: (body: Parameters<typeof usersApi.update>[1]) => usersApi.update(user!.id, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['users'] }); setRole(null); onClose() },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save the change.'),
  })
  const close = () => { setError(''); setRole(null); onClose() }
  return (
    <Drawer open={!!user} onClose={close} title={user?.full_name ?? 'User'}>
      {user && (
        <div className="flex flex-col gap-u10">
          <dl className="flex flex-col gap-u5">
            <div><dt className="text-sm text-muted">Email</dt><dd>{user.email}</dd></div>
            <div><dt className="text-sm text-muted">Last sign-in</dt><dd>{user.last_login_at ? new Date(user.last_login_at + 'Z').toLocaleString() : 'Never'}</dd></div>
          </dl>
          <label className="flex flex-col gap-u3"><span className="text-sm font-medium">Role</span>
            <select className={selectCls} value={role ?? user.role} disabled={isSelf} onChange={(e) => setRole(e.target.value as Role)}>
              {ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          </label>
          {isSelf && <p className="text-sm text-muted">You cannot change your own role or suspend yourself.</p>}
          <div className="flex flex-wrap gap-u4">
            <Button loading={save.isPending} disabled={isSelf || role === null || role === user.role} onClick={() => { setError(''); save.mutate({ role: role! }) }}>Save role</Button>
            <Button variant={user.is_active ? 'outline' : 'primary'} disabled={isSelf} onClick={() => { setError(''); save.mutate({ is_active: !user.is_active }) }}>
              {user.is_active ? 'Suspend account' : 'Reactivate account'}
            </Button>
          </div>
          <p className="text-sm text-muted">Changing a role or suspending an account signs the person out everywhere.</p>
          {error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}
        </div>
      )}
    </Drawer>
  )
}

export default function UsersPage() {
  const [q, setQ] = useState('')
  const [role, setRole] = useState<Role | ''>('')
  const [active, setActive] = useState<'' | 'true' | 'false'>('')
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<UserRecord | null>(null)
  const query = { q: q.trim() || undefined, role, is_active: active, page, page_size: PAGE_SIZE }
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['users', query], queryFn: () => usersApi.list(query), placeholderData: (prev) => prev })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const reset = (fn: () => void) => { fn(); setPage(1) }

  return (
    <div className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-end justify-between gap-u8">
        <div><h1 className="display-lg">Users and roles</h1><p className="mt-u4 max-w-xl text-muted">Add people, assign roles and suspend access. The server enforces every change.</p></div>
        <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> Add user</Button>
      </header>
      <Card>
        <div className="mb-u8 flex flex-wrap gap-u4">
          <label className="min-w-[12rem] flex-1"><span className="sr-only">Search users</span>
            <input type="search" placeholder="Search name or email" value={q} onChange={(e) => reset(() => setQ(e.target.value))} className="h-11 w-full rounded-ctl border border-line bg-surface px-u8 placeholder:text-muted" /></label>
          <label><span className="sr-only">Filter by role</span>
            <select className={selectCls} value={role} onChange={(e) => reset(() => setRole(e.target.value as Role | ''))}><option value="">All roles</option>{ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
          <label><span className="sr-only">Filter by status</span>
            <select className={selectCls} value={active} onChange={(e) => reset(() => setActive(e.target.value as '' | 'true' | 'false'))}><option value="">Any status</option><option value="true">Active</option><option value="false">Suspended</option></select></label>
        </div>
        {isLoading ? <div aria-busy="true" className="flex flex-col gap-u4"><span className="sr-only">Loading users</span>{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          : isError ? <ErrorState description={(error as Error).message} onRetry={() => void refetch()} />
          : !data || data.items.length === 0 ? <EmptyState title="No users found" description="Change the search or filters, or add a user." />
          : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[34rem] border-collapse text-left">
                  <caption className="sr-only">Users</caption>
                  <thead><tr className="border-b border-line text-sm text-muted"><th scope="col" className="px-u4 py-u5 font-medium">Name</th><th scope="col" className="px-u4 py-u5 font-medium">Role</th><th scope="col" className="px-u4 py-u5 font-medium">Status</th></tr></thead>
                  <tbody>
                    {data.items.map((u) => (
                      <tr key={u.id} className="border-b border-line last:border-0">
                        <td className="px-u4 py-u4"><button onClick={() => setEditing(u)} className="min-h-[44px] text-left underline-offset-4 hover:underline"><span className="block font-medium">{u.full_name}</span><span className="block text-sm text-muted">{u.email}</span></button></td>
                        <td className="px-u4 py-u4">{roleLabel(u.role)}</td>
                        <td className="px-u4 py-u4"><Badge tone={u.is_active ? 'ok' : 'bad'}>{u.is_active ? 'Active' : 'Suspended'}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <nav aria-label="Pagination" className="mt-u8 flex items-center justify-between gap-u4">
                <p className="text-sm text-muted">{data.total} {data.total === 1 ? 'user' : 'users'}, page {data.page} of {pages}</p>
                <div className="flex gap-u3"><Button variant="soft" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="soft" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
              </nav>
            </>
          )}
      </Card>
      <CreateUserModal open={creating} onClose={() => setCreating(false)} />
      <EditUserDrawer user={editing} onClose={() => setEditing(null)} />
    </div>
  )
}
