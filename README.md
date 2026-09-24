# GlassBox（历史名 NewArch）- 微服务架构 AI Agent 沙箱平台

[![Status](https://img.shields.io/badge/status-prototype-orange)]()
[![Version](https://img.shields.io/badge/version-0.1-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

一个微服务架构的 AI Agent 平台：AI 在隔离的沙箱容器中执行 Shell、文件与浏览器操作，浏览器画面通过 **Xvfb + Chromium CDP Screencast** 以 WebSocket 推流到前端实时观看。

> 沙箱内**没有桌面环境、没有 VNC / noVNC**：只有 Xvfb 虚拟显示 + Chromium，画面来自 CDP `Page.startScreencast` 帧。
>
> 项目更名后，代码中的镜像名、容器名与 Go module 仍沿用 `newarch-*` / `github.com/newarch/*` 前缀（历史命名）。

## ✨ 特性

- 🤖 **AI Agent 沙箱** - 每个用户一个独立容器（Debian 13 trixie + Xvfb + Chromium），非 root 用户运行
- 📺 **实时画面推流** - Chromium CDP Screencast 经 WebSocket 转发到前端 Canvas 渲染，无桌面环境、无 VNC
- 🏗️ **微服务架构** - 9 个应用服务 + 3 个数据组件（PostgreSQL / Redis / Milvus）
- 🔒 **安全隔离** - 三层 Docker 网络、Capability 白名单、no-new-privileges、CPU/内存/PID 限额、HMAC 签名通信
- 🐚 **持久化会话** - tmux 持久 Shell 会话 + workspace 命名卷，容器重启前工作区不丢失
- 🎨 **调试界面** - 工作空间、服务调试、API 测试、容器管理、服务健康等页面
- 🐳 **容器化部署** - Docker Compose + Taskfile 一键启动

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose v2（`docker compose`）
- [Task](https://taskfile.dev)（可选，用于 `task dev` 等命令）
- 本地开发另需：Go 1.21+、Python 3.11+、Node.js 18+

### 启动服务

```bash
# 克隆项目
git clone https://github.com/ailiheizi/GlassBox.git
cd GlassBox

# 配置环境变量（.env.example 中没有 SANDBOX_SECRET，需自行补上）
cp .env.example .env
#   必填：DOUBAO_API_KEY
#   建议覆盖：JWT_SECRET、SANDBOX_SECRET、HOST_ADDRESS

# 一键启动开发环境（构建沙箱镜像 + 基础设施 + 所有服务，含可选 Langfuse）
task dev

# 或只启动核心环境（不含 Langfuse）
task up

# 不用 Taskfile 时
docker build -t newarch-sandbox:latest ./sandbox
docker compose up -d
```

### 访问地址

- **前端界面**: http://localhost:3000
- **AI 工作空间**（CDP 实时画面）: http://localhost:3000/workspace
- **Gateway API**: http://localhost:8080
- **Worker Manager API**: http://localhost:9000
- **Langfuse（可选，`LANGFUSE_ENABLED=true`）**: http://localhost:3100

## 📦 系统架构

### 核心架构图

```
┌─────────────────────────────────────────────────────────────────┐
│              Public Zone (宿主端口发布 / public 网络)             │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (3000)   │   Gateway (8080)                          │
│  Worker Manager 的 9000 端口也发布到宿主（容器仅接入 internal /   │
│  sandbox-isolated 网络）                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Internal Zone (内部服务层, internal: true)        │
├─────────────────────────────────────────────────────────────────┤
│  Auth (8081) │ Memory (8082) │ Index (8083) │ Browser (8084)    │
│  Task (8085) │ AI (8086)     │ Worker Manager (9000)            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Zone (数据层)                            │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL (5432)  │  Redis (6379)  │  Milvus (19530)          │
│  (Milvus 依赖 etcd + MinIO，仅内部网络)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         Sandbox Isolated Zone (沙箱执行层, 动态创建容器)          │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐      │
│  │  Sandbox-1    │   │  Sandbox-2    │   │  Sandbox-N    │      │
│  │  Xvfb :1      │   │  Xvfb :1      │   │  Xvfb :1      │      │
│  │  Chromium CDP │   │  Chromium CDP │   │  Chromium CDP │      │
│  │  Agent :8000  │   │  Agent :8000  │   │  Agent :8000  │      │
│  └───────────────┘   └───────────────┘   └───────────────┘      │
│  宿主端口: 仅 127.0.0.1:<随机> → 8000（Agent）                   │
│  CDP 9222 不发布到宿主，仅容器网络内可访问                        │
└─────────────────────────────────────────────────────────────────┘
```

### 网络分区

| 网络 | 驱动 | 说明 | 接入方 |
|------|------|------|--------|
| `public` | bridge | 对外暴露 | frontend、gateway、postgres、milvus |
| `internal` | bridge（`internal: true`） | 服务间通信，与公网隔离 | 全部微服务 + 数据组件 |
| `sandbox-isolated` | bridge | 沙箱执行层（未开启 `internal`，以便 Agent 端口映射到宿主） | worker-manager、ai-service、browser-service、task-service + 动态沙箱容器 |

### 观看链路（CDP Screencast）

```
浏览器前端 (/workspace, BrowserViewer)
   │  WebSocket + token
   ▼
Gateway  /api/v1/ai/sandbox/screencast/:user_id/ws   (内部校验 JWT)
   ▼
Worker Manager  /api/v1/tools/:user_id/screencast/ws  (WebSocket 双向中继)
   ▼
沙箱 Agent  /cdp/screencast/ws  (FastAPI)
   ▼
Chromium CDP  Page.startScreencast → 帧数据 + Page.screencastFrameAck
```

### AI Agent 工作流程

```
用户消息 → 前端 → Gateway(/api/v1/ai/sandbox/chat/stream, SSE) → AI Service
   → Worker Manager 获取/创建沙箱 → CDP 截图 / Shell 执行 / browser-use(CDP)
   → 结果 + 实时画面（CDP Screencast）返回前端
```

## 🎯 主要功能

### 1. AI 工作空间（`/workspace`）

- **实时画面** - CDP Screencast 帧渲染（`BrowserViewer`，可调质量/尺寸）
- **AI 对话** - 与 AI 对话，由它操作沙箱
- **文件管理器** - 浏览/读写沙箱 `/home/sandbox`、`/tmp` 下的文件
- **持久 Shell** - 基于 tmux 的持久化 Bash 会话

### 2. AI 可用工具

AI Service 暴露给模型的工具（`services/ai-service/src/core/sandbox.py`）：

| 工具 | 描述 |
|------|------|
| `sandbox_shell` | 在沙箱中执行 Shell 命令（可设超时，默认 30s） |
| `sandbox_wait` | 等待指定时间 |
| `sandbox_screenshot` | 通过 CDP 截取当前浏览器画面（JPEG/base64） |
| `sandbox_bash_execute` / `sandbox_bash_cwd` / `sandbox_bash_env` | tmux 持久化 Bash 会话操作 |
| `sandbox_file_list` / `sandbox_file_read` / `sandbox_file_write` | 沙箱文件管理 |
| `sandbox_browser_use` | 通过 CDP 连接沙箱 Chromium 执行浏览器任务（browser-use） |

沙箱内 Agent（`sandbox/tools/agent_server.py`）自身只实现两个执行工具 `shell`、`wait`，其余能力通过 `/screenshot`、`/files/*`、`/bash/*`、`/cdp/*` 端点提供。

### 3. 微服务职责

| 服务 | 端口 | 技术栈 | 职责 |
|------|------|--------|------|
| Frontend | 3000 | React + TypeScript | 用户界面与调试页面 |
| Gateway | 8080 | Go / Gin | API 网关、路径重写、JWT 校验、SSE / WebSocket 代理 |
| Auth | 8081 | Go / Gin | 用户注册登录、JWT 签发 |
| Memory | 8082 | Go / Gin | 语义记忆、向量检索、聊天历史 |
| Index | 8083 | Go / Gin | 索引管理 |
| Browser | 8084 | Python / FastAPI | 浏览器会话与对话服务 |
| Task | 8085 | Go / Gin | 任务、异步任务与会话管理 |
| AI | 8086 | Python / FastAPI | LLM 编排、沙箱编排、Embedding、多 Agent（LangGraph） |
| Worker Manager | 9000 | Go / Gin | 沙箱生命周期（Docker SDK）、工具代理、CDP 信息与推流代理 |

数据组件：PostgreSQL 15（5432）、Redis 7（6379）、Milvus 2.3.3（19530，附带 etcd 与 MinIO，仅内部网络）。

### 4. 前端页面

`/`（Dashboard）、`/workspace`（AI 工作空间）、`/services`、`/api-tester`、`/ai-debug`、`/containers`、`/environments`、`/health`。

## 📖 文档

- [系统架构](docs/ARCHITECTURE.md)
- [快速开始](docs/GETTING_STARTED.md)
- [沙箱瘦身历史记录](docs/SANDBOX_SLIM_HISTORY.md)（历史存档：旧桌面/远程桌面方案已废弃）
- [异步任务指南](docs/async-tasks-guide.md)（**注意**：handler 已实现但 task-service 未注册路由，接口当前不可用，详见文首说明）
- [Bash 工具最佳实践](docs/bash-tool-best-practices.md)
- [模型配置](docs/MODEL_CONFIGURATION.md)
- [数据库连接](docs/DATABASE_CONNECTIONS.md)
- [开源依赖](docs/OPEN_SOURCE_DEPENDENCIES.md)
- [OpenAPI 规范](docs/api-spec/openapi.yaml)

## 🛠️ 运维命令（Taskfile）

```bash
task              # 列出所有命令
task dev          # 启动开发环境（含 Langfuse，若已启用）
task up           # 启动所有服务（不含 Langfuse）
task down         # 停止所有服务
task restart -- ai-service   # 重建并重启指定服务
task logs -- worker-manager  # 查看指定服务日志
task status       # 查看容器状态
task build        # 构建所有镜像（含沙箱）
task build:sandbox
task test         # Go + Python 测试
task fmt / task lint
task clean        # 删除所有数据卷（不可恢复）
```

## 🔧 开发

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 后端（Go）

```bash
cd services/worker-service
go mod download
go run cmd/worker/main.go
```

### 后端（Python）

```bash
cd services/ai-service
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

### 沙箱

```bash
# 构建沙箱镜像
task build:sandbox        # 等价于 docker build -t newarch-sandbox:latest ./sandbox

# 本地单独运行（Agent 端口映射到宿主 127.0.0.1）
docker run -d --name test-sandbox \
  -e USER_ID=demo \
  -p 127.0.0.1:8001:8000 \
  newarch-sandbox:latest

curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/tools

# CDP 9222 默认不发布到宿主机，仅在容器网络内可访问；
# 如确需在宿主调试，需自行追加 -p 127.0.0.1:9222:9222
```

## 📊 API 端点

所有 Gateway / Worker 端点均需 JWT（`/health` 除外）；沙箱 Agent 端点仅在容器网络内可达。

### Gateway（`http://localhost:8080/api/v1/...`）

```bash
POST   /auth/register | /auth/login | /auth/refresh        # 无需认证
GET    /auth/profile

POST   /ai/sandbox/create/{user_id}
GET    /ai/sandbox/info/{user_id}
DELETE /ai/sandbox/destroy/{user_id}
POST   /ai/sandbox/keepalive/{user_id}
GET    /ai/sandbox/screenshot/{user_id}
POST   /ai/sandbox/chat
POST   /ai/sandbox/chat/stream          # SSE 流式
POST   /ai/sandbox/execute/{user_id}?tool=shell

GET    /ai/sandbox/files/{user_id}/list | read
POST   /ai/sandbox/files/{user_id}/write | rename | mkdir
DELETE /ai/sandbox/files/{user_id}/delete

GET    /ai/sandbox/screencast/{user_id}/ws   # CDP Screencast WebSocket

# 其余：/tasks, /tasks/async, /sessions, /memory, /indexes, /browser, /admin/containers
```

### Worker Manager（`http://localhost:9000/api/v1/...`）

```bash
GET    /api/v1/sandboxes                  # 列出沙箱
POST   /api/v1/sandboxes                  # {"user_id": "..."}
POST   /api/v1/sandboxes/get-or-create
GET    /api/v1/sandboxes/metrics
GET    /api/v1/sandboxes/{user_id}
DELETE /api/v1/sandboxes/{user_id}
POST   /api/v1/sandboxes/{user_id}/keepalive

POST   /api/v1/tools/{user_id}/execute    # {"tool": "shell", "params": {...}}
GET    /api/v1/tools/{user_id}/screenshot
GET    /api/v1/tools/{user_id}/list | health | cdp-info
POST   /api/v1/tools/{user_id}/bash/execute
GET    /api/v1/tools/{user_id}/bash/cwd | sessions
POST   /api/v1/tools/{user_id}/bash/env
DELETE /api/v1/tools/{user_id}/bash/session
GET    /api/v1/tools/{user_id}/screencast/ws   # WebSocket 中继
GET    /api/v1/containers, /api/v1/tasks, /api/v1/metrics
```

### 沙箱 Agent（容器内 `:8000`）

`/health`、`/screenshot`、`/execute`、`/tools`、`/cdp/info`、`/cdp/screencast/ws`（WebSocket）、`/files/{list,read,write,delete,rename,mkdir}`、`/bash/{execute,cwd,env,sessions,session}`。

## 🔒 安全特性（按当前代码）

**沙箱容器**（`services/worker-service/internal/sandbox/manager.go`）

- `CapDrop: ALL`，再显式回加：`SYS_CHROOT`、`SETUID`、`SETGID`、`CHOWN`、`DAC_OVERRIDE`、`FOWNER`
- `SecurityOpt: no-new-privileges:true`
- 资源限制：CPU 1 核（CPUQuota 100000）、内存 2GB、PIDs 512
- 容器内以非 root 用户 `sandbox` 运行；root 仅用于启动 Xvfb / tmux，随后用 `gosu` 降权
- 根文件系统**可写**（`ReadOnlyRootFS` 默认 false）
- 仅 `8000/tcp` 绑定到宿主 `127.0.0.1` 的**随机端口**；CDP `9222` 不做宿主端口映射
- workspace 使用命名卷持久化，容器销毁后卷保留

**网络与通信**

- 三层网络：`public` / `internal`(internal: true) / `sandbox-isolated`；沙箱只接入 `sandbox-isolated`
- Worker ↔ 沙箱 Agent 使用 `SANDBOX_SECRET` 做 HMAC-SHA256 请求/响应签名，时间戳偏差 ±5 分钟
- 工具执行要求 `X-User-ID` 与路径中的 `user_id` 一致，并校验响应签名
- 沙箱文件 API 限制在 `/home/sandbox`、`/tmp` 内，单文件上限 5MB
- 空闲 30 分钟自动回收（清理协程每 5 分钟扫描），单机最多 50 个沙箱，启动时清理遗留孤儿容器

**已知限制（如实说明，勿据此当作已实现）**

- **镜像白名单 `AllowedImages` 对用户沙箱路径不生效**：它只在 worker 的通用容器/任务 API（`internal/docker/client.go`）中校验；用户沙箱由 `SANDBOX_IMAGE`（默认 `newarch-sandbox:latest`）直接创建，不走白名单
- `BlockedPorts`（`[22, 23, 3389]`）当前仅存在于配置结构中，**没有任何代码引用，未生效**
- `gateway` 与 `worker-manager` 均挂载宿主 `/var/run/docker.sock`，属于高权限面
- `docker-compose.yml` 中 `JWT_SECRET`、`RESPONSE_SIGN_SECRET` 存在默认弱值回退，生产部署必须覆盖

## 📈 运行参数（代码默认值）

- 沙箱基础镜像：`debian:trixie`，Xvfb 分辨率 `1280x720x24`（`DISPLAY=:1`）
- 沙箱资源：1 CPU / 2GB RAM / 512 PIDs；最多 50 个沙箱；空闲超时 30 分钟
- 沙箱 Agent 端口 8000（宿主 `127.0.0.1` 随机端口）；CDP 9222 仅容器网络内可达
- Chromium CDP 就绪等待上限 15s（超时仅告警，容器继续启动）
- worker-manager 自身资源上限：2 CPU / 4GB
- 沙箱容器命名：`sandbox-<user_id 前 8 位>-<8 位随机 ID>`

## 🐛 故障排查

### 沙箱无法启动

```bash
# 检查沙箱镜像
docker images | grep newarch-sandbox
task build:sandbox

# 检查 Worker Manager 日志
docker logs newarch-worker-manager
```

### 画面不刷新 / Screencast 连接失败

```bash
# 确认沙箱在运行（需 JWT）
curl -H "Authorization: Bearer <token>" http://localhost:9000/api/v1/sandboxes

# 查看沙箱容器日志（容器名形如 sandbox-<user>-<id>）
docker logs sandbox-{user_id}-{sandbox_id}

# 在沙箱内确认 Chromium CDP 是否存活
docker exec <container> curl -s http://127.0.0.1:19222/json/version
```

常见原因：前端 WebSocket 未携带有效 token；Chromium 启动失败（Agent 日志会出现 `Chromium CDP failed to start`）；`about:blank` 空白页帧率低属正常现象。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。当前为原型阶段，接口与部署方式可能变动。

## 📄 许可证

MIT License（README 声明；仓库当前未包含 LICENSE 文件）。

---

**项目状态**: 🚧 工程原型（prototype）— 提交历史很短、暂无 CI 流水线，尚未达到生产可用标准
**版本**: v0.1
**最后更新**: 2026-09-24

---

**Built with Go, Python, React, Docker, Xvfb and Chromium CDP**
