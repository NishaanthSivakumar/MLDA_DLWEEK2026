from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

import streamlit as st

from lecture_tracker import start_lecture, mark_lecture_complete
from db_engine.get_readiness import get_module_readiness, get_overall_readiness
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
div.stButton > button, div.stLinkButton a {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 11px !important;
    padding: 4px 8px !important;
    height: 32px !important;
    border-radius: 8px !important;
}
.kpi-card {
    border: 1px solid rgba(49, 51, 63, 0.2);
    border-radius: 14px;
    padding: 14px 16px;
    background: rgba(255,255,255,0.02);
}
.small-muted { color: rgba(250,250,250,0.7); font-size: 12px; }
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

st.title("🎓 LumiGRAD")
st.caption(f"Current Academic Week: {current_week_label}")

nav1, nav2, _ = st.columns([1, 1, 4])
with nav1:
    if st.button("📊 Quiz History", use_container_width=True):
        st.session_state["student_id"] = USER_ID
        st.switch_page("pages/quiz_history.py")
with nav2:
    if st.button("📌 For You", use_container_width=True):
        st.session_state["student_id"] = USER_ID
        st.switch_page("pages/for_you.py")

st.divider()

# Top KPIs
gpa_target = st.sidebar.slider("GPA Target", min_value=3.0, max_value=5.0, value=4.5, step=0.1)

overall_readiness = get_overall_readiness(USER_ID, current_week_number)
estimated_gpa = round((overall_readiness / 100.0) * 5.0, 2)
gap = gpa_target - estimated_gpa
risk = risk_label_from_gap(gap)
bg_color, text_color = risk_colors(risk)

state_overall = classify_learning_state(USER_ID)

k1, k2, k3, k4 = st.columns(4)

k1.metric("Overall Readiness", f"{overall_readiness:.1f}%")
k2.metric("Estimated GPA (from readiness)", f"{estimated_gpa:.2f}")
k3.metric("Target Band", nus_band(gpa_target))
k4.markdown(
    f"""
    <div class="kpi-card">
      <div class="small-muted">Learning State</div>
      <div style="font-size:18px; font-weight:700;">{state_overall['state']}</div>
      <div class="small-muted">{state_overall['reason']}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.progress(overall_readiness / 100.0)

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
        <span style="font-weight:500;">(Target {nus_band(gpa_target)} · Estimated {nus_band(estimated_gpa)})</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()
st.subheader("Course Tracker")

weeks = list(range(1, 14))

# Header
header_cols = st.columns([3] + [1] * len(weeks))
header_cols[0].markdown("**Course**")
for i, wk in enumerate(weeks):
    header_cols[i + 1].markdown(f"<div style='text-align:center; font-size:14px; font-weight:600;'>{'🌴' if wk == 7 else f'W{wk}'}</div>", unsafe_allow_html=True)

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
        st.markdown(f"### {course['name']}")
        st.progress(mod_readiness / 100.0)
        st.caption(f"Readiness (completed + quiz≥80% up to W{current_week_number}): **{mod_readiness:.1f}%**")

        state = classify_learning_state(USER_ID, course["canvas_id"])
        st.markdown(
            f"""<span class="badge" style="background:rgba(255,255,255,0.08); display:inline-block; margin-bottom:4px;">{state['state']}</span>
            <div class="small-muted" style="margin-bottom: 16px;">{state['reason']}</div>""",
            unsafe_allow_html=True,
        )

    for i, wk in enumerate(weeks):
        col = row_cols[i + 1]

        if wk == 7:
            col.markdown("<div style='text-align: center; margin-top: 10px;'>🌴</div>", unsafe_allow_html=True)
            continue

        lecture = course_data.get(wk)
        if not lecture:
            col.markdown("<div style='text-align: center; margin-top: 10px;'>—</div>", unsafe_allow_html=True)
            continue

        status = lecture["lecture_status"]
        link = lecture["lecture_link"]

        if status == "COMPLETED":
            col.markdown("<div style='text-align:center; font-size:12px; font-weight:700; color:#4CAF50; margin-bottom:6px; margin-top:6px;'>Done</div>", unsafe_allow_html=True)
            if col.button("Quiz", key=f"quiz_{course['canvas_id']}_{wk}", use_container_width=True):
                # Resolve the lectures.id so quiz_attempts joins work correctly
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