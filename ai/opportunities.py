"""
AI-powered opportunity suggestions based on student's strong topics.

Returns top 2 listings per platform (jobs, events, hackathons) using
the same LLM client as the planner, with a rule-based fallback.
"""
from __future__ import annotations

import json
import os
import re

_USE_LLM = bool(
    (os.getenv("OPENAI_API_KEY"))
    or (
        os.getenv("AZURE_OPENAI_API_KEY")
        and os.getenv("AZURE_OPENAI_ENDPOINT")
        and os.getenv("AZURE_OPENAI_DEPLOYMENT")
    )
)

# Each entry shape:
# {
#   "title": str,
#   "organisation": str,
#   "location": str,
#   "blurb": str,
#   "platform": str,   # "LinkedIn" | "Jobstreet" | "Indeed" | "Symplicity" | "Eventbrite" | "Devpost"
#   "category": str,   # "job" | "event" | "hackathon"
#   "url": str,        # pre-filled deep-search URL (built by for_you.py)
# }

_PLATFORMS_JOB = ["LinkedIn", "Jobstreet", "Indeed", "Symplicity"]
_PLATFORMS_EVENT = ["LinkedIn", "Eventbrite"]
_PLATFORMS_HACK = ["LinkedIn", "Devpost", "Jobstreet"]


def _extract_json(text: str) -> list:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, flags=re.S)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\[.*\])", text, flags=re.S)
    if m:
        return json.loads(m.group(1))
    raise ValueError("Opportunities agent did not return a JSON array")


def _llm_suggestions(strong_topics: list[str]) -> list[dict]:
    from quiz.ai_client import get_client, get_model_or_deployment

    client = get_client()
    model = get_model_or_deployment()

    topics_str = ", ".join(strong_topics[:6])

    system = (
        "You are a career assistant for a university student. "
        "Based on their strongest academic topics, generate realistic and relevant "
        "opportunities (jobs, events, hackathons) they could apply for in Singapore or globally. "
        "Return ONLY a valid JSON array — no prose, no markdown wrapper."
    )

    user = f"""
Student's strongest topics: {topics_str}

Generate exactly 10 opportunity listings — mix of:
- 2 job listings on LinkedIn
- 2 job listings on Jobstreet
- 2 job listings on Indeed
- 2 events on LinkedIn or Eventbrite
- 2 hackathons on Devpost or LinkedIn
- Ensure the events/listings are within 1 month from current date.

Each listing must have these exact keys:
  "title"        – realistic role / event / hackathon name
  "organisation" – company, university, or organiser name
  "location"     – e.g. "Singapore (Hybrid)", "Remote", "Global"
  "blurb"        – 1 sentence why this matches the student's strengths
  "platform"     – one of: "LinkedIn", "Jobstreet", "Indeed", "Symplicity", "Eventbrite", "Devpost"
  "category"     – one of: "job", "event", "hackathon"

Return a JSON array of exactly 10 objects.
"""

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.5,
    )
    return _extract_json(resp.choices[0].message.content)


def _rule_based_suggestions(strong_topics: list[str]) -> list[dict]:
    """Deterministic fallback using strong topic names."""
    topic_a = strong_topics[0] if len(strong_topics) > 0 else "Data Science"
    topic_b = strong_topics[1] if len(strong_topics) > 1 else "Machine Learning"
    topic_c = strong_topics[2] if len(strong_topics) > 2 else "Statistics"

    return [
        # Jobs — LinkedIn
        {
            "title": f"{topic_a} Analyst Intern",
            "organisation": "Grab",
            "location": "Singapore (Hybrid)",
            "blurb": f"Leverage your {topic_a} strength for a data-driven role at a leading tech unicorn.",
            "platform": "LinkedIn",
            "category": "job",
        },
        {
            "title": f"Junior {topic_b} Engineer",
            "organisation": "Sea Group",
            "location": "Singapore",
            "blurb": f"Apply your {topic_b} skills to production ML systems at scale.",
            "platform": "LinkedIn",
            "category": "job",
        },
        # Jobs — Jobstreet
        {
            "title": f"{topic_a} Associate",
            "organisation": "DBS Bank",
            "location": "Singapore",
            "blurb": f"Use your {topic_a} expertise in a high-impact FinTech environment.",
            "platform": "Jobstreet",
            "category": "job",
        },
        {
            "title": f"Research Assistant — {topic_b}",
            "organisation": "NTU",
            "location": "Singapore (On-site)",
            "blurb": f"Deepen your {topic_b} knowledge through applied academic research.",
            "platform": "Jobstreet",
            "category": "job",
        },
        # Jobs — Indeed
        {
            "title": f"{topic_c} Consultant",
            "organisation": "McKinsey & Company",
            "location": "Singapore",
            "blurb": f"Bring your {topic_c} skills to data-driven strategy consulting.",
            "platform": "Indeed",
            "category": "job",
        },
        {
            "title": f"Data Scientist ({topic_a})",
            "organisation": "Shopee",
            "location": "Singapore (Remote-friendly)",
            "blurb": f"Build recommendation and prediction systems using your {topic_a} foundation.",
            "platform": "Indeed",
            "category": "job",
        },
        # Events
        {
            "title": f"{topic_a} & AI Summit Singapore 2026",
            "organisation": "SGTech",
            "location": "Marina Bay Sands, Singapore",
            "blurb": f"Network with industry leaders and researchers in {topic_a}.",
            "platform": "LinkedIn",
            "category": "event",
        },
        {
            "title": f"NUS {topic_b} Workshop Series",
            "organisation": "NUS Centre for Future-Ready Graduates",
            "location": "NUS, Singapore",
            "blurb": f"Hands-on sessions to sharpen your {topic_b} practical skills.",
            "platform": "Eventbrite",
            "category": "event",
        },
        # Hackathons
        {
            "title": f"Global {topic_a} Hackathon 2026",
            "organisation": "Devpost",
            "location": "Global (Online)",
            "blurb": f"Compete with teams worldwide to solve real-world {topic_a} challenges.",
            "platform": "Devpost",
            "category": "hackathon",
        },
        {
            "title": f"NUS Hack4Good — {topic_b} Track",
            "organisation": "NUS Students' Computing Club",
            "location": "Singapore (Hybrid)",
            "blurb": f"Build social-impact solutions powered by {topic_b}.",
            "platform": "LinkedIn",
            "category": "hackathon",
        },
    ]


def get_opportunity_suggestions(strong_topics: list[str]) -> list[dict]:
    """Return 10 opportunity listings (2 per platform group).

    Uses LLM if configured; otherwise rule-based.
    """
    if not strong_topics:
        return []
    if _USE_LLM:
        try:
            return _llm_suggestions(strong_topics)
        except Exception:
            pass
    return _rule_based_suggestions(strong_topics)
