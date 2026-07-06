import os
import re
from PIL import Image
from PIL.ExifTags import TAGS

SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".ico"}

def read_image_text(file_path: str, lang: str = "chi_sim+eng") -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    _, ext = os.path.splitext(file_path)
    if ext.lower() not in SUPPORTED_FORMATS:
        return (f"[WARNING] 文件格式 ({ext}) 不在常用图片格式列表中，"
                f"仍将尝试识别...")

    result = _ocr_with_pytesseract(file_path, lang)
    if result is not None:
        return result

    result = _ocr_with_paddleocr(file_path, lang)
    if result is not None:
        return result

    return (
        "[ERROR] 未检测到可用的 OCR 引擎。\n\n"
        "请选择以下方式之一安装：\n\n"
        "【方案一：pytesseract（推荐，经典稳定）】\n"
        "  1. pip install pytesseract\n"
        "  2. 安装 Tesseract OCR 引擎：\n"
        "     - Windows: 下载 https://github.com/UB-Mannheim/tesseract/wiki\n"
        "     - macOS: brew install tesseract\n"
        "     - Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim\n\n"
        "【方案二：PaddleOCR（纯Python，中文效果好）】\n"
        "  pip install paddlepaddle paddleocr\n"
        "  安装后无需额外配置即可使用。"
    )


def _ocr_with_pytesseract(file_path: str, lang: str) -> str | None:
    try:
        import pytesseract
    except ImportError:
        return None

    try:
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            return None

        img = Image.open(file_path)

        img = img.convert("L")

        custom_config = r'--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img, lang=lang, config=custom_config)

        detail_data = pytesseract.image_to_data(img, lang=lang, config=custom_config, output_type=pytesseract.Output.DICT)

        img.close()

        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if not lines:
            return f"⚠️ 未能从图片中识别出文字。可能原因：图片中无文字、文字过于模糊、或需要添加对应语言包。\n当前识别语言: {lang}"

        total_words = sum(len(line) for line in lines)
        conf_values = [int(detail_data["conf"][i]) for i in range(len(detail_data["conf"]))
                       if detail_data["conf"][i] != "-1" and detail_data["text"][i].strip()]
        avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0

        output = [
            f"━━━ OCR 识别结果 ━━━",
            f"文件: {os.path.basename(file_path)}",
            f"识别语言: {lang}",
            f"识别引擎: pytesseract",
            f"识别文本行数: {len(lines)}",
            f"总字符数: {total_words}",
            f"平均置信度: {avg_conf:.1f}%" if conf_values else "",
            "",
            "────── 识别文字内容 ──────",
        ]
        output.extend(lines)

        number_lines = [l for l in lines if re.search(r'\d+', l)]
        if number_lines:
            output.append("")
            output.append("📊 检测到包含数字的行（可能是表格/数据）：")
            for nl in number_lines[:10]:
                output.append(f"  • {nl}")
            if len(number_lines) > 10:
                output.append(f"  ... 还有 {len(number_lines) - 10} 行")

        return "\n".join(output)

    except Exception as e:
        return f"[ERROR] pytesseract OCR 识别失败: {str(e)}"


def _ocr_with_paddleocr(file_path: str, lang: str) -> str | None:
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        return None

    try:
        paddle_lang = "ch"
        if lang == "eng":
            paddle_lang = "en"
        elif "chi" in lang:
            paddle_lang = "ch"
        elif "jap" in lang or "ja" in lang:
            paddle_lang = "japan"

        ocr = PaddleOCR(use_angle_cls=True, lang=paddle_lang)
        result = ocr.ocr(file_path, cls=True)

        if not result or not result[0]:
            return f"⚠️ 未能从图片中识别出文字（PaddleOCR）。"

        lines = []
        total_conf = 0
        conf_count = 0

        for line in result[0]:
            bbox = line[0]
            text = line[1][0]
            confidence = line[1][1]

            lines.append(text)
            total_conf += confidence
            conf_count += 1

        avg_conf = (total_conf / conf_count * 100) if conf_count else 0

        output = [
            f"━━━ OCR 识别结果 ━━━",
            f"文件: {os.path.basename(file_path)}",
            f"识别语言: {lang} (PaddleOCR: {paddle_lang})",
            f"识别引擎: PaddleOCR",
            f"识别文本行数: {len(lines)}",
            f"总字符数: {sum(len(l) for l in lines)}",
            f"平均置信度: {avg_conf:.1f}%",
            "",
            "────── 识别文字内容 ──────",
        ]
        output.extend(lines)

        number_lines = [l for l in lines if re.search(r'\d+', l)]
        if number_lines:
            output.append("")
            output.append("📊 检测到包含数字的行（可能是表格/数据）：")
            for nl in number_lines[:10]:
                output.append(f"  • {nl}")
            if len(number_lines) > 10:
                output.append(f"  ... 还有 {len(number_lines) - 10} 行")

        return "\n".join(output)

    except Exception as e:
        return f"[ERROR] PaddleOCR 识别失败: {str(e)}"

COLOR_MODE_MAP = {
    "1": "二值图",
    "L": "灰度图",
    "P": "调色板图",
    "RGB": "RGB 真彩色",
    "RGBA": "RGBA 真彩色（带透明度）",
    "CMYK": "CMYK 四色",
    "YCbCr": "YCbCr 色彩空间",
    "LAB": "Lab 色彩空间",
    "HSV": "HSV 色彩空间",
    "I": "32位整数灰度",
    "F": "32位浮点灰度",
}


def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def read_image_info(file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        file_size = os.path.getsize(file_path)
        file_size_str = _format_file_size(file_size)
    except Exception as e:
        file_size_str = f"获取失败: {str(e)}"

    try:
        img = Image.open(file_path)

        info_lines = [
            f"━━━ 图片基本信息 ━━━",
            f"文件路径: {file_path}",
            f"文件大小: {file_size_str}",
            f"图片格式: {img.format or '未知'}",
            f"尺寸: {img.width} × {img.height} 像素",
        ]

        if img.height > 0:
            info_lines.append(f"宽高比: {img.width / img.height:.4f}")

        info_lines.append(f"颜色模式: {img.mode}")

        mode_desc = COLOR_MODE_MAP.get(img.mode)
        if mode_desc:
            info_lines.append(f"模式说明: {mode_desc}")

        if getattr(img, "is_animated", False):
            try:
                frames = getattr(img, "n_frames", 1)
                info_lines.append(f"GIF 帧数: {frames} 帧（动态图片）")
            except Exception:
                pass

        try:
            exif_data = img._getexif()
            if exif_data is not None:
                exif_summary = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, "")
                    if tag_name in ("DateTimeOriginal", "Make", "Model", "ISOSpeedRatings",
                                    "FNumber", "ExposureTime", "FocalLength"):
                        if isinstance(value, bytes):
                            value = value.decode("utf-8", errors="ignore").strip()
                        exif_summary[tag_name] = str(value)
                if exif_summary:
                    info_lines.append("")
                    info_lines.append("📷 拍摄信息摘要：")
                    for k, v in exif_summary.items():
                            info_lines.append(f"  {k}: {v}")
        except Exception:
            pass

        img.close()
        return "\n".join(info_lines)

    except Exception as e:
        return f"[ERROR] 读取图片信息失败: {str(e)}"
