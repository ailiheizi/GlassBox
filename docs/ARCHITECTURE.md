# GlassBox 系统架构

> 本文档依据当前代码（`docker-compose.yml`、`sandbox/Dockerfile`、`sandbox/entrypoint.sh`、`services/worker-service/**`、`gateway/**`、`frontend/**`）重写。
> 项目历史名为 NewArch，镜像名 / 容器名 / Go module 仍沿用 `newarch-*` 与 `github.com/newarch/*` 前缀。
> 沙箱观看链路为 **Xvfb + Chromium CDP Screencast**，容器内**没有桌面环境、没有 VNC / noVNC、没有 VSCode Server**。
> 项目定位是**工程原型**，不是生产就绪系统。已知限制见文末。

## 概述

GlassBox 是一个微服务架构的 AI Agent 平台：AI 在隔离的沙箱容器中执行 Shell、文件与浏览器操作，浏览器画面通过 Chromium CDP `Page.startScreencast` 以 WebSocket 帧流推送到前端 Canvas 渲染。

## 服务清单

9 个应用服务 + 3 个数据组件（另有 Milvus 依赖的 etcd / MinIO）。

| 服务 | 端口 | 语言/框架 | 职责 | 宿主端口发布 |
|------|------|-----------|------|--------------|
| Frontend | 3000 | React 18 + Vite + TS（nginx 提供静态文件） | 调试与工作空间界面 | 3000:3000 |
| Gateway | 8080 | Go / Gin | API 网关、路径重写、JWT 校验、SSE / WebSocket 代理 | 8080:8080 |
| Auth | 8081 | Go / Gin | 注册、登录、刷新、profile | 无（仅内部网络） |
| Memory | 8082 | Go / Gin | 语义记忆、记忆区域、聊天历史 | 无 |
| Index | 8083 | Go / Gin | 索引管理 | 无 |
| Browser | 8084 | Python / FastAPI | 浏览器会话与对话 | 无 |
| Task | 8085 | Go / Gin | 任务管理（同步 CRUD） | 无 |
| AI | 8086 | Python / FastAPI | LLM 编排、沙箱编排、Embedding、LangGraph 多 Agent | 无 |
| Worker Manager | 9000 | Go / Gin + Docker SDK | 沙箱生命周期、工具代理、CDP 信息与推流代理 | 9000:9000 |

| 数据组件 | 镜像 | 端口 | 宿主端口发布 |
|----------|------|------|--------------|
| PostgreSQL | `postgres:15-alpine` | 5432 | 5432:5432 |
| Redis | `redis:7-alpine`（`--appendonly yes`） | 6379 | 6379:6379 |
| Milvus | `milvusdb/milvus:v2.3.3`（standalone，依赖 etcd v3.5.5 + MinIO） | 19530 / 9091 | 19530:19530、9091:9091 |

`auth-service` / `memory-service` / `index-service` / `browser-service` / `task-service` / `ai-service` **未发布任何宿主端口**，只能通过 Gateway 或容器网络访问。

辅助组件：Langfuse（可选，`docker-compose` 之外由 `langfuse-compose.yml` 提供，`LANGFUSE_ENABLED=true` 时启用，Web 入口 http://localhost:3100）。

## 网络分区

三层 Docker 网络（`docker-compose.yml`）：

| 网络 | 驱动 | 说明 | 接入方 |
|------|------|------|--------|
| `public` | bridge | 对外暴露 | frontend、gateway、postgres、milvus |
| `internal` | bridge，`internal: true` | 服务间通信，与公网隔离 | 全部微服务 + postgres、redis、milvus 及其依赖 |
| `sandbox-isolated` | bridge（**未**开启 `internal`，以便宿主端口映射） | 沙箱执行层 | worker-manager、ai-service、browser-service、task-service + 动态创建的沙箱容器 |

沙箱容器只接入 `sandbox-isolated`（由 `SANDBOX_NETWORK=newarch_sandbox-isolated` 指定）。

