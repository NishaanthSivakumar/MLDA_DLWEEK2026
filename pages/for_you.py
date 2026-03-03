"""
📌 For You — personalised insights, weekly plan & professor matches.
"""
from __future__ import annotations

import streamlit as st
from datetime import date
import json
from urllib.parse import quote_plus

from db_engine.topic_mastery import get_topic_summary
from db_engine.learning_state import classify_learning_state
from db_engine.profile import get_student_profile
from ai.planner import generate_combined_weekly_plan, ALL_DAYS
from ai.opportunities import get_opportunity_suggestions
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
.opp-platform-card {
    border: 1px solid rgba(49,51,63,0.20);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 10px;
    background: rgba(255,255,255,0.03);
    transition: border-color 0.2s;
}
.opp-tag {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 4px;
    margin-top: 4px;
    background: rgba(33,150,243,0.12);
    color: #90CAF9;
}
.opp-category-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    margin-right: 6px;
}
.profile-skill-card {
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(49,51,63,0.18);
}
.profile-bar-bg {
    background: rgba(255,255,255,0.08);
    border-radius: 4px;
    height: 6px;
    margin-top: 8px;
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
# STUDENT PROFILE — STRENGTHS & WEAKNESSES
# ---------------------------------------------------
st.header("🧠 Your Soft Skill Profile")
st.caption(
    "Your top strengths and areas to grow — derived from lecture discipline, "
    "study consistency, time management, and revision effort."
)

_profile = get_student_profile(USER_ID, current_week)
_soft    = _profile.get("soft_skills", [])

def _skill_card_html(skill: dict) -> str:
    pct = int(skill["score"] * 100)
    return (
        f'<div class="profile-skill-card">'
        f'<div style="display:flex; justify-content:space-between; align-items:center;">'
        f'<span style="font-size:13px; font-weight:700;">{skill["name"]}</span>'
        f'<span style="font-size:11px; font-weight:700; color:{skill["colour"]};'
        f' background:{skill["colour"]}22; padding:2px 10px; border-radius:999px;">'
        f'{skill["label"]}</span></div>'
        f'<div class="small-muted" style="margin-top:4px; font-size:11px;">'
        f'{skill["description"]}</div>'
        f'<div class="profile-bar-bg">'
        f'<div style="width:{pct}%; background:{skill["colour"]}; height:6px; border-radius:4px;"></div>'
        f'</div>'
        f'<div style="font-size:10px; color:rgba(250,250,250,0.4); margin-top:4px; text-align:right;">'
        f'{pct}%</div>'
        f'</div>'
    )

# Top 2 strong (highest scores) and top 2 weak (lowest scores)
_soft_sorted_desc = sorted(_soft, key=lambda s: s["score"], reverse=True)
_soft_sorted_asc  = sorted(_soft, key=lambda s: s["score"])
_top_strong = _soft_sorted_desc[:2]
_top_weak   = _soft_sorted_asc[:2]

_prof_col_strong, _prof_col_weak = st.columns(2)

with _prof_col_strong:
    st.subheader("💪 Top Strengths")
    if _top_strong:
        for _sk in _top_strong:
            st.markdown(_skill_card_html(_sk), unsafe_allow_html=True)
    else:
        st.info("No activity recorded yet.")

with _prof_col_weak:
    st.subheader("🔧 Areas to Improve")
    if _top_weak:
        for _sk in _top_weak:
            st.markdown(_skill_card_html(_sk), unsafe_allow_html=True)
    else:
        st.info("No activity recorded yet.")

st.divider()


# ---------------------------------------------------
# PER-COURSE SECTIONS
# ---------------------------------------------------
for course in COURSES:
    st.header(f"📘 {course['name']}")

    state = classify_learning_state(USER_ID, course["canvas_id"])
    topics = get_topic_summary(USER_ID, course["canvas_id"], limit=3)
    weak = topics.get("weak", [])
    strong = topics.get("strong", [])

    # Learning state badge
    state_colors = {
        "IMPROVING": ("🟢", "#E8F5E9", "#1B5E20"),
        "STABLE":    ("🟡", "#FFF3E0", "#E65100"),
        "NEEDS ATTENTION":("🔴", "#FFEBEE", "#B71C1C"),
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

    # ---- Professor Recommendations ----
    st.subheader("🎓 Recommended Professors")
    st.caption(
        "Professors whose research interests align with your **strong topics**. "
        "A great way to explore deeper or find a potential supervisor!"
    )

    if strong:
        matches = match_professors(strong, top_n=3)
        if matches:
            for prof in matches:
                matched_badges = "".join(
                    f'<span class="prof-match">{m}</span>' for m in prof["matched_topics"]
                )
                areas_str = ", ".join(prof["research_areas"])
                score_pct = prof["match_score"] * 100
                prof_url = prof.get("url", "")
                name_html = (
                    f'<a href="{prof_url}" target="_blank" style="font-size:16px; font-weight:700;'
                    f' color:inherit; text-decoration:underline; text-underline-offset:3px;">'
                    f'{prof["name"]}</a>'
                    if prof_url
                    else f'<strong style="font-size:16px;">{prof["name"]}</strong>'
                )

                st.markdown(
                    f"""<div class="prof-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                {name_html}
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
# COMBINED WEEKLY STUDY PLAN
# ---------------------------------------------------
st.header("🗓️ My Week — Combined Study Schedule")
st.caption(
    "One actionable calendar across **all your modules**, built from your mastery, "
    "quiz scores and learning state. Commit your time below and let LumiGRAD plan your week."
)

# ── Commitment form ─────────────────────────────────────────────────────────
with st.container():
    st.markdown(
        """
        <div style="border:1px solid rgba(49,51,63,0.20); border-radius:14px;
             padding:20px 22px; background:rgba(255,255,255,0.02); margin-bottom:16px;">
            <div style="font-size:15px; font-weight:700; margin-bottom:4px;">⏳ Commit to your week</div>
            <div style="font-size:12px; color:rgba(250,250,250,0.5); line-height:1.6;">
                Be honest — a realistic commitment leads to a plan you can actually follow blindly.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _commit_col1, _commit_col2 = st.columns([1, 2])
    with _commit_col1:
        _hours_per_day = st.slider(
            "📚 Hours available per study day",
            min_value=0.5, max_value=8.0, value=2.0, step=0.5,
            help="How many hours can you realistically commit per study day this week?"
        )
    with _commit_col2:
        _study_days = st.multiselect(
            "📅 Which days can you study this week?",
            options=ALL_DAYS,
            default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            help="Select all days you are available to study. Rest days will be labelled accordingly."
        )

    if not _study_days:
        st.warning("Select at least one study day to generate your plan.")
    else:
        _total_committed_hrs = len(_study_days) * _hours_per_day
        st.markdown(
            f"""<div style="font-size:12px; color:rgba(250,250,250,0.55); margin-bottom:12px;">
            ✅ You're committing <strong>{_total_committed_hrs:.1f} hrs</strong> this week across
            <strong>{len(_study_days)} days</strong>.
            </div>""",
            unsafe_allow_html=True,
        )

# ── Generate button ──────────────────────────────────────────────────────────
_COMBINED_PLAN_KEY = "_combined_weekly_plan"

if _study_days and st.button("🚀 Generate My Week", key="btn_combined_plan", type="primary"):
    # Gather all courses data
    _all_courses_data = []
    for _c in COURSES:
        _c_state = classify_learning_state(USER_ID, _c["canvas_id"])
        _c_topics = get_topic_summary(USER_ID, _c["canvas_id"], limit=5)
        _all_courses_data.append({
            "name": _c["name"],
            "learning_state": _c_state,
            "weak_topics": _c_topics.get("weak", []),
            "strong_topics": _c_topics.get("strong", []),
        })
    with st.spinner("Building your personalised weekly schedule…"):
        st.session_state[_COMBINED_PLAN_KEY] = generate_combined_weekly_plan(
            all_courses=_all_courses_data,
            current_week=current_week,
            gpa_target=float(gpa_target),
            available_hours_per_day=_hours_per_day,
            study_days=_study_days,
        )

# ── Render the 7-day calendar ────────────────────────────────────────────────
_combined_plan: list[dict] = st.session_state.get(_COMBINED_PLAN_KEY, [])

if _combined_plan:
    DAY_COLORS = ["#1565C0", "#6A1B9A", "#00695C", "#E65100", "#AD1457", "#00838F", "#558B2F"]
    MODULE_COLORS = {
        course["name"]: c
        for course, c in zip(
            COURSES,
            ["#1565C0", "#6A1B9A", "#00695C", "#E65100", "#AD1457"],
        )
    }

    _day_cols = st.columns(7)
    for _di, (_day_data, _col) in enumerate(zip(_combined_plan, _day_cols)):
        _day_name  = _day_data.get("day", ALL_DAYS[_di])
        _is_rest   = _day_data.get("rest", False)
        _tasks     = _day_data.get("tasks", [])
        _total_min = _day_data.get("total_min", 0)
        _focus     = _day_data.get("day_focus", "")
        _day_color = DAY_COLORS[_di % len(DAY_COLORS)]
        _short     = _day_name[:3].upper()

        with _col:
            if _is_rest or not _tasks:
                st.markdown(
                    f"""<div style="border:1px dashed rgba(49,51,63,0.15);
                         border-radius:14px; padding:12px 10px; min-height:320px;
                         display:flex; align-items:center; justify-content:center;
                         text-align:center;">
                        <div style="color:rgba(250,250,250,0.25);">
                            <div style="font-size:13px; font-weight:700;">{_short}</div>
                            <div style="font-size:28px; margin:8px 0;">😴</div>
                            <div style="font-size:10px;">Rest day</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""<div style="font-size:12px; font-weight:700;
                         color:{_day_color}; margin-bottom:2px;">{_short}</div>
                        <div style="font-size:10px; color:rgba(250,250,250,0.45);
                         line-height:1.4; margin-bottom:4px;">{_focus}</div>
                        <div style="font-size:10px; color:rgba(250,250,250,0.35);
                         margin-bottom:8px;">⏱ {_total_min} min total</div>""",
                    unsafe_allow_html=True,
                )
                for _task in _tasks:
                    _mod = _task.get("module", "")
                    _act = _task.get("action", "")
                    _dur = _task.get("duration_min", 0)
                    _why = _task.get("reason", "")
                    _out = _task.get("expected_outcome", "")
                    _mc  = MODULE_COLORS.get(_mod, "#42A5F5")
                    _outcome_html = (
                        f'<div style="font-size:10px; color:rgba(250,250,250,0.35);'
                        f' margin-top:2px;">🎯 {_out}</div>'
                        if _out else ""
                    )
                    st.markdown(
                        f"""<div style="border-left:3px solid {_mc}; padding:6px 8px;
                             margin-bottom:8px; background:rgba(255,255,255,0.03);
                             border-radius:0 6px 6px 0;">
                            <div style="font-size:10px; font-weight:700; color:{_mc};
                                 text-transform:uppercase; letter-spacing:0.04em;">{_mod}</div>
                            <div style="font-size:11px; font-weight:600; margin:3px 0;">{_act}</div>
                            <div style="font-size:10px; color:rgba(250,250,250,0.5);">⏱ {_dur} min</div>
                            <div style="font-size:10px; color:rgba(250,250,250,0.4);
                                 margin-top:2px;">{_why}</div>
                            {_outcome_html}
                        </div>""",
                        unsafe_allow_html=True,
                    )
else:
    st.caption("Fill in your commitment above and click **Generate My Week** to get started.")

st.divider()


# ---------------------------------------------------
# OPPORTUNITIES FOR YOU
# ---------------------------------------------------
# Aggregate strong topics across all courses
_all_strong_topics: list[str] = []
for _course in COURSES:
    _t = get_topic_summary(USER_ID, _course["canvas_id"], limit=5)
    _all_strong_topics.extend([t["topic"] for t in _t.get("strong", [])])

# Deduplicate, preserving order
_seen: set[str] = set()
_unique_strong: list[str] = []
for _t in _all_strong_topics:
    if _t not in _seen:
        _seen.add(_t)
        _unique_strong.append(_t)

st.header("💼 Opportunities For You")
st.caption(
    "Top 2 personalised listings per platform — jobs, events & hackathons — "
    "matched to your **strongest topics**."
)

if not _unique_strong:
    st.info(
        "No strong topics identified yet. Complete more quizzes to unlock personalised "
        "job, event, and hackathon suggestions!"
    )
else:
    # Display which strengths are driving the suggestions
    st.markdown(
        "<div style='margin-bottom:12px;'>"
        + "".join(
            f'<span class="opp-tag">{t}</span>' for t in _unique_strong[:8]
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    # Build URL-encoded query strings for fallback search links
    _primary_query = quote_plus(" ".join(_unique_strong[:3]))
    _broad_query   = quote_plus(" ".join(_unique_strong[:5]))
    _hack_query    = quote_plus("hackathon " + " ".join(_unique_strong[:3]))

    _PLATFORM_SEARCH_URLS = {
        "LinkedIn":   f"https://www.linkedin.com/jobs/search/?keywords={_primary_query}&location=Singapore",
        "Jobstreet":  f"https://www.jobstreet.com.sg/jobs?q={_primary_query}&l=Singapore",
        "Indeed":     f"https://sg.indeed.com/jobs?q={_primary_query}&l=Singapore",
        "Symplicity": "https://nus-csm.symplicity.com/students/",
        "Eventbrite": f"https://www.eventbrite.sg/d/singapore/{_broad_query}/",
        "Devpost":    f"https://devpost.com/hackathons?search={_primary_query}&challenge_type[]=all",
    }
    _PLATFORM_LOGOS = {
        "LinkedIn": "🔵", "Jobstreet": "🟠", "Indeed": "🔷",
        "Symplicity": "🎓", "Eventbrite": "🟣", "Devpost": "⚔️",
    }
    _CAT_META = {
        "job":       ("👔 Jobs",       "#1565C0", "rgba(21,101,192,0.12)"),
        "event":     ("🗓️ Events",     "#6A1B9A", "rgba(106,27,154,0.12)"),
        "hackathon": ("⚡ Hackathons",  "#00695C", "rgba(0,105,92,0.12)"),
    }

    # Generate / cache suggestions
    _opp_key = "_opportunity_suggestions"
    if st.button("🔍 Generate Opportunities", key="btn_opportunities"):
        with st.spinner("Finding opportunities matched to your strengths…"):
            st.session_state[_opp_key] = get_opportunity_suggestions(_unique_strong)

    _suggestions: list[dict] = st.session_state.get(_opp_key, [])

    if not _suggestions:
        st.caption("Click the button above to generate personalised listings.")
    else:
        for _cat_key in ("job", "event", "hackathon"):
            _cat_label, _cat_color, _cat_bg = _CAT_META[_cat_key]
            _cat_items = [s for s in _suggestions if s.get("category") == _cat_key]

            if not _cat_items:
                continue

            st.subheader(_cat_label)

            # Group by platform and show top 2 per platform
            _by_platform: dict[str, list[dict]] = {}
            for _item in _cat_items:
                _plat = _item.get("platform", "LinkedIn")
                _by_platform.setdefault(_plat, []).append(_item)

            _platform_groups = list(_by_platform.items())
            _p_cols = st.columns(max(len(_platform_groups), 1))

            for _p_col, (_plat_name, _listings) in zip(_p_cols, _platform_groups):
                with _p_col:
                    _logo = _PLATFORM_LOGOS.get(_plat_name, "🔗")
                    _search_url = _PLATFORM_SEARCH_URLS.get(_plat_name, "#")

                    # Platform header card
                    st.markdown(
                        f"""<div class="opp-platform-card" style="margin-bottom:8px;">
                            <span class="opp-category-badge"
                                  style="background:{_cat_bg}; color:{_cat_color};">
                                {_cat_label.split()[1]}
                            </span>
                            <div style="font-size:15px; font-weight:700; margin-top:6px;">
                                {_logo} {_plat_name}
                            </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                    # Top 2 listings
                    for _listing in _listings[:2]:
                        _title = _listing.get("title", "")
                        _org   = _listing.get("organisation", "")
                        _loc   = _listing.get("location", "")
                        _blurb = _listing.get("blurb", "")
                        st.markdown(
                            f"""<div style="border:1px solid rgba(49,51,63,0.18); border-radius:10px;
                                      padding:12px 14px; margin-bottom:8px;
                                      background:rgba(255,255,255,0.02);">
                                <div style="font-size:13px; font-weight:700; margin-bottom:2px;">
                                    {_title}
                                </div>
                                <div style="font-size:12px; color:{_cat_color}; font-weight:600;">
                                    {_org}
                                </div>
                                <div class="small-muted" style="margin-top:2px;">📍 {_loc}</div>
                                <div style="font-size:11px; color:rgba(250,250,250,0.5);
                                            margin-top:6px; line-height:1.4;">
                                    {_blurb}
                                </div>
                            </div>""",
                            unsafe_allow_html=True,
                        )

                    # Search-all link button
                    st.link_button(
                        f"See more on {_plat_name} →",
                        _search_url,
                        use_container_width=True,
                    )

            st.markdown("")

st.divider()


# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------
st.caption("Data sourced from NUS Department of Statistics & Data Science faculty directory.")
