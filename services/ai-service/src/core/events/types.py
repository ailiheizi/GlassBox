"""
事件类型定义
借鉴 OpenHands 的 Action/Observation 事件模式
"""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class EventType(str, Enum):
    """事件类型枚举"""
    # Agent 事件
    AGENT_THINKING = "agent.thinking"
    AGENT_ACTION = "agent.action"
    AGENT_MESSAGE = "agent.message"
    AGENT_STATE_CHANGE = "agent.state_change"

    # 工具事件
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    TOOL_ERROR = "tool.error"

    # 沙箱事件
    SANDBOX_CREATED = "sandbox.created"
    SANDBOX_DESTROYED = "sandbox.destroyed"
    SANDBOX_SCREENSHOT = "sandbox.screenshot"
    SANDBOX_COMMAND = "sandbox.command"

    # 规划事件
    PLAN_CREATED = "plan.created"
    PLAN_STEP_START = "plan.step_start"
    PLAN_STEP_COMPLETE = "plan.step_complete"
    PLAN_COMPLETE = "plan.complete"

    # 审查事件
    REVIEW_START = "review.start"
    REVIEW_RESULT = "review.result"

    # 系统事件
    SYSTEM_INFO = "system.info"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_ERROR = "system.error"

    # 流程事件
    STREAM_START = "stream.start"
    STREAM_END = "stream.end"
    STREAM_CHUNK = "stream.chunk"


@dataclass
class Event:
    """基础事件类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType = EventType.SYSTEM_INFO
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"  # 事件来源：planner, executor, reviewer, system
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }

    def to_sse(self) -> str:
        """转换为 SSE 格式"""
        import json
        return f"data: {json.dumps(self.to_dict())}\n\n"


@dataclass
class ActionEvent(Event):
    """动作事件 - Agent 执行的操作"""
    action_type: str = ""  # click, type, shell, browser 等
    action_args: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = EventType.AGENT_ACTION
        self.data = {
            "action_type": self.action_type,
            "action_args": self.action_args,
        }


@dataclass
class ObservationEvent(Event):
    """观察事件 - Agent 观察到的结果"""
    observation_type: str = ""  # screenshot, command_output, error 等
    content: Any = None
    success: bool = True

    def __post_init__(self):
        self.type = EventType.TOOL_RESULT
        self.data = {
            "observation_type": self.observation_type,
            "content": self.content,
            "success": self.success,
        }


@dataclass
class ThinkingEvent(Event):
    """思考事件 - Agent 的思考过程"""
    content: str = ""
    step: int = 0

    def __post_init__(self):
        self.type = EventType.AGENT_THINKING
        self.data = {
            "content": self.content,
            "step": self.step,
        }


@dataclass
class PlanEvent(Event):
    """规划事件"""
    plan_steps: list = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 0

    def __post_init__(self):
        self.type = EventType.PLAN_CREATED
        self.data = {
            "plan_steps": self.plan_steps,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
        }


@dataclass
class ReviewEvent(Event):
    """审查事件"""
    passed: bool = False
    feedback: str = ""
    suggestions: list = field(default_factory=list)

    def __post_init__(self):
        self.type = EventType.REVIEW_RESULT
        self.data = {
            "passed": self.passed,
            "feedback": self.feedback,
            "suggestions": self.suggestions,
        }


@dataclass
class ToolCallEvent(Event):
    """工具调用事件"""
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = EventType.TOOL_CALL
        self.data = {
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
        }


@dataclass
class ToolResultEvent(Event):
    """工具结果事件"""
    tool_name: str = ""
    result: Any = None
    success: bool = True
    error: Optional[str] = None

    def __post_init__(self):
        self.type = EventType.TOOL_RESULT
        self.data = {
            "tool_name": self.tool_name,
            "result": self.result,
            "success": self.success,
            "error": self.error,
        }