```
public:            frontend(3000)   gateway(8080)   postgres(5432)   milvus(19530/9091)
internal(internal): 全部微服务 + postgres + redis + milvus(+etcd/minio)
sandbox-isolated:   worker-manager + ai-service + browser-service + task-service
                    + sandbox-<user>-<id>（动态）
```

## 沙箱执行层（无可视桌面）

镜像：`sandbox/Dockerfile`，基于 `debian:trixie`（Debian 13）。

启动流程（`sandbox/entrypoint.sh`，root 启动系统服务后 `gosu` 降权到非 root 用户 `sandbox`）：

1. `Xvfb :1 -screen 0 1280x720x24`（Chromium 非 headless 需要 DISPLAY）
2. `tmux start-server` + 预建 `default` 会话（工作目录 `/home/sandbox/workspace`）
3. Chromium 以 `--no-sandbox --remote-debugging-port=19222 about:blank` 启动；CDP 就绪轮询上限 15s（超时仅告警，不阻断启动）；随后 `socat` 将 `0.0.0.0:9222` 转发到 `127.0.0.1:19222`（Chromium 忽略 `--remote-debugging-address`），供同网络其它容器访问
4. `uvicorn agent_server:app` 在容器内 `:8000` 暴露 Agent HTTP/WebSocket 服务

容器内**不安装**：桌面环境、VNC 服务端、noVNC/websockify、OpenVSCode Server、pyautogui、xdotool/scrot。

沙箱内 Agent（`sandbox/tools/agent_server.py`）自身只实现两个执行工具 `shell`、`wait`；其余能力以 HTTP / WebSocket 端点提供：

| 端点 | 说明 |
|------|------|
| `GET /health`、`GET /tools` | 健康检查、工具清单 |
| `POST /execute` | 执行 `shell` / `wait` |
| `GET /screenshot` | 通过 CDP `Page.captureScreenshot` 截图（base64 JPEG） |
| `GET /cdp/info` | Chromium 版本与 CDP WebSocket URL |
| `WS /cdp/screencast/ws` | CDP Screencast 帧流（`Page.startScreencast` + `Page.screencastFrameAck`） |
| `GET/POST/DELETE /files/{list,read,write,delete,rename,mkdir}` | 文件管理，限制在 `/home/sandbox`、`/tmp` 内 |
| `POST /bash/execute`、`GET /bash/cwd`、`GET/POST /bash/env[/{key}]`、`GET /bash/sessions`、`DELETE /bash/session` | 基于 tmux 的持久化 Bash 会话（`sandbox/tools/bash_session.py`） |

## 观看链路（CDP Screencast）

前端（nginx）对 `/api/v1/ai/sandbox/screencast/` 单独配置了 WebSocket 反代到 Gateway（`frontend/nginx.conf`）。链路如下：

```
前端 /workspace → BrowserViewer
  ws(s)://<host>/api/v1/ai/sandbox/screencast/<user_id>/ws?quality=&maxWidth=&maxHeight=&token=
        │  （前端 nginx：/api/v1/ai/sandbox/screencast/ → http://gateway:8080/...，带 Upgrade 头）
        ▼
Gateway  GET /api/v1/ai/sandbox/screencast/:user_id/ws
  WSProxy：不经 JWT 中间件；从 ?token= 自校验 JWT，比对 claims.user_id 与路径 user_id（不一致返回 403），
  注入 X-User-ID 后按通用规则剥离 /api/v1/{service} 前缀
        │  重写后的上游路径：/sandbox/screencast/<user_id>/ws
        ▼
Worker Manager  ?（声明的是 /api/v1/tools/:user_id/screencast/ws，见下方「已知限制」）
        │
        ▼
沙箱 Agent  ws://<container>:8000/cdp/screencast/ws
        │
        ▼
Chromium CDP  Page.startScreencast → 帧 + Page.screencastFrameAck
```

`BrowserViewer` 的实际请求见 `frontend/src/components/BrowserViewer.tsx`：质量、尺寸作为查询参数，JWT 通过 `token` 查询参数传递。

### 前端直连服务（调试通道）

