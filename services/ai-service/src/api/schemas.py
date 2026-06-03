from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class FunctionDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class Tool(BaseModel):
    type: str = "function"
    function: FunctionDefinition


class ChatRequest(BaseModel):
    messages: List[Message]
    tools: Optional[List[Tool]] = None
    tool_choice: str = "auto"
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False


class ChatResponse(BaseModel):
    content: str = ""
    role: str = "assistant"
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class EmbeddingRequest(BaseModel):
    text: str
    model: Optional[str] = None


class BatchEmbeddingRequest(BaseModel):
    texts: List[str]
    model: Optional[str] = None


class EmbeddingResponse(BaseModel):
    embedding: List[float]
    dimensions: int
    model: str


class BatchEmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
