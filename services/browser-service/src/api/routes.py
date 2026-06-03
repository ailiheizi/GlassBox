"""
API路由
"""
import json
import logging
from typing import AsyncIterator, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .security import SecureResponseBuilder
from ..core.agent.service import AgentService
from ..core.session.manager import SessionManager
from ..config.settings import settings

logger = logging.getLogger(__name__)


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    metadata: Optional[dict] = None

router = APIRouter()


def get_user_id(request: Request) -> str:
    """
    从Gateway设置的Header获取user_id

    安全设计：
    - 只从Header获取user_id
    - 禁止从Body/Query获取
    - Gateway已验证JWT，这里信任Header
    """
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


def get_request_id(request: Request) -> str:
    """获取请求ID"""
    return request.headers.get("X-Request-ID", "unknown")


@router.post("/chat")
async def chat(
    request: Request,
    user_id: str = Depends(get_user_id),
):
    """
    执行浏览器任务 (SSE流式响应)

    安全设计：
    - user_id从Header获取，不可被用户篡改
    - 每个事件都经过安全校验
    - 响应Header标记user_id供Gateway验证
    """
    request_id = get_request_id(request)

    # 解析请求体
    try:
        body = await request.json()
        task = body.get("task", "")
        session_id = body.get("session_id")
    except Exception as e:
        logger.warning(f"Failed to parse request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not task:
        raise HTTPException(status_code=400, detail="Task is required")

    # 创建安全响应构建器
    response_builder = SecureResponseBuilder(user_id, request_id)

    async def generate() -> AsyncIterator[str]:
        agent = None
        try:
            # 创建Agent，绑定user_id
            agent = AgentService(user_id=user_id, session_id=session_id)
            await agent.initialize()

            # 执行任务
            async for event in agent.execute_task_stream(task):
                # 每个事件都经过安全校验
                secure_event = response_builder.build_response(event)
                yield f"data: {json.dumps(secure_event, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            error_event = response_builder.build_response({
                "event": "error",
                "error": str(e)
            })
            yield f"data: {json.dumps(error_event)}\n\n"

        finally:
            if agent:
                await agent.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Response-User-ID": user_id,  # 标记响应的user_id
            "X-Request-ID": request_id,
        },
    )


@router.get("/sessions")
async def list_sessions(user_id: str = Depends(get_user_id)):
    """获取用户的会话列表"""
    manager = await SessionManager.get_instance()
    sessions = await manager.list_sessions(user_id)
    return {"sessions": [s.to_dict() for s in sessions]}


@router.post("/sessions")
async def create_session(
    request_body: CreateSessionRequest,
    user_id: str = Depends(get_user_id),
):
    """创建新会话"""
    manager = await SessionManager.get_instance()
    session = await manager.create_session(user_id, request_body.metadata)
    return {"session_id": session.id, "session": session.to_dict()}


@router.delete("/sessions/{session_id}")
async def close_session(
    session_id: str,
    user_id: str = Depends(get_user_id),
):
    """关闭会话"""
    manager = await SessionManager.get_instance()
    success = await manager.close_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
