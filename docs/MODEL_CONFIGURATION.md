# 模型配置指南

## 概述

NewArch 支持多模型智能路由，根据任务类型自动选择最合适的模型。本文档涵盖模型配置、路由规则和端点设置。

## 环境变量配置

编辑 `.env` 文件：

```bash
# 豆包 API 配置（火山方舟）
DOUBAO_API_KEY=your_volcengine_api_key
DOUBAO_API_BASE=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-seed-1-6-vision-250815          # 默认模型
DOUBAO_GUI_MODEL=doubao-seed-1-6-vision-250815       # GUI 操作模型
DOUBAO_VISION_MODEL=doubao-seed-1-6-vision-250815    # 视觉分析模型
DOUBAO_EMBEDDING_MODEL=doubao-embedding-vision-251215 # Embedding 模型
DOUBAO_EMBEDDING_DIMENSIONS=2048                      # Embedding 维度

# DeepSeek API 配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# SiliconFlow API 配置（备用）
SILICONFLOW_API_KEY=your_siliconflow_api_key
SILICONFLOW_API_BASE=https://api.siliconflow.cn/v1
SILICONFLOW_VISION_MODEL=deepseek-ai/deepseek-vl2
```

## 火山方舟端点配置

### 基础模型 vs 推理接入点

```
基础模型（Base Model）
    -> 在火山方舟控制台创建推理接入点
推理接入点（Endpoint）
    -> 获得端点 ID（如 ep-20250203-abc123）
在代码中使用端点 ID
```

**重要**：代码中使用的是**推理接入点 ID**，不是基础模型名称。

### 创建推理接入点

1. 访问 [火山方舟控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint)
2. 点击「创建推理接入点」
3. 选择基础模型
4. 记录生成的端点 ID

### 推荐端点配置

| 用途 | 推荐基础模型 | 说明 |
|------|------------|------|
| GUI 操作 | doubao-1.5-ui-tars | 专为 GUI 交互设计，准确率最高 |
| 视觉分析 | doubao-pro-32k | 通用能力强，支持视觉 |
| Embedding | doubao-embedding-vision | 向量化，用于 Skill 检索 |

### 配置方案

#### 方案 1：完整配置（最佳性能）

```bash
DOUBAO_GUI_MODEL=ep-20250203-gui123       # GUI 专用端点
DOUBAO_VISION_MODEL=ep-20250203-vision456  # 视觉分析端点
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx       # 代码生成
```

#### 方案 2：单端点简化配置

```bash
DOUBAO_GUI_MODEL=ep-20250203-abc123
DOUBAO_VISION_MODEL=ep-20250203-abc123     # 复用同一端点
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

#### 方案 3：纯 DeepSeek（最简单）

```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
# 不配置豆包模型，所有任务使用 DeepSeek
# 注意：DeepSeek 不支持视觉任务
```

## 智能模型路由

### 任务类别与模型映射

| 类别 | 描述 | 默认模型 |
|------|------|---------|
| `gui_operation` | GUI 操作（点击、输入等） | DOUBAO_GUI_MODEL |
| `visual_analysis` | 视觉分析（理解截图） | DOUBAO_VISION_MODEL |
| `code_generation` | 代码生成 | deepseek-chat |
| `reasoning` | 复杂推理 | deepseek-reasoner |
| `general_chat` | 通用对话 | DOUBAO_VISION_MODEL |

### 路由模式

#### 关键词路由（默认，推荐）

```json
{ "use_llm_routing": false }
```

- 快速（无需调用 LLM）
- 免费（不消耗额外 API）
- 准确率 80-85%

**关键词规则**：

- GUI 操作：点击、双击、右键、输入、按键、滚动、拖拽、打开、关闭
- 视觉分析：看到、显示、截图、画面、界面、窗口、观察
- 代码生成：写代码、生成代码、实现、函数、类、方法
- 复杂推理：为什么、如何、分析、推理、解释

#### LLM 智能路由

```json
{ "use_llm_routing": true }
```

- 更准确（90%+）
- 理解复杂和模糊任务
- 额外延迟 100-200ms

#### 强制指定模型

```json
{ "force_model": "doubao-1.5-ui-tars-250328" }
```

### API 端点

```bash
# 智能路由聊天（SSE 流式）
POST /api/v1/ai/sandbox/smart/chat/stream

# LangGraph 多 Agent 聊天（SSE 流式）
POST /api/v1/ai/sandbox/smart/chat/langgraph/stream

# 双模式智能聊天（SSE 流式）
POST /api/v1/ai/sandbox/smart/chat/dual-mode/stream

# 任务分析（调试用）
POST /api/v1/ai/sandbox/smart/analyze-task

# 模式分析
POST /api/v1/ai/sandbox/smart/analyze-mode

# 模型列表
GET /api/v1/ai/sandbox/smart/models
```

### 请求参数

```json
{
  "user_id": "string",
  "message": "string",
  "include_screenshot": true,
  "use_llm_routing": false,
  "force_model": null,
  "max_steps": 15,
  "continuous": true,
  "use_langgraph": false,
  "max_iterations": 5,
  "force_mode": null
}
```

## 模型对比

| 模型 | 视觉 | GUI | 代码 | 推理 | 成本 |
|------|------|-----|------|------|------|
| doubao-1.5-ui-tars | 优 | 优 | 良 | 良 | 中 |
| doubao-pro-32k | 良 | 良 | 良 | 良 | 中 |
| deepseek-chat | 无 | 无 | 优 | 良 | 低 |
| deepseek-reasoner | 无 | 无 | 良 | 优 | 低 |

## 调试

### 检查环境变量

```bash
docker exec newarch-ai-service env | grep -E "DOUBAO|DEEPSEEK"
```

### 查看路由决策日志

```bash
docker-compose logs -f ai-service | grep -i "model\|endpoint\|error"
```

### 测试端点连通性

```bash
# 测试豆包端点
curl -X POST "https://ark.cn-beijing.volces.com/api/v3/chat/completions" \
  -H "Authorization: Bearer $DOUBAO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "your-endpoint-id", "messages": [{"role": "user", "content": "hello"}]}'

# 测试 DeepSeek
curl -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "hello"}]}'
```

### 常见错误

**"model does not exist"**：使用了基础模型名称而非推理接入点 ID。在火山方舟控制台创建推理接入点，使用返回的 `ep-*` ID。

**路由失败回退**：系统有多层后备 - LLM 路由失败回退到关键词路由，关键词路由失败回退到默认通用模型。

## 自定义路由规则

修改 `services/ai-service/src/core/model_router.py`：

```python
# 添加新的任务类别
class TaskCategory(str, Enum):
    DATA_ANALYSIS = "data_analysis"  # 新增

# 更新映射
TASK_MODEL_MAPPING = {
    TaskCategory.DATA_ANALYSIS: ModelType.DEEPSEEK_CHAT,
}

# 添加关键词
KEYWORD_RULES = {
    TaskCategory.DATA_ANALYSIS: [
        "数据分析", "统计", "图表", "可视化",
    ],
}
```
