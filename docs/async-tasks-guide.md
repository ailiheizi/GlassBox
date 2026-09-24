# Async Tasks + Webhooks + Multi-Agent 功能

> ## ⚠️ 当前状态：HTTP 接口未接通（以代码为准）
>
> - `services/task-service/internal/handler/async_task_handler.go`（创建/查询/取消异步任务、查询 hooks、重试 hook、统计）与 `internal/repository/async_task_repo.go`、`internal/service/{hook_service,multi_agent_service}.go`、`internal/worker/{hook_worker,task_worker}.go`、`internal/queue/redis_queue.go` 均已实现。
> - 但 `services/task-service/cmd/server/main.go` **只注册了同步任务路由**（`/api/v1/tasks` 的 CRUD、start/complete/fail/cancel/progress/logs），**没有注册 `/tasks/async` 分组**，`AsyncTaskHandler` 未被实例化。
> - 与此同时，`gateway/internal/router/routes.go` 已经声明并向 task-service 转发 `/api/v1/tasks/async*`。
>
> 结论：**按本文档直接调用这些接口目前不会成功**。下面内容描述的是「已实现但未接线」的能力；接通方式（在 task-service 注册 async 路由）不在本次文档整理范围内。相关数据库表也需先手动执行迁移（见下）。
>
> 另外，本文档的响应示例、`agent_count` 上限、Webhook 事件列表等来自 handler 与迁移脚本代码，**未经端到端验证**。

## 概述

异步任务能力按设计包含：非阻塞任务执行、Webhook 回调通知、多 Agent 并行执行、进度追踪、结果聚合、失败重试（均可在上述 handler / worker / 迁移脚本中看到对应实现）。

## 快速开始

### 1. 运行数据库迁移

```bash
# 应用迁移脚本
psql -U postgres -d newarch -f infrastructure/docker/postgres/migrations/001_add_async_tasks.sql
```

### 2. 创建异步任务

```bash
curl -X POST http://localhost:8080/api/v1/tasks/async \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "agent_execution",
    "input": {
      "task": "Search for information about AI agents and summarize the findings",
      "enable_deep_reasoning": false
    },
    "agent_count": 3,
    "callback_url": "https://your-server.com/webhooks/task-complete",
    "callback_events": ["started", "progress", "completed", "failed"],
    "callback_headers": {
      "X-Custom-Header": "your-value",
      "Authorization": "Bearer webhook-secret"
    }
  }'
```

**响应示例：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "task_type": "agent_execution",
  "status": "pending",
  "progress": 0,
  "agent_count": 3,
  "created_at": "2026-01-27T10:00:00Z"
}
```

### 3. 查询任务状态

```bash
curl http://localhost:8080/api/v1/tasks/async/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**响应示例（运行中）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 66,
  "agent_count": 3,
  "agent_results": [
    {
      "agent_index": 0,
      "success": true,
      "duration": 5234,
      "data": {"result": "..."}
    },
    {
      "agent_index": 1,
      "success": true,
      "duration": 4892,
      "data": {"result": "..."}
    }
  ],
  "started_at": "2026-01-27T10:00:01Z"
}
```

**响应示例（已完成）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "agent_count": 3,
  "result": {
    "agent_count": 3,
    "success_count": 3,
    "failed_count": 0,
    "success_rate": 1.0,
    "average_duration_ms": 5012,
    "success": true,
    "primary_result": {"summary": "..."}
  },
  "started_at": "2026-01-27T10:00:01Z",
  "completed_at": "2026-01-27T10:00:16Z"
}
```

### 4. 列出任务

```bash
# 列出所有任务
curl http://localhost:8080/api/v1/tasks/async \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 按状态过滤
curl "http://localhost:8080/api/v1/tasks/async?status=running&limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 5. 取消任务

```bash
curl -X DELETE http://localhost:8080/api/v1/tasks/async/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Webhook 回调

