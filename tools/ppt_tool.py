import os
import tempfile
import shutil
import logging
from typing import List, Optional, Union, Any

from pptx import Presentation
from pptx.util import Inches, Pt, Emu, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# 配置日志记录器
logger = logging.getLogger(__name__)

# ────────────────────────── 常量映射表 ──────────────────────────

COLOR_MAP = {
    "red": RGBColor(0xFF, 0x00, 0x00),
    "green": RGBColor(0x00, 0x80, 0x00),
    "blue": RGBColor(0x00, 0x00, 0xFF),
    "black": RGBColor(0x00, 0x00, 0x00),
    "white": RGBColor(0xFF, 0xFF, 0xFF),
    "yellow": RGBColor(0xFF, 0xFF, 0x00),
    "orange": RGBColor(0xFF, 0xA5, 0x00),
    "purple": RGBColor(0x80, 0x00, 0x80),
    "gray": RGBColor(0x80, 0x80, 0x80),
    "dark_red": RGBColor(0x8B, 0x00, 0x00),
    "dark_green": RGBColor(0x00, 0x64, 0x00),
    "dark_blue": RGBColor(0x00, 0x00, 0x8B),
    "light_gray": RGBColor(0xD3, 0xD3, 0xD3),
    "cyan": RGBColor(0x00, 0xFF, 0xFF),
    "magenta": RGBColor(0xFF, 0x00, 0xFF),
    "brown": RGBColor(0xA5, 0x2A, 0x2A),
    "navy": RGBColor(0x00, 0x00, 0x80),
    "teal": RGBColor(0x00, 0x80, 0x80),
}

ALIGN_MAP = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
    "justify": PP_ALIGN.JUSTIFY,
}

LAYOUT_NAMES = {
    "title": 0,  # 标题幻灯片
    "title_content": 1,  # 标题和内容
    "section": 2,  # 节标题
    "two_content": 3,  # 两栏内容
    "blank": 6,  # 空白
    "content_caption": 8,  # 内容和标题
    "picture_caption": 10,  # 图片和标题
}

SHAPE_TYPE_MAP = {
    "rectangle": MSO_SHAPE.RECTANGLE,
    "rounded_rectangle": MSO_SHAPE.ROUNDED_RECTANGLE,
    "oval": MSO_SHAPE.OVAL,
    "circle": MSO_SHAPE.OVAL,
    "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
    "right_triangle": MSO_SHAPE.RIGHT_TRIANGLE,
    "diamond": MSO_SHAPE.DIAMOND,
    "pentagon": MSO_SHAPE.PENTAGON,
    "hexagon": MSO_SHAPE.HEXAGON,
    "arrow_right": MSO_SHAPE.RIGHT_ARROW,
    "arrow_left": MSO_SHAPE.LEFT_ARROW,
    "arrow_up": MSO_SHAPE.UP_ARROW,
    "arrow_down": MSO_SHAPE.DOWN_ARROW,
    "star": MSO_SHAPE.STAR_5_POINT,
    "heart": MSO_SHAPE.HEART,
    "cloud": MSO_SHAPE.CLOUD,
    "sun": MSO_SHAPE.SUN,
    "moon": MSO_SHAPE.MOON,
    "lightning": MSO_SHAPE.LIGHTNING_BOLT,
    "cross": MSO_SHAPE.CROSS,
    "cube": MSO_SHAPE.CUBE,
    "no_symbol": MSO_SHAPE.NO_SYMBOL,
    "chevron": MSO_SHAPE.CHEVRON,
    "flowchart_process": MSO_SHAPE.FLOWCHART_PROCESS,
    "flowchart_decision": MSO_SHAPE.FLOWCHART_DECISION,
    "flowchart_data": MSO_SHAPE.FLOWCHART_DATA,
    "flowchart_start": MSO_SHAPE.FLOWCHART_TERMINATOR,
}


# ────────────────────────── 内部辅助函数 ──────────────────────────

