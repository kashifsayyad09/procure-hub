import type { HTMLAttributes } from 'react'
import clsx from 'clsx'

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('rounded-card border border-line bg-surface p-u12 shadow-card', className)} {...rest} />
}
