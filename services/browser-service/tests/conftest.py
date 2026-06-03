"""
pytest 配置文件
"""
import pytest
import sys
import os

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# pytest 配置
def pytest_configure(config):
    """pytest 配置"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )

