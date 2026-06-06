import { useState, useEffect } from 'react'
import { api } from '../../api/client'
import { Card, CardHeader } from '../shared/Card'
import { StatusBadge } from '../shared/StatusBadge'
import { EmptyState } from '../shared/EmptyState'
import type { MCPServerItem } from '../../types'
import {
  Plug,
  Plus,
  Trash2,
  Play,
  Square,
  Terminal,
  Globe,
  ChevronDown,
  ChevronRight,
  Loader2,
} from 'lucide-react'

export function MCPServerSettings() {
  const [servers, setServers] = useState<MCPServerItem[]>([])
  const [connected, setConnected] = useState<string[]>([])
  const [tools, setTools] = useState<string[]>([])
  const [resources, setResources] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(true)

  const [newServer, setNewServer] = useState({
    name: '',
    transport: 'stdio' as 'stdio' | 'http',
    command: '',
    args: '',
    url: '',
    description: '',
  })

  const loadServers = async () => {
    try {
      const data = await api.mcpServers()
      setServers(data.servers)
      setConnected(data.connected)
      setTools(data.tools)
      setResources(data.resources)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadServers()
    const interval = setInterval(loadServers, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleConnect = async (name: string) => {
    setActionLoading(name)
    try {
      await api.mcpConnect(name)
      await loadServers()
    } catch {
      // ignore
    } finally {
      setActionLoading(null)
    }
  }

  const handleDisconnect = async (name: string) => {
    setActionLoading(name)
    try {
      await api.mcpDisconnect(name)
      await loadServers()
    } catch {
      // ignore
    } finally {
      setActionLoading(null)
    }
  }

  const handleRemove = async (name: string) => {
    setActionLoading(name)
    try {
      await api.mcpRemoveServer(name)
      await loadServers()
    } catch {
      // ignore
    } finally {
      setActionLoading(null)
    }
  }

  const handleAdd = async () => {
    if (!newServer.name) return
    setActionLoading('add')
    try {
      await api.mcpAddServer({
        name: newServer.name,
        transport: newServer.transport,
        command: newServer.transport === 'stdio' ? newServer.command : undefined,
        args: newServer.transport === 'stdio' ? newServer.args.split(' ').filter(Boolean) : [],
        url: newServer.transport === 'http' ? newServer.url : undefined,
        description: newServer.description,
      })
      setNewServer({ name: '', transport: 'stdio', command: '', args: '', url: '', description: '' })
      setShowAdd(false)
      await loadServers()
    } catch {
      // ignore
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) {
    return (
      <Card className="h-full">
        <CardHeader title="MCP Servers" subtitle="Model Context Protocol" />
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="text-muted animate-spin" />
        </div>
      </Card>
    )
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="MCP Servers"
        subtitle={`${connected.length} connected · ${tools.length} tools · ${resources.length} resources`}
        action={
          <button
            onClick={() => setShowAdd(!showAdd)}
            className="flex items-center gap-1.5 text-[11px] font-medium text-accent hover:text-accent/80 transition-colors"
          >
            <Plus size={14} />
            Add Server
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto space-y-3">
        {showAdd && (
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <input
                placeholder="Server name"
                value={newServer.name}
                onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                className="bg-bg border border-border rounded-md px-2.5 py-1.5 text-xs text-text placeholder:text-muted focus:outline-none focus:border-accent"
              />
              <select
                value={newServer.transport}
                onChange={(e) => setNewServer({ ...newServer, transport: e.target.value as 'stdio' | 'http' })}
                className="bg-bg border border-border rounded-md px-2.5 py-1.5 text-xs text-text focus:outline-none focus:border-accent"
              >
                <option value="stdio">stdio</option>
                <option value="http">HTTP/SSE</option>
              </select>
            </div>

            {newServer.transport === 'stdio' ? (
              <div className="grid grid-cols-2 gap-2">
                <input
                  placeholder="Command (e.g., npx)"
                  value={newServer.command}
                  onChange={(e) => setNewServer({ ...newServer, command: e.target.value })}
                  className="bg-bg border border-border rounded-md px-2.5 py-1.5 text-xs text-text placeholder:text-muted focus:outline-none focus:border-accent"
                />
                <input
                  placeholder="Args (space-separated)"
                  value={newServer.args}
                  onChange={(e) => setNewServer({ ...newServer, args: e.target.value })}
                  className="bg-bg border border-border rounded-md px-2.5 py-1.5 text-xs text-text placeholder:text-muted focus:outline-none focus:border-accent"
                />
              </div>
            ) : (
              <input
                placeholder="URL (e.g., http://localhost:8000/mcp)"
                value={newServer.url}
                onChange={(e) => setNewServer({ ...newServer, url: e.target.value })}
                className="w-full bg-bg border border-border rounded-md px-2.5 py-1.5 text-xs text-text placeholder:text-muted focus:outline-none focus:border-accent"
              />
            )}

            <input
              placeholder="Description (optional)"
              value={newServer.description}
              onChange={(e) => setNewServer({ ...newServer, description: e.target.value })}
              className="w-full bg-bg border border-border rounded-md px-2.5 py-1.5 text-xs text-text placeholder:text-muted focus:outline-none focus:border-accent"
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAdd(false)}
                className="px-3 py-1.5 text-[11px] font-medium text-muted hover:text-text rounded-md border border-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                disabled={!newServer.name || actionLoading === 'add'}
                className="px-3 py-1.5 text-[11px] font-medium text-bg bg-accent hover:bg-accent/90 rounded-md transition-colors disabled:opacity-50"
              >
                {actionLoading === 'add' ? 'Adding...' : 'Add Server'}
              </button>
            </div>
          </div>
        )}

        {servers.length === 0 ? (
          <EmptyState
            icon={<Plug size={28} strokeWidth={1.5} />}
            title="No MCP servers"
            description="Add a server to connect to external tools and resources."
          />
        ) : (
          servers.map((server) => (
            <div
              key={server.name}
              className="rounded-lg border border-border bg-bg-elevated/50 overflow-hidden"
            >
              <div className="flex items-center gap-3 px-3 py-2.5">
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="text-muted"
                >
                  {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>

                <div className="w-7 h-7 rounded-md bg-bg-card flex items-center justify-center">
                  {server.transport === 'stdio' ? (
                    <Terminal size={14} className="text-cyan-400" />
                  ) : (
                    <Globe size={14} className="text-amber-400" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-text-dim">{server.name}</p>
                  <p className="text-[10px] text-muted truncate">{server.description || server.transport}</p>
                </div>

                <StatusBadge
                  status={server.connected ? 'connected' : 'not_configured'}
                  label={server.connected ? 'Connected' : 'Disconnected'}
                />

                <div className="flex items-center gap-1">
                  {server.connected ? (
                    <button
                      onClick={() => handleDisconnect(server.name)}
                      disabled={actionLoading === server.name}
                      className="p-1.5 rounded-md hover:bg-bg-card text-warning transition-colors"
                      title="Disconnect"
                    >
                      {actionLoading === server.name ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Square size={14} />
                      )}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConnect(server.name)}
                      disabled={actionLoading === server.name}
                      className="p-1.5 rounded-md hover:bg-bg-card text-accent transition-colors"
                      title="Connect"
                    >
                      {actionLoading === server.name ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Play size={14} />
                      )}
                    </button>
                  )}
                  <button
                    onClick={() => handleRemove(server.name)}
                    disabled={actionLoading === server.name}
                    className="p-1.5 rounded-md hover:bg-bg-card text-critical transition-colors"
                    title="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {expanded && (
                <div className="px-3 pb-2.5 pt-0 space-y-1.5">
                  {server.transport === 'stdio' && server.command && (
                    <div className="text-[10px] font-mono text-muted bg-bg-card rounded px-2 py-1">
                      {server.command} {(server.args || []).join(' ')}
                    </div>
                  )}
                  {server.transport === 'http' && server.url && (
                    <div className="text-[10px] font-mono text-muted bg-bg-card rounded px-2 py-1">
                      {server.url}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </Card>
  )
}
