"""
Milvus 向量数据库客户端
支持集合自动创建、HNSW 索引、技能向量存储与检索
"""

import json
from typing import List, Dict, Optional, Any
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
import logging

from .exceptions import MilvusConnectionError

logger = logging.getLogger(__name__)


class MilvusClient:
    """Milvus 向量数据库客户端

    支持集合自动创建、技能向量插入与搜索。
    配置参数通过构造函数传入，避免硬编码。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "skill_embeddings",
        embedding_dim: int = 2048,
        hnsw_m: int = 16,
        hnsw_ef_construction: int = 256,
    ):
        """初始化 Milvus 客户端

        Args:
            host: Milvus 主机地址
            port: Milvus 端口
            collection_name: 集合名称
            embedding_dim: 向量维度
            hnsw_m: HNSW 索引参数 M
            hnsw_ef_construction: HNSW 索引参数 efConstruction
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.hnsw_m = hnsw_m
        self.hnsw_ef_construction = hnsw_ef_construction
        self._collection: Optional[Collection] = None
        self._connected = False

    def connect(self) -> None:
        """连接到 Milvus

        Raises:
            MilvusConnectionError: 连接失败
        """
        if self._connected:
            return
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port,
            )
            self._connected = True
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise MilvusConnectionError(f"Failed to connect to Milvus: {e}") from e

    def ensure_collection(self) -> Collection:
        """确保集合存在，不存在则创建（含 HNSW 索引）

        Returns:
            Collection 实例
        """
        self.connect()

        if utility.has_collection(self.collection_name):
            self._collection = Collection(self.collection_name)
            self._collection.load()
            logger.info(f"Collection '{self.collection_name}' already exists, loaded")
            return self._collection

        # 定义 schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="skill_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="steps_json", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="keywords", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.embedding_dim,
            ),
        ]
        schema = CollectionSchema(fields=fields, description="Skill embeddings for two-stage retrieval")
        self._collection = Collection(name=self.collection_name, schema=schema)

        # 创建 HNSW 索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": self.hnsw_m, "efConstruction": self.hnsw_ef_construction},
        }
        self._collection.create_index(field_name="embedding", index_params=index_params)
        self._collection.load()

        logger.info(f"Created collection '{self.collection_name}' with HNSW index (dim={self.embedding_dim})")
        return self._collection

    def insert(self, data: List[Dict[str, Any]]) -> None:
        """批量插入技能数据

        Args:
            data: 技能字典列表，每个包含 skill_id, name, description, category,
                  steps_json, keywords, embedding
        """
        if not data:
            return

        collection = self.ensure_collection()

        # 按列组织数据
        rows = {
            "skill_id": [],
            "name": [],
            "description": [],
            "category": [],
            "steps_json": [],
            "keywords": [],
            "embedding": [],
        }
        for item in data:
            rows["skill_id"].append(item["skill_id"])
            rows["name"].append(item["name"])
            rows["description"].append(item["description"])
            rows["category"].append(item["category"])
            rows["steps_json"].append(item["steps_json"])
            rows["keywords"].append(item["keywords"])
            rows["embedding"].append(item["embedding"])

        collection.insert([
            rows["skill_id"],
            rows["name"],
            rows["description"],
            rows["category"],
            rows["steps_json"],
            rows["keywords"],
            rows["embedding"],
        ])
        collection.flush()
        logger.info(f"Inserted {len(data)} skills into Milvus")

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有技能记录（供 BM25 建索引）

        Returns:
            技能字典列表
        """
        collection = self.ensure_collection()

        results = collection.query(
            expr="skill_id != ''",
            output_fields=["skill_id", "name", "description", "category", "steps_json", "keywords"],
        )

        skills = []
        for row in results:
            skills.append({
                "skill_id": row["skill_id"],
                "name": row["name"],
                "description": row["description"],
                "category": row["category"],
                "steps": json.loads(row["steps_json"]) if row.get("steps_json") else [],
                "keywords": row.get("keywords", ""),
            })
        return skills

    async def search(
        self,
        embedding: List[float],
        top_k: int = 50,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索

        Args:
            embedding: 查询向量
            top_k: 返回数量
            filter_expr: 过滤表达式

        Returns:
            技能列表，按相似度排序
        """
        if not embedding:
            raise ValueError("Embedding cannot be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        try:
            collection = self.ensure_collection()

            search_params = {
                "metric_type": "COSINE",
                "params": {"ef": 64},
            }

            results = collection.search(
                data=[embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["skill_id", "name", "description", "category", "steps_json", "keywords"],
            )

            skills = []
            for hits in results:
                for hit in hits:
                    entity = hit.entity
                    steps_json = entity.get("steps_json", "[]")
                    skills.append({
                        "skill_id": entity.get("skill_id"),
                        "name": entity.get("name"),
                        "description": entity.get("description"),
                        "category": entity.get("category"),
                        "steps": json.loads(steps_json) if steps_json else [],
                        "keywords": entity.get("keywords", ""),
                        "score": hit.score,
                    })
            return skills

        except Exception as e:
            logger.error(f"Search operation failed: {e}")
            raise MilvusConnectionError(f"Search operation failed: {e}") from e

    def has_skills(self) -> bool:
        """检查集合中是否已有数据"""
        try:
            collection = self.ensure_collection()
            return collection.num_entities > 0
        except Exception:
            return False

    def close(self) -> None:
        """关闭连接"""
        try:
            connections.disconnect("default")
            self._connected = False
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