`frontend/nginx.conf` 还提供了 `/internal/<service>/` 反向代理（`/internal/gateway`、`/internal/auth`、`/internal/memory`、`/internal/index`、`/internal/browser`、`/internal/task`、`/internal/ai`），前端容器同时接入 `public` 与 `internal` 网络，因此调试页面（`ServiceDebugger`、`ContainerManager` 等）**绕过 Gateway 直接访问各服务**。这是隐藏的对外面：只要能访问 3000 端口就能触达全部内部服务。

## AI Agent 工作流

```
用户消息 → 前端 → Gateway POST /api/v1/ai/sandbox/chat/stream（SSE）
  → AI Service → Worker Manager 获取/创建沙箱
  → 工具调用（Shell / 文件 / CDP 截图 / browser-use 经 CDP 连接沙箱 Chromium）
  → 结果与实时画面（Screencast）返回前端
```

AI Service 暴露给模型的工具（`services/ai-service/src/core/sandbox.py` 的 `SANDBOX_TOOLS`）：

| 工具 | 说明 |
|------|------|
| `sandbox_shell` | 沙箱内执行 Shell 命令（默认超时 30s） |
| `sandbox_wait` | 等待指定秒数 |
| `sandbox_screenshot` | 经 Agent `/screenshot` 截图（CDP） |
| `sandbox_bash_execute` / `sandbox_bash_cwd` / `sandbox_bash_env` | tmux 持久化会话操作 |
| `sandbox_file_list` / `sandbox_file_read` / `sandbox_file_write` | 文件管理 |
| `sandbox_browser_use` | 通过 CDP 连接沙箱 Chromium，用 browser-use 执行浏览器任务 |

**模式路由已统一**：`services/ai-service/src/core/mode_router.py` 明确说明「去掉 GUI vs Code 双模式路由，统一为 browser-use + bash + 文件操作」，`ModeRouter.select_mode()` 恒定返回 `AUTO`，GUI / CODE 枚举仅为接口兼容保留。因此 **不存在** 基于关键词的「GUI 模式判定」（点击 / 输入 / 滚动 等），也不存在 pyautogui 坐标操作类工具。Gateway 仍保留 `/api/v1/ai/sandbox/smart/analyze-mode`、`/chat/dual-mode/stream` 等兼容端点。

## LangGraph 多 Agent 工作流

`services/ai-service/src/core/langgraph/`：

- 节点：`planner` → `executor` → `reviewer`，条件边决定继续 executor 还是结束（`graph.py`）
- 状态：`AgentState`（`state.py`），含计划、当前步骤、执行结果、评审反馈

## Skill 检索系统

`services/ai-service/src/core/skill/`：

- 两阶段检索：BM25 关键词 + Milvus 向量召回 → RRF 融合 → LLM 精排
- 组件：`SkillSystemManager` / `SkillSystemFactory` / `SkillStore` / 两阶段检索管线 / `SkillSelector`
- 内置技能定义在 `builtin_skills.py`（`open_browser`、`open_feishu`、`open_url`、`install_apt`、`install_pip`、`create_file`、`take_screenshot`，共 7 个）
- 启动时在 `main.py` 的 startup 事件初始化并写入 Milvus

## 模型路由

`services/ai-service/src/core/model_router.py` 按任务类别选择模型（`gui_operation` / `visual_analysis` / `code_generation` / `reasoning` / `general_chat`），支持关键词路由与 LLM 路由。这里的 `gui_operation` 是**任务类别标签**（由关键词触发，例如「点击 / 滚动 / 输入」），落到 `DOUBAO_GUI_MODEL`，与沙箱内是否安装桌面环境无关。详见 [MODEL_CONFIGURATION.md](./MODEL_CONFIGURATION.md)。

## 项目目录结构

