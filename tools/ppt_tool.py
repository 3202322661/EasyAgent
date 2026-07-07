"""
PPT 演示文稿操作工具模块。

提供完整的 .pptx 创建、编辑和读取能力：
  读取: read_ppt_info, read_ppt_text
  创建: create_ppt, add_slide, add_title_slide, add_bullet_slide
  元素: add_textbox, add_shape, add_table_slide, add_image
  格式: set_slide_background
  管理: duplicate_slide, delete_slide, reorder_slides
"""

import logging
import os
import shutil
import tempfile
from typing import Any, List, Optional, Union

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

from tools._utils import parse_color as _parse_rgb, parse_alignment

logger = logging.getLogger(__name__)

# ────────────────────────── 常量映射 ──────────────────────────

ALIGN_MAP = {
    "left":    PP_ALIGN.LEFT,
    "center":  PP_ALIGN.CENTER,
    "right":   PP_ALIGN.RIGHT,
    "justify": PP_ALIGN.JUSTIFY,
}

LAYOUT_INDEX: dict[str, int] = {
    "title":           0,   # 标题幻灯片
    "title_content":   1,   # 标题和内容
    "section":         2,   # 节标题
    "two_content":     3,   # 两栏内容
    "blank":           6,   # 空白
    "content_caption": 8,   # 内容和标题
    "picture_caption": 10,  # 图片和标题
}

SHAPE_TYPE_MAP: dict[str, int] = {
    "rectangle":           MSO_SHAPE.RECTANGLE,
    "rounded_rectangle":   MSO_SHAPE.ROUNDED_RECTANGLE,
    "oval":                MSO_SHAPE.OVAL,
    "circle":              MSO_SHAPE.OVAL,
    "triangle":            MSO_SHAPE.ISOSCELES_TRIANGLE,
    "right_triangle":      MSO_SHAPE.RIGHT_TRIANGLE,
    "diamond":             MSO_SHAPE.DIAMOND,
    "pentagon":            MSO_SHAPE.PENTAGON,
    "hexagon":             MSO_SHAPE.HEXAGON,
    "arrow_right":         MSO_SHAPE.RIGHT_ARROW,
    "arrow_left":          MSO_SHAPE.LEFT_ARROW,
    "arrow_up":            MSO_SHAPE.UP_ARROW,
    "arrow_down":          MSO_SHAPE.DOWN_ARROW,
    "star":                MSO_SHAPE.STAR_5_POINT,
    "heart":               MSO_SHAPE.HEART,
    "cloud":               MSO_SHAPE.CLOUD,
    "sun":                 MSO_SHAPE.SUN,
    "moon":                MSO_SHAPE.MOON,
    "lightning":           MSO_SHAPE.LIGHTNING_BOLT,
    "cross":               MSO_SHAPE.CROSS,
    "cube":                MSO_SHAPE.CUBE,
    "chevron":             MSO_SHAPE.CHEVRON,
    "flowchart_process":   MSO_SHAPE.FLOWCHART_PROCESS,
    "flowchart_decision":  MSO_SHAPE.FLOWCHART_DECISION,
    "flowchart_data":      MSO_SHAPE.FLOWCHART_DATA,
    "flowchart_start":     MSO_SHAPE.FLOWCHART_TERMINATOR,
}


# ────────────────────────── 颜色解析（python-pptx 专用） ──────────────────────────

def _parse_pptx_color(color_val: Optional[str]) -> Optional[RGBColor]:
    """将颜色字符串解析为 python-pptx 的 RGBColor 对象。"""
    rgb = _parse_rgb(color_val)
    if rgb is None:
        return None
    return RGBColor(*rgb)


# ────────────────────────── 内部辅助 ──────────────────────────

