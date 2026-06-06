import { useDashboardStore } from '../../store/dashboardStore'
import { StatusBadge } from '../shared/StatusBadge'
import { Activity, Zap } from 'lucide-react'
import { formatCost, formatNumber } from '../../lib/utils'

const tabs = ['Overview', 'Sessions', 'Config', 'Logs']

export function Header() {
  const { health, metrics, connected, activeTab, setActiveTab, timeRange, setTimeRange } =
    useDashboardStore()

  const status = health?.status || 'stopped'
  const statusLabel = status === 'running' ? 'Running' : status === 'degraded' ? 'Degraded' : 'Stopped'

  return (
    <header className="h-16 border-b border-border bg-bg-card/80 backdrop-blur-sm flex items-center px-6 gap-6 sticky top-0 z-50">
      <div className="flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
          <Zap size={18} className="text-accent" />
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-tight">SHARP</h1>
          <p className="text-[10px] text-muted leading-none">Harness System</p>
        </div>
        <span className="text-[10px] text-muted bg-bg-elevated px-2 py-0.5 rounded-full border border-border">
          v0.1.0
        </span>
      </div>

      <nav className="flex items-center gap-1 bg-bg-elevated rounded-lg p-1 border border-border">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab.toLowerCase())}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
              activeTab === tab.toLowerCase()
                ? 'bg-accent/20 text-accent'
                : 'text-muted hover:text-text-dim'
            }`}
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="flex-1" />

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Activity size={14} className={connected ? 'text-accent' : 'text-muted'} />
          <span className="text-[11px] text-muted">
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>

        <StatusBadge status={status} label={statusLabel} />

        <div className="flex items-center gap-1 bg-bg-elevated rounded-md border border-border">
          {[
            { label: '5m', value: 5 },
            { label: '1h', value: 60 },
            { label: '24h', value: 1440 },
          ].map((r) => (
            <button
              key={r.value}
              onClick={() => setTimeRange(r.value)}
              className={`px-2 py-1 text-[10px] font-medium rounded transition-colors ${
                timeRange === r.value
                  ? 'bg-accent/20 text-accent'
                  : 'text-muted hover:text-text-dim'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        {metrics && (
          <div className="text-right">
            <p className="text-[10px] text-muted">Tokens today</p>
            <p className="text-xs font-mono font-semibold">{formatNumber(metrics.total_tokens)}</p>
          </div>
        )}

        {metrics && (
          <div className="text-right">
            <p className="text-[10px] text-muted">Cost</p>
            <p className="text-xs font-mono font-semibold">{formatCost(metrics.total_cost)}</p>
          </div>
        )}
      </div>
    </header>
  )
}
