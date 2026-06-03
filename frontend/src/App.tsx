import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Terminal,
  Brain,
  Activity,
  Database,
  Menu,
  X,
  Box,
  Layers,
  Wrench,
  Monitor
} from 'lucide-react'
import { ServiceHealth } from './components/ServiceHealth'
import { AuthPanel } from './components/AuthPanel'
import { ApiTester } from './components/ApiTester'
import { AIDebugger } from './components/AIDebugger'
import { ServiceDebugger } from './components/ServiceDebugger'
import { ContainerManager } from './components/ContainerManager'
import { IsolatedEnvironments } from './components/IsolatedEnvironments'
import { AIWorkspace } from './components/AIWorkspace'

function Dashboard() {
  return (
    <div className="space-y-6">
      <ServiceHealth />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Database className="w-5 h-5" />
            快速统计
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-700 rounded-lg p-3">
              <div className="text-2xl font-bold text-blue-400">7</div>
              <div className="text-sm text-gray-400">微服务</div>
            </div>
            <div className="bg-gray-700 rounded-lg p-3">
              <div className="text-2xl font-bold text-green-400">13</div>
              <div className="text-sm text-gray-400">Docker容器</div>
            </div>
            <div className="bg-gray-700 rounded-lg p-3">
              <div className="text-2xl font-bold text-yellow-400">4</div>
              <div className="text-sm text-gray-400">Proto定义</div>
            </div>
            <div className="bg-gray-700 rounded-lg p-3">
              <div className="text-2xl font-bold text-purple-400">70</div>
              <div className="text-sm text-gray-400">单元测试</div>
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">架构概览</h3>
          <div className="text-sm text-gray-400 space-y-2">
            <div className="flex justify-between">
              <span>Gateway</span>
              <span className="text-blue-400">:8080 (公网)</span>
            </div>
            <div className="flex justify-between">
              <span>Auth Service</span>
              <span className="text-gray-500">:8081 (内网)</span>
            </div>
            <div className="flex justify-between">
              <span>Memory Service</span>
              <span className="text-gray-500">:8082 (内网)</span>
            </div>
            <div className="flex justify-between">
              <span>Index Service</span>
              <span className="text-gray-500">:8083 (内网)</span>
            </div>
            <div className="flex justify-between">
              <span>Browser Service</span>
              <span className="text-gray-500">:8084 (内网)</span>
            </div>
            <div className="flex justify-between">
              <span>Task Service</span>
              <span className="text-gray-500">:8085 (内网)</span>
            </div>
            <div className="flex justify-between">
              <span>AI Service</span>
              <span className="text-gray-500">:8086 (内网)</span>
            </div>
          </div>
        </div>
      </div>

      {/* 快捷入口 */}
      <div className="p-4">
        <h3 className="text-lg font-semibold mb-4">快捷调试入口</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <NavLink
            to="/services"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-4 transition"
          >
            <Wrench className="w-8 h-8 text-blue-400 mb-2" />
            <div className="font-medium">服务调试器</div>
            <div className="text-sm text-gray-500">测试每个服务的API端点</div>
          </NavLink>
          <NavLink
            to="/containers"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-4 transition"
          >
            <Box className="w-8 h-8 text-green-400 mb-2" />
            <div className="font-medium">容器管理</div>
            <div className="text-sm text-gray-500">查看和管理Docker容器</div>
          </NavLink>
          <NavLink
            to="/environments"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-4 transition"
          >
            <Layers className="w-8 h-8 text-purple-400 mb-2" />
            <div className="font-medium">隔离环境</div>
            <div className="text-sm text-gray-500">创建独立测试环境</div>
          </NavLink>
          <NavLink
            to="/ai-debug"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-4 transition"
          >
            <Brain className="w-8 h-8 text-pink-400 mb-2" />
            <div className="font-medium">AI调试</div>
            <div className="text-sm text-gray-500">测试AI对话和工具调用</div>
          </NavLink>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [userId, setUserId] = useState<string>('guest')

  // Get authenticated user from localStorage and listen for changes
  useEffect(() => {
    const updateUserId = () => {
      try {
        const userStr = localStorage.getItem('user')
        if (userStr) {
          const user = JSON.parse(userStr)
          const newUserId = user?.id || user?.username || 'guest'
          setUserId(newUserId)
        } else {
          setUserId('guest')
        }
      } catch {
        setUserId('guest')
      }
    }

    // Update on mount
    updateUserId()

    // Listen for storage changes (login/logout in other tabs)
    window.addEventListener('storage', updateUserId)
    return () => window.removeEventListener('storage', updateUserId)
  }, [])

  const navItems = [
    { path: '/', icon: LayoutDashboard, label: '仪表盘' },
    { path: '/workspace', icon: Monitor, label: 'AI工作空间' },
    { path: '/services', icon: Wrench, label: '服务调试' },
    { path: '/api-tester', icon: Terminal, label: 'API测试' },
    { path: '/ai-debug', icon: Brain, label: 'AI调试' },
    { path: '/containers', icon: Box, label: '容器管理' },
    { path: '/environments', icon: Layers, label: '隔离环境' },
    { path: '/health', icon: Activity, label: '健康检查' },
  ]

  return (
    <BrowserRouter>
      <div className="min-h-screen flex">
        {/* 侧边栏 */}
        <aside
          className={`${
            sidebarOpen ? 'w-64' : 'w-16'
          } bg-gray-800 border-r border-gray-700 transition-all duration-300 flex flex-col`}
        >
          {/* Logo */}
          <div className="h-16 flex items-center justify-between px-4 border-b border-gray-700">
            {sidebarOpen && (
              <span className="font-bold text-lg">NewArch Debug</span>
            )}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-gray-700 rounded-lg"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>

          {/* 导航 */}
          <nav className="flex-1 p-2 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg transition ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                  }`
                }
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </NavLink>
            ))}
          </nav>

          {/* 用户面板 */}
          {sidebarOpen && (
            <div className="p-2 border-t border-gray-700">
              <AuthPanel />
            </div>
          )}
        </aside>

        {/* 主内容 */}
        <main className="flex-1 overflow-auto bg-gray-900">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/workspace" element={<AIWorkspace userId={userId} />} />
            <Route path="/services" element={<ServiceDebugger />} />
            <Route path="/api-tester" element={<ApiTester />} />
            <Route path="/ai-debug" element={<AIDebugger />} />
            <Route path="/containers" element={<ContainerManager />} />
            <Route path="/environments" element={<IsolatedEnvironments />} />
            <Route path="/health" element={<ServiceHealth />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
