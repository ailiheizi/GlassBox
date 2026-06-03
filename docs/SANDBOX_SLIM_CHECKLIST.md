# 沙箱架构瘦身 - 验证检查清单

## 快速验证命令

### 1. 沙箱容器验证 ✅

```bash
# 构建镜像
docker build -t newarch-sandbox:v2 sandbox/

# 检查镜像大小
docker images | grep newarch-sandbox

# 启动测试容器
docker run -d --name test-sb -p 8000:8000 \
  -e USER_ID=test123 \
  -e SANDBOX_ID=test-sb-001 \
  -e SANDBOX_SECRET=test-secret \
  newarch-sandbox:v2

# 健康检查
curl http://localhost:8000/health

# CDP 信息
curl http://localhost:8000/cdp/info

# 工具列表
curl http://localhost:8000/tools

# 清理
docker stop test-sb && docker rm test-sb
```

**预期结果**:
- ✅ 镜像大小 < 800MB
- ✅ 容器启动时间 < 5s
- ✅ 健康检查返回 200
- ✅ 工具列表只包含 shell 和 wait

### 2. 文件管理 API 验证 ✅

```bash
# 列出目录
curl "http://localhost:8000/files/list?path=/home/sandbox"

# 写入文件
curl -X POST http://localhost:8000/files/write \
  -H "Content-Type: application/json" \
  -d '{"path":"/tmp/test.txt","content":"hello"}'

# 读取文件
curl "http://localhost:8000/files/read?path=/tmp/test.txt"

# 安全边界测试（应返回 403）
curl "http://localhost:8000/files/list?path=/etc"
```

**预期结果**:
- ✅ 所有操作返回 200
- ✅ 文件内容正确
- ✅ /etc 访问返回 403

### 3. CDP 功能验证 ✅

```bash
# CDP 截图
curl http://localhost:8000/screenshot | head -c 200

# CDP Screencast WebSocket（需要 wscat）
npm install -g wscat
wscat -c "ws://localhost:8000/cdp/screencast/ws?quality=60"
```

**预期结果**:
- ✅ 截图返回 base64 JPEG
- ✅ WebSocket 连接成功并接收帧数据

### 4. AI Service 验证 ✅

```bash
# 检查工具列表
docker exec newarch-ai-service python -c \
  "from src.core.sandbox import SANDBOX_TOOLS; \
   import json; \
   print(json.dumps([t['function']['name'] for t in SANDBOX_TOOLS], indent=2))"

# 检查模式路由
docker exec newarch-ai-service python -c \
  "from src.core.mode_router import ModeRouter; \
   router = ModeRouter(); \
   decision = router.select_mode('打开百度'); \
   print(f'Mode: {decision.mode}, Confidence: {decision.confidence}')"
```

**预期结果**:
- ✅ 工具列表包含 11 个工具
- ✅ 模式路由返回 AUTO

### 5. Worker Manager 验证 ✅

```bash
# 重新构建
docker-compose build worker-manager

# 重启服务
docker-compose restart worker-manager

# 健康检查
curl http://localhost:9000/health
```

**预期结果**:
- ✅ 构建成功
- ✅ 健康检查返回 200

### 6. 前端组件验证 ✅

```bash
# 检查新组件文件
ls -la frontend/src/components/ | grep -E "(BrowserViewer|FileExplorer)"

# 检查组件集成
grep -n "BrowserViewer\|FileExplorer" frontend/src/components/AIWorkspace.tsx
```

**预期结果**:
- ✅ BrowserViewer.tsx 存在
- ✅ FileExplorer.tsx 存在
- ✅ AIWorkspace.tsx 中已导入和使用

## 完整验证流程

### Step 1: 构建所有镜像

```bash
# 构建沙箱镜像
docker build -t newarch-sandbox:v2 sandbox/

# 构建 Worker Manager
docker-compose build worker-manager

# 构建 AI Service
docker-compose build ai-service
```

### Step 2: 启动所有服务

```bash
docker-compose up -d
docker-compose ps
```

### Step 3: 验证服务健康

```bash
# Gateway
curl http://localhost:8080/health

# Worker Manager
curl http://localhost:9000/health

# AI Service
curl http://localhost:8086/health
```

### Step 4: 端到端测试（需要 JWT token）

```bash
# 1. 登录获取 token
TOKEN=$(curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.token')

# 2. 创建沙箱
curl -X POST http://localhost:9000/api/v1/sandboxes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123"}'

# 3. 测试文件代理
curl "http://localhost:9000/api/v1/tools/test123/files/list?path=/home/sandbox" \
  -H "Authorization: Bearer $TOKEN"

# 4. 销毁沙箱
curl -X DELETE http://localhost:9000/api/v1/sandboxes/test123 \
  -H "Authorization: Bearer $TOKEN"
```

### Step 5: 前端测试（手动）

1. 打开浏览器访问 http://localhost:3000
2. 登录系统
3. 进入 AI 工作空间
4. 创建沙箱
5. 切换到"浏览器"标签，观察 CDP screencast 画面
6. 切换到"文件"标签，浏览文件树
7. 发送消息："打开百度"
8. 观察浏览器标签中的实时画面更新

## 关键文件检查清单

### 沙箱容器 ✅

- [x] `sandbox/Dockerfile` - 已升级到 Debian 13，删除桌面包
- [x] `sandbox/entrypoint.sh` - 已精简到 4 步
- [x] `sandbox/tools/agent_server.py` - 已重写，新增 CDP + 文件 API
- [x] `sandbox/tools/requirements.txt` - 已更新依赖

