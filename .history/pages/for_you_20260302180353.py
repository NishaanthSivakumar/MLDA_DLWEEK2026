"""
📌 For You — personalised insights, weekly plan & professor matches.
"""
from __future__ import annotations

import streamlit as st
from datetime import date
import json

from db_engine.topic_mastery import get_topic_summary
from db_engine.learning_state import classify_learning_state
from ai.planner import generate_weekly_plan
from prof_engine import match_professors
from config import path_in_project

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
CALENDAR_FILE = path_in_project("calendar_engine", "nus_calendar_2025_26.json")

USER_ID = "student_001"
COURSES = [
    {"name": "Machine Learning", "canvas_id": "machine_learning_2006"},
    {"name": "Financial Modelling", "canvas_id": "financial_modelling_2025"},
]

st.set_page_config(page_title="For You · LumiGRAD", layout="wide")


# ---------------------------------------------------
# CSS
# ---------------------------------------------------
st.markdown(
    """
<style>
.fy-section {
    border: 1px solid rgba(49,51,63,0.15);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 16px;
    background: rgba(255,255,255,0.02);
}
.fy-topic-weak {
    background: rgba(255,82,82,0.08);
    border-radius: 10px;
    padding: 8px 14px;
    margin-bottom: 6px;
}
.fy-topic-strong {
    background: rgba(76,175,80,0.10);
    border-radius: 10px;
    padding: 8px 14px;
    margin-bottom: 6px;
}
.prof-card {
    border: 1px solid rgba(49,51,63,0.18);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 12px;
    background: rgba(255,255,255,0.02);
}
.prof-match {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    background: rgba(33,150,243,0.12);
    color: #1565C0;
    margin-right: 4px;
}
.small-muted { color: rgba(250,250,250,0.55); font-size: 12px; }
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------
# ACADEMIC WEEK
# ---------------------------------------------------
with open(CALENDAR_FILE, "r") as f:
    semester_calendar = json.load(f)


def _get_week_number(today: date) -> int:
    for week in semester_calendar:
        start = date.fromisoformat(week["start"])
        end = date.fromisoformat(week["end"])
        if start <= today <= end:
            return int(week["week"])
        if today < start:
            return max(1, int(week["week"]) - 1)
    return int(semester_calendar[-1]["week"])


today = date.today()
current_week = _get_week_number(today)


# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------
gpa_target = st.sidebar.slider(
    "GPA Target", min_value=3.0, max_value=5.0, value=4.5, step=0.1
)

if st.sidebar.button("⬅ Back to Dashboard"):
    st.switch_page("landing.py")


# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
st.title("📌 For You")
st.caption("Personalised insights based on your quiz history, topic mastery, and professor research alignment.")
st.divider()


# ---------------------------------------------------
# PER-COURSE SECTIONS
# ---------------------------------------------------
for course in COURSES:
    st.header(f"📘 {course['name']}")

    state = classify_learning_state(USER_ID, course["canvas_id"])
    topics = get_topic_summary(USER_ID, course["canvas_id"], limit=5)
    weak = topics.get("weak", [])
    strong = topics.get("strong", [])

    # Learning state badge
    state_colors = {
        "IMPROVING": ("🟢", "#E8F5E9", "#1B5E20"),
        "STABLE":    ("🟡", "#FFF3E0", "#E65100"),
        "REGRESSING":("🔴", "#FFEBEE", "#B71C1C"),
        "INACTIVE":  ("⚪", "#F5F5F5", "#616161"),
        "NEW":       ("🔵", "#E3F2FD", "#1565C0"),
    }
    icon, bg, fg = state_colors.get(state["state"], ("🔵", "#E3F2FD", "#1565C0"))
    st.markdown(
        f"""<div style="background:{bg}; color:{fg}; padding:10px 16px;
        border-radius:10px; font-weight:600; font-size:14px; margin-bottom:12px;">
        {icon} Learning State: {state['state']} — {state['reason']}
        </div>""",
        unsafe_allow_html=True,
    )

    # Two columns: Weak | Strong
    col_w, col_s = st.columns(2)

    # ---- Weak Topics ----
    with col_w:
        st.subheader("⚠️ Weak Topics")
        if weak:
            for t in weak:
                acc = (t["correct"] / t["attempts"] * 100) if t["attempts"] else 0
                mastery_pct = t["mastery"] * 100
                bar_color = "#ef5350" if mastery_pct < 30 else "#ff9800" if mastery_pct < 60 else "#66bb6a"
                st.markdown(
                    f"""<div class="fy-topic-weak">
                        <strong>{t['topic']}</strong><br/>
                        <span class="small-muted">
                            Mastery {t['mastery']:.2f} · Accuracy {acc:.0f}% · Attempts {t['attempts']}
                        </span>
                        <div style="background:rgba(255,255,255,0.08); border-radius:4px;
                             height:6px; margin-top:6px;">
                            <div style="width:{mastery_pct:.0f}%; background:{bar_color};
                                 height:6px; border-radius:4px;"></div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No weak topics yet — take a quiz to build your learning profile.")

    # ---- Strong Topics ----
    with col_s:
        st.subheader("💪 Strong Topics")
        if strong:
            for t in strong:
                acc = (t["correct"] / t["attempts"] * 100) if t["attempts"] else 0
                mastery_pct = t["mastery"] * 100
                st.markdown(
                    f"""<div class="fy-topic-strong">
                        <strong>{t['topic']}</strong><br/>
                        <span class="small-muted">
                            Mastery {t['mastery']:.2f} · Accuracy {acc:.0f}% · Attempts {t['attempts']}
                        </span>
                        <div style="background:rgba(255,255,255,0.08); border-radius:4px;
                             height:6px; margin-top:6px;">
                            <div style="width:{mastery_pct:.0f}%; background:#66bb6a;
                                 height:6px; border-radius:4px;"></div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No strong topics yet — keep practising!")

    st.markdown("")

    # ---- Weekly Plan ----
    st.subheader("🗓️ Weekly Plan")

    plan_key = f"_plan_data_{course['canvas_id']}"

    if st.button(
        f"Generate weekly plan: {course['name']}",
        key=f"btn_plan_{course['canvas_id']}",
    ):
        plan = generate_weekly_plan(
            learning_state=state,
            weak_topics=weak,
            current_week=current_week,
            gpa_target=float(gpa_target),
        )
        st.session_state[plan_key] = plan

    plan = st.session_state.get(plan_key)
    if plan:
        actions = plan.get("priority_actions", [])
        DAY_LABELS = ["📅 Today", "📅 Day 2", "📅 Day 3", "📅 Day 4", "📅 Day 5"]
        DAY_COLORS = ["#1565C0", "#6A1B9A", "#00695C", "#E65100", "#AD1457"]

        # Pad actions to at least match the number of day columns we want
        n_days = max(len(actions), 4)
        day_cols = st.columns(n_days)

        for idx, col in enumerate(day_cols):
            label = DAY_LABELS[idx] if idx < len(DAY_LABELS) else f"📅 Day {idx + 1}"
            color = DAY_COLORS[idx % len(DAY_COLORS)]

            if idx < len(actions):
                a = actions[idx]
                action_text = a.get("action", "")
                duration = a.get("duration_min", "?")
                reason = a.get("reason", "")
                outcome = a.get("expected_outcome", "")

                card_html = f"""
                <div style="border:1px solid rgba(49,51,63,0.18); border-radius:14px;
                     padding:14px 16px; min-height:200px; background:rgba(255,255,255,0.02);">
                    <div style="font-size:13px; font-weight:700; color:{color};
                         margin-bottom:8px;">{label}</div>
                    <div style="font-size:14px; font-weight:600; margin-bottom:6px;">{action_text}</div>
                    <div style="font-size:12px; color:rgba(250,250,250,0.6); margin-bottom:4px;">
                        ⏱ {duration} min
                    </div>
                    <div style="font-size:11px; color:rgba(250,250,250,0.45); margin-bottom:4px;">
                        {reason}
                    </div>
                """
                if outcome:
                    card_html += f"""<div style="font-size:11px; color:rgba(250,250,250,0.45);">
                        🎯 {outcome}
                    </div>"""
                card_html += "</div>"
                col.markdown(card_html, unsafe_allow_html=True)
            else:
                col.markdown(
                    f"""
                    <div style="border:1px dashed rgba(49,51,63,0.15); border-radius:14px;
                         padding:14px 16px; min-height:200px; display:flex;
                         align-items:center; justify-content:center;">
                        <div style="text-align:center; color:rgba(250,250,250,0.25);">
                            <div style="font-size:13px; font-weight:700;">{label}</div>
                            <div style="font-size:11px; margin-top:4px;">Rest / Catch up</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        if plan.get("note"):
            st.caption(f"💡 {plan['note']}")
    else:
        st.caption("Click the button above to generate a personalised study plan.")

    st.markdown("")

    # ---- Professor Recommendations ----
    st.subheader("🎓 Recommended Professors")
    st.caption(
        "Professors whose research interests align with your **strong topics**. "
        "A great way to explore deeper or find a potential supervisor!"
    )

    if strong:
        matches = match_professors(strong, top_n=5)
        if matches:
            for prof in matches:
                matched_badges = "".join(
                    f'<span class="prof-match">{m}</span>' for m in prof["matched_topics"]
                )
                areas_str = ", ".join(prof["research_areas"])
                score_pct = prof["match_score"] * 100
                st.markdown(
                    f"""<div class="prof-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <strong style="font-size:16px;">
                                    <a href="{prof['url']}" target="_blank"
                                       style="text-decoration:none; color:inherit;">
                                        {prof['name']}
                                    </a>
                                </strong>
                                <span class="small-muted" style="margin-left:8px;">{prof['title']}</span>
                            </div>
                            <div style="font-size:13px; font-weight:600; color:#42A5F5;">
                                {score_pct:.0f}% match
                            </div>
                        </div>
                        <div class="small-muted" style="margin-top:4px;">
                            Research: {areas_str}
                        </div>
                        <div style="margin-top:6px;">{matched_badges}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No strong matches found yet. Keep building your strengths!")
    else:
        st.info("Build your strong topics first — take more quizzes to unlock professor recommendations.")

    st.divider()


# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------
st.caption("Data sourced from NUS Department of Statistics & Data Science faculty directory.")
