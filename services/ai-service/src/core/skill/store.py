"""
SkillStore - 技能存储管理
负责 Milvus 集合初始化、内置技能加载、embedding 生成
"""

import json
import logging
from typing import List, Dict, Any, Optional

from .milvus_client import MilvusClient
from .builtin_skills import BUILTIN_SKILLS

logger = logging.getLogger(__name__)


class SkillStore:
    """技能存储管理器

    职责：
    - 确保 Milvus 集合存在
    - 加载内置技能到 Milvus
    - 提供技能的增删查接口
    """

    def __init__(
        self,
        milvus_client: MilvusClient,
        embedding_service: Any,
    ) -> None:
        self.milvus = milvus_client
        self.embedding_service = embedding_service
        self._initialized = False

    async def initialize(self) -> None:
        """初始化：确保集合存在，加载内置技能"""
        if self._initialized:
            return

        try:
            self.milvus.ensure_collection()

            # 如果集合为空，加载内置技能
            if not self.milvus.has_skills():
                logger.info("No skills found in Milvus, loading builtin skills...")
                await self.add_skills(BUILTIN_SKILLS)
                logger.info(f"Loaded {len(BUILTIN_SKILLS)} builtin skills")
            else:
                logger.info("Skills already exist in Milvus, skipping builtin load")

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize SkillStore: {e}")
            raise

    async def add_skills(self, skills: List[Dict[str, Any]]) -> None:
        """添加技能到 Milvus（生成 embedding 后插入）

        Args:
            skills: 技能定义列表
        """
        if not skills:
            return

        # 为每个 skill 生成 embedding 文本
        texts = []
        for skill in skills:
            embed_text = f"{skill['name']} {skill['description']} {' '.join(skill.get('keywords', []))}"
            texts.append(embed_text)

        # 批量生成 embedding
        embeddings = await self.embedding_service.batch_generate(texts)

        # 构建插入数据
        insert_data = []
        for skill, embedding in zip(skills, embeddings):
            insert_data.append({
                "skill_id": skill["skill_id"],
                "name": skill["name"],
                "description": skill["description"],
                "category": skill.get("category", "general"),
                "steps_json": json.dumps(skill.get("steps", []), ensure_ascii=False),
                "keywords": " ".join(skill.get("keywords", [])),
                "embedding": embedding,
            })

        self.milvus.insert(insert_data)

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """获取所有技能（供 BM25 建索引）"""
        return self.milvus.get_all()