def _safe_open_ppt(file_path: str) -> Presentation:
    """安全地打开或创建 PPT 文件。"""
    if os.path.exists(file_path):
        try:
            return Presentation(file_path)
        except Exception as e:
            logger.warning("打开 PPT '%s' 失败 (%s)，创建新文档。", file_path, e)
    return Presentation()


def _safe_save_ppt(prs: Presentation, file_path: str) -> bool:
    """防御性保存：先写临时文件再替换，防中断、防占用。"""
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".pptx")
        os.close(fd)
        prs.save(tmp_path)
        shutil.copy2(tmp_path, file_path)
        return True
    except PermissionError:
        logger.error("保存 PPT 失败：文件 '%s' 被占用。", file_path)
        return False
    except Exception as e:
        logger.error("保存 PPT 异常: %s", e)
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _resolve_slide_index(slides: Any, slide_index: int) -> int:
    """将用户传入的幻灯片索引（1-based 或 -1）解析为 0-based 索引。

    Returns:
        0-based 索引

    Raises:
        IndexError: 索引超出范围
    """
    n = len(slides)
    if slide_index == -1:
        return n - 1
    idx = slide_index - 1  # 1-based → 0-based
    if 0 <= idx < n:
        return idx
    raise IndexError(f"幻灯片索引 {slide_index} 超出范围 (1-{n})")


def _get_layout(prs: Presentation, layout_key: Union[str, int, None]) -> Any:
    """获取幻灯片布局。"""
    default = prs.slide_layouts[6]  # Blank

    if layout_key is None:
        return default

    if isinstance(layout_key, str):
        idx = LAYOUT_INDEX.get(layout_key.strip().lower().replace(" ", "_"))
        if idx is not None and idx < len(prs.slide_layouts):
            return prs.slide_layouts[idx]
        return default

    if isinstance(layout_key, int) and 0 <= layout_key < len(prs.slide_layouts):
        return prs.slide_layouts[layout_key]

    return default


def _set_text_format(text_frame: Any, text: Optional[str],
                     font_name: Optional[str] = None,
                     font_size: Optional[int] = None,
                     bold: Optional[bool] = None,
                     italic: Optional[bool] = None,
                     color: Optional[str] = None,
                     alignment: Optional[str] = None) -> None:
    """设置文本框的文本与格式。"""
    if text is None:
        return

    text_frame.text = str(text)
    if not text_frame.paragraphs:
        return

    para = text_frame.paragraphs[0]
    parsed_align = parse_alignment(alignment, ALIGN_MAP)
    if parsed_align is not None:
        para.alignment = parsed_align

    for run in para.runs:
        if font_name:
            run.font.name = font_name
        if font_size is not None:
            run.font.size = Pt(font_size)
        if bold is not None:
            run.font.bold = bold
        if italic is not None:
            run.font.italic = italic
        if color:
            parsed = _parse_pptx_color(color)
            if parsed:
                run.font.color.rgb = parsed


def _set_shape_fill(shape: Any, color: Optional[str] = None) -> None:
    """设置形状填充颜色。"""
    if not color:
        return
    parsed = _parse_pptx_color(color)
    if not parsed:
        return
    try:
        shape.fill.solid()
        shape.fill.fore_color.rgb = parsed
    except Exception:
        logger.debug("设置形状填充失败（某些形状不支持填充）")


def _set_shape_line(shape: Any, color: Optional[str] = None,
                    width: Optional[float] = None) -> None:
    """设置形状边框颜色与宽度。"""
    if color:
        parsed = _parse_pptx_color(color)
        if parsed:
            try:
                shape.line.color.rgb = parsed
            except Exception:
                pass
    if width is not None:
        try:
            shape.line.width = Pt(width)
        except Exception:
            pass


def _set_slide_bg(slide: Any, color: Optional[str]) -> None:
    """设置幻灯片背景颜色。"""
    parsed = _parse_pptx_color(color)
    if not parsed:
        return
    try:
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = parsed
    except Exception:
        logger.debug("设置幻灯片背景失败")


