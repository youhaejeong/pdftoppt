from pathlib import Path

import fitz


class PDFParser:
    @staticmethod
    def extract_text(pdf_path: Path) -> str:
        doc = fitz.open(pdf_path)
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(pages).strip()
