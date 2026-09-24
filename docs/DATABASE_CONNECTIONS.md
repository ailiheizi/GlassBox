# 数据库连接指南

直接连接 PostgreSQL、Redis 和 Milvus 查看数据的快速参考。

> 端口可访问性以 `docker-compose.yml` 为准：PostgreSQL 5432、Redis 6379、Milvus 19530 / 9091 **均已发布到宿主机**，可按下列方式直连。

---

## 建表来源

| 来源 | 涉及对象 |
|------|----------|
| `infrastructure/docker/postgres/init.sql`（postgres 容器首次初始化时执行） | `users`、`browser_sessions`、`chat_history`、`semantic_memories`、`memory_zones`、`zone_memories`、`system_indexes`、`ai_indexes`、`tasks`、`security_audit_logs` |
| `infrastructure/docker/postgres/migrations/001_add_async_tasks.sql` | `async_tasks`、`task_hooks`、`reasoning_trajectories`（**需手动执行，compose 不会自动应用**；且对应的 HTTP 接口当前未在 task-service 注册，见 [async-tasks-guide.md](./async-tasks-guide.md)） |
| `infrastructure/docker/postgres/migrations/002_add_indexes_and_constraints.sql` | 额外索引与约束（需手动执行） |
| task-service 启动时 GORM `AutoMigrate` | `tasks`、`task_steps`、`task_logs` |

因此新部署的库中，`async_tasks` / `task_hooks` / `reasoning_trajectories` 可能**不存在**（未执行迁移），使用前请先确认。

---

## PostgreSQL

### 连接信息

| 参数 | 值 |
|------|-----|
| Host | `localhost` |
| Port | `5432` |
| Database | `newarch` |
| Username | `postgres` |
| Password | `postgres` |

### 连接方式

```bash
# 本地 psql
psql -h localhost -p 5432 -U postgres -d newarch

# 通过容器
docker exec -it newarch-postgres psql -U postgres -d newarch
```

GUI 工具（DBeaver / Navicat / DataGrip）填入上述参数即可。

### 数据表

| 表名 | 说明 |
|------|------|
| `users` | 用户账号（UUID、用户名、邮箱、密码哈希） |
| `browser_sessions` | 浏览器会话（状态、metadata JSONB） |
| `chat_history` | 聊天记录（session_id、role、content、tool_calls） |
| `semantic_memories` | 语义记忆元数据（向量存 Milvus，这里存文本和元信息） |
| `memory_zones` | 记忆区域 |
| `zone_memories` | 区域内记忆条目 |
| `system_indexes` | 系统索引（预置网站，只读） |
| `ai_indexes` | AI 索引（用户创建，含 XPath/CSS 选择器） |
| `tasks` | 任务（状态、类型、输入输出） |
| `task_steps` / `task_logs` | 任务步骤与日志（由 GORM AutoMigrate 创建） |
| `async_tasks` | 异步任务（进度、回调、多 Agent 结果）——需先执行 migrations/001 |
| `task_hooks` | Webhook 回调记录——需先执行 migrations/001 |
| `reasoning_trajectories` | 推理轨迹（迭代状态、工具调用、置信度）——需先执行 migrations/001 |
| `security_audit_logs` | 安全审计日志 |

### 常用查询

```sql
-- 查看所有表
\dt

-- 查看表结构
\d users

-- 用户列表
SELECT id, username, email, created_at FROM users ORDER BY created_at DESC;

-- 最近聊天记录
SELECT session_id, role, LEFT(content, 100) AS preview, created_at
FROM chat_history ORDER BY created_at DESC LIMIT 20;

-- 语义记忆
SELECT id, user_id, content_type, LEFT(content, 80) AS preview, is_active, created_at
FROM semantic_memories ORDER BY created_at DESC LIMIT 20;

-- 任务列表
SELECT id, user_id, status, task_type, created_at
FROM tasks ORDER BY created_at DESC LIMIT 20;

-- 异步任务及进度
SELECT id, task_type, status, progress, agent_count, created_at
FROM async_tasks ORDER BY created_at DESC LIMIT 20;

-- 系统索引（预置网站）
SELECT service_name, title, url, tags FROM system_indexes WHERE is_active = true;

-- 浏览器会话
SELECT id, user_id, status, started_at, last_activity_at
FROM browser_sessions ORDER BY created_at DESC LIMIT 20;

-- 安全审计
SELECT user_id, action, tool_name, risk_level, created_at
FROM security_audit_logs ORDER BY created_at DESC LIMIT 20;

-- 推理轨迹
SELECT id, task_id, iteration, reasoning, confidence, timestamp
FROM reasoning_trajectories ORDER BY timestamp DESC LIMIT 20;
```

---

## Milvus

### 连接信息

| 参数 | 值 |
|------|-----|
| Host | `localhost` |
| Port | `19530` (gRPC) |
| Health Check | `http://localhost:9091/healthz` |

