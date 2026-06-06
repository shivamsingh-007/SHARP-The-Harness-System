import type { ExecutionCurrent } from '../../types'
import { formatNumber, formatCost } from '../../lib/utils'

interface SessionStripProps {
  execution: ExecutionCurrent
}

export function SessionStrip({ execution }: SessionStripProps) {
  return (
    <div className="border-t border-border px-4 py-2.5 flex items-center gap-4 text-[11px] bg-bg-elevated/50 rounded-b-xl shrink-0">
      <div className="flex items-center gap-1.5">
        <span className="text-muted">Steps:</span>
        <span className="font-mono font-semibold text-text-dim">{execution.total_steps}</span>
      </div>

      <div className="w-px h-3 bg-border" />

      <div className="flex items-center gap-1.5">
        <span className="text-muted">Iteration:</span>
        <span className="font-mono font-semibold text-text-dim">{execution.iteration}</span>
      </div>

      <div className="w-px h-3 bg-border" />

      <div className="flex items-center gap-1.5">
        <span className="text-muted">Tokens:</span>
        <span className="font-mono font-semibold text-text-dim">{formatNumber(execution.total_tokens)}</span>
      </div>

      <div className="w-px h-3 bg-border" />

      <div className="flex items-center gap-1.5">
        <span className="text-muted">Cost:</span>
        <span className="font-mono font-semibold text-text-dim">{formatCost(execution.total_cost)}</span>
      </div>

      {execution.done && execution.final_answer && (
        <>
          <div className="w-px h-3 bg-border" />
          <div className="flex-1 min-w-0">
            <span className="text-muted">Output: </span>
            <span className="text-text-dim truncate">{execution.final_answer.slice(0, 80)}</span>
          </div>
        </>
      )}
    </div>
  )
}
