"""
Index Service客户端
"""
from typing import Dict, Any, List, Optional
import httpx

from ..config.settings import settings


class IndexClient:
    """Index Service客户端"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.index_service_url

    async def search(
        self,
        user_id: str,
        query: str,
        service_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索索引"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {"query": query, "limit": limit}
            if service_name:
                params["service_name"] = service_name

            response = await client.get(
                f"{self.base_url}/search",
                params=params,
                headers={"X-User-ID": user_id},
            )
            response.raise_for_status()
            return response.json().get("indexes", [])

    async def create(
        self,
        user_id: str,
        url: str,
        title: str,
        description: Optional[str] = None,
        selector: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """创建AI索引"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/ai",
                json={
                    "url": url,
                    "title": title,
                    "description": description,
                    "selector": selector,
                    "tags": tags or [],
                },
                headers={"X-User-ID": user_id},
            )
            response.raise_for_status()
            return response.json()

    async def delete(self, user_id: str, index_id: int) -> bool:
        """删除AI索引"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{self.base_url}/ai/{index_id}",
                headers={"X-User-ID": user_id},
            )
            return response.status_code == 200
