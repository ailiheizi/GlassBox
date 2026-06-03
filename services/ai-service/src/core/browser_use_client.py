"""
BrowserUseClient - 通过 CDP 连接沙箱 Chromium，使用 browser-use 执行浏览器任务
"""

import asyncio
import os
import logging
from typing import Dict, Optional

from browser_use import Agent, BrowserSession, BrowserProfile
from browser_use.llm.deepseek.chat import ChatDeepSeek

logger = logging.getLogger(__name__)

# 按 user_id 缓存实例，复用 BrowserSession 避免杀掉 Chromium
_instances: Dict[str, "BrowserUseClient"] = {}
_instances_lock = asyncio.Lock()

# 速度优化提示：鼓励 LLM 直接行动、合并多步操作
_SPEED_PROMPT = """
Speed optimization instructions:
- Be extremely concise and direct.
- Combine multiple actions in one step whenever possible (e.g. type + click submit).
- If a URL is given in the task, navigate to it directly as the first action.
- Do not explain or narrate — just act.
- When the task is complete, call done() immediately.
"""


class BrowserUseClient:
    """通过 CDP 远程连接沙箱 Chromium，使用 browser-use 执行浏览器任务"""

    @classmethod
    async def get_instance(cls, user_id: str) -> "BrowserUseClient":
        """获取或创建指定用户的 BrowserUseClient 实例（线程安全）"""
        async with _instances_lock:
            if user_id not in _instances:
                _instances[user_id] = cls()
            return _instances[user_id]

    def __init__(self):
        self._cdp_url: Optional[str] = None
        self._browser_session: Optional[BrowserSession] = None

    async def connect(self, cdp_url: str):
        """记录 CDP URL，如果 URL 变了则重置 session"""
        if self._cdp_url != cdp_url:
            if self._browser_session is not None:
                try:
                    await self._browser_session.stop()
                except Exception:
                    pass
                self._browser_session = None
            self._cdp_url = cdp_url
            logger.info(f"BrowserUseClient configured with CDP URL: {cdp_url}")

    async def run_task(self, task: str, max_steps: int = 10) -> dict:
        """执行浏览器任务，返回结果"""
        if not self._cdp_url:
            return {"success": False, "error": "Not connected to browser"}

        # 使用 browser-use 原生的 ChatDeepSeek（正确处理 function calling，不会触发 response_format 错误）
        base_url = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        llm = ChatDeepSeek(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            base_url=base_url,
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        )

        # 复用 BrowserSession，keep_alive=True 防止 Agent 结束后杀掉 Chromium
        if self._browser_session is None:
            self._browser_session = BrowserSession(
                cdp_url=self._cdp_url,
                keep_alive=True,
                browser_profile=BrowserProfile(
                    minimum_wait_page_load_time=0.5,
                    wait_between_actions=0.3,
                ),
            )

        agent = Agent(
            task=task,
            llm=llm,
            browser_session=self._browser_session,
            use_vision=False,
            flash_mode=True,
            max_actions_per_step=5,
            extend_system_message=_SPEED_PROMPT,
        )

        try:
            history = await agent.run(max_steps=max_steps)
            return {
                "success": not history.has_errors(),
                "result": history.final_result(),
                "steps": history.number_of_steps(),
                "is_done": history.is_done(),
            }
        except Exception as e:
            logger.error(f"browser-use task failed: {e}")
            # 连接断开时重置 session，下次会重新创建
            self._browser_session = None
            return {"success": False, "error": str(e)}

    async def disconnect(self):
        """断开连接"""
        if self._browser_session is not None:
            try:
                await self._browser_session.stop()
            except Exception:
                pass
            self._browser_session = None
        self._cdp_url = None
