import { cn } from '../../lib/utils'

interface StatusBadgeProps {
  status: string
  label?: string
  size?: 'sm' | 'md'
}

const statusColors: Record<string, string> = {
  connected: 'bg-accent/20 text-accent border border-accent/30',
  running: 'bg-accent/20 text-accent border border-accent/30',
  closed: 'bg-accent/20 text-accent border border-accent/30',
  degraded: 'bg-warning/20 text-warning border border-warning/30',
  half_open: 'bg-warning/20 text-warning border border-warning/30',
  open: 'bg-critical/20 text-critical border border-critical/30',
  disconnected: 'bg-critical/20 text-critical border border-critical/30',
  stopped: 'bg-critical/20 text-critical border border-critical/30',
  not_configured: 'bg-muted/20 text-muted border border-muted/30',
}

const dotColors: Record<string, string> = {
  connected: 'bg-accent',
  running: 'bg-accent',
  closed: 'bg-accent',
  degraded: 'bg-warning',
  half_open: 'bg-warning',
  open: 'bg-critical',
  disconnected: 'bg-critical',
  stopped: 'bg-critical',
  not_configured: 'bg-muted',
}

export function StatusBadge({ status, label, size = 'sm' }: StatusBadgeProps) {
  const colorClass = statusColors[status] || statusColors.not_configured
  const dotColor = dotColors[status] || dotColors.not_configured

  return (
    <span
      className={cn(
        'status-pill',
        colorClass,
        size === 'sm' ? 'text-[11px] px-2 py-0.5' : 'text-xs px-3 py-1'
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full', dotColor)} />
      {label || status.replace('_', ' ')}
    </span>
  )
}
