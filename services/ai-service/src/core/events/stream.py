"""
EventStream 事件流实现
提供事件发布、订阅和流式传输功能
"""

import asyncio
import json
from typing import AsyncIterator, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from .types import Event, EventType


@dataclass
class Subscription:
    """事件订阅"""
    id: str
    event_types: Set[EventType]
    callback: Optional[Callable[[Event], None]] = None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())


class EventStream:
    """
    事件流管理器
    支持发布/订阅模式和异步流式传输
    """

    def __init__(self, max_history: int = 1000):
        self.subscriptions: Dict[str, Subscription] = {}
        self.history: List[Event] = []
        self.max_history = max_history
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        """
        发布事件到所有匹配的订阅者

        Args:
            event: 要发布的事件
        """
        async with self._lock:
            # 添加到历史记录
            self.history.append(event)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

        # 分发到订阅者
        for sub in self.subscriptions.values():
            if event.type in sub.event_types or not sub.event_types:
                # 放入队列
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    # 队列满了，丢弃旧事件
                    try:
                        sub.queue.get_nowait()
                        sub.queue.put_nowait(event)
                    except:
                        pass

                # 调用回调
                if sub.callback:
                    try:
                        sub.callback(event)
                    except Exception as e:
                        print(f"Event callback error: {e}")

    def subscribe(
        self,
        event_types: Optional[List[EventType]] = None,
        callback: Optional[Callable[[Event], None]] = None
    ) -> str:
        """
        订阅事件

        Args:
            event_types: 要订阅的事件类型列表，None 表示订阅所有
            callback: 事件回调函数

        Returns:
            订阅 ID
        """
        sub_id = str(uuid.uuid4())
        self.subscriptions[sub_id] = Subscription(
            id=sub_id,
            event_types=set(event_types) if event_types else set(),
            callback=callback,
            queue=asyncio.Queue(maxsize=100)
        )
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅

        Args:
            subscription_id: 订阅 ID

        Returns:
            是否成功取消
        """
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            return True
        return False

    async def stream(
        self,
        subscription_id: str,
        timeout: float = 30.0
    ) -> AsyncIterator[Event]:
        """
        流式获取事件

        Args:
            subscription_id: 订阅 ID
            timeout: 超时时间（秒）

        Yields:
            事件对象
        """
        if subscription_id not in self.subscriptions:
            return

        sub = self.subscriptions[subscription_id]

        while True:
            try:
                event = await asyncio.wait_for(
                    sub.queue.get(),
                    timeout=timeout
                )
                yield event
            except asyncio.TimeoutError:
                # 超时，发送心跳
                yield Event(
                    type=EventType.SYSTEM_INFO,
                    data={"heartbeat": True}
                )
            except Exception:
                break

    async def stream_sse(
        self,
        subscription_id: str,
        timeout: float = 30.0
    ) -> AsyncIterator[str]:
        """
        流式获取 SSE 格式的事件

        Args:
            subscription_id: 订阅 ID
            timeout: 超时时间（秒）

        Yields:
            SSE 格式的字符串
        """
        async for event in self.stream(subscription_id, timeout):
            yield event.to_sse()

    def get_history(
        self,
        event_types: Optional[List[EventType]] = None,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Event]:
        """
        获取历史事件

        Args:
            event_types: 过滤的事件类型
            limit: 返回数量限制
            since: 起始时间

        Returns:
            事件列表
        """
        events = self.history

        if event_types:
            events = [e for e in events if e.type in event_types]

        if since:
            events = [e for e in events if e.timestamp >= since]

        return events[-limit:]

    async def wait_for(
        self,
        event_type: EventType,
        timeout: float = 30.0,
        predicate: Optional[Callable[[Event], bool]] = None
    ) -> Optional[Event]:
        """
        等待特定事件

        Args:
            event_type: 要等待的事件类型
            timeout: 超时时间
            predicate: 额外的过滤条件

        Returns:
            匹配的事件，超时返回 None
        """
        sub_id = self.subscribe([event_type])

        try:
            async for event in self.stream(sub_id, timeout):
                if event.type == event_type:
                    if predicate is None or predicate(event):
                        return event
        finally:
            self.unsubscribe(sub_id)

        return None


class SessionEventStream:
    """
    会话级别的事件流
    每个用户会话有独立的事件流
    """

    def __init__(self):
        self.streams: Dict[str, EventStream] = {}

    def get_stream(self, session_id: str) -> EventStream:
        """获取或创建会话的事件流"""
        if session_id not in self.streams:
            self.streams[session_id] = EventStream()
        return self.streams[session_id]

    def remove_stream(self, session_id: str) -> bool:
        """移除会话的事件流"""
        if session_id in self.streams:
            del self.streams[session_id]
            return True
        return False

    async def publish_to_session(self, session_id: str, event: Event) -> None:
        """发布事件到指定会话"""
        event.session_id = session_id
        stream = self.get_stream(session_id)
        await stream.publish(event)

    async def broadcast(self, event: Event) -> None:
        """广播事件到所有会话"""
        for stream in self.streams.values():
            await stream.publish(event)


# 全局事件流实例
_global_event_stream: Optional[EventStream] = None
_session_event_stream: Optional[SessionEventStream] = None


def get_event_stream() -> EventStream:
    """获取全局事件流单例"""
    global _global_event_stream
    if _global_event_stream is None:
        _global_event_stream = EventStream()
    return _global_event_stream


def get_session_event_stream() -> SessionEventStream:
    """获取会话事件流管理器单例"""
    global _session_event_stream
    if _session_event_stream is None:
        _session_event_stream = SessionEventStream()
    return _session_event_stream
