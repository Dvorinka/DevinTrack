import { useState, useMemo, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Table, Th, Td, Tr } from '@/ui/table'
import { Badge } from '@/ui/badge'
import { Button } from '@/ui/button'
import { formatTokens, formatMs, formatTime, formatCost, modelColor, baseModelName } from '@/lib/utils'
import { SourceBadge } from '@/components/SourceBadge'
import { ReasoningBadge } from '@/components/ReasoningBadge'
import type { UsageRow } from '@/types'
import { ChevronLeft, ChevronRight, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react'

const PAGE_SIZE = 5

type SortKey = 'timestamp' | 'new_input_tokens' | 'output_tokens' | 'total_tokens' | 'cached_read_tokens' | 'estimated_cost' | 'duration_ms'
type SortDir = 'asc' | 'desc'

const stopTone: Record<string, 'success' | 'error' | 'warning' | 'muted'> = {
  end_turn: 'success',
  error: 'error',
  cancelled: 'warning',
  max_tokens: 'warning',
}

function SortHeader({
  label,
  sortKey,
  activeKey,
  dir,
  onSort,
  align = 'left',
}: {
  label: string
  sortKey: SortKey
  activeKey: SortKey | null
  dir: SortDir
  onSort: (k: SortKey) => void
  align?: 'left' | 'right'
}) {
  const isActive = activeKey === sortKey
  const Icon = isActive ? (dir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown
  return (
    <Th
      className={`cursor-pointer select-none hover:text-foreground transition-colors ${align === 'right' ? 'text-right' : ''}`}
      onClick={() => onSort(sortKey)}
    >
      <span className={`inline-flex items-center gap-1 ${align === 'right' ? 'flex-row-reverse' : ''}`}>
        {label}
        <Icon size={11} className={isActive ? 'text-foreground' : 'text-muted-foreground/50'} />
      </span>
    </Th>
  )
}

export function RecentRequests({
  data,
  onSelectSession,
}: {
  data: UsageRow[]
  onSelectSession: (id: string) => void
}) {
  const [page, setPage] = useState(0)
  const [sortKey, setSortKey] = useState<SortKey | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const handleSort = useCallback((k: SortKey) => {
    if (sortKey === k) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(k)
      setSortDir('desc')
    }
    setPage(0)
  }, [sortKey])

  const sorted = useMemo(() => {
    if (!sortKey) return data
    return [...data].sort((a, b) => {
      const av = a[sortKey] ?? 0
      const bv = b[sortKey] ?? 0
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
  }, [data, sortKey, sortDir])

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)
  const start = page * PAGE_SIZE
  const pageData = sorted.slice(start, start + PAGE_SIZE)

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Recent requests ({data.length})</CardTitle>
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft size={14} />
            </Button>
            <span className="text-xs text-muted-foreground font-mono tabular-nums">
              {page + 1} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <Table>
          <thead>
            <tr>
              <SortHeader label="Time" sortKey="timestamp" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
              <Th>Model</Th>
              <Th>Session</Th>
              <SortHeader label="New input" sortKey="new_input_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Output" sortKey="output_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Billable" sortKey="total_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Cache reads" sortKey="cached_read_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Cost" sortKey="estimated_cost" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Duration" sortKey="duration_ms" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <Th>Stop</Th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((r) => {
              const mc = modelColor(r.model)
              return (
                <Tr key={r.id}>
                  <Td className="font-mono text-xs text-muted-foreground">{formatTime(r.timestamp)}</Td>
                  <Td>
                    <div className="flex items-center gap-1.5">
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${mc.dot}`} />
                      <span className={`text-xs ${mc.text}`}>
                        {baseModelName(r.model_display_name ?? r.model)}
                      </span>
                      <ReasoningBadge effort={r.reasoning_effort} />
                    </div>
                  </Td>
                  <Td>
                    <div className="flex items-center gap-1.5">
                      <button
                        className="font-mono text-xs text-sky-400 hover:text-sky-300 hover:underline text-left"
                        onClick={() => onSelectSession(r.session_id)}
                      >
                        {r.session_id}
                      </button>
                      <SourceBadge source={r.source} />
                    </div>
                  </Td>
                  <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(r.new_input_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(r.output_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs font-medium">{formatTokens(r.total_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs text-purple-400">
                    {r.cached_read_tokens > 0 ? formatTokens(r.cached_read_tokens) : '-'}
                  </Td>
                  <Td className="text-right font-mono tabular-nums text-xs text-green-400">
                    {r.estimated_cost > 0 ? formatCost(r.estimated_cost) : '-'}
                  </Td>
                  <Td className="text-right font-mono tabular-nums text-xs text-muted-foreground">
                    {formatMs(r.duration_ms)}
                  </Td>
                  <Td>
                    {r.stop_reason && (
                      <Badge tone={stopTone[r.stop_reason] ?? 'muted'}>
                        {r.stop_reason}
                      </Badge>
                    )}
                  </Td>
                </Tr>
              )
            })}
          </tbody>
        </Table>
      </CardContent>
    </Card>
  )
}