# ────────────────────────── 创建接口 ──────────────────────────

def create_ppt(file_path: str, title: Optional[str] = None) -> str:
    """创建新的空白 PPT 文件。

    Args:
        file_path: 保存路径 (.pptx)
        title: 可选的标题幻灯片文本

    Returns:
        操作结果
    """
    try:
        prs = Presentation()
        if title:
            slide_layout = prs.slide_layouts[0]  # Title Slide
            slide = prs.slides.add_slide(slide_layout)
            if slide.shapes.title:
                slide.shapes.title.text = title

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] PPT 文件已创建: '{file_path}'"
        return "[ERROR] 保存 PPT 文件失败，文件可能被占用。"
    except Exception as e:
        logger.exception("创建 PPT 失败")
        return f"[ERROR] 创建 PPT 失败: {e}"


def add_slide(file_path: str, layout: Union[str, int] = "blank",
              title: Optional[str] = None,
              content: Optional[str] = None) -> str:
    """向 PPT 添加新幻灯片。

    Args:
        file_path: PPT 文件路径
        layout: 布局名称或索引
        title: 幻灯片标题
        content: 幻灯片内容文本

    Returns:
        操作结果
    """
    try:
        prs = _safe_open_ppt(file_path)
        slide_layout = _get_layout(prs, layout)
        slide = prs.slides.add_slide(slide_layout)

        if title and slide.shapes.title:
            slide.shapes.title.text = title

        if content:
            for shape in slide.placeholders:
                if shape.placeholder_format.idx == 1:
                    shape.text = content
                    break

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 已添加幻灯片 (布局: {layout})，共 {len(prs.slides)} 张"
        return "[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        logger.exception("添加幻灯片失败")
        return f"[ERROR] 添加幻灯片失败: {e}"


def add_title_slide(file_path: str, title: str = "标题",
                    subtitle: Optional[str] = None,
                    title_color: Optional[str] = None,
                    subtitle_color: Optional[str] = None,
                    bg_color: Optional[str] = None) -> str:
    """添加标题幻灯片（封面页）。

    Args:
        file_path: PPT 文件路径
        title: 主标题
        subtitle: 副标题
        title_color: 标题颜色
        subtitle_color: 副标题颜色
        bg_color: 背景颜色

    Returns:
        操作结果
    """
    try:
        prs = _safe_open_ppt(file_path)
        slide = prs.slides.add_slide(prs.slide_layouts[0])

        if bg_color:
            _set_slide_bg(slide, bg_color)

        if slide.shapes.title:
            _set_text_format(slide.shapes.title.text_frame, title,
                             font_size=44, bold=True, color=title_color)

        if subtitle:
            for shape in slide.placeholders:
                if shape.placeholder_format.idx == 1:
                    _set_text_format(shape.text_frame, subtitle,
                                     font_size=24, color=subtitle_color)
                    break

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 标题幻灯片已添加，共 {len(prs.slides)} 张"
        return "[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        logger.exception("添加标题幻灯片失败")
        return f"[ERROR] 添加标题幻灯片失败: {e}"


