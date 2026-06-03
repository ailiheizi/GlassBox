"""
工具处理器 - user_id在初始化时绑定，不可修改
"""
import json
import base64
from typing import Dict, Any, Optional

from .definitions import ALLOWED_TOOL_NAMES
from .security import check_dangerous_patterns, SecurityError, ToolResultValidator
from ..browser.client import BrowserClient
from ...clients.memory_client import MemoryClient
from ...clients.index_client import IndexClient


class ToolHandler:
    """
    工具处理器

    安全设计：
    - user_id在初始化时绑定，LLM无法修改
    - 所有工具调用都使用绑定的user_id
    - 工具定义中不暴露user_id参数
    """

    def __init__(
        self,
        user_id: str,
        browser_client: BrowserClient,
        memory_client: Optional[MemoryClient] = None,
        index_client: Optional[IndexClient] = None,
    ):
        # user_id在初始化时绑定，不可修改
        self._user_id = user_id
        self._browser = browser_client
        self._memory = memory_client
        self._index = index_client
        self._validator = ToolResultValidator(user_id)

    @property
    def user_id(self) -> str:
        """只读属性"""
        return self._user_id

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        安全检查：
        1. 检查工具是否在白名单中
        2. 检查参数是否包含危险模式
        3. 强制使用绑定的user_id
        4. 校验返回结果
        """
        # 1. 检查工具白名单
        if tool_name not in ALLOWED_TOOL_NAMES:
            raise SecurityError(f"Tool '{tool_name}' is not allowed")

        # 2. 检查危险模式
        check_dangerous_patterns(arguments)

        # 3. 执行工具
        result = await self._dispatch(tool_name, arguments)

        # 4. 校验结果
        validated_result = self._validator.validate(tool_name, result)

        return validated_result

    async def _dispatch(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """分发工具调用"""
        # 浏览器工具
        if tool_name == "navigate":
            return await self._navigate(args)
        elif tool_name == "click":
            return await self._click(args)
        elif tool_name == "type_text":
            return await self._type_text(args)
        elif tool_name == "wait_for_selector":
            return await self._wait_for_selector(args)
        elif tool_name == "get_page_info":
            return await self._get_page_info()
        elif tool_name == "screenshot":
            return await self._screenshot(args)
        elif tool_name == "find_elements":
            return await self._find_elements(args)
        elif tool_name == "scroll":
            return await self._scroll(args)
        # 记忆工具
        elif tool_name == "save_memory":
            return await self._save_memory(args)
        elif tool_name == "search_memory":
            return await self._search_memory(args)
        # 索引工具
        elif tool_name == "search_index":
            return await self._search_index(args)
        elif tool_name == "create_index":
            return await self._create_index(args)
        else:
            raise SecurityError(f"Unknown tool: {tool_name}")

    # ==================== 浏览器工具 ====================

    async def _navigate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        url = args["url"]
        result = await self._browser.navigate(url)
        return {"success": True, "url": result.get("url"), "title": result.get("title")}

    async def _click(self, args: Dict[str, Any]) -> Dict[str, Any]:
        selector = args["selector"]
        result = await self._browser.click(selector)
        return {"success": result.get("success", False), "message": result.get("message", "")}

    async def _type_text(self, args: Dict[str, Any]) -> Dict[str, Any]:
        selector = args["selector"]
        text = args["text"]
        result = await self._browser.type_text(selector, text)
        return {"success": result.get("success", False)}

    async def _wait_for_selector(self, args: Dict[str, Any]) -> Dict[str, Any]:
        selector = args["selector"]
        timeout = args.get("timeout", 10000)
        result = await self._browser.wait_for_selector(selector, timeout)
        return {"success": result.get("success", False)}

    async def _get_page_info(self) -> Dict[str, Any]:
        return await self._browser.get_page_info()

    async def _screenshot(self, args: Dict[str, Any]) -> Dict[str, Any]:
        full_page = args.get("full_page", False)
        screenshot_bytes = await self._browser.screenshot(full_page)
        # 返回base64编码的截图
        return {
            "success": True,
            "image": base64.b64encode(screenshot_bytes).decode("utf-8"),
            "format": "png"
        }

    async def _find_elements(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args["text"]
        elements = await self._browser.find_elements_by_text(text)
        return {"elements": elements}

    async def _scroll(self, args: Dict[str, Any]) -> Dict[str, Any]:
        direction = args["direction"]
        amount = args.get("amount", 500)
        result = await self._browser.scroll(direction, amount)
        return {"success": result.get("success", False)}

    # ==================== 记忆工具 ====================

    async def _save_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self._memory:
            return {"success": False, "error": "Memory service not available"}

        content = args["content"]
        content_type = args.get("content_type", "general")

        # 强制使用绑定的user_id
        result = await self._memory.save(
            user_id=self._user_id,  # 不可被LLM篡改
            content=content,
            content_type=content_type,
        )
        return {"success": True, "memory_id": result.get("id")}

    async def _search_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self._memory:
            return {"success": False, "error": "Memory service not available"}

        query = args["query"]
        limit = min(args.get("limit", 10), 100)  # 限制最大返回数量

        # 强制使用绑定的user_id
        results = await self._memory.search(
            user_id=self._user_id,  # 不可被LLM篡改
            query=query,
            limit=limit,
        )
        return {"results": results}

    # ==================== 索引工具 ====================

    async def _search_index(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self._index:
            return {"success": False, "error": "Index service not available"}

        query = args["query"]
        service_name = args.get("service_name")

        # 强制使用绑定的user_id
        results = await self._index.search(
            user_id=self._user_id,
            query=query,
            service_name=service_name,
        )
        return {"results": results}

    async def _create_index(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self._index:
            return {"success": False, "error": "Index service not available"}

        # 强制使用绑定的user_id
        result = await self._index.create(
            user_id=self._user_id,  # 不可被LLM篡改
            url=args["url"],
            title=args["title"],
            description=args.get("description"),
            selector=args.get("selector"),
        )
        return {"success": True, "index_id": result.get("id")}
