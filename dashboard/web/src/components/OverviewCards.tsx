import { Card } from '@/ui/card'
import { formatTokens, formatCost } from '@/lib/utils'
import type { Overview } from '@/types'
import { ArrowDownRight, ArrowUpRight, Database, Zap, DollarSign } from 'lucide-react'
import type { ReactNode } from 'react'

function StatCard({
  label,
  value,
  displayValue,
  icon,
  accent,
}: {
  label: string
  value: number
  displayValue?: string
  icon: ReactNode
  accent: string
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground font-medium">{label}</span>
        <span className={accent}>{icon}</span>
      </div>
      <div className="font-mono text-2xl font-semibold tabular-nums">
        {displayValue ?? formatTokens(value)}
      </div>
      <div className="text-xs text-muted-foreground mt-1 font-mono tabular-nums">
        {displayValue ? formatTokens(value) : value.toLocaleString()}
      </div>
    </Card>
  )
}

export function OverviewCards({ data }: { data: Overview }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
      <StatCard
        label="Est. Cost"
        value={data.estimated_cost}
        displayValue={formatCost(data.estimated_cost)}
        icon={<DollarSign size={16} />}
        accent="text-green-400"
      />
      <StatCard
        label="Input (new)"
        value={data.new_input_tokens}
        icon={<ArrowDownRight size={16} />}
        accent="text-blue-400"
      />
      <StatCard
        label="Output"
        value={data.output_tokens}
        icon={<ArrowUpRight size={16} />}
        accent="text-emerald-400"
      />
      <StatCard
        label="Total"
        value={data.total_tokens}
        icon={<Zap size={16} />}
        accent="text-amber-400"
      />
      <StatCard
        label="Cached Read"
        value={data.cached_read_tokens}
        icon={<Database size={16} />}
        accent="text-purple-400"
      />
    </div>
  )
}
