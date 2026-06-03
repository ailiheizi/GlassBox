"""
Memory Service客户端
"""
from typing import Dict, Any, List, Optional
import httpx

from ..config.settings import settings


class MemoryClient:
    """Memory Service客户端"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.memory_service_url

    async def save(
        self,
        user_id: str,
        content: str,
        content_type: str = "general",
        session_id: Optional[str] = None,
        source_url: Optional[str] = None,
        page_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """保存记忆"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/semantic",
                json={
                    "content": content,
                    "content_type": content_type,
                    "session_id": session_id,
                    "source_url": source_url,
                    "page_title": page_title,
                },
                headers={"X-User-ID": user_id},
            )
            response.raise_for_status()
            return response.json()

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """搜索记忆"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {"query": query, "limit": limit}
            if content_type:
                params["content_type"] = content_type

            response = await client.get(
                f"{self.base_url}/semantic/search",
                params=params,
                headers={"X-User-ID": user_id},
            )
            response.raise_for_status()
            return response.json().get("memories", [])

    async def get_recent(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取最近记忆"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/recent",
                params={"limit": limit},
                headers={"X-User-ID": user_id},
            )
            response.raise_for_status()
            return response.json().get("memories", [])
