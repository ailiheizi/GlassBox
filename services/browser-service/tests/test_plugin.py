"""
单元测试 - 工具插件系统
"""
import pytest
from typing import Dict, Any

from src.core.tools.plugin import (
    ToolPlugin,
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolRegistry,
    tool,
)


class TestToolDefinition:
    """测试工具定义"""

    def test_to_openai_format_basic(self):
        """测试基本的 OpenAI 格式转换"""
        definition = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="arg1",
                    type="string",
                    description="First argument",
                    required=True,
                ),
            ],
        )

        result = definition.to_openai_format()

        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["description"] == "A test tool"
        assert "arg1" in result["function"]["parameters"]["properties"]
        assert result["function"]["parameters"]["required"] == ["arg1"]

    def test_to_openai_format_with_enum(self):
        """测试带枚举的参数"""
        definition = ToolDefinition(
            name="enum_tool",
            description="Tool with enum",
            parameters=[
                ToolParameter(
                    name="direction",
                    type="string",
                    description="Direction",
                    enum=["up", "down", "left", "right"],
                ),
            ],
        )

        result = definition.to_openai_format()
        props = result["function"]["parameters"]["properties"]

        assert props["direction"]["enum"] == ["up", "down", "left", "right"]

    def test_to_openai_format_with_default(self):
        """测试带默认值的参数"""
        definition = ToolDefinition(
            name="default_tool",
            description="Tool with default",
            parameters=[
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Limit",
                    default=10,
                ),
            ],
        )

        result = definition.to_openai_format()
        props = result["function"]["parameters"]["properties"]

        assert props["limit"]["default"] == 10


class TestToolRegistry:
    """测试工具注册表"""

    def setup_method(self):
        """每个测试前清空注册表"""
        ToolRegistry.clear()

    def test_register_and_get(self):
        """测试注册和获取工具"""
        class TestTool(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name="test_tool",
                    description="Test",
                    category=ToolCategory.CUSTOM,
                )

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {"success": True}

        plugin = TestTool()
        ToolRegistry.register(plugin)

        retrieved = ToolRegistry.get("test_tool")
        assert retrieved is not None
        assert retrieved.definition.name == "test_tool"

    def test_unregister(self):
        """测试注销工具"""
        class TestTool(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(name="to_remove", description="Test")

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        ToolRegistry.register(TestTool())
        assert ToolRegistry.get("to_remove") is not None

        ToolRegistry.unregister("to_remove")
        assert ToolRegistry.get("to_remove") is None

    def test_get_by_category(self):
        """测试按分类获取工具"""
        class BrowserTool(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name="browser_tool",
                    description="Browser",
                    category=ToolCategory.BROWSER,
                )

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        class MemoryTool(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name="memory_tool",
                    description="Memory",
                    category=ToolCategory.MEMORY,
                )

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        ToolRegistry.register(BrowserTool())
        ToolRegistry.register(MemoryTool())

        browser_tools = ToolRegistry.get_by_category(ToolCategory.BROWSER)
        assert len(browser_tools) == 1
        assert browser_tools[0].definition.name == "browser_tool"

    def test_get_all_definitions(self):
        """测试获取所有工具定义"""
        class Tool1(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(name="tool1", description="Tool 1")

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        class Tool2(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(name="tool2", description="Tool 2")

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        ToolRegistry.register(Tool1())
        ToolRegistry.register(Tool2())

        definitions = ToolRegistry.get_all_definitions()
        assert len(definitions) == 2
        names = {d["function"]["name"] for d in definitions}
        assert names == {"tool1", "tool2"}


class TestToolDecorator:
    """测试工具装饰器"""

    def setup_method(self):
        ToolRegistry.clear()

    def test_tool_decorator(self):
        """测试装饰器注册工具"""
        @tool(
            name="decorated_tool",
            description="A decorated tool",
            parameters=[
                ToolParameter(name="input", type="string", description="Input", required=True),
            ],
        )
        async def my_tool(user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
            return {"result": arguments["input"].upper()}

        # 检查工具已注册
        plugin = ToolRegistry.get("decorated_tool")
        assert plugin is not None
        assert plugin.definition.description == "A decorated tool"


class TestToolPlugin:
    """测试工具插件基类"""

    def test_validate_arguments_required(self):
        """测试必需参数验证"""
        class RequiredArgTool(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name="required_arg_tool",
                    description="Test",
                    parameters=[
                        ToolParameter(name="required_arg", type="string", description="Required", required=True),
                    ],
                )

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        tool = RequiredArgTool()

        # 有必需参数时应该通过
        assert tool.validate_arguments({"required_arg": "value"}) is True

        # 缺少必需参数时应该抛出异常
        with pytest.raises(ValueError, match="Missing required parameter"):
            tool.validate_arguments({})

    def test_validate_arguments_optional(self):
        """测试可选参数验证"""
        class OptionalArgTool(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name="optional_arg_tool",
                    description="Test",
                    parameters=[
                        ToolParameter(name="optional_arg", type="string", description="Optional", required=False),
                    ],
                )

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        tool = OptionalArgTool()

        # 没有可选参数也应该通过
        assert tool.validate_arguments({}) is True
