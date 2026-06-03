import json
import os
from typing import List, Dict, Any, Optional, AsyncIterator
from openai import AsyncOpenAI

from .base import BaseLLM, BaseEmbedding
from ...config.settings import settings


class DoubaoLLM(BaseLLM):
    """Doubao LLM客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.doubao_api_key
        self.api_base = api_base or settings.doubao_api_base
        self.model = model or settings.doubao_model

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=300.0,  # 5分钟超时
        )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """聊天接口"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        response = await self.client.chat.completions.create(**kwargs)

        # 转换响应格式
        message = response.choices[0].message
        result = {
            "id": response.id,
            "message": {
                "role": message.role,
                "content": message.content,
            },
            "finish_reason": response.choices[0].finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

        # 处理工具调用
        if message.tool_calls:
            result["message"]["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        return result

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式聊天接口"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                yield {
                    "id": chunk.id,
                    "delta": {
                        "role": delta.role,
                        "content": delta.content,
                        "tool_calls": (
                            [
                                {
                                    "index": tc.index,
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {
                                        "name": tc.function.name if tc.function else None,
                                        "arguments": tc.function.arguments if tc.function else None,
                                    },
                                }
                                for tc in delta.tool_calls
                            ]
                            if delta.tool_calls
                            else None
                        ),
                    },
                    "finish_reason": chunk.choices[0].finish_reason,
                }


class DoubaoEmbedding(BaseEmbedding):
    """Doubao Embedding客户端

    使用火山方舟多模态 embedding 接口 (/embeddings/multimodal)。
    当 API 不可用时，自动回退到确定性 hash 向量。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        dim: int = 2048,
    ):
        import httpx
        self.api_key = api_key or settings.doubao_api_key
        self.api_base = api_base or settings.doubao_api_base
        self.model = model or settings.doubao_embedding_model
        self.dim = dim
        self._use_fallback = False
        self._http_client = httpx.AsyncClient(timeout=60.0)

    async def _call_multimodal_embedding(self, text: str) -> List[float]:
        """调用火山方舟多模态 embedding 接口"""
        resp = await self._http_client.post(
            f"{self.api_base}/embeddings/multimodal",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": [{"type": "text", "text": text}],
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]["embedding"]

    def _hash_embedding(self, text: str) -> List[float]:
        """确定性 hash 向量：相同文本 → 相同向量"""
        import hashlib
        import struct
        h = hashlib.sha512(text.encode("utf-8")).digest()
        result = []
        seed = h
        while len(result) < self.dim:
            seed = hashlib.sha512(seed).digest()
            for i in range(0, len(seed) - 3, 4):
                if len(result) >= self.dim:
                    break
                val = struct.unpack("f", seed[i:i+4])[0]
                if val != val or abs(val) > 1e30:  # NaN or inf
                    val = 0.0
                else:
                    val = max(-1.0, min(1.0, val / 1e30))
                result.append(val)
        return result[:self.dim]

    async def generate(self, text: str) -> List[float]:
        """生成单个文本的Embedding"""
        if self._use_fallback:
            return self._hash_embedding(text)
        try:
            return await self._call_multimodal_embedding(text)
        except Exception:
            self._use_fallback = True
            return self._hash_embedding(text)

    async def batch_generate(self, texts: List[str]) -> List[List[float]]:
        """批量生成Embedding（多模态接口不支持批量，逐条调用）"""
        if self._use_fallback:
            return [self._hash_embedding(t) for t in texts]
        try:
            return [await self._call_multimodal_embedding(t) for t in texts]
        except Exception:
            self._use_fallback = True
            return [self._hash_embedding(t) for t in texts]
