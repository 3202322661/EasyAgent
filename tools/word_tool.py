import os
import tempfile
import shutil
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

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
}

ALIGN_MAP = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _parse_color(color_val):
    if color_val is None:
        return None
    color_lower = color_val.lower().replace(" ", "_")
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]
    if color_val.startswith("#"):
        hex_color = color_val[1:]
        if len(hex_color) == 6:
            try:
                return RGBColor(
                    int(hex_color[0:2], 16),
                    int(hex_color[2:4], 16),
                    int(hex_color[4:6], 16),
                )
            except ValueError:
                pass
    if len(color_val) == 6 and all(c in "0123456789abcdefABCDEF" for c in color_val):
        try:
            return RGBColor(
                int(color_val[0:2], 16),
                int(color_val[2:4], 16),
                int(color_val[4:6], 16),
            )
        except ValueError:
            pass
    return None


def _parse_align(align_str):
    if align_str is None:
        return None
    return ALIGN_MAP.get(align_str.lower())


def _set_run_font(run, font_name=None, font_size=None, bold=None, italic=None,
                  underline=None, color=None):
    """安全地设置 run 的字体格式，避免直接操作底层 XML 导致文件损坏"""
    if font_name:
        try:
            run.font.name = font_name
            # 设置中文字体（通过底层 XML，但尽量安全）
            r = run._element
            rPr = r.find(qn('w:rPr'))
            if rPr is not None:
                rFonts = rPr.find(qn('w:rFonts'))
                if rFonts is not None:
                    rFonts.set(qn('w:eastAsia'), font_name)
        except Exception:
            pass
    if font_size is not None:
        try:
            run.font.size = Pt(font_size)
        except Exception:
            pass
    if bold is not None:
        try:
            run.bold = bold
        except Exception:
            pass
    if italic is not None:
        try:
            run.italic = italic
        except Exception:
            pass
    if underline is not None:
        try:
            run.underline = underline
        except Exception:
            pass
    if color:
        try:
            parsed_color = _parse_color(color)
            if parsed_color:
                run.font.color.rgb = parsed_color
        except Exception:
            pass


def _set_paragraph_format(paragraph, alignment=None, line_spacing=None,
                          space_before=None, space_after=None,
                          first_line_indent=None, left_indent=None,
                          right_indent=None, keep_with_next=None,
                          page_break_before=None):
    pf = paragraph.paragraph_format
    if alignment:
        parsed_align = _parse_align(alignment)
        if parsed_align:
            pf.alignment = parsed_align
    if line_spacing is not None:
        pf.line_spacing = line_spacing
    if space_before is not None:
        pf.space_before = Pt(space_before)
    if space_after is not None:
        pf.space_after = Pt(space_after)
    if first_line_indent is not None:
        pf.first_line_indent = Pt(first_line_indent)
    if left_indent is not None:
        pf.left_indent = Pt(left_indent)
    if right_indent is not None:
        pf.right_indent = Pt(right_indent)
    if keep_with_next is not None:
        pf.keep_with_next = keep_with_next
    if page_break_before is not None:
        pf.page_break_before = page_break_before


def _safe_open_doc(file_path):
    """安全地打开文档，如果文件损坏则创建新文档"""
    if not os.path.exists(file_path):
        return Document()
    try:
        return Document(file_path)
    except Exception as e:
        return Document()


def _safe_save_doc(doc, file_path):
    """安全地保存文档，先保存到临时文件再替换"""
    try:
        # 先保存到临时文件
        fd, tmp_path = tempfile.mkstemp(suffix='.docx')
        os.close(fd)
        doc.save(tmp_path)
        # 替换原文件
        shutil.move(tmp_path, file_path)
        return True
    except Exception:
        return False


