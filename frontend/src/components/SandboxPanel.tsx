import React, { useState, useEffect } from 'react';
import {
  Monitor,
  Trash2,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Clock,
  Cpu,
  HardDrive,
  Loader2,
  Plus
} from 'lucide-react';
import { fetchApi } from '../api/client';

interface SandboxInfo {
  id: string;
  user_id: string;
  container_id: string;
  container_name: string;
  status: string;
  agent_port: number;
  screencast_url: string;
  created_at: string;
  last_active: string;
  resources: {
    cpu_percent: number;
    memory_mb: number;
  };
}

export const SandboxPanel: React.FC = () => {
  const [sandboxes, setSandboxes] = useState<SandboxInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newUserId, setNewUserId] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchSandboxes = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetchApi<{ sandboxes: SandboxInfo[] }>('/ai/sandboxes');
      if (response.error) {
        setError(response.error);
      } else {
        setSandboxes(response.data?.sandboxes || []);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch sandboxes');
    } finally {
      setLoading(false);
    }
  };

  const deleteSandbox = async (userId: string) => {
    if (!confirm(`确定要删除用户 ${userId} 的沙盒吗？`)) {
      return;
    }

    setDeletingId(userId);
    try {
      const response = await fetchApi(`/sandboxes/${userId}`, {
        method: 'DELETE'
      });

      if (response.error) {
        setError(response.error);
      } else {
        await fetchSandboxes();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete sandbox');
    } finally {
      setDeletingId(null);
    }
  };

  const handleCreateSandbox = async () => {
    if (!newUserId.trim()) {
      setError('请输入用户ID');
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const response = await fetchApi(`/ai/sandbox/create/${newUserId.trim()}`, {
        method: 'POST'
      });

      if (response.error) {
        setError(`创建失败: ${response.error}`);
      } else {
        setShowCreateForm(false);
        setNewUserId('');
        await fetchSandboxes();
      }
    } catch (err: any) {
      setError(`创建失败: ${err.message || 'Unknown error'}`);
    } finally {
      setCreating(false);
    }
  };

  const openScreencast = (sandbox: SandboxInfo) => {
    // screencast 通过 WebSocket 在 AIWorkspace 中查看，这里打开工作空间
    window.open(`/workspace?user=${sandbox.user_id}`, '_blank');
  };

  useEffect(() => {
    fetchSandboxes();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchSandboxes, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'creating':
        return <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />;
      case 'stopped':
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'text-green-400';
      case 'creating': return 'text-yellow-400';
      case 'stopped': return 'text-gray-400';
      case 'error': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diff < 60) return `${diff}秒前`;
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    return date.toLocaleString('zh-CN');
  };

  return (
    <div className="h-full flex flex-col">
      {/* 头部工具栏 */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Monitor className="w-5 h-5" />
          用户沙盒
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm"
          >
            <Plus className="w-4 h-4" />
            创建沙箱
          </button>
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            自动刷新
          </label>
          <button
            onClick={fetchSandboxes}
            disabled={loading}
            className="flex items-center gap-1 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      {/* 创建沙箱表单 */}
      {showCreateForm && (
        <div className="bg-gray-800 rounded-lg p-4 mb-4 border border-gray-700">
          <h3 className="text-sm font-semibold mb-3">创建新沙箱</h3>
          <div className="flex gap-2">
            <input
              type="text"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              placeholder="输入用户ID"
              className="flex-1 px-3 py-2 bg-gray-700 rounded text-sm text-white placeholder-gray-500"
              disabled={creating}
            />
            <button
              onClick={handleCreateSandbox}
              disabled={creating || !newUserId.trim()}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded text-sm font-medium"
            >
              {creating ? '创建中...' : '创建'}
            </button>
            <button
              onClick={() => {
                setShowCreateForm(false);
                setNewUserId('');
              }}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded text-sm"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-500/20 border border-red-500 text-red-400 px-4 py-3 rounded mb-4 text-sm">
          {error}
        </div>
      )}

      {/* 沙盒列表 */}
      <div className="flex-1 overflow-auto">
        {sandboxes.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            暂无活跃的沙盒
          </div>
        ) : (
          <div className="grid gap-3">
            {sandboxes.map((sandbox) => (
              <div
                key={sandbox.id}
                className="bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-1">
                    {getStatusIcon(sandbox.status)}
                    <div>
                      <div className="font-medium">{sandbox.user_id}</div>
                      <div className="text-xs text-gray-500">{sandbox.container_name}</div>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getStatusColor(sandbox.status)}`}>
                      {sandbox.status}
                    </span>
                  </div>

                  {/* 资源使用 */}
                  <div className="flex items-center gap-4 text-xs text-gray-400 mr-4">
                    <span className="flex items-center gap-1">
                      <Cpu className="w-3 h-3" />
                      {sandbox.resources.cpu_percent.toFixed(1)}%
                    </span>
                    <span className="flex items-center gap-1">
                      <HardDrive className="w-3 h-3" />
                      {sandbox.resources.memory_mb} MB
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTime(sandbox.last_active)}
                    </span>
                  </div>

                  {/* 操作按钮 */}
                  <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                    <button
                      onClick={() => openScreencast(sandbox)}
                      className="p-1 hover:bg-green-600/20 rounded text-green-400"
                      title="打开工作空间"
                    >
                      <Monitor className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteSandbox(sandbox.user_id)}
                      disabled={deletingId === sandbox.user_id}
                      className="p-1 hover:bg-red-600/20 rounded text-gray-400 hover:text-red-400 disabled:opacity-50"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* VNC 端口信息 */}
                <div className="mt-2 text-xs text-gray-500">
                  Agent: {sandbox.agent_port}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 底部统计 */}
      <div className="mt-4 text-sm text-gray-500">
        共 {sandboxes.length} 个活跃沙盒
      </div>
    </div>
  );
};