def add_bullet_slide(file_path: str, title: str = "内容",
                     bullets: Optional[List[Any]] = None,
                     font_name: Optional[str] = None,
                     font_size: int = 18,
                     color: Optional[str] = None,
                     bg_color: Optional[str] = None) -> str:
    """添加带项目符号列表的内容幻灯片。

    Args:
        file_path: PPT 文件路径
        title: 幻灯片标题
        bullets: 项目符号文本列表
        font_name: 字体
        font_size: 字号
        color: 文字颜色
        bg_color: 背景颜色

    Returns:
        操作结果
    """
    if bullets is None:
        bullets = []

    try:
        prs = _safe_open_ppt(file_path)
        slide = prs.slides.add_slide(prs.slide_layouts[1])  # Title and Content

        if bg_color:
            _set_slide_bg(slide, bg_color)

        if slide.shapes.title:
            slide.shapes.title.text = title

        for shape in slide.placeholders:
            if shape.placeholder_format.idx == 1:
                tf = shape.text_frame
                tf.clear()

                for i, bullet_text in enumerate(bullets):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.text = str(bullet_text)
                    p.level = 0
                    for run in p.runs:
                        if font_name:
                            run.font.name = font_name
                        if font_size:
                            run.font.size = Pt(font_size)
                        parsed_color = _parse_pptx_color(color)
                        if parsed_color:
                            run.font.color.rgb = parsed_color
                break

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 项目符号幻灯片已添加 ({len(bullets)} 条要点)，共 {len(prs.slides)} 张"
        return "[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        logger.exception("添加项目符号幻灯片失败")
        return f"[ERROR] 添加项目符号幻灯片失败: {e}"


# ────────────────────────── 元素添加接口 ──────────────────────────

def add_textbox(file_path: str, text: str,
                slide_index: int = -1,
                left: float = 1.0, top: float = 1.0,
                width: float = 8.0, height: float = 1.5,
                font_name: Optional[str] = None,
                font_size: int = 18,
                bold: Optional[bool] = None,
                italic: Optional[bool] = None,
                color: Optional[str] = None,
                alignment: Optional[str] = None) -> str:
    """在指定幻灯片中添加文本框。

    Args:
        file_path: PPT 文件路径
        text: 文本内容
        slide_index: 幻灯片索引（1-based，-1 表示最后一张）
        left, top, width, height: 位置与尺寸（英寸）
        font_name, font_size, bold, italic, color, alignment: 字体格式

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        if not prs.slides:
            return "[ERROR] PPT 中没有幻灯片，请先添加幻灯片。"

        idx = _resolve_slide_index(prs.slides, slide_index)
        slide = prs.slides[idx]

        txBox = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height))
        txBox.text_frame.word_wrap = True
        _set_text_format(txBox.text_frame, text, font_name=font_name,
                         font_size=font_size, bold=bold, italic=italic,
                         color=color, alignment=alignment)

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 文本框已添加至第 {idx + 1} 张幻灯片"
        return "[ERROR] 保存 PPT 文件失败。"
    except IndexError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        logger.exception("添加文本框失败")
        return f"[ERROR] 添加文本框失败: {e}"


def add_shape(file_path: str,
              shape_type: str = "rectangle",
              slide_index: int = -1,
              left: float = 1.0, top: float = 1.0,
              width: float = 3.0, height: float = 2.0,
              fill_color: Optional[str] = None,
              line_color: Optional[str] = None,
              line_width: Optional[float] = None,
              text: Optional[str] = None,
              font_name: Optional[str] = None,
              font_size: Optional[int] = None,
              font_color: Optional[str] = None,
              bold: Optional[bool] = None,
              alignment: Optional[str] = None) -> str:
    """在指定幻灯片中添加形状。

    支持 20+ 种形状类型，包括矩形、圆形、箭头、星形、心形等。

    Args:
        file_path: PPT 文件路径
        shape_type: 形状类型名称
        slide_index: 幻灯片索引（1-based，-1 表示最后一张）
        left, top, width, height: 位置与尺寸（英寸）
        fill_color: 填充颜色
        line_color: 边框颜色
        line_width: 边框宽度（磅）
        text: 形状内文字
        font_name, font_size, font_color, bold, alignment: 文字格式

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        if not prs.slides:
            return "[ERROR] PPT 中没有幻灯片。"

        idx = _resolve_slide_index(prs.slides, slide_index)
        slide = prs.slides[idx]

        shape_enum = SHAPE_TYPE_MAP.get(
            shape_type.strip().lower().replace(" ", "_"),
            MSO_SHAPE.RECTANGLE,
        )

        shape_obj = slide.shapes.add_shape(
            shape_enum, Inches(left), Inches(top),
            Inches(width), Inches(height),
        )

        _set_shape_fill(shape_obj, color=fill_color)
        _set_shape_line(shape_obj, color=line_color, width=line_width)

        if text is not None and hasattr(shape_obj, 'text_frame'):
            _set_text_format(shape_obj.text_frame, text,
                             font_name=font_name, font_size=font_size,
                             bold=bold, color=font_color, alignment=alignment)

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 形状 ({shape_type}) 已添加至第 {idx + 1} 张幻灯片"
        return "[ERROR] 保存 PPT 文件失败。"
    except IndexError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        logger.exception("添加形状失败")
        return f"[ERROR] 添加形状失败: {e}"


