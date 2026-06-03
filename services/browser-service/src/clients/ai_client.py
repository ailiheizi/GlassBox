"""
AI Service客户端
"""
from typing import Dict, Any, List, Optional
import httpx

from ..config.settings import settings


class AIClient:
    """AI Service客户端"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.ai_service_url

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """调用AI聊天接口"""
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/chat",
                json={
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            return response.json()

    async def generate_embedding(self, text: str) -> List[float]:
        """生成Embedding"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/embedding",
                json={"text": text},
            )
            response.raise_for_status()
            return response.json()["embedding"]
