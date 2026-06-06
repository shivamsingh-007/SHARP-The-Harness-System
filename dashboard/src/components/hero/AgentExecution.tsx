import { useDashboardStore } from '../../store/dashboardStore'
import { Card, CardHeader } from '../shared/Card'
import { EmptyState } from '../shared/EmptyState'
import { ReactTimeline } from './ReactTimeline'
import { SessionStrip } from './SessionStrip'
import { Cpu } from 'lucide-react'

export function AgentExecution() {
  const { execution } = useDashboardStore()

  if (!execution) {
    return (
      <Card elevated className="h-full">
        <CardHeader title="Agent Execution" subtitle="ReAct loop status" />
        <EmptyState icon={<Cpu size={32} strokeWidth={1.5} />} title="Waiting for execution" />
      </Card>
    )
  }

  return (
    <Card elevated className="h-full flex flex-col">
      <CardHeader
        title="Agent Execution"
        subtitle={`${execution.strategy.toUpperCase()} strategy`}
        action={
          execution.active ? (
            <span className="status-pill bg-accent/20 text-accent border border-accent/30 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-accent glow-pulse" />
              Active
            </span>
          ) : execution.done ? (
            <span className="status-pill bg-accent/20 text-accent border border-accent/30 text-[11px]">
              Complete
            </span>
          ) : (
            <span className="status-pill bg-muted/20 text-muted border border-muted/30 text-[11px]">
              Idle
            </span>
          )
        }
      />

      <div className="flex-1 min-h-0">
        {execution.steps.length > 0 ? (
          <ReactTimeline steps={execution.steps} active={execution.active} />
        ) : (
          <EmptyState
            icon={<Cpu size={28} strokeWidth={1.5} />}
            title={execution.active ? 'Starting...' : 'No steps yet'}
            description={
              execution.active
                ? 'Agent is initializing the ReAct loop.'
                : 'Run a request to see the execution timeline.'
            }
          />
        )}
      </div>

      <SessionStrip execution={execution} />
    </Card>
  )
}
