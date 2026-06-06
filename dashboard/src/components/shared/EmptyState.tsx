import { cn } from '../../lib/utils'
import { AlertCircle } from 'lucide-react'

interface EmptyStateProps {
  icon?: React.ReactNode
  title?: string
  description?: string
  className?: string
}

export function EmptyState({
  icon,
  title = 'No data yet',
  description = 'Data will appear here once the engine starts.',
  className,
}: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-8 text-center', className)}>
      <div className="text-muted mb-3">
        {icon || <AlertCircle size={32} strokeWidth={1.5} />}
      </div>
      <p className="text-sm text-text-dim">{title}</p>
      <p className="text-xs text-muted mt-1">{description}</p>
    </div>
  )
}
