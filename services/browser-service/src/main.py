"""
Browser Service - 浏览器自动化服务
"""
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config.settings import settings

app = FastAPI(
    title="Browser Service",
    description="Browser Automation Service for NewArch",
    version="0.1.0",
)

# CORS - 从环境变量读取允许的来源
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-User-ID", "X-Request-ID"],
    expose_headers=["X-Response-User-ID", "X-Request-ID"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


# 注册路由
app.include_router(router, prefix="")


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.server_port,
        reload=settings.environment == "development",
    )
