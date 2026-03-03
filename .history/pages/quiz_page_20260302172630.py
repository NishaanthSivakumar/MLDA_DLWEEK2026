from __future__ import annotations

import time
import streamlit as st

from quiz.quiz_runner import generate_quiz_from_url
from quiz.agents import grader_agent, resource_recommender_agent

from db_engine.quiz_db import save_quiz_attempt, get_last_quiz_attempt
from db_engine.topic_mastery import update_topics_from_question
from db_engine.events import log_event


st.set_page_config(page_title="Study + Quiz", layout="wide")
st.title("🧠 Active Recall Quiz")


# ---------------------------------------------------
# SESSION DATA FROM DASHBOARD
# ---------------------------------------------------
student_id = st.session_state.get("student_id", "student_001")
course_canvas_id = st.session_state.get("course_canvas_id")
lecture_url = st.session_state.get("lecture_link")
lecture_title = st.session_state.get("selected_lecture_title")
week_number = st.session_state.get("week_number")
lecture_db_id = st.session_state.get("lecture_db_id")

if not (course_canvas_id and lecture_url and lecture_title and lecture_db_id):
    st.error("No lecture selected. Please return to dashboard.")
    st.stop()

# Last attempt banner
last_attempt = get_last_quiz_attempt(student_id, int(lecture_db_id))
if last_attempt:
    st.info(
        f"Last attempt: {last_attempt['score']}/{last_attempt['total_questions']} "
        f"on {last_attempt['attempted_at']}"
    )

st.divider()

# ---------------------------------------------------
# GENERATE QUIZ
# ---------------------------------------------------
if "quiz_bundle" not in st.session_state:
    st.session_state.quiz_bundle = None

c1, c2 = st.columns([1, 2])
with c1:
    if st.button("⚡ Generate Quiz", use_container_width=True):
        with st.spinner("Generating quiz..."):
            st.session_state.quiz_bundle = generate_quiz_from_url(
                student_id=student_id,
                lecture_id=int(lecture_db_id),
                lecture_title=lecture_title,
                lecture_url=lecture_url,
                profile_summary="",
            )
            log_event(
                canvas_user_id=student_id,
                canvas_course_id=course_canvas_id,
                week_number=week_number,
                event_type="QUIZ_GENERATE",
                payload={"lecture_db_id": int(lecture_db_id)},
            )

with c2:
    st.caption("This quiz is generated from the selected lecture and will update your topic mastery when submitted.")

quiz = st.session_state.quiz_bundle
if not quiz:
    st.info("Click **Generate Quiz** to begin.")
    st.stop()


# ---------------------------------------------------
# RENDER QUIZ
# ---------------------------------------------------
st.write(f"### {quiz['lecture_title']}")
student_answers = {}
time_spent = {}

for i, q in enumerate(quiz["questions"], start=1):
    st.write(f"**Q{i}. ({q['question_type']}, difficulty {q['difficulty']}/5)**")
    st.write(q["question"])
    st.caption(f"Tags: {', '.join(q['topic_tags'])}")

    t0 = time.time()
    if q["question_type"] == "short_answer":
        ans = st.text_input("Your answer", key=f"sa_{q['question_id']}")
        student_answers[q["question_id"]] = {"type": "short_answer", "text": ans}
    else:
        choice = st.radio(
            "Choose one:",
            options=list(range(len(q["options"]))),
            format_func=lambda idx: q["options"][idx],
            key=f"mcq_{q['question_id']}",
        )
        student_answers[q["question_id"]] = {"type": "mcq", "choice_index": int(choice)}
    time_spent[q["question_id"]] = int(time.time() - t0)
    st.divider()


# ---------------------------------------------------
# SUBMIT + GRADE
# ---------------------------------------------------
if st.button("✅ Submit Quiz", use_container_width=True):
    agent_answers = {}
    for q in quiz["questions"]:
        qid = q["question_id"]
        if student_answers[qid]["type"] == "mcq":
            idx = student_answers[qid]["choice_index"]
            agent_answers[qid] = {"selected_index": idx, "selected_text": q["options"][idx]}
        else:
            agent_answers[qid] = {"text": student_answers[qid]["text"]}

    with st.spinner("Grading..."):
        grading = grader_agent(
            student_id=student_id,
            lecture_id=int(lecture_db_id),
            lecture_text=str(quiz.get("_lecture_text", "")),
            quiz_questions=quiz["questions"],
            student_answers=agent_answers,
        )

    # Score + persist
    correct_count = sum(1 for r in grading["results"] if r["is_correct"])
    total = len(quiz["questions"])
    save_quiz_attempt(
        user_canvas_id=student_id,
        lecture_db_id=int(lecture_db_id),
        score=int(correct_count),
        total=int(total),
    )

    log_event(
        canvas_user_id=student_id,
        canvas_course_id=course_canvas_id,
        week_number=week_number,
        event_type="QUIZ_SUBMIT",
        payload={"lecture_db_id": int(lecture_db_id), "score": correct_count, "total": total},
    )

    # Update topic mastery per question (dynamic learning state)
    grade_map = {r["question_id"]: r for r in grading["results"]}
    for q in quiz["questions"]:
        qid = q["question_id"]
        is_correct = bool(grade_map[qid]["is_correct"])
        update_topics_from_question(
            canvas_user_id=student_id,
            canvas_course_id=course_canvas_id,
            topic_tags=q["topic_tags"],
            is_correct=is_correct,
            time_spent_sec=int(time_spent.get(qid, 0)),
        )

    st.success(f"Final Score: {correct_count}/{total}")

    # --- Fetch learning resources for wrong answers ---
    wrong_qids = {r["question_id"] for r in grading["results"] if not r["is_correct"]}
    wrong_questions = [q for q in quiz["questions"] if q["question_id"] in wrong_qids]

    resources_map: dict = {}
    if wrong_questions:
        with st.spinner("Finding learning resources for missed questions..."):
            try:
                rec = resource_recommender_agent(
                    wrong_questions=wrong_questions,
                    lecture_title=lecture_title,
                )
                resources_map = {r["question_id"]: r for r in rec.get("resources", [])}
            except Exception:
                resources_map = {}

    st.subheader("📌 Feedback (Explainable)")
    for r in grading["results"]:
        with st.container(border=True):
            st.write(
                f"**{r['question_id']}** — "
                f"{'✅ Correct' if r['is_correct'] else '❌ Incorrect'} "
                f"(score {r['score_0_to_1']:.2f})"
            )
            st.write("Feedback:", r["feedback"])
            if r.get("common_misconception"):
                st.caption("Common misconception: " + r["common_misconception"])

            # Show resources for incorrect answers
            if not r["is_correct"] and r["question_id"] in resources_map:
                res = resources_map[r["question_id"]]
                st.markdown("---")
                st.markdown("**📚 Recommended Resources**")

                yt = res.get("youtube", [])
                if yt:
                    st.markdown("🎥 **YouTube Videos**")
                    for v in yt:
                        st.markdown(f"- [{v['title']}]({v['url']})")

                papers = res.get("papers", [])
                if papers:
                    st.markdown("📄 **Papers / References**")
                    for p in papers:
                        st.markdown(f"- [{p['title']}]({p['url']})")

    st.caption("Topic mastery updated using correctness + time spent + inactivity decay.")

st.divider()

if st.button("⬅ Back to Dashboard"):
    st.session_state.quiz_bundle = None
    st.switch_page("landing.py")
