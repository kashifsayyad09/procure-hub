import { useCountUp } from '@/animations/gsap/useCountUp'
import { formatNumber } from '@/utils'
import { Card } from './Card'

export interface Stat { id: string; label: string; value: number; prefix?: string; suffix?: string; note: string }

export function StatCard({ stat }: { stat: Stat }) {
  const shown = useCountUp(stat.value)
  return (
    <Card data-reveal className="flex flex-col gap-u3 p-u10">
      <p className="text-sm text-muted">{stat.label}</p>
      <p className="font-display text-5xl font-medium tracking-display" aria-label={`${stat.label}: ${stat.prefix ?? ''}${formatNumber(stat.value)}${stat.suffix ?? ''}`}>
        <span aria-hidden>{stat.prefix}{formatNumber(shown)}{stat.suffix}</span>
      </p>
      <p className="text-sm text-muted">{stat.note}</p>
    </Card>
  )
}
