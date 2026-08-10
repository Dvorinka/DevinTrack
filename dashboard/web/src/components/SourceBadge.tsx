import { Server } from 'lucide-react'

const sourceStyles: Record<string, { bg: string; text: string; ring: string; label: string }> = {
  local: { bg: 'bg-secondary', text: 'text-muted-foreground', ring: '', label: 'Local' },
  proxmox: { bg: 'bg-orange-500/15', text: 'text-orange-400', ring: 'ring-1 ring-orange-500/30', label: 'Proxmox' },
  remote: { bg: 'bg-sky-500/15', text: 'text-sky-400', ring: 'ring-1 ring-sky-500/30', label: 'Remote' },
}

export function SourceBadge({ source }: { source: string | null | undefined }) {
  if (!source || source === 'local') return null
  const s = sourceStyles[source] ?? {
    bg: 'bg-muted',
    text: 'text-muted-foreground',
    ring: '',
    label: source,
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${s.bg} ${s.text} ${s.ring}`}>
      <Server size={9} />
      {s.label}
    </span>
  )
}
