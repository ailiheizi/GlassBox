import { useState } from 'react'
import { useStore } from '../store'
import { fetchInternal } from '../api/client'
import { Terminal, Send, Trash2 } from 'lucide-react'

type ServiceName = 'gateway' | 'auth' | 'memory' | 'index' | 'browser' | 'task' | 'ai'

const SERVICES: { name: ServiceName; label: string; port: number }[] = [
  { name: 'gateway', label: 'Gateway', port: 8080 },
  { name: 'auth', label: 'Auth Service', port: 8081 },
  { name: 'memory', label: 'Memory Service', port: 8082 },
  { name: 'index', label: 'Index Service', port: 8083 },
  { name: 'browser', label: 'Browser Service', port: 8084 },
  { name: 'task', label: 'Task Service', port: 8085 },
  { name: 'ai', label: 'AI Service', port: 8086 },
]

interface TestResult {
  id: string
  service: string
  method: string
  path: string
  status: number
  latency: number
  response: unknown
  error?: string
  timestamp: Date
}

export function ApiTester() {
  const { user } = useStore()
  const [service, setService] = useState<ServiceName>('gateway')
  const [method, setMethod] = useState<string>('GET')
  const [path, setPath] = useState<string>('/health')
  const [body, setBody] = useState<string>('')
  const [results, setResults] = useState<TestResult[]>([])
  const [loading, setLoading] = useState(false)

  const handleTest = async () => {
    setLoading(true)
    try {
      const headers: Record<string, string> = {}
      if (user?.token) {
        headers['Authorization'] = `Bearer ${user.token}`
      }
      if (user?.id) {
        headers['X-User-ID'] = user.id
      }

      const result = await fetchInternal(
        service,
        path,
        {
          method,
          headers,
          body: method !== 'GET' && body ? body : undefined,
        }
      )

      const testResult: TestResult = {
        id: crypto.randomUUID(),
        service,
        method,
        path,
        status: result.status,
        latency: result.latency,
        response: result.data || result.error,
        error: result.error,
        timestamp: new Date(),
      }

      setResults((prev) => [testResult, ...prev].slice(0, 50))
    } catch (err) {
      const testResult: TestResult = {
        id: crypto.randomUUID(),
        service,
        method,
        path,
        status: 0,
        latency: 0,
        response: null,
        error: String(err),
        timestamp: new Date(),
      }
      setResults((prev) => [testResult, ...prev].slice(0, 50))
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: number) => {
    if (status >= 200 && status < 300) return 'text-green-400'
    if (status >= 400 && status < 500) return 'text-yellow-400'
    if (status >= 500) return 'text-red-400'
    return 'text-gray-400'
  }

  return (
    <div className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Terminal className="w-5 h-5" />
        <h2 className="text-lg font-semibold">API 测试器</h2>
      </div>

      {/* 请求表单 */}
      <div className="bg-gray-800 rounded-lg p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
          <select
            value={service}
            onChange={(e) => setService(e.target.value as ServiceName)}
            className="px-3 py-2 bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {SERVICES.map((s) => (
              <option key={s.name} value={s.name}>
                {s.label} (:{s.port})
              </option>
            ))}
          </select>

          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="px-3 py-2 bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
          </select>

          <input
            type="text"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/health"
            className="px-3 py-2 bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 md:col-span-2"
          />
        </div>

        {method !== 'GET' && (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder='{"key": "value"}'
            rows={3}
            className="w-full px-3 py-2 bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3 font-mono text-sm"
          />
        )}

        <div className="flex gap-2">
          <button
            onClick={handleTest}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition"
          >
            <Send className="w-4 h-4" />
            {loading ? '发送中...' : '发送请求'}
          </button>
          <button
            onClick={() => setResults([])}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition"
          >
            <Trash2 className="w-4 h-4" />
            清空结果
          </button>
        </div>
      </div>

      {/* 快捷测试按钮 */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => { setService('gateway'); setMethod('GET'); setPath('/health'); }}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          Gateway Health
        </button>
        <button
          onClick={() => { setService('auth'); setMethod('POST'); setPath('/register'); setBody('{"username":"test","email":"test@test.com","password":"123456"}'); }}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          注册用户
        </button>
        <button
          onClick={() => { setService('auth'); setMethod('POST'); setPath('/login'); setBody('{"username":"test","password":"123456"}'); }}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          登录
        </button>
        <button
          onClick={() => { setService('memory'); setMethod('GET'); setPath('/health'); }}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          Memory Health
        </button>
        <button
          onClick={() => { setService('ai'); setMethod('GET'); setPath('/health'); }}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          AI Health
        </button>
      </div>

      {/* 结果列表 */}
      <div className="space-y-2">
        {results.map((result) => (
          <div key={result.id} className="bg-gray-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-gray-700 rounded text-xs font-mono">
                  {result.method}
                </span>
                <span className="text-sm text-gray-400">{result.service}</span>
                <span className="text-sm font-mono">{result.path}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className={getStatusColor(result.status)}>
                  {result.status || 'ERR'}
                </span>
                <span className="text-gray-400">{result.latency}ms</span>
                <span className="text-gray-500 text-xs">
                  {result.timestamp.toLocaleTimeString()}
                </span>
              </div>
            </div>
            <pre className="text-xs bg-gray-900 p-2 rounded overflow-x-auto max-h-40">
              {JSON.stringify(result.response, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  )
}