def add_table_slide(file_path: str,
                    data: List[List[Any]],
                    slide_index: int = -1,
                    headers: Optional[List[Any]] = None,
                    left: float = 1.0, top: float = 2.0,
                    width: float = 8.0, height: Optional[float] = None,
                    font_name: Optional[str] = None,
                    font_size: int = 12,
                    header_color: Optional[str] = None,
                    header_bold: bool = True,
                    alignment: Optional[str] = None) -> str:
    """在指定幻灯片中添加表格。

    Args:
        file_path: PPT 文件路径
        data: 二维数据数组
        slide_index: 幻灯片索引
        headers: 表头列表
        left, top, width, height: 位置与尺寸（英寸）
        font_name, font_size: 字体格式
        header_color: 表头文字颜色
        header_bold: 表头是否加粗
        alignment: 文字对齐

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    if not data or not data[0]:
        return "[ERROR] 表格数据为空。"

    try:
        prs = Presentation(file_path)
        if not prs.slides:
            return "[ERROR] PPT 中没有幻灯片。"

        idx = _resolve_slide_index(prs.slides, slide_index)
        slide = prs.slides[idx]

        num_rows = len(data) + (1 if headers else 0)
        num_cols = len(data[0])

        if height is None:
            height = num_rows * 0.5

        table_shape = slide.shapes.add_table(
            num_rows, num_cols, Inches(left), Inches(top),
            Inches(width), Inches(height),
        )
        table = table_shape.table

        # 写表头
        start_row = 0
        if headers:
            for j, header_text in enumerate(headers):
                if j < num_cols:
                    _set_text_format(table.cell(0, j).text_frame,
                                     str(header_text), font_name=font_name,
                                     font_size=font_size, bold=header_bold,
                                     color=header_color, alignment=alignment)
            start_row = 1

        # 写数据
        for i, row_data in enumerate(data):
            for j, cell_text in enumerate(row_data):
                if j < num_cols:
                    _set_text_format(table.cell(start_row + i, j).text_frame,
                                     str(cell_text), font_name=font_name,
                                     font_size=font_size, alignment=alignment)

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 表格 ({num_rows}x{num_cols}) 已添加至第 {idx + 1} 张幻灯片"
        return "[ERROR] 保存 PPT 文件失败。"
    except IndexError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        logger.exception("添加表格失败")
        return f"[ERROR] 添加表格失败: {e}"


def add_image(file_path: str, image_path: str,
              slide_index: int = -1,
              left: float = 1.0, top: float = 1.0,
              width: Optional[float] = None,
              height: Optional[float] = None) -> str:
    """在指定幻灯片中添加图片。

    Args:
        file_path: PPT 文件路径
        image_path: 图片文件路径
        slide_index: 幻灯片索引
        left, top, width, height: 位置与尺寸（英寸）

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] PPT 文件 '{file_path}' 不存在。"
    if not os.path.exists(image_path):
        return f"[ERROR] 图片文件 '{image_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        if not prs.slides:
            return "[ERROR] PPT 中没有幻灯片。"

        idx = _resolve_slide_index(prs.slides, slide_index)
        slide = prs.slides[idx]

        kwargs = {}
        if width is not None:
            kwargs['width'] = Inches(width)
        if height is not None:
            kwargs['height'] = Inches(height)

        slide.shapes.add_picture(image_path, Inches(left), Inches(top), **kwargs)

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 图片已添加至第 {idx + 1} 张幻灯片"
        return "[ERROR] 保存 PPT 文件失败。"
    except IndexError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        logger.exception("添加图片失败")
        return f"[ERROR] 添加图片失败: {e}"


