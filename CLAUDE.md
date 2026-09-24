# CLAUDE.md

本文件为 AI 编码工具提供 GlassBox 仓库的项目说明。仓库历史名为 NewArch：镜像名（`newarch-sandbox`）、容器名（`newarch-*`）、Docker 网络名（`newarch_sandbox-isolated`）、Go module（`github.com/newarch/*`）仍沿用旧前缀，属历史命名，不是待清理项。

> **项目定位：工程原型（prototype）**，提交历史很短、暂无 CI，接口与部署方式可能变动，不要按已完成/上线系统对待。
>
> 沙箱观看链路是 **Xvfb + Chromium CDP Screencast**：容器内**没有桌面环境、没有 VNC / noVNC、没有 VSCode Server、没有 pyautogui/xdotool**。旧桌面方案仅存于历史存档 `docs/SANDBOX_SLIM_HISTORY.md`，不是现状。

## 权威来源

改代码前先读对应实现，不要凭印象：

- `README.md`、`docs/ARCHITECTURE.md`（已按当前代码重写，含已知限制）
- 编排：`docker-compose.yml`（9 个应用服务 + 3 个数据组件）、`langfuse-compose.yml`（可选）
- 沙箱：`sandbox/Dockerfile`、`sandbox/entrypoint.sh`、`sandbox/tools/`

## 常用命令

命令入口是 `Taskfile.yml`；仓库**没有 Makefile，也没有 `scripts/` 目录**（旧文档里的 `make *`、`./scripts/*.sh` 已不存在）。

```bash
task                            # 列出所有命令
task dev                        # 一键起开发环境（构建沙箱镜像 + 基础设施 + 服务 + 可选 Langfuse）
task up / task down             # 起（不含 Langfuse）/ 停全部
task restart -- ai-service      # 重建并重启单个服务
task logs -- worker-manager     # 跟踪日志
task status / task clean        # 容器状态 / 删除所有数据卷（不可恢复）
task build / task build:sandbox
task test / task test:go / task test:python
task fmt / task fmt:go / task fmt:python
task lint / task lint:go / task lint:python
```

不用 Taskfile 时：

```bash
docker build -t newarch-sandbox:latest ./sandbox   # 沙箱镜像必须先构建，worker 才能创建沙箱
docker compose up -d && docker compose logs -f <service>
```

本地单服务开发：

```bash
cd frontend && npm install && npm run dev        # Vite，热更新
cd gateway && go run ./cmd/gateway
cd services/auth-service && go run ./cmd/server  # memory / index / task 同为 cmd/server
cd services/worker-service && go run ./cmd/worker
cd services/ai-service && python -m src.main     # Python 3.11+，需先装 requirements.txt
```

单个测试：`cd services/worker-service && go test -v ./internal/...`、`cd services/ai-service && pytest tests/ -v`。根目录 `tests/unit`、`tests/e2e` 存在但未被 Taskfile 引用。

## 目录结构

```
gateway/                          Go 网关：internal/{router,proxy,middleware,security,admin,config}
services/
  auth|memory|index|task-service/ Go + Gin，cmd/server
  worker-service/                 Go，cmd/worker：沙箱生命周期、工具与推流代理
  ai-service/                     Python FastAPI，src/{api,core,config}：LLM 编排、LangGraph、Skill 检索
  browser-service/                Python FastAPI：浏览器会话与对话
sandbox/                          沙箱镜像：Dockerfile、entrypoint.sh、tools/{agent_server.py,bash_session.py}
frontend/                         React 18 + Vite + TS；生产镜像用 nginx，nginx.conf 内还有 /internal/<service>/ 调试反代
infrastructure/docker/postgres/   init.sql + migrations
shared/proto/                     protobuf 定义与 gen/{go,python}
tests/{unit,e2e}/  docs/
```

## 服务与端口

