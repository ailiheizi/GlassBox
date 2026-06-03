"""
单元测试 - 状态图执行引擎
"""
import pytest
from typing import Dict, Any

from src.core.agent.graph import (
    StateGraph,
    GraphState,
    NodeType,
    ExecutionStatus,
    ExecutionEvent,
    GraphBuilder,
    InMemoryCheckpointStore,
)


class TestGraphState:
    """测试图状态"""

    def test_update(self):
        """测试状态更新"""
        state = GraphState(data={"a": 1})
        state.update({"b": 2})

        assert state.data["a"] == 1
        assert state.data["b"] == 2

    def test_add_history(self):
        """测试添加历史"""
        state = GraphState()
        state.add_history("node1", "executed", {"result": "ok"})

        assert len(state.history) == 1
        assert state.history[0]["node"] == "node1"
        assert state.history[0]["action"] == "executed"

    def test_to_dict(self):
        """测试转换为字典"""
        state = GraphState(
            data={"key": "value"},
            current_node="process",
            status=ExecutionStatus.RUNNING,
        )

        result = state.to_dict()

        assert result["data"]["key"] == "value"
        assert result["current_node"] == "process"
        assert result["status"] == "running"

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "data": {"key": "value"},
            "current_node": "process",
            "status": "running",
            "history": [{"node": "start", "action": "executed"}],
        }

        state = GraphState.from_dict(data)

        assert state.data["key"] == "value"
        assert state.current_node == "process"
        assert state.status == ExecutionStatus.RUNNING
        assert len(state.history) == 1


