# 开源依赖说明

本文档列出 GlassBox（历史名 NewArch）项目使用的开源组件及其许可证信息。

> 依据：各服务的 `requirements.txt` / `pyproject.toml`、`go.mod`、`docker-compose.yml`、各 `Dockerfile`。
> 沙箱内 Debian 系统包数量较多且随基础镜像变动，**未逐一核对**，相关行已标注；如需精确清单请在镜像内执行 `dpkg -l` 并查阅 `/usr/share/doc/*/copyright`。

---

## 目录

- [前端依赖](#前端依赖)
- [Python 服务依赖](#python-服务依赖)
- [Go 服务依赖](#go-服务依赖)
- [基础设施与容器镜像](#基础设施与容器镜像)
- [沙箱系统组件](#沙箱系统组件)
- [许可证合规说明](#许可证合规说明)

---

## 前端依赖

使用服务：Frontend（React + Vite + TypeScript）

### 运行时依赖

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [React](https://github.com/facebook/react) | ^18.2.0 | MIT | UI 框架 |
| [React DOM](https://github.com/facebook/react) | ^18.2.0 | MIT | React DOM 渲染 |
| [React Router DOM](https://github.com/remix-run/react-router) | ^6.20.0 | MIT | 前端路由 |
| [Zustand](https://github.com/pmndrs/zustand) | ^4.4.7 | MIT | 状态管理 |
| [Lucide React](https://github.com/lucide-icons/lucide) | ^0.294.0 | ISC | 图标库 |
| [clsx](https://github.com/lukeed/clsx) | ^2.0.0 | MIT | CSS 类名拼接 |
| [tailwind-merge](https://github.com/dcastil/tailwind-merge) | ^2.1.0 | MIT | Tailwind 类名合并 |

### 开发依赖

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Vite](https://github.com/vitejs/vite) | ^5.0.0 | MIT | 构建工具 |
| [TypeScript](https://github.com/microsoft/TypeScript) | ^5.2.2 | Apache-2.0 | 类型系统 |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) | ^3.3.5 | MIT | CSS 框架 |
| [PostCSS](https://github.com/postcss/postcss) | ^8.4.31 | MIT | CSS 转换工具 |
| [Autoprefixer](https://github.com/postcss/autoprefixer) | ^10.4.16 | MIT | CSS 前缀自动补全 |
| [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react) | ^4.2.0 | MIT | Vite React 插件 |
| @types/react | ^18.2.37 | MIT | React 类型定义 |
| @types/react-dom | ^18.2.15 | MIT | React DOM 类型定义 |

---

## Python 服务依赖

### AI Service（`services/ai-service`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [FastAPI](https://github.com/tiangolo/fastapi) | 0.109.0 | MIT | Web 框架 |
| [Uvicorn](https://github.com/encode/uvicorn) | 0.27.0 | BSD-3-Clause | ASGI 服务器 |
| [Pydantic](https://github.com/pydantic/pydantic) | 2.5.3 | MIT | 数据验证 |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 2.1.0 | MIT | 配置管理 |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | 1.12.0 | Apache-2.0 | LLM API 客户端 |
| [httpx](https://github.com/encode/httpx) | 0.26.0 | BSD-3-Clause | HTTP 客户端 |
| [Pillow](https://github.com/python-pillow/Pillow) | 10.2.0 | HPND | 图像处理 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.0.0 | BSD-3-Clause | 环境变量加载 |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.6 | Apache-2.0 | 表单解析 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | >=0.2.0 | MIT | 多 Agent 编排 |
| [Langfuse](https://github.com/langfuse/langfuse-python) | >=2.50.0 | MIT | LLM 可观测性 |
| [browser-use](https://github.com/browser-use/browser-use) | >=0.11.0,<1.0.0 | MIT | 基于 DOM 的浏览器自动化（经 CDP 连接沙箱 Chromium） |
| [pymilvus](https://github.com/milvus-io/pymilvus) | 未固定 | Apache-2.0 | Milvus 向量数据库客户端（**代码引用，`requirements.txt` 未声明**） |
| [PyJWT](https://github.com/jpadilla/pyjwt) | 未固定 | MIT | JWT 认证（**代码引用，`requirements.txt` 未声明**） |
| [rank-bm25](https://github.com/dorianbrown/rank_bm25) | 未固定 | Apache-2.0 | BM25 文本检索（**代码引用，`requirements.txt` 未声明**） |

> AI Service 的声明文件是 `services/ai-service/requirements.txt`。上表中标记「未声明」的包在源码中被 import，但未写入该文件，属于依赖声明缺口。
> 历史条目 `volcengine-python-sdk` 在当前代码中既无引用也无声明，已移除。

### Browser Service（`services/browser-service`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [FastAPI](https://github.com/tiangolo/fastapi) | 0.109.0 | MIT | Web 框架 |
| [Uvicorn](https://github.com/encode/uvicorn) | 0.27.0 | BSD-3-Clause | ASGI 服务器 |
| [Playwright](https://github.com/microsoft/playwright-python) | 1.41.0 | Apache-2.0 | 浏览器自动化 |
| [Pydantic](https://github.com/pydantic/pydantic) | 2.5.3 | MIT | 数据验证 |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 2.1.0 | MIT | 配置管理 |
| [httpx](https://github.com/encode/httpx) | 0.26.0 | BSD-3-Clause | HTTP 客户端 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.0.0 | BSD-3-Clause | 环境变量加载 |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.6 | Apache-2.0 | 表单解析 |

### Sandbox Agent（`sandbox/tools`）

声明文件：`sandbox/tools/requirements.txt`。

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [FastAPI](https://github.com/tiangolo/fastapi) | >=0.109.0 | MIT | Agent 工具执行 / 文件 / CDP API |
| [Uvicorn](https://github.com/encode/uvicorn) | >=0.27.0 | BSD-3-Clause | ASGI 服务器 |
| [Pydantic](https://github.com/pydantic/pydantic) | >=2.5.3 | MIT | 数据验证 |
| [httpx](https://github.com/encode/httpx) | >=0.26.0 | BSD-3-Clause | HTTP 客户端（调用 Chromium CDP HTTP 端点） |
| [python-multipart](https://github.com/Kludex/python-multipart) | >=0.0.6 | Apache-2.0 | 表单解析 |
| [websockets](https://github.com/python-websockets/websockets) | >=12.0 | BSD-3-Clause | CDP Screencast WebSocket 客户端 |

历史条目（PyAutoGUI、python-xlib、Pillow）已随沙箱瘦身移除，当前不存在于沙箱依赖中。

### 测试依赖

声明文件：`services/ai-service/pyproject.toml`、`services/browser-service/pyproject.toml`。

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [pytest](https://github.com/pytest-dev/pytest) | >=7.4.0 | MIT | 测试框架 |
| [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | >=0.23.0 | Apache-2.0 | 异步测试支持 |

---

## Go 服务依赖

### Gateway（`gateway`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Gin](https://github.com/gin-gonic/gin) | v1.9.1 | MIT | Web 框架 |
| [golang-jwt](https://github.com/golang-jwt/jwt) | v5.2.0 | MIT | JWT 认证 |
| [google/uuid](https://github.com/google/uuid) | v1.5.0 | BSD-3-Clause | UUID 生成 |
| [godotenv](https://github.com/joho/godotenv) | v1.5.1 | MIT | 环境变量加载 |
| [golang.org/x/time](https://pkg.go.dev/golang.org/x/time) | v0.5.0 | BSD-3-Clause | 限流器 |

### Auth Service（`services/auth-service`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Gin](https://github.com/gin-gonic/gin) | v1.9.1 | MIT | Web 框架 |
| [golang-jwt](https://github.com/golang-jwt/jwt) | v5.2.0 | MIT | JWT 认证 |
| [google/uuid](https://github.com/google/uuid) | v1.6.0 | BSD-3-Clause | UUID 生成 |
| [godotenv](https://github.com/joho/godotenv) | v1.5.1 | MIT | 环境变量加载 |
| [golang.org/x/crypto](https://pkg.go.dev/golang.org/x/crypto) | v0.44.0 | BSD-3-Clause | 密码哈希 |
| [GORM](https://github.com/go-gorm/gorm) | v1.25.5 | MIT | ORM 框架 |
| [gorm/driver/postgres](https://github.com/go-gorm/postgres) | v1.5.4 | MIT | PostgreSQL 驱动 |
| [gRPC-Go](https://github.com/grpc/grpc-go) | v1.78.0 | Apache-2.0 | RPC 框架 |

### Memory Service（`services/memory-service`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Gin](https://github.com/gin-gonic/gin) | v1.9.1 | MIT | Web 框架 |
| [google/uuid](https://github.com/google/uuid) | v1.5.0 | BSD-3-Clause | UUID 生成 |
| [milvus-sdk-go](https://github.com/milvus-io/milvus-sdk-go) | v2.3.3 | Apache-2.0 | Milvus 客户端 |
| [GORM](https://github.com/go-gorm/gorm) | v1.25.5 | MIT | ORM 框架 |
| [gorm/driver/postgres](https://github.com/go-gorm/postgres) | v1.5.4 | MIT | PostgreSQL 驱动 |
| [gRPC-Go](https://github.com/grpc/grpc-go) | v1.48.0 | Apache-2.0 | RPC 框架 |

### Task Service（`services/task-service`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Gin](https://github.com/gin-gonic/gin) | v1.9.1 | MIT | Web 框架 |
| [google/uuid](https://github.com/google/uuid) | v1.5.0 | BSD-3-Clause | UUID 生成 |
| [godotenv](https://github.com/joho/godotenv) | v1.5.1 | MIT | 环境变量加载 |
| [GORM](https://github.com/go-gorm/gorm) | v1.25.5 | MIT | ORM 框架 |
| [gorm/driver/postgres](https://github.com/go-gorm/postgres) | v1.5.4 | MIT | PostgreSQL 驱动 |

### Index Service（`services/index-service`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Gin](https://github.com/gin-gonic/gin) | v1.9.1 | MIT | Web 框架 |
| [google/uuid](https://github.com/google/uuid) | v1.5.0 | BSD-3-Clause | UUID 生成 |
| [godotenv](https://github.com/joho/godotenv) | v1.5.1 | MIT | 环境变量加载 |
| [GORM](https://github.com/go-gorm/gorm) | v1.25.5 | MIT | ORM 框架 |
| [gorm/driver/postgres](https://github.com/go-gorm/postgres) | v1.5.4 | MIT | PostgreSQL 驱动 |

### Worker Service（`services/worker-service`）

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Gin](https://github.com/gin-gonic/gin) | v1.9.1 | MIT | Web 框架 |
| [golang-jwt](https://github.com/golang-jwt/jwt) | v5.2.0 | MIT | JWT 认证 |
| [google/uuid](https://github.com/google/uuid) | v1.6.0 | BSD-3-Clause | UUID 生成 |
| [Docker SDK for Go](https://github.com/moby/moby) | v27.4.1 | Apache-2.0 | 容器管理 |
| [docker/go-connections](https://github.com/docker/go-connections) | v0.4.0 | Apache-2.0 | Docker 网络工具 |

### Go 间接依赖（跨服务共用）

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [bytedance/sonic](https://github.com/bytedance/sonic) | Apache-2.0 | 高性能 JSON 编解码 |
| [gin-contrib/sse](https://github.com/gin-contrib/sse) | MIT | SSE 支持 |
| [go-playground/validator](https://github.com/go-playground/validator) | MIT | 参数校验 |
| [google.golang.org/protobuf](https://github.com/protocolbuffers/protobuf-go) | BSD-3-Clause | Protocol Buffers |
| [OpenTelemetry Go](https://github.com/open-telemetry/opentelemetry-go) | Apache-2.0 | 可观测性 |
| [opencontainers/image-spec](https://github.com/opencontainers/image-spec) | Apache-2.0 | OCI 镜像规范 |
| [opencontainers/go-digest](https://github.com/opencontainers/go-digest) | Apache-2.0 | 内容寻址摘要 |
| [jackc/pgx](https://github.com/jackc/pgx) | MIT | PostgreSQL 驱动（底层） |

---

## 基础设施与容器镜像

### 数据库与缓存

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [PostgreSQL](https://www.postgresql.org/) | 15-alpine | PostgreSQL License (类 BSD) | 关系数据库 |
| [Redis](https://redis.io/) | 7-alpine | BSD-3-Clause (v7.2 及以下) | 缓存 |
| [Milvus](https://milvus.io/) | v2.3.3 | Apache-2.0 | 向量数据库 |
| [etcd](https://etcd.io/) | v3.5.5 | Apache-2.0 | Milvus 元数据存储 |
| [MinIO](https://min.io/) | RELEASE.2023-03-20 | AGPL-3.0 | Milvus 对象存储 |

### Langfuse 可观测性平台

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [Langfuse Web/Worker](https://github.com/langfuse/langfuse) | v3 | MIT (核心) / EE License (企业功能) | LLM 可观测性 |
| [ClickHouse](https://clickhouse.com/) | 24.3 | Apache-2.0 | Langfuse 分析存储 |
| PostgreSQL (Langfuse 专用) | 15-alpine | PostgreSQL License | Langfuse 元数据 |
| Redis (Langfuse 专用) | 7-alpine | BSD-3-Clause | Langfuse 缓存 |
| MinIO (Langfuse 专用) | latest | AGPL-3.0 | Langfuse 媒体存储 |

### 构建与运行时基础镜像

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [Node.js](https://nodejs.org/) (node:20-alpine) | MIT | 前端构建 |
| [Nginx](https://nginx.org/) (nginx:alpine) | BSD-2-Clause | 前端静态文件服务 |
| [Golang](https://go.dev/) (golang:1.24-alpine) | BSD-3-Clause | Go 服务构建 |
| [Alpine Linux](https://alpinelinux.org/) (alpine:3.19 / alpine:latest) | MIT | Go 服务运行时 |
| [Python](https://www.python.org/) (python:3.11-slim) | PSF License | Python 服务运行时（ai-service、browser-service） |
| [Debian](https://www.debian.org/) (debian:trixie) | DFSG 兼容（多种自由软件许可证） | 沙箱基础镜像（Debian 13） |

---

## 沙箱系统组件

沙箱容器基于 **Debian 13 (trixie)**，`sandbox/Dockerfile` 中实际安装的组件如下（**无桌面环境、无 VNC / noVNC、无 Web IDE**）：

### 显示与浏览器

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [Xvfb](https://www.x.org/) | MIT (X11) | 虚拟帧缓冲（Chromium 非 headless 需要 DISPLAY） |
| [Chromium](https://www.chromium.org/) | BSD-3-Clause（主体） | 浏览器；CDP 截图与 Screencast 的来源（Debian 原生包，非 snap） |
| [socat](http://www.dest-unreach.org/socat/) | GPL-2.0 | 将 CDP 从 127.0.0.1:19222 转发到 0.0.0.0:9222，供同网络容器访问 |

### 运行时与开发工具

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [Python](https://www.python.org/) 3 + pip + venv | PSF License | Agent 服务运行时 |
| [Node.js](https://nodejs.org/) + npm | MIT | 沙箱内脚本能力 |
| [tmux](https://github.com/tmux/tmux) | ISC | 持久化 Shell 会话（`bash_session.py`） |
| [Git](https://git-scm.com/) | GPL-2.0 | 版本控制 |
| [gosu](https://github.com/tianon/gosu) | Apache-2.0 | entrypoint 中从 root 降权到 `sandbox` 用户 |

### 系统工具与字体

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [curl](https://curl.se/) | MIT (curl license) | HTTP 工具（CDP 就绪探测等） |
| [wget](https://www.gnu.org/software/wget/) | GPL-3.0 | 下载工具 |
| [htop](https://github.com/htop-dev/htop) | GPL-2.0 | 进程监控 |
| [vim](https://www.vim.org/) | Vim License (GPL 兼容) | 文本编辑器 |
| [nano](https://www.nano-editor.org/) | GPL-3.0 | 文本编辑器 |
| net-tools / iputils-ping / procps | GPL-2.0 等（未逐一核对） | 网络与进程排查 |
| fonts-wqy-zenhei / fonts-wqy-microhei | 未逐一核对，请以镜像内 `/usr/share/doc/*/copyright` 为准 | 中文字体 |
| locales | LGPL-2.1 / GPL（未逐一核对） | 中文 locale（zh_CN.UTF-8） |

> 历史文档曾列出 Xfce4、x11vnc、noVNC、websockify、OpenVSCode Server、pyautogui、python-xlib、scrot、xdotool、D-Bus 等组件，**这些已随沙箱瘦身移除**，见 [SANDBOX_SLIM_HISTORY.md](./SANDBOX_SLIM_HISTORY.md)。

---

## 许可证合规说明

### 许可证分类汇总

| 许可证类型 | 组件数量 | 性质 |
|-----------|---------|------|
| MIT | ~40+ | 宽松许可，可自由使用 |
| Apache-2.0 | ~20+ | 宽松许可，需保留声明 |
| BSD-3-Clause / BSD-2-Clause | ~15+ | 宽松许可，可自由使用 |
| ISC | 3 | 宽松许可，等同 MIT |
| PSF / PostgreSQL License / HPND | 3 | 宽松许可 |
| GPL-2.0 / GPL-3.0 | 沙箱容器内若干（socat、Git、wget、vim、nano、htop、procps 等） | Copyleft，仅限沙箱容器内 |
| MPL-2.0 | 0（原 MPL 组件 noVNC 已移除） | — |
| AGPL-3.0 | 1 (MinIO) | 强 Copyleft，需注意网络使用 |

> 表格为粗分类，沙箱内 Debian 系统包的许可证未逐一核对。

### 需要特别关注的许可证

1. **MinIO (AGPL-3.0)**
   - 仅作为 Milvus 和 Langfuse 的内部对象存储使用，不对外暴露服务
   - 未修改 MinIO 源码
   - 如需商用部署，建议替换为 S3 兼容的商业存储或评估 AGPL 合规性

2. **Redis 7.x 许可证变更**
   - Redis 7.4+ 从 BSD-3-Clause 变更为 RSALv2 / SSPLv1 双许可
   - 当前使用 `redis:7-alpine`，如版本 < 7.4 则仍为 BSD-3-Clause
   - 建议锁定版本或评估新许可证对云部署的影响

3. **GPL 组件（socat、Git、wget、vim、nano、htop 等）**
   - 均运行在沙箱容器内部，不与主服务代码链接
   - 如分发沙箱镜像，需确保 GPL 合规（提供源码获取途径）

4. **沙箱内的历史 LGPL 依赖已消失**
   - 早前的 python-xlib（PyAutoGUI 的 X11 后端）与 websockify（Web 客户端 WebSocket 代理，LGPL-3.0）已随沙箱瘦身移除，当前沙箱不再包含 LGPL 组件（locales 等 Debian 包未逐一核对）

5. **Langfuse 双许可**
   - 核心功能为 MIT 许可，可自由使用
   - 企业功能（SCIM、审计日志等）需要单独的 EE License

### 合规建议

- 所有宽松许可（MIT、Apache-2.0、BSD）组件可自由用于商业项目，保留原始许可声明即可
- GPL/LGPL 组件均限制在沙箱容器内，与主业务代码隔离
- 如需分发沙箱镜像，建议在镜像中包含 `/usr/share/doc/*/copyright` 文件
- 定期检查 Redis 版本，关注许可证变更对部署方式的影响
