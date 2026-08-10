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
  new_input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  cached_write_tokens: number
  prompt_count: number
  session_count: number
  estimated_cost: number
}

export interface TimeSeriesPoint {
  date: string
  input_tokens: number
  new_input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  local_input_tokens?: number
  local_new_input_tokens?: number
  local_output_tokens?: number
  local_cached_read_tokens?: number
  remote_input_tokens?: number
  remote_new_input_tokens?: number
  remote_output_tokens?: number
  remote_cached_read_tokens?: number
}

export interface ModelBreakdown {
  model: string
  display_name: string
  input_tokens: number
  new_input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  prompt_count: number
  estimated_cost: number
}

export interface UsageRow {
  id: number
  timestamp: string
  session_id: string
  request_id: string
  model: string | null
  model_display_name: string | null
  input_tokens: number
  new_input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  cached_write_tokens: number
  duration_ms: number
  stop_reason: string | null
  error_message: string | null
  estimated_cost: number
  source: string
}

export interface SessionSummary {
  session_id: string
  created_at: string
  updated_at: string
  model: string | null
  model_display_name: string | null
  reasoning_effort: string | null
  cwd: string | null
  first_prompt: string | null
  description: string | null
  prompt_count: number
  input_tokens: number
  new_input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_read_tokens: number
  total_duration_ms: number
  estimated_cost: number
  source: string
}

export interface SessionDetail {
  session_id: string
  created_at: string
  updated_at: string
  model: string | null
  model_display_name: string | null
  reasoning_effort: string | null
  cwd: string | null
  first_prompt: string | null
  description: string | null
  source: string
  requests: UsageRow[]
  totals: {
    input_tokens: number
    new_input_tokens: number
    output_tokens: number
    total_tokens: number
    cached_read_tokens: number
    cached_write_tokens: number
    duration_ms: number
    estimated_cost: number
  }
}

export interface Performance {
  avg_latency_ms: number
  median_latency_ms: number
  max_latency_ms: number
  error_count: number
  cancelled_count: number
}
