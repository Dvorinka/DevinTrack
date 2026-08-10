import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Table, Th, Td, Tr } from '@/ui/table'
import { Badge } from '@/ui/badge'
import { formatTokens, formatMs, formatTime, formatCost, modelColor } from '@/lib/utils'
import { SourceBadge } from '@/components/SourceBadge'
import type { UsageRow } from '@/types'

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
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent requests</CardTitle>
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
            {data.map((r) => {
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
