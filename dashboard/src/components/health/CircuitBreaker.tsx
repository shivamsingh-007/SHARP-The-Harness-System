import type { CircuitBreakerStatus } from '../../types'
import { cn } from '../../lib/utils'

interface CircuitBreakerProps {
  status: CircuitBreakerStatus
}

const stateConfig: Record<string, { label: string; color: string; bgColor: string; ringColor: string }> = {
  closed: {
    label: 'Normal',
    color: 'text-accent',
    bgColor: 'bg-accent/10',
    ringColor: 'ring-accent/30',
  },
  open: {
    label: 'Tripped',
    color: 'text-critical',
    bgColor: 'bg-critical/10',
    ringColor: 'ring-critical/30',
  },
  half_open: {
    label: 'Recovering',
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    ringColor: 'ring-warning/30',
  },
}

export function CircuitBreaker({ status }: CircuitBreakerProps) {
  const config = stateConfig[status.state] || stateConfig.closed
  const progress = (status.failure_count / status.threshold) * 100

  return (
    <div>
      <p className="kpi-label mb-2">Circuit Breaker</p>
      <div className={cn('rounded-lg border border-border p-3', config.bgColor)}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className={cn('w-8 h-8 rounded-full flex items-center justify-center ring-2', config.ringColor)}>
              <span className={cn('text-xs font-bold font-mono', config.color)}>
                {status.failure_count}
              </span>
            </div>
            <div>
              <p className={cn('text-xs font-semibold', config.color)}>{config.label}</p>
              <p className="text-[10px] text-muted">
                {status.failure_count}/{status.threshold} failures
              </p>
            </div>
          </div>
          {status.state !== 'closed' && (
            <span className="text-[10px] font-mono text-muted">
              Recovery: {status.recovery_seconds}s
            </span>
          )}
        </div>

        <div className="h-1.5 bg-bg-card rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              status.state === 'closed'
                ? 'bg-accent'
                : status.state === 'open'
                ? 'bg-critical'
                : 'bg-warning'
            )}
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
      </div>
    </div>
  )
}
