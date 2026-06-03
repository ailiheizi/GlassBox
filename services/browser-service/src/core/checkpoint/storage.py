"""
Checkpoint 持久化存储 - 支持 PostgreSQL 和 Redis

提供任务执行状态的持久化，支持:
- 失败恢复
- 断点续传
- 历史回溯
"""
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TaskCheckpoint:
    """任务检查点"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    user_id: str = ""
    step_index: int = 0
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "step_index": self.step_index,
            "state": self.state,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskCheckpoint':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            task_id=data.get("task_id", ""),
            user_id=data.get("user_id", ""),
            step_index=data.get("step_index", 0),
            state=data.get("state", {}),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


class CheckpointStorage(ABC):
    """检查点存储接口"""

    @abstractmethod
    async def save(self, checkpoint: TaskCheckpoint) -> None:
        """保存检查点"""
        pass

    @abstractmethod
    async def load(self, task_id: str, user_id: str) -> Optional[TaskCheckpoint]:
        """加载最新检查点"""
        pass

    @abstractmethod
    async def load_by_id(self, checkpoint_id: str) -> Optional[TaskCheckpoint]:
        """按ID加载检查点"""
        pass

    @abstractmethod
    async def delete(self, task_id: str, user_id: str) -> None:
        """删除任务的所有检查点"""
        pass

    @abstractmethod
    async def list_checkpoints(self, task_id: str, user_id: str) -> List[TaskCheckpoint]:
        """列出任务的所有检查点"""
        pass


class InMemoryCheckpointStorage(CheckpointStorage):
    """内存检查点存储 - 用于测试"""

    def __init__(self):
        self._checkpoints: Dict[str, List[TaskCheckpoint]] = {}

    def _key(self, task_id: str, user_id: str) -> str:
        return f"{user_id}:{task_id}"

    async def save(self, checkpoint: TaskCheckpoint) -> None:
        key = self._key(checkpoint.task_id, checkpoint.user_id)
        if key not in self._checkpoints:
            self._checkpoints[key] = []
        self._checkpoints[key].append(checkpoint)
        logger.debug(f"Saved checkpoint {checkpoint.id} for task {checkpoint.task_id}")

    async def load(self, task_id: str, user_id: str) -> Optional[TaskCheckpoint]:
        key = self._key(task_id, user_id)
        checkpoints = self._checkpoints.get(key, [])
        if checkpoints:
            return checkpoints[-1]
        return None

    async def load_by_id(self, checkpoint_id: str) -> Optional[TaskCheckpoint]:
        for checkpoints in self._checkpoints.values():
            for cp in checkpoints:
                if cp.id == checkpoint_id:
                    return cp
        return None

    async def delete(self, task_id: str, user_id: str) -> None:
        key = self._key(task_id, user_id)
        if key in self._checkpoints:
            del self._checkpoints[key]
            logger.debug(f"Deleted checkpoints for task {task_id}")

    async def list_checkpoints(self, task_id: str, user_id: str) -> List[TaskCheckpoint]:
        key = self._key(task_id, user_id)
        return self._checkpoints.get(key, [])


class RedisCheckpointStorage(CheckpointStorage):
    """Redis 检查点存储"""

    def __init__(self, redis_url: str = "redis://localhost:6379", prefix: str = "checkpoint"):
        self._redis_url = redis_url
        self._prefix = prefix
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self._redis_url)
        return self._redis

    def _key(self, task_id: str, user_id: str) -> str:
        return f"{self._prefix}:{user_id}:{task_id}"

    def _id_key(self, checkpoint_id: str) -> str:
        return f"{self._prefix}:id:{checkpoint_id}"

    async def save(self, checkpoint: TaskCheckpoint) -> None:
        redis = await self._get_redis()
        key = self._key(checkpoint.task_id, checkpoint.user_id)
        id_key = self._id_key(checkpoint.id)

        data = json.dumps(checkpoint.to_dict())

        # 保存到列表
        await redis.rpush(key, data)
        # 保存ID索引
        await redis.set(id_key, data, ex=86400 * 7)  # 7天过期
        # 设置列表过期时间
        await redis.expire(key, 86400 * 7)

        logger.debug(f"Saved checkpoint {checkpoint.id} to Redis")

    async def load(self, task_id: str, user_id: str) -> Optional[TaskCheckpoint]:
        redis = await self._get_redis()
        key = self._key(task_id, user_id)

        # 获取最后一个检查点
        data = await redis.lindex(key, -1)
        if data:
            return TaskCheckpoint.from_dict(json.loads(data))
        return None

    async def load_by_id(self, checkpoint_id: str) -> Optional[TaskCheckpoint]:
        redis = await self._get_redis()
        id_key = self._id_key(checkpoint_id)

        data = await redis.get(id_key)
        if data:
            return TaskCheckpoint.from_dict(json.loads(data))
        return None

    async def delete(self, task_id: str, user_id: str) -> None:
        redis = await self._get_redis()
        key = self._key(task_id, user_id)

        # 获取所有检查点ID并删除索引
        checkpoints = await self.list_checkpoints(task_id, user_id)
        for cp in checkpoints:
            await redis.delete(self._id_key(cp.id))

        # 删除列表
        await redis.delete(key)
        logger.debug(f"Deleted checkpoints for task {task_id} from Redis")

    async def list_checkpoints(self, task_id: str, user_id: str) -> List[TaskCheckpoint]:
        redis = await self._get_redis()
        key = self._key(task_id, user_id)

        data_list = await redis.lrange(key, 0, -1)
        return [TaskCheckpoint.from_dict(json.loads(d)) for d in data_list]


class PostgresCheckpointStorage(CheckpointStorage):
    """PostgreSQL 检查点存储"""

    def __init__(self, connection_string: str):
        self._connection_string = connection_string
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(self._connection_string)
        return self._pool

    async def _ensure_table(self):
        """确保表存在"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS task_checkpoints (
                    id UUID PRIMARY KEY,
                    task_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    step_index INT NOT NULL,
                    state JSONB NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_task_user
                    ON task_checkpoints(task_id, user_id);
                CREATE INDEX IF NOT EXISTS idx_checkpoints_created
                    ON task_checkpoints(created_at);
            """)

    async def save(self, checkpoint: TaskCheckpoint) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO task_checkpoints (id, task_id, user_id, step_index, state, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                uuid.UUID(checkpoint.id),
                uuid.UUID(checkpoint.task_id),
                uuid.UUID(checkpoint.user_id),
                checkpoint.step_index,
                json.dumps(checkpoint.state),
                json.dumps(checkpoint.metadata),
                checkpoint.created_at,
            )
        logger.debug(f"Saved checkpoint {checkpoint.id} to PostgreSQL")

    async def load(self, task_id: str, user_id: str) -> Optional[TaskCheckpoint]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, task_id, user_id, step_index, state, metadata, created_at
                FROM task_checkpoints
                WHERE task_id = $1 AND user_id = $2
                ORDER BY created_at DESC
                LIMIT 1
            """, uuid.UUID(task_id), uuid.UUID(user_id))

            if row:
                return TaskCheckpoint(
                    id=str(row["id"]),
                    task_id=str(row["task_id"]),
                    user_id=str(row["user_id"]),
                    step_index=row["step_index"],
                    state=json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
                    metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {},
                    created_at=row["created_at"],
                )
        return None

    async def load_by_id(self, checkpoint_id: str) -> Optional[TaskCheckpoint]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, task_id, user_id, step_index, state, metadata, created_at
                FROM task_checkpoints
                WHERE id = $1
            """, uuid.UUID(checkpoint_id))

            if row:
                return TaskCheckpoint(
                    id=str(row["id"]),
                    task_id=str(row["task_id"]),
                    user_id=str(row["user_id"]),
                    step_index=row["step_index"],
                    state=json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
                    metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {},
                    created_at=row["created_at"],
                )
        return None

    async def delete(self, task_id: str, user_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM task_checkpoints
                WHERE task_id = $1 AND user_id = $2
            """, uuid.UUID(task_id), uuid.UUID(user_id))
        logger.debug(f"Deleted checkpoints for task {task_id} from PostgreSQL")

    async def list_checkpoints(self, task_id: str, user_id: str) -> List[TaskCheckpoint]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, task_id, user_id, step_index, state, metadata, created_at
                FROM task_checkpoints
                WHERE task_id = $1 AND user_id = $2
                ORDER BY created_at ASC
            """, uuid.UUID(task_id), uuid.UUID(user_id))

            return [
                TaskCheckpoint(
                    id=str(row["id"]),
                    task_id=str(row["task_id"]),
                    user_id=str(row["user_id"]),
                    step_index=row["step_index"],
                    state=json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
                    metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {},
                    created_at=row["created_at"],
                )
                for row in rows
            ]


class CheckpointManager:
    """
    检查点管理器

    提供高级检查点操作:
    - 自动保存
    - 恢复执行
    - 清理过期检查点
    """

    def __init__(self, storage: CheckpointStorage):
        self._storage = storage

    async def create_checkpoint(
        self,
        task_id: str,
        user_id: str,
        step_index: int,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskCheckpoint:
        """创建检查点"""
        checkpoint = TaskCheckpoint(
            task_id=task_id,
            user_id=user_id,
            step_index=step_index,
            state=state,
            metadata=metadata or {},
        )
        await self._storage.save(checkpoint)
        return checkpoint

    async def get_latest_checkpoint(self, task_id: str, user_id: str) -> Optional[TaskCheckpoint]:
        """获取最新检查点"""
        return await self._storage.load(task_id, user_id)

    async def get_checkpoint_by_id(self, checkpoint_id: str) -> Optional[TaskCheckpoint]:
        """按ID获取检查点"""
        return await self._storage.load_by_id(checkpoint_id)

    async def get_checkpoint_history(self, task_id: str, user_id: str) -> List[TaskCheckpoint]:
        """获取检查点历史"""
        return await self._storage.list_checkpoints(task_id, user_id)

    async def clear_checkpoints(self, task_id: str, user_id: str) -> None:
        """清除任务的所有检查点"""
        await self._storage.delete(task_id, user_id)

    async def can_resume(self, task_id: str, user_id: str) -> bool:
        """检查是否可以恢复"""
        checkpoint = await self.get_latest_checkpoint(task_id, user_id)
        return checkpoint is not None

    async def get_resume_info(self, task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取恢复信息"""
        checkpoint = await self.get_latest_checkpoint(task_id, user_id)
        if checkpoint:
            return {
                "checkpoint_id": checkpoint.id,
                "step_index": checkpoint.step_index,
                "state": checkpoint.state,
                "created_at": checkpoint.created_at.isoformat(),
            }
        return None
