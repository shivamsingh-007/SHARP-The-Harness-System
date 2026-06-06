import { useState } from 'react'
import type { ConnectionItem as ConnectionItemType } from '../../types'
import { StatusBadge } from '../shared/StatusBadge'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '../../lib/utils'

interface ConnectionItemProps {
  connection: ConnectionItemType
}

export function ConnectionItem({ connection }: ConnectionItemProps) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="rounded-lg border border-border bg-bg-elevated/50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-bg-elevated transition-colors"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-muted shrink-0" />
        ) : (
          <ChevronRight size={14} className="text-muted shrink-0" />
        )}

        <div className="flex-1 text-left">
          <p className="text-xs font-medium text-text-dim">{connection.name}</p>
        </div>

        <StatusBadge status={connection.status} label={connection.status_label} />
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          <div className="grid grid-cols-3 gap-2">
            {connection.metrics.map((m) => (
              <div key={m.label} className="text-center">
                <p className="text-[10px] text-muted uppercase tracking-wide">{m.label}</p>
                <p className="text-sm font-mono font-semibold text-text-dim mt-0.5">{m.value}</p>
              </div>
            ))}
          </div>

          {connection.uptime_pct > 0 && (
            <div className="flex items-center gap-2 pt-1 border-t border-border/50">
              <span className="text-[10px] text-muted">Uptime:</span>
              <div className="flex-1 h-1 bg-bg-card rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    connection.uptime_pct >= 99
                      ? 'bg-accent'
                      : connection.uptime_pct >= 95
                      ? 'bg-warning'
                      : 'bg-critical'
                  )}
                  style={{ width: `${Math.min(100, connection.uptime_pct)}%` }}
                />
              </div>
              <span className="text-[10px] font-mono text-text-dim">
                {connection.uptime_pct.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
