import { Server } from 'lucide-react'

// Presets for known sources — Tailwind classes (JIT-safe).
const presets: Record<string, { bg: string; text: string; ring: string; label: string }> = {
  local: { bg: 'bg-secondary', text: 'text-muted-foreground', ring: '', label: 'Local' },
  proxmox: { bg: 'bg-orange-500/15', text: 'text-orange-400', ring: 'ring-1 ring-orange-500/30', label: 'Proxmox' },
  remote: { bg: 'bg-sky-500/15', text: 'text-sky-400', ring: 'ring-1 ring-sky-500/30', label: 'Remote' },
}

// Color palette for dynamic sources — picked by hashing the source name.
const palette = [
  { h: 210 }, // sky
  { h: 280 }, // purple
  { h: 340 }, // rose
  { h: 160 }, // emerald
  { h: 30 },  // amber
  { h: 190 }, // cyan
  { h: 120 }, // green
  { h: 0 },   // red
  { h: 250 }, // indigo
  { h: 300 }, // fuchsia
]

function hashSource(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

function dynamicStyle(source: string) {
  const { h } = palette[hashSource(source) % palette.length]
  return {
    backgroundColor: `hsl(${h}, 70%, 95%)`,
    color: `hsl(${h}, 70%, 35%)`,
    boxShadow: `inset 0 0 0 1px hsl(${h}, 70%, 70%)`,
  }
}

export function SourceBadge({ source }: { source: string | null | undefined }) {
  if (!source || source === 'local') return null

  const preset = presets[source]
  const label = preset?.label ?? source

  if (preset) {
    return (
      <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${preset.bg} ${preset.text} ${preset.ring}`}>
        <Server size={9} />
        {label}
      </span>
    )
  }

  return (
    <span
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium"
      style={dynamicStyle(source)}
    >
      <Server size={9} />
      {label}
    </span>
  )
}
