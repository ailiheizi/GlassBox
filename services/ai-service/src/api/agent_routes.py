import json
import logging
import os
from typing import AsyncGenerator
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.multi_model_llm import MultiModelLLM
from ..core.agent.sandbox_agent import SandboxAgent
from ..core.vision.doubao_vision import DoubaoVision
from ..config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

# 初始化多模型 LLM 客户端
multi_llm = MultiModelLLM()


class ChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str


async def event_stream(user_id: str, message: str) -> AsyncGenerator[str, None]:
    """SSE 事件流生成器

    Args:
        user_id: 用户 ID
        message: 用户消息

    Yields:
        SSE 格式的事件数据
    """
    try:
        # 创建视觉分析（如果启用）
        vision = None
        doubao_api_key = os.getenv("DOUBAO_API_KEY")
        if not doubao_api_key:
            logger.error("DOUBAO_API_KEY not configured, vision analysis disabled")
            vision = None
        elif os.getenv("DOUBAO_VISION_ENABLED", "true").lower() == "true":
            vision = DoubaoVision(
                api_key=doubao_api_key,
                api_base=os.getenv("DOUBAO_API_BASE")
            )
        else:
            vision = None

        # 创建 Agent（使用多模型 LLM）
        agent = SandboxAgent(
            llm=multi_llm,
            worker_manager_url=settings.worker_manager_url,
            vision=vision
        )

        # 执行任务并流式返回结果
        async for event in agent.execute_task(user_id=user_id, message=message):
            # 将事件转换为 SSE 格式
            event_data = json.dumps(event, ensure_ascii=False)
            yield f"data: {event_data}\n\n"

    except Exception as e:
        logger.error(f"Agent execution error: {e}", exc_info=True)
        error_event = {
            "type": "error",
            "error": str(e)
        }
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def agent_chat(
    request: ChatRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
) -> StreamingResponse:
    """Agent 聊天接口（SSE 流式）

    Args:
        request: 聊天请求
        x_user_id: 用户 ID（从请求头获取）

    Returns:
        SSE 流式响应
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    logger.info(f"Agent chat request from user {x_user_id}: {request.message}")

    return StreamingResponse(
        event_stream(user_id=x_user_id, message=request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )
