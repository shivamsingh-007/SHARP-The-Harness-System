import { useDashboardStore } from '../../store/dashboardStore'
import { Card, CardHeader } from '../shared/Card'
import { CircuitBreaker } from './CircuitBreaker'
import { BudgetGauge } from './BudgetGauge'
import { EmptyState } from '../shared/EmptyState'
import { Shield } from 'lucide-react'

export function SystemHealth() {
  const { safety } = useDashboardStore()

  if (!safety) {
    return (
      <Card className="h-full">
        <CardHeader title="System Health" subtitle="Safety & budget" />
        <EmptyState icon={<Shield size={28} strokeWidth={1.5} />} title="Loading health..." />
      </Card>
    )
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader title="System Health" subtitle="Safety & budget" />

      <div className="flex-1 space-y-4">
        <CircuitBreaker status={safety.circuit_breaker} />
        <BudgetGauge budget={safety.budget} />

        {safety.recent_errors.length > 0 && (
          <div>
            <p className="kpi-label mb-2">Recent Errors</p>
            <div className="space-y-1.5">
              {safety.recent_errors.slice(0, 3).map((err, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-[11px] bg-critical/5 border border-critical/20 rounded-md px-2.5 py-2"
                >
                  <span className="text-critical shrink-0 mt-0.5">●</span>
                  <span className="text-text-dim line-clamp-2">{err.error}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
