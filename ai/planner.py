from __future__ import annotations

import os
import json
import re
import math

# Optional LLM (OpenAI or Azure OpenAI). If not configured, we fall back to rule-based planning.
_USE_LLM = bool(
    (os.getenv("OPENAI_API_KEY"))
    or (os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_DEPLOYMENT"))
)

ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\{.*\})", text, flags=re.S)
    if m:
        return json.loads(m.group(1))
    raise ValueError("Planner did not return JSON")


def _llm_plan(*, learning_state: dict, weak_topics: list[dict], current_week: int, gpa_target: float) -> dict:
    from quiz.ai_client import get_client, get_model_or_deployment

    client = get_client()
    model = get_model_or_deployment()

    system = (
        "You are PlannerAgent for a study dashboard. Create a short 7-day plan that is actionable and explainable. "
        "Return ONLY valid JSON."
    )

    user = {
        "current_week": current_week,
        "gpa_target": gpa_target,
        "learning_state": learning_state,
        "weak_topics": weak_topics[:5],
        "constraints": {
            "max_actions": 5,
            "each_action_minutes": [15, 60],
            "must_include_reason": True,
        },
        "output_schema": {
            "learning_state": "string",
            "top_blockers": ["string"],
            "priority_actions": [
                {
                    "action": "string",
                    "duration_min": 30,
                    "reason": "string",
                    "expected_outcome": "string"
                }
            ],
            "note": "string"
        }
    }

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"INPUT_JSON:\n{json.dumps(user)}"},
        ],
        temperature=0.3,
    )
    return _extract_json(resp.choices[0].message.content)


def _rule_based_plan(*, learning_state: dict, weak_topics: list[dict], current_week: int, gpa_target: float) -> dict:
    actions = []

    if learning_state["state"] == "INACTIVE":
        actions.append({
            "action": "Restart with a light quiz (3 questions) on your weakest topic",
            "duration_min": 20,
            "reason": learning_state["reason"],
        })
        actions.append({
            "action": "Review the last completed lecture slides and write 3 takeaways",
            "duration_min": 25,
            "reason": "Rebuild momentum after inactivity.",
        })
    elif learning_state["state"] == "REGRESSING":
        actions.append({
            "action": "Redo your last quiz attempt and focus on misconceptions",
            "duration_min": 30,
            "reason": learning_state["reason"],
        })

    # Always include weakest-topic actions
    for t in weak_topics[:2]:
        topic = t.get("topic", "topic")
        mastery = t.get("mastery", 0.0)
        actions.append({
            "action": f"Targeted practice: 5 questions on '{topic}'",
            "duration_min": 25,
            "reason": f"Low mastery ({mastery:.2f}).",
        })

    # Keep it short and actionable
    actions = actions[:4]

    return {
        "learning_state": learning_state["state"],
        "gpa_target": gpa_target,
        "current_week": current_week,
        "top_blockers": [learning_state["reason"]],
        "priority_actions": actions,
        "note": "This plan is generated from your quiz performance, topic mastery, and recent activity.",
    }


def generate_weekly_plan(
    *,
    learning_state: dict,
    weak_topics: list[dict],
    current_week: int,
    gpa_target: float,
) -> dict:
    """Return a short plan. Uses LLM if configured; otherwise rule-based."""
    if _USE_LLM:
        try:
            return _llm_plan(
                learning_state=learning_state,
                weak_topics=weak_topics,
                current_week=current_week,
                gpa_target=gpa_target,
            )
        except Exception:
            pass

    return _rule_based_plan(
        learning_state=learning_state,
        weak_topics=weak_topics,
        current_week=current_week,
        gpa_target=gpa_target,
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMBINED MULTI-COURSE WEEKLY PLAN
# ─────────────────────────────────────────────────────────────────────────────

def _llm_combined_plan(
    *,
    all_courses: list[dict],
    current_week: int,
    gpa_target: float,
    available_hours_per_day: float,
    study_days: list[str],
) -> list[dict]:
    """LLM-based combined 7-day schedule across all courses."""
    from quiz.ai_client import get_client, get_model_or_deployment

    client = get_client()
    model = get_model_or_deployment()

    system = (
        "You are PlannerAgent for a university student dashboard. "
        "Generate a realistic day-by-day study schedule for the week that covers ALL modules. "
        "Each study day must fit within the student's committed hours. "
        "Return ONLY a valid JSON array — no prose, no markdown wrapper."
    )

    user = {
        "current_week": current_week,
        "gpa_target": gpa_target,
        "available_hours_per_day": available_hours_per_day,
        "study_days": study_days,
        "rest_days": [d for d in ALL_DAYS if d not in study_days],
        "courses": [
            {
                "name": c["name"],
                "learning_state": c["learning_state"]["state"],
                "learning_reason": c["learning_state"]["reason"],
                "weak_topics": [
                    {"topic": t["topic"], "mastery": round(t["mastery"], 2),
                     "accuracy_pct": round(t["correct"] / t["attempts"] * 100, 0) if t["attempts"] else 0}
                    for t in c["weak_topics"][:3]
                ],
                "strong_topics": [t["topic"] for t in c["strong_topics"][:3]],
            }
            for c in all_courses
        ],
        "instructions": (
            "Return a JSON array of exactly 7 objects, one per day of the week "
            "(Monday through Sunday), in order. "
            "For study days: include a 'tasks' list where each task has: "
            "  'module' (course name), 'action' (specific task), "
            "  'duration_min' (integer, must fit within available_hours_per_day * 60 total), "
            "  'reason' (why this task), 'expected_outcome' (what they'll achieve). "
            "For rest days: 'tasks' should be an empty list and 'rest' should be true. "
            "Distribute modules fairly across study days. "
            "Prioritise weak topics and modules with lower mastery. "
            "Each object must have: 'day' (string), 'tasks' (array), 'rest' (bool), "
            "'total_min' (sum of task durations), 'day_focus' (1-sentence theme for the day)."
        ),
    }

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"INPUT_JSON:\n{json.dumps(user)}"},
        ],
        temperature=0.4,
    )
    raw = resp.choices[0].message.content or ""
    raw = raw.strip()
    # Extract JSON array
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, flags=re.S)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\[.*\])", raw, flags=re.S)
    if m:
        return json.loads(m.group(1))
    raise ValueError("Combined planner did not return a JSON array")


