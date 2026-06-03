import { useState } from 'react'
import { useStore } from '../store'
import { authApi } from '../api/client'
import { User, LogIn, LogOut, UserPlus } from 'lucide-react'

export function AuthPanel() {
  const { user, setUser } = useStore()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      if (mode === 'login') {
        const result = await authApi.login({
          username: form.username,
          password: form.password,
        })
        if (result.error) {
          setError(result.error)
        } else if (result.data) {
          localStorage.setItem('token', result.data.token)
          localStorage.setItem('user', JSON.stringify(result.data.user))
          setUser({ ...result.data.user, token: result.data.token })
        }
      } else {
        const result = await authApi.register({
          username: form.username,
          email: form.email,
          password: form.password,
        })
        if (result.error) {
          setError(result.error)
        } else {
          setMode('login')
          setError('')
          alert('注册成功，请登录')
        }
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
  }

  if (user) {
    return (
      <div className="p-4 bg-gray-800 rounded-lg">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center">
            <User className="w-5 h-5" />
          </div>
          <div>
            <div className="font-medium">{user.username}</div>
            <div className="text-sm text-gray-400">{user.email}</div>
          </div>
        </div>
        <div className="text-xs text-gray-500 mb-3 break-all">
          ID: {user.id}
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg transition"
        >
          <LogOut className="w-4 h-4" />
          退出登录
        </button>
      </div>
    )
  }

  return (
    <div className="p-4 bg-gray-800 rounded-lg">
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setMode('login')}
          className={`flex-1 py-2 rounded-lg transition ${
            mode === 'login' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
          }`}
        >
          <LogIn className="w-4 h-4 inline mr-2" />
          登录
        </button>
        <button
          onClick={() => setMode('register')}
          className={`flex-1 py-2 rounded-lg transition ${
            mode === 'register' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
          }`}
        >
          <UserPlus className="w-4 h-4 inline mr-2" />
          注册
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="text"
          placeholder="用户名"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          className="w-full px-3 py-2 bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
        {mode === 'register' && (
          <input
            type="email"
            placeholder="邮箱"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="w-full px-3 py-2 bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        )}
        <input
          type="password"
          placeholder="密码"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          className="w-full px-3 py-2 bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
        {error && <div className="text-red-400 text-sm">{error}</div>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition"
        >
          {loading ? '处理中...' : mode === 'login' ? '登录' : '注册'}
        </button>
      </form>
    </div>
  )
}
