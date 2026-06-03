"""
NewArch AI Agent Server (Slim)
沙箱内运行的 Agent 服务，提供工具执行、CDP Screencast、文件管理 API
"""

import os
import json
import base64
import subprocess
import time
import hmac
import hashlib
import asyncio
import stat
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bash_session import get_bash_session_manager, BashSessionManager

app = FastAPI(
    title="NewArch Agent API",
    description="AI Agent 工具执行服务 (Slim: CDP Screencast + 文件管理)",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 数据模型 ============

class ToolCall(BaseModel):
    tool: str
    params: Dict[str, Any] = {}

class ToolResult(BaseModel):
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: int
    signature: str

class ScreenshotResponse(BaseModel):
    image: str  # base64 encoded JPEG
    width: int
    height: int
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    user_id: str
    display: str
    uptime: float

# ============ 文件管理数据模型 ============

class FileInfo(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    size: int
    modified: float
    permissions: str

class FileWriteRequest(BaseModel):
    path: str
    content: str
    encoding: str = "utf-8"  # "utf-8" or "base64"

class FileRenameRequest(BaseModel):
    old_path: str
    new_path: str

class FileMkdirRequest(BaseModel):
    path: str

# ============ 全局状态 ============

START_TIME = time.time()
USER_ID = os.environ.get("USER_ID", "unknown")
SANDBOX_ID = os.environ.get("SANDBOX_ID", "unknown")
SANDBOX_SECRET = os.environ.get("SANDBOX_SECRET", "sandbox-secret-key")
DISPLAY = os.environ.get("DISPLAY", ":1")
CDP_INTERNAL_PORT = os.environ.get("CDP_INTERNAL_PORT", "19222")

# 文件管理安全边界
ALLOWED_PATHS = ["/home/sandbox", "/tmp"]
FILE_SIZE_LIMIT = 5 * 1024 * 1024  # 5MB


def generate_signature(user_id: str, sandbox_id: str, timestamp: int) -> str:
    """生成 HMAC-SHA256 签名"""
    data = f"{user_id}:{sandbox_id}:{timestamp}"
    signature = hmac.new(
        SANDBOX_SECRET.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature


def _validate_path(path: str) -> Path:
    """验证文件路径在安全边界内"""
    resolved = Path(path).resolve()
    for allowed in ALLOWED_PATHS:
        if str(resolved).startswith(allowed):
            return resolved
    raise HTTPException(status_code=403, detail=f"Access denied: path must be under {ALLOWED_PATHS}")


# ============ 工具实现 ============

def tool_shell(params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 Shell 命令"""
    command = params.get("command", "")
    timeout = params.get("timeout", 30)
    cwd = params.get("cwd", "/home/sandbox/workspace")

    # 后台命令（以 & 结尾）用 Popen 立即返回
    if command.rstrip().endswith("&"):
        try:
            subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                env={**os.environ, "DISPLAY": DISPLAY},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"stdout": "Process started in background", "stderr": "", "returncode": 0}
        except Exception as e:
            return {"error": str(e)}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env={**os.environ, "DISPLAY": DISPLAY}
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out", "timeout": timeout}
    except Exception as e:
        return {"error": str(e)}


def tool_wait(params: Dict[str, Any]) -> Dict[str, Any]:
    """等待指定时间"""
    seconds = params.get("seconds", 1)
    time.sleep(seconds)
    return {"waited": seconds}


# 精简后的工具映射表
TOOLS = {
    "shell": tool_shell,
    "wait": tool_wait,
}

# ============ API 端点 ============

@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        user_id=USER_ID,
        display=DISPLAY,
        uptime=time.time() - START_TIME
    )


@app.get("/screenshot", response_model=ScreenshotResponse)
async def screenshot():
    """获取当前浏览器截图（通过 CDP Page.captureScreenshot）"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 获取第一个页面的 WebSocket URL
            resp = await client.get(f"http://localhost:{CDP_INTERNAL_PORT}/json")
            pages = resp.json()
            if not pages:
                raise HTTPException(status_code=500, detail="No browser pages found")

            ws_url = pages[0].get("webSocketDebuggerUrl", "")
            if not ws_url:
                raise HTTPException(status_code=500, detail="No WebSocket URL for page")

            # 通过 CDP 协议截图
            import websockets
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({
                    "id": 1,
                    "method": "Page.captureScreenshot",
                    "params": {"format": "jpeg", "quality": 80}
                }))
                result = json.loads(await ws.recv())

                if "error" in result:
                    raise HTTPException(status_code=500, detail=f"CDP error: {result['error']}")

                image_data = result["result"]["data"]

                # 获取页面尺寸
                await ws.send(json.dumps({
                    "id": 2,
                    "method": "Browser.getWindowBounds",
                    "params": {"windowId": 1}
                }))
                # 尝试获取尺寸，失败则用默认值
                try:
                    bounds_result = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    bounds = bounds_result.get("result", {}).get("bounds", {})
                    width = bounds.get("width", 1280)
                    height = bounds.get("height", 720)
                except Exception:
                    width, height = 1280, 720

                from datetime import datetime
                return ScreenshotResponse(
                    image=image_data,
                    width=width,
                    height=height,
                    timestamp=datetime.now().isoformat()
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {str(e)}")


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """执行工具调用"""
    tool_name = call.tool
    params = call.params

    ts = int(time.time())
    sig = generate_signature(USER_ID, SANDBOX_ID, ts)

    if tool_name not in TOOLS:
        return ToolResult(
            status="error",
            error=f"Unknown tool: {tool_name}. Available tools: {list(TOOLS.keys())}",
            timestamp=ts,
            signature=sig
        )

    try:
        tool_func = TOOLS[tool_name]
        result = tool_func(params)

        return ToolResult(
            status="ok",
            result=result,
            timestamp=ts,
            signature=sig
        )
    except Exception as e:
        return ToolResult(
            status="error",
            error=str(e),
            timestamp=ts,
            signature=sig
        )


@app.get("/tools")
async def list_tools():
    """列出所有可用工具"""
    tool_docs = {
        "shell": {"description": "执行 Shell 命令", "params": {"command": "string", "timeout": "int", "cwd": "string"}},
        "wait": {"description": "等待指定时间", "params": {"seconds": "float"}},
    }
    return {"tools": tool_docs}


# ============ CDP 信息 API ============

@app.get("/cdp/info")
async def cdp_info():
    """返回 Chromium CDP 连接信息"""
    cdp_port = os.environ.get("CDP_PORT", "9222")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"http://localhost:{CDP_INTERNAL_PORT}/json/version")
            data = resp.json()
            ws_url = data.get("webSocketDebuggerUrl", "")
            if ws_url:
                ws_url = ws_url.replace(f":{CDP_INTERNAL_PORT}/", f":{cdp_port}/")
            return {
                "cdp_url": f"http://localhost:{cdp_port}",
                "ws_url": ws_url,
                "browser": data.get("Browser", ""),
            }
    except Exception as e:
        return {"error": str(e), "cdp_url": f"http://localhost:{cdp_port}"}


# ============ CDP Screencast WebSocket ============

@app.websocket("/cdp/screencast/ws")
async def cdp_screencast_ws(
    websocket: WebSocket,
    quality: int = Query(default=60),
    maxWidth: int = Query(default=1280),
    maxHeight: int = Query(default=720),
    everyNthFrame: int = Query(default=1),
    format: str = Query(default="jpeg"),
):
    """
    CDP Screencast WebSocket 中继
    客户端连接后，自动启动 Page.startScreencast，转发帧数据
    """
    await websocket.accept()

    import httpx
    import websockets

    cdp_ws = None
    try:
        # 获取第一个页面的 WebSocket URL
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"http://localhost:{CDP_INTERNAL_PORT}/json")
            pages = resp.json()
            if not pages:
                await websocket.send_json({"error": "No browser pages found"})
                await websocket.close()
                return
            page_ws_url = pages[0].get("webSocketDebuggerUrl", "")

        if not page_ws_url:
            await websocket.send_json({"error": "No WebSocket URL for page"})
            await websocket.close()
            return

        # 连接 CDP WebSocket
        cdp_ws = await websockets.connect(page_ws_url)

        # 启用 Page domain
        await cdp_ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await cdp_ws.recv()

        # 启动 screencast
        await cdp_ws.send(json.dumps({
            "id": 2,
            "method": "Page.startScreencast",
            "params": {
                "format": format,
                "quality": quality,
                "maxWidth": maxWidth,
                "maxHeight": maxHeight,
                "everyNthFrame": everyNthFrame,
            }
        }))
        await cdp_ws.recv()

        # 双向中继
        async def forward_cdp_to_client():
            """从 CDP 接收帧，转发给客户端"""
            try:
                async for msg in cdp_ws:
                    data = json.loads(msg)
                    method = data.get("method", "")

                    if method == "Page.screencastFrame":
                        params = data.get("params", {})
                        session_id = params.get("sessionId", 0)

                        # 发送帧给客户端
                        await websocket.send_json({
                            "type": "frame",
                            "data": params.get("data", ""),
                            "metadata": params.get("metadata", {}),
                        })

                        # 确认帧
                        await cdp_ws.send(json.dumps({
                            "id": 100,
                            "method": "Page.screencastFrameAck",
                            "params": {"sessionId": session_id}
                        }))
            except (websockets.exceptions.ConnectionClosed, WebSocketDisconnect):
                pass

        async def forward_client_to_cdp():
            """从客户端接收消息（用于控制命令）"""
            try:
                while True:
                    msg = await websocket.receive_text()
                    data = json.loads(msg)
                    # 客户端可以发送控制命令，如调整质量
                    if data.get("type") == "set_quality":
                        # 重启 screencast 以应用新参数
                        await cdp_ws.send(json.dumps({"id": 3, "method": "Page.stopScreencast"}))
                        await cdp_ws.recv()
                        await cdp_ws.send(json.dumps({
                            "id": 4,
                            "method": "Page.startScreencast",
                            "params": {
                                "format": format,
                                "quality": data.get("quality", quality),
                                "maxWidth": data.get("maxWidth", maxWidth),
                                "maxHeight": data.get("maxHeight", maxHeight),
                                "everyNthFrame": data.get("everyNthFrame", everyNthFrame),
                            }
                        }))
                        await cdp_ws.recv()
            except (WebSocketDisconnect, Exception):
                pass

        # 并行运行两个方向的中继
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(forward_cdp_to_client()),
                asyncio.create_task(forward_client_to_cdp()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        # 停止 screencast
        if cdp_ws:
            try:
                await cdp_ws.send(json.dumps({"id": 99, "method": "Page.stopScreencast"}))
                await cdp_ws.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass


# ============ 文件管理 API ============

@app.get("/files/list")
async def files_list(path: str = "/home/sandbox"):
    """列出目录内容"""
    resolved = _validate_path(path)

    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    items: List[Dict[str, Any]] = []
    try:
        for entry in sorted(resolved.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                st = entry.stat()
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "directory" if entry.is_dir() else "file",
                    "size": st.st_size if entry.is_file() else 0,
                    "modified": st.st_mtime,
                    "permissions": stat.filemode(st.st_mode),
                })
            except PermissionError:
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "unknown",
                    "size": 0,
                    "modified": 0,
                    "permissions": "----------",
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

    return {"path": str(resolved), "items": items}


@app.get("/files/read")
async def files_read(path: str):
    """读取文件内容"""
    resolved = _validate_path(path)

    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    if not resolved.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {path}")
    if resolved.stat().st_size > FILE_SIZE_LIMIT:
        raise HTTPException(status_code=413, detail=f"File too large (max {FILE_SIZE_LIMIT // 1024 // 1024}MB)")

    try:
        content = resolved.read_text(encoding="utf-8")
        return {"path": str(resolved), "content": content, "encoding": "utf-8", "size": len(content)}
    except UnicodeDecodeError:
        # 二进制文件，返回 base64
        content_bytes = resolved.read_bytes()
        return {
            "path": str(resolved),
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "encoding": "base64",
            "size": len(content_bytes),
        }


@app.post("/files/write")
async def files_write(request: FileWriteRequest):
    """写入文件"""
    resolved = _validate_path(request.path)

    # 确保父目录存在
    resolved.parent.mkdir(parents=True, exist_ok=True)

    if request.encoding == "base64":
        content_bytes = base64.b64decode(request.content)
        if len(content_bytes) > FILE_SIZE_LIMIT:
            raise HTTPException(status_code=413, detail=f"Content too large (max {FILE_SIZE_LIMIT // 1024 // 1024}MB)")
        resolved.write_bytes(content_bytes)
        return {"path": str(resolved), "size": len(content_bytes), "encoding": "base64"}
    else:
        if len(request.content.encode("utf-8")) > FILE_SIZE_LIMIT:
            raise HTTPException(status_code=413, detail=f"Content too large (max {FILE_SIZE_LIMIT // 1024 // 1024}MB)")
        resolved.write_text(request.content, encoding="utf-8")
        return {"path": str(resolved), "size": len(request.content), "encoding": "utf-8"}


@app.delete("/files/delete")
async def files_delete(path: str):
    """删除文件或目录"""
    resolved = _validate_path(path)

    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    import shutil
    if resolved.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink()

    return {"deleted": str(resolved)}


@app.post("/files/rename")
async def files_rename(request: FileRenameRequest):
    """重命名/移动文件"""
    old_resolved = _validate_path(request.old_path)
    new_resolved = _validate_path(request.new_path)

    if not old_resolved.exists():
        raise HTTPException(status_code=404, detail=f"Source not found: {request.old_path}")

    new_resolved.parent.mkdir(parents=True, exist_ok=True)
    old_resolved.rename(new_resolved)

    return {"old_path": str(old_resolved), "new_path": str(new_resolved)}


@app.post("/files/mkdir")
async def files_mkdir(request: FileMkdirRequest):
    """创建目录"""
    resolved = _validate_path(request.path)
    resolved.mkdir(parents=True, exist_ok=True)
    return {"path": str(resolved)}


# ============ 持久化 Bash 会话 API ============

class BashExecuteRequest(BaseModel):
    """Bash 执行请求"""
    command: str
    timeout: int = 30
    wait_for_completion: bool = True


class BashExecuteResponse(BaseModel):
    """Bash 执行响应"""
    status: str
    output: Optional[str] = None
    exit_code: Optional[int] = None
    cwd: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None


class BashEnvRequest(BaseModel):
    """环境变量设置请求"""
    key: str
    value: str


@app.post("/bash/execute", response_model=BashExecuteResponse)
async def bash_execute(request: BashExecuteRequest):
    """在持久化 Bash 会话中执行命令"""
    try:
        bash_manager = get_bash_session_manager()
        result = await bash_manager.execute(
            user_id=USER_ID,
            command=request.command,
            timeout=request.timeout,
            wait_for_completion=request.wait_for_completion
        )

        return BashExecuteResponse(
            status=result.get("status", "unknown"),
            output=result.get("output"),
            exit_code=result.get("exit_code"),
            cwd=result.get("cwd"),
            session_id=result.get("session_id"),
            error=result.get("error")
        )
    except Exception as e:
        return BashExecuteResponse(
            status="error",
            error=str(e)
        )


@app.get("/bash/cwd")
async def bash_get_cwd():
    """获取当前工作目录"""
    try:
        bash_manager = get_bash_session_manager()
        cwd = await bash_manager.get_cwd(USER_ID)
        return {"cwd": cwd}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bash/env")
async def bash_set_env(request: BashEnvRequest):
    """设置环境变量"""
    try:
        bash_manager = get_bash_session_manager()
        result = await bash_manager.set_env(USER_ID, request.key, request.value)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/bash/env/{key}")
async def bash_get_env(key: str):
    """获取环境变量"""
    try:
        bash_manager = get_bash_session_manager()
        value = await bash_manager.get_env(USER_ID, key)
        return {"key": key, "value": value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/bash/sessions")
async def bash_list_sessions():
    """列出所有活跃的 Bash 会话"""
    try:
        bash_manager = get_bash_session_manager()
        sessions = await bash_manager.list_sessions()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/bash/session")
async def bash_destroy_session():
    """销毁当前用户的 Bash 会话"""
    try:
        bash_manager = get_bash_session_manager()
        success = await bash_manager.destroy_session(USER_ID)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 启动 ============

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("AGENT_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
