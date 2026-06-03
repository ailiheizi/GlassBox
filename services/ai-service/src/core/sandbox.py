"""
沙箱 Agent 客户端
用于与 Worker Manager 和沙箱内的 Agent 服务通信
"""

import os
import httpx
import hmac
import hashlib
import time
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class SandboxInfo(BaseModel):
    """沙箱信息"""
    id: str
    user_id: str
    container_id: str
    status: str
    agent_port: int
    screencast_url: str = ""


class ToolResult(BaseModel):
    """工具执行结果"""
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: int  # Unix timestamp for signature verification
    signature: Optional[str] = None  # HMAC signature


class ScreenshotResult(BaseModel):
    """截图结果"""
    image: str  # base64
    width: int
    height: int
    timestamp: str


class SandboxClient:
    """沙箱客户端"""

    def __init__(self, worker_url: Optional[str] = None, llm_client=None, jwt_token: Optional[str] = None):
        self.worker_url = worker_url or os.getenv("WORKER_SERVICE_URL", "http://worker-manager:9000")
        self.sandbox_secret = os.getenv("SANDBOX_SECRET", "sandbox-secret-key")
        self.jwt_token = jwt_token or os.getenv("JWT_TOKEN", "")
        self.timeout = 60.0
        self.llm_client = llm_client  # For vision-based analysis

    def _generate_signature(self, user_id: str, sandbox_id: str = "") -> tuple[str, int]:
        """生成 HMAC 签名"""
        timestamp = int(time.time())
        data = f"{user_id}:{sandbox_id}:{timestamp}"
        signature = hmac.new(
            self.sandbox_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp

    def _get_headers(self, user_id: str, sandbox_id: str = "") -> Dict[str, str]:
        """获取请求头，包含认证和签名"""
        signature, timestamp = self._generate_signature(user_id, sandbox_id)
        headers = {
            "X-User-ID": user_id,
            "X-Signature": signature,
            "X-Timestamp": str(timestamp),
            "Content-Type": "application/json"
        }
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    async def get_or_create_sandbox(self, user_id: str) -> SandboxInfo:
        """获取或创建用户沙箱"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.worker_url}/api/v1/sandboxes/get-or-create",
                json={"user_id": user_id},
                headers=self._get_headers(user_id)
            )
            response.raise_for_status()
            return SandboxInfo(**response.json())

    async def get_or_create(self, user_id: str) -> dict:
        """获取或创建沙盒（返回字典）"""
        result = await self.get_or_create_sandbox(user_id)
        return result.dict()

    async def screenshot(self, user_id: str) -> str:
        """获取沙盒截图（返回 base64）"""
        result = await self.get_screenshot(user_id)
        return result.image

    async def get_sandbox(self, user_id: str) -> Optional[SandboxInfo]:
        """获取用户沙箱信息"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                headers = self._get_headers(user_id)
                response = await client.get(f"{self.worker_url}/api/v1/sandboxes/{user_id}", headers=headers)
                response.raise_for_status()
                return SandboxInfo(**response.json())
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

    async def destroy_sandbox(self, user_id: str) -> bool:
        """销毁用户沙箱"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                headers = self._get_headers(user_id)
                response = await client.delete(f"{self.worker_url}/api/v1/sandboxes/{user_id}", headers=headers)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError:
                return False

    async def keepalive(self, user_id: str) -> bool:
        """心跳保活"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                headers = self._get_headers(user_id)
                response = await client.post(f"{self.worker_url}/api/v1/sandboxes/{user_id}/keepalive", headers=headers)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError:
                return False

    async def execute_tool(self, user_id: str, tool: str, params: Dict[str, Any]) -> ToolResult:
        """执行工具"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._get_headers(user_id)
            response = await client.post(
                f"{self.worker_url}/api/v1/tools/{user_id}/execute",
                json={"tool": tool, "params": params},
                headers=headers
            )
            response.raise_for_status()
            return ToolResult(**response.json())

    async def get_screenshot(self, user_id: str) -> ScreenshotResult:
        """获取截图"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._get_headers(user_id)
            response = await client.get(f"{self.worker_url}/api/v1/tools/{user_id}/screenshot", headers=headers)
            response.raise_for_status()
            return ScreenshotResult(**response.json())

    async def get_screenshot_with_resize_info(self, user_id: str) -> Dict[str, Any]:
        """
        获取截图并返回resize信息

        Returns:
            {
                "image": str,  # base64 encoded (可能已resize)
                "original_image": str,  # base64 encoded (原始图像)
                "original_width": int,
                "original_height": int,
                "resized_width": int,
                "resized_height": int,
                "is_resized": bool
            }
        """
        from src.utils.coordinate_utils import smart_resize
        from PIL import Image
        import io
        import base64

        # 获取原始截图
        result = await self.get_screenshot(user_id)

        # 解码图像获取原始尺寸
        image_data = base64.b64decode(result.image)
        img = Image.open(io.BytesIO(image_data))
        original_width, original_height = img.size

        # 计算resize后的尺寸
        resized_height, resized_width = smart_resize(original_height, original_width)

        # 判断是否需要resize
        is_resized = (resized_width, resized_height) != (original_width, original_height)

        # 实际resize图像（如果需要）
        if is_resized:
            img_resized = img.resize((resized_width, resized_height), Image.LANCZOS)
            buffer = io.BytesIO()
            img_resized.save(buffer, format='PNG')
            resized_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        else:
            resized_image_base64 = result.image

        return {
            "image": resized_image_base64,  # 发送给LLM的图像
            "original_image": result.image,  # 原始图像
            "original_width": original_width,
            "original_height": original_height,
            "resized_width": resized_width,
            "resized_height": resized_height,
            "is_resized": is_resized,
            "timestamp": result.timestamp
        }

    async def get_cdp_url(self, user_id: str) -> str:
        """获取沙箱 Chromium 的 CDP URL"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._get_headers(user_id)
            response = await client.get(
                f"{self.worker_url}/api/v1/tools/{user_id}/cdp-info",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            # 将 localhost 替换为沙箱容器可达地址
            return data.get("cdp_url", "")

    async def list_tools(self, user_id: str) -> Dict[str, Any]:
        """获取可用工具列表"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._get_headers(user_id)
            response = await client.get(f"{self.worker_url}/api/v1/tools/{user_id}/list", headers=headers)
            response.raise_for_status()
            return response.json()

    # ============ 文件操作 API ============

    async def file_list(self, user_id: str, path: str = "/home/sandbox") -> Dict[str, Any]:
        """列出沙箱中指定目录的文件"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._get_headers(user_id)
            response = await client.get(
                f"{self.worker_url}/api/v1/tools/{user_id}/files/list",
                params={"path": path},
                headers=headers
            )
            response.raise_for_status()
            return {"success": True, "result": response.json()}

    async def file_read(self, user_id: str, path: str) -> Dict[str, Any]:
        """读取沙箱中指定文件"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._get_headers(user_id)
            response = await client.get(
                f"{self.worker_url}/api/v1/tools/{user_id}/files/read",
                params={"path": path},
                headers=headers
            )
            response.raise_for_status()
            return {"success": True, "result": response.json()}

    async def file_write(self, user_id: str, path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """写入文件到沙箱"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._get_headers(user_id)
            response = await client.post(
                f"{self.worker_url}/api/v1/tools/{user_id}/files/write",
                json={"path": path, "content": content, "encoding": encoding},
                headers=headers
            )
            response.raise_for_status()
            return {"success": True, "result": response.json()}


# 定义 AI 可用的沙箱工具（精简：去掉 GUI 工具，新增文件操作）
SANDBOX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sandbox_shell",
            "description": "在沙箱中执行 Shell 命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时时间（秒），默认 30"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_screenshot",
            "description": "获取沙箱当前浏览器截图（通过 CDP）",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_wait",
            "description": "等待指定时间",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "等待秒数"}
                },
                "required": ["seconds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_bash_execute",
            "description": "在持久化 Bash 会话中执行命令，支持 cd、环境变量等状态保持",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时时间（秒），默认 30"},
                    "wait_for_completion": {"type": "boolean", "description": "是否等待命令完成，默认 true"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_bash_cwd",
            "description": "获取持久化 Bash 会话的当前工作目录",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_bash_env",
            "description": "设置持久化 Bash 会话的环境变量",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "环境变量名"},
                    "value": {"type": "string", "description": "环境变量值"}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_browser_use",
            "description": "智能浏览器操作：使用 DOM 操作执行浏览器任务（推荐用于所有网页任务，如打开网站、登录、搜索、查看页面内容）。比截图点击更准确。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "浏览器任务描述，如'打开百度搜索 browser-use'"},
                    "max_steps": {"type": "integer", "description": "最大执行步数，默认 20"}
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_file_list",
            "description": "列出沙箱中指定目录的文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认 /home/sandbox"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_file_read",
            "description": "读取沙箱中指定文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_file_write",
            "description": "写入内容到沙箱中的文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"},
                    "encoding": {"type": "string", "description": "编码方式: utf-8 或 base64，默认 utf-8"}
                },
                "required": ["path", "content"]
            }
        }
    }
]


# 工具名称到沙箱工具的映射（精简：去掉 GUI 工具）
TOOL_MAPPING = {
    "sandbox_shell": ("shell", lambda p: {"command": p["command"], "timeout": p.get("timeout", 30)}),
    "sandbox_wait": ("wait", lambda p: {"seconds": p["seconds"]}),
    # 持久化 Bash 会话工具
    "sandbox_bash_execute": ("bash_execute", lambda p: {
        "command": p["command"],
        "timeout": p.get("timeout", 30),
        "wait_for_completion": p.get("wait_for_completion", True)
    }),
    "sandbox_bash_cwd": ("bash_cwd", lambda p: {}),
    "sandbox_bash_env": ("bash_env", lambda p: {"key": p["key"], "value": p["value"]}),
}


async def execute_sandbox_tool(
    client: SandboxClient,
    user_id: str,
    tool_name: str,
    params: Dict[str, Any],
    resize_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    执行沙箱工具

    Args:
        client: SandboxClient实例
        user_id: 用户ID
        tool_name: 工具名称
        params: 工具参数
        resize_info: 图像resize信息（保留接口兼容，当前不再需要坐标映射）
    """
    if tool_name == "sandbox_screenshot":
        result = await client.get_screenshot(user_id)
        return {
            "success": True,
            "image": result.image,
            "width": result.width,
            "height": result.height
        }

    # browser-use: 通过 CDP 连接沙箱 Chromium 执行浏览器任务
    if tool_name == "sandbox_browser_use":
        from src.core.browser_use_client import BrowserUseClient
        bu_client = await BrowserUseClient.get_instance(user_id)
        try:
            cdp_url = await client.get_cdp_url(user_id)
            if not cdp_url:
                return {"success": False, "error": "Failed to get CDP URL from sandbox"}
            await bu_client.connect(cdp_url)
            result = await bu_client.run_task(
                task=params["task"],
                max_steps=params.get("max_steps", 20)
            )
            return result
        except Exception as e:
            return {"success": False, "error": f"browser-use failed: {str(e)}"}

    # 文件操作工具：通过 Worker-Manager 文件代理端点
    if tool_name == "sandbox_file_list":
        return await client.file_list(user_id, params.get("path", "/home/sandbox"))

    if tool_name == "sandbox_file_read":
        return await client.file_read(user_id, params["path"])

    if tool_name == "sandbox_file_write":
        return await client.file_write(
            user_id, params["path"], params["content"],
            params.get("encoding", "utf-8")
        )

    if tool_name not in TOOL_MAPPING:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    sandbox_tool, param_mapper = TOOL_MAPPING[tool_name]
    mapped_params = param_mapper(params)

    result = await client.execute_tool(user_id, sandbox_tool, mapped_params)

    if result.status == "ok":
        return {"success": True, "result": result.result}
    else:
        return {"success": False, "error": result.error}
