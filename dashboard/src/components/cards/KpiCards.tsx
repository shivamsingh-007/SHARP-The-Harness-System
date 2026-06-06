import { useDashboardStore } from '../../store/dashboardStore'
import { Card } from '../shared/Card'
import { formatLatency, formatNumber, formatCost } from '../../lib/utils'
import { Clock, AlertTriangle, Activity, Coins, Cpu } from 'lucide-react'

export function KpiCards() {
  const { metrics, health } = useDashboardStore()

  const avgLatency = metrics?.avg_latency_ms || 0
  const errorRate = metrics?.error_rate || 0
  const totalTraces = metrics?.total_traces || 0
  const totalTokens = metrics?.total_tokens || 0
  const totalCost = metrics?.total_cost || 0
  const healthy = health?.connections_healthy || 0
  const total = health?.connections_total || 0

  const cards = [
    {
      label: 'Status',
      value: health?.status === 'running' ? 'Online' : health?.status === 'degraded' ? 'Degraded' : 'Offline',
      sub: `${healthy}/${total} connections`,
      icon: Cpu,
      color: health?.status === 'running' ? 'text-accent' : health?.status === 'degraded' ? 'text-warning' : 'text-critical',
      bgColor: health?.status === 'running' ? 'bg-accent/10' : health?.status === 'degraded' ? 'bg-warning/10' : 'bg-critical/10',
    },
    {
      label: 'Latency',
      value: formatLatency(avgLatency),
      sub: `avg across ${totalTraces} traces`,
      icon: Clock,
      color: 'text-cyan-400',
      bgColor: 'bg-cyan-400/10',
    },
    {
      label: 'Error Rate',
      value: `${errorRate.toFixed(1)}%`,
      sub: `${metrics?.failed_traces || 0} / ${totalTraces} failed`,
      icon: AlertTriangle,
      color: errorRate > 5 ? 'text-critical' : errorRate > 0 ? 'text-warning' : 'text-accent',
      bgColor: errorRate > 5 ? 'bg-critical/10' : errorRate > 0 ? 'bg-warning/10' : 'bg-accent/10',
    },
    {
      label: 'Requests',
      value: formatNumber(totalTraces),
      sub: 'total traces',
      icon: Activity,
      color: 'text-blue-400',
      bgColor: 'bg-blue-400/10',
    },
    {
      label: 'Cost',
      value: formatCost(totalCost),
      sub: `${formatNumber(totalTokens)} tokens`,
      icon: Coins,
      color: 'text-amber-400',
      bgColor: 'bg-amber-400/10',
    },
  ]

  return (
    <div className="grid grid-cols-5 gap-3">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <Card key={card.label} className="!p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="kpi-label">{card.label}</p>
                <p className="kpi-value mt-1">{card.value}</p>
                <p className="text-[10px] text-muted mt-1">{card.sub}</p>
              </div>
              <div className={`w-8 h-8 rounded-lg ${card.bgColor} flex items-center justify-center`}>
                <Icon size={16} className={card.color} />
              </div>
            </div>
          </Card>
        )
      })}
    </div>
  )
}