# ────────────────────────── 格式接口 ──────────────────────────

def set_slide_background(file_path: str, color: str,
                         slide_index: int = -1) -> str:
    """设置幻灯片背景颜色。

    Args:
        file_path: PPT 文件路径
        color: 背景颜色（名称或 #HEX）
        slide_index: 幻灯片索引（1-based，-1 表示全部幻灯片）

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)

        if slide_index == -1:
            targets = list(prs.slides)
        else:
            idx = _resolve_slide_index(prs.slides, slide_index)
            targets = [prs.slides[idx]]

        for slide in targets:
            _set_slide_bg(slide, color)

        if _safe_save_ppt(prs, file_path):
            desc = "所有幻灯片" if slide_index == -1 else f"第 {slide_index} 张幻灯片"
            return f"[SUCCESS] {desc} 背景色已设置"
        return "[ERROR] 保存 PPT 文件失败。"
    except IndexError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        logger.exception("设置背景失败")
        return f"[ERROR] 设置背景失败: {e}"


# ────────────────────────── 幻灯片管理接口 ──────────────────────────

def duplicate_slide(file_path: str, slide_index: int = 1) -> str:
    """复制指定幻灯片并追加到末尾。

    注意：由于 python-pptx 限制，图片等关系资源可能不会被完整复制。

    Args:
        file_path: PPT 文件路径
        slide_index: 要复制的幻灯片索引（1-based）

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        idx = _resolve_slide_index(prs.slides, slide_index)
        source = prs.slides[idx]

        # 创建同布局的新幻灯片并复制所有形状
        new_slide = prs.slides.add_slide(source.slide_layout)
        for shape in source.shapes:
            el = shape._element
            new_el = el.__deepcopy__(None)
            new_slide.shapes._spTree.append(new_el)

        if _safe_save_ppt(prs, file_path):
            return (
                f"[SUCCESS] 第 {slide_index} 张幻灯片已复制\n"
                f"注意：图片等关系资源可能未被完整复制。"
            )
        return "[ERROR] 保存 PPT 文件失败。"
    except IndexError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        logger.exception("复制幻灯片失败")
        return f"[ERROR] 复制幻灯片失败: {e}"


