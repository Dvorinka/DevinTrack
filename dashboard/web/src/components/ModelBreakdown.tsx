import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { formatTokens } from '@/lib/utils'
import type { ModelBreakdown } from '@/types'

export function ModelBreakdown({ data }: { data: ModelBreakdown[] }) {
  const maxTotal = Math.max(...data.map((d) => d.total_tokens), 1)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Models</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <div className="text-muted-foreground text-sm py-8 text-center">
            No data for this period
          </div>
        ) : (
          <div className="space-y-4">
            {data.map((m) => (
              <div key={m.model}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-medium font-mono">{m.model}</span>
                  <span className="text-sm font-mono tabular-nums text-muted-foreground">
                    {formatTokens(m.total_tokens)}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${(m.total_tokens / maxTotal) * 100}%` }}
                  />
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                  <span>{m.prompt_count} prompts</span>
                  <span>in {formatTokens(m.input_tokens)}</span>
                  <span>out {formatTokens(m.output_tokens)}</span>
                  {m.cached_read_tokens > 0 && (
                    <span>cached {formatTokens(m.cached_read_tokens)}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