def _parse_color(color_val: Optional[str]) -> Optional[RGBColor]:
    """解析颜色值，支持英文名称和HEX格式 (如 '#FF0000' 或 'FF0000')"""
    if not color_val:
        return None
    color_val = color_val.strip()
    color_lower = color_val.lower().replace(" ", "_")
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]

    hex_color = color_val.lstrip("#")
    if len(hex_color) == 6 and all(c in "0123456789abcdefABCDEF" for c in hex_color):
        try:
            return RGBColor(
                int(hex_color[0:2], 16),
                int(hex_color[2:4], 16),
                int(hex_color[4:6], 16),
            )
        except ValueError:
            pass
    return None


def _parse_align(align_str: Optional[str]) -> Optional[int]:
    if not align_str:
        return None
    return ALIGN_MAP.get(align_str.strip().lower())


def _safe_open_ppt(file_path: str) -> Any:
    """安全地打开 PPT 文件，确保异常隔离"""
    if os.path.exists(file_path):
        try:
            return Presentation(file_path)
        except Exception as e:
            logger.warning(f"打开现有 PPT '{file_path}' 失败 ({e})，将创建新文档。")
    return Presentation()


def _safe_save_ppt(prs: Any, file_path: str) -> bool:
    """防御性保存：防文件占用、防跨磁盘移动异常"""
    try:
        fd, tmp_path = tempfile.mkstemp(suffix='.pptx')
        os.close(fd)
        prs.save(tmp_path)

        # 使用 copy2 保证跨 Volume 安全，覆盖原文件
        shutil.copy2(tmp_path, file_path)
        os.remove(tmp_path)
        return True
    except PermissionError:
        logger.error(f"保存失败：文件 '{file_path}' 正被其他程序(如PowerPoint)占用。")
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False
    except Exception as e:
        logger.error(f"保存 PPT 发生未知异常: {str(e)}")
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def _get_layout(prs: Any, layout_name_or_index: Union[str, int, None]) -> Any:
    default_layout = prs.slide_layouts[6]  # Blank
    if layout_name_or_index is None:
        return default_layout

    if isinstance(layout_name_or_index, str):
        layout_key = layout_name_or_index.strip().lower().replace(" ", "_")
        idx = LAYOUT_NAMES.get(layout_key)
        if idx is not None and idx < len(prs.slide_layouts):
            return prs.slide_layouts[idx]
        return default_layout

    if isinstance(layout_name_or_index, int) and 0 <= layout_name_or_index < len(prs.slide_layouts):
        return prs.slide_layouts[layout_name_or_index]

    return default_layout


def _set_shape_fill(shape: Any, color: Optional[str] = None, transparency: Optional[float] = None) -> None:
    if not color:
        return
    parsed = _parse_color(color)
    if not parsed:
        return
    try:
        shape.fill.solid()
        shape.fill.fore_color.rgb = parsed
        if transparency is not None and 0.0 <= transparency <= 1.0:
            solidFill = shape.fill._fill
            # 修正底层 XML 寻址：a:solidFill 下必须寻找 a:srgbClr
            srgb = solidFill.find(qn('a:srgbClr'))
            if srgb is None:
                # 兼容部分直接挂载方案
                srgb = solidFill.find(qn('a:sysClr'))

            if srgb is not None:
                alpha = int((1.0 - transparency) * 100000)
                alpha_elem = srgb.find(qn('a:alpha'))
                if alpha_elem is None:
                    from pptx.oxml.xmlchemy import OxmlElement
                    alpha_elem = OxmlElement('a:alpha')
                    srgb.append(alpha_elem)
                alpha_elem.set('val', str(alpha))
    except Exception as e:
        logger.debug(f"设置形状填充失败: {e}")


def _set_shape_line(shape: Any, color: Optional[str] = None, width: Optional[float] = None) -> None:
    if color:
        parsed = _parse_color(color)
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


