"""
Skill 系统单例管理器
提供全局单例访问，简化 API 层的初始化逻辑
"""

import logging
from typing import Optional

from .config import SkillSystemConfig
from .factory import SkillSystemFactory
from .selector import SkillSelector
from .exceptions import SkillInitializationError

logger = logging.getLogger(__name__)


class SkillSystemManager:
    """Skill 系统单例管理器

    提供全局单例访问，确保整个应用只有一个 Skill 系统实例

    Example:
        >>> # 初始化（通常在应用启动时）
        >>> manager = SkillSystemManager.get_instance()
        >>> await manager.initialize(config, embedding_service, llm_client)
        >>>
        >>> # 使用（在 API 路由中）
        >>> manager = SkillSystemManager.get_instance()
        >>> selector = manager.get_selector()
        >>> skills = await selector.select("打开浏览器", top_k=3)
    """

    _instance: Optional["SkillSystemManager"] = None
    _lock = False  # 简单的锁机制，防止并发初始化

    def __init__(self):
        """私有构造函数，使用 get_instance() 获取实例"""
        self._factory: Optional[SkillSystemFactory] = None
        self._selector: Optional[SkillSelector] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "SkillSystemManager":
        """获取单例实例

        Returns:
            SkillSystemManager 单例
        """
        if cls._instance is None:
            cls._instance = cls()
            logger.info("SkillSystemManager instance created")
        return cls._instance

    async def initialize(
        self,
        config: SkillSystemConfig,
        embedding_service,
        llm_client,
    ) -> None:
        """初始化 Skill 系统

        Args:
            config: Skill 系统配置
            embedding_service: Embedding 服务
            llm_client: LLM 客户端

        Raises:
            SkillInitializationError: 初始化失败
        """
        if self._initialized:
            logger.info("SkillSystemManager already initialized, skipping")
            return

        if self._lock:
            logger.warning("SkillSystemManager initialization in progress, waiting...")
            return

        self._lock = True

        try:
            logger.info("Initializing SkillSystemManager...")

            # 创建工厂
            self._factory = SkillSystemFactory(
                config=config,
                embedding_service=embedding_service,
                llm_client=llm_client,
            )

            # 创建 SkillSelector（会自动初始化所有依赖）
            self._selector = await self._factory.create_skill_selector()

            self._initialized = True
            logger.info("SkillSystemManager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize SkillSystemManager: {e}")
            raise SkillInitializationError(f"Failed to initialize SkillSystemManager: {e}") from e
        finally:
            self._lock = False

    def get_selector(self) -> Optional[SkillSelector]:
        """获取 SkillSelector

        Returns:
            SkillSelector 实例，如果未初始化则返回 None
        """
        if not self._initialized:
            logger.warning("SkillSystemManager not initialized, returning None")
            return None
        return self._selector

    def is_initialized(self) -> bool:
        """检查是否已初始化

        Returns:
            True 如果已初始化，否则 False
        """
        return self._initialized

    def close(self) -> None:
        """关闭 Skill 系统，释放资源"""
        if self._factory:
            self._factory.close()
            logger.info("SkillSystemManager closed")

    @classmethod
    def reset(cls) -> None:
        """重置单例（主要用于测试）"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            logger.info("SkillSystemManager reset")
