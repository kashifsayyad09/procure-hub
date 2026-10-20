import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Field } from '@/components/forms/Field'
import { Button } from '@/components/ui/Button'
import { Logo } from '@/components/layout/Sidebar'
import { ThemeToggle } from '@/components/layout/Topbar'
import { SceneBackdrop } from '@/three/SceneBackdrop'
import { ApiError } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { roleById } from '@/types/roles'

export const loginSchema = z.object({
  email: z.string().min(1, 'Enter your work email').email('Enter a valid email address'),
  password: z.string().min(8, 'Use at least 8 characters'),
})
type LoginValues = z.infer<typeof loginSchema>

function messageFor(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 429) return 'Too many failed attempts. Wait a few minutes, then try again.'
    return e.message
  }
  return 'Something went wrong. Try again.'
}

export default function LoginPage() {
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  if (status === 'authenticated' && user) return <Navigate to={roleById(user.role)?.path ?? '/'} replace />

  const onSubmit = async (values: LoginValues) => {
    setError('')
    try {
      const u = await login(values.email.trim(), values.password)
      navigate(roleById(u.role)?.path ?? '/', { replace: true })
    } catch (e) {
      setError(messageFor(e))
    }
  }

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
            <Field label="Work email" type="email" autoComplete="username" error={errors.email?.message} {...register('email')} />
            <Field label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
            <Button type="submit" size="lg" loading={isSubmitting}>Sign in</Button>
            {error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}
          </form>
          <p className="text-sm text-muted">Forgot your password? Ask your administrator to reset it.</p>
        </main>
      </div>
      <aside className="relative hidden overflow-hidden border-l border-line bg-panel/60 lg:block">
        <SceneBackdrop className="absolute inset-0" />
        <p className="absolute bottom-u16 left-u16 right-u16 font-display text-4xl leading-tight tracking-display">Approvals, quotations, orders and invoices, in one place.</p>
      </aside>
    </div>
  )
}
