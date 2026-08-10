import { effortStyle } from '@/lib/utils'

export function ReasoningBadge({ effort }: { effort: string | null | undefined }) {
  const style = effortStyle(effort)
  if (!style) return null
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
    >
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${style.text.replace('text-', 'bg-')}`} />
      {style.label}
    </span>
  )
}
