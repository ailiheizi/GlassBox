"""
Skill 系统配置
集中管理所有配置项，避免硬编码
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SkillSystemConfig:
    """Skill 系统配置

    所有配置项都有默认值，可以通过 settings 覆盖
    """

    # Milvus 配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    collection_name: str = "skill_embeddings"
    embedding_dim: int = 2048

    # HNSW 索引参数
    hnsw_m: int = 16
    hnsw_ef_construction: int = 256
    hnsw_ef_search: int = 64

    # 检索参数
    stage1_top_k: int = 50  # Stage 1 召回数量
    stage1_rrf_k: int = 60  # RRF 融合参数
    stage1_output_k: int = 20  # Stage 1 输出数量

    # LLM 精排参数
    rerank_temperature: float = 0.1
    rerank_max_tokens: int = 512

    # BM25 参数
    bm25_top_k: int = 50

    @classmethod
    def from_settings(cls, settings) -> "SkillSystemConfig":
        """从 settings 创建配置"""
        return cls(
            milvus_host=settings.milvus_host,
            milvus_port=settings.milvus_port,
            embedding_dim=settings.doubao_embedding_dimensions,
        )
