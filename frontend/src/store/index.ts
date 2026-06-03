import { create } from 'zustand'
import type { ServiceStatus, RequestTrace, LogEntry, AIDebugInfo, User } from '../types'

interface AppState {
  // 用户状态
  user: User | null
  setUser: (user: User | null) => void

  // 服务状态
  services: ServiceStatus[]
  updateService: (name: string, status: Partial<ServiceStatus>) => void

  // 请求追踪
  traces: RequestTrace[]
  addTrace: (trace: RequestTrace) => void
  clearTraces: () => void

  // 日志
  logs: LogEntry[]
  addLog: (log: LogEntry) => void
  clearLogs: () => void

  // AI调试
  aiDebug: AIDebugInfo[]
  addAIDebug: (info: AIDebugInfo) => void
  clearAIDebug: () => void

  // UI状态
  activeTab: string
  setActiveTab: (tab: string) => void
}

// 从 localStorage 恢复用户状态
function getInitialUser(): User | null {
  try {
    const token = localStorage.getItem('token')
    const userStr = localStorage.getItem('user')
    if (token && userStr) {
      const user = JSON.parse(userStr)
      return { ...user, token }
    }
  } catch {
    // 忽略解析错误
  }
  return null
}

export const useStore = create<AppState>((set) => ({
  // 用户状态 - 从 localStorage 恢复
  user: getInitialUser(),
  setUser: (user) => set({ user }),

  // 服务状态
  services: [
    { name: 'gateway', url: 'http://gateway:8080', status: 'unknown', lastCheck: new Date() },
    { name: 'auth', url: 'http://auth-service:8081', status: 'unknown', lastCheck: new Date() },
    { name: 'memory', url: 'http://memory-service:8082', status: 'unknown', lastCheck: new Date() },
    { name: 'index', url: 'http://index-service:8083', status: 'unknown', lastCheck: new Date() },
    { name: 'browser', url: 'http://browser-service:8084', status: 'unknown', lastCheck: new Date() },
    { name: 'task', url: 'http://task-service:8085', status: 'unknown', lastCheck: new Date() },
    { name: 'ai', url: 'http://ai-service:8086', status: 'unknown', lastCheck: new Date() },
  ],
  updateService: (name, status) =>
    set((state) => ({
      services: state.services.map((s) =>
        s.name === name ? { ...s, ...status, lastCheck: new Date() } : s
      ),
    })),

  // 请求追踪
  traces: [],
  addTrace: (trace) =>
    set((state) => ({
      traces: [trace, ...state.traces].slice(0, 100),
    })),
  clearTraces: () => set({ traces: [] }),

  // 日志
  logs: [],
  addLog: (log) =>
    set((state) => ({
      logs: [log, ...state.logs].slice(0, 500),
    })),
  clearLogs: () => set({ logs: [] }),

  // AI调试
  aiDebug: [],
  addAIDebug: (info) =>
    set((state) => ({
      aiDebug: [...state.aiDebug, info].slice(-100),
    })),
  clearAIDebug: () => set({ aiDebug: [] }),

  // UI状态
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),
}))
