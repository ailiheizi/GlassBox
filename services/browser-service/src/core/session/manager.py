"""
会话管理器 - 管理浏览器会话的生命周期
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class Session:
    """会话数据"""
    id: str
    user_id: str
    status: str = "active"  # active, closed
    created_at: datetime = field(default_factory=datetime.now)
    last_activity_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "metadata": self.metadata,
        }

    def update_activity(self):
        self.last_activity_at = datetime.now()


class SessionManager:
    """
    会话管理器

    注意：这是内存存储实现，重启后会话丢失。
    生产环境应使用 Redis 或数据库存储。
    """

    _instance: Optional["SessionManager"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]
        self._session_timeout = timedelta(hours=24)

    @classmethod
    async def get_instance(cls) -> "SessionManager":
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def create_session(self, user_id: str, metadata: Optional[Dict] = None) -> Session:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            user_id=user_id,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session

        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session_id)

        return session

    async def get_session(self, session_id: str, user_id: str) -> Optional[Session]:
        """
        获取会话

        安全设计：必须验证 user_id 匹配
        """
        session = self._sessions.get(session_id)
        if session and session.user_id == user_id:
            return session
        return None

    async def list_sessions(self, user_id: str) -> List[Session]:
        """列出用户的所有会话"""
        session_ids = self._user_sessions.get(user_id, [])
        sessions = []
        for sid in session_ids:
            session = self._sessions.get(sid)
            if session and session.status == "active":
                sessions.append(session)
        return sessions

    async def close_session(self, session_id: str, user_id: str) -> bool:
        """
        关闭会话

        安全设计：必须验证 user_id 匹配
        """
        session = await self.get_session(session_id, user_id)
        if session:
            session.status = "closed"
            return True
        return False

    async def update_activity(self, session_id: str, user_id: str) -> bool:
        """更新会话活动时间"""
        session = await self.get_session(session_id, user_id)
        if session:
            session.update_activity()
            return True
        return False

    async def cleanup_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired_ids = []

        for session_id, session in self._sessions.items():
            if now - session.last_activity_at > self._session_timeout:
                expired_ids.append(session_id)

        for session_id in expired_ids:
            session = self._sessions.pop(session_id, None)
            if session:
                user_sessions = self._user_sessions.get(session.user_id, [])
                if session_id in user_sessions:
                    user_sessions.remove(session_id)
