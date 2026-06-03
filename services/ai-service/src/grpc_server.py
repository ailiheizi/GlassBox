"""
AI Service gRPC 实现

提供 Embedding 生成和聊天功能的 gRPC 接口
"""
import grpc
from concurrent import futures
from typing import List, Dict, Any
import logging

# 生成的 proto 代码 (需要先运行 protoc)
# from proto import ai_pb2, ai_pb2_grpc

logger = logging.getLogger(__name__)


class AIServicer:
    """
    AI gRPC 服务实现

    注意: 实际使用需要先用 protoc 生成 Python 代码:
    python -m grpc_tools.protoc -I../../shared/proto \
        --python_out=./proto --grpc_python_out=./proto \
        ../../shared/proto/ai.proto
    """

    def __init__(self, llm_client, embedding_client):
        self.llm_client = llm_client
        self.embedding_client = embedding_client

    async def GenerateEmbedding(self, request, context):
        """生成 Embedding"""
        try:
            text = request.text
            model = request.model or "text-embedding-v2"

            embedding = await self.embedding_client.embed(text, model=model)

            # 返回响应
            return {
                "embedding": embedding,
                "dimensions": len(embedding),
                "model": model,
            }
        except Exception as e:
            logger.error(f"GenerateEmbedding error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return None

    async def BatchGenerateEmbedding(self, request, context):
        """批量生成 Embedding"""
        try:
            texts = list(request.texts)
            model = request.model or "text-embedding-v2"

            embeddings = await self.embedding_client.embed_batch(texts, model=model)

            results = [
                {"index": i, "embedding": emb}
                for i, emb in enumerate(embeddings)
            ]

            return {
                "results": results,
                "model": model,
            }
        except Exception as e:
            logger.error(f"BatchGenerateEmbedding error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return None

    async def Chat(self, request, context):
        """聊天 (非流式)"""
        try:
            # 转换消息格式
            messages = []
            for msg in request.messages:
                message = {
                    "role": msg.role,
                    "content": msg.content,
                }
                if msg.name:
                    message["name"] = msg.name
                if msg.tool_call_id:
                    message["tool_call_id"] = msg.tool_call_id
                if msg.tool_calls:
                    message["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                messages.append(message)

            # 转换工具格式
            tools = None
            if request.tools:
                tools = [
                    {
                        "type": tool.type,
                        "function": {
                            "name": tool.function.name,
                            "description": tool.function.description,
                            "parameters": tool.function.parameters,
                        }
                    }
                    for tool in request.tools
                ]

            # 调用 LLM
            response = await self.llm_client.chat(
                messages=messages,
                tools=tools,
                tool_choice=request.tool_choice or "auto",
                model=request.model,
                temperature=request.temperature or 0.7,
                max_tokens=request.max_tokens or 4096,
            )

            # 构建响应
            result = {
                "id": response.get("id", ""),
                "message": {
                    "role": "assistant",
                    "content": response.get("content", ""),
                },
                "finish_reason": response.get("finish_reason", "stop"),
                "usage": {
                    "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": response.get("usage", {}).get("total_tokens", 0),
                },
            }

            # 处理工具调用
            if response.get("tool_calls"):
                result["message"]["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": tc["type"],
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        }
                    }
                    for tc in response["tool_calls"]
                ]

            return result

        except Exception as e:
            logger.error(f"Chat error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return None


def serve(port: int, llm_client, embedding_client):
    """启动 gRPC 服务器"""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    servicer = AIServicer(llm_client, embedding_client)
    # ai_pb2_grpc.add_AIServiceServicer_to_server(servicer, server)

    server.add_insecure_port(f'[::]:{port}')

    logger.info(f"AI gRPC server starting on port {port}")
    return server


# gRPC 客户端封装
class AIGRPCClient:
    """AI gRPC 客户端"""

    def __init__(self, address: str):
        self.address = address
        self.channel = None
        self.stub = None

    async def connect(self):
        """连接到服务器"""
        self.channel = grpc.aio.insecure_channel(self.address)
        # self.stub = ai_pb2_grpc.AIServiceStub(self.channel)

    async def close(self):
        """关闭连接"""
        if self.channel:
            await self.channel.close()

    async def generate_embedding(self, text: str, model: str = None) -> List[float]:
        """生成 Embedding"""
        raise NotImplementedError("gRPC client methods not implemented - use HTTP API instead")

    async def batch_generate_embedding(self, texts: List[str], model: str = None) -> List[List[float]]:
        """批量生成 Embedding"""
        raise NotImplementedError("gRPC client methods not implemented - use HTTP API instead")

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """聊天"""
        raise NotImplementedError("gRPC client methods not implemented - use HTTP API instead")
