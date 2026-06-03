import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.core.vision.doubao_vision import DoubaoVision


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI 客户端"""
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = AsyncMock(return_value=Mock(
        choices=[Mock(
            message=Mock(content="点击坐标: (150, 300)")
        )]
    ))
    return client


@pytest.mark.asyncio
async def test_analyze_screenshot(mock_openai_client):
    """测试截图分析"""
    with patch('src.core.vision.doubao_vision.AsyncOpenAI', return_value=mock_openai_client):
        vision = DoubaoVision(api_key="test-key")

        screenshot = "base64_encoded_image"
        instruction = "点击登录按钮"

        coords = await vision.analyze_screenshot(screenshot, instruction)

        assert coords is not None
        assert len(coords) == 2
        assert coords[0] == 150
        assert coords[1] == 300


@pytest.mark.asyncio
async def test_parse_coordinates():
    """测试坐标解析"""
    vision = DoubaoVision(api_key="test-key")

    # 测试不同格式
    assert vision._parse_coordinates("(100, 200)") == (100, 200)
    assert vision._parse_coordinates("x=100, y=200") == (100, 200)
    assert vision._parse_coordinates("坐标: 100, 200") == (100, 200)
    assert vision._parse_coordinates("[100, 200]") == (100, 200)


@pytest.mark.asyncio
async def test_analyze_screenshot_no_coordinates():
    """测试无法找到坐标的情况"""
    mock_client = Mock()
    mock_client.chat.completions.create = AsyncMock(return_value=Mock(
        choices=[Mock(
            message=Mock(content="无法找到登录按钮")
        )]
    ))

    with patch('src.core.vision.doubao_vision.AsyncOpenAI', return_value=mock_client):
        vision = DoubaoVision(api_key="test-key")

        coords = await vision.analyze_screenshot("screenshot", "点击不存在的按钮")

        assert coords is None
