import { useDashboardStore } from '../../store/dashboardStore'
import { Card, CardHeader } from '../shared/Card'
import { ConnectionItem } from './ConnectionItem'
import { EmptyState } from '../shared/EmptyState'
import { Plug } from 'lucide-react'

export function ConnectionStatus() {
  const { connections } = useDashboardStore()

  if (!connections || connections.connections.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader title="Connections" subtitle="External dependencies" />
        <EmptyState icon={<Plug size={28} strokeWidth={1.5} />} title="Loading connections..." />
      </Card>
    )
  }

  const healthy = connections.connections.filter((c) => c.status === 'connected').length
  const total = connections.connections.length

  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="Connections"
        subtitle={`${healthy}/${total} connected`}
        action={
          <span className="text-[10px] font-mono text-muted">
            {healthy === total ? 'All healthy' : `${total - healthy} issues`}
          </span>
        }
      />

      <div className="flex-1 space-y-3 overflow-y-auto">
        {connections.connections.map((conn) => (
          <ConnectionItem key={conn.id} connection={conn} />
        ))}
      </div>
    </Card>
  )
}
