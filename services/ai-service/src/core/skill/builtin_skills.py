"""
内置技能定义
每个 skill 包含执行步骤和 BM25 匹配关键词
"""

from typing import List, Dict, Any


BUILTIN_SKILLS: List[Dict[str, Any]] = [
    {
        "skill_id": "open_browser",
        "name": "打开浏览器",
        "description": "打开 Chromium 浏览器，显示默认页面",
        "category": "browser",
        "steps": [
            {"tool": "sandbox_shell", "args": {"command": "chromium --no-sandbox &"}}
        ],
        "keywords": [
            "打开浏览器", "浏览器", "browser", "chromium", "chrome",
            "open browser", "启动浏览器", "上网",
        ],
    },
    {
        "skill_id": "open_feishu",
        "name": "打开飞书",
        "description": "打开 Chromium 浏览器并访问飞书网页版",
        "category": "browser",
        "steps": [
            {
                "tool": "sandbox_shell",
                "args": {"command": "chromium --no-sandbox https://www.feishu.cn &"},
            }
        ],
        "keywords": [
            "飞书", "feishu", "lark", "打开飞书", "open feishu",
            "飞书文档", "飞书会议",
        ],
    },
    {
        "skill_id": "open_url",
        "name": "打开网址",
        "description": "使用 Chromium 浏览器打开指定 URL",
        "category": "browser",
        "steps": [
            {
                "tool": "sandbox_shell",
                "args": {"command": "chromium --no-sandbox {url} &"},
            }
        ],
        "keywords": [
            "打开网址", "访问网站", "url", "网页", "open url",
            "open website", "visit", "navigate", "打开链接",
            "百度", "谷歌", "google", "baidu", "打开网页",
            "访问网页", "浏览网页", "指定网址", "指定网页",
        ],
    },
    {
        "skill_id": "install_apt",
        "name": "APT安装软件包",
        "description": "使用 apt-get 安装系统软件包",
        "category": "system",
        "steps": [
            {
                "tool": "sandbox_shell",
                "args": {"command": "apt-get update && apt-get install -y {package}"},
            }
        ],
        "keywords": [
            "安装", "apt", "install", "软件包", "package",
            "apt-get", "系统安装", "安装软件",
        ],
    },
    {
        "skill_id": "install_pip",
        "name": "pip安装Python包",
        "description": "使用 pip 安装 Python 包",
        "category": "development",
        "steps": [
            {
                "tool": "sandbox_shell",
                "args": {"command": "pip install {package}"},
            }
        ],
        "keywords": [
            "pip", "python", "安装python", "pip install",
            "python包", "python package", "安装库",
        ],
    },
    {
        "skill_id": "create_file",
        "name": "创建文件",
        "description": "在沙箱中创建指定内容的文件",
        "category": "file",
        "steps": [
            {
                "tool": "sandbox_bash_execute",
                "args": {"command": "cat > {filepath} << 'FILEEOF'\n{content}\nFILEEOF"},
            }
        ],
        "keywords": [
            "创建文件", "新建文件", "写文件", "create file",
            "write file", "new file", "保存文件",
        ],
    },
    {
        "skill_id": "take_screenshot",
        "name": "截图观察",
        "description": "截取当前桌面截图用于观察屏幕状态",
        "category": "observation",
        "steps": [
            {"tool": "sandbox_screenshot", "args": {}}
        ],
        "keywords": [
            "截图", "screenshot", "屏幕", "screen", "观察",
            "看看", "查看屏幕", "capture", "当前画面",
        ],
    },
]
