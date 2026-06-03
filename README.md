# NewArch - 微服务架构 AI Agent 平台

[![Status](https://img.shields.io/badge/status-production--ready-green)]()
[![Version](https://img.shields.io/badge/version-1.0.0-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

一个完整的微服务架构 AI Agent 平台，支持 AI 在独立沙箱容器中执行工具操作，用户通过 VNC 实时观看。

## ✨ 特性

- 🤖 **AI Agent 沙箱** - 每个用户独立的桌面环境容器
- 🖥️ **实时 VNC** - 通过 noVNC 在浏览器中观看 AI 操作
- 🏗️ **微服务架构** - 7个独立服务，松耦合设计
- 🔒 **安全隔离** - 多层网络隔离、容器隔离、资源限制
- 🎨 **调试界面** - 强大的可视化调试工具
- 🐳 **容器化部署** - Docker Compose 一键启动

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+

### 启动服务

```bash
# 克隆项目
git clone <your-repo-url> NewArch
cd NewArch

# 一键启动所有服务（包含沙箱镜像构建）
./scripts/start-all.sh

# 或者分步启动：
# 1. 构建沙箱镜像
./scripts/build-sandbox.sh

# 2. 启动所有服务
docker-compose up -d
```

### 访问地址

- **前端界面**: http://localhost:3000
- **AI 工作空间**: http://localhost:3000/workspace
- **Gateway API**: http://localhost:8080
- **Worker API**: http://localhost:9000

## 📦 系统架构

### 核心架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Public Zone (公网层)                        │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (3000)  │  Gateway (8080)  │  noVNC Proxy (6080+)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Internal Zone (内部服务层)                        │
├─────────────────────────────────────────────────────────────────┤
│  Auth (8081) │ Memory (8082) │ Index (8083) │ Browser (8084)   │
│  Task (8085) │ AI (8086)     │ Worker Manager (9000)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Zone (数据层)                            │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL (5432)  │  Redis (6379)  │  Milvus (19530)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Sandbox Isolated Zone (沙箱执行层)                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                     │
│  │Sandbox-1│    │Sandbox-2│    │Sandbox-N│  (动态创建)          │
│  │VNC:5901 │    │VNC:5902 │    │VNC:590N │                     │
│  └─────────┘    └─────────┘    └─────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

### AI Agent 工作流程

```
用户发送消息 → AI Service → 获取/创建沙箱 → 截图分析 → 执行工具 → VNC 实时展示
```

## 🎯 主要功能

### 1. AI 工作空间 (新增)

- **沙箱环境** - Ubuntu + Xfce 桌面环境
- **VNC 查看器** - 浏览器内实时观看 AI 操作
- **AI 对话** - 与 AI 对话，让它帮你操作沙箱
- **工具调用** - 点击、输入、执行命令、打开浏览器等

### 2. 沙箱工具

| 工具 | 描述 |
|------|------|
| `click` | 点击指定坐标 |
| `double_click` | 双击 |
| `type` | 输入文本 |
| `key` | 按键（支持组合键如 ctrl+c） |
| `scroll` | 滚动 |
| `shell` | 执行 Shell 命令 |
| `browser` | 打开浏览器 |
| `terminal` | 打开终端 |
| `screenshot` | 获取截图 |

### 3. 微服务

- **Gateway** - API 网关和路由
- **Auth** - 用户认证和授权
- **Memory** - 语义记忆和向量搜索
- **Index** - 索引管理
- **Browser** - AI 对话和浏览器自动化
- **Task** - 任务管理
- **AI** - AI 接口、Embedding 和沙箱集成
- **Worker Manager** - 沙箱生命周期管理

## 📖 文档

- [AI Agent 沙箱架构设计](docs/ai-agent-sandbox-architecture.md)
- [Worker 架构设计](docs/worker-architecture.md)
- [快速开始指南](docs/quick-start.md)
- [完成报告](docs/completion-report.md)

## 🛠️ 运维工具

```bash
# 构建沙箱镜像
./scripts/build-sandbox.sh

# 启动所有服务
./scripts/start-all.sh

# 备份所有数据
./scripts/backup.sh

# 从备份恢复
./scripts/restore.sh ./backups/20260127_120000

# 实时监控
./scripts/monitor.sh

# API 测试
./scripts/test-apis.sh
```

## 🔧 开发

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

### 后端开发 (Go)

```bash
cd services/worker-service
go mod download
go run cmd/worker/main.go
```

### 后端开发 (Python)

```bash
cd services/ai-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

### 沙箱开发

```bash
# 构建沙箱镜像
./scripts/build-sandbox.sh

# 测试运行
docker run -d --name test-sandbox \
  -p 5901:5900 -p 6081:6080 -p 8001:8000 \
  newarch-sandbox:latest

# 访问 noVNC
open http://localhost:6081/vnc.html
```

## 📊 API 端点

### 沙箱 API (AI Service)

```bash
# 创建沙箱
POST /sandbox/create/{user_id}

# 获取沙箱信息
GET /sandbox/info/{user_id}

# 销毁沙箱
DELETE /sandbox/destroy/{user_id}

# 沙箱聊天 (流式)
POST /sandbox/chat/stream
{
  "user_id": "string",
  "message": "string",
  "include_screenshot": true
}

# 获取截图
GET /sandbox/screenshot/{user_id}

# 执行工具
POST /sandbox/execute/{user_id}?tool=click
{"x": 100, "y": 200}
```

### Worker Manager API

```bash
# 列出沙箱
GET /api/v1/sandboxes

# 创建沙箱
POST /api/v1/sandboxes
{"user_id": "string"}

# 获取沙箱
GET /api/v1/sandboxes/{user_id}

# 删除沙箱
DELETE /api/v1/sandboxes/{user_id}

# 心跳保活
POST /api/v1/sandboxes/{user_id}/keepalive

# 执行工具
POST /api/v1/tools/{user_id}/execute
{"tool": "click", "params": {"x": 100, "y": 200}}

# 获取截图
GET /api/v1/tools/{user_id}/screenshot
```

## 🔒 安全特性

- ✅ JWT 认证
- ✅ 多层网络隔离 (public/internal/sandbox-isolated)
- ✅ 容器隔离
- ✅ 资源限制 (CPU/内存/进程数)
- ✅ 镜像白名单
- ✅ Capability 限制
- ✅ 空闲沙箱自动清理

## 📈 性能指标

- **沙箱启动时间**: < 5s
- **最大沙箱数**: 50 (可配置)
- **沙箱资源**: 1 CPU, 2GB RAM (默认)
- **空闲超时**: 30 分钟
- **VNC 端口范围**: 5901-5999
- **noVNC 端口范围**: 6081-6179

## 🐛 故障排查

### 沙箱无法启动

```bash
# 检查沙箱镜像
docker images | grep newarch-sandbox

# 重新构建
./scripts/build-sandbox.sh

# 检查 Worker Manager 日志
docker logs newarch-worker-manager
```

### VNC 无法连接

```bash
# 检查沙箱状态
curl http://localhost:9000/api/v1/sandboxes

# 检查端口占用
lsof -i :5901

# 检查沙箱日志
docker logs sandbox-{user_id}-{sandbox_id}
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

---

**项目状态**: ✅ 生产就绪
**最后更新**: 2026-01-27
**版本**: v1.0.0

---

**Built with ❤️ using Go, Python, React, Docker, and VNC**
