# 模型配置指南

## 概述

GlassBox（历史名 NewArch）支持多模型路由，按任务类别选择模型。本文档依据 `services/ai-service/src/config/settings.py`、`services/ai-service/src/core/model_router.py` 与 `docker-compose.yml` 校正。

> **注意**：`docker-compose.yml` 会为 ai-service 注入 `DOUBAO_*` / `DEEPSEEK_*` 环境变量。未在 compose 中声明的变量（如 `SILICONFLOW_*`、`DOUBAO_EMBEDDING_DIMENSIONS`）需自行加入编排或本地运行时设置，否则使用代码默认值。

## 环境变量配置

编辑 `.env` 文件（`.env.example` 中的现有条目）：

```bash
# 豆包 API 配置（火山方舟）
DOUBAO_API_KEY=your_volcengine_api_key
DOUBAO_API_BASE=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-seed-1-8-251228              # 代码默认值
DOUBAO_GUI_MODEL=doubao-seed-1-8-251228          # 代码/compose 默认值（任务类别 gui_operation 使用）
DOUBAO_VISION_MODEL=doubao-seed-1-8-251228       # 代码/compose 默认值（视觉分析使用）
DOUBAO_EMBEDDING_MODEL=doubao-embedding-vision-251215  # 代码默认值（.env.example 中现为 doubao-embedding-vision-250615，两者不一致）
DOUBAO_EMBEDDING_DIMENSIONS=2048                 # 代码默认值（skill_embeddings 向量维度）

# DeepSeek API 配置（可选）
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# SiliconFlow API 配置（可选，代码支持但 compose 未注入）
SILICONFLOW_API_KEY=your_siliconflow_api_key
SILICONFLOW_API_BASE=https://api.siliconflow.cn/v1
SILICONFLOW_VISION_MODEL=deepseek-ai/deepseek-vl2
```

## 模型标识的写法

`settings.py` 中三个豆包模型的默认值是**模型名称**（如 `doubao-seed-1-8-251228`）而非推理接入点 ID。文档历史版本要求使用 `ep-*` 推理接入点 ID，这一点**未在当前代码中得到验证**；如果平台侧要求使用接入点 ID，直接把这些变量替换为对应的 `ep-*` 值即可（代码只是把变量值透传给 API），但具体填哪种形式需以火山方舟控制台当前要求为准。

## 智能模型路由

`core/model_router.py` 定义任务类别与模型映射。注意 `gui_operation` 是**任务类别标签**（由关键词触发，如「点击 / 滚动 / 输入」），落到 `DOUBAO_GUI_MODEL`，与沙箱内是否安装桌面环境无关——沙箱当前没有桌面环境，GUI 类操作由 browser-use 经 CDP 完成。

| 类别 | 描述 | 映射模型（代码） |
|------|------|------------------|
| `gui_operation` | 界面交互类任务 | `DOUBAO_GUI_MODEL`（未配置时回退到视觉模型） |
| `visual_analysis` | 视觉分析（理解截图） | `DOUBAO_VISION_MODEL`（未配置豆包时回退 SiliconFlow） |
| `code_generation` | 代码生成 | `deepseek-chat` |
| `reasoning` | 复杂推理 | `deepseek-reasoner` |
| `general_chat` | 通用对话 | `deepseek-chat` |

### 路由模式

#### 关键词路由（默认）

`ModelRouter.KEYWORD_RULES`（`core/model_router.py`）中的实际关键词：

- `gui_operation`：点击 / click / 双击 / 右键 / 输入 / type / 按键 / press / 滚动 / scroll / 拖拽 / drag / 打开 / open / 关闭 / close / 最大最小化 / 切换 / 选择
- `visual_analysis`：看到 / 显示 / 截图 / 画面 / 界面 / 窗口 / 内容 / what do you see / describe / analyze / 观察 / 屏幕
- `code_generation`：写代码 / 生成代码 / 实现 / 函数 / 类 / 方法 / write code / generate / implement / function / class
- `reasoning`：为什么 / 如何 / 分析 / 推理 / 解释 / 原因 / why / how / analyze / reason / explain

请求参数 `use_llm_routing: true` 时会额外调用 LLM 判断类别，失败则回退关键词路由。（历史文档中「关键词路由准确率 80-85%」「LLM 路由 90%+」等数字**未见代码或测试依据，已删除**。）

### API 端点

均经 Gateway（`gateway/internal/router/routes.go`）：

```bash
POST /api/v1/ai/sandbox/smart/chat/stream              # 智能路由聊天（SSE）
POST /api/v1/ai/sandbox/smart/chat/langgraph/stream    # LangGraph 多 Agent（SSE）
GET  /api/v1/ai/sandbox/smart/langgraph/state/:user_id/:session_id
POST /api/v1/ai/sandbox/smart/analyze-mode             # 模式分析（当前恒返回 AUTO）
POST /api/v1/ai/sandbox/smart/analyze-task             # 任务分析
POST /api/v1/ai/sandbox/smart/chat/dual-mode/stream    # 双模式兼容端点（SSE，仍走统一工具集）
GET  /api/v1/ai/sandbox/smart/models                   # 模型列表
```

### 请求参数（smart 系列，字段以 `smart_sandbox_routes.py` / `schemas.py` 为准）

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

`force_mode` 与 `force_model` 仍接受，但 `mode_router.py` 已统一返回 `AUTO`，`force_mode` 不再改变工具集。

## 模型对比

历史文档中的模型对比表（`doubao-1.5-ui-tars` / `doubao-pro-32k` / `deepseek-*` 的能力与成本）**无法从本仓库代码验证**，已删除。选型请以火山方舟 / DeepSeek 官方文档为准。

## 调试

```bash
# 查看 ai-service 实际生效的环境变量（容器内，8086 未发布到宿主）
docker exec newarch-ai-service env | grep -E "DOUBAO|DEEPSEEK|SILICONFLOW"

# 查看日志
docker compose logs -f ai-service

# 容器内健康检查
docker exec newarch-ai-service curl -s http://localhost:8086/health
```

### 常见问题

- **`DOUBAO_API_KEY` 未设置**：所有视觉/豆包相关能力不可用；`model_router.py` 的 `_determine_vision_provider()` 会按「豆包 → SiliconFlow → 兜底」顺序选择视觉模型，最终兜底值是硬编码的 `doubao-1-5-vision-pro-32k`
- **路由失败回退**：LLM 路由失败回退关键词路由，关键词路由无命中则走默认类别

## 自定义路由规则

修改 `services/ai-service/src/core/model_router.py`：

```python
# 添加新的任务类别
class TaskCategory(str, Enum):
    DATA_ANALYSIS = "data_analysis"  # 新增

# 更新映射（TASK_MODEL_MAPPING 构建于 ModelRouter.__init__ 内）
# 添加关键词
KEYWORD_RULES = {
    TaskCategory.DATA_ANALYSIS: [
        "数据分析", "统计", "图表", "可视化",
    ],
}
```

对应的 `ModelType` 枚举值也需一并补充。
