import { useState, useEffect, useCallback } from 'react'
import { PeriodSelector } from '@/components/PeriodSelector'
import { OverviewCards } from '@/components/OverviewCards'
import { UsageChart } from '@/components/UsageChart'
import { ModelBreakdown } from '@/components/ModelBreakdown'
import { RecentRequests } from '@/components/RecentRequests'
import { PerformanceMetrics } from '@/components/PerformanceMetrics'
import { SessionList } from '@/components/SessionList'
import { SessionDetail } from '@/components/SessionDetail'
import {
  getOverview,
  getTimeseries,
  getModels,
  getRecent,
  getSessions,
  getSessionDetail,
  getPerformance,
} from '@/api'
import type {
  Period,
  Overview,
  TimeSeriesPoint,
  ModelBreakdown as ModelData,
  UsageRow,
  SessionSummary,
  SessionDetail as SessionDetailData,
  Performance,
} from '@/types'

export default function App() {
  const [period, setPeriod] = useState<Period>('7d')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [timeseries, setTimeseries] = useState<TimeSeriesPoint[]>([])
  const [models, setModels] = useState<ModelData[]>([])
  const [recent, setRecent] = useState<UsageRow[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [perf, setPerf] = useState<Performance | null>(null)
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [sessionDetail, setSessionDetail] = useState<SessionDetailData | null>(null)
  const [loading, setLoading] = useState(true)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, ts, md, re, se, pf] = await Promise.all([
        getOverview(period),
        getTimeseries(period),
        getModels(period),
        getRecent(30),
        getSessions(),
        getPerformance(period),
      ])
      setOverview(ov)
      setTimeseries(ts)
      setModels(md)
      setRecent(re)
      setSessions(se)
      setPerf(pf)
    } catch (e) {
      console.error('load error', e)
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  const selectSession = useCallback(async (id: string) => {
    setSelectedSession(id)
    try {
      const detail = await getSessionDetail(id)
      setSessionDetail(detail)
    } catch (e) {
      console.error('session detail error', e)
    }
  }, [])

  if (selectedSession && sessionDetail) {
    return (
      <div className="min-h-screen bg-background p-6 max-w-7xl mx-auto">
        <SessionDetail data={sessionDetail} onBack={() => { setSelectedSession(null); setSessionDetail(null) }} />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight">DevinTrack</h1>
            {loading && (
              <span className="text-xs text-muted-foreground animate-pulse">loading...</span>
            )}
          </div>
          <PeriodSelector value={period} onChange={setPeriod} />
        </div>

        {/* Overview cards */}
        {overview && <OverviewCards data={overview} />}

        {/* Chart + Models */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <UsageChart data={timeseries} />
          </div>
          <div>
            <ModelBreakdown data={models} />
          </div>
        </div>

        {/* Recent + Performance */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <RecentRequests data={recent} onSelectSession={selectSession} />
          </div>
          <div>
            {perf && <PerformanceMetrics data={perf} />}
          </div>
        </div>

        {/* Sessions */}
        <SessionList data={sessions} onSelect={selectSession} />
      </div>
    </div>
  )
}