def read_word_text(file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    try:
        doc = Document(file_path)
        lines = []
        for i, para in enumerate(doc.paragraphs, 1):
            text = para.text.strip()
            style_name = para.style.name if para.style else "Normal"
            lines.append(f"{i:4} [{style_name}] {text}")
        result = "\n".join(lines)
        return f"文件 '{file_path}' 的文本内容（共 {len(lines)} 段）:\n{result}"
    except Exception as e:
        return f"[ERROR] 读取 Word 文档失败: {str(e)}"


def read_word_tables(file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    try:
        doc = Document(file_path)
        if not doc.tables:
            return f"文件 '{file_path}' 中未找到表格。"

        output_parts = []
        for t_idx, table in enumerate(doc.tables, 1):
            output_parts.append(f"--- 表格 {t_idx} ({len(table.rows)} 行 x {len(table.columns)} 列) ---")
            for r_idx, row in enumerate(table.rows, 1):
                cells_text = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                output_parts.append(f"  行{r_idx}: {' | '.join(cells_text)}")
            output_parts.append("")
        return f"文件 '{file_path}' 的表格内容:\n" + "\n".join(output_parts)
    except Exception as e:
        return f"[ERROR] 读取表格失败: {str(e)}"


def read_word_info(file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    try:
        doc = Document(file_path)
        para_count = len(doc.paragraphs)
        table_count = len(doc.tables)
        non_empty = sum(1 for p in doc.paragraphs if p.text.strip())
        styles_used = set()
        for p in doc.paragraphs:
            if p.style:
                styles_used.add(p.style.name)

        info_lines = [
            f"文档: {file_path}",
            f"总段落数: {para_count}",
            f"非空段落数: {non_empty}",
            f"表格数量: {table_count}",
            f"使用样式 ({len(styles_used)}): {', '.join(sorted(styles_used))}",
        ]
        return "\n".join(info_lines)
    except Exception as e:
        return f"[ERROR] 读取文档信息失败: {str(e)}"


def create_word_document(file_path: str, title: str = None) -> str:
    try:
        doc = Document()
        if title:
            para = doc.add_heading(title, level=1)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.save(file_path)
        return f"✓ Word 文档已创建: '{file_path}'"
    except Exception as e:
        return f"[ERROR] 创建文档失败: {str(e)}"


def add_paragraph(file_path: str, text: str, style: str = None,
                  font_name: str = None, font_size: int = None,
                  bold: bool = None, italic: bool = None,
                  underline: bool = None, color: str = None,
                  alignment: str = None, line_spacing: float = None,
                  space_before: int = None, space_after: int = None,
                  first_line_indent: int = None) -> str:
    try:
        doc = _safe_open_doc(file_path)

        para = doc.add_paragraph()
        run = para.add_run(text)

        _set_run_font(run, font_name=font_name, font_size=font_size,
                      bold=bold, italic=italic, underline=underline, color=color)

        _set_paragraph_format(para, alignment=alignment, line_spacing=line_spacing,
                              space_before=space_before, space_after=space_after,
                              first_line_indent=first_line_indent)
        if style:
            try:
                para.style = doc.styles[style]
            except KeyError:
                pass

        saved = _safe_save_doc(doc, file_path)
        if saved:
            return f"✓ 段落已添加到 '{file_path}'"
        else:
            return f"[ERROR] 保存文档失败"
    except Exception as e:
        return f"[ERROR] 添加段落失败: {str(e)}"


def add_heading(file_path: str, text: str, level: int = 1,
                font_name: str = None, font_size: int = None,
                color: str = None, alignment: str = None) -> str:
    try:
        doc = _safe_open_doc(file_path)

        # 使用 add_paragraph + 样式设置，避免 add_heading 的兼容性问题
        para = doc.add_paragraph()
        run = para.add_run(text)

        # 设置 Heading 样式
        style_name = f"Heading {level}"
        try:
            para.style = doc.styles[style_name]
        except KeyError:
            pass

        if font_name or font_size or color:
            _set_run_font(run, font_name=font_name, font_size=font_size, color=color)
        if alignment:
            _set_paragraph_format(para, alignment=alignment)

        saved = _safe_save_doc(doc, file_path)
        if saved:
            return f"✓ 标题 (H{level}) 已添加到 '{file_path}'"
        else:
            return f"[ERROR] 保存文档失败"
    except Exception as e:
        return f"[ERROR] 添加标题失败: {str(e)}"


def add_table(file_path: str, data: list, headers: list = None,
              font_name: str = None, font_size: int = None,
              bold_header: bool = True, alignment: str = None) -> str:
    try:
        doc = _safe_open_doc(file_path)

        rows = len(data)
        cols = len(data[0]) if data else 0
        if headers:
            rows += 1

        if rows == 0 or cols == 0:
            return "[ERROR] 表格数据为空。"

        table = doc.add_table(rows=rows, cols=cols)
        table.style = 'Table Grid'

        if alignment:
            align_map = {
                "left": WD_TABLE_ALIGNMENT.LEFT,
                "center": WD_TABLE_ALIGNMENT.CENTER,
                "right": WD_TABLE_ALIGNMENT.RIGHT,
            }
            table.alignment = align_map.get(alignment.lower())

        if headers:
            for j, header_text in enumerate(headers):
                cell = table.rows[0].cells[j]
                cell.text = str(header_text)
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        _set_run_font(run, font_name=font_name, font_size=font_size,
                                      bold=bold_header)

        start_row = 1 if headers else 0
        for i, row_data in enumerate(data):
            for j, cell_text in enumerate(row_data):
                cell = table.rows[start_row + i].cells[j]
                cell.text = str(cell_text)
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        _set_run_font(run, font_name=font_name, font_size=font_size)

        saved = _safe_save_doc(doc, file_path)
        if saved:
            return f"✓ 表格 ({rows} 行 x {cols} 列) 已添加到 '{file_path}'"
        else:
            return f"[ERROR] 保存文档失败"
    except Exception as e:
        return f"[ERROR] 添加表格失败: {str(e)}"


def add_page_break(file_path: str) -> str:
    try:
        doc = _safe_open_doc(file_path)
        doc.add_page_break()
        saved = _safe_save_doc(doc, file_path)
        if saved:
            return f"✓ 分页符已添加到 '{file_path}'"
        else:
            return f"[ERROR] 保存文档失败"
    except Exception as e:
        return f"[ERROR] 添加分页符失败: {str(e)}"


def set_paragraph_format(file_path: str, paragraph_index: int = None,
                         alignment: str = None, line_spacing: float = None,
                         space_before: int = None, space_after: int = None,
                         first_line_indent: int = None,
                         left_indent: int = None, right_indent: int = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    try:
        doc = Document(file_path)
        paragraphs = doc.paragraphs

        if paragraph_index is not None:
            if paragraph_index < 1 or paragraph_index > len(paragraphs):
                return f"[ERROR] 段落索引 {paragraph_index} 超出范围 (1-{len(paragraphs)})。"
            target_paras = [paragraphs[paragraph_index - 1]]
            desc = f"第 {paragraph_index} 段"
        else:
            target_paras = paragraphs
            desc = "所有段落"

        for para in target_paras:
            _set_paragraph_format(para, alignment=alignment, line_spacing=line_spacing,
                                  space_before=space_before, space_after=space_after,
                                  first_line_indent=first_line_indent,
                                  left_indent=left_indent, right_indent=right_indent)

        saved = _safe_save_doc(doc, file_path)
        if saved:
            return f"✓ 已调整 '{file_path}' 中 {desc} 的格式"
        else:
            return f"[ERROR] 保存文档失败"
    except Exception as e:
        return f"[ERROR] 调整段落格式失败: {str(e)}"


def set_run_format(file_path: str, paragraph_index: int,
                   font_name: str = None, font_size: int = None,
                   bold: bool = None, italic: bool = None,
                   underline: bool = None, color: str = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    try:
        doc = Document(file_path)
        paragraphs = doc.paragraphs

        if paragraph_index < 1 or paragraph_index > len(paragraphs):
            return f"[ERROR] 段落索引 {paragraph_index} 超出范围 (1-{len(paragraphs)})。"

        para = paragraphs[paragraph_index - 1]
        for run in para.runs:
            _set_run_font(run, font_name=font_name, font_size=font_size,
                          bold=bold, italic=italic, underline=underline, color=color)

        saved = _safe_save_doc(doc, file_path)
        if saved:
            return f"✓ 已调整 '{file_path}' 第 {paragraph_index} 段的字体格式"
        else:
            return f"[ERROR] 保存文档失败"
    except Exception as e:
        return f"[ERROR] 调整字体格式失败: {str(e)}"


def set_page_margins(file_path: str, top: float = None, bottom: float = None,
                     left: float = None, right: float = None) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    try:
        doc = Document(file_path)
        section = doc.sections[0]

        if top is not None:
            section.top_margin = Inches(top)
        if bottom is not None:
            section.bottom_margin = Inches(bottom)
        if left is not None:
            section.left_margin = Inches(left)
        if right is not None:
            section.right_margin = Inches(right)

        saved = _safe_save_doc(doc, file_path)
        if saved:
            return f"✓ 已设置 '{file_path}' 的页面边距 (上:{top}, 下:{bottom}, 左:{left}, 右:{right})"
        else:
            return f"[ERROR] 保存文档失败"
    except Exception as e:
        return f"[ERROR] 设置页面边距失败: {str(e)}"


def list_doc_styles(file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"
    try:
        doc = Document(file_path)
        styles = doc.styles
        style_info = []
        for style in styles:
            if style.type is not None:
                style_info.append(f"  [{style.type.name}] {style.name}")
        return f"文档 '{file_path}' 的可用样式（共 {len(style_info)} 个）:\n" + "\n".join(style_info)
    except Exception as e:
        return f"[ERROR] 获取样式列表失败: {str(e)}"