### Webhook 事件类型

- `started` - 任务开始执行
- `progress` - 任务进度更新
- `completed` - 任务完成
- `failed` - 任务失败

### Webhook 负载格式

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "progress",
  "status": "running",
  "progress": 66,
  "timestamp": 1706349601,
  "data": {
    "completed_agents": 2,
    "total_agents": 3,
    "progress": 66,
    "failed_agents": 0
  }
}
```

### Webhook 安全验证

每个 webhook 请求都包含签名 header：

```
X-Webhook-Signature: <hmac-sha256-signature>
X-Webhook-Timestamp: <unix-timestamp>
X-Task-ID: <task-id>
X-Event: <event-type>
```

**验证示例（Python）：**

```python
import hmac
import hashlib
from flask import Flask, request

app = Flask(__name__)
WEBHOOK_SECRET = "your-webhook-secret"

def verify_webhook(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.route('/webhooks/task-complete', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data()

    if not verify_webhook(payload, signature):
        return 'Invalid signature', 401

    data = request.get_json()
    task_id = data['task_id']
    event = data['event']

    print(f"Task {task_id} event: {event}")

    if event == 'completed':
        result = data.get('result')
        print(f"Task completed with result: {result}")

    return 'OK', 200
```

### Webhook 重试机制

- 失败的 webhook 会自动重试（最多 3 次）
- 使用指数退避策略：1分钟、2分钟、4分钟
- 只有 5xx 错误会触发重试
- 可以手动重试失败的 webhooks

**手动重试：**

```bash
curl -X POST http://localhost:8080/api/v1/tasks/async/550e8400-e29b-41d4-a716-446655440000/retry \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 查看 Webhook 历史

```bash
curl http://localhost:8080/api/v1/tasks/async/550e8400-e29b-41d4-a716-446655440000/hooks \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**响应示例：**
```json
{
  "hooks": [
    {
      "id": "hook-1",
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "event": "started",
      "callback_url": "https://your-server.com/webhooks/task-complete",
      "response_status": 200,
      "retry_count": 0,
      "created_at": "2026-01-27T10:00:01Z"
    },
    {
      "id": "hook-2",
      "event": "progress",
      "response_status": 200,
      "retry_count": 0,
      "created_at": "2026-01-27T10:00:08Z"
    },
    {
      "id": "hook-3",
      "event": "completed",
      "response_status": 200,
      "retry_count": 0,
      "created_at": "2026-01-27T10:00:16Z"
    }
  ]
}
```

## 多 Agent 并行执行

### 配置 Agent 数量

通过 `agent_count` 参数指定并行执行的 agent 数量（1-10）：

```json
{
  "task_type": "agent_execution",
  "input": {"task": "Your task here"},
  "agent_count": 3
}
```

### 结果聚合策略

系统使用**多数投票**策略聚合结果：

- 如果超过一半的 agents 成功，任务标记为成功
- 返回所有 agents 的结果供分析
- 计算成功率、平均执行时间等统计信息

**聚合结果示例：**

```json
{
  "agent_count": 3,
  "success_count": 3,
  "failed_count": 0,
  "success_rate": 1.0,
  "average_duration_ms": 5012,
  "success": true,
  "aggregation_strategy": "majority_voting",
  "primary_result": {
    "summary": "AI agents are autonomous software entities..."
  },
  "agent_results": [
    {
      "agent_index": 0,
      "success": true,
      "duration": 5234,
      "data": {"result": "..."}
    },
    {
      "agent_index": 1,
      "success": true,
      "duration": 4892,
      "data": {"result": "..."}
    },
    {
      "agent_index": 2,
      "success": true,
      "duration": 4910,
      "data": {"result": "..."}
    }
  ]
}
```

## API 参考

### 创建异步任务

**POST** `/api/v1/tasks/async`

**请求体：**
```json
{
  "task_type": "agent_execution" | "workflow" | "reasoning",
  "input": {
    "task": "string",
    "enable_deep_reasoning": boolean,
    // ... other task-specific parameters
  },
  "agent_count": 1-10,  // 可选，默认 1
  "callback_url": "string",  // 可选
  "callback_events": ["started", "progress", "completed", "failed"],  // 可选
  "callback_headers": {  // 可选
    "key": "value"
  }
}
```

### 获取任务状态

**GET** `/api/v1/tasks/async/:id`

### 列出任务

**GET** `/api/v1/tasks/async?status=<status>&limit=<limit>&offset=<offset>`

**查询参数：**
- `status` - 过滤状态：pending, running, completed, failed, cancelled
- `limit` - 每页数量（默认 20，最大 100）
- `offset` - 偏移量（默认 0）

### 取消任务

**DELETE** `/api/v1/tasks/async/:id`

### 获取任务统计

**GET** `/api/v1/tasks/async/stats`

**响应示例：**
```json
{
  "stats": {
    "pending": 5,
    "running": 3,
    "completed": 142,
    "failed": 8,
    "cancelled": 2
  }
}
```

### 获取任务 Webhooks

**GET** `/api/v1/tasks/async/:id/hooks`

### 重试失败的 Webhooks

**POST** `/api/v1/tasks/async/:id/retry`

## 配置

### 环境变量

在 `docker-compose.yml` 中配置：

```yaml
task-service:
  environment:
    - ENABLE_ASYNC_TASKS=true
    - MAX_CONCURRENT_TASKS=100
    - TASK_WORKER_COUNT=5          # 后台工作器数量
    - WEBHOOK_TIMEOUT=10s
    - WEBHOOK_MAX_RETRIES=3
    - DEFAULT_AGENT_COUNT=1
    - MAX_AGENT_COUNT=10
```

## 监控和调试

### 查看队列状态

```bash
# 使用 Redis CLI
redis-cli

# 查看待处理任务数量
LLEN task_queue:pending

# 查看正在处理的任务
SMEMBERS task_queue:processing
```

### 查看日志

```bash
# Task service 日志
docker logs newarch-task-service -f

# 查看特定任务的日志
docker logs newarch-task-service 2>&1 | grep "task-id"
```

## 最佳实践

### 1. 选择合适的 Agent 数量

- **简单任务**：使用 1 个 agent
- **需要验证的任务**：使用 3 个 agents（多数投票）
- **关键任务**：使用 5-7 个 agents（更高可靠性）
- **避免**：超过 10 个 agents（资源消耗过大）

### 2. Webhook 最佳实践

- ✅ 使用 HTTPS 端点
- ✅ 验证签名
- ✅ 快速响应（< 5秒）
- ✅ 使用幂等处理（可能收到重复通知）
- ✅ 记录所有 webhook 请求
- ❌ 不要在 webhook 处理中执行长时间操作

### 3. 错误处理

- 检查任务状态和错误信息
- 使用 webhook 接收失败通知
- 查看 agent_results 了解具体失败原因
- 必要时重试任务

### 4. 性能优化

- 使用适当的 agent 数量（不是越多越好）
- 为频繁的查询添加缓存
- 定期清理旧任务和 webhook 记录
- 监控队列长度，必要时增加 workers

## 故障排查

### 任务一直处于 pending 状态

**原因：** Worker 未启动或队列阻塞

**解决：**
```bash
# 检查 worker 是否运行
docker logs newarch-task-service | grep "Starting task worker"

# 检查队列长度
redis-cli LLEN task_queue:pending

# 重启 task-service
docker restart newarch-task-service
```

### Webhook 未收到

**原因：** URL 不可达或签名验证失败

**解决：**
```bash
# 查看 webhook 历史
curl http://localhost:8080/api/v1/tasks/async/:id/hooks

# 检查失败的 webhooks
# 查看 response_status 和 response_body

# 手动重试
curl -X POST http://localhost:8080/api/v1/tasks/async/:id/retry
```

### Agent 执行失败

**原因：** Browser service 不可用或输入参数错误

**解决：**
```bash
# 检查 browser-service 状态
curl http://localhost:8084/health

# 查看任务详情中的错误信息
curl http://localhost:8080/api/v1/tasks/async/:id

# 查看 agent_results 中的具体错误
```

## 示例代码

### Node.js 客户端

```javascript
const axios = require('axios');

class AsyncTaskClient {
  constructor(baseURL, token) {
    this.client = axios.create({
      baseURL,
      headers: { 'Authorization': `Bearer ${token}` }
    });
  }

  async createTask(taskType, input, agentCount = 1, callbackURL = null) {
    const response = await this.client.post('/api/v1/tasks/async', {
      task_type: taskType,
      input,
      agent_count: agentCount,
      callback_url: callbackURL,
      callback_events: ['started', 'progress', 'completed', 'failed']
    });
    return response.data;
  }

  async getTask(taskId) {
    const response = await this.client.get(`/api/v1/tasks/async/${taskId}`);
    return response.data;
  }

  async waitForCompletion(taskId, pollInterval = 2000) {
    while (true) {
      const task = await this.getTask(taskId);

      if (task.status === 'completed') {
        return task.result;
      }

      if (task.status === 'failed') {
        throw new Error(task.error);
      }

      if (task.status === 'cancelled') {
        throw new Error('Task was cancelled');
      }

      console.log(`Progress: ${task.progress}%`);
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }
  }
}

// 使用示例
const client = new AsyncTaskClient('http://localhost:8080', 'YOUR_TOKEN');

async function main() {
  // 创建任务
  const task = await client.createTask(
    'agent_execution',
    { task: 'Search for AI agent information' },
    3  // 3 个并行 agents
  );

  console.log(`Task created: ${task.id}`);

  // 等待完成
  const result = await client.waitForCompletion(task.id);
  console.log('Result:', result);
}

main().catch(console.error);
```

### Python 客户端

```python
import requests
import time
from typing import Dict, Any, Optional

class AsyncTaskClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {'Authorization': f'Bearer {token}'}

    def create_task(
        self,
        task_type: str,
        input_data: Dict[str, Any],
        agent_count: int = 1,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        response = requests.post(
            f'{self.base_url}/api/v1/tasks/async',
            json={
                'task_type': task_type,
                'input': input_data,
                'agent_count': agent_count,
                'callback_url': callback_url,
                'callback_events': ['started', 'progress', 'completed', 'failed']
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def get_task(self, task_id: str) -> Dict[str, Any]:
        response = requests.get(
            f'{self.base_url}/api/v1/tasks/async/{task_id}',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def wait_for_completion(self, task_id: str, poll_interval: int = 2) -> Dict[str, Any]:
        while True:
            task = self.get_task(task_id)

            if task['status'] == 'completed':
                return task['result']

            if task['status'] == 'failed':
                raise Exception(task['error'])

            if task['status'] == 'cancelled':
                raise Exception('Task was cancelled')

            print(f"Progress: {task['progress']}%")
            time.sleep(poll_interval)

# 使用示例
client = AsyncTaskClient('http://localhost:8080', 'YOUR_TOKEN')

# 创建任务
task = client.create_task(
    'agent_execution',
    {'task': 'Search for AI agent information'},
    agent_count=3
)

print(f"Task created: {task['id']}")

# 等待完成
result = client.wait_for_completion(task['id'])
print(f"Result: {result}")
```

## 下一步

- [ ] 实现 Skill Auto-Selection（Sprint 1）
- [ ] 实现 UI-TARS Desktop Integration（Sprint 2）
- [ ] 实现 Interactive Reasoning（Sprint 3）
- [ ] 实现 Superpowers Workflow（Sprint 4）

查看完整实现计划：见 `docs/` 下相关设计文档。
