from __future__ import annotations

import io
from pypdf import PdfReader


def pdf_to_text(pdf_bytes: bytes, max_pages: int = 8) -> str:
    """Extract text from the first N pages of a PDF (fast + good enough for quizzes)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts: list[str] = []
    for page in reader.pages[:max_pages]:
        texts.append(page.extract_text() or "")
    return "\n".join(texts).strip()
