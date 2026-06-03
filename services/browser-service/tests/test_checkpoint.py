"""
单元测试 - Checkpoint 存储
"""
import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from src.core.checkpoint.storage import (
    TaskCheckpoint,
    InMemoryCheckpointStorage,
    CheckpointManager,
)


class TestTaskCheckpoint:
    """测试任务检查点"""

    def test_to_dict(self):
        """测试转换为字典"""
        checkpoint = TaskCheckpoint(
            id="cp-123",
            task_id="task-456",
            user_id="user-789",
            step_index=5,
            state={"url": "https://example.com"},
            metadata={"source": "test"},
        )

        result = checkpoint.to_dict()

        assert result["id"] == "cp-123"
        assert result["task_id"] == "task-456"
        assert result["user_id"] == "user-789"
        assert result["step_index"] == 5
        assert result["state"]["url"] == "https://example.com"
        assert result["metadata"]["source"] == "test"
        assert "created_at" in result

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "id": "cp-123",
            "task_id": "task-456",
            "user_id": "user-789",
            "step_index": 5,
            "state": {"url": "https://example.com"},
            "metadata": {"source": "test"},
            "created_at": "2024-01-15T10:30:00",
        }

        checkpoint = TaskCheckpoint.from_dict(data)

        assert checkpoint.id == "cp-123"
        assert checkpoint.task_id == "task-456"
        assert checkpoint.user_id == "user-789"
        assert checkpoint.step_index == 5
        assert checkpoint.state["url"] == "https://example.com"

    def test_from_dict_defaults(self):
        """测试从字典创建时的默认值"""
        data = {}

        checkpoint = TaskCheckpoint.from_dict(data)

        assert checkpoint.task_id == ""
        assert checkpoint.user_id == ""
        assert checkpoint.step_index == 0
        assert checkpoint.state == {}


class TestInMemoryCheckpointStorage:
    """测试内存检查点存储"""

    @pytest.fixture
    def storage(self):
        return InMemoryCheckpointStorage()

    @pytest.mark.asyncio
    async def test_save_and_load(self, storage):
        """测试保存和加载"""
        checkpoint = TaskCheckpoint(
            task_id="task-1",
            user_id="user-1",
            step_index=1,
            state={"data": "test"},
        )

        await storage.save(checkpoint)
        loaded = await storage.load("task-1", "user-1")

        assert loaded is not None
        assert loaded.task_id == "task-1"
        assert loaded.state["data"] == "test"

    @pytest.mark.asyncio
    async def test_load_returns_latest(self, storage):
        """测试加载返回最新的检查点"""
        for i in range(3):
            checkpoint = TaskCheckpoint(
                task_id="task-1",
                user_id="user-1",
                step_index=i,
                state={"step": i},
            )
            await storage.save(checkpoint)

        loaded = await storage.load("task-1", "user-1")

        assert loaded is not None
        assert loaded.step_index == 2
        assert loaded.state["step"] == 2

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, storage):
        """测试加载不存在的检查点"""
        loaded = await storage.load("nonexistent", "user-1")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_by_id(self, storage):
        """测试按ID加载"""
        checkpoint = TaskCheckpoint(
            id="specific-id",
            task_id="task-1",
            user_id="user-1",
            step_index=1,
        )
        await storage.save(checkpoint)

        loaded = await storage.load_by_id("specific-id")

        assert loaded is not None
        assert loaded.id == "specific-id"

    @pytest.mark.asyncio
    async def test_delete(self, storage):
        """测试删除"""
        checkpoint = TaskCheckpoint(
            task_id="task-1",
            user_id="user-1",
            step_index=1,
        )
        await storage.save(checkpoint)

        await storage.delete("task-1", "user-1")
        loaded = await storage.load("task-1", "user-1")

        assert loaded is None

    @pytest.mark.asyncio
    async def test_list_checkpoints(self, storage):
        """测试列出所有检查点"""
        for i in range(5):
            checkpoint = TaskCheckpoint(
                task_id="task-1",
                user_id="user-1",
                step_index=i,
            )
            await storage.save(checkpoint)

        checkpoints = await storage.list_checkpoints("task-1", "user-1")

        assert len(checkpoints) == 5

    @pytest.mark.asyncio
    async def test_user_isolation(self, storage):
        """测试用户隔离"""
        # 用户1的检查点
        await storage.save(TaskCheckpoint(
            task_id="task-1",
            user_id="user-1",
            step_index=1,
            state={"user": "1"},
        ))

        # 用户2的检查点
        await storage.save(TaskCheckpoint(
            task_id="task-1",
            user_id="user-2",
            step_index=1,
            state={"user": "2"},
        ))

        # 用户1只能看到自己的
        loaded = await storage.load("task-1", "user-1")
        assert loaded.state["user"] == "1"

        # 用户2只能看到自己的
        loaded = await storage.load("task-1", "user-2")
        assert loaded.state["user"] == "2"


class TestCheckpointManager:
    """测试检查点管理器"""

    @pytest.fixture
    def manager(self):
        storage = InMemoryCheckpointStorage()
        return CheckpointManager(storage)

    @pytest.mark.asyncio
    async def test_create_checkpoint(self, manager):
        """测试创建检查点"""
        checkpoint = await manager.create_checkpoint(
            task_id="task-1",
            user_id="user-1",
            step_index=5,
            state={"url": "https://example.com"},
            metadata={"source": "test"},
        )

        assert checkpoint.task_id == "task-1"
        assert checkpoint.step_index == 5
        assert checkpoint.state["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self, manager):
        """测试获取最新检查点"""
        await manager.create_checkpoint("task-1", "user-1", 1, {"step": 1})
        await manager.create_checkpoint("task-1", "user-1", 2, {"step": 2})
        await manager.create_checkpoint("task-1", "user-1", 3, {"step": 3})

        latest = await manager.get_latest_checkpoint("task-1", "user-1")

        assert latest is not None
        assert latest.step_index == 3

    @pytest.mark.asyncio
    async def test_can_resume(self, manager):
        """测试检查是否可以恢复"""
        # 没有检查点时不能恢复
        assert await manager.can_resume("task-1", "user-1") is False

        # 有检查点时可以恢复
        await manager.create_checkpoint("task-1", "user-1", 1, {})
        assert await manager.can_resume("task-1", "user-1") is True

    @pytest.mark.asyncio
    async def test_get_resume_info(self, manager):
        """测试获取恢复信息"""
        await manager.create_checkpoint(
            "task-1", "user-1", 5,
            {"url": "https://example.com"},
        )

        info = await manager.get_resume_info("task-1", "user-1")

        assert info is not None
        assert info["step_index"] == 5
        assert info["state"]["url"] == "https://example.com"
        assert "checkpoint_id" in info
        assert "created_at" in info

    @pytest.mark.asyncio
    async def test_clear_checkpoints(self, manager):
        """测试清除检查点"""
        await manager.create_checkpoint("task-1", "user-1", 1, {})
        await manager.create_checkpoint("task-1", "user-1", 2, {})

        await manager.clear_checkpoints("task-1", "user-1")

        assert await manager.can_resume("task-1", "user-1") is False

    @pytest.mark.asyncio
    async def test_get_checkpoint_history(self, manager):
        """测试获取检查点历史"""
        for i in range(5):
            await manager.create_checkpoint("task-1", "user-1", i, {"step": i})

        history = await manager.get_checkpoint_history("task-1", "user-1")

        assert len(history) == 5
        # 验证顺序
        for i, cp in enumerate(history):
            assert cp.step_index == i
