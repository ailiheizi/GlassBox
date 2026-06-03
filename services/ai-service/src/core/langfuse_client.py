"""
Langfuse 可观测性集成模块。
提供初始化、状态查询、trace URL 构建。
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_langfuse_enabled = False
_langfuse_external_host = ""


def is_langfuse_enabled() -> bool:
    return _langfuse_enabled


def get_langfuse_external_host() -> str:
    return _langfuse_external_host


def init_langfuse():
    """初始化 Langfuse SDK，在 app startup 时调用一次。"""
    global _langfuse_enabled, _langfuse_external_host
    from ..config.settings import settings

    if not settings.langfuse_enabled or not settings.langfuse_public_key:
        logger.info("[Langfuse] Disabled or not configured")
        return

    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_host

    _langfuse_enabled = True
    _langfuse_external_host = settings.langfuse_external_host

    # 注册 OpenAI 自动追踪（v3 通过 OpenTelemetry instrumentor）
    try:
        from langfuse.openai import register_tracing
        register_tracing()
        logger.info("[Langfuse] OpenAI auto-tracing registered")
    except Exception as e:
        logger.warning(f"[Langfuse] OpenAI register_tracing failed: {e}")

    # 重新初始化已有的 MultiModelLLM 客户端，使用 Langfuse 包装的 AsyncOpenAI
    try:
        from ..api.smart_sandbox_routes import multi_model_llm
        multi_model_llm.reinit_clients()
        logger.info("[Langfuse] MultiModelLLM clients reinitialized with tracing")
    except Exception as e:
        logger.debug(f"[Langfuse] MultiModelLLM reinit skipped: {e}")

    logger.info(f"[Langfuse] Initialized, host={settings.langfuse_host}")


def get_trace_url(trace_id: str) -> Optional[str]:
    """构建 Langfuse Dashboard 的 trace 链接。"""
    if not _langfuse_enabled or not trace_id:
        return None
    return f"{_langfuse_external_host}/trace/{trace_id}"


def flush():
    """Flush Langfuse 缓冲区，在 app shutdown 时调用。"""
    if not _langfuse_enabled:
        return
    try:
        from langfuse import get_client
        client = get_client()
        client.flush()
        client.shutdown()
    except Exception as e:
        logger.warning(f"[Langfuse] Flush failed: {e}")