def delete_slide(file_path: str, slide_index: int = 1) -> str:
    """删除指定幻灯片。

    通过操作底层 XML 的 sldIdLst 实现真正的删除。

    Args:
        file_path: PPT 文件路径
        slide_index: 要删除的幻灯片索引（1-based）

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        if not prs.slides:
            return "[ERROR] PPT 中没有幻灯片可删除。"

        idx = _resolve_slide_index(prs.slides, slide_index)
        slide_to_delete = prs.slides[idx]
        target_part = slide_to_delete.part

        # 从 presentation part 的 rels 查找目标 slide 对应的 rId
        target_rId: Optional[str] = None
        for rel_id, rel in prs.part.rels.items():
            if rel.target_part == target_part:
                target_rId = rel_id
                break

        if target_rId is None:
            return f"[ERROR] 无法定位幻灯片 {slide_index} 的关系引用。"

        # 从 sldIdLst 中移除对应条目
        sldIdLst = prs.presentation.sldIdLst
        removed = False
        for sldId_elem in list(sldIdLst):
            if sldId_elem.get(qn('r:id')) == target_rId:
                sldIdLst.remove(sldId_elem)
                removed = True
                break

        if not removed:
            return f"[ERROR] 在 sldIdLst 中未找到幻灯片 {slide_index} 的条目。"

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 第 {slide_index} 张幻灯片已删除"
        return "[ERROR] 保存 PPT 文件失败。"
    except IndexError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        logger.exception("删除幻灯片失败")
        return f"[ERROR] 删除幻灯片失败: {e}"


def reorder_slides(file_path: str, new_order: List[int]) -> str:
    """重新排列幻灯片顺序。

    Args:
        file_path: PPT 文件路径
        new_order: 新顺序列表，如 [3, 1, 2]，必须包含 1 到 N 的所有整数

    Returns:
        操作结果
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        n = len(prs.slides)

        if not new_order:
            return "[ERROR] new_order 不能为空。"
        if len(new_order) != n:
            return f"[ERROR] 新顺序长度 ({len(new_order)}) 与幻灯片总数 ({n}) 不符。"
        if sorted(new_order) != list(range(1, n + 1)):
            return "[ERROR] new_order 必须包含 1 到 N 的每个整数恰好一次。"

        sldIdLst = prs.presentation.sldIdLst
        elements = list(sldIdLst)

        # 清空并重排
        for el in elements:
            sldIdLst.remove(el)
        for i in new_order:
            sldIdLst.append(elements[i - 1])

        if _safe_save_ppt(prs, file_path):
            return f"[SUCCESS] 幻灯片已重排，新顺序: {new_order}"
        return "[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        logger.exception("幻灯片重排失败")
        return f"[ERROR] 幻灯片重排失败: {e}"


# ────────────────────────── 读取接口 ──────────────────────────

def read_ppt_info(file_path: str) -> str:
    """读取 PPT 文件的基本信息。

    包含幻灯片数量、尺寸、每张幻灯片的形状与文字预览。

    Args:
        file_path: PPT 文件路径 (.pptx)

    Returns:
        结构化的 PPT 信息
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        lines: List[str] = [
            f"文件: {file_path}",
            f"幻灯片数量: {len(prs.slides)}",
            f"宽度: {prs.slide_width.inches:.2f} 英寸",
            f"高度: {prs.slide_height.inches:.2f} 英寸",
            "",
        ]

        for i, slide in enumerate(prs.slides, 1):
            layout_name = slide.slide_layout.name if slide.slide_layout else "Unknown"
            lines.append(f"--- 幻灯片 {i} (布局: {layout_name}, {len(slide.shapes)} 个形状) ---")

            for shape in slide.shapes:
                s_type = getattr(shape, "shape_type", "Unknown")
                info = f"  - {s_type}: "

                if hasattr(shape, 'text') and shape.text:
                    preview = shape.text[:50].replace("\n", " ")
                    info += f"'{preview}'"
                else:
                    info += f"(无文本)"

                lines.append(info)

        return "\n".join(lines)
    except Exception as e:
        logger.exception("读取 PPT 信息失败")
        return f"[ERROR] 读取 PPT 信息失败: {e}"


def read_ppt_text(file_path: str) -> str:
    """提取 PPT 中所有幻灯片的文字内容。

    Args:
        file_path: PPT 文件路径

    Returns:
        按幻灯片页码分割的纯文本
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        out: List[str] = [f"文件 '{file_path}' 文字内容:"]

        for i, slide in enumerate(prs.slides, 1):
            texts: List[str] = []
            for shape in slide.shapes:
                if hasattr(shape, 'text') and shape.text:
                    raw = str(shape.text).strip()
                    if raw:
                        texts.append(raw)

            if texts:
                out.append(f"\n--- 幻灯片 {i} ---")
                for t in texts:
                    out.append(f"  {t}")
            else:
                out.append(f"\n--- 幻灯片 {i} (无文字) ---")

        return "\n".join(out)
    except Exception as e:
        logger.exception("读取 PPT 文字失败")
        return f"[ERROR] 读取 PPT 文字失败: {e}"
