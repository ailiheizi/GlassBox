"""
多模型 LLM 客户端
支持 SiliconFlow、DeepSeek、豆包（火山方舟）等多个 API 提供商
"""
import os
import json
import time
import asyncio
import hashlib
import logging
from typing import Dict, Any, Optional, List, AsyncIterator
from openai import AsyncOpenAI
import httpx

from .model_router import ModelProvider, ModelType, ModelRouter

logger = logging.getLogger(__name__)


def _get_async_openai_class():
    """获取 AsyncOpenAI 类，优先使用 Langfuse 包装版本以实现自动追踪。"""
    try:
        from .langfuse_client import is_langfuse_enabled
        if is_langfuse_enabled():
            from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
            return LangfuseAsyncOpenAI
    except Exception:
        pass
    return AsyncOpenAI


class DoubaoClient:
    """豆包/火山方舟专用客户端 - 使用 /api/v3/responses 端点"""

    def __init__(self, api_key: str, base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(120.0, connect=10.0)
        # 上下文缓存: cache_key -> context_id
        self._context_cache: Dict[str, str] = {}
        self._cache_lock = asyncio.Lock()

    async def _get_or_create_context(self, model: str, system_prompt: str) -> Optional[str]:
        """获取或创建上下文缓存，返回 context_id。

        通过缓存 system prompt，后续请求无需重复发送完整 prompt，节省 token。
        """
        cache_key = hashlib.md5(f"{model}:{system_prompt}".encode()).hexdigest()

        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        async with self._cache_lock:
            # 双重检查
            if cache_key in self._context_cache:
                return self._context_cache[cache_key]

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/context/create",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "system", "content": system_prompt}],
                            "ttl": 3600,
                        },
                    )
                    resp.raise_for_status()
                    context_id = resp.json().get("id")
                    if context_id:
                        self._context_cache[cache_key] = context_id
                        logger.info(f"[DoubaoClient] Context cache created: {context_id[:16]}...")
                        return context_id
            except Exception as e:
                logger.debug(f"[DoubaoClient] Context cache creation failed (will send full messages): {e}")
            return None

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """调用 Doubao /api/v3/responses 端点，支持上下文缓存"""
        start_time = time.time()

        # 尝试提取 system prompt 用于上下文缓存
        system_msg = None
        other_msgs = []
        for msg in messages:
            if msg.get("role") == "system" and system_msg is None:
                system_msg = msg
            else:
                other_msgs.append(msg)

        context_id = None
        if system_msg:
            context_id = await self._get_or_create_context(model, system_msg["content"])

        # 如果有缓存，只发送非 system 消息；否则发送全部
        msgs_to_send = other_msgs if context_id else messages
        input_messages = self._convert_messages(msgs_to_send)

        payload = {
            "model": model,
            "input": input_messages,
            "max_output_tokens": max_tokens,
        }
        if context_id:
            payload["context_id"] = context_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        # 解析响应 - 只提取 completed 状态的 message
        content = ""
        for output in data.get("output", []):
            if output.get("type") == "message" and output.get("status") == "completed":
                for c in output.get("content", []):
                    if c.get("type") == "output_text":
                        content += c.get("text", "")

        usage = data.get("usage", {})
        trace_id = kwargs.get("trace_id")
        span_name = kwargs.get("span_name")
        self._log_generation(
            model=model, input_messages=messages, output=content,
            usage=usage, latency_ms=int((time.time() - start_time) * 1000),
            trace_id=trace_id, span_name=span_name,
            extra_metadata={"context_id": context_id} if context_id else None,
        )

        return {
            "content": content,
            "role": "assistant",
            "finish_reason": "stop" if data.get("status") == "completed" else None,
            "usage": usage,
            "context_id": context_id,
        }

    async def chat_with_image(
        self,
        prompt: str,
        image_base64: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        trace_id: Optional[str] = None,
    ) -> str:
        """带图像的对话"""
        start_time = time.time()
        input_messages = [{
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": f"data:image/png;base64,{image_base64}"},
                {"type": "input_text", "text": prompt}
            ]
        }]

        payload = {
            "model": model,
            "input": input_messages,
            "max_output_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        # 解析响应 - 只提取 completed 状态的 message
        content = ""
        for output in data.get("output", []):
            if output.get("type") == "message" and output.get("status") == "completed":
                for c in output.get("content", []):
                    if c.get("type") == "output_text":
                        content += c.get("text", "")

        self._log_generation(
            model=model,
            input_messages=[{"role": "user", "content": f"[image] {prompt[:100]}"}],
            output=content,
            usage=data.get("usage", {}),
            latency_ms=int((time.time() - start_time) * 1000),
            trace_id=trace_id,
        )

        return content

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 OpenAI 格式的 messages 转换为 Doubao 格式"""
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, str):
                # 纯文本消息
                result.append({
                    "role": role,
                    "content": [{"type": "input_text", "text": content}]
                })
            elif isinstance(content, list):
                # 多模态消息
                converted_content = []
                for item in content:
                    if item.get("type") == "text":
                        converted_content.append({"type": "input_text", "text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        image_url = item.get("image_url", {})
                        url = image_url.get("url", "") if isinstance(image_url, dict) else image_url
                        converted_content.append({"type": "input_image", "image_url": url})
                result.append({"role": role, "content": converted_content})

        return result

    @staticmethod
    def _sanitize_messages_for_log(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将消息中的 base64 图片替换为占位标记，保留完整结构用于 Langfuse 记录。"""
        result = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                sanitized = []
                for item in content:
                    if item.get("type") == "image_url":
                        image_url = item.get("image_url", {})
                        url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url)
                        if url.startswith("data:"):
                            # base64 data URI → 只保留 MIME 类型
                            mime = url.split(";")[0] if ";" in url else url[:30]
                            sanitized.append({"type": "image_url", "image_url": f"[{mime}, base64 omitted]"})
                        else:
                            sanitized.append(item)
                    else:
                        sanitized.append(item)
                result.append({**msg, "content": sanitized})
            else:
                result.append(msg)
        return result

    def _log_generation(self, model, input_messages, output, usage, latency_ms, trace_id=None, span_name=None, extra_metadata=None):
        """将 generation 记录到 Langfuse（如果启用）。

        当提供 trace_id 时，在已有 trace 下创建子 generation（而非新建 trace）。
        """
        try:
            from .langfuse_client import is_langfuse_enabled
            if not is_langfuse_enabled():
                return
            from langfuse import get_client
            langfuse = get_client()

            gen_name = span_name or f"doubao-{model}"
            safe_input = self._sanitize_messages_for_log(input_messages)

            metadata = {"provider": "doubao", "endpoint": "/api/v3/responses", "latency_ms": latency_ms}
            if extra_metadata:
                metadata.update(extra_metadata)

            gen_kwargs = dict(
                name=gen_name,
                model=model,
                input=safe_input,
                output=output[:2000] if output else "",
                usage={
                    "input": usage.get("input_tokens") or usage.get("prompt_tokens", 0),
                    "output": usage.get("output_tokens") or usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                },
                metadata=metadata,
            )

            if trace_id:
                trace = langfuse.trace(id=trace_id)
            else:
                trace = langfuse.trace(name=gen_name, metadata={"provider": "doubao"})

            trace.generation(**gen_kwargs)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"[Langfuse] _log_generation failed: {e}")


