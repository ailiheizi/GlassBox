import { useState } from 'react'
import { useStore } from '../store'
import { Brain, Send, Trash2, ChevronDown, ChevronRight } from 'lucide-react'

export function AIDebugger() {
  const { user, aiDebug, addAIDebug, clearAIDebug } = useStore()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

  const toggleExpand = (id: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleChat = async () => {
    if (!input.trim() || !user?.token) return

    setLoading(true)
    addAIDebug({
      id: crypto.randomUUID(),
      timestamp: new Date(),
      type: 'input',
      content: input,
    })

    try {
      const response = await fetch('/api/v1/browser/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`,
        },
        body: JSON.stringify({ message: input }),
      })

      if (response.headers.get('content-type')?.includes('text/event-stream')) {
        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        while (reader) {
          const { done, value } = await reader.read()
          if (done) break

          const text = decoder.decode(value)
          const lines = text.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                addAIDebug({
                  id: crypto.randomUUID(),
                  timestamp: new Date(),
                  type: data.type || 'output',
                  content: typeof data.content === 'string' ? data.content : JSON.stringify(data),
                  metadata: data,
                })
              } catch {
                // 非JSON数据
              }
            }
          }
        }
      } else {
        const data = await response.json()
        addAIDebug({
          id: crypto.randomUUID(),
          timestamp: new Date(),
          type: 'output',
          content: JSON.stringify(data, null, 2),
          metadata: data,
        })
      }
    } catch (err) {
      addAIDebug({
        id: crypto.randomUUID(),
        timestamp: new Date(),
        type: 'output',
        content: `Error: ${err}`,
      })
    } finally {
      setLoading(false)
      setInput('')
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'input':
        return 'bg-blue-500/20 border-blue-500/50 text-blue-300'
      case 'output':
        return 'bg-green-500/20 border-green-500/50 text-green-300'
      case 'tool_call':
        return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300'
      case 'tool_result':
        return 'bg-purple-500/20 border-purple-500/50 text-purple-300'
      case 'thinking':
        return 'bg-gray-500/20 border-gray-500/50 text-gray-300'
      default:
        return 'bg-gray-500/20 border-gray-500/50 text-gray-300'
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'input':
        return '用户输入'
      case 'output':
        return 'AI输出'
      case 'tool_call':
        return '工具调用'
      case 'tool_result':
        return '工具结果'
      case 'thinking':
        return '思考过程'
      default:
        return type
    }
  }

  return (
    <div className="p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5" />
          <h2 className="text-lg font-semibold">AI 调试器</h2>
        </div>
        <button
          onClick={clearAIDebug}
          className="flex items-center gap-1 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          <Trash2 className="w-4 h-4" />
          清空
        </button>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto space-y-2 mb-4">
        {aiDebug.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            {user ? '发送消息开始调试' : '请先登录'}
          </div>
        ) : (
          aiDebug.map((item) => (
            <div
              key={item.id}
              className={`border rounded-lg p-3 ${getTypeColor(item.type)}`}
            >
              <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => toggleExpand(item.id)}
              >
                <div className="flex items-center gap-2">
                  {expandedItems.has(item.id) ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                  <span className="text-xs font-medium uppercase">
                    {getTypeLabel(item.type)}
                  </span>
                </div>
                <span className="text-xs opacity-60">
                  {item.timestamp.toLocaleTimeString()}
                </span>
              </div>

              <div className={`mt-2 ${expandedItems.has(item.id) ? '' : 'line-clamp-2'}`}>
                <pre className="text-sm whitespace-pre-wrap break-words font-mono">
                  {item.content}
                </pre>
              </div>

              {expandedItems.has(item.id) && item.metadata && (
                <div className="mt-2 pt-2 border-t border-current/20">
                  <div className="text-xs opacity-60 mb-1">Metadata:</div>
                  <pre className="text-xs bg-black/20 p-2 rounded overflow-x-auto">
                    {JSON.stringify(item.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* 输入框 */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleChat()}
          placeholder={user ? '输入消息...' : '请先登录'}
          disabled={!user || loading}
          className="flex-1 px-4 py-2 bg-gray-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          onClick={handleChat}
          disabled={!user || loading || !input.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition"
        >
          <Send className="w-4 h-4" />
          {loading ? '发送中...' : '发送'}
        </button>
      </div>
    </div>
  )
}
