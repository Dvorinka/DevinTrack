import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { Table, Th, Td, Tr } from '@/ui/table'
import { formatTokens, formatMs, formatTime } from '@/lib/utils'
import type { SessionSummary } from '@/types'

export function SessionList({
  data,
  onSelect,
}: {
  data: SessionSummary[]
  onSelect: (id: string) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sessions</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <thead>
            <tr>
              <Th>Session</Th>
              <Th>Model</Th>
              <Th className="text-right">Prompts</Th>
              <Th className="text-right">Input</Th>
              <Th className="text-right">Output</Th>
              <Th className="text-right">Total</Th>
              <Th className="text-right">Cached</Th>
              <Th className="text-right">Duration</Th>
              <Th>Updated</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <Tr
                key={s.session_id}
                onClick={() => onSelect(s.session_id)}
                className="cursor-pointer"
              >
                <Td>
                  <span className="font-mono text-xs text-sky-400">{s.session_id}</span>
                </Td>
                <Td>
                  <span className="font-mono text-xs">{s.model ?? '-'}</span>
                </Td>
                <Td className="text-right font-mono tabular-nums text-xs">{s.prompt_count}</Td>
                <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(s.input_tokens)}</Td>
                <Td className="text-right font-mono tabular-nums text-xs">{formatTokens(s.output_tokens)}</Td>
                <Td className="text-right font-mono tabular-nums text-xs font-medium">{formatTokens(s.total_tokens)}</Td>
                <Td className="text-right font-mono tabular-nums text-xs text-purple-400">
                  {s.cached_read_tokens > 0 ? formatTokens(s.cached_read_tokens) : '-'}
                </Td>
                <Td className="text-right font-mono tabular-nums text-xs text-muted-foreground">
                  {formatMs(s.total_duration_ms)}
                </Td>
                <Td className="font-mono text-xs text-muted-foreground">{formatTime(s.updated_at)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </CardContent>
    </Card>
  )
}
