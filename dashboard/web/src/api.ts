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

export function getOverview(period: Period): Promise<Overview> {
  return fetchJSON(`${BASE}/overview?period=${period}`)
}

export function getTimeseries(period: Period): Promise<TimeSeriesPoint[]> {
  return fetchJSON(`${BASE}/timeseries?period=${period}`)
}

export function getModels(period: Period): Promise<ModelBreakdown[]> {
  return fetchJSON(`${BASE}/models?period=${period}`)
}

export function getRecent(limit = 20): Promise<UsageRow[]> {
  return fetchJSON(`${BASE}/recent?limit=${limit}`)
}

export function getSessions(): Promise<SessionSummary[]> {
  return fetchJSON(`${BASE}/sessions`)
}

export function getSessionDetail(id: string): Promise<SessionDetail> {
  return fetchJSON(`${BASE}/sessions/${id}`)
}

export function getPerformance(period: Period): Promise<Performance> {
  return fetchJSON(`${BASE}/performance?period=${period}`)
}
