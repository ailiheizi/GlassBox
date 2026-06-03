"""
AI Service 沙箱客户端单元测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/ai-service'))

from unittest.mock import patch, MagicMock, AsyncMock
import httpx


class TestSandboxClient:
    """沙箱客户端测试"""

    @pytest.fixture
    def client(self):
        """创建沙箱客户端"""
        from src.core.sandbox import SandboxClient
        return SandboxClient(worker_url="http://test-worker:9000")

    @pytest.mark.asyncio
    async def test_get_or_create_sandbox(self, client):
        """测试获取或创建沙箱"""
        mock_response = {
            "id": "sandbox-123",
            "user_id": "user-456",
            "container_id": "container-789",
            "status": "running",
            "agent_port": 8000,
            "screencast_url": "ws://localhost:8000/cdp/screencast/ws"
        }

        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None
            )

            sandbox = await client.get_or_create_sandbox("user-456")

            assert sandbox.id == "sandbox-123"
            assert sandbox.user_id == "user-456"
            assert sandbox.status == "running"
            assert sandbox.agent_port == 8000

    @pytest.mark.asyncio
    async def test_get_sandbox_not_found(self, client):
        """测试获取不存在的沙箱"""
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )
            mock_get.return_value = mock_response

            sandbox = await client.get_sandbox("nonexistent-user")
            assert sandbox is None

    @pytest.mark.asyncio
    async def test_execute_tool(self, client):
        """测试执行工具"""
        mock_response = {
            "status": "ok",
            "result": {"clicked": {"x": 100, "y": 200}},
            "timestamp": "2026-01-27T10:00:00"
        }

        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None
            )

            result = await client.execute_tool("user-123", "click", {"x": 100, "y": 200})

            assert result.status == "ok"
            assert result.result["clicked"]["x"] == 100

    @pytest.mark.asyncio
    async def test_get_screenshot(self, client):
        """测试获取截图"""
        mock_response = {
            "image": "base64encodedimage",
            "width": 1280,
            "height": 720,
            "timestamp": "2026-01-27T10:00:00"
        }

        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None
            )

            result = await client.get_screenshot("user-123")

            assert result.image == "base64encodedimage"
            assert result.width == 1280
            assert result.height == 720

    @pytest.mark.asyncio
    async def test_keepalive(self, client):
        """测试心跳保活"""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                raise_for_status=lambda: None
            )

            result = await client.keepalive("user-123")
            assert result is True

    @pytest.mark.asyncio
    async def test_destroy_sandbox(self, client):
        """测试销毁沙箱"""
        with patch('httpx.AsyncClient.delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = MagicMock(
                status_code=200,
                raise_for_status=lambda: None
            )

            result = await client.destroy_sandbox("user-123")
            assert result is True


class TestSandboxTools:
    """沙箱工具定义测试"""

    def test_sandbox_tools_defined(self):
        """测试工具定义存在"""
        from src.core.sandbox import SANDBOX_TOOLS

        assert len(SANDBOX_TOOLS) > 0

        tool_names = [t["function"]["name"] for t in SANDBOX_TOOLS]
        required_tools = [
            "sandbox_shell",
            "sandbox_screenshot",
            "sandbox_browser_use",
            "sandbox_file_list",
            "sandbox_file_read",
            "sandbox_file_write",
        ]

        for tool in required_tools:
            assert tool in tool_names, f"Missing tool: {tool}"

    def test_tool_mapping_defined(self):
        """测试工具映射存在"""
        from src.core.sandbox import TOOL_MAPPING

        assert "sandbox_shell" in TOOL_MAPPING
        assert "sandbox_wait" in TOOL_MAPPING

    def test_tool_mapping_params(self):
        """测试工具参数映射"""
        from src.core.sandbox import TOOL_MAPPING

        # 测试 shell 映射
        tool_name, param_mapper = TOOL_MAPPING["sandbox_shell"]
        assert tool_name == "shell"

        params = param_mapper({"command": "ls -la", "timeout": 10})
        assert params["command"] == "ls -la"
        assert params["timeout"] == 10

    @pytest.mark.asyncio
    async def test_execute_sandbox_tool(self):
        """测试执行沙箱工具"""
        from src.core.sandbox import SandboxClient, execute_sandbox_tool

        client = SandboxClient(worker_url="http://test:9000")

        with patch.object(client, 'execute_tool', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                status="ok",
                result={"stdout": "hello", "stderr": "", "returncode": 0}
            )

            result = await execute_sandbox_tool(
                client, "user-123", "sandbox_shell", {"command": "echo hello"}
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_sandbox_screenshot(self):
        """测试执行截图工具"""
        from src.core.sandbox import SandboxClient, execute_sandbox_tool

        client = SandboxClient(worker_url="http://test:9000")

        with patch.object(client, 'get_screenshot', new_callable=AsyncMock) as mock_screenshot:
            mock_screenshot.return_value = MagicMock(
                image="base64image",
                width=1280,
                height=720
            )

            result = await execute_sandbox_tool(
                client, "user-123", "sandbox_screenshot", {}
            )

            assert result["success"] is True
            assert result["image"] == "base64image"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
