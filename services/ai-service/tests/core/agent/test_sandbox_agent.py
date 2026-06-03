import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.core.agent.sandbox_agent import SandboxAgent


@pytest.fixture
def mock_components():
    """Mock 所有组件"""
    return {
        "llm": Mock(),
        "sandbox_client": Mock(),
        "skill_selector": Mock(),
        "reasoning_engine": Mock(),
    }


@pytest.mark.asyncio
async def test_sandbox_agent_execute_task(mock_components):
    """测试任务执行"""
    agent = SandboxAgent(
        llm=mock_components["llm"],
        worker_manager_url="http://localhost:9000"
    )

    # Mock 方法
    agent.sandbox_client.get_or_create = AsyncMock(return_value={
        "id": "sandbox123",
        "user_id": "user123",
        "status": "running"
    })
    agent.sandbox_client.screenshot = AsyncMock(return_value="base64_screenshot")
    agent.reasoning_engine.analyze = AsyncMock(return_value={
        "content": "需要执行 browser_navigate",
        "reasoning": "用户想访问网站"
    })
    agent.skill_selector.select = AsyncMock(return_value=[
        {"name": "browser_navigate", "score": 0.95}
    ])
    agent.sandbox_client.execute_tool = AsyncMock(return_value={
        "status": "ok",
        "result": {"url": "https://google.com"}
    })

    # 执行任务
    results = []
    async for result in agent.execute_task("user123", "打开 google.com"):
        results.append(result)

    assert len(results) > 0
    assert results[0]["type"] == "status"
    agent.sandbox_client.get_or_create.assert_called_once()


@pytest.mark.asyncio
async def test_sandbox_agent_empty_message():
    """测试空消息"""
    agent = SandboxAgent(llm=Mock(), worker_manager_url="http://localhost:9000")

    with pytest.raises(ValueError, match="Message cannot be empty"):
        async for _ in agent.execute_task("user123", ""):
            pass


@pytest.mark.asyncio
async def test_sandbox_agent_with_vision():
    """测试带视觉分析的 SandboxAgent"""
    mock_vision = Mock()
    mock_vision.analyze_screenshot = AsyncMock(return_value=(150, 300))

    mock_sandbox_client = Mock()
    mock_sandbox_client.execute_tool = AsyncMock(return_value={
        "status": "ok",
        "result": {"x": 150, "y": 300}
    })

    agent = SandboxAgent(
        llm=Mock(),
        worker_manager_url="http://localhost:9000",
        vision=mock_vision
    )
    agent.sandbox_client = mock_sandbox_client

    result = await agent.click_with_vision(
        user_id="user123",
        instruction="点击登录按钮",
        screenshot="base64_screenshot"
    )

    mock_vision.analyze_screenshot.assert_called_once_with("base64_screenshot", "点击登录按钮")
    mock_sandbox_client.execute_tool.assert_called_once_with(
        user_id="user123",
        tool="click",
        params={"x": 150, "y": 300}
    )
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_sandbox_agent_vision_fallback():
    """测试视觉分析失败时的降级处理"""
    mock_vision = Mock()
    mock_vision.analyze_screenshot = AsyncMock(return_value=None)  # Vision fails

    mock_sandbox_client = Mock()
    mock_sandbox_client.execute_tool = AsyncMock(return_value={
        "status": "ok",
        "result": {"fallback": True}
    })

    agent = SandboxAgent(
        llm=Mock(),
        worker_manager_url="http://localhost:9000",
        vision=mock_vision
    )
    agent.sandbox_client = mock_sandbox_client

    result = await agent.click_with_vision(
        user_id="user123",
        instruction="点击登录按钮",
        screenshot="base64_screenshot"
    )

    # Should fall back to tool-based click
    mock_sandbox_client.execute_tool.assert_called_once_with(
        user_id="user123",
        tool="click_element",
        params={"selector": "点击登录按钮"}
    )
    assert result["status"] == "ok"
