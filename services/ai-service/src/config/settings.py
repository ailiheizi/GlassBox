from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 服务配置
    server_port: int = 8085
    environment: str = "development"

    # Doubao API配置（火山方舟）
    doubao_api_key: str = ""
    doubao_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str = "doubao-seed-1-8-251228"
    doubao_vision_model: str = "doubao-seed-1-8-251228"
    doubao_gui_model: str = "doubao-seed-1-8-251228"
    doubao_embedding_model: str = "doubao-embedding-vision-251215"
    doubao_embedding_dimensions: int = 2048

    # DeepSeek API配置
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # SiliconFlow API配置（备用）
    siliconflow_api_key: str = ""
    siliconflow_api_base: str = "https://api.siliconflow.cn/v1"
    siliconflow_vision_model: str = "deepseek-ai/deepseek-vl2"

    # OpenAI API配置 (可选)
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    openai_model: str = "gpt-4"

    # 默认配置
    default_temperature: float = 0.7
    default_max_tokens: int = 4096

    # Milvus配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # Worker Manager配置
    worker_manager_url: str = "http://localhost:9000"
    jwt_secret: str = "your-super-secret-key-change-in-production"

    # Langfuse 可观测性
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse-web:3000"
    langfuse_external_host: str = "http://localhost:3100"

    class Config:
        env_file = "../../.env"  # 相对于 ai-service 目录
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略额外的环境变量


settings = Settings()
