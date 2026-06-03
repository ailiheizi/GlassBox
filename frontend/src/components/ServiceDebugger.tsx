import { useState } from 'react'
import { Send, Trash2, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react'

interface Endpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  path: string
  description: string
  body?: string
  requiresAuth?: boolean
}

interface ServiceConfig {
  name: string
  label: string
  port: number
  color: string
  endpoints: Endpoint[]
}

const SERVICES: ServiceConfig[] = [
  {
    name: 'auth',
    label: 'Auth Service',
    port: 8081,
    color: 'blue',
    endpoints: [
      { method: 'GET', path: '/health', description: '健康检查' },
      { method: 'POST', path: '/register', description: '用户注册', body: '{"username":"test","email":"test@test.com","password":"123456"}' },
      { method: 'POST', path: '/login', description: '用户登录', body: '{"username":"test","password":"123456"}' },
      { method: 'GET', path: '/profile', description: '获取用户信息', requiresAuth: true },
      { method: 'POST', path: '/refresh', description: '刷新Token', requiresAuth: true },
      { method: 'POST', path: '/logout', description: '退出登录', requiresAuth: true },
    ]
  },
  {
    name: 'memory',
    label: 'Memory Service',
    port: 8082,
    color: 'green',
    endpoints: [
      { method: 'GET', path: '/health', description: '健康检查' },
      { method: 'POST', path: '/semantic', description: '保存语义记忆', body: '{"content":"测试内容","content_type":"text"}', requiresAuth: true },
      { method: 'GET', path: '/semantic/search?query=测试&limit=10', description: '搜索语义记忆', requiresAuth: true },
      { method: 'GET', path: '/recent?limit=20', description: '获取最近记忆', requiresAuth: true },
      { method: 'DELETE', path: '/semantic/{id}', description: '删除记忆', requiresAuth: true },
    ]
  },
  {
    name: 'index',
    label: 'Index Service',
    port: 8083,
    color: 'yellow',
    endpoints: [
      { method: 'GET', path: '/health', description: '健康检查' },
      { method: 'GET', path: '/ai', description: '获取AI索引列表', requiresAuth: true },
      { method: 'POST', path: '/ai', description: '创建AI索引', body: '{"url":"https://example.com","title":"示例","description":"描述"}', requiresAuth: true },
      { method: 'GET', path: '/search?query=关键词', description: '搜索索引', requiresAuth: true },
      { method: 'DELETE', path: '/ai/{id}', description: '删除索引', requiresAuth: true },
    ]
  },
  {
    name: 'browser',
    label: 'Browser Service',
    port: 8084,
    color: 'purple',
    endpoints: [
      { method: 'GET', path: '/health', description: '健康检查' },
      { method: 'POST', path: '/chat', description: 'AI对话(带浏览器)', body: '{"message":"帮我搜索最新新闻"}', requiresAuth: true },
      { method: 'GET', path: '/sessions', description: '获取会话列表', requiresAuth: true },
      { method: 'POST', path: '/sessions', description: '创建新会话', body: '{"name":"测试会话"}', requiresAuth: true },
      { method: 'DELETE', path: '/sessions/{id}', description: '删除会话', requiresAuth: true },
    ]
  },
  {
    name: 'task',
    label: 'Task Service',
    port: 8085,
    color: 'orange',
    endpoints: [
      { method: 'GET', path: '/health', description: '健康检查' },
      { method: 'GET', path: '/tasks', description: '获取任务列表', requiresAuth: true },
      { method: 'POST', path: '/tasks', description: '创建任务', body: '{"input":"执行一个测试任务"}', requiresAuth: true },
      { method: 'GET', path: '/tasks/{id}', description: '获取任务详情', requiresAuth: true },
      { method: 'DELETE', path: '/tasks/{id}', description: '取消任务', requiresAuth: true },
    ]
  },
  {
    name: 'ai',
    label: 'AI Service',
    port: 8086,
    color: 'pink',
    endpoints: [
      { method: 'GET', path: '/health', description: '健康检查' },
      { method: 'POST', path: '/chat', description: 'AI对话', body: '{"messages":[{"role":"user","content":"你好"}],"stream":false}' },
      { method: 'POST', path: '/chat/stream', description: 'AI流式对话', body: '{"messages":[{"role":"user","content":"你好"}],"stream":true}' },
      { method: 'POST', path: '/embedding', description: '生成Embedding', body: '{"text":"测试文本"}' },
      { method: 'POST', path: '/tools/call', description: '工具调用', body: '{"tool":"search","params":{"query":"test"}}' },
    ]
  },
  {
    name: 'gateway',
    label: 'Gateway',
    port: 8080,
    color: 'cyan',
    endpoints: [
      { method: 'GET', path: '/health', description: '健康检查' },
      { method: 'GET', path: '/api/v1/auth/profile', description: '通过网关获取用户信息', requiresAuth: true },
      { method: 'POST', path: '/api/v1/auth/login', description: '通过网关登录', body: '{"username":"test","password":"123456"}' },
      { method: 'GET', path: '/api/v1/memory/recent', description: '通过网关获取记忆', requiresAuth: true },
    ]
  },
]

