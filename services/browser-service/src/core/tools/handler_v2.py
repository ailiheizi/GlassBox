"""
工具处理器 V2 - 基于插件系统重构

支持:
- 动态工具注册
- 插件扩展
- 安全校验
"""
import json
from typing import Dict, Any, Optional
import logging

from .plugin import ToolRegistry, ToolCategory
from .security import check_dangerous_patterns, SecurityError, ToolResultValidator
from ..browser.client import BrowserClient
from ...clients.memory_client import MemoryClient
from ...clients.index_client import IndexClient

# 确保内置工具已注册
from . import builtin  # noqa: F401

logger = logging.getLogger(__name__)


class ToolHandlerV2:
    """
    工具处理器 V2

    基于插件系统的工具处理器，支持动态注册和扩展

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

        # 构建执行上下文
        self._context = {
            "browser": browser_client,
            "memory": memory_client,
            "index": index_client,
        }

    @property
    def user_id(self) -> str:
        """只读属性"""
        return self._user_id

    def get_tools(self, categories: Optional[list] = None) -> list:
        """
        获取工具定义列表

        Args:
            categories: 工具分类过滤，None 表示所有

        Returns:
            OpenAI 格式的工具定义列表
        """
        if categories is None:
            return ToolRegistry.get_all_definitions()

        tools = []
        for cat in categories:
            if isinstance(cat, str):
                cat = ToolCategory(cat)
            plugins = ToolRegistry.get_by_category(cat)
            tools.extend([p.definition.to_openai_format() for p in plugins])
        return tools

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        安全检查：
        1. 检查工具是否已注册
        2. 检查参数是否包含危险模式
        3. 验证参数
        4. 强制使用绑定的user_id
        5. 校验返回结果
        """
        # 1. 检查工具是否已注册
        plugin = ToolRegistry.get(tool_name)
        if plugin is None:
            raise SecurityError(f"Tool '{tool_name}' is not registered")

        # 2. 检查危险模式
        check_dangerous_patterns(arguments)

        # 3. 验证参数
        try:
            plugin.validate_arguments(arguments)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        # 4. 执行工具 (user_id 由系统注入)
        try:
            result = await plugin.execute(
                user_id=self._user_id,
                arguments=arguments,
                context=self._context,
            )
        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} - {e}")
            return {"success": False, "error": str(e)}

        # 5. 校验结果
        validated_result = self._validator.validate(tool_name, result)

        return validated_result

    async def execute_batch(self, tool_calls: list) -> list:
        """
        批量执行工具

        Args:
            tool_calls: [{"name": "tool_name", "arguments": {...}}, ...]

        Returns:
            执行结果列表
        """
        results = []
        for call in tool_calls:
            tool_name = call.get("name")
            arguments = call.get("arguments", {})

            # 如果 arguments 是字符串，尝试解析为 JSON
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    results.append({
                        "tool_name": tool_name,
                        "success": False,
                        "error": "Invalid JSON arguments",
                    })
                    continue

            result = await self.execute(tool_name, arguments)
            results.append({
                "tool_name": tool_name,
                **result,
            })

        return results


# 兼容旧版本的别名
ToolHandler = ToolHandlerV2
