"""
集成模型路由的沙箱聊天路由
支持根据任务自动选择最合适的模型
支持连续思考和循环执行
支持 GUI/代码双模式智能路由
"""
import json
import os
import asyncio
import uuid
from typing import AsyncIterator, Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.sandbox import (
    SandboxClient,
    SANDBOX_TOOLS,
    execute_sandbox_tool,
)
from ..core.model_router import ModelRouter, TaskCategory, ModelType, ModelProvider
from ..core.multi_model_llm import MultiModelLLM
from ..core.mode_router import ModeRouter, OperationMode, get_mode_router
from ..core.skill import SkillSystemManager
from ..core.langfuse_client import is_langfuse_enabled, get_trace_url
from ..config.settings import settings

import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/sandbox/smart", tags=["sandbox-smart"])

# 初始化多模型客户端和路由器
multi_model_llm = MultiModelLLM()
model_router = ModelRouter(deepseek_client=multi_model_llm.clients.get("deepseek"))
mode_router = get_mode_router()

# 最大执行步数
MAX_STEPS = 15
# 工具执行后等待时间（毫秒）
TOOL_WAIT_MS = 1000

def _resolve_call_params(model_info: dict) -> dict:
    """将 select_model() 结果转换为实际调用参数。

    优先使用 doubao（视觉能力），只有当路由结果明确是 deepseek 且 client 可用时才用 deepseek。
    如果 deepseek client 不可用，回退到 doubao。
    """
    provider = model_info.get("provider", ModelProvider.DEEPSEEK)
    if isinstance(provider, ModelProvider):
        provider = provider.value

    # 判断各 client 是否可用
    has_doubao = multi_model_llm.doubao_client is not None
    has_deepseek = "deepseek" in multi_model_llm.clients

    if provider == "doubao" and has_doubao:
        model_name = os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-1-8-251228")
        return {"model_name": model_name, "provider": "doubao", "use_doubao": True}

    if provider == "deepseek" and has_deepseek:
        # 保留 select_model 返回的具体模型（deepseek-chat / deepseek-reasoner）
        raw_model = model_info.get("model", "")
        if isinstance(raw_model, str) and raw_model.startswith("deepseek"):
            model_name = raw_model
        else:
            model_name = "deepseek-chat"
        return {"model_name": model_name, "provider": "deepseek", "use_doubao": False}

    # 回退：deepseek 不可用 → doubao；doubao 不可用 → deepseek
    if has_doubao:
        model_name = os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-1-8-251228")
        return {"model_name": model_name, "provider": "doubao", "use_doubao": True}
    if has_deepseek:
        return {"model_name": "deepseek-chat", "provider": "deepseek", "use_doubao": False}

    # 都没有，给个默认值让后续报错更清晰
    return {"model_name": "deepseek-chat", "provider": "deepseek", "use_doubao": False}


