"""
安全工具执行器 - AI只能调用白名单中的工具
"""
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class SecurityError(Exception):
    """安全错误"""
    pass


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


# 禁止的危险模式
BLOCKED_PATTERNS = [
    r"exec\s*\(",
    r"eval\s*\(",
    r"__import__",
    r"subprocess",
    r"os\.system",
    r"os\.popen",
    r"open\s*\(",
    r"requests\.",
    r"urllib",
    r"socket\.",
    r"pickle",
    r"marshal",
]


def check_dangerous_patterns(arguments: Dict[str, Any]) -> None:
    """检查参数中是否包含危险模式"""
    def check_value(value: Any) -> None:
        if isinstance(value, str):
            for pattern in BLOCKED_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    raise SecurityError(f"Dangerous pattern detected in argument")
        elif isinstance(value, dict):
            for v in value.values():
                check_value(v)
        elif isinstance(value, list):
            for item in value:
                check_value(item)

    for key, value in arguments.items():
        check_value(value)


class ToolResultValidator:
    """工具执行结果校验器"""

    def __init__(self, user_id: str):
        self._user_id = user_id

    def validate(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """校验工具执行结果"""
        # 递归检查嵌套数据中的user_id
        self._check_nested(result)
        # 过滤敏感字段
        return self._filter_result(result)

    def _check_nested(self, data: Any) -> None:
        """递归检查嵌套数据中的user_id"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "user_id" and value != self._user_id:
                    raise SecurityError("Result contains wrong user_id")
                self._check_nested(value)
        elif isinstance(data, list):
            for item in data:
                self._check_nested(item)

    def _filter_result(self, result: Any) -> Any:
        """过滤结果中的敏感信息"""
        sensitive_keys = {"internal_id", "db_connection", "secret", "password", "token"}

        if isinstance(result, dict):
            return {
                k: self._filter_result(v)
                for k, v in result.items()
                if k not in sensitive_keys
            }
        elif isinstance(result, list):
            return [self._filter_result(item) for item in result]
        return result
