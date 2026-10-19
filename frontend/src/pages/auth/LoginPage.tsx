import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Field } from '@/components/forms/Field'
import { Button } from '@/components/ui/Button'
import { Logo } from '@/components/layout/Sidebar'
import { ThemeToggle } from '@/components/layout/Topbar'
import { SceneBackdrop } from '@/three/SceneBackdrop'
import { ROLES } from '@/types/roles'

export const loginSchema = z.object({
  email: z.string().min(1, 'Enter your work email').email('Enter a valid email address'),
  password: z.string().min(8, 'Use at least 8 characters'),
})
type LoginValues = z.infer<typeof loginSchema>

export default function LoginPage() {
  const [notice, setNotice] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  // Phase 1 is UI only: no credentials are sent anywhere. Real sign-in is Phase 2.
  const onSubmit = () => setNotice('Your details look valid, but sign-in is not connected yet. It arrives in Phase 2. Use a workspace preview below for now.')

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col px-u8 py-u8 sm:px-u20">
        <div className="flex items-center justify-between"><Logo /><ThemeToggle /></div>
        <main id="main" className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-u12 py-u16">
          <div>
            <h1 className="display-lg">Sign in</h1>
            <p className="mt-u4 text-muted">Use the email your administrator registered for you.</p>
          </div>
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-u8">
            <Field label="Work email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
            <Field label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
            <Button type="submit" size="lg" loading={isSubmitting}>Sign in</Button>
            {notice && <p role="status" className="rounded-ctl bg-violet/25 p-u7 text-violet-ink">{notice}</p>}
          </form>
          <div>
            <p className="text-sm text-muted">Preview a workspace (Phase 1 only)</p>
            <ul className="mt-u4 flex flex-wrap gap-u3">
              {ROLES.map((r) => <li key={r.id}><Link to={r.path} className="inline-flex min-h-[44px] items-center rounded-full bg-pill px-u8 hover:bg-panel">{r.label}</Link></li>)}
            </ul>
          </div>
        </main>
      </div>
      <aside className="relative hidden overflow-hidden border-l border-line bg-panel/60 lg:block">
        <SceneBackdrop className="absolute inset-0" />
        <p className="absolute bottom-u16 left-u16 right-u16 font-display text-4xl leading-tight tracking-display">Approvals, quotations, orders and invoices, in one place.</p>
      </aside>
    </div>
  )
}
