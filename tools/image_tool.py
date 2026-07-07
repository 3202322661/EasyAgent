"""
图片处理工具模块。

提供图片 OCR 文字识别和图片信息读取：
  - read_image_text: 识别图片中的文字（支持中英文）
  - read_image_info: 读取图片基本信息与 EXIF 数据

OCR 引擎支持：自动检测 pytesseract / PaddleOCR，优先使用 pytesseract。
"""

import logging
import os
import re
from typing import Optional

from PIL import Image
from PIL.ExifTags import TAGS

from tools._utils import format_file_size

logger = logging.getLogger(__name__)

# ────────────────────────── 常量 ──────────────────────────

SUPPORTED_IMAGE_FORMATS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".tif"
}

COLOR_MODE_DESCRIPTIONS: dict[str, str] = {
    "1":     "二值图（黑白）",
    "L":     "灰度图",
    "P":     "调色板图",
    "RGB":   "RGB 真彩色",
    "RGBA":  "RGBA 真彩色（带透明度）",
    "CMYK":  "CMYK 印刷四色",
    "YCbCr": "YCbCr 色彩空间",
    "LAB":   "Lab 色彩空间",
    "HSV":   "HSV 色彩空间",
    "I":     "32位整数灰度",
    "F":     "32位浮点灰度",
}

EXIF_FIELDS_OF_INTEREST = {
    "DateTimeOriginal", "Make", "Model", "ISOSpeedRatings",
    "FNumber", "ExposureTime", "FocalLength", "Flash",
    "GPSInfo", "Software", "Artist", "Copyright",
}


# ────────────────────────── OCR 引擎 ──────────────────────────

def _ocr_pytesseract(file_path: str, lang: str) -> Optional[str]:
    """使用 pytesseract 引擎进行 OCR 识别。"""
    try:
        import pytesseract
    except ImportError:
        return None

    try:
        # 检查 Tesseract 是否可用
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            return None

        img = Image.open(file_path)
        # 转为灰度图以提高识别率
        img_gray = img.convert("L")

        config = r'--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img_gray, lang=lang, config=config)
        detail = pytesseract.image_to_data(
            img_gray, lang=lang, config=config,
            output_type=pytesseract.Output.DICT,
        )

        img.close()

        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if not lines:
            return f"[INFO] 未能从图片中识别出文字。\n可能原因：图片无文字、文字模糊、或缺少语言包。\n当前识别语言: {lang}"

        total_chars = sum(len(line) for line in lines)

        # 计算平均置信度（安全处理字符串类型的置信度值）
        confidences: list[float] = []
        for i, conf_val in enumerate(detail.get("conf", [])):
            try:
                c = float(conf_val)
                if c >= 0 and i < len(detail.get("text", [])):
                    if detail["text"][i].strip():
                        confidences.append(c)
            except (ValueError, TypeError):
                pass

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        out: list[str] = [
            "=" * 50,
            f"OCR 识别结果",
            f"文件: {os.path.basename(file_path)}",
            f"引擎: pytesseract  |  语言: {lang}",
            f"识别行数: {len(lines)}  |  总字符数: {total_chars}",
        ]
        if confidences:
            out.append(f"平均置信度: {avg_conf:.1f}%")
        out.append("=" * 50)
        out.append("")
        out.extend(lines)

        # 标注含数字的行
        number_lines = [l for l in lines if re.search(r'\d', l)]
        if number_lines:
            out.append("")
            out.append(f"[含数字行: {len(number_lines)} 行]")
            for nl in number_lines[:10]:
                out.append(f"  - {nl}")
            if len(number_lines) > 10:
                out.append(f"  ... 另有 {len(number_lines) - 10} 行")

        return "\n".join(out)

    except Exception as e:
        logger.warning("pytesseract OCR 失败: %s", e)
        return None


def _ocr_paddleocr(file_path: str, lang: str) -> Optional[str]:
    """使用 PaddleOCR 引擎进行 OCR 识别。"""
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        return None

    try:
        # 语言映射
        paddle_lang = "ch"
        if lang == "eng":
            paddle_lang = "en"
        elif "jap" in lang or "ja" in lang:
            paddle_lang = "japan"
        elif "korean" in lang or "ko" in lang:
            paddle_lang = "korean"

        ocr = PaddleOCR(use_angle_cls=True, lang=paddle_lang)
        result = ocr.ocr(file_path, cls=True)

        if not result or not result[0]:
            return f"[INFO] 未能从图片中识别出文字（PaddleOCR）。"

        lines: list[str] = []
        confidences: list[float] = []

        for line_data in result[0]:
            text = line_data[1][0]
            confidence = line_data[1][1]
            lines.append(text)
            confidences.append(confidence)

        avg_conf = (sum(confidences) / len(confidences) * 100) if confidences else 0.0

        out: list[str] = [
            "=" * 50,
            f"OCR 识别结果",
            f"文件: {os.path.basename(file_path)}",
            f"引擎: PaddleOCR ({paddle_lang})  |  语言: {lang}",
            f"识别行数: {len(lines)}  |  总字符数: {sum(len(l) for l in lines)}",
        ]
        if confidences:
            out.append(f"平均置信度: {avg_conf:.1f}%")
        out.append("=" * 50)
        out.append("")
        out.extend(lines)

        # 标注含数字的行
        number_lines = [l for l in lines if re.search(r'\d', l)]
        if number_lines:
            out.append("")
            out.append(f"[含数字行: {len(number_lines)} 行]")
            for nl in number_lines[:10]:
                out.append(f"  - {nl}")
            if len(number_lines) > 10:
                out.append(f"  ... 另有 {len(number_lines) - 10} 行")

        return "\n".join(out)

    except Exception as e:
        logger.warning("PaddleOCR 识别失败: %s", e)
        return None


