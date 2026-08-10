import { useState, useRef, useEffect } from 'react'
import type { CwdEntry } from '@/api'
import { ChevronDown, Folder } from 'lucide-react'

function shortPath(cwd: string): string {
  const parts = cwd.split('/')
  if (parts.length <= 3) return cwd
  return '.../' + parts.slice(-2).join('/')
}

export function CwdFilter({
  cwdList,
  value,
  onChange,
}: {
  cwdList: CwdEntry[]
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

  const selected = cwdList.find((c) => c.cwd === value)

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 bg-secondary text-foreground text-xs rounded-md px-3 py-1.5 border border-border hover:bg-secondary/80 transition-colors"
        title={value === 'all' ? 'All folders' : value}
      >
        <Folder size={12} className="text-amber-400" />
        <span className="font-medium">
          {value === 'all' ? 'All folders' : (selected ? shortPath(selected.cwd) : 'Folder')}
        </span>
        <ChevronDown size={12} className="text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[240px] max-w-[400px] rounded-lg border border-border bg-card shadow-lg overflow-hidden">
          <button
            onClick={() => { onChange('all'); setOpen(false) }}
            className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-secondary transition-colors ${
              value === 'all' ? 'bg-secondary font-medium' : ''
            }`}
          >
            <Folder size={12} className="text-muted-foreground" />
            <span>All folders</span>
            <span className="ml-auto text-muted-foreground">
              {cwdList.reduce((sum, c) => sum + c.session_count, 0)}
            </span>
          </button>
          {cwdList.map((c) => (
            <button
              key={c.cwd}
              onClick={() => { onChange(c.cwd); setOpen(false) }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-secondary transition-colors ${
                value === c.cwd ? 'bg-secondary font-medium' : ''
              }`}
              title={c.cwd}
            >
              <Folder size={12} className="text-amber-400" />
              <span className="truncate text-foreground">{shortPath(c.cwd)}</span>
              <span className="ml-auto text-muted-foreground shrink-0">{c.session_count}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
