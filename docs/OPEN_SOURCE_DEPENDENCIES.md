# 开源依赖说明

本文档列出 NewArch 项目使用的所有开源组件及其许可证信息。

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
| [pymilvus](https://github.com/milvus-io/pymilvus) | >=2.3.0 | Apache-2.0 | Milvus 向量数据库客户端 |
| [PyJWT](https://github.com/jpadilla/pyjwt) | >=2.8.0 | MIT | JWT 认证 |
| [volcengine-python-sdk](https://github.com/volcengine/volcengine-python-sdk) | >=5.0.8 | Apache-2.0 | 火山引擎 SDK |
| [rank-bm25](https://github.com/dorianbrown/rank_bm25) | >=0.2.2 | Apache-2.0 | BM25 文本检索 |

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

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [FastAPI](https://github.com/tiangolo/fastapi) | 0.109.0 | MIT | 工具执行 API |
| [Uvicorn](https://github.com/encode/uvicorn) | 0.27.0 | BSD-3-Clause | ASGI 服务器 |
| [Pydantic](https://github.com/pydantic/pydantic) | 2.5.3 | MIT | 数据验证 |
| [PyAutoGUI](https://github.com/asweigart/pyautogui) | 0.9.54 | BSD-3-Clause | GUI 自动化操作 |
| [Pillow](https://github.com/python-pillow/Pillow) | 10.2.0 | HPND | 截图处理 |
| [python-xlib](https://github.com/python-xlib/python-xlib) | 0.33 | LGPL-2.1 | X11 协议绑定 |
| [httpx](https://github.com/encode/httpx) | 0.26.0 | BSD-3-Clause | HTTP 客户端 |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.6 | Apache-2.0 | 表单解析 |

### 测试依赖

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
| [Python](https://www.python.org/) (python:3.11-slim) | PSF License | Python 服务运行时 |
| [Debian](https://www.debian.org/) (bookworm-slim) | DFSG 兼容（多种自由软件许可证） | 沙箱基础镜像 |
| [Alpine Linux](https://alpinelinux.org/) | MIT | 轻量运行时基础镜像 |

---

## 沙箱系统组件

沙箱容器基于 Debian 12 (Bookworm)，包含以下系统级开源组件：

### 桌面环境与显示

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [Xfce4](https://xfce.org/) | GPL-2.0+ | 轻量桌面环境 |
| [Xvfb](https://www.x.org/) | MIT (X11) | 虚拟帧缓冲 |
| [x11vnc](https://github.com/LibVNC/x11vnc) | GPL-2.0 | VNC 服务器 |
| [noVNC](https://github.com/novnc/noVNC) | MPL-2.0 | Web VNC 客户端 |
| [websockify](https://github.com/novnc/websockify) | LGPL-3.0 | WebSocket 代理 |

### 开发工具

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [OpenVSCode Server](https://github.com/gitpod-io/openvscode-server) | MIT | Web IDE |
| [Chromium](https://www.chromium.org/) | BSD-3-Clause (主体) | 浏览器 |
| [tmux](https://github.com/tmux/tmux) | ISC | 终端复用 / BashSession |
| [Git](https://git-scm.com/) | GPL-2.0 | 版本控制 |

### 系统工具

| 组件 | 许可证 | 用途 |
|------|--------|------|
| [scrot](https://github.com/resurrecting-open-source-projects/scrot) | MIT-feh | 截图工具 |
| [xdotool](https://github.com/jordansissel/xdotool) | BSD-3-Clause | X11 自动化 |
| [curl](https://curl.se/) | MIT (curl license) | HTTP 工具 |
| [wget](https://www.gnu.org/software/wget/) | GPL-3.0 | 下载工具 |
| [htop](https://github.com/htop-dev/htop) | GPL-2.0 | 进程监控 |
| [vim](https://www.vim.org/) | Vim License (GPL 兼容) | 文本编辑器 |
| [nano](https://www.nano-editor.org/) | GPL-3.0 | 文本编辑器 |
| [gosu](https://github.com/tianon/gosu) | Apache-2.0 | 用户切换 |
| [D-Bus](https://www.freedesktop.org/wiki/Software/dbus/) | AFL-2.1 / GPL-2.0+ | 进程间通信 |

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
| GPL-2.0 / GPL-3.0 | ~8 | Copyleft，仅限沙箱容器内 |
| LGPL-2.1 / LGPL-3.0 | 2 | 弱 Copyleft |
| MPL-2.0 | 1 | 文件级 Copyleft |
| AGPL-3.0 | 1 (MinIO) | 强 Copyleft，需注意网络使用 |

### 需要特别关注的许可证

1. **MinIO (AGPL-3.0)**
   - 仅作为 Milvus 和 Langfuse 的内部对象存储使用，不对外暴露服务
   - 未修改 MinIO 源码
   - 如需商用部署，建议替换为 S3 兼容的商业存储或评估 AGPL 合规性

2. **Redis 7.x 许可证变更**
   - Redis 7.4+ 从 BSD-3-Clause 变更为 RSALv2 / SSPLv1 双许可
   - 当前使用 `redis:7-alpine`，如版本 < 7.4 则仍为 BSD-3-Clause
   - 建议锁定版本或评估新许可证对云部署的影响

3. **GPL 组件（Xfce4、x11vnc、Git、wget、vim、nano、htop）**
   - 均运行在沙箱容器内部，不与主服务代码链接
   - 如分发沙箱镜像，需确保 GPL 合规（提供源码获取途径）

4. **LGPL 组件（python-xlib、websockify）**
   - python-xlib (LGPL-2.1)：PyAutoGUI 的 X11 后端依赖，动态导入
   - websockify (LGPL-3.0)：noVNC 的 WebSocket 代理，独立进程运行

5. **Langfuse 双许可**
   - 核心功能为 MIT 许可，可自由使用
   - 企业功能（SCIM、审计日志等）需要单独的 EE License

### 合规建议

- 所有宽松许可（MIT、Apache-2.0、BSD）组件可自由用于商业项目，保留原始许可声明即可
- GPL/LGPL 组件均限制在沙箱容器内，与主业务代码隔离
- 如需分发沙箱镜像，建议在镜像中包含 `/usr/share/doc/*/copyright` 文件
- 定期检查 Redis 版本，关注许可证变更对部署方式的影响
