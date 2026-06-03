const API_BASE = '/api/v1'

// 内网服务代理路径 (通过nginx代理访问Docker内部服务)
const INTERNAL_SERVICES = {
  gateway: '/internal/gateway',
  auth: '/internal/auth',
  memory: '/internal/memory',
  index: '/internal/index',
  browser: '/internal/browser',
  task: '/internal/task',
  ai: '/internal/ai',
}

export async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<{ data?: T; error?: string; status: number }> {
  try {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      return { error: data?.error || response.statusText, status: response.status }
    }

    return { data, status: response.status }
  } catch (error) {
    return { error: String(error), status: 0 }
  }
}

// 直接访问内部服务 (用于调试)
export async function fetchInternal<T>(
  service: keyof typeof INTERNAL_SERVICES,
  path: string,
  options: RequestInit = {}
): Promise<{ data?: T; error?: string; status: number; latency: number }> {
  const start = Date.now()
  try {
    const response = await fetch(`${INTERNAL_SERVICES[service]}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    const latency = Date.now() - start
    const data = await response.json().catch(() => null)

    if (!response.ok) {
      return { error: data?.error || response.statusText, status: response.status, latency }
    }

    return { data, status: response.status, latency }
  } catch (error) {
    return { error: String(error), status: 0, latency: Date.now() - start }
  }
}

// 健康检查
export async function checkServiceHealth(service: keyof typeof INTERNAL_SERVICES) {
  return fetchInternal(service, '/health')
}

// Auth API
export const authApi = {
  register: (data: { username: string; email: string; password: string }) =>
    fetchApi('/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  login: (data: { username: string; password: string }) =>
    fetchApi<{ token: string; user: { id: string; username: string; email: string } }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify(data) }
    ),

  profile: () => fetchApi('/auth/profile'),
}

// Memory API
export const memoryApi = {
  save: (data: { content: string; content_type?: string }) =>
    fetchApi('/memory/semantic', { method: 'POST', body: JSON.stringify(data) }),

  search: (query: string, limit = 10) =>
    fetchApi(`/memory/semantic/search?query=${encodeURIComponent(query)}&limit=${limit}`),

  recent: (limit = 20) =>
    fetchApi(`/memory/recent?limit=${limit}`),
}

// Index API
export const indexApi = {
  search: (query: string) =>
    fetchApi(`/indexes/search?query=${encodeURIComponent(query)}`),

  listAI: () => fetchApi('/indexes/ai'),

  createAI: (data: { url: string; title: string; description?: string }) =>
    fetchApi('/indexes/ai', { method: 'POST', body: JSON.stringify(data) }),
}

// Task API
export const taskApi = {
  list: () => fetchApi('/tasks'),
  create: (data: { input: string }) =>
    fetchApi('/tasks', { method: 'POST', body: JSON.stringify(data) }),
  get: (id: string) => fetchApi(`/tasks/${id}`),
}

// Sandbox API
export const sandboxApi = {
  getSandboxes: () => fetchApi('/ai/sandboxes', { method: 'GET' }),

  getSandbox: (userId: string) =>
    fetchApi(`/ai/sandbox/info/${userId}`, { method: 'GET' }),

  createSandbox: (userId: string) =>
    fetchApi(`/ai/sandbox/create/${userId}`, { method: 'POST' }),

  deleteSandbox: (userId: string) =>
    fetchApi(`/ai/sandbox/destroy/${userId}`, { method: 'DELETE' }),

  keepaliveSandbox: (userId: string) =>
    fetchApi(`/ai/sandbox/keepalive/${userId}`, { method: 'POST' }),

  getScreenshot: (userId: string) =>
    fetchApi(`/ai/sandbox/screenshot/${userId}`, { method: 'GET' }),

  chat: (data: { user_id: string; message: string; include_screenshot?: boolean }) =>
    fetchApi('/ai/sandbox/chat', { method: 'POST', body: JSON.stringify(data) }),

  chatStream: (data: { user_id: string; message: string; include_screenshot?: boolean }) =>
    fetchApi('/ai/sandbox/chat/stream', { method: 'POST', body: JSON.stringify(data) }),
}
