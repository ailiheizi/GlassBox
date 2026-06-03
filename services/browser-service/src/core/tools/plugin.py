"""
工具插件系统 - 支持动态注册和扩展工具

借鉴:
- Claude Code 的插件系统
- Browser-Use 的装饰器模式
- OpenManus 的配置驱动设计
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
import functools
import logging

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """工具分类"""
    BROWSER = "browser"
    MEMORY = "memory"
    INDEX = "index"
    CUSTOM = "custom"


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # string, integer, boolean, array, object
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    category: ToolCategory = ToolCategory.CUSTOM

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI 工具格式"""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.default is not None:
                prop["default"] = param.default
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }


class ToolPlugin(ABC):
    """
    工具插件基类

    所有自定义工具都应继承此类
    """

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """返回工具定义"""
        pass

    @abstractmethod
    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        Args:
            user_id: 用户ID (由系统注入，不可篡改)
            arguments: 工具参数
            context: 执行上下文 (browser_client, memory_client 等)

        Returns:
            执行结果
        """
        pass

    def validate_arguments(self, arguments: Dict[str, Any]) -> bool:
        """验证参数"""
        for param in self.definition.parameters:
            if param.required and param.name not in arguments:
                raise ValueError(f"Missing required parameter: {param.name}")
        return True


class ToolRegistry:
    """
    工具注册表 - 单例模式

    管理所有已注册的工具插件
    """
    _instance: Optional['ToolRegistry'] = None
    _plugins: Dict[str, ToolPlugin] = {}
    _categories: Dict[ToolCategory, List[str]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._plugins = {}
            cls._categories = {cat: [] for cat in ToolCategory}
        return cls._instance

    @classmethod
    def register(cls, plugin: ToolPlugin) -> None:
        """注册工具插件"""
        instance = cls()
        name = plugin.definition.name
        category = plugin.definition.category

        if name in instance._plugins:
            logger.warning(f"Tool '{name}' already registered, overwriting")

        instance._plugins[name] = plugin
        if name not in instance._categories[category]:
            instance._categories[category].append(name)

        logger.info(f"Registered tool: {name} (category: {category.value})")

    @classmethod
    def unregister(cls, name: str) -> None:
        """注销工具插件"""
        instance = cls()
        if name in instance._plugins:
            plugin = instance._plugins.pop(name)
            category = plugin.definition.category
            if name in instance._categories[category]:
                instance._categories[category].remove(name)
            logger.info(f"Unregistered tool: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[ToolPlugin]:
        """获取工具插件"""
        instance = cls()
        return instance._plugins.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, ToolPlugin]:
        """获取所有工具插件"""
        instance = cls()
        return instance._plugins.copy()

    @classmethod
    def get_by_category(cls, category: ToolCategory) -> List[ToolPlugin]:
        """按分类获取工具"""
        instance = cls()
        names = instance._categories.get(category, [])
        return [instance._plugins[name] for name in names if name in instance._plugins]

    @classmethod
    def get_all_definitions(cls) -> List[Dict[str, Any]]:
        """获取所有工具定义 (OpenAI 格式)"""
        instance = cls()
        return [plugin.definition.to_openai_format() for plugin in instance._plugins.values()]

    @classmethod
    def get_allowed_names(cls) -> set:
        """获取所有允许的工具名称"""
        instance = cls()
        return set(instance._plugins.keys())

    @classmethod
    def clear(cls) -> None:
        """清空所有注册"""
        instance = cls()
        instance._plugins.clear()
        instance._categories = {cat: [] for cat in ToolCategory}


def tool(
    name: str,
    description: str,
    category: ToolCategory = ToolCategory.CUSTOM,
    parameters: Optional[List[ToolParameter]] = None,
):
    """
    工具装饰器 - 简化工具注册

    用法:
        @tool(
            name="my_tool",
            description="My custom tool",
            parameters=[
                ToolParameter(name="arg1", type="string", description="Argument 1", required=True),
            ]
        )
        async def my_tool(user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
            return {"result": "success"}
    """
    def decorator(func: Callable):
        # 创建动态工具类
        class DynamicTool(ToolPlugin):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name=name,
                    description=description,
                    parameters=parameters or [],
                    category=category,
                )

            async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                return await func(user_id, arguments, context)

        # 注册工具
        plugin = DynamicTool()
        ToolRegistry.register(plugin)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        # 保存插件引用
        wrapper._plugin = plugin
        return wrapper

    return decorator


class PluginLoader:
    """
    插件加载器 - 从配置或目录加载插件
    """

    @staticmethod
    def load_from_config(config: Dict[str, Any]) -> None:
        """
        从配置加载插件

        配置格式:
        {
            "plugins": [
                {
                    "name": "tool_name",
                    "description": "Tool description",
                    "category": "custom",
                    "module": "path.to.module",
                    "class": "ToolClassName",
                    "enabled": true
                }
            ]
        }
        """
        import importlib

        plugins = config.get("plugins", [])
        for plugin_config in plugins:
            if not plugin_config.get("enabled", True):
                continue

            try:
                module_path = plugin_config["module"]
                class_name = plugin_config["class"]

                module = importlib.import_module(module_path)
                plugin_class: Type[ToolPlugin] = getattr(module, class_name)
                plugin = plugin_class()

                ToolRegistry.register(plugin)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_config.get('name', 'unknown')}: {e}")

    @staticmethod
    def load_from_directory(directory: str) -> None:
        """
        从目录加载插件

        目录结构:
        plugins/
            my_tool/
                __init__.py  # 包含 ToolPlugin 子类
                config.yaml  # 可选配置
        """
        import os
        import importlib.util

        if not os.path.isdir(directory):
            logger.warning(f"Plugin directory not found: {directory}")
            return

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                init_file = os.path.join(item_path, "__init__.py")
                if os.path.exists(init_file):
                    try:
                        spec = importlib.util.spec_from_file_location(item, init_file)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)

                            # 查找 ToolPlugin 子类
                            for attr_name in dir(module):
                                attr = getattr(module, attr_name)
                                if (isinstance(attr, type) and
                                    issubclass(attr, ToolPlugin) and
                                    attr is not ToolPlugin):
                                    plugin = attr()
                                    ToolRegistry.register(plugin)
                    except Exception as e:
                        logger.error(f"Failed to load plugin from {item_path}: {e}")
