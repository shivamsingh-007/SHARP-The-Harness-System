import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useWebSocket } from './hooks/useWebSocket'
import { useMetrics } from './hooks/useMetrics'
import { Header } from './components/layout/Header'
import { StatusBar } from './components/layout/StatusBar'
import { AgentExecution } from './components/hero/AgentExecution'
import { ConnectionStatus } from './components/connections/ConnectionStatus'
import { SystemHealth } from './components/health/SystemHealth'
import { PerformanceCharts } from './components/charts/PerformanceCharts'
import { MCPServerSettings } from './components/mcp/MCPServerSettings'
import { PluginManager } from './components/plugins/PluginManager'
import { useDashboardStore } from './store/dashboardStore'
import { KpiCards } from './components/cards/KpiCards'

const queryClient = new QueryClient()

function OverviewTab() {
  return (
    <div className="flex-1 overflow-auto p-4 space-y-4">
      <KpiCards />
      <div className="grid grid-cols-12 gap-4" style={{ minHeight: 'calc(100vh - 280px)' }}>
        <div className="col-span-3">
          <ConnectionStatus />
        </div>
        <div className="col-span-6 flex flex-col gap-4">
          <div className="flex-1">
            <AgentExecution />
          </div>
        </div>
        <div className="col-span-3 flex flex-col gap-4">
          <SystemHealth />
          <PerformanceCharts />
        </div>
      </div>
    </div>
  )
}

function MCPTab() {
  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="grid grid-cols-2 gap-4" style={{ minHeight: 'calc(100vh - 200px)' }}>
        <MCPServerSettings />
        <PluginManager />
      </div>
    </div>
  )
}

function PluginsTab() {
  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="max-w-3xl mx-auto" style={{ minHeight: 'calc(100vh - 200px)' }}>
        <PluginManager />
      </div>
    </div>
  )
}

function PlaceholderTab({ name }: { name: string }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        <p className="text-lg font-semibold text-text-dim mb-2">{name}</p>
        <p className="text-sm text-muted">Coming soon</p>
      </div>
    </div>
  )
}

function DashboardContent() {
  useWebSocket()
  useMetrics()
  const { activeTab } = useDashboardStore()

  switch (activeTab) {
    case 'overview':
      return <OverviewTab />
    case 'mcp':
      return <MCPTab />
    case 'plugins':
      return <PluginsTab />
    case 'sessions':
      return <PlaceholderTab name="Sessions" />
    case 'config':
      return <PlaceholderTab name="Config" />
    case 'logs':
      return <PlaceholderTab name="Logs" />
    default:
      return <OverviewTab />
  }
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="h-screen flex flex-col bg-bg circuit-bg">
        <Header />
        <DashboardContent />
        <StatusBar />
      </div>
    </QueryClientProvider>
  )
}
