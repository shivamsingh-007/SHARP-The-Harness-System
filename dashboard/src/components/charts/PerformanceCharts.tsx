import { useDashboardStore } from '../../store/dashboardStore'
import { Card, CardHeader } from '../shared/Card'
import { EmptyState } from '../shared/EmptyState'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'
import { BarChart3 } from 'lucide-react'

export function PerformanceCharts() {
  const { timeseries } = useDashboardStore()

  if (!timeseries || timeseries.points.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader title="Performance" subtitle="Latency & throughput" />
        <EmptyState
          icon={<BarChart3 size={28} strokeWidth={1.5} />}
          title="No metrics yet"
          description="Charts will populate after the first run."
        />
      </Card>
    )
  }

  const data = timeseries.points.map((p) => ({
    name: p.label,
    p50: p.latency_p50,
    p95: p.latency_p95,
    throughput: p.throughput,
    tokens: p.tokens,
  }))

  return (
    <Card className="h-full flex flex-col">
      <CardHeader title="Performance" subtitle="Latency & throughput" />

      <div className="flex-1 space-y-4">
        <div>
          <p className="text-[10px] text-muted uppercase tracking-wide mb-2">Latency (ms)</p>
          <div className="h-[120px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data}>
                <defs>
                  <linearGradient id="p50Grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#059669" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#059669" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="p95Grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f4a261" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#f4a261" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: '#6c7086' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#6c7086' }}
                  axisLine={false}
                  tickLine={false}
                  width={40}
                />
                <Tooltip
                  contentStyle={{
                    background: '#12121a',
                    border: '1px solid #1e1e2e',
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Area type="monotone" dataKey="p50" stroke="#059669" fill="url(#p50Grad)" strokeWidth={2} />
                <Area type="monotone" dataKey="p95" stroke="#f4a261" fill="url(#p95Grad)" strokeWidth={1.5} strokeDasharray="4 4" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-1">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-0.5 bg-accent rounded" />
              <span className="text-[10px] text-muted">p50</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-0.5 bg-warning rounded" style={{ borderTop: '1px dashed' }} />
              <span className="text-[10px] text-muted">p95</span>
            </div>
          </div>
        </div>

        <div>
          <p className="text-[10px] text-muted uppercase tracking-wide mb-2">Throughput (req/min)</p>
          <div className="h-[80px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: '#6c7086' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#6c7086' }}
                  axisLine={false}
                  tickLine={false}
                  width={30}
                />
                <Tooltip
                  contentStyle={{
                    background: '#12121a',
                    border: '1px solid #1e1e2e',
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Bar dataKey="throughput" fill="#059669" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </Card>
  )
}
