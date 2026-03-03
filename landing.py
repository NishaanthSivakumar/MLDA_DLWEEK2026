from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

import streamlit as st

from lecture_tracker import start_lecture, mark_lecture_complete, mark_lecture_incomplete
from db_engine.get_readiness import get_module_readiness, get_overall_readiness, get_cumulative_lectures_completed, get_course_lectures_completed
from db_engine.learning_state import classify_learning_state
from db_engine.lookup import get_lecture_db_id


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
from config import path_in_project
CALENDAR_FILE = path_in_project("calendar_engine", "nus_calendar_2025_26.json")

USER_ID = "student_001"
COURSES = [
    {"name": "Machine Learning", "canvas_id": "machine_learning_2006"},
    {"name": "Financial Modelling", "canvas_id": "financial_modelling_2025"},
]

st.set_page_config(page_title="LumiGRAD", layout="wide")


# ---------------------------------------------------
# CSS: compact buttons + clean cards
# ---------------------------------------------------
st.markdown(
    """
<style>
/* ---- Global typography ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

/* ---- Compact buttons ---- */
div.stButton > button, div.stLinkButton a {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 12px !important;
    padding: 6px 10px !important;
    height: 34px !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
    transition: all 0.15s ease !important;
}
div.stButton > button:hover { opacity: 0.85 !important; }

/* ---- Done (completed) button — green tint ---- */
div.stButton > button[kind="secondary"][data-testid] {
    border: 1.5px solid rgba(76,175,80,0.5) !important;
}

/* ---- KPI cards ---- */
.kpi-card {
    border: 1px solid rgba(49, 51, 63, 0.15);
    border-radius: 10px;
    padding: 16px 18px;
    background: rgba(255,255,255,0.025);
}
.kpi-card .small-muted { margin-top: 2px; }

/* ---- Utility classes ---- */
.small-muted { color: rgba(250,250,250,0.55); font-size: 12px; line-height: 1.5; }
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

/* ---- Course header row ---- */
.week-header {
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    color: rgba(250,250,250,0.6);
    padding: 6px 0;
}

/* ---- Section spacing ---- */
[data-testid="stVerticalBlock"] > div:has(> hr) { margin: 4px 0 !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------
# CALENDAR HELPERS
# ---------------------------------------------------
with open(CALENDAR_FILE, "r") as f:
    semester_calendar = json.load(f)


def get_current_week_label(today: date) -> str:
    for week in semester_calendar:
        start = date.fromisoformat(week["start"])
        end = date.fromisoformat(week["end"])
        if start <= today <= end:
            return f"Week {week['week']}"
    return "Recess Week"


def get_current_academic_week_number(today: date) -> int:
    """If today is in-between defined weeks (e.g., recess), return last completed academic week."""
    for week in semester_calendar:
        start = date.fromisoformat(week["start"])
        end = date.fromisoformat(week["end"])

        if start <= today <= end:
            return int(week["week"])

        if today < start:
            return max(1, int(week["week"]) - 1)

    return int(semester_calendar[-1]["week"])


# ---------------------------------------------------
# RISK (NUS GPA band view) – simple + explainable
# ---------------------------------------------------
def nus_band(gpa: float) -> str:
    if gpa >= 4.5:
        return "First Class Honours"
    if gpa >= 4.0:
        return "Second Upper"
    if gpa >= 3.5:
        return "Second Lower"
    if gpa >= 3.0:
        return "Third Class"
    return "Pass"


def risk_label_from_gap(gap: float) -> str:
    if gap <= 0:
        return "Low"
    if gap <= 0.3:
        return "Moderate"
    return "High"


def risk_colors(risk_label: str) -> tuple[str, str]:
    if risk_label == "Low":
        return "#E8F5E9", "#1B5E20"
    if risk_label == "Moderate":
        return "#FFF3E0", "#E65100"
    return "#FFEBEE", "#B71C1C"


# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------
today = date.today()
current_week_number = get_current_academic_week_number(today)
current_week_label = get_current_week_label(today)

# ---------------------------------------------------
# HEADER + WELLNESS SIDE PANEL
# ---------------------------------------------------

left_col, right_col = st.columns([3, 1])

with left_col:
    st.markdown(
        """<div style="margin-bottom: 0px;">
            <span style="font-size: 32px; font-weight: 700; letter-spacing: -0.5px;">🎓 LumiGRAD</span>
            <span style="font-size: 14px; color: rgba(250,250,250,0.5); margin-left: 12px; font-weight: 500;">Student Dashboard</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(f"📅 {current_week_label} · Academic Year 2025/26")

    nav1, nav2, _ = st.columns([1, 1, 3])
    with nav1:
        if st.button("📊 Quiz History", use_container_width=True):
            st.session_state["student_id"] = USER_ID
            st.switch_page("pages/quiz_history.py")
    with nav2:
        if st.button("📌 For You", use_container_width=True):
            st.session_state["student_id"] = USER_ID
            st.switch_page("pages/for_you.py")

with right_col:

    overall_states = [
        classify_learning_state(USER_ID, c["canvas_id"])["state"]
        for c in COURSES
    ]

    if "NEEDS ATTENTION" in overall_states:
        bg = "rgba(244,67,54,0.08)"
        border = "rgba(244,67,54,0.3)"
        title = "💛 Needs Attention"
        text = "We noticed a dip. Every setback is a setup for a comeback. One focused session can turn this around 💪. Alternatively, reach out to a guidance counselor if you need support."

    elif "INACTIVE" in overall_states:
        bg = "rgba(158,158,158,0.08)"
        border = "rgba(158,158,158,0.3)"
        title = "👀 Low Activity"
        text = "If you're resting intentionally, great. If not, try restarting small."

    elif "IMPROVING" in overall_states:
        bg = "rgba(76,175,80,0.08)"
        border = "rgba(76,175,80,0.3)"
        title = "🌿 On Track"
        text = "Keep the momentum going — every quiz you complete compounds your mastery. 🚀"

    else:
        bg = "rgba(255,152,0,0.08)"
        border = "rgba(255,152,0,0.3)"
        title = "⚖️ Steady"
        text = "You are doing great. Remember to have fun too!"

    st.markdown(
        f"""
        <div style="
            background:{bg};
            border:1px solid {border};
            border-radius:12px;
            padding:14px;
            font-size:12px;
        ">
            <div style="font-weight:700; margin-bottom:4px;">{title}</div>
            <div style="opacity:0.8;">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Top KPIs
gpa_target = st.sidebar.slider("GPA Target", min_value=3.0, max_value=5.0, value=4.5, step=0.1)

overall_readiness = get_overall_readiness(USER_ID, current_week_number)
gap = gpa_target - round((overall_readiness / 100.0) * 5.0, 2)
risk = risk_label_from_gap(gap)
bg_color, text_color = risk_colors(risk)

lectures_done, lectures_total = get_cumulative_lectures_completed(USER_ID, current_week_number)

state_overall = classify_learning_state(USER_ID)

k1, k2, k3, k4 = st.columns(4)

k1.metric("Overall Readiness", f"{overall_readiness:.1f}%")
k2.metric("Lectures Completed", f"{lectures_done} / {lectures_total}",
          help=f"Cumulative lectures marked complete up to {current_week_label}")

# Per-module breakdown below the Lectures Completed KPI
_module_lines = ""
for _c in COURSES:
    _c_done, _c_total = get_course_lectures_completed(USER_ID, _c["canvas_id"], current_week_number)
    _c_left = _c_total - _c_done
    _c_color = "#ef5350" if _c_left > 0 else "#66bb6a"
    _module_lines += (
        f'<div style="display:flex; justify-content:space-between; '
        f'align-items:center; margin-bottom:3px;">'
        f'<span style="font-size:11px; color:rgba(250,250,250,0.6);">{_c["name"]}</span>'
        f'<span style="font-size:11px; font-weight:600; color:{_c_color};">'
        f'{_c_done}/{_c_total} · {_c_left} left</span></div>'
    )
k2.markdown(
    f'<div style="margin-top:6px;">{_module_lines}</div>',
    unsafe_allow_html=True,
)

_STATE_META = {
    "IMPROVING":  ("🟢", "#1B5E20", "rgba(76,175,80,0.10)"),
    "STABLE":     ("🟡", "#E65100", "rgba(255,152,0,0.10)"),
    "NEEDS ATTENTION": ("🔴", "#B71C1C", "rgba(244,67,54,0.10)"),
    "INACTIVE":   ("⚪", "#616161", "rgba(158,158,158,0.10)"),
    "NEW":        ("🔵", "#1565C0", "rgba(33,150,243,0.10)"),
}
_MOTIVATIONAL_QUOTES = {
    "IMPROVING":  ("Keep the momentum going — every quiz you complete compounds your mastery.", "🚀"),
    "STABLE":     ("Consistency is a superpower. Stay the course and the results will follow.", "🎯"),
    "NEEDS ATTENTION": ("Every setback is a setup for a comeback. One focused session can turn this around.", "💪"),
    "INACTIVE":   ("The best time to restart was yesterday — the second-best time is right now.", "⚡"),
    "NEW":        ("Welcome aboard! Small daily habits now will pay huge dividends by finals.", "🌱"),
}

_s_icon, _s_text_color, _s_bg = _STATE_META.get(
    state_overall["state"], ("🔵", "#1565C0", "rgba(33,150,243,0.10)")
)
_quote_text, _quote_icon = _MOTIVATIONAL_QUOTES.get(
    state_overall["state"], ("You've got this — keep pushing forward.", "✨")
)

k3.markdown(
    f"""
    <div class="kpi-card" style="background:{_s_bg}; height:100%;">
      <div class="small-muted" style="margin-bottom:6px;">Learning State</div>
      <div style="font-size:20px; font-weight:700; letter-spacing:-0.3px; color:{_s_text_color};">
        {_s_icon} {state_overall['state']}
      </div>
      <div class="small-muted" style="margin-top:6px; font-size:11px; line-height:1.5;">
        {state_overall['reason']}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
k4.markdown(
    f"""
    <div class="kpi-card" style="height:100%;">
      <div class="small-muted" style="margin-bottom:6px;">Target Band</div>
      <div style="font-size:20px; font-weight:700; letter-spacing:-0.3px;">
        {nus_band(gpa_target)}
      </div>
      <div class="small-muted" style="margin-top:6px; font-size:11px;">
        GPA target: {gpa_target:.1f}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.progress(overall_readiness / 100.0)

# Motivational quote banner
st.markdown(
    f"""
    <div style="
        background:{_s_bg};
        border: 1px solid {_s_text_color}33;
        border-radius: 12px;
        padding: 14px 20px;
        margin-top: 12px;
        display: flex;
        align-items: center;
        gap: 12px;
    ">
        <span style="font-size:24px;">{_quote_icon}</span>
        <span style="font-size:13px; font-weight:500; color:rgba(250,250,250,0.85); line-height:1.5;">
            {_quote_text}
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div style="
        background-color: {bg_color};
        padding: 12px 16px;
        border-radius: 12px;
        margin-top: 10px;
        font-weight: 700;
        color: {text_color};
        font-size: 14px;
        border: 1px solid rgba(0,0,0,0.08);
    ">
        Risk of not achieving GPA {gpa_target:.2f}: {risk}
        <span style="font-weight:500;">(Target band: {nus_band(gpa_target)})</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()
st.markdown("<div style='font-size:20px; font-weight:700; letter-spacing:-0.3px; margin-bottom:8px;'>Course Tracker</div>", unsafe_allow_html=True)

weeks = list(range(1, 14))

# Header
header_cols = st.columns([3] + [1] * len(weeks))
header_cols[0].markdown("<div class='week-header' style='text-align:left; font-size:14px;'>Course</div>", unsafe_allow_html=True)
for i, wk in enumerate(weeks):
    if wk == 7:
        label = "🌴"
    elif wk <= current_week_number:
        label = f"W{wk}"
    else:
        label = f"<span style='opacity:0.3;'>W{wk}</span>"
    header_cols[i + 1].markdown(f"<div class='week-header'>{label}</div>", unsafe_allow_html=True)

st.divider()


# Load tracker data (minimal, using your existing tables)
def load_course_tracker(user_canvas_id: str, course_canvas_id: str):
    from db_engine.db import get_connection
    from db_engine.lookup import get_user_id, get_course_id

    user_id = get_user_id(user_canvas_id)
    course_id = get_course_id(course_canvas_id)
    if user_id is None or course_id is None:
        return None

    weeks_dict = {wk: {"lecture_status": "NOT_STARTED", "lecture_link": None} for wk in range(1, 14)}
    weeks_dict[7] = None

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT l.week_number, l.canvas_slide_url, lp.status
        FROM lectures l
        LEFT JOIN lecture_progress lp
          ON l.id = lp.lecture_id AND lp.user_id = ?
        WHERE l.course_id = ?
        ORDER BY l.week_number
        """,
        (user_id, course_id),
    )
    rows = cur.fetchall()
    conn.close()

    for r in rows:
        wk = r["week_number"]
        if wk == 7:
            continue
        weeks_dict[wk]["lecture_status"] = r["status"] or "NOT_STARTED"
        weeks_dict[wk]["lecture_link"] = r["canvas_slide_url"]

    return weeks_dict


# Course rows
for course in COURSES:
    course_data = load_course_tracker(USER_ID, course["canvas_id"])
    if not course_data:
        continue

    row_cols = st.columns([3] + [1] * len(weeks), vertical_alignment="top")
    
    with row_cols[0]:
        mod_readiness = get_module_readiness(USER_ID, course["canvas_id"], current_week_number)
        st.markdown(f"<div style='font-size:18px; font-weight:700; letter-spacing:-0.2px; margin-bottom:4px;'>{course['name']}</div>", unsafe_allow_html=True)
        st.progress(mod_readiness / 100.0)
        st.caption(f"Readiness (completed + quiz ≥ 80% up to W{current_week_number}): **{mod_readiness:.1f}%**")

        state = classify_learning_state(USER_ID, course["canvas_id"])
        state_colors_map = {
            "IMPROVING": "#4CAF50", "STABLE": "#FF9800",
            "NEEDS ATTENTION": "#EF5350", "INACTIVE": "#9E9E9E", "NEW": "#42A5F5",
        }
        s_color = state_colors_map.get(state['state'], '#9E9E9E')
        st.markdown(
            f"""<span class="badge" style="background:{s_color}22; color:{s_color}; border:1px solid {s_color}44; display:inline-block; margin-bottom:6px;">{state['state']}</span>
            <div class="small-muted" style="margin-bottom:12px;">{state['reason']}</div>""",
            unsafe_allow_html=True,
        )

    for i, wk in enumerate(weeks):
        col = row_cols[i + 1]

        if wk == 7:
            col.markdown("<div style='text-align: center; margin-top: 10px;'>🌴</div>", unsafe_allow_html=True)
            continue

        if wk > current_week_number:
            col.markdown("<div style='text-align: center; margin-top: 10px; color: rgba(255,255,255,0.2)'>—</div>", unsafe_allow_html=True)
            continue

        lecture = course_data.get(wk)
        if not lecture:
            col.markdown("<div style='text-align: center; margin-top: 10px; color: rgba(255,255,255,0.2)'>—</div>", unsafe_allow_html=True)
            continue

        status = lecture["lecture_status"]
        link = lecture["lecture_link"]

        if status == "COMPLETED":
            if col.button("Done ✓", key=f"done_badge_{course['canvas_id']}_{wk}", use_container_width=True):
                mark_lecture_incomplete(USER_ID, course["canvas_id"], wk)
                st.rerun()
            if col.button("Quiz", key=f"quiz_{course['canvas_id']}_{wk}", use_container_width=True):
                lecture_db_id = get_lecture_db_id(course["canvas_id"], wk)

                st.session_state["student_id"] = USER_ID
                st.session_state["course_canvas_id"] = course["canvas_id"]
                st.session_state["selected_lecture_title"] = f"{course['name']} Week {wk}"
                st.session_state["week_number"] = wk
                st.session_state["lecture_db_id"] = lecture_db_id
                st.session_state["lecture_link"] = link

                st.switch_page("pages/quiz_page.py")

        elif status == "IN_PROGRESS":
            col.link_button("Resume", link, use_container_width=True)
            if col.button("Finish", key=f"done_{course['canvas_id']}_{wk}", type="secondary", use_container_width=True):
                mark_lecture_complete(USER_ID, course["canvas_id"], wk)
                st.rerun()
        else:
            if col.button("Start", key=f"start_{course['canvas_id']}_{wk}", type="primary", use_container_width=True):
                start_lecture(USER_ID, course["canvas_id"], wk)
                st.markdown(f'<script>window.open("{link}", "_blank");</script>', unsafe_allow_html=True)

    st.divider()