"""
沙箱 Agent 服务单元测试 (Slim 版本)
"""

import pytest
import sys
import os

# 添加 sandbox/tools 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../sandbox/tools'))

from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


class TestAgentServer:
    """Agent Server 测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from agent_server import app
        return TestClient(app)

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime" in data

    def test_list_tools(self, client):
        """测试列出工具"""
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data

        # 验证精简后的工具存在
        tools = data["tools"]
        required_tools = ["shell", "wait"]
        for tool in required_tools:
            assert tool in tools, f"Missing tool: {tool}"

    def test_execute_shell(self, client):
        """测试 Shell 命令"""
        with patch('agent_server.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="output",
                stderr="",
                returncode=0
            )
            response = client.post("/execute", json={
                "tool": "shell",
                "params": {"command": "echo hello"}
            })
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["result"]["stdout"] == "output"

    def test_execute_unknown_tool(self, client):
        """测试未知工具"""
        response = client.post("/execute", json={
            "tool": "unknown_tool",
            "params": {}
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Unknown tool" in data["error"]

    def test_files_list_valid_path(self, client):
        """测试文件列表 - 有效路径"""
        response = client.get("/files/list?path=/tmp")
        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert "items" in data

    def test_files_list_forbidden_path(self, client):
        """测试文件列表 - 禁止路径"""
        response = client.get("/files/list?path=/etc")
        assert response.status_code == 403

    def test_files_write_and_read(self, client):
        """测试文件写入和读取"""
        import tempfile
        test_path = "/tmp/test_agent_file.txt"
        test_content = "hello from test"

        # 写入
        response = client.post("/files/write", json={
            "path": test_path,
            "content": test_content,
        })
        assert response.status_code == 200

        # 读取
        response = client.get(f"/files/read?path={test_path}")
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == test_content
        assert data["encoding"] == "utf-8"

        # 清理
        client.delete(f"/files/delete?path={test_path}")

    def test_files_mkdir(self, client):
        """测试创建目录"""
        test_dir = "/tmp/test_agent_dir"
        response = client.post("/files/mkdir", json={"path": test_dir})
        assert response.status_code == 200

        # 验证目录存在
        response = client.get(f"/files/list?path={test_dir}")
        assert response.status_code == 200

        # 清理
        client.delete(f"/files/delete?path={test_dir}")

    def test_files_rename(self, client):
        """测试重命名文件"""
        old_path = "/tmp/test_rename_old.txt"
        new_path = "/tmp/test_rename_new.txt"

        # 创建文件
        client.post("/files/write", json={"path": old_path, "content": "rename test"})

        # 重命名
        response = client.post("/files/rename", json={
            "old_path": old_path,
            "new_path": new_path,
        })
        assert response.status_code == 200

        # 验证新文件存在
        response = client.get(f"/files/read?path={new_path}")
        assert response.status_code == 200

        # 清理
        client.delete(f"/files/delete?path={new_path}")


class TestToolFunctions:
    """工具函数测试"""

    def test_tool_wait(self):
        """测试等待工具"""
        from agent_server import tool_wait
        import time

        start = time.time()
        result = tool_wait({"seconds": 0.1})
        elapsed = time.time() - start

        assert result["waited"] == 0.1
        assert elapsed >= 0.1

    def test_tool_shell(self):
        """测试 shell 工具"""
        from agent_server import tool_shell

        result = tool_shell({"command": "echo hello", "timeout": 5})
        assert "stdout" in result
        assert "hello" in result["stdout"]
        assert result["returncode"] == 0

    def test_validate_path_allowed(self):
        """测试路径验证 - 允许的路径"""
        from agent_server import _validate_path
        result = _validate_path("/tmp/test")
        assert str(result).startswith("/tmp")

    def test_validate_path_forbidden(self):
        """测试路径验证 - 禁止的路径"""
        from agent_server import _validate_path
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_path("/etc/passwd")
        assert exc_info.value.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
