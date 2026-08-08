import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Button } from '@/ui/button'
import { Badge } from '@/ui/badge'
import { Table, Th, Td, Tr } from '@/ui/table'
import { formatTokens, formatMs, formatTime, formatDate } from '@/lib/utils'
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

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft size={14} className="mr-1" />
          Back
        </Button>
        <h2 className="text-lg font-semibold font-mono">{data.session_id}</h2>
        {data.model && <Badge>{data.model}</Badge>}
      </div>

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

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground mb-1">Total input</div>
          <div className="font-mono text-xl font-semibold tabular-nums text-blue-400">{formatTokens(t.input_tokens)}</div>
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
                <Th className="text-right">Input</Th>
                <Th className="text-right">Output</Th>
                <Th className="text-right">Total</Th>
                <Th className="text-right">Cached</Th>
                <Th className="text-right">Duration</Th>
                <Th>Stop</Th>
              </tr>
            </thead>
            <tbody>
              {data.requests.map((r) => (
                <Tr key={r.id}>
                  <Td className="font-mono text-xs text-muted-foreground">{formatTime(r.timestamp)}</Td>
                  <Td className="font-mono text-xs">{r.request_id}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(r.input_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(r.output_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs font-medium">{formatTokens(r.total_tokens)}</Td>
                  <Td className="text-right font-mono tabular-nums text-xs text-purple-400">
                    {r.cached_read_tokens > 0 ? formatTokens(r.cached_read_tokens) : '-'}
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
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
