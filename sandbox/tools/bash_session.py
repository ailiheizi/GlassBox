"""
BashSession 持久化管理器
借鉴 OpenHands 使用 tmux 管理持久化 shell 会话
支持 cd、环境变量等状态保持
"""

import asyncio
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional
import subprocess
import time


@dataclass
class BashSession:
    """单个 Bash 会话"""
    session_id: str
    user_id: str
    tmux_session: str
    cwd: str = "/home/sandbox/workspace"
    env: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


class BashSessionManager:
    """
    Bash 会话管理器
    使用 tmux 实现持久化 shell 会话
    """

    def __init__(self):
        self.sessions: Dict[str, BashSession] = {}
        self.default_shell = "/bin/bash"
        self.tmux_cmd = "tmux"

    def _get_tmux_session_name(self, user_id: str) -> str:
        """生成 tmux 会话名称"""
        # 清理 user_id 中的特殊字符
        clean_id = re.sub(r'[^a-zA-Z0-9_-]', '_', user_id)[:32]
        return f"bash_{clean_id}"

    async def get_or_create(self, user_id: str) -> BashSession:
        """获取或创建用户的 Bash 会话"""
        if user_id in self.sessions:
            session = self.sessions[user_id]
            session.last_active = time.time()
            return session

        # 创建新会话
        session_id = str(uuid.uuid4())[:8]
        tmux_session = self._get_tmux_session_name(user_id)

        # 检查 tmux 会话是否已存在
        check_cmd = f"{self.tmux_cmd} has-session -t {tmux_session} 2>/dev/null"
        result = subprocess.run(check_cmd, shell=True)

        if result.returncode != 0:
            # 创建新的 tmux 会话
            create_cmd = f"{self.tmux_cmd} new-session -d -s {tmux_session} -c /home/sandbox/workspace"
            subprocess.run(create_cmd, shell=True, check=True)

            # 设置初始环境
            init_cmds = [
                "export TERM=xterm-256color",
                "export LANG=zh_CN.UTF-8",
                f"export DISPLAY={os.environ.get('DISPLAY', ':1')}",
            ]
            for cmd in init_cmds:
                await self._send_keys(tmux_session, cmd)

        session = BashSession(
            session_id=session_id,
            user_id=user_id,
            tmux_session=tmux_session,
        )
        self.sessions[user_id] = session
        return session

    async def _send_keys(self, tmux_session: str, command: str, wait: bool = True) -> None:
        """向 tmux 会话发送按键"""
        # 转义特殊字符
        escaped_cmd = command.replace("'", "'\\''")
        send_cmd = f"{self.tmux_cmd} send-keys -t {tmux_session} '{escaped_cmd}' Enter"
        subprocess.run(send_cmd, shell=True)

        if wait:
            await asyncio.sleep(0.1)

    async def _capture_pane(self, tmux_session: str, lines: int = 500) -> str:
        """捕获 tmux 窗格内容"""
        capture_cmd = f"{self.tmux_cmd} capture-pane -t {tmux_session} -p -S -{lines}"
        result = subprocess.run(capture_cmd, shell=True, capture_output=True, text=True)
        return result.stdout

    async def execute(
        self,
        user_id: str,
        command: str,
        timeout: int = 30,
        wait_for_completion: bool = True
    ) -> Dict:
        """
        在用户的持久化会话中执行命令

        Args:
            user_id: 用户 ID
            command: 要执行的命令
            timeout: 超时时间（秒）
            wait_for_completion: 是否等待命令完成

        Returns:
            包含 output, exit_code, cwd 的字典
        """
        session = await self.get_or_create(user_id)
        session.last_active = time.time()

        # 生成唯一标记用于识别命令输出
        marker_start = f"__CMD_START_{uuid.uuid4().hex[:8]}__"
        marker_end = f"__CMD_END_{uuid.uuid4().hex[:8]}__"

        # 构建带标记的命令
        # 使用 ; 确保即使命令失败也能输出结束标记
        wrapped_command = f"echo '{marker_start}'; {command}; __exit_code__=$?; echo '{marker_end}'; echo \"EXIT_CODE:$__exit_code__\"; pwd"

        # 发送命令
        await self._send_keys(session.tmux_session, wrapped_command)

        if not wait_for_completion:
            return {
                "status": "running",
                "message": "Command sent to background",
                "session_id": session.session_id
            }

        # 等待命令完成
        start_time = time.time()
        output = ""
        exit_code = None
        cwd = session.cwd

        while time.time() - start_time < timeout:
            await asyncio.sleep(0.2)

            # 捕获输出
            pane_content = await self._capture_pane(session.tmux_session)

            # 查找标记
            if marker_start in pane_content and marker_end in pane_content:
                # 提取命令输出
                start_idx = pane_content.rfind(marker_start) + len(marker_start)
                end_idx = pane_content.rfind(marker_end)

                if start_idx < end_idx:
                    output = pane_content[start_idx:end_idx].strip()

                    # 提取退出码
                    exit_match = re.search(r'EXIT_CODE:(\d+)', pane_content[end_idx:])
                    if exit_match:
                        exit_code = int(exit_match.group(1))

                    # 提取当前工作目录（pwd 输出在最后）
                    lines_after_marker = pane_content[end_idx:].strip().split('\n')
                    for line in reversed(lines_after_marker):
                        line = line.strip()
                        if line.startswith('/') and 'EXIT_CODE' not in line and marker_end not in line:
                            cwd = line
                            session.cwd = cwd
                            break

                    break
        else:
            # 超时
            return {
                "status": "timeout",
                "output": output or "Command timed out",
                "exit_code": -1,
                "cwd": session.cwd,
                "timeout": timeout
            }

        return {
            "status": "completed",
            "output": output,
            "exit_code": exit_code if exit_code is not None else 0,
            "cwd": cwd,
            "session_id": session.session_id
        }

    async def get_cwd(self, user_id: str) -> str:
        """获取用户会话的当前工作目录"""
        if user_id not in self.sessions:
            return "/home/sandbox/workspace"

        session = self.sessions[user_id]

        # 执行 pwd 获取最新目录
        result = await self.execute(user_id, "pwd", timeout=5)
        if result.get("status") == "completed":
            output = result.get("output", "").strip()
            if output.startswith('/'):
                session.cwd = output

        return session.cwd

    async def set_env(self, user_id: str, key: str, value: str) -> Dict:
        """设置环境变量"""
        session = await self.get_or_create(user_id)

        # 转义值中的特殊字符
        escaped_value = value.replace('"', '\\"')
        command = f'export {key}="{escaped_value}"'

        result = await self.execute(user_id, command, timeout=5)

        if result.get("status") == "completed":
            session.env[key] = value

        return result

    async def get_env(self, user_id: str, key: str) -> Optional[str]:
        """获取环境变量"""
        result = await self.execute(user_id, f"echo ${key}", timeout=5)

        if result.get("status") == "completed":
            return result.get("output", "").strip()

        return None

    async def destroy_session(self, user_id: str) -> bool:
        """销毁用户会话"""
        if user_id not in self.sessions:
            return False

        session = self.sessions[user_id]

        # 杀死 tmux 会话
        kill_cmd = f"{self.tmux_cmd} kill-session -t {session.tmux_session} 2>/dev/null"
        subprocess.run(kill_cmd, shell=True)

        del self.sessions[user_id]
        return True

    async def list_sessions(self) -> list:
        """列出所有活跃会话"""
        return [
            {
                "user_id": s.user_id,
                "session_id": s.session_id,
                "cwd": s.cwd,
                "created_at": s.created_at,
                "last_active": s.last_active,
            }
            for s in self.sessions.values()
        ]

    async def cleanup_idle_sessions(self, max_idle_seconds: int = 3600) -> int:
        """清理空闲会话"""
        now = time.time()
        to_remove = []

        for user_id, session in self.sessions.items():
            if now - session.last_active > max_idle_seconds:
                to_remove.append(user_id)

        for user_id in to_remove:
            await self.destroy_session(user_id)

        return len(to_remove)


# 全局单例
_bash_session_manager: Optional[BashSessionManager] = None


def get_bash_session_manager() -> BashSessionManager:
    """获取 BashSessionManager 单例"""
    global _bash_session_manager
    if _bash_session_manager is None:
        _bash_session_manager = BashSessionManager()
    return _bash_session_manager
