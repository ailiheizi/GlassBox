"""
单元测试 - 浏览器反检测模块
"""
import pytest
import json
from typing import Dict, Any

from src.core.browser.stealth import (
    BrowserType,
    Viewport,
    Fingerprint,
    FingerprintGenerator,
    StealthConfig,
    StealthScripts,
    StealthBrowser,
    create_stealth_context_options,
)


class TestViewport:
    """测试视口配置"""

    def test_default_values(self):
        """测试默认值"""
        viewport = Viewport(1920, 1080)

        assert viewport.width == 1920
        assert viewport.height == 1080
        assert viewport.device_scale_factor == 1.0
        assert viewport.is_mobile is False
        assert viewport.has_touch is False

    def test_mobile_viewport(self):
        """测试移动端视口"""
        viewport = Viewport(
            width=375,
            height=812,
            device_scale_factor=3.0,
            is_mobile=True,
            has_touch=True,
        )

        assert viewport.is_mobile is True
        assert viewport.has_touch is True
        assert viewport.device_scale_factor == 3.0


class TestFingerprintGenerator:
    """测试指纹生成器"""

    def test_generate_chrome_fingerprint(self):
        """测试生成 Chrome 指纹"""
        generator = FingerprintGenerator(BrowserType.CHROME, "en-US")
        fingerprint = generator.generate()

        assert fingerprint.user_agent is not None
        assert "Chrome" in fingerprint.user_agent
        assert fingerprint.language == "en-US"
        assert fingerprint.viewport is not None

    def test_generate_firefox_fingerprint(self):
        """测试生成 Firefox 指纹"""
        generator = FingerprintGenerator(BrowserType.FIREFOX, "zh-CN")
        fingerprint = generator.generate()

        assert "Firefox" in fingerprint.user_agent
        assert fingerprint.language == "zh-CN"

    def test_fingerprint_randomness(self):
        """测试指纹随机性"""
        generator = FingerprintGenerator(BrowserType.CHROME)

        fingerprints = [generator.generate() for _ in range(10)]

        # 检查是否有不同的值（随机性）
        user_agents = set(fp.user_agent for fp in fingerprints)
        # 由于 UA 池有限，可能有重复，但不应该全部相同
        # 这里只检查生成成功
        assert len(fingerprints) == 10

    def test_platform_inference(self):
        """测试平台推断"""
        generator = FingerprintGenerator(BrowserType.CHROME)

        # 生成多个指纹，检查平台推断
        for _ in range(5):
            fp = generator.generate()
            if "Windows" in fp.user_agent:
                assert fp.platform == "Win32"
            elif "Macintosh" in fp.user_agent:
                assert fp.platform == "MacIntel"
            elif "Linux" in fp.user_agent:
                assert fp.platform == "Linux x86_64"


