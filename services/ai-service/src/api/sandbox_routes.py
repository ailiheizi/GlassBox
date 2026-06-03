"""
沙箱 AI Agent 路由
支持 AI 在沙箱中执行工具操作
"""

import json
import re
import os
from typing import AsyncIterator, Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.sandbox import (
    SandboxClient,
    SANDBOX_TOOLS,
    execute_sandbox_tool,
)
from ..core.multi_model_llm import MultiModelLLM
from ..config.settings import settings

router = APIRouter(prefix="/sandbox", tags=["sandbox"])

# 初始化多模型 LLM 客户端
llm_client = MultiModelLLM()


def _get_system_prompt_with_tools() -> str:
    """获取包含工具说明的系统提示词"""
    return """你是一个 AI 助手，可以通过操作用户的虚拟桌面来帮助用户完成任务。
你可以看到屏幕截图，并使用工具来点击、输入、执行命令等。

可用工具：
1. sandbox_click(x, y) - 点击指定坐标
2. sandbox_double_click(x, y) - 双击指定坐标
3. sandbox_type(text) - 输入文本
4. sandbox_key(key) - 按键，如 enter, tab, ctrl+c
5. sandbox_scroll(amount, x, y) - 滚动，正数向上，负数向下
6. sandbox_shell(command) - 执行 Shell 命令
7. sandbox_browser(url) - 打开浏览器访问网址
8. sandbox_terminal(command) - 打开终端执行命令

重要提示：
1. 仔细观察截图，理解当前屏幕状态
2. 返回工具调用时，使用 JSON 格式：{"tool": "工具名", "args": {参数}}
3. 可以返回多个工具调用，用数组包裹
4. 先解释你看到了什么，再决定执行什么操作

输出格式示例：
我看到屏幕上有一个文本编辑器。我将点击文件菜单。
```json
{"tool": "sandbox_click", "args": {"x": 50, "y": 30}}
```"""


def _build_tool_prompt(message: str, screenshot_base64: str) -> str:
    """构建带截图的工具提示词"""
    return f"""用户请求：{message}

请分析截图并决定下一步操作。如果需要执行操作，请用 JSON 格式返回工具调用。"""


def _fix_malformed_json(raw: str) -> str:
    """尝试修复 LLM 输出的畸形 JSON。

    常见问题：
    - {"x": 578, "426"}  → 缺少 key，应为 {"x": 578, "y": 426}
    - {"425": "y", "x": 571} → key/value 反转
    """
    import re as _re

    # 修复 {"x": N, "M"} → {"x": N, "y": M}
    # 匹配 "x" 后面跟着一个孤立的数字字符串
    raw = _re.sub(
        r'"x"\s*:\s*(\d+)\s*,\s*"(\d+)"\s*}',
        r'"x": \1, "y": \2}',
        raw,
    )
    # 修复 {"y": N, "M"} → {"y": N, "x": M}
    raw = _re.sub(
        r'"y"\s*:\s*(\d+)\s*,\s*"(\d+)"\s*}',
        r'"y": \1, "x": \2}',
        raw,
    )
    # 修复 key/value 反转: {"425": "y", ...} → {"y": 425, ...}
    raw = _re.sub(
        r'"(\d+)"\s*:\s*"(x|y)"',
        lambda m: f'"{m.group(2)}": {m.group(1)}',
        raw,
    )
    return raw


