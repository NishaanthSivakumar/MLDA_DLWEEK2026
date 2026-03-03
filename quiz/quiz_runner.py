from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from .utils import pdf_to_text
from .agents import quiz_agent


def extract_pdf_link_from_page(page_url: str) -> str | None:
    """MIT OCW pages usually contain a PDF link. We scrape the first .pdf href."""
    resp = requests.get(page_url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            if href.startswith("http"):
                return href
            # OCW relative links
            return "https://ocw.mit.edu" + href
    return None


def generate_quiz_from_url(
    *,
    student_id: str,
    lecture_id: int,
    lecture_title: str,
    lecture_url: str,
    profile_summary: str = "- No prior history.",
    n_questions: int = 8,
) -> dict:
    """End-to-end agentic quiz generation:
    lecture page -> PDF -> text -> QuizAgent.
    """

    pdf_url = extract_pdf_link_from_page(lecture_url)
    if not pdf_url:
        raise RuntimeError("No PDF found on the lecture page.")

    pdf_resp = requests.get(pdf_url, timeout=40)
    pdf_resp.raise_for_status()

    lecture_text = pdf_to_text(pdf_resp.content)
    if not lecture_text:
        raise RuntimeError("PDF text extraction failed (empty text).")

    quiz = quiz_agent(
        student_id=student_id,
        lecture_id=str(lecture_id),
        lecture_title=lecture_title,
        lecture_url=lecture_url,
        lecture_text=lecture_text,
        student_profile_summary=profile_summary,
        n_questions=n_questions,
    )

    # Keep the grounding text for grading/explainability (not shown in UI).
    quiz["_lecture_text"] = lecture_text
    quiz["_pdf_url"] = pdf_url
    return quiz
