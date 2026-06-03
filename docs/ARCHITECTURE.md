# NewArch 系统架构

## 概述

NewArch 是一个微服务架构的 AI Agent 平台，AI 在隔离的沙箱容器（Debian + Xfce 桌面）中操作，用户通过 VNC 实时观看。平台使用 LangGraph 实现多 Agent 工作流（Planner -> Executor -> Reviewer），支持 GUI 模式（pyautogui）和 Code 模式（VSCode Server）。

## 服务架构

### 服务端口

| 服务 | 端口 | 语言 | 职责 |
|------|------|------|------|
| Frontend | 3000 | React/TS | 用户界面 |
| Gateway | 8080 | Go/Gin | API 网关、路径重写、SSE 代理 |
| Auth | 8081 | Go/Gin | JWT 认证 |
| Memory | 8082 | Go/Gin | 语义记忆、向量搜索 |
| Index | 8083 | Go/Gin | 索引管理 |
| Browser | 8084 | Python/FastAPI | 浏览器自动化（Playwright） |
| Task | 8085 | Go/Gin | 任务管理 |
| AI | 8086 | Python/FastAPI | LLM 集成、沙箱编排 |
| Worker Manager | 9000 | Go/Gin | 沙箱生命周期、Docker SDK |

### 网络区域

```
┌─────────────────────────────────────────────────────────┐
│  public (newarch_public)                                │
│    Frontend, Gateway - 暴露到宿主机                      │
├─────────────────────────────────────────────────────────┤
│  internal (newarch_internal)                            │
│    所有微服务 - 与公网隔离                                │
├─────────────────────────────────────────────────────────┤
│  sandbox-isolated (newarch_sandbox-isolated)            │
│    Worker Manager + 动态沙箱容器                         │
└─────────────────────────────────────────────────────────┘
```

### 数据流

```
User -> Frontend -> Gateway -> AI Service -> Worker Manager -> Sandbox Agent
                                  |
                            LLM (Doubao/DeepSeek)
                                  |
                            分析截图 -> 决定工具/动作
                                  |
User <- VNC stream <------------- Sandbox (Xfce desktop + pyautogui/bash)
```

## Gateway 路由

Gateway 将 `/api/v1/{service}/...` 重写为 `/{service}/...` 后代理：
- `/api/v1/ai/sandbox/chat/stream` -> `http://ai-service:8086/sandbox/chat/stream`
- SSE 端点使用 `SSEProxy` 处理事件流
- 普通 HTTP 使用 `HTTPProxy` 带超时处理

关键文件：`gateway/internal/router/routes.go`

## 沙箱系统

### 端口池管理

Worker Manager 从固定范围分配端口：

| 服务 | 容器端口 | 宿主机端口范围 |
|------|---------|--------------|
| VNC | 5900 | 5901-5999 |
| noVNC | 6080 | 6081-6179 |
| VSCode | 3000 | 7001-7099 |
| Agent | 8000 | 动态高端口 |

最大并发沙箱数：99

### 沙箱生命周期

1. **创建**：Worker Manager 分配端口，创建 Docker 容器（Debian 基础镜像）
2. **初始化**：容器启动 Xvfb、x11vnc、websockify、VSCode Server、Agent Server
3. **保活**：前端每 30s 发送 keepalive 防止空闲超时
4. **销毁**：Worker Manager 停止容器，释放端口回端口池

### VNC 连接

- 使用 `vnc_lite.html`（非 vnc.html，避免 JS 错误）
- URL 格式：`http://localhost:6081/vnc_lite.html?autoconnect=true&scale=true`
- noVNC 从容器内 `/usr/share/novnc/` 提供服务
- websockify 代理 WebSocket 到 x11vnc 的 5900 端口

### 工具执行链

```
Frontend -> Gateway -> AI Service -> Worker Manager -> Sandbox Agent
                                                          |
                                                    执行工具 (pyautogui/bash)
                                                          |
SSE Stream <------------------------------------------  返回结果
```

AI Service 根据 LLM 响应决定调用哪些工具。工具定义在 `SANDBOX_TOOLS` 中，使用 JSON Schema 进行函数调用。

## LangGraph 多 Agent 工作流

### 工作流程

1. **Planner**：分析任务，创建分步计划
2. **Executor**：执行每一步，调用工具，更新状态
3. **Reviewer**：审查结果，决定任务是否完成或需要重试
4. 基于状态的条件路由（continue -> executor, complete -> end）

### 状态管理

- 状态在对话期间保持在内存中
- 每条消息创建新的状态快照
- 状态包含：plan, current_step, execution_results, review_feedback

关键文件：
- `services/ai-service/src/core/langgraph/state.py` - AgentState
- `services/ai-service/src/core/langgraph/nodes.py` - 节点函数
- `services/ai-service/src/core/langgraph/graph.py` - StateGraph 构建

## 双模式路由

### 操作模式

- `gui` - VNC 查看，pyautogui 操作（click, type, scroll, screenshot）
- `code` - VSCode 编辑，Shell 命令执行（bash, file operations）
- `auto` - LLM 分析任务并根据关键词决定模式

