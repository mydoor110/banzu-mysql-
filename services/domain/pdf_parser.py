#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 解析领域函数
从 blueprints/performance.py 提取，供 services 和 blueprints 共同引用。
消除 services -> blueprints 的反向依赖。
"""
import re

# PDF解析正则表达式
HEADER_PERIOD_RE = re.compile(r"考核周期\s+(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
ROW_RE = re.compile(
    r"^\s*\d+\s+"
    r"(?P<emp_no>\d{1,20})\s+"
    r"(?P<name>[\u4e00-\u9fa5A-Za-z·.\-]{1,30})\s+"
    r"(?P<grade>A|B\+|B|C|D)\s+"
    r"(?P<score>\d+(?:\.\d+)?)\s+"
)


def extract_text_from_pdf(pdf_path):
    """从PDF提取文本"""
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # 移除tolerance参数以提升速度
                text += page.extract_text() or ""
                text += "\n"
        if text.strip():
            return text
    except Exception as exc:
        print("pdfplumber failed:", exc)

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        if text.strip():
            return text
    except Exception as exc:
        print("PyPDF2 failed:", exc)
    raise RuntimeError("无法从PDF提取文本，请确认PDF包含文本层并非扫描件。")


def parse_pdf_text(text: str):
    """解析PDF文本，提取绩效数据"""
    year, month = None, None
    m = HEADER_PERIOD_RE.search(text)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
    rows = []
    for line in text.splitlines():
        line = line.strip()
        m = ROW_RE.match(line)
        if not m:
            continue
        d = m.groupdict()
        rows.append({
            "emp_no": d["emp_no"],
            "name": d["name"],
            "grade": d["grade"],
            "score": float(d["score"]),
        })
    return year, month, rows