def _rule_based_combined_plan(
    *,
    all_courses: list[dict],
    current_week: int,
    gpa_target: float,
    available_hours_per_day: float,
    study_days: list[str],
) -> list[dict]:
    """Deterministic fallback: distributes weak-topic tasks across study days."""
    budget_min = int(available_hours_per_day * 60)

    # Build a flat task pool, alternating between courses
    task_pool: list[dict] = []
    max_per_course = 6
    for course in all_courses:
        course_tasks: list[dict] = []
        state = course["learning_state"]["state"]
        if state in ("REGRESSING", "INACTIVE"):
            course_tasks.append({
                "module": course["name"],
                "action": f"Review recent lecture notes for {course['name']}",
                "duration_min": 30,
                "reason": course["learning_state"]["reason"],
                "expected_outcome": "Rebuild familiarity with core concepts.",
            })
        for t in course["weak_topics"][:3]:
            topic = t.get("topic", "topic")
            mastery = t.get("mastery", 0.0)
            acc = round(t["correct"] / t["attempts"] * 100, 0) if t.get("attempts") else 0
            course_tasks.append({
                "module": course["name"],
                "action": f"Practice 5 quiz questions on '{topic}'",
                "duration_min": 25,
                "reason": f"Mastery {mastery:.2f}, accuracy {acc:.0f}% — needs reinforcement.",
                "expected_outcome": f"Improve mastery of '{topic}' above 0.60.",
            })
        # Add a revision sweep
        course_tasks.append({
            "module": course["name"],
            "action": f"Review strong topics for {course['name']} — attempt harder questions",
            "duration_min": 20,
            "reason": "Consolidate existing strengths.",
            "expected_outcome": "Maintain and deepen strong-topic mastery.",
        })
        task_pool.extend(course_tasks[:max_per_course])

    # Distribute tasks across study days within budget
    schedule: list[dict] = []
    task_idx = 0
    for day in ALL_DAYS:
        if day not in study_days:
            schedule.append({"day": day, "tasks": [], "rest": True, "total_min": 0,
                              "day_focus": "Rest and recharge — no tasks scheduled."})
            continue

        day_tasks: list[dict] = []
        used_min = 0
        while task_idx < len(task_pool):
            t = task_pool[task_idx]
            if used_min + t["duration_min"] > budget_min:
                break
            day_tasks.append(t)
            used_min += t["duration_min"]
            task_idx += 1

        modules_today = list({t["module"] for t in day_tasks})
        focus = f"Focus: {' + '.join(modules_today)}" if modules_today else "Light review day"
        schedule.append({
            "day": day, "tasks": day_tasks, "rest": len(day_tasks) == 0,
            "total_min": used_min, "day_focus": focus,
        })

    return schedule


def generate_combined_weekly_plan(
    *,
    all_courses: list[dict],
    current_week: int,
    gpa_target: float,
    available_hours_per_day: float,
    study_days: list[str],
) -> list[dict]:
    """Return a 7-day combined schedule across all modules.

    all_courses: list of {name, learning_state, weak_topics, strong_topics}
    Returns a list of 7 day-dicts (Monday→Sunday).
    Uses LLM if configured; otherwise rule-based.
    """
    if _USE_LLM:
        try:
            return _llm_combined_plan(
                all_courses=all_courses,
                current_week=current_week,
                gpa_target=gpa_target,
                available_hours_per_day=available_hours_per_day,
                study_days=study_days,
            )
        except Exception:
            pass

    return _rule_based_combined_plan(
        all_courses=all_courses,
        current_week=current_week,
        gpa_target=gpa_target,
        available_hours_per_day=available_hours_per_day,
        study_days=study_days,
    )
