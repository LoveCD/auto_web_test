# -*- coding: utf-8 -*-
"""DOCX 品牌化共享 helper：FiberHome 封面 logo + FH 文档编号页眉。

参考样例：reports/case-docs/测试报告-CM-REAL-SECURITY-20260820-143302.docx
（gen-case-doc.js + test-report-template.docx 链路产物）

提供两个能力，供所有 Python 文档生成器复用：
  1. add_cover_logo(doc)    —— 封面左上角插入 FiberHome logo（inline，约 4.0cm x 1.3cm）
  2. apply_fh_header(doc,
        cover_text=...,     —— 封面节页眉（默认 FH/SDVCSBG/X.XXX.XXX（XXXXXX）/RB）
        body_text=...,      —— 正文节页眉（默认 SDV测试报告 + FH 编号；None=不区分节）
        body_first_text=... —— 正文首页页眉（可选）
     )

页眉规则（对齐参考样例）：
  - 封面节：右对齐、黑体、小五 FH/SDVCSBG/X.XXX.XXX（XXXXXX）/RB
  - 正文节：右对齐、黑体，「SDV测试报告」+ 空格 + FH 编号
  - 无分节文档（单 section）：直接挂封面节样式页眉

用法（生成器内）：
    from tools.docx_branding import add_cover_logo, apply_fh_header
    doc = Document()
    ...
    add_cover_logo(doc)          # 封面第一个段落
    ...标题/信息表...
    apply_fh_header(doc)         # 保存前调用（或分节后按节挂页眉）
"""
import os

from docx.document import Document as _Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ASSET_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fiberhome_logo.png")

# 参考样例页眉文案
FH_COVER_HEADER = "FH/SDVCSBG/X.XXX.XXX（XXXXXX）/RB"
FH_BODY_PREFIX = "SDV测试报告"


def add_cover_logo(doc, width_cm=4.0, align=WD_ALIGN_PARAGRAPH.LEFT):
    """在文档当前位置插入封面 logo 段落（参考样例：封面左上角，左对齐）。

    logo 原始尺寸 577x186，按参考样例 extent 1447800x466725 EMU
    （= 4.02cm x 1.30cm）等比缩放。
    """
    paras = doc.paragraphs
    if paras and not paras[0].text and not _para_has_image(paras[0]):
        p = paras[0]  # 复用文档首个空段落
    else:
        p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run()
    run.add_picture(ASSET_LOGO, width=Cm(width_cm))
    return p


def _para_has_image(p) -> bool:
    return bool(p._p.findall('.//' + qn('w:drawing')))


def _make_header_xml(text, font="黑体"):
    """构造右对齐黑体页眉 XML（对齐参考样例 header1.xml 结构）。"""
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<w:p><w:pPr><w:jc w:val="right"/><w:rPr>'
        f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}"/>'
        '</w:rPr></w:pPr>'
        f'<w:r><w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}"/>'
        f'<w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">{esc}</w:t></w:r>'
        '</w:p></w:hdr>'
    )


def apply_fh_header(doc: _Document,
                    cover_text: str = FH_COVER_HEADER,
                    body_text: str = None,
                    body_first_text: str = None):
    """为文档所有 section 挂 FH 页眉。

    - 单 section 文档：挂 cover_text（右对齐 FH 编号）。
    - 多 section 文档：第一个 section（封面节）挂 cover_text，
      其余 section 挂 body_text（若给定，格式「SDV测试报告 + 编号」）。
    页眉以 XML 直插方式创建（python-docx 无直接 set xml API），并确保
    「首页不同/奇偶不同」不会吞掉页眉。
    """
    sections = list(doc.sections)
    for i, sec in enumerate(sections):
        if i == 0:
            text = cover_text
        elif i == 1 and body_first_text is not None:
            text = body_first_text
        elif body_text is not None:
            text = body_text
        else:
            text = cover_text
        _attach_header_xml(sec, text)
        # 关闭首页不同/奇偶不同，保证每页都显示
        sec.different_first_page_header_footer = False
        try:
            sec.odd_and_even_pages_header_footer = False
        except AttributeError:
            pass


def _attach_header_xml(sec, text: str):
    """把页眉 XML 写入 section：替换 islinked 空页眉。"""
    hdr = sec.header
    hdr.is_linked_to_previous = False
    # 清空默认空段落内容，直接用底层 XML 重建
    hdr_el = hdr._element
    # 删除现有段落
    for p in list(hdr_el.findall(qn('w:p'))):
        hdr_el.remove(p)
    # 解析新 XML 并追加
    from docx.oxml import parse_xml
    new_hdr = parse_xml(_make_header_xml(text))
    for child in list(new_hdr):
        hdr_el.append(child)
