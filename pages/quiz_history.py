from __future__ import annotations

import streamlit as st
import pandas as pd

from db_engine.quiz_db import get_quiz_history, get_user_courses_with_attempts

st.set_page_config(page_title="Quiz History", layout="wide")
st.title("📊 Quiz History")

# ---------------------------------------------------
# USER
# ---------------------------------------------------
USER_ID = st.session_state.get("student_id", "student_001")

# ---------------------------------------------------
# MODULE TOGGLE
# ---------------------------------------------------
courses = get_user_courses_with_attempts(USER_ID)

if not courses:
    st.info("No quiz attempts yet. Complete a quiz from the dashboard to see your history here.")
    if st.button("⬅ Back to Dashboard"):
        st.switch_page("landing.py")
    st.stop()

# Build selection options: "All Modules" + each course
course_labels = {c["canvas_course_id"]: c["course_name"] for c in courses}
options = ["All Modules"] + [c["course_name"] for c in courses]

selected = st.selectbox("Filter by module", options, index=0)

if selected == "All Modules":
    history = get_quiz_history(USER_ID)
else:
    # reverse-lookup canvas_course_id from name
    canvas_id = next(cid for cid, name in course_labels.items() if name == selected)
    history = get_quiz_history(USER_ID, canvas_id)

if not history:
    st.warning("No quiz attempts found for this selection.")
    if st.button("⬅ Back to Dashboard"):
        st.switch_page("landing.py")
    st.stop()

# ---------------------------------------------------
# SUMMARY METRICS
# ---------------------------------------------------
df = pd.DataFrame(history)
df["pct"] = (df["score"] / df["total_questions"] * 100).round(1)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Attempts", len(df))
col2.metric("Average Score", f"{df['pct'].mean():.1f}%")
col3.metric("Best Score", f"{df['pct'].max():.1f}%")
col4.metric("Lectures Quizzed", df["lecture_title"].nunique())

st.divider()

# ---------------------------------------------------
# HISTORY TABLE
# ---------------------------------------------------
display = df.rename(
    columns={
        "course_name": "Module",
        "lecture_title": "Lecture",
        "week_number": "Week",
        "score": "Score",
        "total_questions": "Total",
        "pct": "Score %",
        "attempted_at": "Date",
    }
)[["Module", "Lecture", "Week", "Score", "Total", "Score %", "Date"]]

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------
# PER-LECTURE BREAKDOWN (bar chart)
# ---------------------------------------------------
st.subheader("Score Trend")

chart_df = df[["lecture_title", "pct", "attempted_at"]].copy()
chart_df["attempted_at"] = pd.to_datetime(chart_df["attempted_at"])
chart_df = chart_df.sort_values("attempted_at")
chart_df = chart_df.rename(columns={"attempted_at": "Date", "pct": "Score %", "lecture_title": "Lecture"})

st.bar_chart(chart_df, x="Date", y="Score %", color="Lecture", use_container_width=True)

st.divider()

if st.button("⬅ Back to Dashboard"):
    st.switch_page("landing.py")
