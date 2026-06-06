import { useDashboardStore } from '../../store/dashboardStore'
import { timeAgo } from '../../lib/utils'

export function StatusBar() {
  const { health } = useDashboardStore()

  const uptime = health?.uptime_seconds || 0
  const healthy = health?.connections_healthy || 0
  const total = health?.connections_total || 0
  const lastRun = health?.last_run_seconds_ago

  return (
    <footer className="h-8 border-t border-border bg-bg-card/60 backdrop-blur-sm flex items-center px-6 gap-6 text-[11px] text-muted shrink-0">
      <div className="flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${uptime > 0 ? 'bg-accent' : 'bg-muted'}`} />
        <span>
          Uptime:{' '}
          <span className="font-mono text-text-dim">
            {uptime > 0 ? `${Math.floor(uptime / 60)}m ${Math.floor(uptime % 60)}s` : 'N/A'}
          </span>
        </span>
      </div>

      <div className="w-px h-3 bg-border" />

      <span>
        Environment:{' '}
        <span className="font-mono text-text-dim">{health?.environment || 'development'}</span>
      </span>

      <div className="w-px h-3 bg-border" />

      <span>
        Connections:{' '}
        <span className="font-mono text-text-dim">
          {healthy}/{total} healthy
        </span>
      </span>

      <div className="w-px h-3 bg-border" />

      <span>
        Last run:{' '}
        <span className="font-mono text-text-dim">
          {lastRun !== null && lastRun !== undefined ? timeAgo(lastRun) : 'never'}
        </span>
      </span>

      <div className="flex-1" />

      <span className="text-[10px]">
        SHARP Dashboard · {new Date().toLocaleDateString()}
      </span>
    </footer>
  )
}
