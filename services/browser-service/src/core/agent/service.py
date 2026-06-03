"""
Agent服务 - 浏览器自动化执行引擎
"""
import json
from typing import Dict, Any, Optional, AsyncIterator, List

from ..browser.client import BrowserClient
from ..tools.handler import ToolHandler
from ..tools.definitions import get_all_tools
from ...clients.ai_client import AIClient
from ...clients.memory_client import MemoryClient
from ...clients.index_client import IndexClient
from ...config.settings import settings


class AgentService:
    """
    Agent服务

    安全设计：
    - user_id在初始化时绑定，不可修改
    - 所有工具调用都使用绑定的user_id
    """

    def __init__(self, user_id: str, session_id: Optional[str] = None):
        # user_id在初始化时绑定
        self._user_id = user_id
        self._session_id = session_id

        self._browser: Optional[BrowserClient] = None
        self._tool_handler: Optional[ToolHandler] = None
        self._ai_client: Optional[AIClient] = None
        self._memory_client: Optional[MemoryClient] = None
        self._index_client: Optional[IndexClient] = None

        self._conversation_history: List[Dict[str, Any]] = []
        self._max_iterations = settings.max_iterations

    @property
    def user_id(self) -> str:
        """只读属性"""
        return self._user_id

    async def initialize(self) -> None:
        """初始化Agent"""
        # 初始化浏览器
        self._browser = BrowserClient()
        await self._browser.initialize()

        # 初始化客户端
        self._ai_client = AIClient()
        self._memory_client = MemoryClient()
        self._index_client = IndexClient()

        # 初始化工具处理器，绑定user_id
        self._tool_handler = ToolHandler(
            user_id=self._user_id,
            browser_client=self._browser,
            memory_client=self._memory_client,
            index_client=self._index_client,
        )

        # 初始化对话历史
        self._conversation_history = [
            {"role": "system", "content": self._get_system_prompt()}
        ]

    async def close(self) -> None:
        """关闭Agent"""
        if self._browser:
            await self._browser.close()

    async def execute_task_stream(self, task: str) -> AsyncIterator[Dict[str, Any]]:
        """
        流式执行任务

        安全设计：
        - 所有工具调用都使用绑定的user_id
        - 工具定义中不暴露user_id参数
        """
        yield {"event": "start", "task": task}

        # 添加用户任务
        self._conversation_history.append({
            "role": "user",
            "content": task
        })

        iteration = 0
        while iteration < self._max_iterations:
            iteration += 1
            yield {"event": "iteration", "current": iteration, "max": self._max_iterations}

            # 调用AI
            try:
                response = await self._ai_client.chat(
                    messages=self._conversation_history,
                    tools=get_all_tools(),
                    tool_choice="auto",
                )
            except Exception as e:
                yield {"event": "error", "error": f"AI call failed: {str(e)}"}
                break

            message = response.get("message", {})
            finish_reason = response.get("finish_reason")

            # 添加助手消息到历史
            self._conversation_history.append(message)

            # 检查是否有工具调用
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # 没有工具调用，任务完成
                yield {
                    "event": "assistant_message",
                    "content": message.get("content", ""),
                }
                yield {"event": "task_complete"}
                break

            # 执行工具调用
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                yield {
                    "event": "tool_call",
                    "tool": tool_name,
                    "arguments": arguments,
                }

                # 执行工具 (使用绑定的user_id)
                try:
                    result = await self._tool_handler.execute(tool_name, arguments)
                    yield {
                        "event": "tool_result",
                        "tool": tool_name,
                        "result": result,
                    }

                    # 添加工具结果到历史
                    self._conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                except Exception as e:
                    error_result = {"error": str(e)}
                    yield {
                        "event": "tool_error",
                        "tool": tool_name,
                        "error": str(e),
                    }

                    self._conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": json.dumps(error_result),
                    })

            # 管理历史长度
            self._manage_history()

        else:
            yield {"event": "task_timeout", "message": "Max iterations reached"}

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个浏览器自动化助手。你可以使用以下工具来完成用户的任务：

## 浏览器操作
- navigate: 导航到URL
- click: 点击元素
- type_text: 输入文本
- wait_for_selector: 等待元素
- get_page_info: 获取页面信息
- screenshot: 截图
- find_elements: 查找元素
- scroll: 滚动页面

## 记忆操作
- save_memory: 保存记忆
- search_memory: 搜索记忆

## 索引操作
- search_index: 搜索索引
- create_index: 创建索引

## 重要规则
1. 在执行操作前，先使用get_page_info了解当前页面
2. 如果点击失败，尝试使用不同的选择器
3. 保存重要信息到记忆中
4. 任务完成后，给出清晰的总结
"""

    def _manage_history(self) -> None:
        """管理对话历史长度"""
        # 保留系统提示 + 最近20条消息
        if len(self._conversation_history) > 21:
            self._conversation_history = (
                self._conversation_history[:1] +  # 系统提示
                self._conversation_history[-20:]  # 最近20条
            )