def _strip_image_content(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """剥离消息中的 image_url 内容，用于发送给不支持视觉的模型（如 DeepSeek）。

    将多模态消息（content 为 list）中的 image_url 项移除，只保留文本。
    如果一条消息只剩文本，则将 content 从 list 简化为 str。
    """
    cleaned = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
            joined = "\n".join(t for t in text_parts if t)
            cleaned.append({**msg, "content": joined if joined else "(screenshot omitted)"})
        else:
            cleaned.append(msg)
    return cleaned


def _get_skill_selector():
    """从 SkillSystemManager 获取 SkillSelector"""
    return SkillSystemManager.get_instance().get_selector()


class SmartSandboxChatRequest(BaseModel):
    """智能沙箱聊天请求"""
    user_id: str
    message: str
    include_screenshot: bool = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    use_llm_routing: bool = False
    force_model: Optional[str] = None
    max_steps: int = MAX_STEPS  # 最大执行步数
    continuous: bool = True  # 是否连续执行直到任务完成
    force_mode: Optional[str] = None  # 强制操作模式: gui, code, auto


class ModelSelectionInfo(BaseModel):
    """模型选择信息"""
    selected_model: str
    task_category: str
    confidence: float
    reason: str


def _get_jwt_token(request: Request) -> Optional[str]:
    """从请求头中提取 JWT token"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def _get_sandbox_client(request: Request) -> SandboxClient:
    """创建沙箱客户端，传入 JWT token"""
    jwt_token = _get_jwt_token(request)
    if not jwt_token:
        from ..main import get_service_token
        jwt_token = get_service_token()
    return SandboxClient(jwt_token=jwt_token)


def _get_continuous_system_prompt() -> str:
    """获取支持连续执行的系统提示词"""
    return """你是一个强大的 AI 助手，可以通过操作用户的沙箱环境来帮助用户完成任务。
你可以执行命令、操作浏览器、管理文件。

## 核心能力
1. **智能浏览器操作** - 通过 CDP DOM 操作精准控制 Chromium 浏览器（推荐）
2. **命令执行** - 可以直接执行 Shell 命令
3. **文件管理** - 可以列出、读取、写入沙箱中的文件

## 可用工具
1. sandbox_browser_use - **智能浏览器操作**（推荐用于所有网页任务）
   参数：task (任务描述字符串), max_steps (可选，默认20)
   示例：{"tool": "sandbox_browser_use", "args": {"task": "打开百度搜索 browser-use"}}
   说明：使用 DOM 操作，准确率高，支持多标签页。
   适用场景：打开网站、登录、搜索、查看页面内容、填写表单等所有浏览器操作。

2. sandbox_shell - **直接执行命令**（推荐用于安装软件、文件操作等）
   参数：command (命令字符串)
   示例：{"tool": "sandbox_shell", "args": {"command": "ls -la"}}

3. sandbox_bash_execute - **持久化会话执行命令**（支持 cd、环境变量保持）
   参数：command (命令字符串), timeout (可选), wait_for_completion (可选)
   示例：{"tool": "sandbox_bash_execute", "args": {"command": "cd /home/sandbox && npm init -y"}}

4. sandbox_file_list - **列出目录内容**
   参数：path (目录路径，默认 /home/sandbox)
   示例：{"tool": "sandbox_file_list", "args": {"path": "/home/sandbox/workspace"}}

5. sandbox_file_read - **读取文件内容**
   参数：path (文件路径)
   示例：{"tool": "sandbox_file_read", "args": {"path": "/home/sandbox/workspace/main.py"}}

6. sandbox_file_write - **写入文件**
   参数：path (文件路径), content (内容), encoding (可选，默认 utf-8)
   示例：{"tool": "sandbox_file_write", "args": {"path": "/home/sandbox/workspace/hello.py", "content": "print('hello')"}}

7. sandbox_screenshot - **获取浏览器截图**（通过 CDP）
8. sandbox_wait - **等待指定时间**

## 重要规则
1. **浏览器/网页任务必须优先使用 sandbox_browser_use**，它通过 DOM 操作，准确率远高于其他方式。
2. **优先使用命令** - 能用 shell 命令完成的任务，优先用 sandbox_shell 或 sandbox_bash_execute
3. **文件操作** - 使用 sandbox_file_read/write 读写文件，比 shell 的 cat/echo 更可靠
4. **每次只执行一个操作** - 然后等待结果
5. **根据上一步结果调整** - 如果失败，尝试其他方法
6. **完成所有子任务** - 用户的消息可能包含多个子任务，你必须逐一完成所有子任务后才能标记 STATUS: COMPLETED
7. **需要用户介入时立即停下（最高优先级）** - 当判断任务需要以下操作时，**禁止调用任何工具**，必须直接输出文字说明 + STATUS: FAILED：
   - 需要登录（扫码、输入密码、短信验证码等）
   - 需要人机验证（滑块验证、图片验证码等）
   - 需要授权确认（OAuth 授权弹窗等）
   - 需要支付或敏感操作确认

## 输出格式
### 观察 (Observation)
描述当前状态

### 思考 (Thinking)
分析当前状态，思考下一步。回顾用户的原始任务，检查是否所有子任务都已完成。

### 决策 (Decision)
说明要执行的操作

### 工具调用 (Action)
**必须**输出以下 JSON 格式：
```json
{"tool": "工具名", "args": {"参数名": "参数值"}}
```

### 状态 (Status)
- 所有子任务全部完成：STATUS: COMPLETED
- 还有子任务未完成或需要继续：STATUS: CONTINUE
- 遇到无法解决的问题：STATUS: FAILED
- 需要用户手动操作（登录、验证码等）：STATUS: FAILED"""


def _check_task_status(content: str) -> str:
    """检查任务状态 - 只匹配显式状态标记，避免 LLM 思考内容误判"""
    content_upper = content.upper()
    if "STATUS: COMPLETED" in content_upper:
        return "completed"
    elif "STATUS: FAILED" in content_upper:
        return "failed"
    return "continue"


@router.post("/chat/stream")
async def smart_sandbox_chat_stream(request: SmartSandboxChatRequest, http_request: Request):
    """
    智能沙箱聊天接口（流式 SSE）
    支持连续思考和循环执行
    """

    async def generate() -> AsyncIterator[str]:
        try:
            # 创建 Langfuse root trace（如果启用）
            trace_id = None
            try:
                if is_langfuse_enabled():
                    from langfuse import get_client
                    langfuse = get_client()
                    trace = langfuse.trace(
                        name="sandbox-chat-stream",
                        metadata={"user_id": request.user_id, "task": request.message[:200]},
                    )
                    trace_id = trace.id
            except Exception:
                pass

            sandbox_client = _get_sandbox_client(http_request)
            sandbox = await sandbox_client.get_or_create_sandbox(request.user_id)

            yield f"data: {json.dumps({'type': 'sandbox_info', 'data': {'id': sandbox.id, 'screencast_url': sandbox.screencast_url, 'status': sandbox.status}})}\n\n"

            # 1. 选择模型（开头路由）
            if request.force_model:
                selected_model = request.force_model
                model_info = {
                    "model": selected_model,
                    "category": "forced",
                    "confidence": 1.0,
                    "reason": "User specified model"
                }
            else:
                model_info = await model_router.select_model(
                    task=request.message,
                    context={"has_screenshot": request.include_screenshot},
                    use_llm_routing=request.use_llm_routing
                )
                selected_model = model_info["model"]

            # 补充路由推理细节
            model_info["routing_method"] = "forced" if request.force_model else ("llm" if request.use_llm_routing else "keyword")
            model_info["task_preview"] = request.message[:100]
            yield f"data: {json.dumps({'type': 'model_selection', 'data': model_info})}\n\n"

            # 如果使用了 LLM 路由，发送 DeepSeek 的推理过程
            if model_info.get("llm_response") or model_info.get("llm_reasoning"):
                yield f"data: {json.dumps({'type': 'model_routing_reasoning', 'data': {'llm_response': model_info.get('llm_response', ''), 'llm_reasoning': model_info.get('llm_reasoning', ''), 'model': 'deepseek-chat'}})}\n\n"

            # 将路由结果转换为调用参数（每步可切换）
            call_params = _resolve_call_params(model_info)
            vision_model = os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-1-8-251228")

            # 记录初始路由选择到 Langfuse
            if trace_id:
                try:
                    from langfuse import get_client
                    langfuse = get_client()
                    root_trace = langfuse.trace(id=trace_id)
                    root_trace.span(
                        name="model-routing",
                        input={"task": request.message[:200], "method": model_info.get("routing_method", "keyword")},
                        output={"selected_model": call_params["model_name"], "provider": call_params["provider"], "category": model_info.get("category", ""), "confidence": model_info.get("confidence", 0)},
                    )
                except Exception:
                    pass

            # 获取模型配置
            try:
                model_config = model_router.get_model_config(ModelType(selected_model))
            except ValueError:
                model_config = {
                    "supports_vision": True,
                    "supports_tools": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "use_coordinate_mapping": False
                }

            # 2. 初始化对话历史（注入匹配的技能）
            system_prompt = _get_continuous_system_prompt()
            try:
                skill_sel = _get_skill_selector()
                if skill_sel:
                    matched_skills = await skill_sel.select(message=request.message, top_k=5)
                    if matched_skills:
                        # 发送技能检索详情
                        yield f"data: {json.dumps({'type': 'skill_retrieval_detail', 'data': {'query': request.message, 'matched_count': len(matched_skills), 'skills': [{'name': s['name'], 'description': s.get('description', ''), 'score': s.get('rerank_score', s.get('similarity', 0))} for s in matched_skills]}})}\n\n"
                        skills_text = "\n## 相关技能\n以下技能与当前任务相关，请优先参考：\n"
                        for sk in matched_skills:
                            steps_str = json.dumps(sk.get("steps", []), ensure_ascii=False)
                            skills_text += f"- {sk['name']}: {sk['description']}\n  步骤: {steps_str}\n"
                        system_prompt += "\n" + skills_text
                        yield f"data: {json.dumps({'type': 'skills_matched', 'data': {'count': len(matched_skills), 'skills': [s['name'] for s in matched_skills]}})}\n\n"
            except Exception:
                pass  # skill 查询失败不影响主流程
            messages = [{"role": "system", "content": system_prompt}]

            # 执行循环
            step = 0
            max_steps = min(request.max_steps, MAX_STEPS)
            task_status = "continue"
            action_history = []  # 记录执行历史：{"action": ..., "result": ..., "status": ...}

            while step < max_steps and task_status == "continue":
                step += 1
                yield f"data: {json.dumps({'type': 'step_start', 'data': {'step': step, 'max_steps': max_steps}})}\n\n"

                # 3. 获取截图（只有当前模型需要视觉时才截图）
                resize_info = None
                if request.include_screenshot and call_params["use_doubao"]:
                    try:
                        screenshot_data = await sandbox_client.get_screenshot_with_resize_info(request.user_id)
                        resize_info = screenshot_data
                        yield f"data: {json.dumps({'type': 'screenshot', 'data': {'step': step, 'width': screenshot_data['original_width'], 'height': screenshot_data['original_height']}})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'warning', 'data': {'message': f'Failed to get screenshot: {str(e)}'}})}\n\n"

                # 4. 构建用户消息
                if step == 1:
                    # 第一步：包含原始任务
                    user_content = f"任务：{request.message}"
                else:
                    # 后续步骤：包含历史和当前状态
                    def _format_history(hist: list) -> str:
                        lines = []
                        for i, h in enumerate(hist[-5:]):
                            status_icon = "✓" if h.get("status") == "success" else "✗"
                            result_summary = str(h.get("result", ""))[:100]
                            lines.append(f"- 步骤{i+1} [{status_icon}]: {h['action']}")
                            if result_summary:
                                lines.append(f"  结果: {result_summary}")
                        return "\n".join(lines)

                    history_text = _format_history(action_history)
                    last_status = action_history[-1].get("status", "unknown") if action_history else "none"

                    user_content = f"""继续执行完整任务：{request.message}

已执行的操作：
{history_text}

上一步状态：{last_status}
请回顾用户的完整任务描述，检查是否所有子任务都已完成。如果还有未完成的子任务，请继续执行下一步操作。只有当所有子任务都完成后才能标记 STATUS: COMPLETED。"""

                # 添加用户消息（带截图）
                if resize_info:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_content},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{resize_info['image']}"
                                }
                            }
                        ]
                    })
                else:
                    messages.append({"role": "user", "content": user_content})

                # 5. 调用模型（由 call_params 驱动）
                temperature = request.temperature if request.temperature is not None else model_config.get("temperature", 0.7)
                max_tokens = request.max_tokens if request.max_tokens is not None else model_config.get("max_tokens", 4096)

                full_content = ""
                tool_calls_map = {}

                if call_params["use_doubao"]:
                    # 使用豆包视觉模型
                    yield f"data: {json.dumps({'type': 'thinking_start', 'data': {'model': call_params['model_name'], 'step': step}})}\n\n"
                    yield f"data: {json.dumps({'type': 'llm_call_start', 'data': {'step': step, 'model': call_params['model_name'], 'provider': 'doubao', 'has_screenshot': bool(resize_info), 'purpose': 'analyze_and_decide'}})}\n\n"

                    try:
                        response = await multi_model_llm.doubao_client.chat(
                            messages=messages,
                            model=call_params["model_name"],
                            max_tokens=max_tokens,
                            trace_id=trace_id,
                            span_name=f"step-{step}-doubao",
                        )

                        full_content = response.get("content", "")
                        reasoning_content = response.get("reasoning", "")
                        resp_usage = response.get("usage", {})
                        tool_calls = []
                        if full_content:
                            from ..api.sandbox_routes import _parse_tool_calls_from_response
                            tool_calls = _parse_tool_calls_from_response(full_content)

                        yield f"data: {json.dumps({'type': 'llm_call_end', 'data': {'step': step, 'model': call_params['model_name'], 'has_tool_calls': bool(tool_calls), 'tool_calls_count': len(tool_calls), 'has_reasoning': bool(reasoning_content), 'content_length': len(full_content), 'usage': {'input_tokens': resp_usage.get('input_tokens') or resp_usage.get('prompt_tokens', 0), 'output_tokens': resp_usage.get('output_tokens') or resp_usage.get('completion_tokens', 0), 'total_tokens': resp_usage.get('total_tokens', 0)}, 'trace_url': get_trace_url(trace_id) if trace_id else None}})}\n\n"

                        yield f"data: {json.dumps({'type': 'thinking', 'data': {'step': step, 'content': full_content}})}\n\n"

                        if reasoning_content:
                            yield f"data: {json.dumps({'type': 'reasoning', 'data': {'step': step, 'content': reasoning_content}})}\n\n"

                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'data': {'message': f'Model call failed: {str(e)}'}})}\n\n"
                        break

                else:
                    # 使用 DeepSeek 流式调用
                    tools = SANDBOX_TOOLS if model_config.get("supports_tools") else None
                    stream_usage = {}

                    yield f"data: {json.dumps({'type': 'thinking_start', 'data': {'model': call_params['model_name'], 'step': step}})}\n\n"
                    yield f"data: {json.dumps({'type': 'llm_call_start', 'data': {'step': step, 'model': call_params['model_name'], 'provider': 'deepseek', 'has_screenshot': False, 'purpose': 'analyze_and_decide'}})}\n\n"

                    try:
                        # 剥离历史消息中的 image_url，DeepSeek 不支持视觉
                        clean_messages = _strip_image_content(messages)
                        async for chunk in multi_model_llm.stream_chat(
                            messages=clean_messages,
                            model=call_params["model_name"],
                            tools=tools,
                            tool_choice="auto" if tools else None,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            trace_id=trace_id,
                            name=f"step-{step}-deepseek",
                        ):
                            delta = chunk.get("delta", {})
                            content = delta.get("content")

                            if content:
                                full_content += content

                            # 捕获最终 chunk 的 usage
                            if chunk.get("usage"):
                                stream_usage = chunk["usage"]

                            # 累积 tool_calls
                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_map:
                                        tool_calls_map[idx] = {
                                            "id": tc.get("id", ""),
                                            "type": tc.get("type", "function"),
                                            "function": {"name": "", "arguments": ""}
                                        }
                                    if tc.get("function"):
                                        if tc["function"].get("name"):
                                            tool_calls_map[idx]["function"]["name"] += tc["function"]["name"]
                                        if tc["function"].get("arguments"):
                                            tool_calls_map[idx]["function"]["arguments"] += tc["function"]["arguments"]
                                    if tc.get("id"):
                                        tool_calls_map[idx]["id"] = tc["id"]

                        # 流式完成后一次性发送完整思考内容（避免前端碎片化）
                        if full_content:
                            yield f"data: {json.dumps({'type': 'thinking', 'data': {'step': step, 'content': full_content}})}\n\n"

                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'data': {'message': f'Model call failed: {str(e)}'}})}\n\n"
                        break

                    yield f"data: {json.dumps({'type': 'llm_call_end', 'data': {'step': step, 'model': call_params['model_name'], 'has_tool_calls': bool(tool_calls_map), 'tool_calls_count': len(tool_calls_map), 'has_reasoning': False, 'content_length': len(full_content), 'usage': stream_usage, 'trace_url': get_trace_url(trace_id) if trace_id else None}})}\n\n"

                yield f"data: {json.dumps({'type': 'thinking_end', 'data': {'step': step}})}\n\n"

                # 6. 检查任务状态
                task_status = _check_task_status(full_content)
                yield f"data: {json.dumps({'type': 'task_status', 'data': {'step': step, 'status': task_status}})}\n\n"

                if task_status != "continue":
                    break

                # 7. 解析并执行工具调用
                tool_calls = list(tool_calls_map.values())

                # 如果没有从流式响应中获取到工具调用，尝试从内容中解析
                if not tool_calls and full_content:
                    from ..api.sandbox_routes import _parse_tool_calls_from_response
                    tool_calls = _parse_tool_calls_from_response(full_content)

                if not tool_calls:
                    yield f"data: {json.dumps({'type': 'warning', 'data': {'message': 'No tool calls found in response'}})}\n\n"
                    # 如果没有工具调用但任务未完成，可能需要用户输入
                    if not request.continuous:
                        break
                    continue

                # 执行工具
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict) and "function" in tool_call:
                        tool_name = tool_call.get("function", {}).get("name", "")
                        tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                    else:
                        continue

                    try:
                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield f"data: {json.dumps({'type': 'tool_call', 'data': {'step': step, 'tool': tool_name, 'args': tool_args}})}\n\n"

                    # 执行工具
                    use_coordinate_mapping = model_config.get("use_coordinate_mapping", False)
                    try:
                        tool_result = await execute_sandbox_tool(
                            sandbox_client,
                            request.user_id,
                            tool_name,
                            tool_args,
                            resize_info if use_coordinate_mapping else None
                        )
                        yield f"data: {json.dumps({'type': 'tool_result', 'data': {'step': step, 'tool': tool_name, 'result': tool_result}})}\n\n"

                        # 记录执行历史（包含结果）
                        result_summary = tool_result.get("result", {}) if isinstance(tool_result, dict) else str(tool_result)
                        action_history.append({
                            "action": f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)})",
                            "result": result_summary,
                            "status": "success"
                        })

                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'tool_error', 'data': {'step': step, 'tool': tool_name, 'error': str(e)}})}\n\n"
                        # 记录失败历史
                        action_history.append({
                            "action": f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)})",
                            "result": str(e),
                            "status": "failed"
                        })

                # 8. 添加助手响应到历史
                messages.append({"role": "assistant", "content": full_content})

                # 9. 中途模型切换判断
                last_tool = ""
                if tool_calls:
                    last_tc = tool_calls[-1]
                    if isinstance(last_tc, dict) and "function" in last_tc:
                        last_tool = last_tc.get("function", {}).get("name", "")

                if last_tool:
                    if model_router.should_switch_to_vision(call_params["provider"], last_tool):
                        old_model = call_params["model_name"]
                        call_params = {"model_name": vision_model, "provider": "doubao", "use_doubao": True}
                        yield f"data: {json.dumps({'type': 'model_switch', 'data': {'from_model': old_model, 'to_model': vision_model, 'reason': 'GUI tool executed, need vision for next step', 'step': step}})}\n\n"
                    elif model_router.should_switch_to_text(call_params["provider"], last_tool):
                        old_model = call_params["model_name"]
                        call_params = {"model_name": "deepseek-chat", "provider": "deepseek", "use_doubao": False}
                        yield f"data: {json.dumps({'type': 'model_switch', 'data': {'from_model': old_model, 'to_model': 'deepseek-chat', 'reason': 'Code tool executed, vision not needed', 'step': step}})}\n\n"

                # 等待屏幕更新
                if request.continuous and step < max_steps:
                    await asyncio.sleep(TOOL_WAIT_MS / 1000)

                yield f"data: {json.dumps({'type': 'step_end', 'data': {'step': step}})}\n\n"

            # 输出最终状态
            yield f"data: {json.dumps({'type': 'execution_complete', 'data': {'total_steps': step, 'final_status': task_status, 'action_history': action_history}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze-task")
async def analyze_task(message: str, use_llm: bool = False):
    """分析任务类别（用于测试和调试）"""
    try:
        result = await model_router.select_model(
            task=message,
            use_llm_routing=use_llm
        )
        return {
            "success": True,
            "task": message,
            "analysis": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_available_models():
    """列出所有可用的模型"""
    models = {}
    task_model_mapping = model_router.get_task_model_mapping()

    for model_type in ModelType:
        config = model_router.get_model_config(model_type)
        models[model_type.value] = {
            "name": model_type.value,
            "config": config,
            "category": [
                cat.value for cat, m in task_model_mapping.items()
                if m == model_type
            ]
        }

    return {
        "success": True,
        "models": models,
        "task_categories": [cat.value for cat in TaskCategory]
    }


# ============ 操作模式路由 ============

@router.post("/analyze-mode")
async def analyze_operation_mode(message: str):
    """
    分析任务应该使用的操作模式
    返回 GUI 模式、代码模式或自动模式
    """
    try:
        decision = mode_router.select_mode(message)
        return {
            "success": True,
            "task": message,
            "mode": decision.mode.value,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "suggested_tools": decision.suggested_tools
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/dual-mode/stream")
async def dual_mode_chat_stream(request: SmartSandboxChatRequest, http_request: Request):
    """
    双模式智能聊天接口（流式 SSE）
    自动根据任务选择 GUI 或代码模式
    """

    async def generate() -> AsyncIterator[str]:
        try:
            # 创建 Langfuse root trace
            trace_id = None
            try:
                if is_langfuse_enabled():
                    from langfuse import get_client
                    langfuse = get_client()
                    trace = langfuse.trace(
                        name="sandbox-dual-mode-stream",
                        metadata={"user_id": request.user_id, "task": request.message[:200]},
                    )
                    trace_id = trace.id
            except Exception:
                pass

            sandbox_client = _get_sandbox_client(http_request)
            sandbox = await sandbox_client.get_or_create_sandbox(request.user_id)

            yield f"data: {json.dumps({'type': 'sandbox_info', 'data': {'id': sandbox.id, 'screencast_url': sandbox.screencast_url, 'status': sandbox.status}})}\n\n"

            # 1. 选择操作模式
            if request.force_mode:
                try:
                    selected_mode = OperationMode(request.force_mode)
                except ValueError:
                    selected_mode = OperationMode.AUTO
                mode_decision = {
                    "mode": selected_mode.value,
                    "confidence": 1.0,
                    "reason": "User specified mode",
                    "suggested_tools": mode_router._get_gui_tools() if selected_mode == OperationMode.GUI else mode_router._get_code_tools()
                }
            else:
                decision = mode_router.select_mode(
                    request.message,
                    context={"has_screenshot": request.include_screenshot}
                )
                selected_mode = decision.mode
                mode_decision = {
                    "mode": decision.mode.value,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    "suggested_tools": decision.suggested_tools
                }

            yield f"data: {json.dumps({'type': 'mode_selection', 'data': mode_decision})}\n\n"

            # 2. 选择模型
            if request.force_model:
                selected_model = request.force_model
                model_info = {
                    "model": selected_model,
                    "category": "forced",
                    "confidence": 1.0,
                    "reason": "User specified model"
                }
            else:
                model_info = await model_router.select_model(
                    task=request.message,
                    context={"has_screenshot": request.include_screenshot},
                    use_llm_routing=request.use_llm_routing
                )
                selected_model = model_info["model"]

            model_info["routing_method"] = "forced" if request.force_model else ("llm" if request.use_llm_routing else "keyword")
            model_info["task_preview"] = request.message[:100]
            yield f"data: {json.dumps({'type': 'model_selection', 'data': model_info})}\n\n"

            # 如果使用了 LLM 路由，发送 DeepSeek 的推理过程
            if model_info.get("llm_response") or model_info.get("llm_reasoning"):
                yield f"data: {json.dumps({'type': 'model_routing_reasoning', 'data': {'llm_response': model_info.get('llm_response', ''), 'llm_reasoning': model_info.get('llm_reasoning', ''), 'model': 'deepseek-chat'}})}\n\n"

            # 获取模型配置
            try:
                model_config = model_router.get_model_config(ModelType(selected_model))
            except ValueError:
                model_config = {
                    "supports_vision": True,
                    "supports_tools": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "use_coordinate_mapping": False
                }

            # 记录路由选择到 Langfuse
            if trace_id:
                try:
                    from langfuse import get_client
                    langfuse = get_client()
                    root_trace = langfuse.trace(id=trace_id)
                    root_trace.span(
                        name="dual-mode-routing",
                        input={"task": request.message[:200], "mode": mode_decision.get("mode", ""), "method": model_info.get("routing_method", "keyword")},
                        output={"selected_model": selected_model, "mode": mode_decision.get("mode", ""), "confidence": mode_decision.get("confidence", 0)},
                    )
                except Exception:
                    pass

            # 3. 根据模式获取系统提示词
            system_prompt = mode_router.get_mode_prompt(selected_mode)
            messages = [{"role": "system", "content": system_prompt}]

            # 执行循环
            step = 0
            max_steps = min(request.max_steps, MAX_STEPS)
            task_status = "continue"
            action_history = []
            current_mode = selected_mode

            while step < max_steps and task_status == "continue":
                step += 1
                yield f"data: {json.dumps({'type': 'step_start', 'data': {'step': step, 'max_steps': max_steps, 'mode': current_mode.value}})}\n\n"

                # 4. 根据模式决定是否获取截图
                resize_info = None
                if current_mode in [OperationMode.GUI, OperationMode.AUTO] and request.include_screenshot:
                    try:
                        screenshot_data = await sandbox_client.get_screenshot_with_resize_info(request.user_id)
                        resize_info = screenshot_data
                        yield f"data: {json.dumps({'type': 'screenshot', 'data': {'step': step, 'width': screenshot_data['original_width'], 'height': screenshot_data['original_height']}})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'warning', 'data': {'message': f'Failed to get screenshot: {str(e)}'}})}\n\n"

                # 5. 构建用户消息
                if step == 1:
                    user_content = f"任务：{request.message}"
                else:
                    def _format_history(hist: list) -> str:
                        lines = []
                        for i, h in enumerate(hist[-5:]):
                            status_icon = "✓" if h.get("status") == "success" else "✗"
                            result_summary = str(h.get("result", ""))[:100]
                            lines.append(f"- 步骤{i+1} [{status_icon}]: {h['action']}")
                            if result_summary:
                                lines.append(f"  结果: {result_summary}")
                        return "\n".join(lines)

                    history_text = _format_history(action_history)
                    last_status = action_history[-1].get("status", "unknown") if action_history else "none"

                    user_content = f"""继续执行完整任务：{request.message}

已执行的操作：
{history_text}

上一步状态：{last_status}
请回顾用户的完整任务描述，检查是否所有子任务都已完成。如果还有未完成的子任务，请继续执行下一步操作。只有当所有子任务都完成后才能标记 STATUS: COMPLETED。"""

                # 添加用户消息
                if resize_info and current_mode != OperationMode.CODE:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_content},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{resize_info['image']}"
                                }
                            }
                        ]
                    })
                else:
                    messages.append({"role": "user", "content": user_content})

                # 6. 调用模型
                temperature = request.temperature if request.temperature is not None else model_config.get("temperature", 0.7)
                max_tokens = request.max_tokens if request.max_tokens is not None else model_config.get("max_tokens", 4096)

                full_content = ""
                tool_calls_map = {}

                # 根据模式和截图选择调用方式
                if resize_info and current_mode != OperationMode.CODE and multi_model_llm.doubao_client:
                    vision_model = os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-1-8-251228")
                    yield f"data: {json.dumps({'type': 'thinking_start', 'data': {'model': vision_model, 'step': step, 'mode': current_mode.value}})}\n\n"
                    yield f"data: {json.dumps({'type': 'llm_call_start', 'data': {'step': step, 'model': vision_model, 'provider': 'doubao', 'has_screenshot': True, 'purpose': 'analyze_and_decide'}})}\n\n"

                    try:
                        response = await multi_model_llm.doubao_client.chat(
                            messages=messages,
                            model=vision_model,
                            max_tokens=max_tokens,
                            trace_id=trace_id,
                            span_name=f"step-{step}-doubao-dual",
                        )
                        full_content = response.get("content", "")
                        reasoning_content = response.get("reasoning", "")
                        resp_usage = response.get("usage", {})

                        yield f"data: {json.dumps({'type': 'llm_call_end', 'data': {'step': step, 'model': vision_model, 'has_tool_calls': False, 'tool_calls_count': 0, 'has_reasoning': bool(reasoning_content), 'content_length': len(full_content), 'usage': {'input_tokens': resp_usage.get('input_tokens') or resp_usage.get('prompt_tokens', 0), 'output_tokens': resp_usage.get('output_tokens') or resp_usage.get('completion_tokens', 0), 'total_tokens': resp_usage.get('total_tokens', 0)}, 'trace_url': get_trace_url(trace_id) if trace_id else None}})}\n\n"
                        yield f"data: {json.dumps({'type': 'thinking', 'data': {'step': step, 'content': full_content}})}\n\n"

                        if reasoning_content:
                            yield f"data: {json.dumps({'type': 'reasoning', 'data': {'step': step, 'content': reasoning_content}})}\n\n"

                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'data': {'message': f'Model call failed: {str(e)}'}})}\n\n"
                        break
                else:
                    tools = SANDBOX_TOOLS if model_config.get("supports_tools") else None
                    stream_usage = {}
                    yield f"data: {json.dumps({'type': 'thinking_start', 'data': {'model': 'deepseek-chat', 'step': step, 'mode': current_mode.value}})}\n\n"
                    yield f"data: {json.dumps({'type': 'llm_call_start', 'data': {'step': step, 'model': 'deepseek-chat', 'provider': 'deepseek', 'has_screenshot': False, 'purpose': 'analyze_and_decide'}})}\n\n"

                    try:
                        clean_messages = _strip_image_content(messages)
                        async for chunk in multi_model_llm.stream_chat(
                            messages=clean_messages,
                            model="deepseek-chat",
                            tools=tools,
                            tool_choice="auto" if tools else None,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            trace_id=trace_id,
                            name=f"step-{step}-deepseek-dual",
                        ):
                            delta = chunk.get("delta", {})
                            content = delta.get("content")

                            if content:
                                full_content += content

                            # 捕获最终 chunk 的 usage
                            if chunk.get("usage"):
                                stream_usage = chunk["usage"]

                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_map:
                                        tool_calls_map[idx] = {
                                            "id": tc.get("id", ""),
                                            "type": tc.get("type", "function"),
                                            "function": {"name": "", "arguments": ""}
                                        }
                                    if tc.get("function"):
                                        if tc["function"].get("name"):
                                            tool_calls_map[idx]["function"]["name"] += tc["function"]["name"]
                                        if tc["function"].get("arguments"):
                                            tool_calls_map[idx]["function"]["arguments"] += tc["function"]["arguments"]
                                    if tc.get("id"):
                                        tool_calls_map[idx]["id"] = tc["id"]

                        # 流式完成后一次性发送完整思考内容（避免前端碎片化）
                        if full_content:
                            yield f"data: {json.dumps({'type': 'thinking', 'data': {'step': step, 'content': full_content}})}\n\n"

                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'data': {'message': f'Model call failed: {str(e)}'}})}\n\n"
                        break

                    yield f"data: {json.dumps({'type': 'llm_call_end', 'data': {'step': step, 'model': 'deepseek-chat', 'has_tool_calls': bool(tool_calls_map), 'tool_calls_count': len(tool_calls_map), 'has_reasoning': False, 'content_length': len(full_content), 'usage': stream_usage, 'trace_url': get_trace_url(trace_id) if trace_id else None}})}\n\n"

                yield f"data: {json.dumps({'type': 'thinking_end', 'data': {'step': step}})}\n\n"

                # 7. 检查任务状态
                task_status = _check_task_status(full_content)
                yield f"data: {json.dumps({'type': 'task_status', 'data': {'step': step, 'status': task_status}})}\n\n"

                if task_status != "continue":
                    break

                # 8. 解析并执行工具调用
                tool_calls = list(tool_calls_map.values())

                if not tool_calls and full_content:
                    from ..api.sandbox_routes import _parse_tool_calls_from_response
                    tool_calls = _parse_tool_calls_from_response(full_content)

                if not tool_calls:
                    yield f"data: {json.dumps({'type': 'warning', 'data': {'message': 'No tool calls found in response'}})}\n\n"
                    if not request.continuous:
                        break
                    continue

                # 执行工具
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict) and "function" in tool_call:
                        tool_name = tool_call.get("function", {}).get("name", "")
                        tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                    else:
                        continue

                    try:
                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    except json.JSONDecodeError:
                        tool_args = {}

                    # 根据工具类型动态调整模式
                    tool_mode = _get_tool_mode(tool_name)
                    if tool_mode != current_mode and current_mode == OperationMode.AUTO:
                        current_mode = tool_mode
                        yield f"data: {json.dumps({'type': 'mode_switch', 'data': {'new_mode': current_mode.value, 'reason': f'Tool {tool_name} requires {current_mode.value} mode'}})}\n\n"

                    yield f"data: {json.dumps({'type': 'tool_call', 'data': {'step': step, 'tool': tool_name, 'args': tool_args, 'mode': current_mode.value}})}\n\n"

                    use_coordinate_mapping = model_config.get("use_coordinate_mapping", False)
                    try:
                        tool_result = await execute_sandbox_tool(
                            sandbox_client,
                            request.user_id,
                            tool_name,
                            tool_args,
                            resize_info if use_coordinate_mapping else None
                        )
                        yield f"data: {json.dumps({'type': 'tool_result', 'data': {'step': step, 'tool': tool_name, 'result': tool_result}})}\n\n"

                        result_summary = tool_result.get("result", {}) if isinstance(tool_result, dict) else str(tool_result)
                        action_history.append({
                            "action": f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)})",
                            "result": result_summary,
                            "status": "success",
                            "mode": current_mode.value
                        })

                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'tool_error', 'data': {'step': step, 'tool': tool_name, 'error': str(e)}})}\n\n"
                        action_history.append({
                            "action": f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)})",
                            "result": str(e),
                            "status": "failed",
                            "mode": current_mode.value
                        })

                messages.append({"role": "assistant", "content": full_content})

                if request.continuous and step < max_steps:
                    await asyncio.sleep(TOOL_WAIT_MS / 1000)

                yield f"data: {json.dumps({'type': 'step_end', 'data': {'step': step}})}\n\n"

            yield f"data: {json.dumps({'type': 'execution_complete', 'data': {'total_steps': step, 'final_status': task_status, 'final_mode': current_mode.value, 'action_history': action_history}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _get_tool_mode(tool_name: str) -> OperationMode:
    """根据工具名称判断操作模式"""
    gui_tools = {"sandbox_click", "sandbox_double_click", "sandbox_type", "sandbox_key",
                 "sandbox_scroll", "sandbox_move", "sandbox_drag", "sandbox_browser"}
    code_tools = {"sandbox_shell", "sandbox_bash_execute", "sandbox_terminal"}
    # browser-use 归为 AUTO，它自带 DOM 反馈，不需要视觉也不需要终端
    browser_use_tools = {"sandbox_browser_use"}

    if tool_name in gui_tools:
        return OperationMode.GUI
    elif tool_name in code_tools:
        return OperationMode.CODE
    elif tool_name in browser_use_tools:
        return OperationMode.AUTO
    else:
        return OperationMode.AUTO
