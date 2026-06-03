"""
AgentState 定义
LangGraph 状态图的状态类型
"""

from typing import TypedDict, Annotated, List, Dict, Any, Literal, Optional
import operator


class PlanStep(TypedDict):
    """规划步骤"""
    step_id: int
    description: str
    tool: Optional[str]
    args: Optional[Dict[str, Any]]
    status: Literal["pending", "executing", "completed", "failed", "skipped"]
    result: Optional[Any]


class ActionRecord(TypedDict):
    """执行记录"""
    step: int
    action_type: str
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    result: Optional[Any]
    success: bool
    error: Optional[str]
    timestamp: str


class SandboxInfo(TypedDict):
    """沙箱信息"""
    id: str
    user_id: str
    screencast_url: str
    agent_url: str
    status: str


class AgentState(TypedDict):
    """
    Agent 状态定义
    用于 LangGraph StateGraph
    """
    # 任务信息
    task: str  # 用户的原始任务描述
    user_id: str  # 用户 ID
    session_id: str  # 会话 ID

    # 执行状态
    status: Literal["planning", "executing", "reviewing", "completed", "failed"]
    iteration: int  # 当前迭代次数
    max_iterations: int  # 最大迭代次数

    # 规划结果
    plan: List[PlanStep]  # 执行计划
    current_step: int  # 当前执行步骤索引

    # 执行历史 (使用 reducer 累加)
    actions: Annotated[List[ActionRecord], operator.add]

    # 截图和沙箱信息
    screenshot: Optional[str]  # base64 编码的截图
    screenshot_width: Optional[int]
    screenshot_height: Optional[int]
    sandbox_info: Optional[SandboxInfo]

    # 思考和推理
    thinking: str  # 当前思考内容
    reasoning: str  # 推理过程

    # 审查结果
    review_passed: bool
    review_feedback: str
    review_suggestions: List[str]

    # 消息历史（用于 LLM 对话）
    messages: List[Dict[str, Any]]

    # 错误信息
    error: Optional[str]


def create_initial_state(
    task: str,
    user_id: str,
    session_id: str,
    sandbox_info: Optional[SandboxInfo] = None,
    max_iterations: int = 5
) -> AgentState:
    """
    创建初始状态

    Args:
        task: 用户任务描述
        user_id: 用户 ID
        session_id: 会话 ID
        sandbox_info: 沙箱信息
        max_iterations: 最大迭代次数

    Returns:
        初始化的 AgentState
    """
    return AgentState(
        task=task,
        user_id=user_id,
        session_id=session_id,
        status="planning",
        iteration=0,
        max_iterations=max_iterations,
        plan=[],
        current_step=0,
        actions=[],
        screenshot=None,
        screenshot_width=None,
        screenshot_height=None,
        sandbox_info=sandbox_info,
        thinking="",
        reasoning="",
        review_passed=False,
        review_feedback="",
        review_suggestions=[],
        messages=[],
        error=None,
    )
