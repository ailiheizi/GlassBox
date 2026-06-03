"""
LangGraph StateGraph 构建
创建 Planner -> Executor -> Reviewer 的状态图
"""

from typing import Literal, Optional, Any, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import PlannerNode, ExecutorNode, ReviewerNode


def route_after_review(state: AgentState) -> Literal["planner", "executor", "end"]:
    """
    审查后的路由决策

    Args:
        state: 当前状态

    Returns:
        下一个节点名称
    """
    # 检查是否通过审查
    if state.get("review_passed", False):
        return "end"

    # 检查是否达到最大迭代次数
    if state.get("iteration", 0) >= state.get("max_iterations", 5):
        return "end"

    # 检查是否有错误
    if state.get("error"):
        return "end"

    # 需要重新规划
    return "planner"


def route_after_executor(state: AgentState) -> Literal["executor", "reviewer"]:
    """
    执行后的路由决策

    Args:
        state: 当前状态

    Returns:
        下一个节点名称
    """
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    # 如果还有步骤要执行
    if current_step < len(plan):
        return "executor"

    # 所有步骤执行完毕，进入审查
    return "reviewer"


def create_sandbox_agent_graph(
    sandbox_client: Any,
    llm_client: Any,
    checkpointer: Optional[Any] = None,
    skill_selector: Optional[Any] = None,
) -> Any:
    """
    创建沙箱 Agent 状态图

    Args:
        sandbox_client: 沙箱客户端
        llm_client: LLM 客户端
        checkpointer: 检查点保存器，默认自动创建 MemorySaver
        skill_selector: 技能选择器（用于注入匹配技能到 Planner）

    Returns:
        编译后的状态图
    """
    # 创建节点
    planner = PlannerNode(llm_client, skill_selector=skill_selector)
    executor = ExecutorNode(sandbox_client)
    reviewer = ReviewerNode(llm_client)

    # 创建状态图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("planner", planner)
    workflow.add_node("executor", executor)
    workflow.add_node("reviewer", reviewer)

    # 添加边
    # START -> planner
    workflow.add_edge(START, "planner")

    # planner -> executor
    workflow.add_edge("planner", "executor")

    # executor -> executor 或 reviewer（条件边）
    workflow.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "executor": "executor",
            "reviewer": "reviewer"
        }
    )

    # reviewer -> planner 或 end（条件边）
    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "planner": "planner",
            "end": END
        }
    )

    # 使用检查点保存器（默认自动创建 MemorySaver）
    if checkpointer is None:
        checkpointer = MemorySaver()

    # 编译图
    return workflow.compile(checkpointer=checkpointer)


class SandboxAgentRunner:
    """
    沙箱 Agent 运行器
    封装状态图的执行逻辑
    """

    def __init__(self, sandbox_client: Any, llm_client: Any, skill_selector: Optional[Any] = None):
        self.sandbox_client = sandbox_client
        self.llm_client = llm_client
        self.skill_selector = skill_selector
        self.graph = create_sandbox_agent_graph(sandbox_client, llm_client, skill_selector=skill_selector)

    async def run(
        self,
        task: str,
        user_id: str,
        session_id: str,
        sandbox_info: Optional[Dict] = None,
        max_iterations: int = 5,
        stream: bool = True
    ):
        """
        运行 Agent

        Args:
            task: 任务描述
            user_id: 用户 ID
            session_id: 会话 ID
            sandbox_info: 沙箱信息
            max_iterations: 最大迭代次数
            stream: 是否流式输出

        Yields:
            状态更新事件
        """
        from .state import create_initial_state

        # 创建初始状态
        initial_state = create_initial_state(
            task=task,
            user_id=user_id,
            session_id=session_id,
            sandbox_info=sandbox_info,
            max_iterations=max_iterations
        )

        # 获取初始截图
        try:
            screenshot_data = await self.sandbox_client.get_screenshot(user_id)
            initial_state["screenshot"] = screenshot_data.get("image")
            initial_state["screenshot_width"] = screenshot_data.get("width")
            initial_state["screenshot_height"] = screenshot_data.get("height")
        except:
            pass

        # 配置
        config = {
            "configurable": {
                "thread_id": f"{user_id}-{session_id}"
            }
        }

        if stream:
            # 流式执行
            async for event in self.graph.astream(initial_state, config, stream_mode="updates"):
                yield event
        else:
            # 非流式执行
            result = await self.graph.ainvoke(initial_state, config)
            yield result

    async def get_state(self, user_id: str, session_id: str) -> Optional[AgentState]:
        """
        获取当前状态

        Args:
            user_id: 用户 ID
            session_id: 会话 ID

        Returns:
            当前状态
        """
        config = {
            "configurable": {
                "thread_id": f"{user_id}-{session_id}"
            }
        }

        try:
            state = await self.graph.aget_state(config)
            return state.values if state else None
        except:
            return None


# 全局实例缓存
_agent_runners: Dict[str, SandboxAgentRunner] = {}


def get_agent_runner(
    sandbox_client: Any,
    llm_client: Any,
    cache_key: str = "default"
) -> SandboxAgentRunner:
    """
    获取或创建 Agent 运行器

    Args:
        sandbox_client: 沙箱客户端
        llm_client: LLM 客户端
        cache_key: 缓存键

    Returns:
        Agent 运行器实例
    """
    global _agent_runners

    if cache_key not in _agent_runners:
        _agent_runners[cache_key] = SandboxAgentRunner(sandbox_client, llm_client)

    return _agent_runners[cache_key]
