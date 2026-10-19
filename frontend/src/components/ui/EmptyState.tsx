import type { ReactNode } from 'react'
import { Inbox, AlertTriangle } from 'lucide-react'
import { Button } from './Button'

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-u4 px-u8 py-u20 text-center">
      <Inbox className="h-8 w-8 text-muted" aria-hidden />
      <h3 className="text-xl">{title}</h3>
      <p className="max-w-sm text-muted">{description}</p>
      {action}
    </div>
  )
}

export function ErrorState({ title = 'Could not load this data', description, onRetry }: { title?: string; description: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-u4 px-u8 py-u20 text-center">
      <AlertTriangle className="h-8 w-8 text-bad" aria-hidden />
      <h3 className="text-xl">{title}</h3>
      <p className="max-w-sm text-muted">{description}</p>
      {onRetry && <Button variant="outline" onClick={onRetry}>Try again</Button>}
    </div>
  )
}