class MultiModelLLM:
    """多模型 LLM 客户端"""

    def __init__(self):
        """初始化多模型客户端"""
        self.clients: Dict[str, AsyncOpenAI] = {}
        self.doubao_client: Optional[DoubaoClient] = None  # 豆包专用客户端
        self.router = ModelRouter()
        self._init_clients()

    def _init_clients(self):
        """初始化各个模型的客户端"""
        from ..config.settings import settings

        OpenAIClass = _get_async_openai_class()

        # 豆包/火山引擎客户端（使用专用 DoubaoClient）
        doubao_api_key = settings.doubao_api_key or os.getenv("DOUBAO_API_KEY")
        doubao_base_url = settings.doubao_api_base or os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")

        if doubao_api_key:
            self.doubao_client = DoubaoClient(
                api_key=doubao_api_key,
                base_url=doubao_base_url,
            )
            # 同时保留 OpenAI 兼容客户端用于其他操作
            self.clients["doubao"] = OpenAIClass(
                api_key=doubao_api_key,
                base_url=doubao_base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )

        # DeepSeek 客户端
        deepseek_api_key = settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        deepseek_base_url = settings.deepseek_api_base or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")

        if deepseek_api_key:
            self.clients["deepseek"] = OpenAIClass(
                api_key=deepseek_api_key,
                base_url=deepseek_base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )

        # SiliconFlow 客户端（备用）
        siliconflow_api_key = settings.siliconflow_api_key or os.getenv("SILICONFLOW_API_KEY")
        siliconflow_base_url = settings.siliconflow_api_base or os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")

        if siliconflow_api_key:
            self.clients["siliconflow"] = OpenAIClass(
                api_key=siliconflow_api_key,
                base_url=siliconflow_base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )

    def reinit_clients(self):
        """Langfuse 初始化后重新创建客户端，以启用自动追踪。"""
        logger.info("[MultiModelLLM] Reinitializing clients with Langfuse tracing")
        self._init_clients()

    def _get_client_for_provider(self, provider: ModelProvider) -> Optional[AsyncOpenAI]:
        """根据提供商获取客户端"""
        return self.clients.get(provider.value)

    def _get_client_for_model(self, model: str) -> Optional[AsyncOpenAI]:
        """根据模型名称获取对应的客户端"""
        model_lower = model.lower()

        # 豆包模型（直接使用 Model ID）
        if "doubao" in model_lower or "ui-tars" in model_lower or model.startswith("ep-"):
            return self.clients.get("doubao")

        # DeepSeek 模型
        if "deepseek-chat" in model_lower or "deepseek-reasoner" in model_lower:
            return self.clients.get("deepseek")

        # SiliconFlow 模型
        if "deepseek-vl" in model_lower or "qwen" in model_lower.replace("-", ""):
            return self.clients.get("siliconflow")

        # 默认使用豆包
        return self.clients.get("doubao") or self.clients.get("deepseek")

    def get_vision_client_and_model(self) -> tuple[Optional[AsyncOpenAI], str]:
        """获取视觉模型的客户端和模型名称"""
        # 优先使用豆包
        if "doubao" in self.clients:
            doubao_vision = os.getenv("DOUBAO_VISION_MODEL", "doubao-1-5-vision-pro-32k")
            doubao_gui = os.getenv("DOUBAO_GUI_MODEL", "doubao-1-5-ui-tars-250328")
            return self.clients["doubao"], doubao_vision or doubao_gui

        # 备用 SiliconFlow
        if "siliconflow" in self.clients:
            return self.clients["siliconflow"], os.getenv("SILICONFLOW_VISION_MODEL", "deepseek-ai/deepseek-vl2")

        return None, ""

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用指定模型进行对话

        Args:
            messages: 消息列表
            model: 模型名称
            tools: 工具列表
            tool_choice: 工具选择策略
            temperature: 温度
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            模型响应
        """
        client = self._get_client_for_model(model)
        if not client:
            raise ValueError(f"No client available for model: {model}. Check your API key configuration.")

        # 构建请求参数
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        # 只有支持工具的模型才添加 tools 参数
        if tools and self._model_supports_tools(model):
            request_params["tools"] = tools
            request_params["tool_choice"] = tool_choice

        # 调用模型
        response = await client.chat.completions.create(**request_params)

        # 解析响应
        choice = response.choices[0]
        result = {
            "content": choice.message.content or "",
            "role": choice.message.role,
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
        }

        # 处理工具调用
        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in choice.message.tool_calls
            ]

        return result

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式调用指定模型

        Args:
            messages: 消息列表
            model: 模型名称
            tools: 工具列表
            tool_choice: 工具选择策略
            temperature: 温度
            max_tokens: 最大 token 数
            **kwargs: 支持 trace_id / name 用于 Langfuse 嵌套

        Yields:
            流式响应块
        """
        # 从 kwargs 提取 Langfuse 参数，不传给 OpenAI SDK
        trace_id = kwargs.pop("trace_id", None)
        span_name = kwargs.pop("name", None)

        client = self._get_client_for_model(model)
        if not client:
            raise ValueError(f"No client available for model: {model}")

        # 构建请求参数
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            **kwargs
        }

        # 只有支持工具的模型才添加 tools 参数
        if tools and self._model_supports_tools(model):
            request_params["tools"] = tools
            request_params["tool_choice"] = tool_choice

        # 如果有 trace_id 且 Langfuse 启用，创建嵌套 span 作为当前 observation
        langfuse_span = None
        if trace_id and span_name:
            try:
                from .langfuse_client import is_langfuse_enabled
                if is_langfuse_enabled():
                    from langfuse import get_client
                    langfuse = get_client()
                    trace = langfuse.trace(id=trace_id)
                    langfuse_span = trace.span(name=span_name)
            except Exception:
                pass

        # 流式调用（在 span 上下文内，使 LangfuseAsyncOpenAI 自动嵌套）
        if langfuse_span:
            with langfuse_span.start_as_current_observation():
                async for chunk_result in self._iter_stream(client, request_params):
                    yield chunk_result
            langfuse_span.end()
        else:
            async for chunk_result in self._iter_stream(client, request_params):
                yield chunk_result

    async def _iter_stream(
        self, client: AsyncOpenAI, request_params: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """内部方法：执行流式调用并逐 chunk 解析。"""
        stream = await client.chat.completions.create(**request_params)

        async for chunk in stream:
            if not chunk.choices:
                if hasattr(chunk, 'usage') and chunk.usage:
                    yield {
                        "delta": {},
                        "finish_reason": None,
                        "usage": {
                            "prompt_tokens": chunk.usage.prompt_tokens or 0,
                            "completion_tokens": chunk.usage.completion_tokens or 0,
                            "total_tokens": chunk.usage.total_tokens or 0,
                        },
                    }
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            result = {
                "delta": {},
                "finish_reason": choice.finish_reason,
            }

            if hasattr(chunk, 'usage') and chunk.usage:
                result["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens or 0,
                    "completion_tokens": chunk.usage.completion_tokens or 0,
                    "total_tokens": chunk.usage.total_tokens or 0,
                }

            if delta.content:
                result["delta"]["content"] = delta.content

            if delta.tool_calls:
                result["delta"]["tool_calls"] = [
                    {
                        "index": tc.index,
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name if tc.function else None,
                            "arguments": tc.function.arguments if tc.function else None,
                        }
                    }
                    for tc in delta.tool_calls
                ]

            yield result

    def _model_supports_tools(self, model: str) -> bool:
        """判断模型是否支持工具调用"""
        model_lower = model.lower()
        # DeepSeek Reasoner 不支持工具
        if "reasoner" in model_lower:
            return False
        # 视觉模型通常不支持工具
        if "vl" in model_lower or "vision" in model_lower:
            return False
        return True

    def _model_supports_vision(self, model: str) -> bool:
        """判断模型是否支持视觉"""
        model_lower = model.lower()
        # DeepSeek chat/reasoner 不支持视觉
        if model_lower in ["deepseek-chat", "deepseek-reasoner"]:
            return False
        # 视觉模型
        if "vl" in model_lower or "vision" in model_lower:
            return True
        # 豆包 GUI 模型支持视觉
        if "ui-tars" in model_lower or model.startswith("ep-"):
            return True
        return False

    async def chat_with_image(
        self,
        prompt: str,
        image_base64: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        带图像的对话 - 使用 Doubao /api/v3/responses 端点

        Args:
            prompt: 提示词
            image_base64: base64 编码的图像
            model: 模型名称（可选，不指定则使用默认视觉模型）
            temperature: 温度
            max_tokens: 最大 token 数

        Returns:
            模型响应文本
        """
        # 优先使用 DoubaoClient（支持 /api/v3/responses 端点）
        if self.doubao_client:
            if not model:
                model = os.getenv("DOUBAO_VISION_MODEL", "doubao-seed-1-8-251228")
            return await self.doubao_client.chat_with_image(
                prompt=prompt,
                image_base64=image_base64,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # 回退到 OpenAI 兼容客户端（SiliconFlow 等）
        if not model:
            client, model = self.get_vision_client_and_model()
            if not client:
                raise ValueError("No vision model available. Please configure DOUBAO_API_KEY or SILICONFLOW_API_KEY.")
        else:
            client = self._get_client_for_model(model)
            if not client:
                raise ValueError(f"No client available for model: {model}")

        if not self._model_supports_vision(model):
            raise ValueError(f"Model {model} does not support vision")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""

    async def analyze_screenshot(
        self,
        image_base64: str,
        task: str = "描述这个截图的内容",
    ) -> str:
        """
        分析截图

        Args:
            image_base64: base64 编码的截图
            task: 分析任务描述

        Returns:
            分析结果
        """
        return await self.chat_with_image(
            prompt=task,
            image_base64=image_base64,
            temperature=0.3,
            max_tokens=2048,
        )

    def get_available_providers(self) -> Dict[str, bool]:
        """获取可用的提供商状态"""
        return {
            "siliconflow": "siliconflow" in self.clients,
            "deepseek": "deepseek" in self.clients,
            "doubao": "doubao" in self.clients,
        }

    def get_default_chat_model(self) -> str:
        """获取默认的聊天模型"""
        if "doubao" in self.clients:
            return os.getenv("DOUBAO_VISION_MODEL", "doubao-1-5-vision-pro-32k")
        elif "deepseek" in self.clients:
            return "deepseek-chat"
        elif "siliconflow" in self.clients:
            return os.getenv("SILICONFLOW_VISION_MODEL", "deepseek-ai/deepseek-vl2")
        return ""

    def get_default_vision_model(self) -> str:
        """获取默认的视觉模型"""
        _, model = self.get_vision_client_and_model()
        return model
