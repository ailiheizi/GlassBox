from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 服务配置
    server_port: int = 8082
    environment: str = "development"

    # 外部服务地址
    ai_service_url: str = "http://localhost:8085"
    memory_service_url: str = "http://localhost:8083"
    index_service_url: str = "http://localhost:8084"

    # 浏览器配置
    browser_headless: bool = True
    browser_viewport_width: int = 1920
    browser_viewport_height: int = 1080

    # Agent配置
    max_iterations: int = 50
    response_sign_secret: str = "response-sign-secret"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
