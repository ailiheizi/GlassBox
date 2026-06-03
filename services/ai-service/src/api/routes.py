import json
from typing import AsyncIterator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .schemas import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
)
from ..core.multi_model_llm import MultiModelLLM
from ..core.llm import DoubaoEmbedding
from ..config.settings import settings

router = APIRouter()

# 初始化客户端
llm_client = MultiModelLLM()
embedding_client = DoubaoEmbedding()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口 (非流式)"""
    try:
        messages = [msg.model_dump(exclude_none=True) for msg in request.messages]
        tools = [tool.model_dump() for tool in request.tools] if request.tools else None

        # 使用默认聊天模型
        model = llm_client.get_default_chat_model() or "deepseek-chat"

        result = await llm_client.chat(
            messages=messages,
            model=model,
            tools=tools,
            tool_choice=request.tool_choice,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """聊天接口 (流式SSE)"""

    async def generate() -> AsyncIterator[str]:
        try:
            messages = [msg.model_dump(exclude_none=True) for msg in request.messages]
            tools = [tool.model_dump() for tool in request.tools] if request.tools else None

            # 使用默认聊天模型
            model = llm_client.get_default_chat_model() or "deepseek-chat"

            async for chunk in llm_client.stream_chat(
                messages=messages,
                model=model,
                tools=tools,
                tool_choice=request.tool_choice,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/embedding", response_model=EmbeddingResponse)
async def generate_embedding(request: EmbeddingRequest):
    """生成单个文本的Embedding"""
    try:
        embedding = await embedding_client.generate(request.text)
        return EmbeddingResponse(
            embedding=embedding,
            dimensions=len(embedding),
            model=settings.doubao_embedding_model,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embedding/batch", response_model=BatchEmbeddingResponse)
async def batch_generate_embedding(request: BatchEmbeddingRequest):
    """批量生成Embedding"""
    try:
        embeddings = await embedding_client.batch_generate(request.texts)
        return BatchEmbeddingResponse(
            embeddings=embeddings,
            model=settings.doubao_embedding_model,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """列出可用模型"""
    providers = llm_client.get_available_providers()

    chat_models = []
    if providers.get("doubao"):
        chat_models.append({"id": "doubao-seed-1-8-251228", "provider": "doubao", "type": "vision"})
    if providers.get("deepseek"):
        chat_models.append({"id": "deepseek-chat", "provider": "deepseek", "type": "chat"})
    if providers.get("siliconflow"):
        chat_models.append({"id": "deepseek-ai/deepseek-vl2", "provider": "siliconflow", "type": "vision"})

    return {
        "chat_models": chat_models,
        "embedding_models": [
            {
                "id": settings.doubao_embedding_model,
                "provider": "doubao",
                "dimensions": settings.doubao_embedding_dimensions,
            },
        ],
        "providers": providers,
    }
