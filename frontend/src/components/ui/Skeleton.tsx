import type { HTMLAttributes } from 'react'
import clsx from 'clsx'

export function Skeleton({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={clsx('animate-pulse rounded-ctl bg-pill', className)} {...rest} />
}
