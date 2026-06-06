import { useState, useEffect } from 'react'
import { api } from '../../api/client'
import { Card, CardHeader } from '../shared/Card'
import { StatusBadge } from '../shared/StatusBadge'
import { EmptyState } from '../shared/EmptyState'
import type { PluginItem } from '../../types'
import { Puzzle, Package, Loader2 } from 'lucide-react'

export function PluginManager() {
  const [builtin, setBuiltin] = useState<PluginItem[]>([])
  const [mcpPlugins, setMcpPlugins] = useState<PluginItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.plugins()
        setBuiltin(data.builtin)
        setMcpPlugins(data.mcp)
        setTotal(data.total)
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [])

  const riskColors: Record<string, string> = {
    read: 'text-accent bg-accent/10',
    write: 'text-amber-400 bg-amber-400/10',
    execute: 'text-orange-400 bg-orange-400/10',
    critical: 'text-critical bg-critical/10',
  }

  if (loading) {
    return (
      <Card className="h-full">
        <CardHeader title="Plugins" subtitle="Tools & extensions" />
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="text-muted animate-spin" />
        </div>
      </Card>
    )
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="Plugins"
        subtitle={`${total} tools registered · ${builtin.length} built-in · ${mcpPlugins.length} MCP`}
      />

      <div className="flex-1 overflow-y-auto space-y-4">
        {total === 0 ? (
          <EmptyState
            icon={<Puzzle size={28} strokeWidth={1.5} />}
            title="No plugins"
            description="Register tools or connect MCP servers to add capabilities."
          />
        ) : (
          <>
            {builtin.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Package size={14} className="text-accent" />
                  <p className="kpi-label">Built-in Tools</p>
                </div>
                <div className="space-y-1.5">
                  {builtin.map((plugin) => (
                    <div
                      key={plugin.name}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg border border-border bg-bg-elevated/50"
                    >
                      <div className="w-6 h-6 rounded bg-accent/10 flex items-center justify-center">
                        <Puzzle size={12} className="text-accent" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-text-dim">{plugin.name}</p>
                        <p className="text-[10px] text-muted truncate">{plugin.description}</p>
                      </div>
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${riskColors[plugin.risk_level] || riskColors.read}`}>
                        {plugin.risk_level}
                      </span>
                      <StatusBadge status="connected" label="Active" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {mcpPlugins.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Package size={14} className="text-cyan-400" />
                  <p className="kpi-label">MCP Tools</p>
                </div>
                <div className="space-y-1.5">
                  {mcpPlugins.map((plugin) => (
                    <div
                      key={plugin.name}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg border border-border bg-bg-elevated/50"
                    >
                      <div className="w-6 h-6 rounded bg-cyan-400/10 flex items-center justify-center">
                        <Puzzle size={12} className="text-cyan-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-text-dim">{plugin.name}</p>
                        <p className="text-[10px] text-muted truncate">{plugin.description}</p>
                      </div>
                      <span className="text-[10px] text-muted font-mono">{plugin.server}</span>
                      <StatusBadge status="connected" label="MCP" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  )
}
