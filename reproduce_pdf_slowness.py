import time
import sys
import os

def test_pdfplumber(pdf_path):
    print(f"\n--- Testing pdfplumber ---")
    start_time = time.time()
    text = ""
    try:
        import pdfplumber
        print(f"pdfplumber version: {pdfplumber.__version__}")
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_start = time.time()
                content = page.extract_text() or ""
                text += content + "\n"
                # print(f"  Page {i+1}: {time.time() - page_start:.4f}s")
        
        duration = time.time() - start_time
        print(f"pdfplumber Total Time: {duration:.4f}s")
        print(f"Extracted length: {len(text)}")
        return duration
    except ImportError:
        print("pdfplumber not installed")
        return None
    except Exception as e:
        print(f"pdfplumber failed: {e}")
        return None

def test_pypdf2(pdf_path):
    print(f"\n--- Testing PyPDF2 ---")
    start_time = time.time()
    text = ""
    try:
        import PyPDF2
        print(f"PyPDF2 version: {PyPDF2.__version__}")
        reader = PyPDF2.PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
            content = page.extract_text() or ""
            text += content + "\n"
        
        duration = time.time() - start_time
        print(f"PyPDF2 Total Time: {duration:.4f}s")
        print(f"Extracted length: {len(text)}")
        return duration
    except ImportError:
        print("PyPDF2 not installed")
        return None
    except Exception as e:
        print(f"PyPDF2 failed: {e}")
        return None

def test_pymupdf(pdf_path):
    print(f"\n--- Testing PyMuPDF (fitz) ---")
    start_time = time.time()
    text = ""
    try:
        import fitz
        print(f"PyMuPDF version: {fitz.__version__}")
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text() + "\n"
        
        duration = time.time() - start_time
        print(f"PyMuPDF Total Time: {duration:.4f}s")
        print(f"Extracted length: {len(text)}")
        return duration
    except ImportError:
        print("PyMuPDF (fitz) not installed")
        return None
    except Exception as e:
        print(f"PyMuPDF failed: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 reproduce_pdf_slowness.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    t1 = test_pdfplumber(pdf_path)
    t2 = test_pypdf2(pdf_path)
    t3 = test_pymupdf(pdf_path)

    print("\n=== Summary ===")
    if t1 is not None: print(f"pdfplumber: {t1:.4f}s")
    if t2 is not None: print(f"PyPDF2:     {t2:.4f}s")
    if t3 is not None: print(f"PyMuPDF:    {t3:.4f}s")
