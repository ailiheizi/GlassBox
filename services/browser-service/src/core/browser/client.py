"""
Playwright浏览器客户端
"""
import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ...config.settings import settings


class BrowserClient:
    """Playwright浏览器客户端"""

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def initialize(self) -> None:
        """初始化浏览器"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.browser_headless,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        # 创建上下文，设置伪装
        self._context = await self._browser.new_context(
            viewport={
                "width": settings.browser_viewport_width,
                "height": settings.browser_viewport_height,
            },
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )

        # 注入反检测脚本
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            window.chrome = { runtime: {} };
        """)

        self._page = await self._context.new_page()

    async def close(self) -> None:
        """关闭浏览器"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def navigate(self, url: str) -> Dict[str, Any]:
        """导航到URL"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        response = await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "status": response.status if response else None,
        }

    async def click(self, selector: str) -> Dict[str, Any]:
        """点击元素"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        try:
            # 尝试CSS选择器
            await self._page.click(selector, timeout=5000)
            return {"success": True, "message": "Clicked successfully"}
        except Exception:
            try:
                # 尝试文本选择器
                await self._page.click(f"text={selector}", timeout=5000)
                return {"success": True, "message": "Clicked by text"}
            except Exception as e:
                # 尝试JS点击
                try:
                    await self._page.evaluate(f"""
                        const el = document.querySelector('{selector}');
                        if (el) el.click();
                    """)
                    return {"success": True, "message": "Clicked via JS"}
                except Exception:
                    return {"success": False, "message": str(e)}

    async def type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """输入文本"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        try:
            await self._page.fill(selector, text, timeout=5000)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for_selector(self, selector: str, timeout: int = 10000) -> Dict[str, Any]:
        """等待元素"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_info(self) -> Dict[str, Any]:
        """获取页面信息"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        title = await self._page.title()
        url = self._page.url

        # 获取页面文本
        text = await self._page.evaluate("document.body.innerText")

        # 获取按钮
        buttons = await self._page.evaluate("""
            Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"]'))
                .slice(0, 20)
                .map(el => ({
                    text: el.innerText || el.value || '',
                    selector: el.id ? '#' + el.id : null
                }))
        """)

        # 获取输入框
        inputs = await self._page.evaluate("""
            Array.from(document.querySelectorAll('input, textarea'))
                .slice(0, 20)
                .map(el => ({
                    type: el.type,
                    name: el.name,
                    placeholder: el.placeholder,
                    selector: el.id ? '#' + el.id : null
                }))
        """)

        return {
            "title": title,
            "url": url,
            "text": text[:5000] if text else "",  # 限制长度
            "buttons": buttons,
            "inputs": inputs,
        }

    async def screenshot(self, full_page: bool = False) -> bytes:
        """截图"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        return await self._page.screenshot(full_page=full_page, type="png")

    async def find_elements_by_text(self, text: str) -> List[Dict[str, Any]]:
        """根据文本查找元素"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        elements = await self._page.evaluate(f"""
            Array.from(document.querySelectorAll('*'))
                .filter(el => el.innerText && el.innerText.includes('{text}'))
                .slice(0, 10)
                .map(el => ({{
                    tag: el.tagName.toLowerCase(),
                    text: el.innerText.slice(0, 100),
                    selector: el.id ? '#' + el.id : null
                }}))
        """)
        return elements

    async def scroll(self, direction: str, amount: int = 500) -> Dict[str, Any]:
        """滚动页面"""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        scroll_map = {
            "up": f"window.scrollBy(0, -{amount})",
            "down": f"window.scrollBy(0, {amount})",
            "left": f"window.scrollBy(-{amount}, 0)",
            "right": f"window.scrollBy({amount}, 0)",
        }

        if direction not in scroll_map:
            return {"success": False, "error": "Invalid direction"}

        await self._page.evaluate(scroll_map[direction])
        return {"success": True}
