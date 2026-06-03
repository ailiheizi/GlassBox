"""
操作模式路由器（精简版）
去掉 GUI vs Code 双模式路由，统一为 browser-use + bash + 文件操作
保留接口兼容性，但不再区分 GUI/Code 模式
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class OperationMode(str, Enum):
    """操作模式（保留枚举兼容性）"""
    GUI = "gui"
    CODE = "code"
    AUTO = "auto"


@dataclass
class ModeDecision:
    """模式决策结果"""
    mode: OperationMode
    confidence: float
    reason: str
    suggested_tools: List[str]


class ModeRouter:
    """
    操作模式路由器（精简版）
    统一返回 AUTO 模式，不再区分 GUI/Code
    """

    def select_mode(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ModeDecision:
        """统一返回 AUTO 模式"""
        return ModeDecision(
            mode=OperationMode.AUTO,
            confidence=0.9,
            reason="统一模式：browser-use + bash + 文件操作",
            suggested_tools=self._get_all_tools()
        )

    def _get_all_tools(self) -> List[str]:
        return [
            "sandbox_browser_use",
            "sandbox_shell",
            "sandbox_bash_execute",
            "sandbox_file_list",
            "sandbox_file_read",
            "sandbox_file_write",
            "sandbox_wait",
        ]

    def _get_gui_tools(self) -> List[str]:
        """保留接口兼容"""
        return self._get_all_tools()

    def _get_code_tools(self) -> List[str]:
        """保留接口兼容"""
        return self._get_all_tools()

    def get_mode_prompt(self, mode: OperationMode) -> str:
        """统一提示词"""
        return """你可以使用以下工具完成任务：

## 浏览器工具（推荐用于所有网页任务）
- sandbox_browser_use(task) - 通过 DOM 操作执行浏览器任务，准确率高

## 命令行工具
- sandbox_shell(command) - 执行命令
- sandbox_bash_execute(command) - 持久化会话执行（支持 cd、环境变量保持）

## 文件操作工具
- sandbox_file_list(path) - 列出目录内容
- sandbox_file_read(path) - 读取文件
- sandbox_file_write(path, content) - 写入文件

## 选择原则
1. 浏览器/网页任务优先使用 sandbox_browser_use
2. 能用命令完成的任务，优先用命令
3. 文件读写使用 sandbox_file_read/write，比 shell 的 cat/echo 更可靠"""


# 全局单例
_mode_router: Optional[ModeRouter] = None


def get_mode_router() -> ModeRouter:
    """获取 ModeRouter 单例"""
    global _mode_router
    if _mode_router is None:
        _mode_router = ModeRouter()
    return _mode_router
