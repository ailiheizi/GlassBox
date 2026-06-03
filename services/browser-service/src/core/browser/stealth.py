"""
浏览器反检测模块 - 借鉴 Browser-Use 的 Stealth 设计

提供:
- 指纹伪装
- WebDriver 检测绕过
- Canvas/WebGL 指纹随机化
- User-Agent 轮换
- 代理支持
"""
import random
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BrowserType(Enum):
    """浏览器类型"""
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"


@dataclass
class Viewport:
    """视口配置"""
    width: int
    height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False


@dataclass
class Fingerprint:
    """浏览器指纹"""
    user_agent: str
    viewport: Viewport
    platform: str
    language: str
    languages: List[str]
    timezone: str
    webgl_vendor: str
    webgl_renderer: str
    hardware_concurrency: int
    device_memory: int
    screen_resolution: tuple
    color_depth: int


# 常用 User-Agent 池
USER_AGENTS = {
    BrowserType.CHROME: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ],
    BrowserType.FIREFOX: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ],
    BrowserType.SAFARI: [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ],
    BrowserType.EDGE: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ],
}

# 常用视口尺寸
VIEWPORTS = [
    Viewport(1920, 1080),
    Viewport(1366, 768),
    Viewport(1536, 864),
    Viewport(1440, 900),
    Viewport(1280, 720),
    Viewport(2560, 1440),
    Viewport(1680, 1050),
]

