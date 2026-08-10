import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { formatTokens } from '@/lib/utils'
import type { TimeSeriesPoint, Period } from '@/types'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-card p-3 text-xs shadow-lg">
      <div className="font-medium mb-2">{label}</div>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center gap-2 mb-1">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm"
            style={{ background: entry.color }}
          />
          <span className="text-muted-foreground">{entry.name}:</span>
          <span className="font-mono tabular-nums">{formatTokens(entry.value)}</span>
        </div>
      ))}
    </div>
  )
}

function formatXAxisTick(value: string, period: Period) {
  if (period === 'today' || period === 'yesterday') {
    const parts = value.split(' ')
    return parts.length > 1 ? parts[1] : value
  }
  const parts = value.split('-')
  return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : value
}

export function UsageChart({ data, period }: { data: TimeSeriesPoint[]; period: Period }) {
  const title = period === 'today' || period === 'yesterday'
    ? 'Token usage by hour'
    : 'Token usage by day'

  // Check if any remote data exists to show the second stack group.
  const hasRemote = data.some(
    (d) => (d.remote_input_tokens ?? 0) > 0 || (d.remote_output_tokens ?? 0) > 0
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">
            No data for this period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} maxBarSize={48}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => formatXAxisTick(v, period)}
              />
              <YAxis
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => formatTokens(v)}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'hsl(var(--accent))', opacity: 0.3 }} />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                iconType="square"
                iconSize={8}
              />

              {/* Local stack — blue/purple/green */}
              <Bar dataKey="local_new_input_tokens" name="Local Input" stackId="local" fill="#3b82f6" radius={[0, 0, 0, 0]} />
              <Bar dataKey="local_cached_read_tokens" name="Local Cached" stackId="local" fill="#a855f7" radius={[0, 0, 0, 0]} />
              <Bar dataKey="local_output_tokens" name="Local Output" stackId="local" fill="#10b981" radius={[hasRemote ? 0 : 3, hasRemote ? 0 : 3, 0, 0]} />

              {/* Remote (Proxmox) stack — orange/amber/red, side by side */}
              {hasRemote && (
                <>
                  <Bar dataKey="remote_new_input_tokens" name="Proxmox Input" stackId="remote" fill="#f97316" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="remote_cached_read_tokens" name="Proxmox Cached" stackId="remote" fill="#fbbf24" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="remote_output_tokens" name="Proxmox Output" stackId="remote" fill="#ef4444" radius={[3, 3, 0, 0]} />
                </>
              )}
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
