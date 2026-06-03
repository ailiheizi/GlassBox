from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class Trajectory:
    """推理轨迹跟踪"""

    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.created_at = datetime.now()

    def add_step(
        self,
        action: str,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None
    ):
        """添加推理步骤

        Args:
            action: 执行的动作
            params: 动作参数
            result: 执行结果
            reasoning: 推理过程
        """
        step = {
            "step_id": len(self.steps) + 1,
            "action": action,
            "params": params,
            "result": result,
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat()
        }
        self.steps.append(step)

    def get_context(self, last_n: int = 5) -> str:
        """获取最近 N 步的上下文

        Args:
            last_n: 返回最近 N 步

        Returns:
            格式化的上下文字符串
        """
        recent_steps = self.steps[-last_n:] if len(self.steps) > last_n else self.steps

        context_lines = []
        for step in recent_steps:
            line = f"Step {step['step_id']}: {step['action']}({json.dumps(step['params'])})"
            if step.get('result'):
                line += f" -> {step['result'].get('status', 'unknown')}"
            context_lines.append(line)

        return "\n".join(context_lines)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "steps": self.steps,
            "created_at": self.created_at.isoformat(),
            "total_steps": len(self.steps)
        }

    def clear(self):
        """清空轨迹"""
        self.steps = []
