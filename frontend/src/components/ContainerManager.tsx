import { useState, useEffect } from 'react'
import {
  Box,
  Play,
  Square,
  RefreshCw,
  Trash2,
  Terminal,
  HardDrive,
  Cpu,
  Clock,
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-react'
import { SandboxPanel } from './SandboxPanel'

interface Container {
  id: string
  name: string
  image: string
  status: 'running' | 'stopped' | 'restarting' | 'error'
  ports: string[]
  created: string
  health?: 'healthy' | 'unhealthy' | 'starting'
  cpu?: string
  memory?: string
  network?: string
}

interface ContainerLog {
  timestamp: string
  message: string
  level: 'info' | 'warn' | 'error'
}

// API 基础路径
const API_BASE = '/internal/gateway/api/v1/admin/containers'

export function ContainerManager() {
  const [activeTab, setActiveTab] = useState<'containers' | 'sandboxes'>('containers')
  const [containers, setContainers] = useState<Container[]>([])
  const [selectedContainer, setSelectedContainer] = useState<string | null>(null)
  const [logs, setLogs] = useState<ContainerLog[]>([])
  const [loading, setLoading] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'running' | 'stopped'>('all')
  const [autoRefresh, setAutoRefresh] = useState(false)

  // 获取容器列表
  const fetchContainers = async () => {
    try {
      const response = await fetch(API_BASE)
      if (response.ok) {
        const data = await response.json()
        // 转换后端数据格式
        const mapped: Container[] = data.map((c: Record<string, unknown>) => ({
          id: c.id as string,
          name: c.name as string,
          image: c.image as string,
          status: c.state === 'running' ? 'running' : 'stopped',
          ports: (c.ports as string[]) || [],
          created: new Date((c.created as number) * 1000).toLocaleString(),
          health: c.health as Container['health'],
          network: c.network as string,
        }))
        setContainers(mapped)
      }
    } catch {
      // Silently fail - UI will show empty state
    }
  }

  // 获取容器日志
  const fetchLogs = async (containerId: string) => {
    setLoading('logs')
    try {
      const response = await fetch(`${API_BASE}/${containerId}/logs?tail=100`)
      if (response.ok) {
        const data = await response.json()
        setLogs(data.logs || [])
      }
    } catch {
      // Silently fail - UI will show empty state
    } finally {
      setLoading(null)
    }
  }

  // 获取容器资源统计
  const fetchStats = async (containerId: string) => {
    try {
      const response = await fetch(`${API_BASE}/${containerId}/stats`)
      if (response.ok) {
        const data = await response.json()
        // 更新容器的 CPU 和内存信息
        setContainers(prev => prev.map(c =>
          c.id === containerId ? { ...c, cpu: data.cpu, memory: data.memory } : c
        ))
      }
    } catch {
      // Silently fail - stats are optional
    }
  }

  // 容器操作
  const containerAction = async (containerId: string, action: 'start' | 'stop' | 'restart' | 'remove') => {
    setLoading(containerId)
    try {
      const response = await fetch(`${API_BASE}/${containerId}/${action}`, {
        method: action === 'remove' ? 'DELETE' : 'POST',
      })

      if (response.ok) {
        // 刷新容器列表
        await fetchContainers()
      } else {
        const error = await response.json()
        alert(`操作失败: ${error.error || '未知错误'}`)
      }
    } catch (err) {
      alert(`操作失败: ${err instanceof Error ? err.message : '未知错误'}`)
    } finally {
      setLoading(null)
    }
  }

  // 刷新容器状态
  const refreshContainers = async () => {
    setLoading('refresh')
    await fetchContainers()
    setLoading(null)
  }

  // 初始加载
  useEffect(() => {
    fetchContainers()
  }, [])

  useEffect(() => {
    if (selectedContainer) {
      fetchLogs(selectedContainer)
      fetchStats(selectedContainer)
    }
  }, [selectedContainer])

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        refreshContainers()
        if (selectedContainer) {
          fetchStats(selectedContainer)
        }
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh, selectedContainer])

  const filteredContainers = containers.filter(c => {
    if (filter === 'running') return c.status === 'running'
    if (filter === 'stopped') return c.status === 'stopped'
    return true
  })

  const getStatusIcon = (status: Container['status']) => {
    switch (status) {
      case 'running':
        return <CheckCircle className="w-4 h-4 text-green-400" />
      case 'stopped':
        return <XCircle className="w-4 h-4 text-gray-400" />
      case 'restarting':
        return <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />
    }
  }

  const getHealthBadge = (health?: Container['health']) => {
    if (!health) return null
    const colors = {
      healthy: 'bg-green-500/20 text-green-400',
      unhealthy: 'bg-red-500/20 text-red-400',
      starting: 'bg-yellow-500/20 text-yellow-400',
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs ${colors[health]}`}>
        {health}
      </span>
    )
  }

  return (
    <div className="h-full flex flex-col p-4">
      {/* Tab 切换 */}
      <div className="flex border-b border-gray-700 mb-4">
        <button
          onClick={() => setActiveTab('containers')}
          className={`px-4 py-2 ${
            activeTab === 'containers'
              ? 'border-b-2 border-blue-500 text-blue-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          Docker 容器
        </button>
        <button
          onClick={() => setActiveTab('sandboxes')}
          className={`px-4 py-2 ${
            activeTab === 'sandboxes'
              ? 'border-b-2 border-blue-500 text-blue-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          用户沙盒
        </button>
      </div>

      {activeTab === 'sandboxes' ? (
        <SandboxPanel />
      ) : (
        <>
          {/* 头部工具栏 */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Box className="w-5 h-5" />
                容器管理
              </h2>
          <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
            {(['all', 'running', 'stopped'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded text-sm transition ${
                  filter === f ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {f === 'all' ? '全部' : f === 'running' ? '运行中' : '已停止'}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            自动刷新
          </label>
          <button
            onClick={refreshContainers}
            disabled={loading === 'refresh'}
            className="flex items-center gap-1 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading === 'refresh' ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      {/* 容器列表 */}
      <div className="flex-1 overflow-auto">
        <div className="grid gap-3">
          {filteredContainers.map(container => (
            <div
              key={container.id}
              className={`bg-gray-800 rounded-lg p-4 cursor-pointer transition ${
                selectedContainer === container.id ? 'ring-2 ring-blue-500' : 'hover:bg-gray-750'
              }`}
              onClick={() => setSelectedContainer(container.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {getStatusIcon(container.status)}
                  <div>
                    <div className="font-medium">{container.name}</div>
                    <div className="text-xs text-gray-500">{container.image}</div>
                  </div>
                  {getHealthBadge(container.health)}
                </div>

                <div className="flex items-center gap-4">
                  {/* 资源使用 */}
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    {container.cpu && (
                      <span className="flex items-center gap-1">
                        <Cpu className="w-3 h-3" />
                        {container.cpu}
                      </span>
                    )}
                    {container.memory && (
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-3 h-3" />
                        {container.memory}
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {container.created}
                    </span>
                  </div>

                  {/* 端口 */}
                  {container.ports.length > 0 && (
                    <div className="flex gap-1">
                      {container.ports.map(port => (
                        <span key={port} className="px-2 py-0.5 bg-gray-700 rounded text-xs font-mono">
                          {port}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* 操作按钮 */}
                  <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                    {container.status === 'stopped' ? (
                      <button
                        onClick={() => containerAction(container.id, 'start')}
                        disabled={loading === container.id}
                        className="p-1 hover:bg-green-600/20 rounded text-green-400"
                        title="启动"
                      >
                        <Play className="w-4 h-4" />
                      </button>
                    ) : (
                      <button
                        onClick={() => containerAction(container.id, 'stop')}
                        disabled={loading === container.id}
                        className="p-1 hover:bg-red-600/20 rounded text-red-400"
                        title="停止"
                      >
                        <Square className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => containerAction(container.id, 'restart')}
                      disabled={loading === container.id}
                      className="p-1 hover:bg-yellow-600/20 rounded text-yellow-400"
                      title="重启"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => containerAction(container.id, 'remove')}
                      disabled={loading === container.id}
                      className="p-1 hover:bg-red-600/20 rounded text-gray-400 hover:text-red-400"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* 网络信息 */}
              {container.network && (
                <div className="mt-2 text-xs text-gray-500">
                  网络: {container.network}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 容器日志面板 */}
      {selectedContainer && (
        <div className="mt-4 bg-gray-800 rounded-lg p-4 max-h-64 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Terminal className="w-4 h-4" />
              容器日志 - {containers.find(c => c.id === selectedContainer)?.name}
            </h3>
            <button
              onClick={() => setSelectedContainer(null)}
              className="text-gray-500 hover:text-white"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-y-auto bg-gray-900 rounded p-2 font-mono text-xs">
            {loading === 'logs' ? (
              <div className="text-gray-500">加载中...</div>
            ) : logs.length === 0 ? (
              <div className="text-gray-500">暂无日志</div>
            ) : (
              logs.map((log, idx) => (
                <div key={idx} className={`${
                  log.level === 'error' ? 'text-red-400' :
                  log.level === 'warn' ? 'text-yellow-400' : 'text-gray-300'
                }`}>
                  <span className="text-gray-600">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  {' '}{log.message}
                </div>
              ))
            )}
          </div>
        </div>
      )}
        </>
      )}
    </div>
  )
}
