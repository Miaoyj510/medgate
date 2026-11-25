# -*- coding: utf-8 -*-
"""把 Markdown 讲稿转成排版好的 docx。"""
import io, re, sys
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = "项目全面讲解.md"
OUT = "医保智能审核与处方前置Agent平台-项目全面讲解.docx"

CN_BODY = "宋体"
CN_HEAD = "微软雅黑"
MONO = "Consolas"

ACCENT = RGBColor(0x1F, 0x3B, 0x63)
GREY = RGBColor(0x59, 0x59, 0x59)


def set_cn(run, font):
    run.font.name = font
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts'); rpr.append(rfonts)
    rfonts.set(qn('w:eastAsia'), font)
    rfonts.set(qn('w:ascii'), font)
    rfonts.set(qn('w:hAnsi'), font)


def shade(el, fill):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill)
    el.append(shd)


def p_border(p, color="C9D6E8", size=18, left_only=False):
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    sides = ['left'] if left_only else ['top', 'left', 'bottom', 'right']
    for side in sides:
        el = OxmlElement('w:' + side)
        el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(size))
        el.set(qn('w:space'), '6'); el.set(qn('w:color'), color)
        pbdr.append(el)
    pPr.append(pbdr)


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def add_inline(p, text, size=None, color=None, bold=False, font=CN_BODY):
    for piece in INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            r = p.add_run(piece[2:-2]); r.bold = True; set_cn(r, font)
        elif piece.startswith("`") and piece.endswith("`"):
            r = p.add_run(piece[1:-1]); set_cn(r, MONO); r.font.size = Pt((size or 10.5) - 0.5)
            r.font.color.rgb = RGBColor(0x8B, 0x2E, 0x2E)
        else:
            r = p.add_run(piece); r.bold = bold; set_cn(r, font)
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color
    return p


def style_doc(doc):
    st = doc.styles['Normal']
    st.font.name = CN_BODY; st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), CN_BODY)
    pf = st.paragraph_format
    pf.space_after = Pt(5); pf.line_spacing = 1.35
    for name, size, color in (('Heading 1', 18, ACCENT), ('Heading 2', 13.5, ACCENT), ('Heading 3', 11.5, ACCENT)):
        s = doc.styles[name]
        s.font.name = CN_HEAD; s.font.size = Pt(size); s.font.bold = True
        s.font.color.rgb = color
        s.element.rPr.rFonts.set(qn('w:eastAsia'), CN_HEAD)
        s.paragraph_format.space_before = Pt(12 if name == 'Heading 1' else 9)
        s.paragraph_format.space_after = Pt(6)
        s.paragraph_format.keep_with_next = True


def add_page_number_footer(section, text):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text + "    ·    ")
    set_cn(r, CN_BODY); r.font.size = Pt(8); r.font.color.rgb = GREY
    fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'), 'PAGE')
    rr = OxmlElement('w:r'); rpr = OxmlElement('w:rPr')
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), '16'); rpr.append(sz)
    rr.append(rpr); fld.append(rr)
    p._p.append(fld)


def set_cell(cell, text, size=9, bold=False, fill=None, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.line_spacing = 1.2
    if align:
        p.alignment = align
    add_inline(p, text, size=size, bold=bold, font=CN_HEAD if bold else CN_BODY)
    if fill:
        shade(cell._tc.get_or_add_tcPr(), fill)
    tcPr = cell._tc.get_or_add_tcPr()
    vmar = OxmlElement('w:tcMar')
    for side, val in (('top', 40), ('bottom', 40), ('left', 80), ('right', 80)):
        el = OxmlElement('w:' + side); el.set(qn('w:w'), str(val)); el.set(qn('w:type'), 'dxa'); vmar.append(el)
    tcPr.append(vmar)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement('w:tblHeader'); el.set(qn('w:val'), 'true'); trPr.append(el)


def split_row(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def is_sep(line):
    return bool(re.match(r"^\|[\s\-:|]+\|$", line.strip()))


def main():
    src = io.open(SRC, encoding="utf-8").read().split("\n")
    doc = Document()
    style_doc(doc)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = Cm(2.2); sec.bottom_margin = Cm(2.0)
    add_page_number_footer(sec, "医保智能审核与处方前置 Agent 平台 · 项目全面讲解")

    i = 0
    n = len(src)
    title_done = False
    while i < n:
        line = src[i].rstrip()
        if not line.strip():
            i += 1; continue

        # 表格
        if line.lstrip().startswith("|"):
            block = []
            while i < n and src[i].lstrip().startswith("|"):
                block.append(src[i]); i += 1
            rows = [split_row(b) for b in block if not is_sep(b)]
            if not rows: continue
            ncol = max(len(r) for r in rows)
            t = doc.add_table(rows=0, cols=ncol)
            t.style = 'Table Grid'
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            t.autofit = True
            for ri, row in enumerate(rows):
                cells = t.add_row().cells
                for ci in range(ncol):
                    txt = row[ci] if ci < len(row) else ""
                    set_cell(cells[ci], txt, size=9, bold=(ri == 0),
                             fill="E8EEF7" if ri == 0 else None)
                if ri == 0:
                    repeat_header(t.rows[0])
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue

        # 引用块
        if line.lstrip().startswith(">"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.3)
            p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(8)
            add_inline(p, line.lstrip()[1:].strip(), size=10, color=RGBColor(0x33, 0x33, 0x33))
            shade(p._p.get_or_add_pPr(), "F4F7FB")
            p_border(p, left_only=True)
            i += 1; continue

        # 标题
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and not title_done:
                # 封面
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(90)
                r = p.add_run(text.split("·")[0].strip()); r.bold = True; set_cn(r, CN_HEAD)
                r.font.size = Pt(26); r.font.color.rgb = ACCENT
                p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p2.paragraph_format.space_before = Pt(6)
                r2 = p2.add_run(text.split("·", 1)[1].strip() if "·" in text else text)
                set_cn(r2, CN_HEAD); r2.font.size = Pt(15); r2.font.color.rgb = RGBColor(0x33, 0x55, 0x88)
                p3 = doc.add_paragraph(); p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p3.paragraph_format.space_before = Pt(24)
                r3 = p3.add_run("项目理解手册 · 供产品/医保/药学/信息科与后续参与实现者阅读")
                set_cn(r3, CN_BODY); r3.font.size = Pt(11); r3.font.color.rgb = GREY
                p4 = doc.add_paragraph(); p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p4.paragraph_format.space_before = Pt(10)
                r4 = p4.add_run("编写日期：2026-11-16　|　对应 PRD 版本：v1.1　|　内容以 PRD 为准")
                set_cn(r4, CN_BODY); r4.font.size = Pt(9.5); r4.font.color.rgb = GREY
                title_done = True
                i += 1; continue
            if level == 1:
                doc.add_page_break()
            h = doc.add_heading(level=min(level, 3))
            add_inline(h, text, size={1: 18, 2: 13.5, 3: 11.5}[level], color=ACCENT, bold=True, font=CN_HEAD)
            for r in h.runs:
                r.bold = True
            i += 1; continue

        # 列表
        if re.match(r"^\s*-\s+", line):
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, re.sub(r"^\s*-\s+", "", line))
            i += 1; continue

        # 正文
        p = doc.add_paragraph()
        add_inline(p, line.strip())
        i += 1

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()