interface RequestLog {
  id: string
  timestamp: Date
  service: string
  method: string
  path: string
  status: number
  latency: number
  request?: string
  response: string
  error?: string
}

export function ServiceDebugger() {
  const [activeService, setActiveService] = useState<string>('auth')
  const [logs, setLogs] = useState<RequestLog[]>([])
  const [loading, setLoading] = useState<string | null>(null)
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set())
  const [customPath, setCustomPath] = useState('')
  const [customMethod, setCustomMethod] = useState<'GET' | 'POST' | 'PUT' | 'DELETE'>('GET')
  const [customBody, setCustomBody] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const token = localStorage.getItem('token')
  const userId = localStorage.getItem('userId')

  const getServiceUrl = (serviceName: string) => {
    if (serviceName === 'gateway') {
      return '/internal/gateway'
    }
    return `/internal/${serviceName}`
  }

  const executeRequest = async (
    service: string,
    method: string,
    path: string,
    body?: string,
    requiresAuth?: boolean
  ) => {
    const requestId = `${service}-${Date.now()}`
    setLoading(requestId)

    const start = Date.now()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (requiresAuth && token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    if (userId) {
      headers['X-User-ID'] = userId
    }

    try {
      const url = `${getServiceUrl(service)}${path}`
      const response = await fetch(url, {
        method,
        headers,
        body: method !== 'GET' && body ? body : undefined,
      })

      const latency = Date.now() - start
      let responseText: string

      const contentType = response.headers.get('content-type')
      if (contentType?.includes('application/json')) {
        const data = await response.json()
        responseText = JSON.stringify(data, null, 2)
      } else {
        responseText = await response.text()
      }

      const log: RequestLog = {
        id: crypto.randomUUID(),
        timestamp: new Date(),
        service,
        method,
        path,
        status: response.status,
        latency,
        request: body,
        response: responseText,
      }

      setLogs(prev => [log, ...prev].slice(0, 100))
      setExpandedLogs(prev => new Set([...prev, log.id]))
    } catch (err) {
      const latency = Date.now() - start
      const log: RequestLog = {
        id: crypto.randomUUID(),
        timestamp: new Date(),
        service,
        method,
        path,
        status: 0,
        latency,
        request: body,
        response: '',
        error: String(err),
      }
      setLogs(prev => [log, ...prev].slice(0, 100))
      setExpandedLogs(prev => new Set([...prev, log.id]))
    } finally {
      setLoading(null)
    }
  }

  const toggleLog = (id: string) => {
    setExpandedLogs(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const getStatusColor = (status: number) => {
    if (status >= 200 && status < 300) return 'text-green-400'
    if (status >= 400 && status < 500) return 'text-yellow-400'
    if (status >= 500 || status === 0) return 'text-red-400'
    return 'text-gray-400'
  }

  const getMethodColor = (method: string) => {
    switch (method) {
      case 'GET': return 'bg-green-600'
      case 'POST': return 'bg-blue-600'
      case 'PUT': return 'bg-yellow-600'
      case 'DELETE': return 'bg-red-600'
      default: return 'bg-gray-600'
    }
  }

  const activeServiceConfig = SERVICES.find(s => s.name === activeService)

  return (
    <div className="h-full flex">
      {/* 服务选择侧边栏 */}
      <div className="w-48 bg-gray-800 border-r border-gray-700 p-2 space-y-1">
        <div className="text-xs text-gray-500 uppercase px-2 py-1">服务列表</div>
        {SERVICES.map(service => (
          <button
            key={service.name}
            onClick={() => setActiveService(service.name)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
              activeService === service.name
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:bg-gray-700 hover:text-white'
            }`}
          >
            <div className="font-medium">{service.label}</div>
            <div className="text-xs opacity-60">:{service.port}</div>
          </button>
        ))}
      </div>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 端点列表 */}
        <div className="p-4 border-b border-gray-700">
          <h3 className="text-lg font-semibold mb-3">{activeServiceConfig?.label} 端点</h3>

          {/* 预设端点 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 mb-4">
            {activeServiceConfig?.endpoints.map((endpoint, idx) => (
              <button
                key={idx}
                onClick={() => executeRequest(
                  activeService,
                  endpoint.method,
                  endpoint.path,
                  endpoint.body,
                  endpoint.requiresAuth
                )}
                disabled={loading !== null}
                className="flex items-center gap-2 p-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-left transition disabled:opacity-50"
              >
                <span className={`px-2 py-0.5 rounded text-xs font-mono ${getMethodColor(endpoint.method)}`}>
                  {endpoint.method}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{endpoint.description}</div>
                  <div className="text-xs text-gray-500 truncate">{endpoint.path}</div>
                </div>
                {endpoint.requiresAuth && (
                  <span className="text-xs text-yellow-500">🔒</span>
                )}
              </button>
            ))}
          </div>

          {/* 自定义请求 */}
          <div className="bg-gray-700 rounded-lg p-3">
            <div className="text-sm text-gray-400 mb-2">自定义请求</div>
            <div className="flex gap-2 mb-2">
              <select
                value={customMethod}
                onChange={e => setCustomMethod(e.target.value as typeof customMethod)}
                className="px-2 py-1 bg-gray-600 rounded text-sm"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
              </select>
              <input
                type="text"
                value={customPath}
                onChange={e => setCustomPath(e.target.value)}
                placeholder="/path"
                className="flex-1 px-3 py-1 bg-gray-600 rounded text-sm"
              />
              <button
                onClick={() => executeRequest(activeService, customMethod, customPath, customBody, true)}
                disabled={loading !== null || !customPath}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm disabled:opacity-50 flex items-center gap-1"
              >
                <Send className="w-4 h-4" />
                发送
              </button>
            </div>
            {customMethod !== 'GET' && (
              <textarea
                value={customBody}
                onChange={e => setCustomBody(e.target.value)}
                placeholder='{"key": "value"}'
                rows={2}
                className="w-full px-3 py-2 bg-gray-600 rounded text-sm font-mono"
              />
            )}
          </div>
        </div>

        {/* 请求日志 */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">请求日志</h3>
            <button
              onClick={() => setLogs([])}
              className="flex items-center gap-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
            >
              <Trash2 className="w-4 h-4" />
              清空
            </button>
          </div>

          {logs.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              点击上方端点发送请求
            </div>
          ) : (
            <div className="space-y-2">
              {logs.map(log => (
                <div key={log.id} className="bg-gray-800 rounded-lg overflow-hidden">
                  <div
                    className="flex items-center gap-2 p-3 cursor-pointer hover:bg-gray-750"
                    onClick={() => toggleLog(log.id)}
                  >
                    {expandedLogs.has(log.id) ? (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                    )}
                    <span className={`px-2 py-0.5 rounded text-xs font-mono ${getMethodColor(log.method)}`}>
                      {log.method}
                    </span>
                    <span className="text-sm text-gray-400">{log.service}</span>
                    <span className="text-sm font-mono flex-1 truncate">{log.path}</span>
                    <span className={`text-sm font-mono ${getStatusColor(log.status)}`}>
                      {log.status || 'ERR'}
                    </span>
                    <span className="text-xs text-gray-500">{log.latency}ms</span>
                    <span className="text-xs text-gray-600">
                      {log.timestamp.toLocaleTimeString()}
                    </span>
                  </div>

                  {expandedLogs.has(log.id) && (
                    <div className="border-t border-gray-700 p-3 space-y-3">
                      {log.request && (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-gray-500">Request Body</span>
                            <button
                              onClick={() => copyToClipboard(log.request!, `req-${log.id}`)}
                              className="text-gray-500 hover:text-white"
                            >
                              {copiedId === `req-${log.id}` ? (
                                <Check className="w-4 h-4 text-green-400" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                            </button>
                          </div>
                          <pre className="text-xs bg-gray-900 p-2 rounded overflow-x-auto">
                            {log.request}
                          </pre>
                        </div>
                      )}
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-gray-500">
                            {log.error ? 'Error' : 'Response'}
                          </span>
                          <button
                            onClick={() => copyToClipboard(log.error || log.response, `res-${log.id}`)}
                            className="text-gray-500 hover:text-white"
                          >
                            {copiedId === `res-${log.id}` ? (
                              <Check className="w-4 h-4 text-green-400" />
                            ) : (
                              <Copy className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                        <pre className={`text-xs p-2 rounded overflow-x-auto max-h-60 ${
                          log.error ? 'bg-red-900/30 text-red-300' : 'bg-gray-900'
                        }`}>
                          {log.error || log.response || '(empty)'}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
