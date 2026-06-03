from typing import AsyncGenerator, Dict, Any, Optional
from ..sandbox import SandboxClient
from ..skill.selector import SkillSelector
from ..reasoning.engine import ReasoningEngine
from ..reasoning.trajectory import Trajectory
from ..vision.doubao_vision import DoubaoVision
import logging
import re

logger = logging.getLogger(__name__)


class SandboxAgent:
    """沙盒 Agent 编排器"""

    def __init__(
        self,
        llm,
        worker_manager_url: str,
        skill_selector: Optional[SkillSelector] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        vision: Optional[DoubaoVision] = None
    ):
        self.llm = llm
        self.sandbox_client = SandboxClient(worker_manager_url)
        self.skill_selector = skill_selector or SkillSelector()
        self.reasoning_engine = reasoning_engine or ReasoningEngine(llm)
        self.vision = vision
        self.trajectory = Trajectory()
        # Set trajectory in reasoning engine
        self.reasoning_engine.set_trajectory(self.trajectory)

    async def execute_task(
        self,
        user_id: str,
        message: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """执行用户任务

        Args:
            user_id: 用户 ID
            message: 用户消息

        Yields:
            执行步骤的结果
        """
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        logger.info(f"Executing task for user {user_id}: {message}")

        # Step 1: 获取或创建沙盒
        yield {"type": "status", "message": "获取沙盒环境..."}
        sandbox = await self.sandbox_client.get_or_create(user_id)
        logger.info(f"Sandbox ready: {sandbox['id']}")

        # Step 2: 获取截图
        yield {"type": "status", "message": "获取屏幕截图..."}
        screenshot = await self.sandbox_client.screenshot(user_id)

        # Step 3: 推理分析
        yield {"type": "status", "message": "分析用户意图..."}
        reasoning = await self.reasoning_engine.analyze(
            message=message,
            screenshot=screenshot
        )
        yield {
            "type": "reasoning",
            "content": reasoning["content"],
            "reasoning": reasoning["reasoning"]
        }

        # Step 4: 技能选择
        yield {"type": "status", "message": "选择相关技能..."}
        skills = await self.skill_selector.select(
            message=message,
            context={"has_screenshot": bool(screenshot)},
            top_k=3
        )
        yield {
            "type": "skills",
            "skills": skills
        }

        # Step 5: 执行工具调用
        for skill in skills[:1]:  # 暂时只执行第一个技能
            tool_name = skill["name"]

            # Extract params once and reuse
            params = self._extract_params(message, tool_name)

            yield {
                "type": "tool_call",
                "tool": tool_name,
                "params": params
            }

            try:
                result = await self.sandbox_client.execute_tool(
                    user_id=user_id,
                    tool=tool_name,
                    params=params
                )

                # Convert result to dict if needed
                result_dict = result.dict() if hasattr(result, 'dict') else result

                # 记录到轨迹
                self.trajectory.add_step(
                    action=tool_name,
                    params=params,
                    result=result_dict
                )

                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "status": result_dict.get("status"),
                    "result": result_dict.get("result")
                }

            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                yield {
                    "type": "error",
                    "tool": tool_name,
                    "error": str(e)
                }

        yield {"type": "complete", "message": "任务执行完成"}

    def _extract_params(self, message: str, tool_name: str) -> Dict[str, Any]:
        """从消息中提取工具参数

        简单实现：根据工具类型提取参数
        实际应该使用 LLM 提取
        """
        params = {}

        if tool_name == "browser_navigate":
            # 提取 URL
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, message)
            if urls:
                params["url"] = urls[0]

        elif tool_name == "click_element":
            # 简单实现：返回默认坐标
            params["x"] = 100
            params["y"] = 100

        elif tool_name == "type_text":
            # 提取引号中的文本
            text_pattern = r'["\']([^"\']+)["\']'
            texts = re.findall(text_pattern, message)
            if texts:
                params["text"] = texts[0]

        return params

    async def click_with_vision(
        self,
        user_id: str,
        instruction: str,
        screenshot: str
    ) -> Dict[str, Any]:
        """使用视觉分析进行点击（视觉优先，工具降级）

        Note: This is a utility method for vision-based clicking.
        Currently not integrated into execute_task() workflow.
        Can be used by external callers for explicit vision-based operations.

        Args:
            user_id: 用户 ID
            instruction: 点击指令（如"点击登录按钮"）
            screenshot: 截图 base64

        Returns:
            执行结果
        """
        # 尝试视觉分析
        if self.vision and screenshot:
            try:
                coords = await self.vision.analyze_screenshot(screenshot, instruction)

                if coords:
                    logger.info(f"Vision analysis found coordinates: {coords}")
                    return await self.sandbox_client.execute_tool(
                        user_id=user_id,
                        tool="click",
                        params={"x": coords[0], "y": coords[1]}
                    )
                else:
                    logger.warning("Vision analysis failed to find coordinates, falling back to tools")

            except Exception as e:
                logger.error(f"Vision analysis error: {e}, falling back to tools")

        # 降级到工具
        logger.info("Using fallback tool-based click")
        return await self.sandbox_client.execute_tool(
            user_id=user_id,
            tool="click_element",
            params={"selector": instruction}
        )

    def get_trajectory(self) -> Trajectory:
        """获取执行轨迹"""
        return self.trajectory

    def clear_trajectory(self):
        """清空轨迹"""
        self.trajectory.clear()
