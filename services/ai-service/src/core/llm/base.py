from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator


class BaseLLM(ABC):
    """LLM基类"""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """聊天接口"""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式聊天接口"""
        pass


class BaseEmbedding(ABC):
    """Embedding基类"""

    @abstractmethod
    async def generate(self, text: str) -> List[float]:
        """生成单个文本的Embedding"""
        pass

    @abstractmethod
    async def batch_generate(self, texts: List[str]) -> List[List[float]]:
        """批量生成Embedding"""
        pass