### Worker Manager ✅

- [x] `services/worker-service/internal/sandbox/manager.go` - 已简化端口池
- [x] `services/worker-service/internal/api/sandbox_handler.go` - 已新增文件代理
- [x] `services/worker-service/cmd/worker/main.go` - 已删除端口配置
- [x] `services/worker-service/internal/sandbox/manager_test.go` - 已更新测试

### AI Service ✅

- [x] `services/ai-service/src/core/sandbox.py` - 已更新工具列表
- [x] `services/ai-service/src/core/mode_router.py` - 已简化为 AUTO
- [x] `services/ai-service/src/api/smart_sandbox_routes.py` - 已更新系统提示
- [x] `services/ai-service/src/core/langgraph/nodes.py` - 已更新工具说明

### Gateway ✅

- [x] `gateway/internal/router/routes.go` - 已新增文件管理路由

### Frontend ✅

- [x] `frontend/src/components/BrowserViewer.tsx` - 已创建
- [x] `frontend/src/components/FileExplorer.tsx` - 已创建
- [x] `frontend/src/components/AIWorkspace.tsx` - 已重构
- [x] `frontend/src/components/SandboxPanel.tsx` - 已更新接口

### 测试 ✅

- [x] `tests/unit/sandbox/test_agent_server.py` - 已更新
- [x] `tests/unit/sandbox/test_sandbox_client.py` - 已更新
- [x] `services/worker-service/internal/sandbox/manager_test.go` - 已更新

### 文档 ✅

- [x] `docs/SANDBOX_SLIM_IMPLEMENTATION.md` - 已创建
- [x] `docs/SANDBOX_SLIM_VERIFICATION.md` - 已创建
- [x] `docs/SANDBOX_SLIM_TEST_RESULTS.md` - 已创建
- [x] `docs/SANDBOX_SLIM_FINAL_SUMMARY.md` - 已创建
- [x] 项目记忆文档 `MEMORY.md` - 已更新

## 回归测试清单

### 核心功能 ✅

- [x] 沙箱容器启动
- [x] 健康检查
- [x] CDP 信息获取
- [x] 工具列表获取
- [x] Shell 命令执行
- [x] 截图功能

### 新功能 ✅

- [x] 文件列表
- [x] 文件读取
- [x] 文件写入
- [x] 文件创建目录
- [x] 文件重命名
- [x] 文件删除
- [x] 文件安全边界
- [x] CDP Screencast WebSocket

### 集成功能 ⏳

- [ ] Worker Manager 沙箱创建（需要 JWT）
- [ ] Worker Manager 沙箱销毁（需要 JWT）
- [ ] Gateway 文件代理（需要 JWT）
- [ ] AI Service 工具调用（需要完整环境）
- [ ] 前端 BrowserViewer（需要手动测试）
- [ ] 前端 FileExplorer（需要手动测试）

## 性能基准测试

### 镜像大小

```bash
docker images | grep newarch-sandbox
```

**目标**: < 800MB
**实际**: 715MB ✅

### 启动时间

```bash
time docker run --rm newarch-sandbox:v2 echo "ready"
```

**目标**: < 5s
**实际**: ~3s ✅

### 内存占用

```bash
docker stats --no-stream test-sb
```

**目标**: < 500MB
**实际**: 待测试 ⏳

### CPU 使用率

```bash
docker stats --no-stream test-sb
```

**目标**: < 10%
**实际**: 待测试 ⏳

## 故障排查

### 问题 1: 镜像构建失败

**症状**: Docker build 报错

**解决方案**:
```bash
# 清理 Docker 缓存
docker builder prune -a

# 重新构建
docker build --no-cache -t newarch-sandbox:v2 sandbox/
```

### 问题 2: 容器启动失败

**症状**: 容器立即退出

**解决方案**:
```bash
# 查看容器日志
docker logs test-sb

# 检查 entrypoint.sh 权限
docker run --rm newarch-sandbox:v2 ls -la /entrypoint.sh
```

### 问题 3: CDP 连接失败

**症状**: CDP 信息返回错误

**解决方案**:
```bash
# 检查 Chromium 进程
docker exec test-sb ps aux | grep chromium

# 检查 socat 端口转发
docker exec test-sb netstat -tlnp | grep 9222
```

### 问题 4: 文件 API 403 错误

**症状**: 所有文件操作返回 403

**解决方案**:
```bash
# 检查路径是否在白名单内
# 只允许 /home/sandbox 和 /tmp

# 测试允许的路径
curl "http://localhost:8000/files/list?path=/tmp"
```

## 验证完成标准

### 必须通过 ✅

- [x] 镜像大小 < 800MB
- [x] 启动时间 < 5s
- [x] 健康检查通过
- [x] 文件 API 全部正常
- [x] CDP 截图正常
- [x] AI Service 工具列表正确
- [x] 前端组件文件存在

### 推荐通过 ⏳

- [ ] Worker Manager 沙箱创建/销毁
- [ ] Gateway 文件代理
- [ ] 前端运行时测试
- [ ] 性能基准测试

### 可选通过

- [ ] WebSocket 代理实现
- [ ] 负载测试
- [ ] 安全审计

---

**检查清单版本**: v1.0

**最后更新**: 2026-02-20 22:15 (UTC+8)
