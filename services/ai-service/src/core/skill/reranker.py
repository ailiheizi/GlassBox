"""
两阶段技能检索管线
Stage 1: BM25 + Milvus ANN + RRF 融合
Stage 2: LLM Cross-Encoder 精排
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Okapi

from .milvus_client import MilvusClient
from ...config.settings import settings

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """简单分词：空格分割 + 中文逐字拆分"""
    tokens = []
    for word in text.lower().split():
        # 英文单词直接加入
        has_cjk = False
        for ch in word:
            if "\u4e00" <= ch <= "\u9fff":
                tokens.append(ch)
                has_cjk = True
            else:
                if not has_cjk:
                    tokens.append(word)
                    break
        if not has_cjk and not tokens:
            tokens.append(word)
    # 去重保序
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result if result else [text.lower()]


class BM25Index:
    """BM25 关键词索引"""

    def __init__(self) -> None:
        self._bm25: Optional[BM25Okapi] = None
        self._skills: List[Dict[str, Any]] = []
        self._corpus: List[List[str]] = []

    def build(self, skills: List[Dict[str, Any]]) -> None:
        """从技能列表构建 BM25 索引

        对每个 skill，将 keywords + name + description 拼接后分词。
        """
        self._skills = skills
        self._corpus = []

        for skill in skills:
            text_parts = [
                skill.get("keywords", ""),
                skill.get("name", ""),
                skill.get("description", ""),
            ]
            combined = " ".join(text_parts)
            self._corpus.append(_tokenize(combined))

        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
            logger.info(f"BM25 index built with {len(self._corpus)} skills")

    def search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """BM25 搜索

        Returns:
            带 bm25_score 的技能列表
        """
        if not self._bm25 or not self._skills:
            return []

        query_tokens = _tokenize(query)
        scores = self._bm25.get_scores(query_tokens)

        scored = []
        for i, score in enumerate(scores):
            if score > 0:
                skill = dict(self._skills[i])
                skill["bm25_score"] = float(score)
                scored.append(skill)

        scored.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored[:top_k]


def _rrf_fuse(
    milvus_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion 分数融合

    score = sum(1 / (k + rank)) 对两路结果分别计算后求和。
    """
    scores: Dict[str, float] = {}
    skill_map: Dict[str, Dict[str, Any]] = {}

    # Milvus 结果
    for rank, skill in enumerate(milvus_results):
        sid = skill["skill_id"]
        scores[sid] = scores.get(sid, 0) + 1.0 / (k + rank + 1)
        skill_map[sid] = skill

    # BM25 结果
    for rank, skill in enumerate(bm25_results):
        sid = skill["skill_id"]
        scores[sid] = scores.get(sid, 0) + 1.0 / (k + rank + 1)
        if sid not in skill_map:
            skill_map[sid] = skill

    # 按融合分数排序
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    for sid, rrf_score in ranked:
        skill = dict(skill_map[sid])
        skill["rrf_score"] = rrf_score
        results.append(skill)

    return results


class SkillRetrievalPipeline:
    """两阶段技能检索管线

    Stage 1: Milvus ANN + BM25 → RRF 融合 (top 20)
    Stage 2: LLM Cross-Encoder 精排 (top 3-5)
    """

    def __init__(
        self,
        milvus_client: MilvusClient,
        embedding_service: Any,
        llm_client: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        self.milvus = milvus_client
        self.embedding_service = embedding_service
        self.llm_client = llm_client
        self.config = config
        self.bm25_index = BM25Index()
        self._index_built = False

    def build_bm25_index(self, skills: List[Dict[str, Any]]) -> None:
        """从技能列表构建 BM25 索引"""
        self.bm25_index.build(skills)
        self._index_built = True

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """执行两阶段检索

        Args:
            query: 用户查询
            top_k: 最终返回数量

        Returns:
            排序后的技能列表
        """
        # Stage 1: 召回
        candidates = await self._stage1_recall(query)

        if not candidates:
            logger.warning(f"No candidates found for query: {query[:50]}")
            return []

        # Stage 2: 精排
        reranked = await self._stage2_rerank(query, candidates, top_k)

        return reranked

    async def _stage1_recall(self, query: str) -> List[Dict[str, Any]]:
        """Stage 1: Milvus ANN + BM25 + RRF 融合"""
        milvus_results = []
        bm25_results = []

        # 从 config 获取参数，如果没有 config 则使用默认值
        stage1_top_k = self.config.stage1_top_k if self.config else 50
        rrf_k = self.config.stage1_rrf_k if self.config else 60
        output_k = self.config.stage1_output_k if self.config else 20
        bm25_top_k = self.config.bm25_top_k if self.config else 50

        # Milvus ANN 搜索
        try:
            embedding = await self.embedding_service.generate(query)
            milvus_results = await self.milvus.search(embedding=embedding, top_k=stage1_top_k)
        except Exception as e:
            logger.warning(f"Milvus search failed, falling back to BM25 only: {e}")

        # BM25 搜索
        if self._index_built:
            bm25_results = self.bm25_index.search(query, top_k=bm25_top_k)

        # 如果两路都有结果，做 RRF 融合
        if milvus_results and bm25_results:
            return _rrf_fuse(milvus_results, bm25_results, k=rrf_k, top_k=output_k)

        # 只有一路有结果
        if milvus_results:
            return milvus_results[:output_k]
        if bm25_results:
            return bm25_results[:output_k]

        return []

    async def _stage2_rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Stage 2: LLM Cross-Encoder 精排

        将候选 skill 提交给 LLM 打分，失败时回退到 Stage 1 分数。
        """
        if not self.llm_client:
            logger.info("No LLM client for reranking, using Stage 1 scores")
            return candidates[:top_k]

        # 构建 prompt
        skill_list = []
        for i, skill in enumerate(candidates):
            skill_list.append(
                f"{i+1}. {skill['name']} - {skill['description']}"
            )
        skills_text = "\n".join(skill_list)

        prompt = f"""请根据用户查询，对以下技能按相关性打分（0-10分）。

用户查询：{query}

候选技能：
{skills_text}

请严格按以下 JSON 格式输出，只输出 JSON，不要其他内容：
```json
[{{"index": 1, "score": 8}}, {{"index": 2, "score": 3}}]
```"""

        # 从 config 获取参数
        temperature = self.config.rerank_temperature if self.config else 0.1
        max_tokens = self.config.rerank_max_tokens if self.config else 512

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=settings.doubao_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.get("message", {}).get("content", "") or response.get("content", "")

            scores = self._parse_rerank_scores(content, len(candidates))

            # 按 LLM 分数排序
            scored_candidates = []
            for i, skill in enumerate(candidates):
                skill_copy = dict(skill)
                skill_copy["rerank_score"] = scores.get(i + 1, 0)
                scored_candidates.append(skill_copy)

            scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            return scored_candidates[:top_k]

        except Exception as e:
            logger.warning(f"LLM reranking failed, falling back to Stage 1 scores: {e}")
            return candidates[:top_k]

    def _parse_rerank_scores(self, content: str, count: int) -> Dict[int, float]:
        """解析 LLM 返回的打分结果"""
        scores: Dict[int, float] = {}

        # 尝试提取 JSON
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            try:
                items = json.loads(json_match.group(0))
                for item in items:
                    idx = item.get("index", 0)
                    score = item.get("score", 0)
                    if 1 <= idx <= count:
                        scores[idx] = float(score)
                return scores
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # 回退：所有候选同分
        for i in range(1, count + 1):
            scores[i] = 5.0
        return scores