```
GlassBox/
├── docker-compose.yml              # 主编排（9 服务 + 3 数据组件）
├── langfuse-compose.yml            # 可选可观测性栈
├── Taskfile.yml                    # 运维/开发命令
├── frontend/                       # React + Vite + TS
│   └── src/
│       ├── App.tsx                 # 路由（/、/workspace、/services、/api-tester、/ai-debug、/containers、/environments、/health）
│       ├── components/BrowserViewer.tsx   # CDP Screencast 渲染
│       ├── components/AIWorkspace.tsx     # AI 工作空间
│       ├── components/FileExplorer.tsx    # 沙箱文件管理
│       └── api/client.ts
├── gateway/                        # Go API 网关
│   └── internal/router/routes.go   # 路由定义
├── services/
│   ├── auth-service/               # Go 认证
│   ├── memory-service/             # Go 语义记忆
│   ├── index-service/              # Go 索引
│   ├── browser-service/            # Python 浏览器会话（Playwright）
│   ├── task-service/               # Go 任务
│   ├── ai-service/                 # Python AI 编排（src/{api,core,config}）
│   └── worker-service/             # Go Worker Manager
│       └── internal/sandbox/manager.go    # 沙箱容器创建与回收
├── sandbox/                        # 沙箱镜像
│   ├── Dockerfile                  # debian:trixie + Xvfb + Chromium + Agent
│   ├── entrypoint.sh               # 4 步启动（Xvfb / tmux / Chromium+socat / Agent）
│   └── tools/                      # agent_server.py、bash_session.py、requirements.txt
├── infrastructure/docker/postgres/ # init.sql + migrations
├── shared/proto/                   # protobuf 定义
├── tests/                          # unit / e2e
└── docs/                           # 文档
```

## 安全设计（按当前代码）

### 沙箱容器（`services/worker-service/internal/sandbox/manager.go`）

- `CapDrop: ALL`，显式回加 `SYS_CHROOT`、`SETUID`、`SETGID`、`CHOWN`、`DAC_OVERRIDE`、`FOWNER`
- `SecurityOpt: no-new-privileges:true`
- 资源限制：CPU 1 核（CPUQuota 100000）、内存 2GB、PIDs 512
- 容器内以非 root 用户 `sandbox` 运行（root 仅用于 Xvfb/tmux 启动，随后 `gosu` 降权）
- 根文件系统可写（`READ_ONLY_ROOT_FS` 默认 false）
- 端口：仅 `8000/tcp` 绑定宿主 `127.0.0.1` 的**随机端口**；CDP `9222` 不做宿主端口映射
- workspace 命名卷 `sandbox-<user 前 8 位>-<8 位随机 ID>-workspace:/home/sandbox/workspace` 持久化
- 容器标签：`newarch.sandbox=true`、`newarch.user_id`、`newarch.sandbox_id`；命名 `sandbox-<user 前 8 位>-<8 位随机 ID>`
- 容量与回收：最多 50 个沙箱（`MAX_SANDBOXES`）、空闲 30 分钟回收（`IDLE_TIMEOUT`）、清理协程每 5 分钟扫描一次、启动时按标签清理遗留孤儿容器

### 网络与通信

- 沙箱只接入 `sandbox-isolated`，无法直达 `internal` 中的服务
- Worker ↔ 沙箱 Agent 使用 `SANDBOX_SECRET` 做 HMAC-SHA256 请求/响应签名（时间戳偏差 ±5 分钟）
- 工具执行要求 `X-User-ID` 与路径 `user_id` 一致，并校验响应签名
- 文件 API 限制在 `/home/sandbox`、`/tmp`，单文件上限 5MB
- 所有 Gateway / Worker 端点需 JWT（`/health` 除外）；Screencast WebSocket 由 Gateway 自校验 `?token=` 并比对 user_id

### JWT

- Auth Service 签发；Gateway 中间件校验后代理到下游；Worker Manager 用同一 `JWT_SECRET` 校验

## 已知限制（以代码为准，勿当作已实现）

