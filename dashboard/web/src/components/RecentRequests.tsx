import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Table, Th, Td, Tr } from '@/ui/table'
import { Badge } from '@/ui/badge'
import { Button } from '@/ui/button'
import { formatTokens, formatMs, formatTime, formatCost, modelColor } from '@/lib/utils'
import { SourceBadge } from '@/components/SourceBadge'
import type { UsageRow } from '@/types'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 5

const stopTone: Record<string, 'success' | 'error' | 'warning' | 'muted'> = {
  end_turn: 'success',
  error: 'error',
  cancelled: 'warning',
  max_tokens: 'warning',
}

export function RecentRequests({
  data,
  onSelectSession,
}: {
  data: UsageRow[]
  onSelectSession: (id: string) => void
}) {
  const [page, setPage] = useState(0)
  const totalPages = Math.ceil(data.length / PAGE_SIZE)
  const start = page * PAGE_SIZE
  const pageData = data.slice(start, start + PAGE_SIZE)

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
              <Th>Time</Th>
              <Th>Model</Th>
              <Th>Session</Th>
              <Th className="text-right">New input</Th>
              <Th className="text-right">Output</Th>
              <Th className="text-right">Billable</Th>
              <Th className="text-right">Cache reads</Th>
              <Th className="text-right">Cost</Th>
              <Th className="text-right">Duration</Th>
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
                        {r.model_display_name ?? r.model ?? '-'}
                      </span>
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
