from __future__ import annotations

import json
import re
from typing import Any

from .ai_client import get_client, get_model_or_deployment


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction (handles occasional extra prose)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty model response")

    try:
        return json.loads(text)
    except Exception:
        pass

    # fenced code block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if m:
        return json.loads(m.group(1))

    # first JSON object
    m = re.search(r"(\{.*\})", text, flags=re.S)
    if m:
        return json.loads(m.group(1))

    raise ValueError("Model did not return valid JSON")


def _chat_json(*, system: str, user: str) -> dict:
    client = get_client()
    model = get_model_or_deployment()

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return _extract_json(resp.choices[0].message.content)


def quiz_agent(
    *,
    student_id: str,
    lecture_id: str,
    lecture_title: str,
    lecture_url: str,
    lecture_text: str,
    student_profile_summary: str,
    n_questions: int = 8,
) -> dict[str, Any]:
    """Agentic quiz generator grounded in lecture text."""

    system = (
        "You are QuizAgent. Generate personalized active-recall questions grounded ONLY in the lecture text. "
        "Return ONLY valid JSON (no markdown, no prose)."
    )

    user = f"""
STUDENT_ID: {student_id}
LECTURE_ID: {lecture_id}
LECTURE_TITLE: {lecture_title}
LECTURE_URL: {lecture_url}

STUDENT_PROFILE_SUMMARY:
{student_profile_summary or '- No prior history.'}

RULES:
- Generate exactly {n_questions} questions.
- Mix ~70% mcq and ~30% short_answer.
- Each question must include why_this_question.
- For mcq: 4 options and answer_index (0..3).
- For short_answer: answer_text.

ABSTRACTION & TAGGING RULES:
- Before generating questions, internally identify 4–7 HIGH-LEVEL DOMAINS from the lecture.
- A DOMAIN is a broad conceptual area (e.g., "Linear Models", "Optimization", "Model Evaluation", "Generalization").
- A DOMAIN must NOT be a specific algorithm, formula, parameter, or implementation detail.
- Bad domains (too low-level): "Perceptron Algorithm", "Margin Violations", "Offset Parameter", "Convergence".
- Good domains (high-level): "Linear Classification", "Optimization Theory", "Generalization", "Loss Functions".

- Each question MUST include:
    - "domain": one of the identified high-level domains
    - "subtopic": a specific concept that explicitly appears in the lecture text

- The domain MUST be reused across multiple questions.
- Do NOT invent a new domain for each question.
- Domains should represent conceptual clusters, not specific terms.

OUTPUT JSON SHAPE:
{{
  "student_id": "{student_id}",
  "lecture_id": {lecture_id},
  "lecture_title": "{lecture_title}",
  "lecture_url": "{lecture_url}",
  "questions": [
    {{
      "question_id": "q1",
      "question_type": "mcq",
      "difficulty": 3,
      "topic_tags": ["tag1"],
      "question": "...",
      "why_this_question": "...",
      "options": ["A","B","C","D"],
      "answer_index": 2
    }}
  ]
}}

LECTURE_TEXT:
{lecture_text}
"""

    return _chat_json(system=system, user=user)


def grader_agent(
    *,
    student_id: str,
    lecture_id: int,
    lecture_text: str,
    quiz_questions: list[dict],
    student_answers: dict,
) -> dict[str, Any]:
    """LLM-based grading for explainable feedback."""

    system = (
        "You are GraderAgent. Grade student answers using ONLY lecture text and the provided questions. "
        "Be strict, identify misconceptions, and return ONLY valid JSON (no prose)."
    )

    user = f"""
STUDENT_ID: {student_id}
LECTURE_ID: {lecture_id}

LECTURE_TEXT:
{lecture_text}

QUIZ_QUESTIONS_JSON:
{json.dumps(quiz_questions)}

STUDENT_ANSWERS_JSON:
{json.dumps(student_answers)}

OUTPUT JSON SHAPE:
{{
  "results": [
    {{
      "question_id": "q1",
      "is_correct": true,
      "score_0_to_1": 1.0,
      "feedback": "...",
      "common_misconception": "..."
    }}
  ]
}}
"""

    return _chat_json(system=system, user=user)


def resource_recommender_agent(
    *,
    wrong_questions: list[dict],
    lecture_title: str,
) -> dict[str, Any]:
    """For each incorrectly-answered question, recommend YouTube videos and
    published papers with direct URLs to help the student learn."""

    system = (
        "You are ResourceAgent. For each incorrectly-answered question, recommend "
        "learning resources to help the student master the underlying concepts.\n"
        "Rules:\n"
        "- Provide 1-2 YouTube video URLs and 1-2 academic/published paper URLs per question.\n"
        "- YouTube URLs MUST be real, well-known educational channels (3Blue1Brown, StatQuest, "
        "MIT OpenCourseWare, Stanford Online, etc.). Use the format https://www.youtube.com/results?search_query=<url-encoded-topic> "
        "if you are not 100%% certain of the exact video ID.\n"
        "- Paper URLs should point to arxiv.org, IEEE, ACM DL, or Google Scholar search. "
        "Use https://scholar.google.com/scholar?q=<url-encoded-topic> if unsure of the exact paper URL.\n"
        "- Every URL must be a direct, clickable link.\n"
        "- Return ONLY valid JSON (no markdown, no prose)."
    )

    questions_payload = []
    for q in wrong_questions:
        questions_payload.append({
            "question_id": q["question_id"],
            "question": q["question"],
            "topic_tags": q["topic_tags"],
        })

    user = f"""
LECTURE_TITLE: {lecture_title}

INCORRECT QUESTIONS:
{json.dumps(questions_payload, indent=2)}

OUTPUT JSON SHAPE:
{{
  "resources": [
    {{
      "question_id": "q1",
      "youtube": [
        {{"title": "...", "url": "https://..."}}
      ],
      "papers": [
        {{"title": "...", "url": "https://..."}}
      ]
    }}
  ]
}}
"""

    return _chat_json(system=system, user=user)

    return _chat_json(system=system, user=user)