- **镜像白名单 `AllowedImages` 对用户沙箱路径不生效**：只在 worker 的通用容器/任务 API（`internal/docker/client.go`）中校验；用户沙箱由 `SANDBOX_IMAGE`（默认 `newarch-sandbox:latest`）直接创建，不走白名单
- `BlockedPorts`（`[22, 23, 3389]`）仅存在于配置结构，**没有任何代码引用，未生效**
- `gateway` 与 `worker-manager` 均挂载宿主 `/var/run/docker.sock`（高权限面）
- `JWT_SECRET`、`RESPONSE_SIGN_SECRET`、`SANDBOX_SECRET` 在 compose / 代码中存在默认弱值回退，部署前必须覆盖
- **Gateway 前缀剥离与下游路径存在多处不一致（未做端到端验证）**：详见下方「Gateway 路径映射」小节
- **异步任务 HTTP 接口未接通**：`services/task-service/internal/handler/async_task_handler.go` 已实现，但 `cmd/server/main.go` 只注册了同步 `/api/v1/tasks` 路由，未注册 `/tasks/async`；Gateway 侧却已声明 `/api/v1/tasks/async*` 转发。详见 [async-tasks-guide.md](./async-tasks-guide.md) 顶部说明
- **前端调试通道绕过鉴权**：`/internal/<service>/` 反代使 3000 端口可触达全部内部服务（见上文「前端直连服务」）

### Gateway 路径映射（未验证）

Gateway 代理统一剥掉 `/api/v1/{service}` 前缀后再转发（`gateway/internal/proxy/http_proxy.go`），因此只有「在根路径上挂载同名子路径」的服务能对上：

| Gateway 声明路径 | 剥离后的上游路径 | 下游服务实际注册路径 | 是否匹配 |
|------------------|------------------|----------------------|----------|
| `/api/v1/ai/sandbox/**` | `/sandbox/**` | ai-service `/sandbox/**` | 匹配 |
| `/api/v1/browser/chat`、`/sessions` | `/chat`、`/sessions` | browser-service `/chat`、`/sessions` | 匹配 |
| `/api/v1/ai/agent/chat` | `/agent/chat` | ai-service `/api/v1/agent/chat` | **不匹配** |
| `/api/v1/memory/*`、`/api/v1/indexes/*`、`/api/v1/tasks*`、`/api/v1/sessions*` | `/semantic`、`/ai`、`/tasks` … | memory `/api/v1/memories`、index `/api/v1/indexes`、task `/api/v1/tasks` | **不匹配** |
| `/api/v1/ai/sandbox/files/{user_id}/*` | `/sandbox/files/{user_id}/*` | worker `/api/v1/tools/{user_id}/files/*` | **不匹配** |
| `/api/v1/ai/sandbox/screencast/{user_id}/ws` | `/sandbox/screencast/{user_id}/ws` | worker `/api/v1/tools/{user_id}/screencast/ws` | **不匹配** |

表中「不匹配」仅表示**声明的路径**无法对应，是否另有补偿逻辑未验证；经 Gateway 调用这些接口前请自行确认。

## 技术栈

- **Go 服务**：Gin、GORM（auth / memory / index / task）、Docker SDK for Go（worker）
- **Python 服务**：FastAPI、Uvicorn、OpenAI SDK（豆包兼容）、httpx、LangGraph、browser-use（ai-service）、Playwright（browser-service）
- **前端**：React 18、TypeScript、Vite 5、Tailwind CSS、Zustand、react-router-dom 6、lucide-react、nginx（生产静态托管）
- **数据**：PostgreSQL 15、Redis 7、Milvus 2.3.3（+etcd、MinIO）
- **沙箱**：Debian 13 (trixie)、Xvfb、Chromium（Debian 原生包，非 snap）、socat、tmux、gosu、Python 3、Node.js/npm

**为什么用 Debian 而非 Ubuntu**：Ubuntu 的 Chromium 是 snap 包装器，在容器中不可用；Debian 提供原生 Chromium 包。

## 相关文档

- [快速开始](./GETTING_STARTED.md)
- [模型配置](./MODEL_CONFIGURATION.md)
- [数据库连接](./DATABASE_CONNECTIONS.md)
- [异步任务指南](./async-tasks-guide.md)（能力未接通，见文首说明）
- [Bash 工具最佳实践](./bash-tool-best-practices.md)
- [开源依赖](./OPEN_SOURCE_DEPENDENCIES.md)
- [沙箱瘦身历史记录](./SANDBOX_SLIM_HISTORY.md)
- [OpenAPI 规范](./api-spec/openapi.yaml)
