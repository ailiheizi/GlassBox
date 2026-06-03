"""
内置工具 - 使用插件系统重构

将原有的硬编码工具迁移到插件系统
"""
from typing import Dict, Any, List
import base64

from .plugin import (
    ToolPlugin,
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolRegistry,
)


# ==================== 浏览器工具 ====================

class NavigateTool(ToolPlugin):
    """导航工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="navigate",
            description="导航到指定URL",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="要导航到的URL",
                    required=True,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        url = arguments["url"]
        result = await browser.navigate(url)
        return {"success": True, "url": result.get("url"), "title": result.get("title")}


class ClickTool(ToolPlugin):
    """点击工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="click",
            description="点击页面元素",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS选择器或文本内容",
                    required=True,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        selector = arguments["selector"]
        result = await browser.click(selector)
        return {"success": result.get("success", False), "message": result.get("message", "")}


class TypeTextTool(ToolPlugin):
    """输入文本工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="type_text",
            description="在输入框中输入文本",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="selector",
                    type="string",
                    description="输入框的CSS选择器",
                    required=True,
                ),
                ToolParameter(
                    name="text",
                    type="string",
                    description="要输入的文本",
                    required=True,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        selector = arguments["selector"]
        text = arguments["text"]
        result = await browser.type_text(selector, text)
        return {"success": result.get("success", False)}


class WaitForSelectorTool(ToolPlugin):
    """等待元素工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="wait_for_selector",
            description="等待元素出现",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS选择器",
                    required=True,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="超时时间(毫秒)",
                    default=10000,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        selector = arguments["selector"]
        timeout = arguments.get("timeout", 10000)
        result = await browser.wait_for_selector(selector, timeout)
        return {"success": result.get("success", False)}


class GetPageInfoTool(ToolPlugin):
    """获取页面信息工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_page_info",
            description="获取当前页面信息",
            category=ToolCategory.BROWSER,
            parameters=[],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        return await browser.get_page_info()


class ScreenshotTool(ToolPlugin):
    """截图工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="screenshot",
            description="截取当前页面截图",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="full_page",
                    type="boolean",
                    description="是否截取整个页面",
                    default=False,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        full_page = arguments.get("full_page", False)
        screenshot_bytes = await browser.screenshot(full_page)
        return {
            "success": True,
            "image": base64.b64encode(screenshot_bytes).decode("utf-8"),
            "format": "png",
        }


class FindElementsTool(ToolPlugin):
    """查找元素工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_elements",
            description="根据文本查找元素",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="text",
                    type="string",
                    description="要查找的文本",
                    required=True,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        text = arguments["text"]
        elements = await browser.find_elements_by_text(text)
        return {"elements": elements}


class ScrollTool(ToolPlugin):
    """滚动工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="scroll",
            description="滚动页面",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="direction",
                    type="string",
                    description="滚动方向",
                    required=True,
                    enum=["up", "down", "left", "right"],
                ),
                ToolParameter(
                    name="amount",
                    type="integer",
                    description="滚动距离(像素)",
                    default=500,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        direction = arguments["direction"]
        amount = arguments.get("amount", 500)
        result = await browser.scroll(direction, amount)
        return {"success": result.get("success", False)}


# ==================== 记忆工具 ====================

class SaveMemoryTool(ToolPlugin):
    """保存记忆工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="save_memory",
            description="保存一条记忆",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="content",
                    type="string",
                    description="记忆内容",
                    required=True,
                ),
                ToolParameter(
                    name="content_type",
                    type="string",
                    description="内容类型",
                    default="general",
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        memory = context.get("memory")
        if not memory:
            return {"success": False, "error": "Memory service not available"}

        content = arguments["content"]
        content_type = arguments.get("content_type", "general")

        # user_id 由系统注入，不可篡改
        result = await memory.save(
            user_id=user_id,
            content=content,
            content_type=content_type,
        )
        return {"success": True, "memory_id": result.get("id")}


class SearchMemoryTool(ToolPlugin):
    """搜索记忆工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_memory",
            description="搜索记忆",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="搜索关键词",
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="返回数量",
                    default=10,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        memory = context.get("memory")
        if not memory:
            return {"success": False, "error": "Memory service not available"}

        query = arguments["query"]
        limit = min(arguments.get("limit", 10), 100)

        # user_id 由系统注入，不可篡改
        results = await memory.search(
            user_id=user_id,
            query=query,
            limit=limit,
        )
        return {"results": results}


# ==================== 索引工具 ====================

class SearchIndexTool(ToolPlugin):
    """搜索索引工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_index",
            description="搜索索引",
            category=ToolCategory.INDEX,
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="搜索关键词",
                    required=True,
                ),
                ToolParameter(
                    name="service_name",
                    type="string",
                    description="服务名称过滤",
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        index = context.get("index")
        if not index:
            return {"success": False, "error": "Index service not available"}

        query = arguments["query"]
        service_name = arguments.get("service_name")

        results = await index.search(
            user_id=user_id,
            query=query,
            service_name=service_name,
        )
        return {"results": results}


class CreateIndexTool(ToolPlugin):
    """创建索引工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="create_index",
            description="创建AI索引",
            category=ToolCategory.INDEX,
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL",
                    required=True,
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="标题",
                    required=True,
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="描述",
                ),
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS选择器",
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        index = context.get("index")
        if not index:
            return {"success": False, "error": "Index service not available"}

        result = await index.create(
            user_id=user_id,
            url=arguments["url"],
            title=arguments["title"],
            description=arguments.get("description"),
            selector=arguments.get("selector"),
        )
        return {"success": True, "index_id": result.get("id")}


# ==================== 注册所有内置工具 ====================

def register_builtin_tools():
    """注册所有内置工具"""
    builtin_tools = [
        # 浏览器工具
        NavigateTool(),
        ClickTool(),
        TypeTextTool(),
        WaitForSelectorTool(),
        GetPageInfoTool(),
        ScreenshotTool(),
        FindElementsTool(),
        ScrollTool(),
        # 记忆工具
        SaveMemoryTool(),
        SearchMemoryTool(),
        # 索引工具
        SearchIndexTool(),
        CreateIndexTool(),
    ]

    for tool in builtin_tools:
        ToolRegistry.register(tool)


# 模块加载时自动注册
register_builtin_tools()
