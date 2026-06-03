from typing import Dict, Any, Optional
from .trajectory import Trajectory
import logging
import os

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """推理引擎"""

    def __init__(self, llm, trajectory: Optional[Trajectory] = None):
        self.llm = llm
        self.trajectory = trajectory or Trajectory()

    async def analyze(
        self,
        message: str,
        screenshot: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """分析用户消息并生成推理

        Args:
            message: 用户消息
            screenshot: 截图 base64（可选）
            context: 额外上下文

        Returns:
            推理结果，包含 content 和 reasoning
        """
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        # 构建提示词
        prompt = self._build_prompt(message, screenshot, context)

        # 选择模型：有截图用视觉模型，否则用文本模型
        model = "deepseek-chat"  # 默认文本模型

        # 调用 LLM 进行推理
        response = await self.llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": "你是一个 AI Agent 推理引擎，负责分析用户意图并规划执行步骤。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=model,
            max_tokens=2048,
        )

        # 处理 DoubaoLLM 的响应格式
        if "message" in response:
            content = response["message"].get("content", "")
        else:
            content = response.get("content", "")

        result = {
            "content": content,
            "reasoning": response.get("reasoning", content),  # 如果没有单独的reasoning，使用content
            "trajectory_context": self.trajectory.get_context()
        }

        logger.info(f"Reasoning completed for message: {message[:50]}")
        return result

    def _build_prompt(
        self,
        message: str,
        screenshot: Optional[str],
        context: Optional[Dict]
    ) -> str:
        """构建推理提示词"""
        prompt_parts = [f"用户消息: {message}"]

        # 添加历史轨迹
        if self.trajectory.steps:
            trajectory_context = self.trajectory.get_context(last_n=3)
            prompt_parts.append(f"\n历史操作:\n{trajectory_context}")

        # 添加截图信息
        if screenshot:
            prompt_parts.append("\n[包含屏幕截图]")

        # 添加额外上下文
        if context:
            prompt_parts.append(f"\n额外上下文: {context}")

        prompt_parts.append("\n请分析用户意图并说明需要执行的操作。")

        return "\n".join(prompt_parts)

    def set_trajectory(self, trajectory: Trajectory):
        """设置轨迹"""
        self.trajectory = trajectory

    def add_step(
        self,
        action: str,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None
    ):
        """添加推理步骤到轨迹"""
        self.trajectory.add_step(action, params, result, reasoning)
