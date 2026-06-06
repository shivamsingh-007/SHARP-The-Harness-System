import type {
  HealthResponse,
  AggregateMetrics,
  TraceDetail,
  TimeseriesResponse,
  ConnectionsResponse,
  ExecutionCurrent,
  SafetyResponse,
} from '../types'

const BASE = ''

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  health: () => fetchJSON<HealthResponse>('/api/health'),
  metricsAggregate: () => fetchJSON<AggregateMetrics>('/api/metrics/aggregate'),
  metricsTraces: () => fetchJSON<TraceDetail[]>('/api/metrics/traces'),
  metricsTimeseries: (window = 60) =>
    fetchJSON<TimeseriesResponse>(`/api/metrics/timeseries?window=${window}`),
  connections: () => fetchJSON<ConnectionsResponse>('/api/connections'),
  executionCurrent: () => fetchJSON<ExecutionCurrent>('/api/execution/current'),
  safety: () => fetchJSON<SafetyResponse>('/api/safety'),
  config: () => fetchJSON<Record<string, unknown>>('/api/config'),
  run: (request: string) =>
    fetch(`${BASE}/api/engine/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request }),
    }).then((r) => r.json()),
}
