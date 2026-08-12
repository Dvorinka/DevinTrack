import type {
  Overview,
  TimeSeriesPoint,
  ModelBreakdown,
  UsageRow,
  SessionSummary,
  SessionDetail,
  Performance,
  Period,
} from './types'

const BASE = '/api'

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export function getOverview(period: Period, model: string = 'all'): Promise<Overview> {
  return fetchJSON(`${BASE}/overview?period=${period}&model=${model}`)
}

export function getTimeseries(period: Period, model: string = 'all'): Promise<TimeSeriesPoint[]> {
  return fetchJSON(`${BASE}/timeseries?period=${period}&model=${model}`)
}

export function getModels(period: Period): Promise<ModelBreakdown[]> {
  return fetchJSON(`${BASE}/models?period=${period}`)
}

export function getRecent(limit = 20, model: string = 'all'): Promise<UsageRow[]> {
  return fetchJSON(`${BASE}/recent?limit=${limit}&model=${model}`)
}

export function getSessions(cwdFilter: string = 'all', period: Period = 'all'): Promise<SessionSummary[]> {
  return fetchJSON(`${BASE}/sessions?cwd=${encodeURIComponent(cwdFilter)}&period=${period}`)
}

export function getSessionDetail(id: string): Promise<SessionDetail> {
  return fetchJSON(`${BASE}/sessions/${id}`)
}

export function getPerformance(period: Period): Promise<Performance> {
  return fetchJSON(`${BASE}/performance?period=${period}`)
}

export async function resetAllData(): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${BASE}/reset`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function reprocessLog(): Promise<{
  ok: boolean
  processed: number
  inserted: number
  deleted_duplicates: number
  sessions_affected: string[]
}> {
  const res = await fetch(`${BASE}/reprocess`, { method: 'POST' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface CwdEntry {
  cwd: string
  session_count: number
  prompt_count: number
}

export function getCwdList(): Promise<CwdEntry[]> {
  return fetchJSON(`${BASE}/cwd_list`)
}