### 连接方式

**Python pymilvus：**

```bash
pip install pymilvus
```

```python
from pymilvus import connections, Collection, utility

connections.connect(host="localhost", port=19530)
print(utility.list_collections())
```

**Attu GUI：**

下载 [Attu](https://github.com/zilliztech/attu)，连接 `localhost:19530`，可视化浏览集合和数据。

### 集合一览

| 集合名 | 说明 | 向量维度 | 索引 | 所属服务 |
|--------|------|---------|------|---------|
| `skill_embeddings` | 技能向量（`builtin_skills.py` 中 7 个内置技能） | 2048 | HNSW（metric COSINE） | ai-service |
| `semantic_memories` | 语义记忆向量 | 1536 | IVF_FLAT（metric L2，nlist 128） | memory-service |

两个集合都由服务启动时自动创建（ai-service 的 `skill/milvus_client.py` 的 `ensure_collection`、memory-service 的 `milvus/client.go` 的 `ensureCollection`），Milvus 本身不含预置 schema。

### skill_embeddings 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT64 | 自增主键 |
| `skill_id` | VARCHAR(128) | 技能唯一标识（如 `open_browser`） |
| `name` | VARCHAR(256) | 技能名称（如 `打开浏览器`） |
| `description` | VARCHAR(1024) | 技能描述 |
| `category` | VARCHAR(64) | 分类：browser / system / development / file / observation |
| `steps_json` | VARCHAR(4096) | 执行步骤 JSON |
| `keywords` | VARCHAR(1024) | BM25 检索关键词 |
| `embedding` | FLOAT_VECTOR(2048) | 豆包 Embedding 向量 |

### semantic_memories 字段（memory-service 定义）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(64) | 主键（非自增，由应用生成） |
| `user_id` | VARCHAR(64) | 用户标识 |
| `embedding` | FLOAT_VECTOR(1536) | 记忆向量 |

### HNSW 索引参数（仅 `skill_embeddings`）

| 参数 | 值 |
|------|-----|
| M | 16 |
| efConstruction | 256 |
| ef (search) | 64 |
| metric_type | COSINE |

### 常用查询

```python
from pymilvus import connections, Collection, utility

connections.connect(host="localhost", port=19530)

# 列出所有集合
print("Collections:", utility.list_collections())

# ---- skill_embeddings ----
col = Collection("skill_embeddings")
col.load()
print(f"\nskill_embeddings: {col.num_entities} entities")

# 查看所有技能（不含向量）
results = col.query(
    expr='skill_id != ""',
    output_fields=["skill_id", "name", "description", "category", "keywords"],
    limit=50,
)
for r in results:
    print(f"  [{r['category']}] {r['skill_id']}: {r['name']}")
    print(f"    {r['description'][:60]}")
    print(f"    keywords: {r['keywords']}")

# 查看某个技能的执行步骤
import json
results = col.query(
    expr='skill_id == "open_browser"',
    output_fields=["skill_id", "name", "steps_json"],
    limit=1,
)
if results:
    steps = json.loads(results[0]["steps_json"])
    print(f"\n{results[0]['name']} 执行步骤:")
    for s in steps:
        print(f"  {s}")

# ---- semantic_memories ----
if "semantic_memories" in utility.list_collections():
    mem = Collection("semantic_memories")
    mem.load()
    print(f"\nsemantic_memories: {mem.num_entities} entities")

    # 查看 schema
    for field in mem.schema.fields:
        print(f"  {field.name}: {field.dtype}")

connections.disconnect("default")
```

---

## Redis

### 连接信息

| 参数 | 值 |
|------|-----|
| Host | `localhost` |
| Port | `6379` |
| Password | 无 |

### 连接方式

```bash
# 本地
redis-cli -h localhost -p 6379

# 通过容器
docker exec -it newarch-redis redis-cli
```

### 常用命令

```bash
KEYS *                          # 所有 key
TYPE <key>                      # key 类型
TTL <key>                       # 过期时间
LRANGE task_queue:pending 0 -1  # 待处理任务队列
SMEMBERS task_queue:processing  # 处理中任务集合
```

---

## 端口汇总

| 服务 | 端口 | 宿主机可访问 |
|------|------|-------------|
| PostgreSQL | 5432 | 是 |
| Redis | 6379 | 是 |
| Milvus gRPC | 19530 | 是 |
| Milvus Health | 9091 | 是 |
| Gateway | 8080 | 是 |
| Frontend | 3000 | 是 |
| Worker Manager | 9000 | 是 |
| auth / memory / index / browser / task / ai（8081-8086） | — | **否**，仅容器网络内（经 Gateway 访问） |
| 沙箱 Agent | 8000 | 仅 `127.0.0.1` 上的随机端口（由 Worker 动态映射） |
| 沙箱 CDP | 9222 | 否，仅 `sandbox-isolated` 网络内 |
