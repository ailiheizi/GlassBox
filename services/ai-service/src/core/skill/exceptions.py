"""
Skill 系统异常定义
提供更具体的异常类型，便于错误处理
"""


class SkillSystemError(Exception):
    """Skill 系统基础异常"""
    pass


class SkillInitializationError(SkillSystemError):
    """Skill 系统初始化失败"""
    pass


class SkillNotFoundError(SkillSystemError):
    """技能未找到"""
    pass


class SkillRetrievalError(SkillSystemError):
    """技能检索失败"""
    pass


class MilvusConnectionError(SkillSystemError):
    """Milvus 连接失败"""
    pass


class EmbeddingGenerationError(SkillSystemError):
    """Embedding 生成失败"""
    pass