def _set_text_format(text_frame: Any, text: Optional[str], font_name: Optional[str] = None,
                     font_size: Optional[int] = None, bold: Optional[bool] = None,
                     italic: Optional[bool] = None, color: Optional[str] = None,
                     alignment: Optional[str] = None) -> None:
    if text is None:
        return

    text_frame.text = str(text)
    if not text_frame.paragraphs:
        return

    para = text_frame.paragraphs[0]
    parsed_align = _parse_align(alignment)
    if parsed_align:
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
            parsed = _parse_color(color)
            if parsed:
                run.font.color.rgb = parsed


def _set_slide_bg_color(slide: Any, color: Optional[str]) -> None:
    parsed = _parse_color(color)
    if not parsed:
        return
    try:
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = parsed
    except Exception as e:
        logger.debug(f"设置背景色失败: {e}")


# ────────────────────────── 公开接口函数 ──────────────────────────

def create_ppt(file_path: str, title: Optional[str] = None) -> str:
    try:
        prs = Presentation()
        if title:
            slide_layout = prs.slide_layouts[0]
            slide = prs.slides.add_slide(slide_layout)
            if slide.shapes.title:
                slide.shapes.title.text = title

        if _safe_save_ppt(prs, file_path):
            return f"✓ PPT 文件已创建: '{file_path}'"
        return f"[ERROR] 保存 PPT 文件失败，文件可能被占用。"
    except Exception as e:
        return f"[ERROR] 创建 PPT 失败: {str(e)}"


def add_slide(file_path: str, layout: Union[str, int] = "blank",
              title: Optional[str] = None, content: Optional[str] = None) -> str:
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
            return f"✓ 已添加幻灯片 (布局: '{layout}')"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 添加幻灯片失败: {str(e)}"