# ────────────────────────── 公开接口 ──────────────────────────

def read_image_text(file_path: str, lang: str = "chi_sim+eng") -> str:
    """识别图片中的文字内容（OCR）。

    自动检测可用 OCR 引擎，优先级: pytesseract > PaddleOCR。

    Args:
        file_path: 图片文件路径
        lang: OCR 语言代码，默认 'chi_sim+eng'（中英混合）

    Returns:
        识别结果文本
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    if not os.path.isfile(file_path):
        return f"[ERROR] '{file_path}' 不是一个文件。"

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_IMAGE_FORMATS:
        return (
            f"[WARNING] 文件格式 '{ext}' 可能不被支持，仍将尝试识别。\n"
            f"支持的格式: {', '.join(sorted(SUPPORTED_IMAGE_FORMATS))}"
        )

    # 尝试 pytesseract
    result = _ocr_pytesseract(file_path, lang)
    if result is not None:
        return result

    # 降级到 PaddleOCR
    result = _ocr_paddleocr(file_path, lang)
    if result is not None:
        return result

    # 两个引擎都不可用
    return (
        "[ERROR] 未检测到可用的 OCR 引擎。\n\n"
        "请安装以下任一方案:\n\n"
        "方案一 — pytesseract (推荐):\n"
        "  pip install pytesseract\n"
        "  然后安装 Tesseract OCR:\n"
        "    Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "    macOS:   brew install tesseract\n"
        "    Ubuntu:  sudo apt install tesseract-ocr tesseract-ocr-chi-sim\n\n"
        "方案二 — PaddleOCR (纯 Python，中文效果更好):\n"
        "  pip install paddlepaddle paddleocr\n"
    )


def read_image_info(file_path: str) -> str:
    """读取图片文件的基本信息。

    包含：文件大小、格式、尺寸、颜色模式、GIF 帧数、EXIF 拍摄信息。

    Args:
        file_path: 图片文件路径

    Returns:
        格式化的图片信息
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    # 文件大小
    try:
        file_size = os.path.getsize(file_path)
        size_str = format_file_size(file_size)
    except OSError as e:
        size_str = f"获取失败 ({e})"
        file_size = 0

    try:
        img = Image.open(file_path)

        info_lines: list[str] = [
            "=" * 50,
            f"图片基本信息",
            f"文件: {file_path}",
            f"大小: {size_str}",
            f"格式: {img.format or '未知'}",
            f"尺寸: {img.width} x {img.height} 像素",
        ]

        if img.height > 0:
            ratio = img.width / img.height
            info_lines.append(f"宽高比: {ratio:.4f} ({'横向' if ratio > 1 else '纵向' if ratio < 1 else '正方形'})")

        info_lines.append(f"颜色模式: {img.mode}")
        mode_desc = COLOR_MODE_DESCRIPTIONS.get(img.mode)
        if mode_desc:
            info_lines.append(f"模式说明: {mode_desc}")

        # GIF 动画信息
        if getattr(img, "is_animated", False):
            frames = getattr(img, "n_frames", 1)
            info_lines.append(f"动画帧数: {frames} 帧")

        # EXIF 信息
        try:
            exif_data = img._getexif()
            if exif_data:
                exif_summary: dict[str, str] = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, "")
                    if tag_name in EXIF_FIELDS_OF_INTEREST:
                        if isinstance(value, bytes):
                            value = value.decode("utf-8", errors="ignore").strip()
                        exif_summary[tag_name] = str(value)

                if exif_summary:
                    info_lines.append("")
                    info_lines.append("--- EXIF 拍摄信息 ---")
                    for k, v in exif_summary.items():
                        info_lines.append(f"  {k}: {v}")
        except Exception:
            pass  # EXIF 读取失败不影响整体

        img.close()
        return "\n".join(info_lines)

    except Exception as e:
        logger.exception("读取图片信息失败")
        return f"[ERROR] 读取图片信息失败: {e}"
