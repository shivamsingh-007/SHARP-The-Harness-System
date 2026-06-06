import { create } from 'zustand'
import type {
  HealthResponse,
  AggregateMetrics,
  ConnectionsResponse,
  ExecutionCurrent,
  SafetyResponse,
  TimeseriesResponse,
} from '../types'

interface DashboardState {
  connected: boolean
  health: HealthResponse | null
  metrics: AggregateMetrics | null
  connections: ConnectionsResponse | null
  execution: ExecutionCurrent | null
  safety: SafetyResponse | null
  timeseries: TimeseriesResponse | null
  timeRange: number
  activeTab: string

  setConnected: (v: boolean) => void
  setHealth: (v: HealthResponse) => void
  setMetrics: (v: AggregateMetrics) => void
  setConnections: (v: ConnectionsResponse) => void
  setExecution: (v: ExecutionCurrent) => void
  setSafety: (v: SafetyResponse) => void
  setTimeseries: (v: TimeseriesResponse) => void
  setTimeRange: (v: number) => void
  setActiveTab: (v: string) => void
  updateFromSnapshot: (data: {
    health: HealthResponse
    metrics: AggregateMetrics
    execution: ExecutionCurrent
    safety: SafetyResponse
  }) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  connected: false,
  health: null,
  metrics: null,
  connections: null,
  execution: null,
  safety: null,
  timeseries: null,
  timeRange: 60,
  activeTab: 'overview',

  setConnected: (v) => set({ connected: v }),
  setHealth: (v) => set({ health: v }),
  setMetrics: (v) => set({ metrics: v }),
  setConnections: (v) => set({ connections: v }),
  setExecution: (v) => set({ execution: v }),
  setSafety: (v) => set({ safety: v }),
  setTimeseries: (v) => set({ timeseries: v }),
  setTimeRange: (v) => set({ timeRange: v }),
  setActiveTab: (v) => set({ activeTab: v }),
  updateFromSnapshot: (data) =>
    set({
      health: data.health,
      metrics: data.metrics,
      execution: data.execution,
      safety: data.safety,
    }),
}))
