# GlassBox 快速开始

> 本文档依据当前代码重写。项目定位为**工程原型**，非生产就绪系统；沙箱为 **Xvfb + Chromium CDP Screencast**，**无桌面环境、无 VNC / noVNC**。

## 系统概览

- **9 个应用服务**：Frontend、Gateway、Auth、Memory、Index、Browser、Task、AI、Worker Manager
- **3 个数据组件**：PostgreSQL、Redis、Milvus（另含 Milvus 依赖的 etcd、MinIO）
- **前端界面**：React 18 + Vite + TypeScript（生产镜像用 nginx 托管）
- **沙箱环境**：Debian 13 (trixie) + Xvfb + Chromium；AI 通过 Shell / 文件 API / CDP 操作，画面经 CDP Screencast 以 WebSocket 帧流推送到前端 Canvas

## 前置要求

- Docker 20.10+
- Docker Compose v2（`docker compose`）
- [Task](https://taskfile.dev)（可选，用于 `task dev` / `task up` 等）
- 本地开发额外需要：Go 1.21+、Python 3.11+、Node.js 18+

## 环境配置

```bash
cp .env.example .env
```

`.env.example` 当前包含：`JWT_SECRET`、`DOUBAO_API_KEY`、`DOUBAO_API_BASE`、`DOUBAO_MODEL`、`DOUBAO_EMBEDDING_MODEL`、`RESPONSE_SIGN_SECRET`、`LANGFUSE_*`、`DOCKER_VOLUME_DIRECTORY`。

**必须自行补充**（`.env.example` 中缺失，但 `docker-compose.yml` 会读取）：

```bash
# 必填：Worker 与沙箱 Agent 之间 HMAC 签名用；不填则为空字符串
SANDBOX_SECRET=<强随机值>

# 建议覆盖
JWT_SECRET=<强随机值>          # 默认回退为 your-super-secret-key-change-in-production
HOST_ADDRESS=localhost         # 生成沙箱 Screencast URL 时使用
```

其他可选变量见 `docker-compose.yml` 的 `ai-service` 段（`DOUBAO_GUI_MODEL`、`DOUBAO_VISION_MODEL`、`DEEPSEEK_*`、`LANGFUSE_ENABLED` 等），详见 [MODEL_CONFIGURATION.md](./MODEL_CONFIGURATION.md)。

## 启动

### 方式一：Taskfile（推荐）

```bash
task dev     # 构建沙箱镜像 + 基础设施 + 所有服务 + Langfuse（需 LANGFUSE_ENABLED=true）
task up      # 同上，但不含 Langfuse
task status  # 查看容器状态
task logs -- worker-manager
task down    # 停止
```

`task dev` / `task up` 会先检查 `.env` 是否存在，并在沙箱镜像缺失时自动构建；基础设施（postgres / redis / milvus-etcd / milvus-minio / milvus）带 `--wait` 就绪等待。

### 方式二：Docker Compose

```bash
docker build -t newarch-sandbox:latest ./sandbox
docker compose up -d
docker compose ps
```

### 访问地址

| 入口 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost:3000 | Dashboard、服务调试、API 测试、容器管理、服务健康 |
| AI 工作空间 | http://localhost:3000/workspace | CDP 实时画面 + 对话 + 文件管理器 + 持久 Shell |
| Gateway API | http://localhost:8080 | 对外 API 唯一入口 |
| Worker Manager API | http://localhost:9000 | 沙箱与工具管理（也发布到宿主） |
| Langfuse（可选） | http://localhost:3100 | `LANGFUSE_ENABLED=true` 时 |
| Milvus | http://localhost:9091/healthz | 健康检查 |

**注意**：auth(8081) / memory(8082) / index(8083) / browser(8084) / task(8085) / ai(8086) **未发布宿主端口**，无法用 `curl localhost:8086` 直接访问；需经 Gateway，或在容器内执行：

```bash
docker exec newarch-ai-service curl -s http://localhost:8086/health
```

前端容器另外提供了 `/internal/<service>/` 反向代理（`frontend/nginx.conf`），可直接经 3000 端口调试各服务，例如 `http://localhost:3000/internal/ai/health`、`http://localhost:3000/internal/gateway/health`。这是调试用通道，会绕过 Gateway 的鉴权。

## 验证服务

> **接口可用性提醒**：Gateway 会剥离 `/api/v1/{service}` 前缀后转发，部分 Gateway 声明路径与下游服务实际注册路径不一致（尤其 `/memory/*`、`/indexes/*`、`/tasks*`、以及经 Worker 的沙箱文件 / Screencast 代理），**端到端未验证**。详见 [ARCHITECTURE.md](./ARCHITECTURE.md) 的「已知限制」。下面的示例优先给可确认的路径。

### 健康检查

```bash
# Gateway（唯一可从宿主直接验证的核心服务）
curl -sf http://localhost:8080/health

# Worker Manager
curl -sf http://localhost:9000/health

# 其余服务（容器内）
docker exec newarch-auth-service curl -s http://localhost:8081/health
docker exec newarch-task-service curl -s http://localhost:8085/health
```

### 注册与登录

```bash
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "password123"}'

curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'

export TOKEN="<your-token-here>"
```

### 沙箱验证（经 Gateway → Worker Manager）

```bash
# 创建沙箱
curl -X POST http://localhost:8080/api/v1/ai/sandbox/create/testuser \
  -H "Authorization: Bearer $TOKEN"

# 查看沙箱信息（含 screencast_url / agent_port）
curl http://localhost:8080/api/v1/ai/sandbox/info/testuser \
  -H "Authorization: Bearer $TOKEN"

# 截图（CDP）
curl http://localhost:8080/api/v1/ai/sandbox/screenshot/testuser \
  -H "Authorization: Bearer $TOKEN" -o shot.jpg
```

Worker Manager 侧同一组能力（需 JWT）：

```bash
curl http://localhost:9000/api/v1/sandboxes -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:9000/api/v1/sandboxes/get-or-create \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"user_id": "testuser"}'
curl http://localhost:9000/api/v1/sandboxes/metrics -H "Authorization: Bearer $TOKEN"
```

### 沙箱 Agent 直连验证（无需 JWT，仅容器网络 / 本机映射端口）

```bash
# 在沙箱容器内
docker exec <sandbox-container> curl -s http://localhost:8000/health
docker exec <sandbox-container> curl -s http://localhost:8000/tools     # 仅 shell / wait
docker exec <sandbox-container> curl -s http://localhost:8000/cdp/info  # Chromium + CDP WS URL
docker exec <sandbox-container> curl -s http://localhost:8000/files/list?path=/home/sandbox
docker exec <sandbox-container> curl -s "http://localhost:8000/files/list?path=/etc"  # 应被拒绝（越界）

# 沙箱容器名形如 sandbox-<user 前 8 位>-<8 位随机 ID>
docker ps --filter "label=newarch.sandbox=true"
```

本机单独跑沙箱镜像调试：

```bash
docker run -d --name test-sandbox -e USER_ID=demo \
  -p 127.0.0.1:8001:8000 newarch-sandbox:latest

curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/tools

# CDP 9222 默认不发布到宿主；如需宿主调试，自行追加 -p 127.0.0.1:9222:9222
```

## 日常开发

### 容器化

```bash
docker compose up -d                    # 启动
docker compose ps                       # 状态
docker compose logs -f ai-service       # 日志
docker compose up -d --build ai-service # 重建单个服务
docker compose down                     # 停止
```

### 本地开发

```bash
# 前端（热重载）
cd frontend && npm install && npm run dev

# Go 服务
cd gateway && go run ./cmd/gateway
cd services/worker-service && go run ./cmd/worker

# Python 服务
cd services/ai-service && python -m uvicorn src.main:app --host 0.0.0.0 --port 8086 --reload
```

### 代码质量与测试（使用 Taskfile，仓库当前没有 Makefile）

```bash
task fmt          # Go + Python 格式化
task lint         # Go + Python 检查
task test         # Go + Python 测试
task test:go
task test:python
```

## 数据库操作

```bash
# PostgreSQL（宿主 5432 已发布）
docker exec -it newarch-postgres psql -U postgres -d newarch

# Redis（宿主 6379 已发布）
docker exec -it newarch-redis redis-cli

# Milvus 健康检查（宿主 9091 已发布）
curl http://localhost:9091/healthz
```

表结构与常见查询见 [DATABASE_CONNECTIONS.md](./DATABASE_CONNECTIONS.md)。

## 故障排查

### 沙箱无法启动

```bash
docker images | grep newarch-sandbox     # 镜像是否存在
task build:sandbox                       # 重新构建
docker logs newarch-worker-manager       # Worker 日志
```

常见原因：`.env` 未设置 `SANDBOX_SECRET`；已达 `MAX_SANDBOXES=50`；`sandbox-isolated` 网络不存在（compose 未启动）。

### 画面不刷新 / Screencast 连接失败

```bash
# 确认沙箱在运行（需 JWT）
curl -H "Authorization: Bearer $TOKEN" http://localhost:9000/api/v1/sandboxes

# 沙箱容器日志
docker logs <sandbox-container-name>

# 沙箱内确认 Chromium CDP 是否存活
docker exec <container> curl -s http://127.0.0.1:19222/json/version
```

常见原因：前端 WebSocket 未携带有效 `token`（`BrowserViewer` 通过 `?token=` 传递）；JWT 中 `user_id` 与 URL 中的 `user_id` 不一致（Gateway 返回 403）；Chromium 启动失败（Agent 日志出现 `Chromium CDP failed to start`）；`about:blank` 空白页帧率低属正常现象。

### Agent / 工具调用失败

- 工具调用返回签名错误：Worker 与沙箱的 `SANDBOX_SECRET` 不一致（`docker-compose.yml` 中该变量无默认值，缺失时为空）
- 文件 API 403：路径超出 `/home/sandbox`、`/tmp`；或单文件超过 5MB

### AI Service 问题

```bash
docker compose logs -f ai-service
docker exec newarch-ai-service env | grep -E "DOUBAO|DEEPSEEK|MILVUS|SANDBOX"
docker exec newarch-ai-service curl -s http://localhost:8086/health
```

### 容器无法启动

```bash
docker logs newarch-<service-name>
docker network ls | grep newarch
docker system df
```

## 备份与恢复

```bash
# PostgreSQL 备份 / 恢复
docker exec newarch-postgres pg_dump -U postgres newarch > backup.sql
docker exec -i newarch-postgres psql -U postgres newarch < backup.sql

# Redis 备份
docker exec newarch-redis redis-cli SAVE
docker cp newarch-redis:/data/dump.rdb ./redis-backup.rdb
```

注意：沙箱 workspace 使用命名卷 `sandbox-<user>-<id>-workspace`，销毁容器不会删除卷，但当前没有自动清理机制。

## 安全提醒（原型阶段）

1. 覆盖 `.env` 中的弱默认值（`JWT_SECRET`、`RESPONSE_SIGN_SECRET`），并补齐 `SANDBOX_SECRET`
2. gateway 与 worker-manager 挂载宿主 `/var/run/docker.sock`，属高权限面，不要对公网暴露 9000
3. 仅暴露必要端口（3000、8080；9000 建议仅本机使用）
4. `.env`、credentials 已在 `.gitignore` 中

## 更多资源

- [系统架构](./ARCHITECTURE.md)
- [模型配置](./MODEL_CONFIGURATION.md)
- [数据库连接](./DATABASE_CONNECTIONS.md)
- [异步任务指南](./async-tasks-guide.md)（能力未接通，见文首说明）
- [Bash 工具最佳实践](./bash-tool-best-practices.md)
- [开源依赖](./OPEN_SOURCE_DEPENDENCIES.md)
- [沙箱瘦身历史记录](./SANDBOX_SLIM_HISTORY.md)
- [OpenAPI 规范](./api-spec/openapi.yaml)
