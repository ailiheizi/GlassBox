# NewArch 快速开始指南

## 系统概览

NewArch 是一个微服务架构的 AI Agent 平台，包含：
- **8 个微服务**：Gateway, Auth, Memory, Index, Browser, Task, AI, Worker Manager
- **3 个数据库**：PostgreSQL, Redis, Milvus
- **前端界面**：React + Vite，支持 VNC 实时查看和 VSCode 编辑
- **沙箱环境**：Debian 12 + Xfce 桌面，AI 在其中操作

## 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- Go 1.21+（可选，本地开发 Go 服务）
- Node.js 20+（可选，本地开发前端）
- Python 3.11+（可选，本地开发 Python 服务）

## 环境配置

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，配置必要的 API Key：

```bash
# 必须配置
JWT_SECRET=your-super-secret-key
DOUBAO_API_KEY=your_volcengine_api_key
SANDBOX_SECRET=your-sandbox-hmac-secret

# 推荐配置
DEEPSEEK_API_KEY=your_deepseek_api_key

# 可选：指定模型端点
DOUBAO_GUI_MODEL=ep-xxxxxxxx    # 火山方舟推理接入点 ID
DOUBAO_VISION_MODEL=ep-xxxxxxxx
```

详细的模型配置参见 [MODEL_CONFIGURATION.md](./MODEL_CONFIGURATION.md)。

### 2. 构建沙箱镜像

```bash
./scripts/build-sandbox.sh
```

### 3. 启动所有服务

```bash
# 构建沙箱 + 启动所有服务
./scripts/start-all.sh

# 或者分步执行
docker-compose up -d

# 查看容器状态
docker-compose ps
```

### 4. 访问前端

打开浏览器访问：**http://localhost:3000**

## 验证服务

### 健康检查

```bash
# Gateway
curl http://localhost:8080/health

# AI Service
curl http://localhost:8086/health

# Worker Manager
curl http://localhost:9000/health
```

### 用户注册和登录

```bash
# 注册
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "password123"}'

# 登录（保存返回的 token）
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'

export TOKEN="<your-token-here>"
```

### 测试沙箱

```bash
# 创建沙箱
curl -X POST http://localhost:9000/api/v1/sandboxes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "testuser"}'

# 查看沙箱状态
curl http://localhost:9000/api/v1/sandboxes \
  -H "Authorization: Bearer $TOKEN"
```

### 验证架构升级

```bash
./scripts/verify-upgrade.sh
```

## 日常开发

### Docker 开发

```bash
docker-compose up -d              # 启动所有服务
docker-compose down               # 停止所有服务
docker-compose logs -f <service>  # 查看日志
docker-compose restart <service>  # 重启服务
docker-compose up -d --build <service>  # 重新构建并启动
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

### 代码质量

```bash
make fmt            # 格式化 Go 代码
make lint           # Lint Go 代码
make fmt-python     # 格式化 Python（black, isort）
make lint-python    # Lint Python（flake8, mypy）
make test           # 运行所有测试
```

## 数据库操作

```bash
# PostgreSQL
docker exec -it newarch-postgres psql -U postgres -d newarch

# Redis
docker exec -it newarch-redis redis-cli

# Milvus 健康检查
curl http://localhost:9091/healthz
```

## 故障排查

### 沙箱创建失败

```bash
# 检查端口池
curl http://localhost:9000/api/v1/sandboxes/metrics -H "Authorization: Bearer $TOKEN"

# 重建沙箱镜像
./scripts/build-sandbox.sh

# 重启 Worker Manager（重置端口池）
docker-compose restart worker-manager
```

### "no available VSCode ports"

确保 `services/worker-service/cmd/worker/main.go` 中 `sandboxConfig` 包含 `VSCodePortStart: 7001` 和 `VSCodePortEnd: 7099`。

### VNC 连接问题

1. 检查沙箱容器运行状态：`docker ps | grep sandbox`
2. 检查 VNC 进程：`docker exec <container> ps aux | grep vnc`
3. 确认使用 `vnc_lite.html`（非 `vnc.html`）
4. 测试直接访问：`curl http://localhost:6081/vnc_lite.html`

### AI Service 问题

```bash
# 查看日志
docker-compose logs -f ai-service

# 检查 Skill 系统初始化
docker logs newarch-ai-service --tail 20 | grep -i skill

# 检查环境变量
docker exec newarch-ai-service env | grep -E "DOUBAO|DEEPSEEK|MILVUS"
```

### 容器无法启动

```bash
docker logs newarch-<service-name>   # 查看日志
docker network ls | grep newarch     # 检查网络
docker system df                     # 检查磁盘空间
```

## 备份与恢复

```bash
# PostgreSQL 备份
docker exec newarch-postgres pg_dump -U postgres newarch > backup.sql

# PostgreSQL 恢复
docker exec -i newarch-postgres psql -U postgres newarch < backup.sql

# Redis 备份
docker exec newarch-redis redis-cli SAVE
docker cp newarch-redis:/data/dump.rdb ./redis-backup.rdb
```

## 安全建议

1. **修改默认密码**：更新 `.env` 中的 `JWT_SECRET` 和数据库密码
2. **使用 HTTPS**：生产环境配置 TLS/SSL
3. **限制网络访问**：只暴露必要端口（3000, 8080）
4. **不提交敏感文件**：`.env`、credentials 等已在 `.gitignore` 中

## 更多资源

- [系统架构](./ARCHITECTURE.md)
- [模型配置](./MODEL_CONFIGURATION.md)
- [数据库连接](./DATABASE_CONNECTIONS.md)
- [异步任务指南](./async-tasks-guide.md)
- [Bash 工具最佳实践](./bash-tool-best-practices.md)
- [API 规范](./api-spec/)
