export type Period = 'today' | 'yesterday' | '7d' | '30d' | 'month' | 'year' | 'all'

export const PERIODS: { value: Period; label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: 'month', label: 'Month' },
  { value: 'year', label: 'Year' },
  { value: 'all', label: 'All time' },
]

export interface Overview {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  cached_write_tokens: number
  prompt_count: number
  session_count: number
}

export interface TimeSeriesPoint {
  date: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
}

export interface ModelBreakdown {
  model: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  prompt_count: number
}

export interface UsageRow {
  id: number
  timestamp: string
  session_id: string
  request_id: string
  model: string | null
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  cached_write_tokens: number
  duration_ms: number
  stop_reason: string | null
  error_message: string | null
}

export interface SessionSummary {
  session_id: string
  created_at: string
  updated_at: string
  model: string | null
  prompt_count: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  total_duration_ms: number
}

export interface SessionDetail {
  session_id: string
  created_at: string
  updated_at: string
  model: string | null
  requests: UsageRow[]
  totals: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cached_read_tokens: number
    cached_write_tokens: number
    duration_ms: number
  }
}

export interface Performance {
  avg_latency_ms: number
  median_latency_ms: number
  max_latency_ms: number
  error_count: number
  cancelled_count: number
}