class TestStateGraph:
    """测试状态图"""

    def test_add_node(self):
        """测试添加节点"""
        graph = StateGraph("test")

        async def handler(state: GraphState) -> GraphState:
            return state

        graph.add_node("process", NodeType.ACTION, handler=handler)

        node = graph.get_node("process")
        assert node is not None
        assert node.name == "process"
        assert node.node_type == NodeType.ACTION

    def test_add_edge(self):
        """测试添加边"""
        graph = StateGraph("test")
        graph.add_node("process", NodeType.ACTION)
        graph.add_edge("start", "process")
        graph.add_edge("process", "end")

        edges = graph.get_edges("start")
        assert len(edges) == 1
        assert edges[0].to_node == "process"

    def test_default_nodes(self):
        """测试默认节点"""
        graph = StateGraph("test")

        assert graph.get_node("start") is not None
        assert graph.get_node("end") is not None

    @pytest.mark.asyncio
    async def test_simple_execution(self):
        """测试简单执行"""
        graph = StateGraph("test")

        async def process(state: GraphState) -> GraphState:
            state.update({"processed": True})
            return state

        graph.add_node("process", NodeType.ACTION, handler=process)
        graph.add_edge("start", "process")
        graph.add_edge("process", "end")

        events = []
        async for event in graph.run({"input": "test"}):
            events.append(event)

        # 检查事件
        assert any(e.event_type == "node_start" for e in events)
        assert any(e.event_type == "node_end" for e in events)
        assert any(e.event_type == "completed" for e in events)

        # 检查最终状态
        final_event = events[-1]
        assert final_event.state.data["processed"] is True

    @pytest.mark.asyncio
    async def test_decision_node(self):
        """测试决策节点"""
        graph = StateGraph("test")

        async def check_value(state: GraphState) -> str:
            if state.data.get("value", 0) > 10:
                return "high"
            return "low"

        async def handle_high(state: GraphState) -> GraphState:
            state.update({"result": "high_path"})
            return state

        async def handle_low(state: GraphState) -> GraphState:
            state.update({"result": "low_path"})
            return state

        graph.add_node("decide", NodeType.DECISION, condition=check_value)
        graph.add_node("high_handler", NodeType.ACTION, handler=handle_high)
        graph.add_node("low_handler", NodeType.ACTION, handler=handle_low)

        graph.add_edge("start", "decide")
        graph.add_edge("decide", "high_handler", condition="high")
        graph.add_edge("decide", "low_handler", condition="low")
        graph.add_edge("high_handler", "end")
        graph.add_edge("low_handler", "end")

        # 测试高值路径
        events = []
        async for event in graph.run({"value": 15}):
            events.append(event)

        final = events[-1]
        assert final.state.data["result"] == "high_path"

    @pytest.mark.asyncio
    async def test_human_node(self):
        """测试人工节点"""
        graph = StateGraph("test")

        async def before_human(state: GraphState) -> GraphState:
            state.update({"before": True})
            return state

        graph.add_node("prepare", NodeType.ACTION, handler=before_human)
        graph.add_node("review", NodeType.HUMAN, description="需要人工审核")
        graph.add_node("after", NodeType.ACTION)

        graph.add_edge("start", "prepare")
        graph.add_edge("prepare", "review")
        graph.add_edge("review", "after")
        graph.add_edge("after", "end")

        events = []
        async for event in graph.run():
            events.append(event)

        # 应该在人工节点暂停
        assert any(e.event_type == "human_required" for e in events)
        final = events[-1]
        assert final.state.status == ExecutionStatus.WAITING_HUMAN

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self):
        """测试从检查点恢复"""
        store = InMemoryCheckpointStore()
        graph = StateGraph("test", checkpoint_store=store)

        call_count = {"value": 0}

        async def increment(state: GraphState) -> GraphState:
            call_count["value"] += 1
            state.update({"count": call_count["value"]})
            return state

        graph.add_node("step1", NodeType.ACTION, handler=increment)
        graph.add_node("step2", NodeType.ACTION, handler=increment)

        graph.add_edge("start", "step1")
        graph.add_edge("step1", "step2")
        graph.add_edge("step2", "end")

        # 第一次执行
        async for _ in graph.run():
            pass

        assert call_count["value"] == 2

    @pytest.mark.asyncio
    async def test_node_timeout(self):
        """测试节点超时"""
        import asyncio

        graph = StateGraph("test")

        async def slow_handler(state: GraphState) -> GraphState:
            await asyncio.sleep(2)
            return state

        graph.add_node("slow", NodeType.ACTION, handler=slow_handler, timeout=0.1)
        graph.add_edge("start", "slow")
        graph.add_edge("slow", "end")

        events = []
        async for event in graph.run():
            events.append(event)

        # 应该失败
        final = events[-1]
        assert final.state.status == ExecutionStatus.FAILED
        assert "timed out" in final.state.error

    @pytest.mark.asyncio
    async def test_node_retry(self):
        """测试节点重试"""
        attempt_count = {"value": 0}

        graph = StateGraph("test")

        async def flaky_handler(state: GraphState) -> GraphState:
            attempt_count["value"] += 1
            if attempt_count["value"] < 3:
                raise Exception("Temporary failure")
            state.update({"success": True})
            return state

        graph.add_node("flaky", NodeType.ACTION, handler=flaky_handler, retry_count=3)
        graph.add_edge("start", "flaky")
        graph.add_edge("flaky", "end")

        events = []
        async for event in graph.run():
            events.append(event)

        # 应该成功（第3次尝试）
        final = events[-1]
        assert final.state.status == ExecutionStatus.COMPLETED
        assert attempt_count["value"] == 3

    def test_visualize(self):
        """测试可视化"""
        graph = StateGraph("test")
        graph.add_node("process", NodeType.ACTION)
        graph.add_node("decide", NodeType.DECISION)
        graph.add_edge("start", "process")
        graph.add_edge("process", "decide")
        graph.add_edge("decide", "end", condition="done")

        mermaid = graph.visualize()

        assert "graph TD" in mermaid
        assert "process" in mermaid
        assert "decide" in mermaid
        assert "done" in mermaid


class TestGraphBuilder:
    """测试图构建器"""

    def test_chain_api(self):
        """测试链式 API"""
        async def handler(state: GraphState) -> GraphState:
            return state

        async def condition(state: GraphState) -> str:
            return "next"

        graph = (GraphBuilder("test")
            .from_start()
            .node("step1", handler)
            .node("step2", handler)
            .decision("check", condition)
            .branch("next", "end")
            .build())

        assert graph.get_node("step1") is not None
        assert graph.get_node("step2") is not None
        assert graph.get_node("check") is not None

    def test_human_node(self):
        """测试人工节点"""
        async def handler(state: GraphState) -> GraphState:
            return state

        graph = (GraphBuilder("test")
            .from_start()
            .node("prepare", handler)
            .human("review", "需要审核")
            .to_end()
            .build())

        review_node = graph.get_node("review")
        assert review_node is not None
        assert review_node.node_type == NodeType.HUMAN
        assert review_node.description == "需要审核"

    @pytest.mark.asyncio
    async def test_builder_execution(self):
        """测试构建器创建的图执行"""
        async def add_one(state: GraphState) -> GraphState:
            value = state.data.get("value", 0)
            state.update({"value": value + 1})
            return state

        graph = (GraphBuilder("counter")
            .from_start()
            .node("add1", add_one)
            .node("add2", add_one)
            .node("add3", add_one)
            .to_end()
            .build())

        events = []
        async for event in graph.run({"value": 0}):
            events.append(event)

        final = events[-1]
        assert final.state.data["value"] == 3
