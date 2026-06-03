#!/bin/bash
# NewArch Sandbox Entrypoint Script
# root 启动系统服务，gosu 降权运行用户进程

set -e

echo "=========================================="
echo "  NewArch AI Agent Sandbox (Slim)"
echo "=========================================="
echo "User ID: ${USER_ID:-unknown}"
echo "Resolution: ${RESOLUTION}"
echo "Agent Port: ${AGENT_PORT}"
echo "CDP Port: ${CDP_PORT:-9222}"
echo "=========================================="

# 清理旧的锁文件
rm -f /tmp/.X1-lock
rm -f /tmp/.X11-unix/X1

# ---- 以下以 root 身份启动系统级服务 ----

# 1. 启动虚拟显示 (Xvfb) - 需要 root 创建 X socket
echo "[1/4] Starting Xvfb..."
Xvfb :1 -screen 0 ${RESOLUTION}x24 &
XVFB_PID=$!
sleep 2

if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "ERROR: Xvfb failed to start"
    exit 1
fi
echo "  Xvfb started (PID: $XVFB_PID)"

# 确保 X11 socket 可被 sandbox 用户访问
chmod 1777 /tmp/.X11-unix

# 2. 启动 tmux 服务器（以 sandbox 用户身份）
echo "[2/4] Starting tmux server..."
gosu sandbox tmux start-server
gosu sandbox tmux new-session -d -s default -c /home/sandbox/workspace || true
echo "  tmux server started"

# ---- 以下以 sandbox 用户身份运行 ----
export DISPLAY=:1

# 3. 启动 Chromium（CDP 远程调试模式）
echo "[3/4] Starting Chromium with CDP..."
CDP_PORT=${CDP_PORT:-9222}
# 使用不同的内部端口，socat 转发到 0.0.0.0
CDP_INTERNAL_PORT=19222
gosu sandbox bash -c "export DISPLAY=:1 HOME=/home/sandbox; chromium --no-sandbox \
    --remote-debugging-port=${CDP_INTERNAL_PORT} \
    --remote-allow-origins=* \
    --no-first-run --no-default-browser-check \
    --disable-extensions about:blank" &
CHROMIUM_PID=$!

# 等待 Chromium CDP 就绪（最多 15 秒）
CDP_READY=false
for i in $(seq 1 15); do
    if curl -s --max-time 2 http://127.0.0.1:${CDP_INTERNAL_PORT}/json/version > /dev/null 2>&1; then
        CDP_READY=true
        echo "  Chromium CDP started on internal port ${CDP_INTERNAL_PORT} (waited ${i}s)"
        break
    fi
    sleep 1
done

if [ "$CDP_READY" = true ]; then
    # 用 socat 将 0.0.0.0:9222 转发到 127.0.0.1:19222，使外部容器可访问
    socat TCP-LISTEN:${CDP_PORT},fork,bind=0.0.0.0,reuseaddr TCP:127.0.0.1:${CDP_INTERNAL_PORT} &
    SOCAT_PID=$!
    sleep 1
    echo "  CDP port forwarding started (PID: $SOCAT_PID) on 0.0.0.0:${CDP_PORT}"
else
    echo "WARNING: Chromium CDP failed to start after 15s, continuing anyway..."
fi

# 4. 启动 AI Agent 服务
echo "[4/4] Starting AI Agent service..."
cd /opt/ai-tools
gosu sandbox python3 -m uvicorn agent_server:app --host 0.0.0.0 --port ${AGENT_PORT} &
AGENT_PID=$!
sleep 2

if ! kill -0 $AGENT_PID 2>/dev/null; then
    echo "WARNING: AI Agent service failed to start, continuing anyway..."
else
    echo "  AI Agent started (PID: $AGENT_PID) on port ${AGENT_PORT}"
fi

echo ""
echo "=========================================="
echo "  Sandbox Ready! (user: sandbox)"
echo "=========================================="
echo "  CDP:     http://localhost:${CDP_PORT:-9222}"
echo "  Agent:   http://localhost:${AGENT_PORT}"
echo "=========================================="
echo ""

# 信号处理 - 优雅关闭
cleanup() {
    echo "Shutting down sandbox..."
    kill $AGENT_PID 2>/dev/null || true
    [ -n "$SOCAT_PID" ] && kill $SOCAT_PID 2>/dev/null || true
    [ -n "$CHROMIUM_PID" ] && kill $CHROMIUM_PID 2>/dev/null || true
    kill $XVFB_PID 2>/dev/null || true
    gosu sandbox tmux kill-server 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# 保持容器运行，监控进程
while true; do
    if ! kill -0 $XVFB_PID 2>/dev/null; then
        echo "ERROR: Xvfb died, exiting..."
        exit 1
    fi
    if ! kill -0 $AGENT_PID 2>/dev/null; then
        echo "ERROR: Agent server died, exiting..."
        exit 1
    fi
    sleep 10
done
