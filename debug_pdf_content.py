import sys
import os
import re

HEADER_PERIOD_RE = re.compile(r"考核周期\s+(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
ROW_RE = re.compile(
    r"^\s*\d+\s+"
    r"(?P<emp_no>\d{1,20})\s+"
    r"(?P<name>[\u4e00-\u9fa5A-Za-z·.\-]{1,30})\s+"
    r"(?P<grade>A|B\+|B|C|D)\s+"
    r"(?P<score>\d+(?:\.\d+)?)\s+"
)

def test_extraction_content(pdf_path):
    print(f"Analyzing {pdf_path}...")
    
    # 1. PyMuPDF Extraction
    print("\n--- PyMuPDF Output Preview ---")
    pymupdf_text = ""
    try:
        import fitz
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text = page.get_text()
                # PyMuPDF默认提取可能保留了布局空格，或者完全不同的顺序
                pymupdf_text += text + "\n"
        
        print("First 500 chars:")
        print(pymupdf_text[:500])
        print("-" * 20)
        
        # Try parsing
        count = 0
        for line in pymupdf_text.splitlines():
            if ROW_RE.match(line.strip()):
                count += 1
        print(f"Matched rows: {count}")

    except Exception as e:
        print(f"PyMuPDF failed: {e}")

    # 2. pdfplumber Extraction (Format Reference)
    # 我们可以尝试模拟 pdfplumber 的输出格式，或者虽然它慢，但它是“正确”的格式
    # 由于环境限制可能无法运行 pdfplumber，我们主要通过 PyMuPDF 的输出来调试正则

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 debug_pdf_content.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    test_extraction_content(pdf_path)
