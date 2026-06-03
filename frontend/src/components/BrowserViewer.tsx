/**
 * BrowserViewer - CDP Screencast 帧渲染器
 * 通过 WebSocket 接收 CDP Page.startScreencast 帧并渲染
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';

interface BrowserViewerProps {
  userId: string;
  apiBaseUrl?: string;
  quality?: number;
  maxWidth?: number;
  maxHeight?: number;
}

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export const BrowserViewer: React.FC<BrowserViewerProps> = ({
  userId,
  apiBaseUrl = '',
  quality = 60,
  maxWidth = 1280,
  maxHeight = 720,
}) => {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [fps, setFps] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameCountRef = useRef(0);
  const fpsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');
    setError(null);

    // 获取 JWT token
    const token = localStorage.getItem('token');
    if (!token) {
      setError('未找到认证令牌');
      setStatus('error');
      return;
    }

    // 构建 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = apiBaseUrl
      ? new URL(apiBaseUrl, window.location.origin).host
      : window.location.host;
    const wsUrl = `${protocol}//${host}/api/v1/ai/sandbox/screencast/${userId}/ws?quality=${quality}&maxWidth=${maxWidth}&maxHeight=${maxHeight}&token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      setError(null);
      frameCountRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'frame' && data.data && imgRef.current) {
          imgRef.current.src = `data:image/jpeg;base64,${data.data}`;
          frameCountRef.current++;
        } else if (data.error) {
          setError(data.error);
          setStatus('error');
        }
      } catch {
        // 忽略解析错误
      }
    };

    ws.onerror = () => {
      setStatus('error');
      setError('WebSocket 连接失败');
    };

    ws.onclose = (event) => {
      setStatus('disconnected');
      wsRef.current = null;

      // 自动重连（非正常关闭时）
      if (event.code !== 1000) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      }
    };
  }, [userId, apiBaseUrl, quality, maxWidth, maxHeight]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close(1000);
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  // 自动连接
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // FPS 计算
  useEffect(() => {
    fpsIntervalRef.current = setInterval(() => {
      setFps(frameCountRef.current);
      frameCountRef.current = 0;
    }, 1000);

    return () => {
      if (fpsIntervalRef.current) clearInterval(fpsIntervalRef.current);
    };
  }, []);

  const statusColor = {
    disconnected: 'bg-gray-500',
    connecting: 'bg-yellow-500',
    connected: 'bg-green-500',
    error: 'bg-red-500',
  }[status];

  const statusText = {
    disconnected: '未连接',
    connecting: '连接中...',
    connected: `已连接 (${fps} fps)`,
    error: '连接错误',
  }[status];

  return (
    <div className="flex flex-col h-full bg-black">
      {/* 状态栏 */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${statusColor}`} />
          <span className="text-gray-400 text-xs">{statusText}</span>
        </div>
        <div className="flex items-center space-x-2">
          {status === 'connected' ? (
            <button
              onClick={disconnect}
              className="px-2 py-0.5 text-xs text-gray-400 hover:text-white bg-gray-700 rounded"
            >
              断开
            </button>
          ) : (
            <button
              onClick={connect}
              className="px-2 py-0.5 text-xs text-gray-400 hover:text-white bg-gray-700 rounded"
            >
              连接
            </button>
          )}
        </div>
      </div>

      {/* 画面区域 */}
      <div className="flex-1 flex items-center justify-center overflow-hidden">
        {status === 'connected' || status === 'connecting' ? (
          <img
            ref={imgRef}
            alt="Browser Screencast"
            className="max-w-full max-h-full object-contain"
            style={{ imageRendering: 'auto' }}
          />
        ) : (
          <div className="text-center text-gray-500">
            {error ? (
              <>
                <p className="text-red-400 mb-2">{error}</p>
                <button
                  onClick={connect}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  重新连接
                </button>
              </>
            ) : (
              <p>等待浏览器画面...</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default BrowserViewer;