def add_textbox(file_path: str, slide_index: int = -1,
                left: float = 1.0, top: float = 1.0,
                width: float = 8.0, height: float = 1.5,
                text: str = "", font_name: Optional[str] = None,
                font_size: int = 18, bold: Optional[bool] = None,
                italic: Optional[bool] = None, color: Optional[str] = None,
                alignment: Optional[str] = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides
        if not slides:
            return "[ERROR] PPT 中没有幻灯片。"

        target_idx = len(slides) - 1 if slide_index == -1 else slide_index - 1
        if not (0 <= target_idx < len(slides)):
            return f"[ERROR] 幻灯片索引 {slide_index} 超出范围。"

        slide = slides[target_idx]
        txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txBox.text_frame
        tf.word_wrap = True

        _set_text_format(tf, text, font_name, font_size, bold, italic, color, alignment)

        if _safe_save_ppt(prs, file_path):
            return f"✓ 文本框已添加至第 {target_idx + 1} 张幻灯片。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 添加文本框失败: {str(e)}"


def add_shape(file_path: str, slide_index: int = -1,
              shape_type: str = "rectangle",
              left: float = 1.0, top: float = 1.0,
              width: float = 3.0, height: float = 2.0,
              fill_color: Optional[str] = None, line_color: Optional[str] = None,
              line_width: Optional[float] = None, text: Optional[str] = None,
              font_name: Optional[str] = None, font_size: Optional[int] = None,
              font_color: Optional[str] = None, bold: Optional[bool] = None,
              alignment: Optional[str] = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides
        if not slides:
            return "[ERROR] PPT 中没有幻灯片。"

        target_idx = len(slides) - 1 if slide_index == -1 else slide_index - 1
        if not (0 <= target_idx < len(slides)):
            return f"[ERROR] 幻灯片索引 {slide_index} 超出范围。"

        slide = slides[target_idx]
        shape_enum = SHAPE_TYPE_MAP.get(shape_type.strip().lower().replace(" ", "_"), MSO_SHAPE.RECTANGLE)

        shape = slide.shapes.add_shape(
            shape_enum, Inches(left), Inches(top), Inches(width), Inches(height)
        )

        _set_shape_fill(shape, color=fill_color)
        _set_shape_line(shape, color=line_color, width=line_width)

        if text is not None and hasattr(shape, 'text_frame'):
            _set_text_format(shape.text_frame, text, font_name, font_size, bold=bold, color=font_color,
                             alignment=alignment)

        if _safe_save_ppt(prs, file_path):
            return f"✓ 形状({shape_type})已添加至第 {target_idx + 1} 张幻灯片。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 添加形状失败: {str(e)}"


def add_table_slide(file_path: str, slide_index: int = -1,
                    data: Optional[List[List[Any]]] = None, headers: Optional[List[Any]] = None,
                    left: float = 1.0, top: float = 2.0,
                    width: float = 8.0, height: Optional[float] = None,
                    font_name: Optional[str] = None, font_size: int = 12,
                    header_color: Optional[str] = None, header_bold: bool = True,
                    alignment: Optional[str] = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    if not data or not data[0]:
        return "[ERROR] 表格数据为空或无效。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides
        if not slides:
            return "[ERROR] PPT 中没有幻灯片。"

        target_idx = len(slides) - 1 if slide_index == -1 else slide_index - 1
        if not (0 <= target_idx < len(slides)):
            return f"[ERROR] 幻灯片索引 {slide_index} 超出范围。"

        slide = slides[target_idx]
        num_rows = len(data) + (1 if headers else 0)
        num_cols = len(data[0])

        if height is None:
            height = num_rows * 0.5

        table_shape = slide.shapes.add_table(num_rows, num_cols, Inches(left), Inches(top), Inches(width),
                                             Inches(height))
        table = table_shape.table

        start_row = 0
        if headers:
            for j, header_text in enumerate(headers):
                if j < num_cols:
                    _set_text_format(table.cell(0, j).text_frame, str(header_text), font_name, font_size,
                                     bold=header_bold, color=header_color, alignment=alignment)
            start_row = 1

        for i, row_data in enumerate(data):
            for j, cell_text in enumerate(row_data):
                if j < num_cols:
                    _set_text_format(table.cell(start_row + i, j).text_frame, str(cell_text), font_name, font_size,
                                     alignment=alignment)

        if _safe_save_ppt(prs, file_path):
            return f"✓ 表格({num_rows}x{num_cols})已添加至幻灯片。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 添加表格失败: {str(e)}"


def add_image(file_path: str, slide_index: int = -1,
              image_path: str = "",
              left: float = 1.0, top: float = 1.0,
              width: Optional[float] = None, height: Optional[float] = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] PPT 文件 '{file_path}' 不存在。"
    if not image_path or not os.path.exists(image_path):
        return f"[ERROR] 目标图片文件 '{image_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides
        if not slides:
            return "[ERROR] PPT 中没有幻灯片。"

        target_idx = len(slides) - 1 if slide_index == -1 else slide_index - 1
        slide = slides[target_idx]

        w_inch = Inches(width) if width else None
        h_inch = Inches(height) if height else None

        if w_inch and h_inch:
            slide.shapes.add_picture(image_path, Inches(left), Inches(top), w_inch, h_inch)
        elif w_inch:
            slide.shapes.add_picture(image_path, Inches(left), Inches(top), width=w_inch)
        elif h_inch:
            slide.shapes.add_picture(image_path, Inches(left), Inches(top), height=h_inch)
        else:
            slide.shapes.add_picture(image_path, Inches(left), Inches(top))

        if _safe_save_ppt(prs, file_path):
            return f"✓ 图片已添加至第 {target_idx + 1} 张幻灯片。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 添加图片失败: {str(e)}"


def set_slide_background(file_path: str, slide_index: int = -1, color: Optional[str] = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    if not color:
        return "[ERROR] 必须指定背景颜色。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides

        target_slides = []
        if slide_index == -1:
            target_slides = list(slides)
        else:
            if not (0 < slide_index <= len(slides)):
                return f"[ERROR] 幻灯片索引超限。"
            target_slides = [slides[slide_index - 1]]

        for slide in target_slides:
            _set_slide_bg_color(slide, color)

        if _safe_save_ppt(prs, file_path):
            return f"✓ 幻灯片背景设置完毕。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 设置背景失败: {str(e)}"


def duplicate_slide(file_path: str, slide_index: int = 1) -> str:
    """注意：由于 python-pptx 原生限制，深拷贝仅复制元素节点，可能会丢失部分源幻灯片的关系资源(如原始图片链接)"""
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides
        if not (0 < slide_index <= len(slides)):
            return f"[ERROR] 幻灯片索引 {slide_index} 超出范围。"

        source_slide = slides[slide_index - 1]
        new_slide = prs.slides.add_slide(source_slide.slide_layout)

        for shape in source_slide.shapes:
            el = shape._element
            new_el = el.__deepcopy__(None)
            new_slide.shapes._spTree.append(new_el)

        if _safe_save_ppt(prs, file_path):
            return f"✓ 第 {slide_index} 张幻灯片已复制 (警告: 图片等关系资源可能未被完全拷贝)。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 复制幻灯片失败: {str(e)}"


def delete_slide(file_path: str, slide_index: int = 1) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides
        if not (0 < slide_index <= len(slides)):
            return f"[ERROR] 幻灯片索引 {slide_index} 超出范围。"

        sldIdLst = prs.presentation.sldIdLst
        slide_id = slides[slide_index - 1].slide_id

        # 移除底层 XML 节点
        for sldId in sldIdLst:
            if sldId.get(qn('r:id')) == slide_id or str(sldId.get('id')) == str(slide_id):
                sldIdLst.remove(sldId)
                break

        # 注意：此处切勿重新调用 len(prs.slides)，缓存已污染
        if _safe_save_ppt(prs, file_path):
            return f"✓ 第 {slide_index} 张幻灯片已成功删除。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 删除幻灯片失败: {str(e)}"


def reorder_slides(file_path: str, new_order: List[int]) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    try:
        prs = Presentation(file_path)
        slides = prs.slides
        n = len(slides)

        if not new_order or len(new_order) != n:
            return f"[ERROR] 提供的顺序规则长度 ({len(new_order) if new_order else 0}) 与总幻灯片数 ({n}) 不符。"
        if sorted(new_order) != list(range(1, n + 1)):
            return "[ERROR] 重排序规则必须严格包含 1 到 N 的所有唯一正整数。"

        sldIdLst = prs.presentation.sldIdLst
        sldId_elements = list(sldIdLst)
        reordered = [sldId_elements[i - 1] for i in new_order]

        for element in sldId_elements:
            sldIdLst.remove(element)
        for element in reordered:
            sldIdLst.append(element)

        if _safe_save_ppt(prs, file_path):
            return f"✓ 幻灯片已重排，新序列: {new_order}"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 幻灯片重排失败: {str(e)}"


# ────────────────────────── 读取与提取接口 (Read & Extract APIs) ──────────────────────────

def read_ppt_info(file_path: str) -> str:
    """
    读取 PPT 文件的基本信息（强类型防崩溃版）。

    Args:
        file_path: PPT 文件路径

    Returns:
        包含幻灯片数量、尺寸、布局类型及形状坐标的结构化字符串。
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 目标文件 '{file_path}' 不存在，无法读取信息。"

    try:
        prs = Presentation(file_path)
        info_lines: List[str] = [
            f"文件: {file_path}",
            f"幻灯片数量: {len(prs.slides)}",
            f"幻灯片宽度: {prs.slide_width.inches:.2f} 英寸 ({prs.slide_width.emu} EMU)",
            f"幻灯片高度: {prs.slide_height.inches:.2f} 英寸 ({prs.slide_height.emu} EMU)",
            "",
        ]

        for i, slide in enumerate(prs.slides, 1):
            shape_count = len(slide.shapes)
            layout_name = slide.slide_layout.name if slide.slide_layout else "Unknown"
            info_lines.append(f"--- 幻灯片 {i} (布局: {layout_name}, {shape_count} 个形状) ---")

            for shape in slide.shapes:
                # 防御性读取 shape_type，部分占位符可能缺失该属性
                s_type = getattr(shape, "shape_type", "Unknown")
                shape_info = f"  - {s_type}: "

                # 防空指针文本提取
                if hasattr(shape, 'text') and shape.text:
                    text_preview = shape.text[:50].replace("\n", " ")
                    shape_info += f"'{text_preview}'"
                else:
                    # 保护性读取坐标，某些复杂形状对象可能无确切边界
                    left = getattr(shape, "left", "N/A")
                    top = getattr(shape, "top", "N/A")
                    w = getattr(shape, "width", "N/A")
                    h = getattr(shape, "height", "N/A")
                    shape_info += f"位置=({left}, {top}), 尺寸=({w}, {h})"

                info_lines.append(shape_info)

        return "\n".join(info_lines)
    except Exception as e:
        logger.error(f"读取 PPT 信息发生严重异常: {e}")
        return f"[ERROR] 读取 PPT 信息失败: {str(e)}"


def read_ppt_text(file_path: str) -> str:
    """
    提取 PPT 文件中所有幻灯片的文字内容。

    Args:
        file_path: PPT 文件路径

    Returns:
        纯文本提取结果，按幻灯片页码分割。
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 目标文件 '{file_path}' 不存在，无法读取文本。"

    try:
        prs = Presentation(file_path)
        output: List[str] = [f"文件 '{file_path}' 的文字内容:"]

        for i, slide in enumerate(prs.slides, 1):
            output.append(f"\n--- 幻灯片 {i} ---")
            for shape in slide.shapes:
                if hasattr(shape, 'text'):
                    # 强制转换为字符串并剥离两端空白，规避 NoneType 异常
                    raw_text = str(shape.text).strip()
                    if raw_text:
                        output.append(f"  {raw_text}")

        return "\n".join(output)
    except Exception as e:
        logger.error(f"读取 PPT 文字发生严重异常: {e}")
        return f"[ERROR] 读取 PPT 文字失败: {str(e)}"


# ────────────────────────── 高级排版接口 (Advanced Layout APIs) ──────────────────────────

def add_title_slide(file_path: str, title: str = "标题",
                    subtitle: Optional[str] = None,
                    title_color: Optional[str] = None,
                    subtitle_color: Optional[str] = None,
                    bg_color: Optional[str] = None) -> str:
    """添加标准标题（封面）幻灯片"""
    try:
        prs = _safe_open_ppt(file_path)
        slide = prs.slides.add_slide(prs.slide_layouts[0])  # Layout 0: Title Slide

        if bg_color:
            _set_slide_bg_color(slide, bg_color)

        if slide.shapes.title:
            _set_text_format(slide.shapes.title.text_frame, title, font_size=44, bold=True, color=title_color)

        if subtitle:
            for shape in slide.placeholders:
                if shape.placeholder_format.idx == 1:
                    _set_text_format(shape.text_frame, subtitle, font_size=24, color=subtitle_color)
                    break

        if _safe_save_ppt(prs, file_path):
            return f"✓ 标题幻灯片已添加，共 {len(prs.slides)} 张。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 添加标题幻灯片失败: {str(e)}"


def add_bullet_slide(file_path: str, title: str = "内容",
                     bullets: Optional[List[Any]] = None,
                     font_name: Optional[str] = None,
                     font_size: int = 18,
                     color: Optional[str] = None,
                     bg_color: Optional[str] = None) -> str:
    """添加标准项目符号列表幻灯片"""
    if not bullets:
        bullets = []

    try:
        prs = _safe_open_ppt(file_path)
        slide = prs.slides.add_slide(prs.slide_layouts[1])  # Layout 1: Title and Content

        if bg_color:
            _set_slide_bg_color(slide, bg_color)

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
                        parsed_color = _parse_color(color)
                        if parsed_color:
                            run.font.color.rgb = parsed_color
                break

        if _safe_save_ppt(prs, file_path):
            return f"✓ 项目符号幻灯片已添加 (包含 {len(bullets)} 条要点)。"
        return f"[ERROR] 保存 PPT 文件失败。"
    except Exception as e:
        return f"[ERROR] 添加内容幻灯片失败: {str(e)}"