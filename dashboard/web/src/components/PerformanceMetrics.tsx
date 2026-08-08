import { Card, CardHeader, CardTitle, CardContent } from '@/ui/card'
import { formatMs } from '@/lib/utils'
import type { Performance } from '@/types'
import { Clock, AlertTriangle, XCircle, TrendingUp } from 'lucide-react'
import type { ReactNode } from 'react'

function Metric({
  label,
  value,
  icon,
  accent,
}: {
  label: string
  value: string
  icon: ReactNode
  accent: string
}) {
  return (
    <div className="flex items-center gap-3">
      <span className={accent}>{icon}</span>
      <div>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="font-mono text-sm font-medium tabular-nums">{value}</div>
      </div>
    </div>
  )
}

export function PerformanceMetrics({ data }: { data: Performance }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-5">
          <Metric
            label="Avg latency"
            value={formatMs(data.avg_latency_ms)}
            icon={<Clock size={16} />}
            accent="text-sky-400"
          />
          <Metric
            label="Median latency"
            value={formatMs(data.median_latency_ms)}
            icon={<Clock size={16} />}
            accent="text-sky-300"
          />
          <Metric
            label="Longest request"
            value={formatMs(data.max_latency_ms)}
            icon={<TrendingUp size={16} />}
            accent="text-amber-400"
          />
          <div />
          <Metric
            label="Errors"
            value={String(data.error_count)}
            icon={<XCircle size={16} />}
            accent={data.error_count > 0 ? 'text-red-400' : 'text-muted-foreground'}
          />
          <Metric
            label="Cancelled / max tokens"
            value={String(data.cancelled_count)}
            icon={<AlertTriangle size={16} />}
            accent={data.cancelled_count > 0 ? 'text-amber-400' : 'text-muted-foreground'}
          />
        </div>
      </CardContent>
    </Card>
  )
}
