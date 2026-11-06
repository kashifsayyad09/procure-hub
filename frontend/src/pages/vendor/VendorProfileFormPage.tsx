import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ApiError, vendorsApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { VendorForm } from '@/features/vendors/VendorForm'

/** Creates the vendor user's own record the first time, edits it afterwards. */
export default function VendorProfileFormPage() {
  const mine = useQuery({ queryKey: ['vendor', 'me'], queryFn: vendorsApi.mine, retry: false })
  const missing = mine.error instanceof ApiError && mine.error.status === 404
  if (mine.isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading your profile</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (mine.isError && !missing) return <ErrorState description={mine.error instanceof ApiError ? mine.error.message : 'Try again in a moment.'} onRetry={() => void mine.refetch()} />
  const existing = mine.data
  if (existing && !existing.actions.includes('edit')) return <ErrorState title="You cannot edit this profile" description="A suspended vendor cannot change its profile. Contact procurement." />
  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to="/app/vendor/profile" className="text-sm text-muted underline-offset-4 hover:underline">Back to your profile</Link>
        <h1 className="display-lg mt-u3">{existing ? 'Edit your profile' : 'Register your company'}</h1>
        {existing?.status === 'verified' && <p className="mt-u4 max-w-xl text-muted">Changing the company name, tax ID, registration number or country means a reviewer must verify the profile again.</p>}
      </header>
      <VendorForm key={existing?.id ?? 'new'} mode={existing ? 'edit' : 'register'} existing={existing} after={() => '/app/vendor/profile'} />
    </div>
  )
}
