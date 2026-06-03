"""
坐标处理工具
基于 UI-TARS 的坐标转换逻辑
"""
import math
from typing import Tuple, Optional

IMAGE_FACTOR = 28
MIN_PIXELS = 100 * IMAGE_FACTOR * IMAGE_FACTOR
MAX_PIXELS_DOUBAO = 5120 * IMAGE_FACTOR * IMAGE_FACTOR  # ~4M pixels
MAX_RATIO = 200


def smart_resize(
    height: int,
    width: int,
    factor: int = IMAGE_FACTOR,
    min_pixels: int = MIN_PIXELS,
    max_pixels: int = MAX_PIXELS_DOUBAO,
) -> Tuple[int, int]:
    """
    智能调整图像尺寸，确保：
    1. 宽高都是factor的倍数（默认28）
    2. 总像素数在[min_pixels, max_pixels]范围内
    3. 尽可能保持原始宽高比

    Args:
        height: 原始图像高度
        width: 原始图像宽度
        factor: 尺寸必须是此值的倍数
        min_pixels: 最小像素数
        max_pixels: 最大像素数

    Returns:
        (resized_height, resized_width): 调整后的尺寸

    Raises:
        ValueError: 如果宽高比超过MAX_RATIO
    """
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"宽高比必须小于 {MAX_RATIO}, 当前为 {max(height, width) / min(height, width)}"
        )

    # 四舍五入到factor的倍数
    w_bar = max(factor, round(width / factor) * factor)
    h_bar = max(factor, round(height / factor) * factor)

    # 如果超过最大像素，缩小
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = math.floor(height / beta / factor) * factor
        w_bar = math.floor(width / beta / factor) * factor
    # 如果小于最小像素，放大
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = math.ceil(height * beta / factor) * factor
        w_bar = math.ceil(width * beta / factor) * factor

    return h_bar, w_bar


def map_coordinate_to_original(
    model_x: float,
    model_y: float,
    resized_width: int,
    resized_height: int,
    original_width: int,
    original_height: int,
) -> Tuple[int, int]:
    """
    将模型输出的坐标映射回原始图像尺寸

    Args:
        model_x: 模型输出的x坐标
        model_y: 模型输出的y坐标
        resized_width: 发送给模型的图像宽度
        resized_height: 发送给模型的图像高度
        original_width: 原始截图宽度
        original_height: 原始截图高度

    Returns:
        (real_x, real_y): 映射到原始图像的坐标
    """
    real_x = int(model_x / resized_width * original_width)
    real_y = int(model_y / resized_height * original_height)
    return real_x, real_y


def parse_box_coordinate(
    box_str: str,
    resized_width: int,
    resized_height: int,
    original_width: int,
    original_height: int,
) -> Tuple[int, int]:
    """
    解析box坐标字符串并映射到原始尺寸

    Args:
        box_str: 格式如 "[x1, y1, x2, y2]" 或 "(x1, y1, x2, y2)"
        resized_width: resize后的宽度
        resized_height: resize后的高度
        original_width: 原始宽度
        original_height: 原始高度

    Returns:
        (center_x, center_y): box中心点在原始图像中的坐标

    Raises:
        ValueError: 如果box格式无效
    """
    # 移除括号并分割
    numbers = (
        box_str.replace("[", "")
        .replace("]", "")
        .replace("(", "")
        .replace(")", "")
        .split(",")
    )
    coords = [float(n.strip()) for n in numbers if n.strip()]

    if len(coords) == 2:
        # 如果只有两个坐标，直接使用
        x1, y1 = coords
        x2, y2 = x1, y1
    elif len(coords) == 4:
        x1, y1, x2, y2 = coords
    else:
        raise ValueError(f"Invalid box format: {box_str}, expected 2 or 4 numbers")

    # 计算中心点
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2

    # 映射到原始尺寸
    return map_coordinate_to_original(
        center_x,
        center_y,
        resized_width,
        resized_height,
        original_width,
        original_height,
    )


def should_resize_image(width: int, height: int, max_pixels: int = MAX_PIXELS_DOUBAO) -> bool:
    """
    判断图像是否需要resize

    Args:
        width: 图像宽度
        height: 图像高度
        max_pixels: 最大像素数

    Returns:
        True if resize is needed
    """
    resized_height, resized_width = smart_resize(height, width, max_pixels=max_pixels)
    return (resized_width, resized_height) != (width, height)
