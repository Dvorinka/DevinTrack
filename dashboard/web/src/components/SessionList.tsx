import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Table, Th, Td, Tr } from '@/ui/table'
import { Button } from '@/ui/button'
import { formatTokens, formatMs, formatTime, formatCost, modelColor } from '@/lib/utils'
import { ReasoningBadge } from '@/components/ReasoningBadge'
import { SourceBadge } from '@/components/SourceBadge'
import type { SessionSummary } from '@/types'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 5

export function SessionList({
  data,
  onSelect,
}: {
  data: SessionSummary[]
  onSelect: (id: string) => void
}) {
  const [page, setPage] = useState(0)
  const totalPages = Math.ceil(data.length / PAGE_SIZE)
  const start = page * PAGE_SIZE
  const pageData = data.slice(start, start + PAGE_SIZE)

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
              <Th className="text-right">Prompts</Th>
              <Th className="text-right">New input</Th>
              <Th className="text-right">Output</Th>
              <Th className="text-right">Billable</Th>
              <Th className="text-right">Cache reads</Th>
              <Th className="text-right">Cost</Th>
              <Th className="text-right">Duration</Th>
              <Th>Updated</Th>
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
                    <span className="text-xs text-foreground">
                      {s.description || s.first_prompt || (
                        <span className="text-muted-foreground italic">no prompt</span>
                      )}
                    </span>
                  </Td>
                  <Td>
                    <span className={`text-xs ${mc.text}`}>
                      {s.model_display_name ?? s.model ?? '-'}
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
