import uvicorn
import os
import logging
import tomllib
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.sandbox_routes import router as sandbox_router
from .api.smart_sandbox_routes import router as smart_sandbox_router
from .api import agent_routes
from .config.settings import settings
from .core.jwt_utils import generate_service_token
from .core.skill import SkillSystemManager, SkillSystemConfig
from .core.llm.doubao import DoubaoEmbedding
from .core.multi_model_llm import MultiModelLLM

logger = logging.getLogger(__name__)


def _get_version() -> str:
    """Read version from pyproject.toml."""
    try:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "unknown"

app = FastAPI(
    title="AI Service",
    description="AI Service for NewArch - LLM, Embedding and Sandbox Agent",
    version="0.2.0",
)

# Generate service JWT token on startup
_service_jwt_token = None

@app.on_event("startup")
async def startup_event():
    """Application startup: JWT token + Skill system initialization"""
    global _service_jwt_token
    jwt_secret = os.getenv("JWT_SECRET", settings.jwt_secret)
    _service_jwt_token = generate_service_token(jwt_secret, "ai-service")
    logger.info("[AI Service] Generated JWT token for service-to-service authentication")

    # 初始化 Langfuse
    try:
        from .core.langfuse_client import init_langfuse
        init_langfuse()
    except Exception as e:
        logger.warning(f"[AI Service] Langfuse init failed (non-fatal): {e}")

    # Skill 系统初始化（非阻塞，失败不影响服务启动）
    try:
        config = SkillSystemConfig.from_settings(settings)
        embedding_service = DoubaoEmbedding()
        llm_client = MultiModelLLM().doubao_client
        manager = SkillSystemManager.get_instance()
        await manager.initialize(config, embedding_service, llm_client)
        logger.info("[AI Service] Skill system initialized successfully")
    except Exception as e:
        logger.warning(f"[AI Service] Skill system init failed (non-fatal): {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown: flush Langfuse buffer"""
    try:
        from .core.langfuse_client import flush
        flush()
    except Exception:
        pass

def get_service_token() -> str:
    """Get the service JWT token"""
    return _service_jwt_token or ""

# CORS - 从环境变量读取允许的来源
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-User-ID", "X-Request-ID"],
)


# 健康检查
@app.get("/health")
async def health():
    from .core.langfuse_client import is_langfuse_enabled
    providers = {}
    try:
        from .api.smart_sandbox_routes import multi_model_llm
        providers = multi_model_llm.get_available_providers()
    except Exception:
        pass
    return {
        "status": "ok",
        "version": _get_version(),
        "langfuse": is_langfuse_enabled(),
        "providers": providers,
    }


# 注册路由
app.include_router(router, prefix="")
app.include_router(sandbox_router, prefix="")
app.include_router(smart_sandbox_router, prefix="")  # 智能路由
app.include_router(agent_routes.router)


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.server_port,
        reload=settings.environment == "development",
    )