### 模式检测关键词

- GUI 模式："click", "open browser", "screenshot", "desktop", "window"
- Code 模式："edit file", "write code", "terminal", "bash", "git", "compile"

关键文件：`services/ai-service/src/core/mode_router.py`

## Skill 检索系统

### 两阶段检索

1. **Stage 1 召回**：BM25 关键词 + Milvus ANN 向量搜索 -> RRF 融合（top 20）
2. **Stage 2 精排**：LLM Cross-Encoder 打分（top 3-5）

### 组件

- `SkillSystemManager` - 全局单例管理器
- `SkillSystemFactory` - 组件创建和依赖注入
- `SkillStore` - 技能存储（Milvus + Embedding）
- `SkillRetrievalPipeline` - 两阶段检索管线
- `SkillSelector` - 对外接口

初始化在 `main.py` 的 startup 事件中完成。

## 项目目录结构

```
NewArch/
├── docker-compose.yml              # 主编排文件
├── frontend/                       # React + Vite 前端
│   └── src/components/AIWorkspace.tsx  # 主工作区
├── gateway/                        # Go API 网关
│   └── internal/router/routes.go   # 路由定义
├── services/
│   ├── auth-service/               # Go 认证服务
│   ├── ai-service/                 # Python AI 服务
│   │   └── src/
│   │       ├── main.py             # 应用入口 + Skill 初始化
│   │       ├── api/
│   │       │   ├── sandbox_routes.py       # 基础沙箱路由
│   │       │   └── smart_sandbox_routes.py # 智能路由（标准/LangGraph/双模式）
│   │       ├── core/
│   │       │   ├── sandbox.py      # SANDBOX_TOOLS 定义
│   │       │   ├── langgraph/      # LangGraph 多 Agent
│   │       │   ├── mode_router.py  # 双模式路由
│   │       │   ├── model_router.py # 模型选择路由
│   │       │   └── skill/          # Skill 检索系统
│   │       │       ├── manager.py  # SkillSystemManager
│   │       │       ├── factory.py  # SkillSystemFactory
│   │       │       ├── config.py   # SkillSystemConfig
│   │       │       ├── store.py    # SkillStore
│   │       │       ├── reranker.py # 两阶段检索管线
│   │       │       ├── selector.py # SkillSelector
│   │       │       └── milvus_client.py # Milvus 客户端
│   │       └── config/settings.py  # 配置
│   ├── worker-service/             # Go Worker Manager
│   │   ├── cmd/worker/main.go      # 入口（必须包含 VSCode 端口配置）
│   │   └── internal/sandbox/manager.go # 容器管理
│   ├── memory-service/             # Go 语义记忆
│   ├── browser-service/            # Python 浏览器自动化
│   └── task-service/               # Go 任务管理
├── sandbox/                        # 沙箱镜像
│   ├── Dockerfile                  # Debian 12 + Xfce + VNC + VSCode
│   ├── entrypoint.sh               # 启动脚本
│   └── tools/
│       ├── agent_server.py         # FastAPI 工具服务
│       └── bash_session.py         # tmux 持久化 Shell
├── infrastructure/docker/postgres/init.sql  # 数据库 Schema
├── scripts/
│   ├── build-sandbox.sh            # 构建沙箱镜像
│   ├── start-all.sh                # 构建 + 启动所有服务
│   └── verify-upgrade.sh           # 验证架构升级
└── docs/                           # 文档
```

## 安全设计

### 网络隔离

- Public Zone -> Internal Zone：仅 Gateway 可访问内部服务
- Internal Zone -> Sandbox Zone：仅 AI Service 和 Worker Manager 可访问沙箱
- Sandbox 之间完全隔离，禁止互相访问

### 沙箱安全

- 容器 capabilities 降权（drop ALL, add SYS_CHROOT/SETUID/SETGID）
- 资源限制：CPU 1核、内存 2GB、进程数 256、磁盘 5GB
- no-new-privileges 启用
- seccomp 默认配置

### JWT 认证

- 所有 API 请求需要 JWT（健康检查除外）
- Gateway 验证 JWT 后代理到下游服务
- Auth Service 负责签发 JWT

## 部署架构

### 单机开发部署（Docker Compose）

所有服务 + 数据库在同一台机器上运行，沙箱容器动态创建。

### 双服务器生产部署

- Server 1（Core）：前端、网关、微服务、数据库
- Server 2（Worker）：Worker Manager + 沙箱容器（推荐 16+ CPU, 64GB+ RAM）

## 技术栈

- **Go 服务**：Gin, GORM, Docker SDK
- **Python 服务**：FastAPI, OpenAI SDK, httpx, LangGraph, pyautogui
- **前端**：React 18, TypeScript, Vite, Tailwind CSS, Zustand
- **数据库**：PostgreSQL, Redis, Milvus
- **沙箱**：Debian 12 + Xfce + x11vnc + noVNC + OpenVSCode Server + Chromium + tmux

**为什么用 Debian 而非 Ubuntu**：Ubuntu 22.04 的 Chromium 是 snap 包装器，在 Docker 中无法工作。Debian 12 提供原生 Chromium 包。
