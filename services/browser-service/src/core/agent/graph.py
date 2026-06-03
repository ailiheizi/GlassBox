"""
状态图执行引擎 - 借鉴 LangGraph 设计

支持:
- 图状态机定义
- 条件分支
- 并行执行
- 检查点恢复
- Human-in-the-Loop
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Dict, Any, List, Optional, Callable, Awaitable,
    TypeVar, Generic, Union, AsyncIterator
)
import asyncio
import uuid
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


class NodeType(Enum):
    """节点类型"""
    START = "start"
    END = "end"
    ACTION = "action"
    DECISION = "decision"
    HUMAN = "human"
    PARALLEL = "parallel"
    SUBGRAPH = "subgraph"


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GraphState:
    """图状态"""
    data: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    current_node: str = "start"
    status: ExecutionStatus = ExecutionStatus.PENDING
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def update(self, updates: Dict[str, Any]) -> 'GraphState':
        """更新状态"""
        self.data.update(updates)
        self.updated_at = datetime.now()
        return self

    def add_history(self, node: str, action: str, result: Any = None):
        """添加历史记录"""
        self.history.append({
            "node": node,
            "action": action,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "data": self.data,
            "history": self.history,
            "current_node": self.current_node,
            "status": self.status.value,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphState':
        """从字典创建"""
        state = cls()
        state.data = data.get("data", {})
        state.history = data.get("history", [])
        state.current_node = data.get("current_node", "start")
        state.status = ExecutionStatus(data.get("status", "pending"))
        state.error = data.get("error")
        if "created_at" in data:
            state.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            state.updated_at = datetime.fromisoformat(data["updated_at"])
        return state


# 节点处理函数类型
NodeHandler = Callable[[GraphState], Awaitable[GraphState]]
ConditionHandler = Callable[[GraphState], Awaitable[str]]


@dataclass
class Node:
    """图节点"""
    name: str
    node_type: NodeType
    handler: Optional[NodeHandler] = None
    condition: Optional[ConditionHandler] = None
    description: str = ""
    timeout: Optional[float] = None  # 超时时间（秒）
    retry_count: int = 0  # 重试次数
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """图边"""
    from_node: str
    to_node: str
    condition: Optional[str] = None  # 条件标签
    priority: int = 0  # 优先级（用于多条边时）


@dataclass
class Checkpoint:
    """检查点"""
    id: str
    graph_id: str
    state: GraphState
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "graph_id": self.graph_id,
            "state": self.state.to_dict(),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        return cls(
            id=data["id"],
            graph_id=data["graph_id"],
            state=GraphState.from_dict(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class CheckpointStore(ABC):
    """检查点存储接口"""

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> None:
        """保存检查点"""
        pass

    @abstractmethod
    async def load(self, graph_id: str) -> Optional[Checkpoint]:
        """加载最新检查点"""
        pass

    @abstractmethod
    async def delete(self, graph_id: str) -> None:
        """删除检查点"""
        pass

    @abstractmethod
    async def list_checkpoints(self, graph_id: str) -> List[Checkpoint]:
        """列出所有检查点"""
        pass


class InMemoryCheckpointStore(CheckpointStore):
    """内存检查点存储"""

    def __init__(self):
        self._checkpoints: Dict[str, List[Checkpoint]] = {}

    async def save(self, checkpoint: Checkpoint) -> None:
        if checkpoint.graph_id not in self._checkpoints:
            self._checkpoints[checkpoint.graph_id] = []
        self._checkpoints[checkpoint.graph_id].append(checkpoint)

    async def load(self, graph_id: str) -> Optional[Checkpoint]:
        checkpoints = self._checkpoints.get(graph_id, [])
        if checkpoints:
            return checkpoints[-1]
        return None

    async def delete(self, graph_id: str) -> None:
        if graph_id in self._checkpoints:
            del self._checkpoints[graph_id]

    async def list_checkpoints(self, graph_id: str) -> List[Checkpoint]:
        return self._checkpoints.get(graph_id, [])


@dataclass
class ExecutionEvent:
    """执行事件"""
    event_type: str  # node_start, node_end, state_update, error, human_required
    node: str
    state: GraphState
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class StateGraph:
    """
    状态图执行引擎

    用法:
        graph = StateGraph("my_graph")

        # 添加节点
        graph.add_node("start", NodeType.START)
        graph.add_node("process", NodeType.ACTION, handler=process_handler)
        graph.add_node("decide", NodeType.DECISION, condition=decide_condition)
        graph.add_node("end", NodeType.END)

        # 添加边
        graph.add_edge("start", "process")
        graph.add_edge("process", "decide")
        graph.add_edge("decide", "end", condition="done")
        graph.add_edge("decide", "process", condition="continue")

        # 执行
        async for event in graph.run(initial_state):
            print(event)
    """

    def __init__(
        self,
        name: str,
        checkpoint_store: Optional[CheckpointStore] = None,
    ):
        self.name = name
        self.id = str(uuid.uuid4())
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, List[Edge]] = {}
        self._checkpoint_store = checkpoint_store or InMemoryCheckpointStore()

        # 自动添加 start 和 end 节点
        self.add_node("start", NodeType.START)
        self.add_node("end", NodeType.END)

    def add_node(
        self,
        name: str,
        node_type: NodeType,
        handler: Optional[NodeHandler] = None,
        condition: Optional[ConditionHandler] = None,
        description: str = "",
        timeout: Optional[float] = None,
        retry_count: int = 0,
        **metadata,
    ) -> 'StateGraph':
        """添加节点"""
        self._nodes[name] = Node(
            name=name,
            node_type=node_type,
            handler=handler,
            condition=condition,
            description=description,
            timeout=timeout,
            retry_count=retry_count,
            metadata=metadata,
        )
        return self

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[str] = None,
        priority: int = 0,
    ) -> 'StateGraph':
        """添加边"""
        if from_node not in self._edges:
            self._edges[from_node] = []

        self._edges[from_node].append(Edge(
            from_node=from_node,
            to_node=to_node,
            condition=condition,
            priority=priority,
        ))

        # 按优先级排序
        self._edges[from_node].sort(key=lambda e: -e.priority)
        return self

    def get_node(self, name: str) -> Optional[Node]:
        """获取节点"""
        return self._nodes.get(name)

    def get_edges(self, from_node: str) -> List[Edge]:
        """获取从指定节点出发的边"""
        return self._edges.get(from_node, [])

    async def _get_next_node(self, current: str, state: GraphState) -> Optional[str]:
        """获取下一个节点"""
        node = self._nodes.get(current)
        if not node:
            return None

        edges = self.get_edges(current)
        if not edges:
            return None

        # 如果是决策节点，使用条件函数
        if node.node_type == NodeType.DECISION and node.condition:
            condition_result = await node.condition(state)
            for edge in edges:
                if edge.condition == condition_result:
                    return edge.to_node
            # 如果没有匹配的条件，使用第一条边
            return edges[0].to_node if edges else None

        # 否则使用第一条边
        return edges[0].to_node if edges else None

    async def _execute_node(self, node: Node, state: GraphState) -> GraphState:
        """执行节点"""
        if node.handler is None:
            return state

        # 支持重试
        last_error = None
        for attempt in range(node.retry_count + 1):
            try:
                if node.timeout:
                    state = await asyncio.wait_for(
                        node.handler(state),
                        timeout=node.timeout,
                    )
                else:
                    state = await node.handler(state)
                return state
            except asyncio.TimeoutError:
                last_error = f"Node {node.name} timed out after {node.timeout}s"
                logger.warning(f"{last_error} (attempt {attempt + 1}/{node.retry_count + 1})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Node {node.name} failed: {e} (attempt {attempt + 1}/{node.retry_count + 1})")

        # 所有重试都失败
        state.error = last_error
        state.status = ExecutionStatus.FAILED
        return state

    async def _save_checkpoint(self, state: GraphState) -> None:
        """保存检查点"""
        checkpoint = Checkpoint(
            id=str(uuid.uuid4()),
            graph_id=self.id,
            state=state,
        )
        await self._checkpoint_store.save(checkpoint)

    async def run(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        resume_from_checkpoint: bool = False,
    ) -> AsyncIterator[ExecutionEvent]:
        """
        执行图

        Args:
            initial_state: 初始状态数据
            resume_from_checkpoint: 是否从检查点恢复

        Yields:
            执行事件
        """
        # 初始化或恢复状态
        if resume_from_checkpoint:
            checkpoint = await self._checkpoint_store.load(self.id)
            if checkpoint:
                state = checkpoint.state
                logger.info(f"Resumed from checkpoint at node: {state.current_node}")
            else:
                state = GraphState(data=initial_state or {})
        else:
            state = GraphState(data=initial_state or {})

        state.status = ExecutionStatus.RUNNING
        current_node = state.current_node

        while current_node != "end":
            node = self._nodes.get(current_node)
            if not node:
                state.error = f"Node not found: {current_node}"
                state.status = ExecutionStatus.FAILED
                yield ExecutionEvent(
                    event_type="error",
                    node=current_node,
                    state=state,
                    data={"error": state.error},
                )
                break

            # 发送节点开始事件
            yield ExecutionEvent(
                event_type="node_start",
                node=current_node,
                state=state,
            )

            # 处理 Human-in-the-Loop 节点
            if node.node_type == NodeType.HUMAN:
                state.status = ExecutionStatus.WAITING_HUMAN
                state.current_node = current_node
                await self._save_checkpoint(state)

                yield ExecutionEvent(
                    event_type="human_required",
                    node=current_node,
                    state=state,
                    data={"message": node.description or "Human input required"},
                )
                return  # 暂停执行，等待人工输入

            # 执行节点
            state = await self._execute_node(node, state)
            state.add_history(current_node, "executed")

            # 检查执行状态
            if state.status == ExecutionStatus.FAILED:
                yield ExecutionEvent(
                    event_type="error",
                    node=current_node,
                    state=state,
                    data={"error": state.error},
                )
                break

            # 发送节点结束事件
            yield ExecutionEvent(
                event_type="node_end",
                node=current_node,
                state=state,
            )

            # 保存检查点
            await self._save_checkpoint(state)

            # 获取下一个节点
            next_node = await self._get_next_node(current_node, state)
            if next_node is None:
                state.error = f"No outgoing edge from node: {current_node}"
                state.status = ExecutionStatus.FAILED
                yield ExecutionEvent(
                    event_type="error",
                    node=current_node,
                    state=state,
                    data={"error": state.error},
                )
                break

            current_node = next_node
            state.current_node = current_node

        # 执行完成
        if state.status != ExecutionStatus.FAILED:
            state.status = ExecutionStatus.COMPLETED
            yield ExecutionEvent(
                event_type="completed",
                node="end",
                state=state,
            )

    async def resume_with_human_input(
        self,
        human_input: Dict[str, Any],
    ) -> AsyncIterator[ExecutionEvent]:
        """
        使用人工输入恢复执行

        Args:
            human_input: 人工输入数据

        Yields:
            执行事件
        """
        checkpoint = await self._checkpoint_store.load(self.id)
        if not checkpoint:
            raise ValueError("No checkpoint found to resume from")

        state = checkpoint.state
        if state.status != ExecutionStatus.WAITING_HUMAN:
            raise ValueError(f"Graph is not waiting for human input, status: {state.status}")

        # 更新状态
        state.update(human_input)
        state.add_history(state.current_node, "human_input", human_input)

        # 获取下一个节点
        next_node = await self._get_next_node(state.current_node, state)
        if next_node:
            state.current_node = next_node
            state.status = ExecutionStatus.RUNNING

            # 继续执行
            async for event in self.run(resume_from_checkpoint=True):
                yield event
        else:
            state.status = ExecutionStatus.COMPLETED
            yield ExecutionEvent(
                event_type="completed",
                node="end",
                state=state,
            )

    def visualize(self) -> str:
        """生成图的可视化表示 (Mermaid 格式)"""
        lines = ["graph TD"]

        for node in self._nodes.values():
            shape = {
                NodeType.START: f"{node.name}(({node.name}))",
                NodeType.END: f"{node.name}(({node.name}))",
                NodeType.ACTION: f"{node.name}[{node.name}]",
                NodeType.DECISION: f"{node.name}{{{node.name}}}",
                NodeType.HUMAN: f"{node.name}[/{node.name}/]",
                NodeType.PARALLEL: f"{node.name}[[{node.name}]]",
            }.get(node.node_type, f"{node.name}[{node.name}]")
            lines.append(f"    {shape}")

        for from_node, edges in self._edges.items():
            for edge in edges:
                if edge.condition:
                    lines.append(f"    {from_node} -->|{edge.condition}| {edge.to_node}")
                else:
                    lines.append(f"    {from_node} --> {edge.to_node}")

        return "\n".join(lines)


# ==================== 便捷构建器 ====================

class GraphBuilder:
    """图构建器 - 链式 API"""

    def __init__(self, name: str):
        self._graph = StateGraph(name)
        self._current_node: Optional[str] = None

    def node(
        self,
        name: str,
        handler: NodeHandler,
        node_type: NodeType = NodeType.ACTION,
        **kwargs,
    ) -> 'GraphBuilder':
        """添加节点"""
        self._graph.add_node(name, node_type, handler=handler, **kwargs)
        if self._current_node:
            self._graph.add_edge(self._current_node, name)
        self._current_node = name
        return self

    def decision(
        self,
        name: str,
        condition: ConditionHandler,
        **kwargs,
    ) -> 'GraphBuilder':
        """添加决策节点"""
        self._graph.add_node(name, NodeType.DECISION, condition=condition, **kwargs)
        if self._current_node:
            self._graph.add_edge(self._current_node, name)
        self._current_node = name
        return self

    def human(self, name: str, description: str = "", **kwargs) -> 'GraphBuilder':
        """添加人工节点"""
        self._graph.add_node(name, NodeType.HUMAN, description=description, **kwargs)
        if self._current_node:
            self._graph.add_edge(self._current_node, name)
        self._current_node = name
        return self

    def branch(self, condition: str, to_node: str) -> 'GraphBuilder':
        """添加条件分支"""
        if self._current_node:
            self._graph.add_edge(self._current_node, to_node, condition=condition)
        return self

    def to_end(self) -> 'GraphBuilder':
        """连接到结束节点"""
        if self._current_node:
            self._graph.add_edge(self._current_node, "end")
        return self

    def from_start(self) -> 'GraphBuilder':
        """从开始节点开始"""
        self._current_node = "start"
        return self

    def build(self) -> StateGraph:
        """构建图"""
        return self._graph