def _parse_tool_calls_from_response(content: str) -> List[Dict[str, Any]]:
    """从模型响应中解析工具调用"""
    tool_calls = []

    # 匹配 ```json ... ``` 代码块
    json_pattern = r'```json\s*([\s\S]*?)\s*```'
    matches = re.findall(json_pattern, content)

    for match in matches:
        try:
            fixed = _fix_malformed_json(match)
            parsed = json.loads(fixed)
            # 支持单个工具调用或数组
            if isinstance(parsed, list):
                for item in parsed:
                    if "tool" in item:
                        tool_calls.append({
                            "id": f"call_{len(tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": item["tool"],
                                "arguments": json.dumps(item.get("args", {}))
                            }
                        })
            elif isinstance(parsed, dict) and "tool" in parsed:
                tool_calls.append({
                    "id": f"call_{len(tool_calls)}",
                    "type": "function",
                    "function": {
                        "name": parsed["tool"],
                        "arguments": json.dumps(parsed.get("args", {}))
                    }
                })
        except json.JSONDecodeError:
            continue

    # 如果没找到代码块，尝试直接解析 JSON
    if not tool_calls:
        try:
            # 尝试找到 {...} 格式
            json_obj_pattern = r'\{[^{}]*"tool"[^{}]*\}'
            obj_matches = re.findall(json_obj_pattern, content)
            for match in obj_matches:
                parsed = json.loads(match)
                if "tool" in parsed:
                    tool_calls.append({
                        "id": f"call_{len(tool_calls)}",
                        "type": "function",
                        "function": {
                            "name": parsed["tool"],
                            "arguments": json.dumps(parsed.get("args", {}))
                        }
                    })
        except:
            pass

    return tool_calls


class SandboxChatRequest(BaseModel):
    """沙箱聊天请求"""
    user_id: str
    message: str
    include_screenshot: bool = True
    temperature: float = 0.7
    max_tokens: int = 4096


class SandboxChatResponse(BaseModel):
    """沙箱聊天响应"""
    message: str
    tool_calls: list = []
    sandbox_info: Optional[dict] = None


def _get_jwt_token(request: Request) -> Optional[str]:
    """从请求头中提取 JWT token"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def _get_sandbox_client(request: Request) -> SandboxClient:
    """创建沙箱客户端，传入 JWT token"""
    # 优先使用请求中的 JWT token，如果没有则使用服务级别的 token
    jwt_token = _get_jwt_token(request)
    if not jwt_token:
        # 导入服务级别的 token
        from ..main import get_service_token
        jwt_token = get_service_token()
    return SandboxClient(jwt_token=jwt_token)


@router.post("/chat", response_model=SandboxChatResponse)
async def sandbox_chat(request: SandboxChatRequest, http_request: Request):
    """沙箱聊天接口 (非流式)"""
    try:
        sandbox_client = _get_sandbox_client(http_request)
        sandbox = await sandbox_client.get_or_create_sandbox(request.user_id)

        messages = [
            {
                "role": "system",
                "content": """你是一个 AI 助手，可以通过操作用户的虚拟桌面来帮助用户完成任务。
你可以看到屏幕截图，并使用工具来点击、输入、执行命令等。

