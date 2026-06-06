export interface HealthResponse {
  status: string;
  uptime_seconds: number;
  last_run_seconds_ago: number | null;
  environment: string;
  connections_healthy: number;
  connections_total: number;
  version: string;
}

export interface AggregateMetrics {
  total_traces: number;
  successful_traces: number;
  failed_traces: number;
  total_tokens: number;
  total_cost: number;
  avg_latency_ms: number;
  success_rate: number;
  error_rate: number;
}

export interface TraceDetail {
  trace_id: string;
  latency_ms: number;
  tokens_used: number;
  cost_usd: number;
  success: boolean;
  timestamp: number;
}

export interface TimeseriesPoint {
  label: string;
  latency_p50: number;
  latency_p95: number;
  throughput: number;
  tokens: number;
  cost: number;
}

export interface TimeseriesResponse {
  points: TimeseriesPoint[];
}

export interface ConnectionMetric {
  label: string;
  value: string;
}

export interface ConnectionItem {
  id: string;
  name: string;
  type: string;
  status: string;
  status_label: string;
  metrics: ConnectionMetric[];
  uptime_pct: number;
}

export interface ConnectionsResponse {
  connections: ConnectionItem[];
}

export interface ExecutionStep {
  step_type: string;
  content: string;
  iteration: number;
  timestamp: number;
  duration_ms: number;
  tool_name: string | null;
  tool_args: Record<string, unknown> | null;
}

export interface ExecutionCurrent {
  active: boolean;
  iteration: number;
  steps: ExecutionStep[];
  done: boolean;
  final_answer: string;
  strategy: string;
  total_steps: number;
  total_tokens: number;
  total_cost: number;
  started_at: number | null;
}

export interface CircuitBreakerStatus {
  state: string;
  failure_count: number;
  threshold: number;
  recovery_seconds: number;
}

export interface BudgetStatus {
  session_tokens: number;
  session_cost: number;
  total_tokens: number;
  total_cost: number;
  token_limit: number;
  cost_limit: number;
  token_usage_pct: number;
  cost_usage_pct: number;
}

export interface SafetyResponse {
  circuit_breaker: CircuitBreakerStatus;
  budget: BudgetStatus;
  recent_errors: Array<{ error: string; timestamp: number }>;
}

export interface WSSnapshot {
  health: HealthResponse;
  metrics: AggregateMetrics;
  execution: ExecutionCurrent;
  safety: SafetyResponse;
  timestamp: number;
}

export interface MCPServerItem {
  name: string;
  transport: string;
  command: string | null;
  args: string[];
  url: string | null;
  enabled: boolean;
  description: string;
  connected: boolean;
}

export interface MCPServersResponse {
  servers: MCPServerItem[];
  connected: string[];
  tools: string[];
  resources: string[];
  prompts: string[];
}

export interface PluginItem {
  name: string;
  description: string;
  risk_level: string;
  source: string;
  server?: string;
}

export interface PluginsResponse {
  builtin: PluginItem[];
  mcp: PluginItem[];
  total: number;
}
