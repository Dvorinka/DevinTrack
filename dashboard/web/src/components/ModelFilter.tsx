import { modelColor } from '@/lib/utils'
import type { ModelBreakdown } from '@/types'
import { ChevronDown } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

export function ModelFilter({
  models,
  value,
  onChange,
}: {
  models: ModelBreakdown[]
  value: string
  onChange: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const selected = models.find((m) => m.model === value)
  const selectedColor = modelColor(value === 'all' ? null : value)

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 bg-secondary text-foreground text-xs rounded-md px-3 py-1.5 border border-border hover:bg-secondary/80 transition-colors"
      >
        {value !== 'all' && (
          <span className={`inline-block w-2 h-2 rounded-full ${selectedColor.dot}`} />
        )}
        <span className="font-medium">
          {value === 'all' ? 'All models' : (selected?.display_name ?? value)}
        </span>
        {value !== 'all' && selected && (
          <span className="text-muted-foreground">{selected.prompt_count}</span>
        )}
        <ChevronDown size={12} className="text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[200px] rounded-lg border border-border bg-card shadow-lg overflow-hidden">
          <button
            onClick={() => { onChange('all'); setOpen(false) }}
            className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-secondary transition-colors ${
              value === 'all' ? 'bg-secondary font-medium' : ''
            }`}
          >
            <span className="inline-block w-2 h-2 rounded-full bg-gray-400" />
            <span>All models</span>
            <span className="ml-auto text-muted-foreground">
              {models.reduce((sum, m) => sum + m.prompt_count, 0)}
            </span>
          </button>
          {models.map((m) => {
            const mc = modelColor(m.model)
            return (
              <button
                key={m.model}
                onClick={() => { onChange(m.model); setOpen(false) }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-secondary transition-colors ${
                  value === m.model ? 'bg-secondary font-medium' : ''
                }`}
              >
                <span className={`inline-block w-2 h-2 rounded-full ${mc.dot}`} />
                <span className={mc.text}>{m.display_name}</span>
                <span className="ml-auto text-muted-foreground">{m.prompt_count}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
