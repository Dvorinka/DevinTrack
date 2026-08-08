import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

type Tone = 'default' | 'success' | 'error' | 'warning' | 'muted'

const tones: Record<Tone, string> = {
  default: 'bg-secondary text-secondary-foreground',
  success: 'bg-emerald-500/15 text-emerald-400',
  error: 'bg-red-500/15 text-red-400',
  warning: 'bg-amber-500/15 text-amber-400',
  muted: 'bg-muted text-muted-foreground',
}

export function Badge({
  className,
  tone = 'default',
  children,
}: {
  className?: string
  tone?: Tone
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
