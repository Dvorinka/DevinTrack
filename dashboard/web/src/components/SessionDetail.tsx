import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Button } from '@/ui/button'
import { Badge } from '@/ui/badge'
import { Table, Th, Td, Tr } from '@/ui/table'
import { formatTokens, formatMs, formatTime, formatDate, formatCost, modelColor } from '@/lib/utils'
import { ReasoningBadge } from '@/components/ReasoningBadge'
import { SourceBadge } from '@/components/SourceBadge'
import type { SessionDetail } from '@/types'
import { ArrowLeft } from 'lucide-react'

const stopTone: Record<string, 'success' | 'error' | 'warning' | 'muted'> = {
  end_turn: 'success',
  error: 'error',
  cancelled: 'warning',
  max_tokens: 'warning',
}

export function SessionDetail({
  data,
  onBack,
}: {
  data: SessionDetail
  onBack: () => void
}) {
  const t = data.totals
  const started = formatDate(data.created_at)
  const updated = formatTime(data.updated_at)
  const mc = modelColor(data.model)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft size={14} className="mr-1" />
          Back
        </Button>
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2.5 h-2.5 rounded-full ${mc.dot}`} />
          <h2 className="text-lg font-semibold font-mono">{data.session_id}</h2>
        </div>
        {data.model && (
          <Badge className={mc.text}>
            {data.model_display_name ?? data.model}
          </Badge>
        )}
        <ReasoningBadge effort={data.reasoning_effort} />
        <SourceBadge source={data.source} />
      </div>

      {(data.description || data.first_prompt) && (
        <Card className="p-4">
          {data.description && (
            <div className="mb-2">
              <div className="text-xs text-muted-foreground mb-1">Description</div>
              <div className="text-sm font-medium">{data.description}</div>
            </div>
          )}
          {data.first_prompt && (
            <div className="mb-2">
              <div className="text-xs text-muted-foreground mb-1">First prompt</div>
              <div className="text-sm font-mono">{data.first_prompt}</div>
            </div>
          )}
          {data.cwd && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">Working directory</div>
              <div className="text-xs font-mono text-muted-foreground">{data.cwd}</div>
            </div>
          )}
        </Card>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Requests</div>
          <div className="font-mono text-xl font-semibold tabular-nums">{data.requests.length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Started</div>
          <div className="font-mono text-sm font-medium">{started}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Last active</div>
          <div className="font-mono text-sm font-medium">{updated}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Total duration</div>
          <div className="font-mono text-xl font-semibold tabular-nums">{formatMs(t.duration_ms)}</div>
        </Card>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Est. cost</div>
          <div className="font-mono text-xl font-semibold tabular-nums text-green-400">{formatCost(t.estimated_cost)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">New input</div>
          <div className="font-mono text-xl font-semibold tabular-nums text-blue-400">{formatTokens(t.new_input_tokens)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Total output</div>
          <div className="font-mono text-xl font-semibold tabular-nums text-emerald-400">{formatTokens(t.output_tokens)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Total tokens</div>
          <div className="font-mono text-xl font-semibold tabular-nums text-amber-400">{formatTokens(t.total_tokens)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Cached read</div>
          <div className="font-mono text-xl font-semibold tabular-nums text-purple-400">{formatTokens(t.cached_read_tokens)}</div>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Requests</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <thead>
              <tr>
                <Th>Time</Th>
                <Th>Req ID</Th>
                <Th>Model</Th>
                <Th className="text-right">Input</Th>
                <Th className="text-right">Output</Th>
                <Th className="text-right">Total</Th>
                <Th className="text-right">Cached</Th>
                <Th className="text-right">Cost</Th>
                <Th className="text-right">Duration</Th>
                <Th>Stop</Th>
              </tr>
            </thead>
            <tbody>
              {data.requests.map((r) => {
                const rmc = modelColor(r.model)
                return (
                  <Tr key={r.id}>
                    <Td className="font-mono text-xs text-muted-foreground">{formatTime(r.timestamp)}</Td>
                    <Td className="font-mono text-xs">{r.request_id}</Td>
                    <Td>
                      <div className="flex items-center gap-1.5">
                        <span className={`inline-block w-1.5 h-1.5 rounded-full ${rmc.dot}`} />
                        <span className={`text-xs ${rmc.text}`}>
                          {r.model_display_name ?? r.model ?? '-'}
                        </span>
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
    </div>
  )
}
