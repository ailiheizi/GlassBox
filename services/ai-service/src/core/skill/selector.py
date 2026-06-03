"""
技能选择器
使用两阶段检索管线（BM25 + Milvus ANN + LLM 精排）选择最相关的技能
"""

from typing import List, Dict, Optional, Any
from .reranker import SkillRetrievalPipeline
import logging

logger = logging.getLogger(__name__)


class SkillSelector:
    """技能选择器

    根据用户消息和上下文信息，通过两阶段检索选择最相关的技能。
    """

    def __init__(
        self,
        pipeline: Optional[SkillRetrievalPipeline] = None,
    ) -> None:
        self.pipeline = pipeline

    async def select(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """选择相关技能

        Args:
            message: 用户消息
            context: 上下文信息（如截图分析结果）
            top_k: 返回技能数量

        Returns:
            技能列表，按相关性排序
        """
        if not message or not message.strip():
            return []

        if not self.pipeline:
            logger.warning("SkillSelector has no pipeline configured, returning empty")
            return []

        try:
            skills = await self.pipeline.retrieve(query=message, top_k=top_k)

            # 根据上下文重新排序
            if context:
                skills = self._rerank_with_context(skills, context)

            logger.info(f"Selected {len(skills)} skills for: {message[:50]}")
            return skills

        except Exception as e:
            logger.error(f"Failed to select skills: {e}")
            return []

    def _rerank_with_context(
        self,
        skills: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """根据上下文重新排序技能

        如果上下文包含截图分析信息，则提升视觉相关技能的权重。
        """
        if context.get("has_screenshot"):
            visual_skills = {"take_screenshot", "sandbox_click", "sandbox_type"}
            for skill in skills:
                if skill.get("skill_id") in visual_skills:
                    score_key = "rerank_score" if "rerank_score" in skill else "rrf_score" if "rrf_score" in skill else "score"
                    if score_key in skill:
                        skill[score_key] = skill[score_key] * 1.2

            # 重新排序
            score_key = "rerank_score" if skills and "rerank_score" in skills[0] else "rrf_score" if skills and "rrf_score" in skills[0] else "score"
            skills.sort(key=lambda x: x.get(score_key, 0), reverse=True)

        return skills
