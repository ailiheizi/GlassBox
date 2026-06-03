"""
工具定义 - 注意：不包含user_id参数
"""
from typing import List, Dict, Any

# 导航工具
NAVIGATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "导航到指定URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要导航到的URL"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

# 交互工具
INTERACTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "点击页面元素",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS选择器或文本内容"
                    }
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "在输入框中输入文本",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "输入框的CSS选择器"
                    },
                    "text": {
                        "type": "string",
                        "description": "要输入的文本"
                    }
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_selector",
            "description": "等待元素出现",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS选择器"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时时间(毫秒)",
                        "default": 10000
                    }
                },
                "required": ["selector"]
            }
        }
    }
]

# 检查工具
INSPECTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_page_info",
            "description": "获取当前页面信息",
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
            "name": "screenshot",
            "description": "截取当前页面截图",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "是否截取整个页面",
                        "default": False
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_elements",
            "description": "根据文本查找元素",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要查找的文本"
                    }
                },
                "required": ["text"]
            }
        }
    }
]

# 滚动工具
SCROLL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "滚动页面",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                        "description": "滚动方向"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "滚动距离(像素)",
                        "default": 500
                    }
                },
                "required": ["direction"]
            }
        }
    }
]

# 记忆工具 - 注意：没有user_id参数，服务端会自动注入
MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "保存一条记忆",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "记忆内容"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "内容类型",
                        "default": "general"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "搜索记忆",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# 索引工具
INDEX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_index",
            "description": "搜索索引",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "service_name": {
                        "type": "string",
                        "description": "服务名称过滤"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_index",
            "description": "创建AI索引",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL"
                    },
                    "title": {
                        "type": "string",
                        "description": "标题"
                    },
                    "description": {
                        "type": "string",
                        "description": "描述"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS选择器"
                    }
                },
                "required": ["url", "title"]
            }
        }
    }
]


def get_all_tools() -> List[Dict[str, Any]]:
    """获取所有工具定义"""
    return (
        NAVIGATION_TOOLS +
        INTERACTION_TOOLS +
        INSPECTION_TOOLS +
        SCROLL_TOOLS +
        MEMORY_TOOLS +
        INDEX_TOOLS
    )


# 工具白名单
ALLOWED_TOOL_NAMES = {
    # 浏览器操作
    "navigate",
    "click",
    "type_text",
    "wait_for_selector",
    "get_page_info",
    "screenshot",
    "find_elements",
    "scroll",
    # 记忆操作
    "save_memory",
    "search_memory",
    # 索引操作
    "search_index",
    "create_index",
}
