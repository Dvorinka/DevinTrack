import { useState, useEffect, useCallback } from 'react'
import { PeriodSelector } from '@/components/PeriodSelector'
import { OverviewCards } from '@/components/OverviewCards'
import { UsageChart } from '@/components/UsageChart'
import { ModelBreakdown } from '@/components/ModelBreakdown'
import { RecentRequests } from '@/components/RecentRequests'
import { PerformanceMetrics } from '@/components/PerformanceMetrics'
import { SessionList } from '@/components/SessionList'
import { SessionDetail } from '@/components/SessionDetail'
import { ModelFilter } from '@/components/ModelFilter'
import {
  getOverview,
  getTimeseries,
  getModels,
  getRecent,
  getSessions,
  getSessionDetail,
  getPerformance,
  resetAllData,
  reprocessLog,
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
import { Trash2, RefreshCw } from 'lucide-react'

export default function App() {
  const [period, setPeriod] = useState<Period>('7d')
  const [modelFilter, setModelFilter] = useState<string>('all')
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
        getOverview(period, modelFilter),
        getTimeseries(period, modelFilter),
        getModels(period),
        getRecent(30, modelFilter),
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
  }, [period, modelFilter])

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

  const handleReset = useCallback(async () => {
    if (!confirm('Delete ALL usage and session data? This cannot be undone.')) return
    try {
      await resetAllData()
      setSelectedSession(null)
      setSessionDetail(null)
      await loadDashboard()
    } catch (e) {
      console.error('reset error', e)
    }
  }, [loadDashboard])

  const handleReprocess = useCallback(async () => {
    setLoading(true)
    try {
      const result = await reprocessLog()
      const msg = `Reprocessed ${result.processed} events, inserted ${result.inserted}, removed ${result.deleted_duplicates} duplicates.`
      alert(msg)
      await loadDashboard()
    } catch (e) {
      console.error('reprocess error', e)
      alert('Reprocess failed: ' + String(e))
    } finally {
      setLoading(false)
    }
  }, [loadDashboard])

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
          <div className="flex items-center gap-3">
            {models.length > 0 && (
              <ModelFilter models={models} value={modelFilter} onChange={setModelFilter} />
            )}
            <PeriodSelector value={period} onChange={setPeriod} />
            <button
              onClick={handleReprocess}
              disabled={loading}
              className="flex items-center gap-1.5 bg-secondary text-foreground text-xs rounded-md px-3 py-1.5 border border-border hover:bg-sky-500/10 hover:border-sky-500/50 hover:text-sky-400 transition-colors disabled:opacity-50"
              title="Re-read wrapper.log and fix usage rows from agent_stopped events"
            >
              <RefreshCw size={12} />
              Reprocess
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 bg-secondary text-foreground text-xs rounded-md px-3 py-1.5 border border-border hover:bg-red-500/10 hover:border-red-500/50 hover:text-red-400 transition-colors"
              title="Delete all data"
            >
              <Trash2 size={12} />
              Reset
            </button>
          </div>
        </div>

        {/* Overview cards */}
        {overview && <OverviewCards data={overview} />}

        {/* Chart + Models */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <UsageChart data={timeseries} period={period} />
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
