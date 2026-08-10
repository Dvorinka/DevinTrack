import { useState, useMemo, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Table, Th, Td, Tr } from '@/ui/table'
import { Button } from '@/ui/button'
import { formatTokens, formatMs, formatTime, formatCost, modelColor, baseModelName } from '@/lib/utils'
import { ReasoningBadge } from '@/components/ReasoningBadge'
import { SourceBadge } from '@/components/SourceBadge'
import type { SessionSummary } from '@/types'
import { ChevronLeft, ChevronRight, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react'

const PAGE_SIZE = 5

type SortKey = 'updated_at' | 'prompt_count' | 'new_input_tokens' | 'output_tokens' | 'total_tokens' | 'cached_read_tokens' | 'estimated_cost' | 'total_duration_ms'
type SortDir = 'asc' | 'desc'

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

export function SessionList({
  data,
  onSelect,
}: {
  data: SessionSummary[]
  onSelect: (id: string) => void
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
    const sorted = [...data].sort((a, b) => {
      const av = a[sortKey] ?? 0
      const bv = b[sortKey] ?? 0
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
    return sorted
  }, [data, sortKey, sortDir])

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)
  const start = page * PAGE_SIZE
  const pageData = sorted.slice(start, start + PAGE_SIZE)

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Sessions ({data.length})</CardTitle>
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
              <Th>Session</Th>
              <Th>Description / First prompt</Th>
              <Th>Model</Th>
              <Th>Reasoning</Th>
              <Th>Source</Th>
              <SortHeader label="Prompts" sortKey="prompt_count" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="New input" sortKey="new_input_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Output" sortKey="output_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Billable" sortKey="total_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Cache reads" sortKey="cached_read_tokens" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Cost" sortKey="estimated_cost" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Duration" sortKey="total_duration_ms" activeKey={sortKey} dir={sortDir} onSort={handleSort} align="right" />
              <SortHeader label="Updated" sortKey="updated_at" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
            </tr>
          </thead>
          <tbody>
            {pageData.map((s) => {
              const mc = modelColor(s.model)
              const isRemote = s.source && s.source !== 'local'
              return (
                <Tr
                  key={s.session_id}
                  onClick={() => onSelect(s.session_id)}
                  className={`cursor-pointer ${isRemote ? 'bg-orange-500/[0.03]' : ''}`}
                >
                  <Td>
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full ${isRemote ? 'bg-orange-400' : mc.dot}`} />
                      <span className="font-mono text-xs text-sky-400">{s.session_id}</span>
                    </div>
                  </Td>
                  <Td className="max-w-[240px] truncate">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs text-foreground truncate">
                        {s.description || s.first_prompt || (
                          <span className="text-muted-foreground italic">no prompt</span>
                        )}
                      </span>
                      {s.cwd && (
                        <span className="text-[10px] text-muted-foreground/70 font-mono truncate" title={s.cwd}>
                          {s.cwd}
                        </span>
                      )}
                    </div>
                  </Td>
                  <Td>
                    <span className={`text-xs ${mc.text}`}>
                      {baseModelName(s.model_display_name ?? s.model)}
                    </span>
                  </Td>
                  <Td>
                    <ReasoningBadge effort={s.reasoning_effort} />
                  </Td>
                  <Td>
                    <SourceBadge source={s.source} />
                  </Td>
                  <Td className="text-right font-mono tabular-nums text-xs">{s.prompt_count}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(s.new_input_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(s.output_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs font-medium">{formatTokens(s.total_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs text-purple-400">
                    {s.cached_read_tokens > 0 ? formatTokens(s.cached_read_tokens) : '-'}
                  </Td>
                  <Td className="text-right font-mono tabular-nums text-xs text-green-400">
                    {s.estimated_cost > 0 ? formatCost(s.estimated_cost) : '-'}
                  </Td>
                  <Td className="text-right font-mono tabular-nums text-xs text-muted-foreground">
                    {formatMs(s.total_duration_ms)}
                  </Td>
                  <Td className="font-mono text-xs text-muted-foreground">{formatTime(s.updated_at)}</Td>
                </Tr>
              )
            })}
          </tbody>
        </Table>
      </CardContent>
    </Card>
  )
}
