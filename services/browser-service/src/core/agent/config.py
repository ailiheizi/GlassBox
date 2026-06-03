"""
多 Agent 配置系统 - 借鉴 OpenManus 的配置驱动设计

支持:
- YAML/TOML 配置文件
- 多 Agent 类型定义
- 动态 Agent 加载
- Agent 能力组合
"""
import os
import yaml
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Agent 类型"""
    BROWSER = "browser"
    DATA_ANALYSIS = "data_analysis"
    RESEARCH = "research"
    CODING = "coding"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM 配置"""
    model: str = "doubao-pro-32k"
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMConfig':
        return cls(
            model=data.get("model", "doubao-pro-32k"),
            api_base=data.get("api_base"),
            api_key=data.get("api_key"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 4096),
            timeout=data.get("timeout", 60),
        )


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    agent_type: AgentType
    enabled: bool = True
    description: str = ""
    llm: Optional[LLMConfig] = None
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""
    max_iterations: int = 10
    timeout: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'AgentConfig':
        agent_type = AgentType(data.get("type", "custom"))
        llm_data = data.get("llm")
        llm = LLMConfig.from_dict(llm_data) if llm_data else None

        return cls(
            name=name,
            agent_type=agent_type,
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            llm=llm,
            tools=data.get("tools", []),
            system_prompt=data.get("system_prompt", ""),
            max_iterations=data.get("max_iterations", 10),
            timeout=data.get("timeout", 300),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AppConfig:
    """应用配置"""
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8084
    debug: bool = False

    # 默认 LLM 配置
    default_llm: Optional[LLMConfig] = None

    # Agent 配置
    agents: Dict[str, AgentConfig] = field(default_factory=dict)

    # 工具配置
    enabled_tools: List[str] = field(default_factory=list)
    tool_plugins_dir: Optional[str] = None

    # 浏览器配置
    browser_headless: bool = True
    browser_stealth: bool = True
    browser_proxy: Optional[str] = None

    # 安全配置
    max_concurrent_sessions: int = 10
    session_timeout: int = 3600

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        # 解析服务配置
        server = data.get("server", {})

        # 解析默认 LLM
        llm_data = data.get("llm")
        default_llm = LLMConfig.from_dict(llm_data) if llm_data else None

        # 解析 Agent 配置
        agents = {}
        for name, agent_data in data.get("agents", {}).items():
            agents[name] = AgentConfig.from_dict(name, agent_data)

        # 解析工具配置
        tools = data.get("tools", {})

        # 解析浏览器配置
        browser = data.get("browser", {})

        # 解析安全配置
        security = data.get("security", {})

        return cls(
            host=server.get("host", "0.0.0.0"),
            port=server.get("port", 8084),
            debug=server.get("debug", False),
            default_llm=default_llm,
            agents=agents,
            enabled_tools=tools.get("enabled", []),
            tool_plugins_dir=tools.get("plugins_dir"),
            browser_headless=browser.get("headless", True),
            browser_stealth=browser.get("stealth", True),
            browser_proxy=browser.get("proxy"),
            max_concurrent_sessions=security.get("max_concurrent_sessions", 10),
            session_timeout=security.get("session_timeout", 3600),
        )


class ConfigLoader:
    """配置加载器"""

    @staticmethod
    def load_yaml(path: str) -> AppConfig:
        """从 YAML 文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return AppConfig.from_dict(data)

    @staticmethod
    def load_toml(path: str) -> AppConfig:
        """从 TOML 文件加载配置"""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        with open(path, 'rb') as f:
            data = tomllib.load(f)
        return AppConfig.from_dict(data)

    @staticmethod
    def load(path: str) -> AppConfig:
        """自动检测格式并加载配置"""
        if path.endswith('.yaml') or path.endswith('.yml'):
            return ConfigLoader.load_yaml(path)
        elif path.endswith('.toml'):
            return ConfigLoader.load_toml(path)
        else:
            raise ValueError(f"Unsupported config format: {path}")

    @staticmethod
    def load_from_env() -> AppConfig:
        """从环境变量加载配置"""
        config_path = os.getenv("CONFIG_PATH")
        if config_path and os.path.exists(config_path):
            return ConfigLoader.load(config_path)

        # 尝试默认路径
        default_paths = [
            "config.yaml",
            "config.yml",
            "config.toml",
            "configs/config.yaml",
        ]

        for path in default_paths:
            if os.path.exists(path):
                return ConfigLoader.load(path)

        # 返回默认配置
        logger.warning("No config file found, using defaults")
        return AppConfig()


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.tools = config.tools

    @abstractmethod
    async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        pass

    @property
    def is_enabled(self) -> bool:
        return self.config.enabled


class AgentRegistry:
    """Agent 注册表"""

    _agents: Dict[str, Type[BaseAgent]] = {}
    _instances: Dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent_type: AgentType):
        """注册 Agent 类型"""
        def decorator(agent_class: Type[BaseAgent]):
            cls._agents[agent_type.value] = agent_class
            return agent_class
        return decorator

    @classmethod
    def create(cls, config: AgentConfig) -> BaseAgent:
        """创建 Agent 实例"""
        agent_class = cls._agents.get(config.agent_type.value)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {config.agent_type}")

        instance = agent_class(config)
        cls._instances[config.name] = instance
        return instance

    @classmethod
    def get(cls, name: str) -> Optional[BaseAgent]:
        """获取 Agent 实例"""
        return cls._instances.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, BaseAgent]:
        """获取所有 Agent 实例"""
        return cls._instances.copy()

    @classmethod
    def load_from_config(cls, app_config: AppConfig) -> None:
        """从配置加载所有 Agent"""
        for name, agent_config in app_config.agents.items():
            if agent_config.enabled:
                try:
                    cls.create(agent_config)
                    logger.info(f"Loaded agent: {name}")
                except Exception as e:
                    logger.error(f"Failed to load agent {name}: {e}")


# ==================== 预定义 Agent 类型 ====================

@AgentRegistry.register(AgentType.BROWSER)
class BrowserAgent(BaseAgent):
    """浏览器自动化 Agent"""

    async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # 实际实现会调用浏览器服务
        return {"status": "completed", "task": task}


@AgentRegistry.register(AgentType.DATA_ANALYSIS)
class DataAnalysisAgent(BaseAgent):
    """数据分析 Agent"""

    async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "task": task}


@AgentRegistry.register(AgentType.RESEARCH)
class ResearchAgent(BaseAgent):
    """研究 Agent"""

    async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "task": task}


@AgentRegistry.register(AgentType.CODING)
class CodingAgent(BaseAgent):
    """编程 Agent"""

    async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "task": task}


@AgentRegistry.register(AgentType.CUSTOM)
class CustomAgent(BaseAgent):
    """自定义 Agent"""

    async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "task": task}
