"""
Skill 系统工厂
统一管理组件创建和依赖注入，简化初始化流程
"""

import logging
from typing import Optional

from .config import SkillSystemConfig
from .milvus_client import MilvusClient
from .store import SkillStore
from .reranker import SkillRetrievalPipeline
from .selector import SkillSelector
from .exceptions import SkillInitializationError

logger = logging.getLogger(__name__)


class SkillSystemFactory:
    """Skill 系统工厂

    提供统一的组件创建接口，自动处理依赖注入

    Example:
        >>> factory = SkillSystemFactory(config, embedding_service, llm_client)
        >>> selector = await factory.create_skill_selector()
        >>> skills = await selector.select("打开浏览器", top_k=3)
    """

    def __init__(
        self,
        config: SkillSystemConfig,
        embedding_service,
        llm_client,
    ):
        """初始化工厂

        Args:
            config: Skill 系统配置
            embedding_service: Embedding 服务（DoubaoEmbedding）
            llm_client: LLM 客户端（DoubaoLLM）
        """
        self.config = config
        self.embedding_service = embedding_service
        self.llm_client = llm_client

        # 缓存已创建的组件
        self._milvus_client: Optional[MilvusClient] = None
        self._skill_store: Optional[SkillStore] = None
        self._pipeline: Optional[SkillRetrievalPipeline] = None
        self._selector: Optional[SkillSelector] = None

    def create_milvus_client(self) -> MilvusClient:
        """创建 MilvusClient（单例）"""
        if self._milvus_client is None:
            self._milvus_client = MilvusClient(
                host=self.config.milvus_host,
                port=self.config.milvus_port,
                collection_name=self.config.collection_name,
                embedding_dim=self.config.embedding_dim,
                hnsw_m=self.config.hnsw_m,
                hnsw_ef_construction=self.config.hnsw_ef_construction,
            )
            logger.info(f"Created MilvusClient: {self.config.milvus_host}:{self.config.milvus_port}")
        return self._milvus_client

    async def create_skill_store(self) -> SkillStore:
        """创建 SkillStore（单例）"""
        if self._skill_store is None:
            milvus_client = self.create_milvus_client()
            self._skill_store = SkillStore(
                milvus_client=milvus_client,
                embedding_service=self.embedding_service,
            )
            await self._skill_store.initialize()
            logger.info("SkillStore initialized")
        return self._skill_store

    async def create_retrieval_pipeline(self) -> SkillRetrievalPipeline:
        """创建 SkillRetrievalPipeline（单例）"""
        if self._pipeline is None:
            milvus_client = self.create_milvus_client()
            skill_store = await self.create_skill_store()

            self._pipeline = SkillRetrievalPipeline(
                milvus_client=milvus_client,
                embedding_service=self.embedding_service,
                llm_client=self.llm_client,
                config=self.config,
            )

            # 构建 BM25 索引
            all_skills = skill_store.get_all_skills()
            self._pipeline.build_bm25_index(all_skills)
            logger.info(f"SkillRetrievalPipeline initialized with {len(all_skills)} skills")

        return self._pipeline

    async def create_skill_selector(self) -> SkillSelector:
        """创建 SkillSelector（单例）

        这是最常用的入口，创建完整的 Skill 选择器

        Returns:
            SkillSelector 实例

        Raises:
            SkillInitializationError: 初始化失败
        """
        if self._selector is None:
            try:
                pipeline = await self.create_retrieval_pipeline()
                self._selector = SkillSelector(pipeline=pipeline)
                logger.info("SkillSelector created successfully")
            except Exception as e:
                logger.error(f"Failed to create SkillSelector: {e}")
                raise SkillInitializationError(f"Failed to create SkillSelector: {e}") from e

        return self._selector

    def close(self) -> None:
        """关闭所有资源"""
        if self._milvus_client:
            self._milvus_client.close()
            logger.info("MilvusClient closed")
