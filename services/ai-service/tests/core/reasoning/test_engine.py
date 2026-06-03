import pytest
from unittest.mock import Mock, AsyncMock
from src.core.reasoning.engine import ReasoningEngine
from src.core.reasoning.trajectory import Trajectory


@pytest.fixture
def mock_llm():
    """Mock LLM 客户端"""
    llm = Mock()
    llm.chat = AsyncMock(return_value={
        "content": "用户想要打开浏览器访问 Google，需要执行 browser_navigate 工具",
        "reasoning": "分析用户意图：访问网站 -> 需要浏览器导航功能"
    })
    return llm


@pytest.mark.asyncio
async def test_reasoning_engine_analyze(mock_llm):
    """测试推理分析"""
    engine = ReasoningEngine(llm=mock_llm)

    message = "打开浏览器访问 google.com"
    screenshot = None

    result = await engine.analyze(message, screenshot)

    assert "content" in result
    assert "reasoning" in result
    assert "browser_navigate" in result["content"]
    mock_llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_reasoning_engine_with_trajectory():
    """测试带轨迹的推理"""
    engine = ReasoningEngine(llm=Mock())
    trajectory = Trajectory()

    # 添加历史步骤
    trajectory.add_step(
        action="browser_navigate",
        params={"url": "https://google.com"},
        result={"status": "ok"}
    )

    engine.set_trajectory(trajectory)

    assert len(engine.trajectory.steps) == 1
    assert engine.trajectory.steps[0]["action"] == "browser_navigate"


@pytest.mark.asyncio
async def test_reasoning_engine_with_doubao_response_format():
    """测试与 DoubaoLLM 响应格式的集成"""
    mock_llm = Mock()
    mock_llm.chat = AsyncMock(return_value={
        "id": "test-id",
        "message": {
            "role": "assistant",
            "content": "用户想要打开浏览器访问 Google，需要执行 browser_navigate 工具"
        },
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 30,
            "total_tokens": 80
        }
    })

    engine = ReasoningEngine(llm=mock_llm)

    message = "打开浏览器访问 google.com"
    result = await engine.analyze(message)

    assert "content" in result
    assert "reasoning" in result
    assert "trajectory_context" in result
    assert "browser_navigate" in result["content"]
    mock_llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_reasoning_engine_empty_message():
    """测试空消息"""
    engine = ReasoningEngine(llm=Mock())

    with pytest.raises(ValueError, match="Message cannot be empty"):
        await engine.analyze("")
