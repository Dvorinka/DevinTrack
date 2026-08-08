import { Card } from '@/ui/card'
import { formatTokens } from '@/lib/utils'
import type { Overview } from '@/types'
import { ArrowDownRight, ArrowUpRight, Database, FileText, Layers, Zap } from 'lucide-react'
import type { ReactNode } from 'react'

function StatCard({
  label,
  value,
  icon,
  accent,
}: {
  label: string
  value: number
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
        {formatTokens(value)}
      </div>
      <div className="text-xs text-muted-foreground mt-1 font-mono tabular-nums">
        {value.toLocaleString()}
      </div>
    </Card>
  )
}

export function OverviewCards({ data }: { data: Overview }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
      <StatCard
        label="Input"
        value={data.input_tokens}
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
      <StatCard
        label="Cached Write"
        value={data.cached_write_tokens}
        icon={<Database size={16} />}
        accent="text-purple-300"
      />
      <StatCard
        label="Prompts"
        value={data.prompt_count}
        icon={<FileText size={16} />}
        accent="text-sky-400"
      />
      <StatCard
        label="Sessions"
        value={data.session_count}
        icon={<Layers size={16} />}
        accent="text-indigo-400"
      />
    </div>
  )
}