重要提示：
1. 仔细观察截图，理解当前屏幕状态
2. 一步一步执行操作，每次操作后等待屏幕更新
3. 如果操作失败，尝试其他方法
4. 向用户解释你正在做什么"""
            }
        ]

        # 获取截图（带resize信息用于坐标映射）
        resize_info = None
        if request.include_screenshot:
            try:
                screenshot_data = await sandbox_client.get_screenshot_with_resize_info(request.user_id)
                resize_info = screenshot_data  # 保存resize信息供后续坐标映射使用

                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_data['image']}"
                            }
                        }
                    ]
                })
            except Exception:
                messages.append({"role": "user", "content": request.message})
        else:
            messages.append({"role": "user", "content": request.message})

        # 使用 DoubaoClient 调用视觉模型（/api/v3/responses 端点）
        # 注意：seed-1-6-vision 不支持 tools，需要在 prompt 中引导输出格式
        if request.include_screenshot and llm_client.doubao_client and resize_info:
            # 使用 chat_with_image 方法
            vision_model = os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-1-8-251228")
            prompt = f"{_get_system_prompt_with_tools()}\n\n用户请求：{request.message}\n\n请分析截图并决定下一步操作。"

            response_content = await llm_client.doubao_client.chat_with_image(
                prompt=prompt,
                image_base64=resize_info['image'],
                model=vision_model,
                max_tokens=request.max_tokens,
            )

            # 解析工具调用
            tool_calls = _parse_tool_calls_from_response(response_content)
            result = {
                "content": response_content,
                "tool_calls": tool_calls
            }
        else:
            result = await llm_client.chat(
                messages=messages,
                model="deepseek-chat",
                tools=SANDBOX_TOOLS,
                tool_choice="auto",
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

        tool_calls_results = []
        if result.get("tool_calls"):
            for tool_call in result["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])

                # 执行工具时传入resize信息用于坐标映射
                tool_result = await execute_sandbox_tool(
                    sandbox_client, request.user_id, tool_name, tool_args, resize_info
                )
                tool_calls_results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result
                })

        return SandboxChatResponse(
            message=result.get("content", ""),
            tool_calls=tool_calls_results,
            sandbox_info={
                "id": sandbox.id,
                "screencast_url": sandbox.screencast_url,
                "status": sandbox.status
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def sandbox_chat_stream(request: SandboxChatRequest, http_request: Request):
    """沙箱聊天接口 (流式 SSE)"""

    async def generate() -> AsyncIterator[str]:
        try:
            sandbox_client = _get_sandbox_client(http_request)
            sandbox = await sandbox_client.get_or_create_sandbox(request.user_id)

            yield f"data: {json.dumps({'type': 'sandbox_info', 'data': {'id': sandbox.id, 'screencast_url': sandbox.screencast_url, 'status': sandbox.status}})}\n\n"

            messages = [
                {
                    "role": "system",
                    "content": """你是一个 AI 助手，可以通过操作用户的虚拟桌面来帮助用户完成任务。
你可以看到屏幕截图，并使用工具来点击、输入、执行命令等。

