import { useState } from 'react'
import {
  Layers,
  Plus,
  Trash2,
  Play,
  Square,
  Copy,
  Settings,
  Globe,
  Lock,
  Database,
  Cpu,
  HardDrive,
  Network
} from 'lucide-react'

interface IsolatedEnvironment {
  id: string
  name: string
  status: 'running' | 'stopped' | 'creating' | 'error'
  services: string[]
  network: string
  created: string
  config: {
    postgres: boolean
    redis: boolean
    milvus: boolean
    exposeGateway: boolean
    gatewayPort?: number
  }
}

const DEFAULT_SERVICES = [
  'gateway',
  'auth-service',
  'memory-service',
  'index-service',
  'browser-service',
  'task-service',
  'ai-service'
]

export function IsolatedEnvironments() {
  const [environments, setEnvironments] = useState<IsolatedEnvironment[]>([
    {
      id: 'env-main',
      name: 'Production',
      status: 'running',
      services: DEFAULT_SERVICES,
      network: 'newarch-internal',
      created: '2 hours ago',
      config: {
        postgres: true,
        redis: true,
        milvus: true,
        exposeGateway: true,
        gatewayPort: 8080
      }
    }
  ])

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newEnvName, setNewEnvName] = useState('')
  const [newEnvConfig, setNewEnvConfig] = useState({
    postgres: true,
    redis: true,
    milvus: false,
    exposeGateway: true,
    gatewayPort: 9080,
    services: [...DEFAULT_SERVICES]
  })
  const [loading, setLoading] = useState<string | null>(null)

  const createEnvironment = async () => {
    if (!newEnvName.trim()) return

    setLoading('create')

    // 模拟创建环境
    await new Promise(resolve => setTimeout(resolve, 2000))

    const newEnv: IsolatedEnvironment = {
      id: `env-${Date.now()}`,
      name: newEnvName,
      status: 'running',
      services: newEnvConfig.services,
      network: `newarch-${newEnvName.toLowerCase().replace(/\s+/g, '-')}`,
      created: 'just now',
      config: {
        postgres: newEnvConfig.postgres,
        redis: newEnvConfig.redis,
        milvus: newEnvConfig.milvus,
        exposeGateway: newEnvConfig.exposeGateway,
        gatewayPort: newEnvConfig.gatewayPort
      }
    }

    setEnvironments(prev => [...prev, newEnv])
    setShowCreateModal(false)
    setNewEnvName('')
    setLoading(null)
  }

  const toggleEnvironment = async (envId: string, action: 'start' | 'stop') => {
    setLoading(envId)
    await new Promise(resolve => setTimeout(resolve, 1500))

    setEnvironments(prev => prev.map(env => {
      if (env.id === envId) {
        return {
          ...env,
          status: action === 'start' ? 'running' : 'stopped'
        }
      }
      return env
    }))
    setLoading(null)
  }

  const deleteEnvironment = async (envId: string) => {
    if (envId === 'env-main') {
      alert('不能删除主环境')
      return
    }

    setLoading(envId)
    await new Promise(resolve => setTimeout(resolve, 1000))
    setEnvironments(prev => prev.filter(env => env.id !== envId))
    setLoading(null)
  }

  const cloneEnvironment = (env: IsolatedEnvironment) => {
    setNewEnvName(`${env.name} (Copy)`)
    setNewEnvConfig({
      ...env.config,
      services: [...env.services],
      gatewayPort: (env.config.gatewayPort || 8080) + 1000
    })
    setShowCreateModal(true)
  }

  const generateDockerCompose = (env: IsolatedEnvironment) => {
    const compose = `# Docker Compose for ${env.name}
# Network: ${env.network}
# Generated at: ${new Date().toISOString()}

version: '3.8'

networks:
  ${env.network}:
    driver: bridge
    internal: ${!env.config.exposeGateway}

services:
${env.config.postgres ? `  postgres-${env.id}:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: newarch
    networks:
      - ${env.network}
` : ''}
${env.config.redis ? `  redis-${env.id}:
    image: redis:7-alpine
    networks:
      - ${env.network}
` : ''}
${env.services.map(svc => `  ${svc}-${env.id}:
    image: newarch-${svc}:latest
    networks:
      - ${env.network}
${svc === 'gateway' && env.config.exposeGateway ? `    ports:
      - "${env.config.gatewayPort}:8080"` : ''}`).join('\n')}
`

    navigator.clipboard.writeText(compose)
    alert('Docker Compose 配置已复制到剪贴板')
  }

  return (
    <div className="h-full flex flex-col p-4">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Layers className="w-5 h-5" />
          隔离环境管理
        </h2>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition"
        >
          <Plus className="w-4 h-4" />
          创建新环境
        </button>
      </div>

      {/* 环境说明 */}
      <div className="bg-gray-800 rounded-lg p-4 mb-4">
        <h3 className="font-medium mb-2">什么是隔离环境？</h3>
        <p className="text-sm text-gray-400 mb-3">
          隔离环境允许你创建独立的 Docker 网络和服务实例，用于测试、开发或演示。
          每个环境都有自己的数据库、缓存和服务，互不干扰。
        </p>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-2 text-gray-400">
            <Network className="w-4 h-4 text-blue-400" />
            独立网络隔离
          </div>
          <div className="flex items-center gap-2 text-gray-400">
            <Database className="w-4 h-4 text-green-400" />
            独立数据存储
          </div>
          <div className="flex items-center gap-2 text-gray-400">
            <Lock className="w-4 h-4 text-yellow-400" />
            安全沙箱环境
          </div>
        </div>
      </div>

      {/* 环境列表 */}
      <div className="flex-1 overflow-auto space-y-4">
        {environments.map(env => (
          <div
            key={env.id}
            className="bg-gray-800 rounded-lg p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${
                  env.status === 'running' ? 'bg-green-400' :
                  env.status === 'stopped' ? 'bg-gray-400' :
                  env.status === 'creating' ? 'bg-yellow-400 animate-pulse' :
                  'bg-red-400'
                }`} />
                <div>
                  <h3 className="font-semibold">{env.name}</h3>
                  <div className="text-xs text-gray-500">
                    {env.network} · 创建于 {env.created}
                  </div>
                </div>
                {env.id === 'env-main' && (
                  <span className="px-2 py-0.5 bg-blue-600/20 text-blue-400 rounded text-xs">
                    主环境
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {env.config.exposeGateway && env.config.gatewayPort && (
                  <a
                    href={`http://localhost:${env.config.gatewayPort}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
                  >
                    <Globe className="w-4 h-4" />
                    :{env.config.gatewayPort}
                  </a>
                )}

                {env.status === 'running' ? (
                  <button
                    onClick={() => toggleEnvironment(env.id, 'stop')}
                    disabled={loading === env.id}
                    className="p-2 hover:bg-red-600/20 rounded text-red-400"
                    title="停止"
                  >
                    <Square className="w-4 h-4" />
                  </button>
                ) : (
                  <button
                    onClick={() => toggleEnvironment(env.id, 'start')}
                    disabled={loading === env.id}
                    className="p-2 hover:bg-green-600/20 rounded text-green-400"
                    title="启动"
                  >
                    <Play className="w-4 h-4" />
                  </button>
                )}

                <button
                  onClick={() => cloneEnvironment(env)}
                  className="p-2 hover:bg-gray-700 rounded text-gray-400"
                  title="克隆"
                >
                  <Copy className="w-4 h-4" />
                </button>

                <button
                  onClick={() => generateDockerCompose(env)}
                  className="p-2 hover:bg-gray-700 rounded text-gray-400"
                  title="导出 Docker Compose"
                >
                  <Settings className="w-4 h-4" />
                </button>

                {env.id !== 'env-main' && (
                  <button
                    onClick={() => deleteEnvironment(env.id)}
                    disabled={loading === env.id}
                    className="p-2 hover:bg-red-600/20 rounded text-gray-400 hover:text-red-400"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            {/* 服务和配置 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-2">服务 ({env.services.length})</div>
                <div className="flex flex-wrap gap-1">
                  {env.services.map(svc => (
                    <span
                      key={svc}
                      className="px-2 py-0.5 bg-gray-700 rounded text-xs"
                    >
                      {svc}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-2">基础设施</div>
                <div className="flex gap-2">
                  {env.config.postgres && (
                    <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-600/20 text-blue-400 rounded text-xs">
                      <Database className="w-3 h-3" />
                      PostgreSQL
                    </span>
                  )}
                  {env.config.redis && (
                    <span className="flex items-center gap-1 px-2 py-0.5 bg-red-600/20 text-red-400 rounded text-xs">
                      <Cpu className="w-3 h-3" />
                      Redis
                    </span>
                  )}
                  {env.config.milvus && (
                    <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-600/20 text-purple-400 rounded text-xs">
                      <HardDrive className="w-3 h-3" />
                      Milvus
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 创建环境模态框 */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 w-full max-w-lg">
            <h3 className="text-lg font-semibold mb-4">创建隔离环境</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">环境名称</label>
                <input
                  type="text"
                  value={newEnvName}
                  onChange={e => setNewEnvName(e.target.value)}
                  placeholder="例如: Testing, Staging, Demo"
                  className="w-full px-3 py-2 bg-gray-700 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">基础设施</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={newEnvConfig.postgres}
                      onChange={e => setNewEnvConfig(prev => ({ ...prev, postgres: e.target.checked }))}
                      className="rounded"
                    />
                    <span>PostgreSQL 数据库</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={newEnvConfig.redis}
                      onChange={e => setNewEnvConfig(prev => ({ ...prev, redis: e.target.checked }))}
                      className="rounded"
                    />
                    <span>Redis 缓存</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={newEnvConfig.milvus}
                      onChange={e => setNewEnvConfig(prev => ({ ...prev, milvus: e.target.checked }))}
                      className="rounded"
                    />
                    <span>Milvus 向量数据库</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">服务选择</label>
                <div className="grid grid-cols-2 gap-2">
                  {DEFAULT_SERVICES.map(svc => (
                    <label key={svc} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={newEnvConfig.services.includes(svc)}
                        onChange={e => {
                          if (e.target.checked) {
                            setNewEnvConfig(prev => ({
                              ...prev,
                              services: [...prev.services, svc]
                            }))
                          } else {
                            setNewEnvConfig(prev => ({
                              ...prev,
                              services: prev.services.filter(s => s !== svc)
                            }))
                          }
                        }}
                        className="rounded"
                      />
                      <span className="text-sm">{svc}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2 mb-2">
                  <input
                    type="checkbox"
                    checked={newEnvConfig.exposeGateway}
                    onChange={e => setNewEnvConfig(prev => ({ ...prev, exposeGateway: e.target.checked }))}
                    className="rounded"
                  />
                  <span className="text-sm text-gray-400">暴露 Gateway 端口</span>
                </label>
                {newEnvConfig.exposeGateway && (
                  <input
                    type="number"
                    value={newEnvConfig.gatewayPort}
                    onChange={e => setNewEnvConfig(prev => ({ ...prev, gatewayPort: parseInt(e.target.value) }))}
                    placeholder="端口号"
                    className="w-32 px-3 py-2 bg-gray-700 rounded-lg"
                  />
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg"
              >
                取消
              </button>
              <button
                onClick={createEnvironment}
                disabled={!newEnvName.trim() || loading === 'create'}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
              >
                {loading === 'create' ? '创建中...' : '创建环境'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
