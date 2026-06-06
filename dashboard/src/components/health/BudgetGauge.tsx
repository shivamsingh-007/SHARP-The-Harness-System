import type { BudgetStatus } from '../../types'
import { formatCost, formatNumber } from '../../lib/utils'

interface BudgetGaugeProps {
  budget: BudgetStatus
}

export function BudgetGauge({ budget }: BudgetGaugeProps) {
  const costPct = Math.min(100, budget.cost_usage_pct)
  const tokenPct = Math.min(100, budget.token_usage_pct)

  return (
    <div>
      <p className="kpi-label mb-2">Budget</p>
      <div className="space-y-3">
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-muted">Cost</span>
            <span className="text-[11px] font-mono text-text-dim">
              {formatCost(budget.session_cost)} / {formatCost(budget.cost_limit)}
            </span>
          </div>
          <div className="h-2 bg-bg-card rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                costPct >= 80 ? 'bg-critical' : costPct >= 50 ? 'bg-warning' : 'bg-accent'
              }`}
              style={{ width: `${costPct}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-muted">Tokens</span>
            <span className="text-[11px] font-mono text-text-dim">
              {formatNumber(budget.session_tokens)} / {formatNumber(budget.token_limit)}
            </span>
          </div>
          <div className="h-2 bg-bg-card rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                tokenPct >= 80 ? 'bg-critical' : tokenPct >= 50 ? 'bg-warning' : 'bg-accent'
              }`}
              style={{ width: `${tokenPct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
