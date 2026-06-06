import type {
  HealthResponse,
  AggregateMetrics,
  TraceDetail,
  TimeseriesResponse,
  ConnectionsResponse,
  ExecutionCurrent,
  SafetyResponse,
  MCPServersResponse,
  PluginsResponse,
} from '../types'

const BASE = ''

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  return res.json()
}

async function deleteJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
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

  // MCP Server Management
  mcpServers: () => fetchJSON<MCPServersResponse>('/api/mcp/servers'),
  mcpAddServer: (server: Record<string, unknown>) =>
    postJSON<{ ok: boolean; server: string }>('/api/mcp/servers', server),
  mcpRemoveServer: (name: string) =>
    deleteJSON<{ ok: boolean }>(`/api/mcp/servers/${name}`),
  mcpConnect: (name: string) =>
    postJSON<{ ok: boolean; connected: boolean }>(`/api/mcp/servers/${name}/connect`),
  mcpDisconnect: (name: string) =>
    postJSON<{ ok: boolean }>(`/api/mcp/servers/${name}/disconnect`),

  // Plugins
  plugins: () => fetchJSON<PluginsResponse>('/api/plugins'),

  // Engine
  run: (request: string) =>
    postJSON<Record<string, unknown>>('/api/engine/run', { request }),
}