重要提示：
1. 仔细观察截图，理解当前屏幕状态
2. 一步一步执行操作，每次操作后等待屏幕更新
3. 如果操作失败，尝试其他方法
4. 向用户解释你正在做什么"""
                }
            ]

            # 获取截图（带resize信息用于坐标映射）
            resize_info = None
            if request.include_screenshot:
                try:
                    screenshot_data = await sandbox_client.get_screenshot_with_resize_info(request.user_id)
                    resize_info = screenshot_data  # 保存resize信息供后续坐标映射使用

                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": request.message},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_data['image']}"
                                }
                            }
                        ]
                    })
                    yield f"data: {json.dumps({'type': 'screenshot', 'data': {'width': screenshot_data['original_width'], 'height': screenshot_data['original_height'], 'is_resized': screenshot_data['is_resized']}})}\n\n"
                except Exception as e:
                    messages.append({"role": "user", "content": request.message})
                    yield f"data: {json.dumps({'type': 'warning', 'data': {'message': f'Failed to get screenshot: {str(e)}'}})}\n\n"
            else:
                messages.append({"role": "user", "content": request.message})

            full_content = ""
            tool_calls_map = {}  # 用 index 作为 key 累积 tool_calls

            # 使用 DoubaoClient 调用视觉模型（非流式，因为 /api/v3/responses 不支持流式）
            if request.include_screenshot and llm_client.doubao_client and resize_info:
                vision_model = os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-1-8-251228")
                prompt = f"{_get_system_prompt_with_tools()}\n\n用户请求：{request.message}\n\n请分析截图并决定下一步操作。"

                response_content = await llm_client.doubao_client.chat_with_image(
                    prompt=prompt,
                    image_base64=resize_info['image'],
                    model=vision_model,
                    max_tokens=request.max_tokens,
                )

                full_content = response_content
                yield f"data: {json.dumps({'type': 'text', 'data': {'content': response_content}})}\n\n"

                # 解析工具调用
                tool_calls = _parse_tool_calls_from_response(response_content)
            else:
                # 使用 DeepSeek 流式调用（支持 tools）
                async for chunk in llm_client.stream_chat(
                    messages=messages,
                    model="deepseek-chat",
                    tools=SANDBOX_TOOLS,
                    tool_choice="auto",
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ):
                    delta = chunk.get("delta", {})
                    content = delta.get("content")

                    if content:
                        full_content += content
                        yield f"data: {json.dumps({'type': 'text', 'data': {'content': content}})}\n\n"

                    # 累积 tool_calls（流式返回时是分片的）
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {
                                    "id": tc.get("id", ""),
                                    "type": tc.get("type", "function"),
                                    "function": {"name": "", "arguments": ""}
                                }
                            # 累积 function name 和 arguments
                            if tc.get("function"):
                                if tc["function"].get("name"):
                                    tool_calls_map[idx]["function"]["name"] += tc["function"]["name"]
                                if tc["function"].get("arguments"):
                                    tool_calls_map[idx]["function"]["arguments"] += tc["function"]["arguments"]
                            if tc.get("id"):
                                tool_calls_map[idx]["id"] = tc["id"]

                # 转换为列表
                tool_calls = list(tool_calls_map.values())

            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")

                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_args = {}

                yield f"data: {json.dumps({'type': 'tool_call', 'data': {'tool': tool_name, 'args': tool_args}})}\n\n"

                # 执行工具时传入resize信息用于坐标映射
                tool_result = await execute_sandbox_tool(
                    sandbox_client, request.user_id, tool_name, tool_args, resize_info
                )

                yield f"data: {json.dumps({'type': 'tool_result', 'data': {'tool': tool_name, 'result': tool_result}})}\n\n"

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


@router.get("")
async def list_all_sandboxes(http_request: Request):
    """获取所有沙箱列表"""
    try:
        sandbox_client = _get_sandbox_client(http_request)
        # Call Worker Manager's list endpoint
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            headers = sandbox_client._get_headers("")
            response = await client.get(
                f"{sandbox_client.worker_url}/api/v1/sandboxes",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return {"sandboxes": data.get("sandboxes", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info/{user_id}")
async def get_sandbox_info(user_id: str, http_request: Request):
    """获取用户沙箱信息"""
    try:
        sandbox_client = _get_sandbox_client(http_request)
        sandbox = await sandbox_client.get_sandbox(user_id)
        if sandbox is None:
            raise HTTPException(status_code=404, detail="Sandbox not found")

        return {
            "id": sandbox.id,
            "user_id": sandbox.user_id,
            "status": sandbox.status,
            "agent_port": sandbox.agent_port,
            "screencast_url": sandbox.screencast_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create/{user_id}")
async def create_sandbox(user_id: str, http_request: Request):
    """创建用户沙箱"""
    try:
        sandbox_client = _get_sandbox_client(http_request)
        sandbox = await sandbox_client.get_or_create_sandbox(user_id)
        return {
            "id": sandbox.id,
            "user_id": sandbox.user_id,
            "status": sandbox.status,
            "agent_port": sandbox.agent_port,
            "screencast_url": sandbox.screencast_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/destroy/{user_id}")
async def destroy_sandbox(user_id: str, http_request: Request):
    """销毁用户沙箱"""
    try:
        sandbox_client = _get_sandbox_client(http_request)
        success = await sandbox_client.destroy_sandbox(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        return {"status": "destroyed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keepalive/{user_id}")
async def keepalive(user_id: str, http_request: Request):
    """心跳保活"""
    try:
        sandbox_client = _get_sandbox_client(http_request)
        success = await sandbox_client.keepalive(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        return {"status": "ok", "ttl": 1800}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/screenshot/{user_id}")
async def get_screenshot(user_id: str, http_request: Request):
    """获取沙箱截图"""
    try:
        sandbox_client = _get_sandbox_client(http_request)
        screenshot = await sandbox_client.get_screenshot(user_id)
        return {
            "image": screenshot.image,
            "width": screenshot.width,
            "height": screenshot.height,
            "timestamp": screenshot.timestamp,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/{user_id}")
async def execute_tool(user_id: str, tool: str = Query(...), params: dict = {}, http_request: Request = None):
    """执行沙箱工具"""
    try:
        sandbox_client = _get_sandbox_client(http_request) if http_request else SandboxClient()
        result = await execute_sandbox_tool(sandbox_client, user_id, f"sandbox_{tool}", params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