| 服务 | 端口 | 宿主发布 |
|------|------|----------|
| Frontend | 3000 | 是 |
| Gateway | 8080 | 是 |
| Worker Manager | 9000 | 是（容器只接 internal + sandbox-isolated） |
| Auth / Memory / Index / Browser / Task / AI | 8081–8086 | 否，仅内部网络，经 Gateway 访问 |

数据组件：PostgreSQL 15（5432）、Redis 7（6379）、Milvus 2.3.3（19530/9091，含 etcd + MinIO）。三层网络：`public` / `internal`（`internal: true`）/ `sandbox-isolated`（未开 internal，以便宿主端口映射）；沙箱只接入 `sandbox-isolated`。

## 沙箱

- 镜像基于 `debian:trixie`（Debian 13），装 Xvfb、Debian 原生 Chromium（非 snap）、socat、tmux、gosu、Python 3、Node/npm。
- `entrypoint.sh` 四步：Xvfb `:1`（`1280x720x24`）→ tmux 预建 `default` 会话 → Chromium `--remote-debugging-port=19222` + `socat` 把 `0.0.0.0:9222` 转发到 `127.0.0.1:19222` → `uvicorn agent_server:app` 监听 `:8000`。root 仅用于启动 Xvfb/tmux，之后 `gosu` 降权到非 root 用户 `sandbox`（工作区 `/home/sandbox/workspace`）。
- Agent（`sandbox/tools/agent_server.py`）自带执行工具只有 `shell`、`wait`；截图、文件、tmux Bash 会话、CDP 推流走独立端点（`/screenshot`、`/files/*`、`/bash/*`、`/cdp/*`）。
- 观看链路：前端 `BrowserViewer` → Gateway `/api/v1/ai/sandbox/screencast/:user_id/ws`（从 `?token=` 自校验 JWT）→ worker-manager 中继 → Agent `/cdp/screencast/ws` → CDP `Page.startScreencast`。
- 改 `sandbox/Dockerfile` 或 `sandbox/tools/` 后：`task build:sandbox`，再重建 worker-manager 与既有沙箱（旧沙箱沿用旧镜像）。

## 约定与注意事项

- `.env` 从 `.env.example` 复制；`SANDBOX_SECRET` 不在 `.env.example` 里，需自行补（worker 与沙箱 Agent 之间的 HMAC-SHA256 签名密钥）。`JWT_SECRET` 等存在默认弱值回退。
- `ai-service` 挂载 `./services/ai-service/src:/app/src` 支持热改代码，改完 `task restart -- ai-service`。
- 新增服务：建 `services/<name>/`（含 Dockerfile）→ 加进 `docker-compose.yml` 与相应网络 → 在 `gateway/internal/router/routes.go` 注册路由。
- 新增 AI 工具：先在 `services/ai-service/src/core/sandbox.py` 的 `SANDBOX_TOOLS` 声明，再在沙箱 Agent 里实现对应端点。
- 格式化与检查：Go 用 `gofmt` + `golangci-lint`（仓库无 lint 配置文件，走默认规则）；Python 用 `black` + `isort` + `flake8`。
- 已知限制（勿当作已实现，细节见 `docs/ARCHITECTURE.md`）：`AllowedImages` 对用户沙箱路径不生效；`BlockedPorts` 无代码引用；task-service 的 `/tasks/async` 路由未注册；前端 `/internal/<service>/` 反代绕过 Gateway 鉴权；Gateway 前缀剥离与部分下游路径不匹配（未端到端验证）。

## 文档索引

- `README.md`：概览、快速开始、API 端点清单
- `docs/ARCHITECTURE.md`：架构、安全设计、已知限制（**改架构相关代码前先读**）
- `docs/GETTING_STARTED.md`、`docs/MODEL_CONFIGURATION.md`、`docs/DATABASE_CONNECTIONS.md`、`docs/bash-tool-best-practices.md`
- `docs/async-tasks-guide.md`（能力未接通）、`docs/SANDBOX_SLIM_HISTORY.md`（历史存档）、`docs/api-spec/openapi.yaml`
