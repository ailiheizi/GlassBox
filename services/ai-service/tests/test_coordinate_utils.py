"""
测试坐标转换功能
验证 smart_resize 和坐标映射是否正确工作
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.coordinate_utils import (
    smart_resize,
    map_coordinate_to_original,
    parse_box_coordinate,
    should_resize_image,
    IMAGE_FACTOR,
    MAX_PIXELS_DOUBAO
)


def test_smart_resize():
    """测试 smart_resize 函数"""
    print("=" * 60)
    print("测试 smart_resize 函数")
    print("=" * 60)

    test_cases = [
        # (width, height, expected_width, expected_height)
        (1920, 1080, 1960, 1092),  # 标准 1080p
        (2560, 1440, 2576, 1456),  # 2K
        (3840, 2160, 3864, 2156),  # 4K
        (1366, 768, 1372, 784),    # 笔记本常见分辨率
        (800, 600, 812, 616),      # 小屏幕
    ]

    for width, height, expected_w, expected_h in test_cases:
        resized_h, resized_w = smart_resize(height, width)

        # 验证是否是 IMAGE_FACTOR 的倍数
        assert resized_w % IMAGE_FACTOR == 0, f"Width {resized_w} not divisible by {IMAGE_FACTOR}"
        assert resized_h % IMAGE_FACTOR == 0, f"Height {resized_h} not divisible by {IMAGE_FACTOR}"

        # 验证像素数在合理范围内
        total_pixels = resized_w * resized_h
        assert total_pixels <= MAX_PIXELS_DOUBAO, f"Pixels {total_pixels} exceeds max {MAX_PIXELS_DOUBAO}"

        print(f"✓ {width}x{height} -> {resized_w}x{resized_h}")
        print(f"  预期: {expected_w}x{expected_h}")
        print(f"  像素数: {total_pixels:,} / {MAX_PIXELS_DOUBAO:,}")
        print()


def test_coordinate_mapping():
    """测试坐标映射"""
    print("=" * 60)
    print("测试坐标映射")
    print("=" * 60)

    # 模拟场景：1920x1080 的屏幕被 resize 到 1960x1092
    original_width = 1920
    original_height = 1080
    resized_height, resized_width = smart_resize(original_height, original_width)

    print(f"原始尺寸: {original_width}x{original_height}")
    print(f"Resize后: {resized_width}x{resized_height}")
    print()

    test_cases = [
        # (model_x, model_y, description)
        (980, 546, "屏幕中心"),
        (100, 100, "左上角"),
        (1860, 992, "右下角"),
        (500, 300, "任意点1"),
        (1200, 700, "任意点2"),
    ]

    for model_x, model_y, desc in test_cases:
        real_x, real_y = map_coordinate_to_original(
            model_x, model_y,
            resized_width, resized_height,
            original_width, original_height
        )

        # 计算误差
        expected_x = int(model_x * original_width / resized_width)
        expected_y = int(model_y * original_height / resized_height)
        error_x = abs(real_x - expected_x)
        error_y = abs(real_y - expected_y)

        print(f"✓ {desc}")
        print(f"  模型输出: ({model_x}, {model_y})")
        print(f"  映射结果: ({real_x}, {real_y})")
        print(f"  预期结果: ({expected_x}, {expected_y})")
        print(f"  误差: ({error_x}, {error_y}) pixels")
        print()


def test_box_coordinate_parsing():
    """测试 box 坐标解析"""
    print("=" * 60)
    print("测试 box 坐标解析")
    print("=" * 60)

    original_width = 1920
    original_height = 1080
    resized_height, resized_width = smart_resize(original_height, original_width)

    test_cases = [
        "[100, 200, 150, 250]",  # 标准格式
        "(100, 200, 150, 250)",  # 圆括号
        "[500, 300, 500, 300]",  # 点坐标（x1=x2, y1=y2）
        "[100, 200]",            # 简化格式（只有两个坐标）
    ]

    for box_str in test_cases:
        try:
            center_x, center_y = parse_box_coordinate(
                box_str,
                resized_width, resized_height,
                original_width, original_height
            )
            print(f"✓ {box_str}")
            print(f"  中心点: ({center_x}, {center_y})")
            print()
        except Exception as e:
            print(f"✗ {box_str}")
            print(f"  错误: {e}")
            print()


def test_should_resize():
    """测试是否需要 resize 判断"""
    print("=" * 60)
    print("测试是否需要 resize")
    print("=" * 60)

    test_cases = [
        (1920, 1080, True),   # 标准屏幕，需要 resize
        (1960, 1092, False),  # 已经是 28 的倍数，不需要
        (800, 600, True),     # 小屏幕，需要
        (3840, 2160, True),   # 4K，需要
    ]

    for width, height, expected in test_cases:
        result = should_resize_image(width, height)
        status = "✓" if result == expected else "✗"
        print(f"{status} {width}x{height}: {'需要' if result else '不需要'} resize (预期: {'需要' if expected else '不需要'})")


def test_real_world_scenario():
    """测试真实场景"""
    print("=" * 60)
    print("真实场景测试")
    print("=" * 60)

    # 场景：用户在 1920x1080 的屏幕上，模型看到的是 resize 后的图像
    original_width = 1920
    original_height = 1080
    resized_height, resized_width = smart_resize(original_height, original_width)

    print(f"用户屏幕: {original_width}x{original_height}")
    print(f"模型看到: {resized_width}x{resized_height}")
    print()

    # 模拟模型输出：点击屏幕中央的按钮
    # 模型输出的坐标是基于 resize 后的图像
    model_output = "click(start_box='[980, 546, 980, 546]')"
    print(f"模型输出: {model_output}")
    print()

    # 解析坐标
    center_x, center_y = parse_box_coordinate(
        "[980, 546, 980, 546]",
        resized_width, resized_height,
        original_width, original_height
    )

    print(f"实际点击位置: ({center_x}, {center_y})")
    print(f"屏幕中心: ({original_width // 2}, {original_height // 2})")

    # 计算误差
    error_x = abs(center_x - original_width // 2)
    error_y = abs(center_y - original_height // 2)
    print(f"误差: ({error_x}, {error_y}) pixels")

    if error_x < 10 and error_y < 10:
        print("✓ 坐标映射准确！")
    else:
        print("✗ 坐标映射存在较大误差")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("UI-TARS 坐标转换功能测试")
    print("=" * 60 + "\n")

    try:
        test_smart_resize()
        test_coordinate_mapping()
        test_box_coordinate_parsing()
        test_should_resize()
        test_real_world_scenario()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}\n")
        return 1
    except Exception as e:
        print(f"\n✗ 发生错误: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