# WebGL 渲染器配置
WEBGL_CONFIGS = [
    {"vendor": "Intel Inc.", "renderer": "Intel Iris OpenGL Engine"},
    {"vendor": "Intel Inc.", "renderer": "Intel(R) UHD Graphics 630"},
    {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce GTX 1080/PCIe/SSE2"},
    {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 3080/PCIe/SSE2"},
    {"vendor": "AMD", "renderer": "AMD Radeon Pro 5500M OpenGL Engine"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)"},
]

# 时区列表
TIMEZONES = [
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "Europe/London",
    "Europe/Paris",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Singapore",
]


class FingerprintGenerator:
    """指纹生成器"""

    def __init__(
        self,
        browser_type: BrowserType = BrowserType.CHROME,
        locale: str = "en-US",
    ):
        self.browser_type = browser_type
        self.locale = locale

    def generate(self) -> Fingerprint:
        """生成随机指纹"""
        user_agent = random.choice(USER_AGENTS[self.browser_type])
        viewport = random.choice(VIEWPORTS)
        webgl = random.choice(WEBGL_CONFIGS)

        # 根据 User-Agent 推断平台
        if "Windows" in user_agent:
            platform = "Win32"
        elif "Macintosh" in user_agent:
            platform = "MacIntel"
        else:
            platform = "Linux x86_64"

        return Fingerprint(
            user_agent=user_agent,
            viewport=viewport,
            platform=platform,
            language=self.locale,
            languages=[self.locale, self.locale.split("-")[0]],
            timezone=random.choice(TIMEZONES),
            webgl_vendor=webgl["vendor"],
            webgl_renderer=webgl["renderer"],
            hardware_concurrency=random.choice([4, 8, 12, 16]),
            device_memory=random.choice([4, 8, 16, 32]),
            screen_resolution=(viewport.width, viewport.height),
            color_depth=24,
        )


@dataclass
class StealthConfig:
    """隐身配置"""
    # 基础配置
    fingerprint: Optional[Fingerprint] = None

    # 功能开关
    hide_webdriver: bool = True
    hide_automation: bool = True
    mock_permissions: bool = True
    mock_plugins: bool = True
    mock_languages: bool = True
    mock_webgl: bool = True
    mock_canvas: bool = True
    mock_audio: bool = True
    mock_fonts: bool = False  # 字体指纹较复杂，默认关闭

    # 代理配置
    proxy: Optional[str] = None  # 格式: http://user:pass@host:port

    # 高级配置
    extra_headers: Dict[str, str] = field(default_factory=dict)
    extra_args: List[str] = field(default_factory=list)


class StealthScripts:
    """隐身脚本集合"""

    @staticmethod
    def hide_webdriver() -> str:
        """隐藏 webdriver 标志"""
        return """
        // 删除 webdriver 属性
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // 删除 __webdriver_evaluate
        delete window.__webdriver_evaluate;
        delete window.__selenium_evaluate;
        delete window.__webdriver_script_function;
        delete window.__webdriver_script_func;
        delete window.__webdriver_script_fn;
        delete window.__fxdriver_evaluate;
        delete window.__driver_unwrapped;
        delete window.__webdriver_unwrapped;
        delete window.__driver_evaluate;
        delete window.__selenium_unwrapped;
        delete window.__fxdriver_unwrapped;

        // 删除 cdc_ 属性 (ChromeDriver)
        const cdcProps = Object.keys(window).filter(k => k.startsWith('cdc_'));
        cdcProps.forEach(prop => delete window[prop]);

        // 删除 $cdc_ 属性
        const $cdcProps = Object.keys(document).filter(k => k.startsWith('$cdc_'));
        $cdcProps.forEach(prop => delete document[prop]);
        """

    @staticmethod
    def hide_automation() -> str:
        """隐藏自动化标志"""
        return """
        // 修改 navigator.plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
                ];
                plugins.length = 3;
                return plugins;
            },
        });

        // 修改 navigator.mimeTypes
        Object.defineProperty(navigator, 'mimeTypes', {
            get: () => {
                const mimeTypes = [
                    { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                    { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                ];
                mimeTypes.length = 2;
                return mimeTypes;
            },
        });

        // 修改 navigator.permissions.query
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """

    @staticmethod
    def mock_webgl(vendor: str, renderer: str) -> str:
        """模拟 WebGL 指纹"""
        return f"""
        const getParameterProxyHandler = {{
            apply: function(target, thisArg, args) {{
                const param = args[0];
                const gl = thisArg;

                // UNMASKED_VENDOR_WEBGL
                if (param === 37445) {{
                    return '{vendor}';
                }}
                // UNMASKED_RENDERER_WEBGL
                if (param === 37446) {{
                    return '{renderer}';
                }}

                return Reflect.apply(target, thisArg, args);
            }}
        }};

        // 代理 WebGLRenderingContext
        const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = new Proxy(originalGetParameter, getParameterProxyHandler);

        // 代理 WebGL2RenderingContext
        if (typeof WebGL2RenderingContext !== 'undefined') {{
            const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = new Proxy(originalGetParameter2, getParameterProxyHandler);
        }}
        """

    @staticmethod
    def mock_canvas() -> str:
        """模拟 Canvas 指纹 (添加噪声)"""
        return """
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            if (type === 'image/png' || type === undefined) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    const data = imageData.data;

                    // 添加微小噪声
                    for (let i = 0; i < data.length; i += 4) {
                        // 只修改少量像素
                        if (Math.random() < 0.01) {
                            data[i] = data[i] ^ (Math.random() * 2 | 0);     // R
                            data[i+1] = data[i+1] ^ (Math.random() * 2 | 0); // G
                            data[i+2] = data[i+2] ^ (Math.random() * 2 | 0); // B
                        }
                    }

                    context.putImageData(imageData, 0, 0);
                }
            }
            return originalToDataURL.apply(this, arguments);
        };

        // 同样处理 toBlob
        const originalToBlob = HTMLCanvasElement.prototype.toBlob;
        HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
            if (type === 'image/png' || type === undefined) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    const data = imageData.data;

                    for (let i = 0; i < data.length; i += 4) {
                        if (Math.random() < 0.01) {
                            data[i] = data[i] ^ (Math.random() * 2 | 0);
                            data[i+1] = data[i+1] ^ (Math.random() * 2 | 0);
                            data[i+2] = data[i+2] ^ (Math.random() * 2 | 0);
                        }
                    }

                    context.putImageData(imageData, 0, 0);
                }
            }
            return originalToBlob.apply(this, arguments);
        };
        """

    @staticmethod
    def mock_audio() -> str:
        """模拟 AudioContext 指纹"""
        return """
        const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
        AudioContext.prototype.createAnalyser = function() {
            const analyser = originalCreateAnalyser.apply(this, arguments);
            const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;

            analyser.getFloatFrequencyData = function(array) {
                originalGetFloatFrequencyData.apply(this, arguments);
                // 添加微小噪声
                for (let i = 0; i < array.length; i++) {
                    array[i] = array[i] + (Math.random() * 0.0001 - 0.00005);
                }
            };

            return analyser;
        };
        """

    @staticmethod
    def mock_navigator(fingerprint: Fingerprint) -> str:
        """模拟 navigator 属性"""
        return f"""
        // 平台
        Object.defineProperty(navigator, 'platform', {{
            get: () => '{fingerprint.platform}',
        }});

        // 语言
        Object.defineProperty(navigator, 'language', {{
            get: () => '{fingerprint.language}',
        }});

        Object.defineProperty(navigator, 'languages', {{
            get: () => {json.dumps(fingerprint.languages)},
        }});

        // 硬件并发数
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: () => {fingerprint.hardware_concurrency},
        }});

        // 设备内存
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: () => {fingerprint.device_memory},
        }});

        // 屏幕分辨率
        Object.defineProperty(screen, 'width', {{
            get: () => {fingerprint.screen_resolution[0]},
        }});

        Object.defineProperty(screen, 'height', {{
            get: () => {fingerprint.screen_resolution[1]},
        }});

        Object.defineProperty(screen, 'availWidth', {{
            get: () => {fingerprint.screen_resolution[0]},
        }});

        Object.defineProperty(screen, 'availHeight', {{
            get: () => {fingerprint.screen_resolution[1] - 40},
        }});

        Object.defineProperty(screen, 'colorDepth', {{
            get: () => {fingerprint.color_depth},
        }});

        Object.defineProperty(screen, 'pixelDepth', {{
            get: () => {fingerprint.color_depth},
        }});
        """


class StealthBrowser:
    """
    隐身浏览器包装器

    用法:
        stealth = StealthBrowser()
        config = stealth.generate_config()

        # 使用 Playwright
        context = await browser.new_context(**config.to_playwright_context())
        await stealth.apply_scripts(context)
    """

    def __init__(
        self,
        browser_type: BrowserType = BrowserType.CHROME,
        locale: str = "en-US",
    ):
        self.browser_type = browser_type
        self.locale = locale
        self._fingerprint_generator = FingerprintGenerator(browser_type, locale)

    def generate_config(
        self,
        proxy: Optional[str] = None,
        **kwargs,
    ) -> StealthConfig:
        """生成隐身配置"""
        fingerprint = self._fingerprint_generator.generate()

        return StealthConfig(
            fingerprint=fingerprint,
            proxy=proxy,
            **kwargs,
        )

    def get_stealth_scripts(self, config: StealthConfig) -> List[str]:
        """获取隐身脚本列表"""
        scripts = []
        fp = config.fingerprint

        if config.hide_webdriver:
            scripts.append(StealthScripts.hide_webdriver())

        if config.hide_automation:
            scripts.append(StealthScripts.hide_automation())

        if config.mock_webgl and fp:
            scripts.append(StealthScripts.mock_webgl(fp.webgl_vendor, fp.webgl_renderer))

        if config.mock_canvas:
            scripts.append(StealthScripts.mock_canvas())

        if config.mock_audio:
            scripts.append(StealthScripts.mock_audio())

        if fp:
            scripts.append(StealthScripts.mock_navigator(fp))

        return scripts

    def get_combined_script(self, config: StealthConfig) -> str:
        """获取合并后的隐身脚本"""
        scripts = self.get_stealth_scripts(config)
        return "\n\n".join([
            "(function() {",
            *scripts,
            "})();",
        ])

    def to_playwright_context(self, config: StealthConfig) -> Dict[str, Any]:
        """转换为 Playwright context 配置"""
        fp = config.fingerprint
        if not fp:
            return {}

        context_options = {
            "user_agent": fp.user_agent,
            "viewport": {
                "width": fp.viewport.width,
                "height": fp.viewport.height,
            },
            "device_scale_factor": fp.viewport.device_scale_factor,
            "is_mobile": fp.viewport.is_mobile,
            "has_touch": fp.viewport.has_touch,
            "locale": fp.language,
            "timezone_id": fp.timezone,
            "color_scheme": "light",
        }

        if config.proxy:
            context_options["proxy"] = {"server": config.proxy}

        if config.extra_headers:
            context_options["extra_http_headers"] = config.extra_headers

        return context_options

    async def apply_to_context(self, context, config: StealthConfig) -> None:
        """
        将隐身脚本应用到 Playwright context

        Args:
            context: Playwright BrowserContext
            config: 隐身配置
        """
        script = self.get_combined_script(config)
        await context.add_init_script(script)
        logger.info("Applied stealth scripts to browser context")

    async def apply_to_page(self, page, config: StealthConfig) -> None:
        """
        将隐身脚本应用到 Playwright page

        Args:
            page: Playwright Page
            config: 隐身配置
        """
        script = self.get_combined_script(config)
        await page.add_init_script(script)
        logger.info("Applied stealth scripts to page")


# 便捷函数
def create_stealth_context_options(
    browser_type: BrowserType = BrowserType.CHROME,
    locale: str = "en-US",
    proxy: Optional[str] = None,
) -> tuple:
    """
    创建隐身浏览器上下文配置

    Returns:
        (context_options, stealth_script)
    """
    stealth = StealthBrowser(browser_type, locale)
    config = stealth.generate_config(proxy=proxy)

    return (
        stealth.to_playwright_context(config),
        stealth.get_combined_script(config),
    )
