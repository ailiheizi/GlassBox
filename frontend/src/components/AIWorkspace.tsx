/**
 * AI 工作空间组件
 * 集成 CDP Screencast 浏览器查看器、文件管理器和 AI 聊天面板
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { BrowserViewer } from './BrowserViewer';
import { FileExplorer } from './FileExplorer';
import { TraceTimeline, TraceEvent } from './TraceTimeline';

interface SandboxInfo {
  id: string;
  user_id: string;
  status: string;
  agent_port: number;
  screencast_url: string;
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  thinking?: string;
  reasoning?: string;
  modelInfo?: ModelSelectionInfo;
  step?: number;
  status?: string;
}

interface ModelSelectionInfo {
  model: string;
  category: string;
  confidence: number;
  reason: string;
}

interface ExecutionState {
  currentStep: number;
  maxSteps: number;
  status: 'idle' | 'thinking' | 'executing' | 'completed' | 'failed';
  thinkingContent: string;
  reasoningContent: string;
  modelInfo: ModelSelectionInfo | null;
  actionHistory: string[];
  traceEvents: TraceEvent[];
}

interface ToolCall {
  tool: string;
  args: Record<string, any>;
  result?: Record<string, any>;
}

interface AIWorkspaceProps {
  userId: string;
  apiBaseUrl?: string;
}

export const AIWorkspace: React.FC<AIWorkspaceProps> = ({
  userId,
  apiBaseUrl = '/api/v1'
}) => {
  const [sandbox, setSandbox] = useState<SandboxInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTab, setActiveTab] = useState<'browser' | 'files'>('browser');

  const [executionState, setExecutionState] = useState<ExecutionState>({
    currentStep: 0,
    maxSteps: 0,
    status: 'idle',
    thinkingContent: '',
    reasoningContent: '',
    modelInfo: null,
    actionHistory: [],
    traceEvents: [],
  });

  const [showTrace, setShowTrace] = useState(true);
  const [traceWidth, setTraceWidth] = useState(320);
  const isDraggingRef = useRef(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const thinkingBufferRef = useRef<{ step: number; content: string; model?: string } | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // TraceTimeline 拖拽调节宽度
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    const startX = e.clientX;
    const startWidth = traceWidth;

    const onMouseMove = (ev: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = ev.clientX - startX;
      const newWidth = Math.max(200, Math.min(600, startWidth + delta));
      setTraceWidth(newWidth);
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [traceWidth]);

  // 推送 trace 事件
  let traceIdCounter = 0;
  const pushTraceEvent = (type: TraceEvent['type'], data: Record<string, any>) => {
    const evt: TraceEvent = {
      id: `trace-${Date.now()}-${traceIdCounter++}`,
      timestamp: new Date(),
      type,
      data,
    };
    setExecutionState(prev => ({
      ...prev,
      traceEvents: [...prev.traceEvents, evt],
    }));
  };

  // 创建或获取沙箱
  const initSandbox = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('未登录，请先登录');
      }

      const response = await fetch(`${apiBaseUrl}/ai/sandbox/create/${userId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.status === 401) {
        localStorage.removeItem('token');
        throw new Error('登录已过期，请重新登录');
      }

      if (!response.ok) {
        throw new Error(`Failed to create sandbox: ${response.statusText}`);
      }

      const data = await response.json();
      setSandbox(data);

      setMessages([{
        role: 'system',
        content: `沙箱环境已创建 (ID: ${data.id})。浏览器标签查看实时画面，文件标签管理沙箱文件。`,
        timestamp: new Date(),
      }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [userId, apiBaseUrl]);

  // 销毁沙箱
  const destroySandbox = async () => {
    if (!sandbox) return;

    try {
      const token = localStorage.getItem('token');
      await fetch(`${apiBaseUrl}/ai/sandbox/destroy/${userId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      setSandbox(null);
      setMessages([]);
    } catch (err) {
      console.error('Failed to destroy sandbox:', err);
    }
  };

  // 心跳保活
  useEffect(() => {
    if (!sandbox) return;

    let failCount = 0;
    const maxFailures = 3;

    const interval = setInterval(async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await fetch(`${apiBaseUrl}/ai/sandbox/keepalive/${userId}`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (response.ok) {
          failCount = 0;
        } else if (response.status === 401) {
          localStorage.removeItem('token');
          setError('登录已过期，请重新登录');
          setSandbox(null);
        } else if (response.status === 404) {
          setError('沙箱已过期，请重新创建');
          setSandbox(null);
        } else {
          failCount++;
          if (failCount >= maxFailures) {
            setError('沙箱连接不稳定，请检查网络或重新创建');
          }
        }
      } catch (err) {
        console.error('Keepalive failed:', err);
        failCount++;
        if (failCount >= maxFailures) {
          setError('无法连接到服务器，请检查网络');
        }
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [sandbox, userId, apiBaseUrl]);

  // 停止执行
  const stopExecution = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
      setExecutionState(prev => ({ ...prev, status: 'idle' }));
      setMessages(prev => {
        const newMessages = [...prev];
        if (newMessages.length > 0) {
          const lastMsg = newMessages[newMessages.length - 1];
          if (lastMsg.role === 'assistant') {
            lastMsg.content += '\n[用户停止执行]';
          }
        }
        return newMessages;
      });
    }
  }, []);

  // 发送消息
  const sendMessage = async () => {
    if (!inputMessage.trim() || !sandbox || isStreaming) return;

    const messageContent = inputMessage;
    const userMessage: Message = {
      role: 'user',
      content: messageContent,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsStreaming(true);

    abortControllerRef.current = new AbortController();

    try {
      const token = localStorage.getItem('token');
      if (!token) throw new Error('登录已过期，请重新登录');

      const response = await fetch(`${apiBaseUrl}/ai/sandbox/smart/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          user_id: userId,
          message: messageContent,
          include_screenshot: true,
          continuous: true,
          max_steps: 15,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (response.status === 401) {
        localStorage.removeItem('token');
        throw new Error('登录已过期，请重新登录');
      }

      if (!response.ok) throw new Error(`Chat failed: ${response.statusText}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let assistantMessage: Message = {
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        toolCalls: [],
        thinking: '',
        reasoning: '',
      };

      setExecutionState({
        currentStep: 0,
        maxSteps: 0,
        status: 'idle',
        thinkingContent: '',
        reasoningContent: '',
        modelInfo: null,
        actionHistory: [],
        traceEvents: [],
      });

      setMessages(prev => [...prev, assistantMessage]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);

              if (parsed.type === 'sandbox_info') {
                setSandbox(prev => prev ? {
                  ...prev,
                  id: parsed.data.id || prev.id,
                  screencast_url: parsed.data.screencast_url || prev.screencast_url,
                  status: parsed.data.status || prev.status,
                } : prev);

              } else if (parsed.type === 'model_selection') {
                const modelInfo = parsed.data as ModelSelectionInfo;
                setExecutionState(prev => ({ ...prev, modelInfo }));
                assistantMessage.modelInfo = modelInfo;
                pushTraceEvent('model_routing', parsed.data);

              } else if (parsed.type === 'skill_retrieval_detail') {
                pushTraceEvent('skill_retrieval', parsed.data);

              } else if (parsed.type === 'skills_matched') {
                // 忽略（skill_retrieval_detail 已包含完整数据）

              } else if (parsed.type === 'model_routing_reasoning') {
                pushTraceEvent('thinking', {
                  content: parsed.data.llm_response || '',
                  reasoning: parsed.data.llm_reasoning || '',
                  model: parsed.data.model || 'deepseek-chat',
                  label: '模型路由推理',
                });

              } else if (parsed.type === 'step_start') {
                const { step, max_steps } = parsed.data;
                setExecutionState(prev => ({
                  ...prev,
                  currentStep: step,
                  maxSteps: max_steps,
                  status: 'executing',
                  thinkingContent: '',
                }));
                assistantMessage.step = step;
                pushTraceEvent('step_start', parsed.data);

              } else if (parsed.type === 'thinking_start') {
                setExecutionState(prev => ({ ...prev, status: 'thinking' }));
                thinkingBufferRef.current = { step: parsed.data.step, content: '', model: parsed.data.model };

              } else if (parsed.type === 'thinking') {
                const content = parsed.data.content || '';
                assistantMessage.thinking = (assistantMessage.thinking || '') + content;
                if (thinkingBufferRef.current && thinkingBufferRef.current.step === parsed.data.step) {
                  thinkingBufferRef.current.content += content;
                } else {
                  thinkingBufferRef.current = { step: parsed.data.step, content, model: undefined };
                }
                setExecutionState(prev => ({
                  ...prev,
                  thinkingContent: prev.thinkingContent + content,
                }));

              } else if (parsed.type === 'thinking_end') {
                if (thinkingBufferRef.current && thinkingBufferRef.current.content) {
                  pushTraceEvent('thinking', {
                    step: thinkingBufferRef.current.step,
                    content: thinkingBufferRef.current.content,
                    model: thinkingBufferRef.current.model,
                  });
                }
                thinkingBufferRef.current = null;

              } else if (parsed.type === 'reasoning') {
                const content = parsed.data.content || '';
                setExecutionState(prev => ({ ...prev, reasoningContent: content }));
                assistantMessage.reasoning = content;
                pushTraceEvent('thinking', { content, step: parsed.data.step, label: '推理过程' });

              } else if (parsed.type === 'llm_call_start') {
                pushTraceEvent('llm_call_start', parsed.data);

              } else if (parsed.type === 'llm_call_end') {
                pushTraceEvent('llm_call_end', parsed.data);

              } else if (parsed.type === 'task_status') {
                assistantMessage.status = parsed.data.status;

              } else if (parsed.type === 'text') {
                assistantMessage.content += parsed.data.content || '';
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1] = { ...assistantMessage };
                  return newMessages;
                });

              } else if (parsed.type === 'tool_call') {
                assistantMessage.toolCalls?.push({
                  tool: parsed.data.tool,
                  args: parsed.data.args,
                });
                pushTraceEvent('tool_call', parsed.data);

              } else if (parsed.type === 'tool_result') {
                const lastToolCall = assistantMessage.toolCalls?.[assistantMessage.toolCalls.length - 1];
                if (lastToolCall) lastToolCall.result = parsed.data.result;
                pushTraceEvent('tool_result', parsed.data);

              } else if (parsed.type === 'tool_error') {
                pushTraceEvent('tool_error', parsed.data);

              } else if (parsed.type === 'step_end') {
                pushTraceEvent('step_end', parsed.data);

              } else if (parsed.type === 'execution_complete') {
                const { total_steps, final_status, action_history } = parsed.data;
                setExecutionState(prev => ({
                  ...prev,
                  status: final_status === 'completed' ? 'completed' : 'failed',
                  actionHistory: action_history || [],
                }));
                pushTraceEvent('execution_complete', parsed.data);
                const statusText = final_status === 'completed' ? '已完成' : '执行失败';
                assistantMessage.content += `\n${statusText} (共 ${total_steps} 步)\n`;
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1] = { ...assistantMessage };
                  return newMessages;
                });

              } else if (parsed.type === 'warning') {
                pushTraceEvent('warning', parsed.data);

              } else if (parsed.type === 'error') {
                setError(parsed.data.message);
                pushTraceEvent('error', parsed.data);

              } else if (parsed.type === 'screenshot') {
                pushTraceEvent('screenshot', parsed.data);

              } else if (parsed.type === 'mode_selection') {
                pushTraceEvent('model_routing', { ...parsed.data, label: '操作模式' });

              } else if (parsed.type === 'mode_switch') {
                pushTraceEvent('node_transition', { from_node: null, to_node: parsed.data.new_mode, iteration: 0, reason: parsed.data.reason });

              } else if (parsed.type === 'model_switch') {
                pushTraceEvent('model_switch', parsed.data);
              }
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        console.log('Request aborted by user');
      } else {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const isAuthenticated = !!localStorage.getItem('token') && userId !== 'guest';

  useEffect(() => {
    if (isAuthenticated) {
      initSandbox();
    }
  }, [initSandbox, isAuthenticated]);

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900">
        <div className="text-center text-gray-400">
          <p className="text-lg mb-2">请先登录后使用 AI 工作空间</p>
          <p className="text-sm">登录后即可创建沙箱环境</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-900">
      {/* 左侧: 浏览器/文件查看器 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 头部 */}
        <div className="bg-gray-800 px-4 py-2 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${sandbox ? 'bg-green-500' : 'bg-yellow-500'}`} />
            <span className="text-white font-medium">
              沙箱 {sandbox?.id || '未连接'}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            {/* 标签切换: 浏览器 / 文件 */}
            <div className="flex bg-gray-700 rounded-lg p-1 mr-2">
              <button
                onClick={() => setActiveTab('browser')}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  activeTab === 'browser'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                浏览器
              </button>
              <button
                onClick={() => setActiveTab('files')}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  activeTab === 'files'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                文件
              </button>
            </div>
            <button
              onClick={initSandbox}
              disabled={loading}
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? '创建中...' : '重新创建'}
            </button>
            <button
              onClick={destroySandbox}
              disabled={!sandbox}
              className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
            >
              销毁
            </button>
          </div>
        </div>

        {/* 主内容区 */}
        <div className="flex-1 bg-black relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4" />
                <p className="text-white">正在创建沙箱环境...</p>
              </div>
            </div>
          )}

          {error && !loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
              <div className="text-center">
                <p className="text-red-500 mb-4">{error}</p>
                <button
                  onClick={initSandbox}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  重试
                </button>
              </div>
            </div>
          )}

          {sandbox && !loading && !error && (
            <>
              {/* 浏览器视图 (CDP Screencast) */}
              <div className={`w-full h-full ${activeTab === 'browser' ? 'block' : 'hidden'}`}>
                <BrowserViewer userId={userId} />
              </div>
              {/* 文件管理器 */}
              <div className={`w-full h-full ${activeTab === 'files' ? 'block' : 'hidden'}`}>
                <FileExplorer userId={userId} />
              </div>
            </>
          )}
        </div>
      </div>

      {/* 中间: TraceTimeline（可折叠） */}
      {showTrace && (
        <>
          <div
            className="flex flex-col bg-gray-850 border-l border-gray-700"
            style={{ width: `${traceWidth}px`, minWidth: '200px', maxWidth: '600px' }}
          >
            <TraceTimeline
              events={executionState.traceEvents}
              isStreaming={isStreaming}
              onClose={() => setShowTrace(false)}
            />
          </div>
          <div
            className="w-1 bg-gray-700 cursor-col-resize hover:bg-blue-500 transition-colors flex-shrink-0"
            onMouseDown={handleDragStart}
          />
        </>
      )}

      {/* 右侧: 聊天面板 */}
      <div className="w-80 flex flex-col bg-gray-800 border-l border-gray-700 flex-shrink-0">
        <div className="px-3 py-2 border-b border-gray-700">
          <div className="flex items-center justify-between">
            <h2 className="text-white font-medium text-sm">AI 助手</h2>
            <button
              onClick={() => setShowTrace(!showTrace)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                showTrace ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400 hover:text-white'
              }`}
            >
              链路
            </button>
          </div>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`${
                msg.role === 'user' ? 'ml-6' : msg.role === 'system' ? 'mx-2' : 'mr-6'
              }`}
            >
              <div
                className={`rounded-lg p-2.5 text-sm ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : msg.role === 'system'
                    ? 'bg-gray-700 text-gray-300 text-xs'
                    : 'bg-gray-700 text-white'
                }`}
              >
                {msg.content && <p className="whitespace-pre-wrap">{msg.content}</p>}
              </div>
              <p className="text-gray-500 text-xs mt-1">
                {msg.timestamp.toLocaleTimeString()}
              </p>
            </div>
          ))}

          {isStreaming && (
            <div className="bg-gray-700 rounded-lg p-2.5">
              <div className="flex items-center space-x-2 text-gray-400 text-sm">
                <div className="animate-pulse">●</div>
                <span>
                  {executionState.status === 'thinking' ? 'AI 正在思考...' :
                    executionState.status === 'executing' ? `步骤 ${executionState.currentStep}/${executionState.maxSteps}` :
                    'AI 正在处理...'}
                </span>
              </div>
              {executionState.currentStep > 0 && (
                <div className="w-full bg-gray-600 rounded-full h-1 mt-2">
                  <div
                    className="bg-blue-500 h-1 rounded-full transition-all duration-300"
                    style={{ width: `${(executionState.currentStep / executionState.maxSteps) * 100}%` }}
                  />
                </div>
              )}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入框 */}
        <div className="p-3 border-t border-gray-700">
          <div className="flex space-x-2">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入消息..."
              disabled={!sandbox || isStreaming}
              className="flex-1 bg-gray-700 text-white rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 text-sm"
              rows={2}
            />
            {isStreaming ? (
              <button
                onClick={stopExecution}
                className="px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
              >
                停止
              </button>
            ) : (
              <button
                onClick={sendMessage}
                disabled={!sandbox || !inputMessage.trim()}
                className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                发送
              </button>
            )}
          </div>
          <p className="text-gray-500 text-xs mt-1">
            Enter 发送，Shift+Enter 换行
          </p>
        </div>
      </div>
    </div>
  );
};

export default AIWorkspace;
