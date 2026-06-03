#!/usr/bin/env python3
"""
UI-TARS 改进验证脚本
快速检查配置和测试功能
"""
import os
import sys
import asyncio
import json
from typing import Dict, Any

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def check_environment():
    """检查环境变量配置"""
    print_header("环境变量检查")

    required_vars = {
        "DOUBAO_API_KEY": "火山引擎 API Key（必须）",
        "DEEPSEEK_API_KEY": "DeepSeek API Key（可选，用于代码生成）",
    }

    optional_vars = {
        "DOUBAO_MODEL": "豆包模型名称",
        "DOUBAO_BASE_URL": "豆包 API 地址",
        "SANDBOX_SECRET": "沙箱签名密钥",
    }

    all_ok = True

    # 检查必需变量
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else value
            print_success(f"{desc}: {masked}")
        else:
            print_error(f"{desc}: 未配置")
            all_ok = False

    # 检查可选变量
    print()
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            print_success(f"{desc}: {value}")
        else:
            print_warning(f"{desc}: 未配置（使用默认值）")

    return all_ok


def check_files():
    """检查必需文件是否存在"""
    print_header("文件完整性检查")

    required_files = [
        ("src/utils/coordinate_utils.py", "坐标处理工具"),
        ("src/core/model_router.py", "模型路由器"),
        ("src/core/multi_model_llm.py", "多模型客户端"),
        ("src/api/smart_sandbox_routes.py", "智能路由 API"),
        ("src/core/sandbox.py", "沙箱客户端"),
    ]

    all_ok = True
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for file_path, desc in required_files:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            print_success(f"{desc}: {file_path} ({size} bytes)")
        else:
            print_error(f"{desc}: {file_path} 不存在")
            all_ok = False

    return all_ok


async def test_coordinate_utils():
    """测试坐标转换功能"""
    print_header("坐标转换功能测试")

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from utils.coordinate_utils import smart_resize, map_coordinate_to_original

        # 测试 smart_resize
        test_cases = [
            (1920, 1080, "1080p"),
            (2560, 1440, "2K"),
            (3840, 2160, "4K"),
        ]

        for width, height, name in test_cases:
            resized_h, resized_w = smart_resize(height, width)
            print_success(f"{name} ({width}x{height}) → {resized_w}x{resized_h}")

        # 测试坐标映射
        print()
        print_info("测试坐标映射...")
        original_w, original_h = 1920, 1080
        resized_h, resized_w = smart_resize(original_h, original_w)

        model_x, model_y = 980, 546
        real_x, real_y = map_coordinate_to_original(
            model_x, model_y,
            resized_w, resized_h,
            original_w, original_h
        )

        print_success(f"模型坐标 ({model_x}, {model_y}) → 真实坐标 ({real_x}, {real_y})")

        # 验证准确性
        expected_x = int(model_x * original_w / resized_w)
        expected_y = int(model_y * original_h / resized_h)
        error_x = abs(real_x - expected_x)
        error_y = abs(real_y - expected_y)

        if error_x <= 1 and error_y <= 1:
            print_success(f"坐标映射准确！误差: ({error_x}, {error_y}) pixels")
            return True
        else:
            print_error(f"坐标映射误差过大: ({error_x}, {error_y}) pixels")
            return False

    except Exception as e:
        print_error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_model_router():
    """测试模型路由功能"""
    print_header("模型路由功能测试")

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from core.model_router import ModelRouter, TaskCategory

        router = ModelRouter()

        test_tasks = [
            ("请帮我点击屏幕上的提交按钮", TaskCategory.GUI_OPERATION),
            ("这个截图显示了什么内容？", TaskCategory.VISUAL_ANALYSIS),
            ("写一个 Python 函数计算斐波那契数列", TaskCategory.CODE_GENERATION),
            ("为什么这个程序会报错？", TaskCategory.REASONING),
            ("今天天气怎么样？", TaskCategory.GENERAL_CHAT),
        ]

        all_ok = True
        for task, expected_category in test_tasks:
            result = await router.select_model(task, use_llm_routing=False)

            if result["category"] == expected_category:
                print_success(f"✓ '{task[:30]}...'")
                print_info(f"  → 类别: {result['category']}, 模型: {result['model']}")
            else:
                print_warning(f"⚠ '{task[:30]}...'")
                print_info(f"  → 预期: {expected_category}, 实际: {result['category']}")
                all_ok = False

        return all_ok

    except Exception as e:
        print_error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_endpoints():
    """测试 API 端点"""
    print_header("API 端点测试")

    try:
        import httpx

        base_url = os.getenv("API_BASE_URL", "http://localhost:8086")

        endpoints = [
            ("GET", "/health", "健康检查"),
            ("GET", "/sandbox/smart/models", "模型列表"),
        ]

        all_ok = True
        async with httpx.AsyncClient(timeout=5.0) as client:
            for method, path, desc in endpoints:
                try:
                    url = f"{base_url}{path}"
                    if method == "GET":
                        response = await client.get(url)
                    else:
                        response = await client.post(url)

                    if response.status_code == 200:
                        print_success(f"{desc}: {method} {path}")
                    else:
                        print_warning(f"{desc}: {method} {path} (状态码: {response.status_code})")
                        all_ok = False

                except httpx.ConnectError:
                    print_error(f"{desc}: 无法连接到 {base_url}")
                    print_info("  提示: 请确保服务已启动")
                    all_ok = False
                except Exception as e:
                    print_error(f"{desc}: {str(e)}")
                    all_ok = False

        return all_ok

    except ImportError:
        print_warning("httpx 未安装，跳过 API 测试")
        print_info("  安装: pip install httpx")
        return True


def print_recommendations():
    """打印使用建议"""
    print_header("使用建议")

    print(f"{Colors.BOLD}推荐配置：{Colors.END}")
    print("1. ✅ 配置火山引擎 API Key（必须）")
    print("2. ✅ 配置 DeepSeek API Key（推荐，用于代码生成）")
    print("3. ✅ 使用智能路由接口: /sandbox/smart/chat/stream")
    print("4. ✅ 启用关键词路由（默认，快速且免费）")
    print()

    print(f"{Colors.BOLD}快速开始：{Colors.END}")
    print("1. 修改 .env 文件配置 API Key")
    print("2. 重启服务: docker-compose restart ai-service")
    print("3. 测试接口: curl http://localhost:8086/sandbox/smart/models")
    print()

    print(f"{Colors.BOLD}文档参考：{Colors.END}")
    print("• docs/IMPLEMENTATION_COMPLETE.md - 完整实施总结")
    print("• docs/smart-model-routing-guide.md - 智能路由使用指南")
    print("• docs/ui-tars-improvements-summary.md - 改进总结")
    print()


async def main():
    """主函数"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║          UI-TARS 改进验证工具 v1.0                        ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")

    results = {}

    # 1. 检查环境变量
    results['env'] = check_environment()

    # 2. 检查文件
    results['files'] = check_files()

    # 3. 测试坐标转换
    results['coordinate'] = await test_coordinate_utils()

    # 4. 测试模型路由
    results['router'] = await test_model_router()

    # 5. 测试 API（可选）
    if os.getenv("TEST_API", "false").lower() == "true":
        results['api'] = await test_api_endpoints()

    # 打印总结
    print_header("验证总结")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.END} - {name}")

    print()
    print(f"{Colors.BOLD}总计: {passed}/{total} 项通过{Colors.END}")

    if passed == total:
        print_success("\n🎉 所有检查通过！系统已准备就绪。")
        print_recommendations()
        return 0
    else:
        print_error(f"\n⚠️  {total - passed} 项检查失败，请查看上述错误信息。")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
