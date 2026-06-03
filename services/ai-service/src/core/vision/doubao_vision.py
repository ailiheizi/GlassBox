from typing import Optional, Tuple
from openai import AsyncOpenAI
import re
import logging
import os

logger = logging.getLogger(__name__)


class DoubaoVision:
    """豆包视觉分析"""

    def __init__(self, api_key: str, api_base: str = None, model: str = None):
        self.api_key = api_key
        self.api_base = api_base or "https://ark.cn-beijing.volces.com/api/v3"
        self.model = model or os.getenv(
            "DOUBAO_VISION_MODEL",
            "doubao-1-5-thinking-vision-pro-250428"
        )

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=60.0
        )

    async def analyze_screenshot(
        self,
        screenshot_base64: str,
        instruction: str
    ) -> Optional[Tuple[int, int]]:
        """分析截图并返回操作坐标

        Args:
            screenshot_base64: 截图的 base64 编码
            instruction: 操作指令（如"点击登录按钮"）

        Returns:
            (x, y) 坐标元组，如果无法找到则返回 None
        """
        try:
            prompt = f"""请分析这个截图，找到 '{instruction}' 的位置。

要求：
1. 仔细观察截图中的所有元素
2. 找到与指令最匹配的元素
3. 返回该元素中心点的坐标

请以以下格式返回坐标：
坐标: (x, y)

如果找不到匹配的元素，请回复"未找到"。"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                max_tokens=500
            )

            content = response.choices[0].message.content
            logger.info(f"Vision analysis result: {content}")

            # 解析坐标
            coordinates = self._parse_coordinates(content)
            return coordinates

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return None

    def _parse_coordinates(self, text: str) -> Optional[Tuple[int, int]]:
        """从文本中解析坐标

        支持多种格式：
        - (100, 200)
        - x=100, y=200
        - 坐标: 100, 200
        - [100, 200]
        """
        if not text:
            return None

        # 尝试多种正则表达式模式
        patterns = [
            r'\((\d+),\s*(\d+)\)',           # (100, 200)
            r'x[=:]\s*(\d+).*?y[=:]\s*(\d+)', # x=100, y=200
            r'坐标[：:]\s*(\d+)[,，]\s*(\d+)', # 坐标: 100, 200
            r'\[(\d+),\s*(\d+)\]',           # [100, 200]
            r'(\d+)[,，]\s*(\d+)',           # 100, 200
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                logger.info(f"Parsed coordinates: ({x}, {y})")
                return (x, y)

        logger.warning(f"Could not parse coordinates from: {text}")
        return None

    async def describe_screenshot(self, screenshot_base64: str) -> str:
        """描述截图内容

        Args:
            screenshot_base64: 截图的 base64 编码

        Returns:
            截图描述文本
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "请详细描述这个截图中的内容，包括所有可见的UI元素、文本和布局。"
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Screenshot description failed: {e}")
            return None
