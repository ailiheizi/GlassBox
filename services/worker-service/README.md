# Worker Service

Worker Service 是 NewArch 架构中的容器执行层，负责在隔离环境中创建和管理 Docker 容器，执行用户任务。

## 特性

- **容器生命周期管理**: 创建、启动、停止、删除容器
- **任务执行**: 异步执行用户提交的任务
- **资源限制**: CPU、内存、磁盘配额控制
- **安全隔离**: 网络隔离、只读文件系统、Capability 限制
- **镜像白名单**: 只允许预定义的安全镜像
- **监控指标**: 实时资源使用和任务统计

## 架构

```
┌─────────────────────────────────────┐
│         Worker Service              │
├─────────────────────────────────────┤
│  API Layer (Gin)                    │
│  ├─ Container Management            │
│  ├─ Task Execution                  │
│  └─ Metrics                         │
├─────────────────────────────────────┤
│  Docker Client                      │
│  ├─ Container Operations            │
│  ├─ Resource Limits                 │
│  └─ Security Policies               │
├─────────────────────────────────────┤
│  Docker Engine                      │
│  └─ Isolated Containers             │
└─────────────────────────────────────┘
```

## 快速开始

### 本地开发

1. 安装依赖:
```bash
go mod download
```

2. 配置环境变量:
```bash
cp .env.example .env
# 编辑 .env 文件
```

3. 运行服务:
```bash
go run cmd/worker/main.go
```

### Docker 部署

1. 构建镜像:
```bash
docker build -t newarch-worker:latest .
```

2. 运行容器:
```bash
docker-compose up -d
```

## API 文档

### 健康检查

```
GET /health
```

### 容器管理

#### 列出容器
```
GET /api/v1/containers?all=true
Authorization: Bearer <token>
```

#### 创建容器
```
POST /api/v1/containers
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "my-container",
  "image": "python:3.11-slim",
  "command": ["python", "-c", "print('Hello')"],
  "environment": {
    "ENV_VAR": "value"
  },
  "resources": {
    "cpu_quota": 100000,
    "memory": 536870912
  },
  "network_mode": "none"
}
```

#### 启动容器
```
POST /api/v1/containers/:id/start
Authorization: Bearer <token>
```

#### 停止容器
```
POST /api/v1/containers/:id/stop
Authorization: Bearer <token>
```

#### 删除容器
```
DELETE /api/v1/containers/:id?force=true
Authorization: Bearer <token>
```

#### 获取日志
```
GET /api/v1/containers/:id/logs?tail=100
Authorization: Bearer <token>
```

#### 获取资源统计
```
GET /api/v1/containers/:id/stats
Authorization: Bearer <token>
```

### 任务管理

#### 提交任务
```
POST /api/v1/tasks
Authorization: Bearer <token>
Content-Type: application/json

{
  "type": "code_execution",
  "image": "python:3.11-slim",
  "command": ["python", "script.py"],
  "environment": {
    "PYTHONPATH": "/app"
  },
  "resources": {
    "cpu_quota": 100000,
    "memory": 536870912
  },
  "timeout": 300000000000
}
```

响应:
```json
{
  "task_id": "uuid",
  "status": "pending"
}
```

#### 获取任务状态
```
GET /api/v1/tasks/:id
Authorization: Bearer <token>
```

#### 取消任务
```
DELETE /api/v1/tasks/:id
Authorization: Bearer <token>
```

### 监控指标

```
GET /api/v1/metrics
Authorization: Bearer <token>
```

响应:
```json
{
  "active_containers": 5,
  "total_containers": 10,
  "tasks_running": 3,
  "tasks_completed": 100,
  "tasks_failed": 2
}
```

## 安全配置

### 镜像白名单

在 `config/config.go` 中配置允许的镜像:

```go
AllowedImages: []string{
    "python:3.11-slim",
    "node:18-alpine",
    "golang:1.21-alpine",
    "ubuntu:22.04",
}
```

### 网络隔离

默认情况下，容器使用 `none` 网络模式，完全隔离网络访问。

### 资源限制

每个容器都有强制的资源限制:
- CPU: 默认 1 核
- 内存: 默认 512MB
- 磁盘: 可配置

### Capability 限制

默认移除危险的 Linux capabilities:
- NET_RAW
- NET_ADMIN
- SYS_ADMIN
- SYS_MODULE

## 监控

Worker Service 暴露 Prometheus 格式的指标:

```
GET /metrics
```

指标包括:
- 容器数量
- 任务执行统计
- 资源使用情况

## 部署建议

### 生产环境

1. **独立服务器**: Worker 应部署在独立的服务器上，与核心服务物理隔离
2. **TLS 加密**: 使用 HTTPS 通信
3. **防火墙**: 只允许核心服务访问 Worker
4. **资源监控**: 配置 Prometheus + Grafana
5. **日志聚合**: 使用 ELK 或 Loki
6. **定期清理**: 自动清理过期容器和镜像

### Kubernetes

参考 `docs/worker-architecture.md` 中的 K8s 部署配置。

## 故障排查

### 容器创建失败

检查:
1. 镜像是否在白名单中
2. Docker daemon 是否运行
3. 资源是否充足

### 认证失败

检查:
1. JWT_SECRET 是否正确
2. Token 是否过期
3. Authorization header 格式

### 性能问题

检查:
1. 并发容器数量
2. 资源使用情况
3. Docker daemon 配置

## 开发

### 运行测试

```bash
go test ./...
```

### 代码格式化

```bash
go fmt ./...
```

### 构建

```bash
go build -o worker ./cmd/worker
```

## 许可证

MIT
