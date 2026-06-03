import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.core.skill.selector import SkillSelector
from src.core.skill.milvus_client import MilvusClient, MilvusClientError


@pytest.fixture
def mock_milvus():
    """Mock Milvus 客户端"""
    client = Mock(spec=MilvusClient)
    client.search = AsyncMock(return_value=[
        {"id": "skill1", "name": "browser_navigate", "score": 0.95, "description": "Navigate browser", "category": "browser"},
        {"id": "skill2", "name": "click_element", "score": 0.87, "description": "Click element", "category": "interaction"}
    ])
    return client


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service"""
    service = Mock()
    service.embed = AsyncMock(return_value=[0.1] * 768)
    return service


@pytest.mark.asyncio
async def test_skill_selector_select_skills(mock_milvus):
    """测试技能选择"""
    selector = SkillSelector(milvus_client=mock_milvus)

    message = "打开浏览器访问 google.com"
    skills = await selector.select(message, top_k=3)

    assert len(skills) > 0
    assert skills[0]["name"] == "browser_navigate"
    assert skills[0]["score"] > 0.8
    mock_milvus.search.assert_called_once()


@pytest.mark.asyncio
async def test_skill_selector_empty_message():
    """测试空消息"""
    selector = SkillSelector(milvus_client=Mock())

    with pytest.raises(ValueError, match="Message cannot be empty"):
        await selector.select("")


@pytest.mark.asyncio
async def test_skill_selector_whitespace_message():
    """测试仅包含空格的消息"""
    selector = SkillSelector(milvus_client=Mock())

    with pytest.raises(ValueError, match="Message cannot be empty"):
        await selector.select("   ")


@pytest.mark.asyncio
async def test_skill_selector_invalid_top_k():
    """测试无效的 top_k 参数"""
    selector = SkillSelector(milvus_client=Mock())

    with pytest.raises(ValueError, match="top_k must be greater than 0"):
        await selector.select("test message", top_k=0)

    with pytest.raises(ValueError, match="top_k must be greater than 0"):
        await selector.select("test message", top_k=-1)


@pytest.mark.asyncio
async def test_skill_selector_with_embedding_service(mock_milvus, mock_embedding_service):
    """测试与 embedding_service 集成"""
    selector = SkillSelector(
        milvus_client=mock_milvus,
        embedding_service=mock_embedding_service
    )

    message = "打开浏览器"
    skills = await selector.select(message)

    assert len(skills) > 0
    mock_embedding_service.embed.assert_called_once_with(message)
    mock_milvus.search.assert_called_once()


@pytest.mark.asyncio
async def test_skill_selector_with_context_reranking(mock_milvus):
    """测试基于上下文的重新排序"""
    selector = SkillSelector(milvus_client=mock_milvus)

    message = "点击按钮"
    context = {"has_screenshot": True}
    skills = await selector.select(message, context=context)

    # click_element 应该被提升权重
    assert len(skills) > 0
    click_skill = next((s for s in skills if s["name"] == "click_element"), None)
    if click_skill:
        assert click_skill["score"] > 0.87  # 原始分数乘以 1.2


@pytest.mark.asyncio
async def test_skill_selector_milvus_connection_failure(mock_milvus):
    """测试 Milvus 连接失败"""
    mock_milvus.search = AsyncMock(side_effect=MilvusClientError("Connection failed"))
    selector = SkillSelector(milvus_client=mock_milvus)

    with pytest.raises(MilvusClientError, match="Connection failed"):
        await selector.select("test message")


@pytest.mark.asyncio
async def test_skill_selector_milvus_search_exception(mock_milvus):
    """测试 Milvus 查询异常"""
    mock_milvus.search = AsyncMock(side_effect=MilvusClientError("Search operation failed"))
    selector = SkillSelector(milvus_client=mock_milvus)

    with pytest.raises(MilvusClientError, match="Search operation failed"):
        await selector.select("test message")


@pytest.mark.asyncio
async def test_skill_selector_empty_results(mock_milvus):
    """测试空结果"""
    mock_milvus.search = AsyncMock(return_value=[])
    selector = SkillSelector(milvus_client=mock_milvus)

    skills = await selector.select("test message")

    assert len(skills) == 0
    mock_milvus.search.assert_called_once()


@pytest.mark.asyncio
async def test_skill_selector_multiple_skills_sorting(mock_milvus):
    """测试多个技能的排序"""
    mock_milvus.search = AsyncMock(return_value=[
        {"id": "skill1", "name": "skill_a", "score": 0.5, "description": "Skill A", "category": "cat1"},
        {"id": "skill2", "name": "skill_b", "score": 0.9, "description": "Skill B", "category": "cat2"},
        {"id": "skill3", "name": "skill_c", "score": 0.7, "description": "Skill C", "category": "cat3"}
    ])
    selector = SkillSelector(milvus_client=mock_milvus)

    message = "test"
    context = {"has_screenshot": True}
    skills = await selector.select(message, context=context)

    # 验证排序（分数从高到低）
    assert len(skills) == 3
    assert skills[0]["score"] >= skills[1]["score"]
    assert skills[1]["score"] >= skills[2]["score"]


@pytest.mark.asyncio
async def test_skill_selector_embedding_service_failure(mock_milvus, mock_embedding_service):
    """测试 embedding_service 失败"""
    mock_embedding_service.embed = AsyncMock(side_effect=Exception("Embedding failed"))
    selector = SkillSelector(
        milvus_client=mock_milvus,
        embedding_service=mock_embedding_service
    )

    with pytest.raises(Exception, match="Embedding failed"):
        await selector.select("test message")


@pytest.mark.asyncio
async def test_skill_selector_without_embedding_service():
    """测试没有 embedding_service 时使用随机向量"""
    mock_milvus = Mock(spec=MilvusClient)
    mock_milvus.search = AsyncMock(return_value=[
        {"id": "skill1", "name": "test_skill", "score": 0.9, "description": "Test", "category": "test"}
    ])
    selector = SkillSelector(milvus_client=mock_milvus)

    message = "test message"
    skills = await selector.select(message)

    assert len(skills) > 0
    # 验证 search 被调用，且传入的 embedding 是列表
    call_args = mock_milvus.search.call_args
    assert call_args is not None
    embedding = call_args.kwargs.get("embedding") or call_args[1][0]
    assert isinstance(embedding, list)
    assert len(embedding) == 768


@pytest.mark.asyncio
async def test_skill_selector_context_without_screenshot():
    """测试没有截图的上下文"""
    mock_milvus = Mock(spec=MilvusClient)
    mock_milvus.search = AsyncMock(return_value=[
        {"id": "skill1", "name": "click_element", "score": 0.9, "description": "Click", "category": "interaction"}
    ])
    selector = SkillSelector(milvus_client=mock_milvus)

    message = "test"
    context = {"has_screenshot": False}
    skills = await selector.select(message, context=context)

    # 分数应该保持不变
    assert skills[0]["score"] == 0.9

