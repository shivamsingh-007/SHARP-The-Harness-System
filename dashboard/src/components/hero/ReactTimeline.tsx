import { cn } from '../../lib/utils'
import type { ExecutionStep } from '../../types'
import { Brain, Zap, Eye } from 'lucide-react'

interface ReactTimelineProps {
  steps: ExecutionStep[]
  active: boolean
}

const stepConfig: Record<string, { icon: typeof Brain; color: string; bgColor: string; label: string }> = {
  thought: { icon: Brain, color: 'text-cyan-400', bgColor: 'bg-cyan-400/20 border-cyan-400/40', label: 'Think' },
  action: { icon: Zap, color: 'text-amber-400', bgColor: 'bg-amber-400/20 border-amber-400/40', label: 'Act' },
  observation: { icon: Eye, color: 'text-emerald-400', bgColor: 'bg-emerald-400/20 border-emerald-400/40', label: 'Observe' },
}

export function ReactTimeline({ steps, active }: ReactTimelineProps) {
  const lastStepIdx = steps.length - 1

  return (
    <div className="relative pl-8 py-2 overflow-y-auto max-h-[340px]">
      <div className="absolute left-[15px] top-4 bottom-4 w-[2px] bg-border" />

      {steps.map((step, i) => {
        const config = stepConfig[step.step_type] || stepConfig.thought
        const Icon = config.icon
        const isLast = i === lastStepIdx
        const isCurrent = isLast && active

        return (
          <div key={i} className="relative mb-4 last:mb-0 group">
            <div
              className={cn(
                'absolute -left-8 w-[30px] h-[30px] rounded-full border-2 flex items-center justify-center z-10 transition-all',
                config.bgColor,
                isCurrent && 'glow-pulse',
                isLast && !active && step.step_type === 'observation' && 'bg-accent/30 border-accent/50'
              )}
            >
              <Icon size={14} className={config.color} />
            </div>

            <div
              className={cn(
                'rounded-lg border p-3 transition-all',
                isCurrent
                  ? 'bg-bg-elevated border-accent/30'
                  : 'bg-bg-card border-border hover:border-border/80'
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={cn('text-[11px] font-semibold uppercase tracking-wide', config.color)}>
                  {config.label}
                </span>
                <span className="text-[10px] text-muted font-mono">Step {step.iteration}</span>
                {step.duration_ms > 0 && (
                  <span className="text-[10px] text-muted font-mono ml-auto">
                    {step.duration_ms.toFixed(0)}ms
                  </span>
                )}
              </div>

              <p className="text-xs text-text-dim leading-relaxed line-clamp-3">
                {step.content}
              </p>

              {step.tool_name && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[10px] bg-amber-400/10 text-amber-400 px-1.5 py-0.5 rounded font-mono">
                    {step.tool_name}
                  </span>
                  {step.tool_args && (
                    <span className="text-[10px] text-muted font-mono truncate max-w-[200px]">
                      {JSON.stringify(step.tool_args)}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}

      {active && (
        <div className="relative mb-4 last:mb-0">
          <div className="absolute -left-8 w-[30px] h-[30px] rounded-full border-2 border-dashed border-muted/40 flex items-center justify-center z-10">
            <div className="w-2 h-2 rounded-full bg-muted/40 glow-pulse" />
          </div>
          <div className="rounded-lg border border-dashed border-muted/20 p-3">
            <p className="text-[11px] text-muted italic">Waiting for next step...</p>
          </div>
        </div>
      )}
    </div>
  )
}
