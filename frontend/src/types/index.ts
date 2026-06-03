// 服务状态
export interface ServiceStatus {
  name: string
  url: string
  status: 'healthy' | 'unhealthy' | 'unknown'
  latency?: number
  lastCheck: Date
}

// 请求追踪
export interface RequestTrace {
  id: string
  requestId: string
  method: string
  path: string
  status: number
  duration: number
  timestamp: Date
  userId?: string
  service: string
  error?: string
}

// 日志条目
export interface LogEntry {
  id: string
  timestamp: Date
  level: 'debug' | 'info' | 'warn' | 'error'
  service: string
  message: string
  metadata?: Record<string, unknown>
}

// AI调试信息
export interface AIDebugInfo {
  id: string
  timestamp: Date
  type: 'input' | 'output' | 'tool_call' | 'tool_result' | 'thinking'
  content: string
  metadata?: Record<string, unknown>
}

// 用户信息
export interface User {
  id: string
  username: string
  email: string
  token?: string
}

// API响应
export interface ApiResponse<T> {
  data?: T
  error?: string
  status: number
}