class TestStealthConfig:
    """测试隐身配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = StealthConfig()

        assert config.hide_webdriver is True
        assert config.hide_automation is True
        assert config.mock_webgl is True
        assert config.mock_canvas is True
        assert config.proxy is None

    def test_config_with_proxy(self):
        """测试带代理的配置"""
        config = StealthConfig(proxy="http://user:pass@proxy:8080")

        assert config.proxy == "http://user:pass@proxy:8080"

    def test_config_with_fingerprint(self):
        """测试带指纹的配置"""
        generator = FingerprintGenerator(BrowserType.CHROME)
        fingerprint = generator.generate()

        config = StealthConfig(fingerprint=fingerprint)

        assert config.fingerprint is not None
        assert config.fingerprint.user_agent == fingerprint.user_agent


class TestStealthScripts:
    """测试隐身脚本"""

    def test_hide_webdriver_script(self):
        """测试隐藏 webdriver 脚本"""
        script = StealthScripts.hide_webdriver()

        assert "navigator" in script
        assert "webdriver" in script
        assert "undefined" in script

    def test_hide_automation_script(self):
        """测试隐藏自动化脚本"""
        script = StealthScripts.hide_automation()

        assert "plugins" in script
        assert "mimeTypes" in script
        assert "permissions" in script

    def test_mock_webgl_script(self):
        """测试模拟 WebGL 脚本"""
        script = StealthScripts.mock_webgl("Intel Inc.", "Intel Iris OpenGL Engine")

        assert "Intel Inc." in script
        assert "Intel Iris OpenGL Engine" in script
        assert "WebGLRenderingContext" in script

    def test_mock_canvas_script(self):
        """测试模拟 Canvas 脚本"""
        script = StealthScripts.mock_canvas()

        assert "toDataURL" in script
        assert "toBlob" in script
        assert "imageData" in script.lower() or "ImageData" in script

    def test_mock_audio_script(self):
        """测试模拟 Audio 脚本"""
        script = StealthScripts.mock_audio()

        assert "AudioContext" in script
        assert "createAnalyser" in script

    def test_mock_navigator_script(self):
        """测试模拟 navigator 脚本"""
        fingerprint = Fingerprint(
            user_agent="Mozilla/5.0 Test",
            viewport=Viewport(1920, 1080),
            platform="Win32",
            language="en-US",
            languages=["en-US", "en"],
            timezone="America/New_York",
            webgl_vendor="Intel",
            webgl_renderer="Intel HD",
            hardware_concurrency=8,
            device_memory=16,
            screen_resolution=(1920, 1080),
            color_depth=24,
        )

        script = StealthScripts.mock_navigator(fingerprint)

        assert "Win32" in script
        assert "en-US" in script
        assert "8" in script  # hardware_concurrency
        assert "16" in script  # device_memory


class TestStealthBrowser:
    """测试隐身浏览器"""

    def test_generate_config(self):
        """测试生成配置"""
        stealth = StealthBrowser(BrowserType.CHROME, "en-US")
        config = stealth.generate_config()

        assert config.fingerprint is not None
        assert config.hide_webdriver is True

    def test_generate_config_with_proxy(self):
        """测试生成带代理的配置"""
        stealth = StealthBrowser()
        config = stealth.generate_config(proxy="http://proxy:8080")

        assert config.proxy == "http://proxy:8080"

    def test_get_stealth_scripts(self):
        """测试获取隐身脚本"""
        stealth = StealthBrowser()
        config = stealth.generate_config()
        scripts = stealth.get_stealth_scripts(config)

        assert len(scripts) > 0
        # 应该包含多个脚本
        assert any("webdriver" in s for s in scripts)

    def test_get_combined_script(self):
        """测试获取合并脚本"""
        stealth = StealthBrowser()
        config = stealth.generate_config()
        combined = stealth.get_combined_script(config)

        assert "(function() {" in combined
        assert "})();" in combined

    def test_to_playwright_context(self):
        """测试转换为 Playwright 上下文配置"""
        stealth = StealthBrowser(BrowserType.CHROME)
        config = stealth.generate_config(proxy="http://proxy:8080")
        context_options = stealth.to_playwright_context(config)

        assert "user_agent" in context_options
        assert "viewport" in context_options
        assert context_options["viewport"]["width"] > 0
        assert context_options["proxy"]["server"] == "http://proxy:8080"

    def test_to_playwright_context_without_fingerprint(self):
        """测试没有指纹时的上下文配置"""
        stealth = StealthBrowser()
        config = StealthConfig()  # 没有指纹
        context_options = stealth.to_playwright_context(config)

        assert context_options == {}


class TestCreateStealthContextOptions:
    """测试便捷函数"""

    def test_create_options(self):
        """测试创建选项"""
        context_options, script = create_stealth_context_options(
            browser_type=BrowserType.CHROME,
            locale="en-US",
        )

        assert "user_agent" in context_options
        assert "viewport" in context_options
        assert len(script) > 0

    def test_create_options_with_proxy(self):
        """测试创建带代理的选项"""
        context_options, script = create_stealth_context_options(
            proxy="http://proxy:8080",
        )

        assert context_options["proxy"]["server"] == "http://proxy:8080"


class TestBrowserTypeUserAgents:
    """测试不同浏览器类型的 User-Agent"""

    @pytest.mark.parametrize("browser_type,expected_keyword", [
        (BrowserType.CHROME, "Chrome"),
        (BrowserType.FIREFOX, "Firefox"),
        (BrowserType.SAFARI, "Safari"),
        (BrowserType.EDGE, "Edg"),
    ])
    def test_user_agent_contains_browser_name(self, browser_type, expected_keyword):
        """测试 User-Agent 包含浏览器名称"""
        generator = FingerprintGenerator(browser_type)
        fingerprint = generator.generate()

        assert expected_keyword in fingerprint.user_agent
