import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import calendar

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Study Dashboard", layout="wide", page_icon="📚")

DATA_FILE = "study_data.json"
EVENTS_FILE = "events_data.json"

# ─────────────────────────────────────────────
# DEFAULT DATA  (only used on first run)
# ─────────────────────────────────────────────
DEFAULT_DATA = {
    "CHE 306": {
        "Ch5 L1": False, "Ch7 L2": False, "Ch7 L3": False, "Ch7 L4": False,
        "Ch10 L5": False, "Ch10 L6": False, "Ch10 L7": False, "Ch12 L8": False,
        "Ch12 L9": False, "Ch12 L10": False, "Ch13 L11": False, "Ch13 L12": False,
        "Ch9 L13": False, "Ch9 L14": False, "Ch9 L15": False
    },
    "CHEM 311": {
        "Ch 35.1": False, "Ch 35.2": False, "Ch 35.3": False, "Ch 35.4": False,
        "Ch 35.5": False, "Ch 35.7": False, "Ch 35.8": False, "Ch 35.9": False,
        "Ch 35.10": False, "Ch 35.13": False, "Ch 35.14": False, "Ch 35.15": False,
        "Ch 36.1": False, "Ch 36.2": False, "Ch 36.3": False, "Ch 36.4": False,
        "Ch 36.5": False, "Ch 36.6": False
    },
    "CHE 309": {
        "HT part": False, "MT Part": False, "FM Part": False, "Final Lab Prep": False
    },
    "CHE 360": {
        "unit 6": False, "unit 8": False, "unit 9": False, "Project": False
    },
    "GS 495": {
        "week 8 & 9": False, "week 10": False, "week 11": False, "week 12": False, "Project": False
    },
    "CHEM 312": {
        "The Laboratory Safety, Lab Report/Rejection Rule, and Density": False,
        "Absorption Spectrum of Conjugated Dye": False,
        "Gas Viscosity": False,
        "Kinetics Using Spectroscopy": False,
        "Fluorescence quenching of Rhodamine B Dye": False,
        "Adsorption Isotherm of Acetic Acid": False
    }
}

# ─────────────────────────────────────────────
# PERSISTENCE HELPERS
# ─────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_DATA

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    return []

def save_events(events):
    with open(EVENTS_FILE, "w") as f:
        json.dump(events, f, indent=2)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}

/* Dark background */
.stApp {
    background-color: #0d0f14;
    color: #e8e8e8;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #13161e;
    border-right: 1px solid #1e2330;
}

/* Headers */
h1, h2, h3 {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
}

/* Course card */
.course-card {
    background: #13161e;
    border: 1px solid #1e2330;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
}
.course-card:hover {
    border-color: #4f6ef7;
}

/* Event badges */
.badge-exam {
    background: #ff4757;
    color: white;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    letter-spacing: 0.05em;
}
.badge-due {
    background: #ffa502;
    color: #0d0f14;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    letter-spacing: 0.05em;
}
.badge-other {
    background: #3742fa;
    color: white;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    letter-spacing: 0.05em;
}

/* Countdown urgent */
.countdown-urgent {
    color: #ff4757;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    font-size: 0.85rem;
}
.countdown-soon {
    color: #ffa502;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    font-size: 0.85rem;
}
.countdown-ok {
    color: #2ed573;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    font-size: 0.85rem;
}

/* Calendar cell */
.cal-day {
    background: #13161e;
    border: 1px solid #1e2330;
    border-radius: 8px;
    min-height: 70px;
    padding: 4px 6px;
    font-size: 0.78rem;
}
.cal-day-today {
    border-color: #4f6ef7 !important;
    background: #181d2e !important;
}
.cal-day-number {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    color: #666;
    margin-bottom: 2px;
}
.cal-day-number-today {
    color: #4f6ef7;
    font-weight: 700;
}
.cal-event-dot-exam { color: #ff4757; font-size: 0.65rem; }
.cal-event-dot-due  { color: #ffa502; font-size: 0.65rem; }
.cal-event-dot-other{ color: #3742fa; font-size: 0.65rem; }

/* Section title */
.section-title {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #4f6ef7;
    margin-bottom: 0.5rem;
}

/* Overall stat */
.stat-box {
    background: #13161e;
    border: 1px solid #1e2330;
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
}
.stat-number {
    font-family: 'Space Mono', monospace;
    font-size: 2rem;
    font-weight: 700;
    color: #4f6ef7;
}
.stat-label {
    font-size: 0.78rem;
    color: #888;
    margin-top: 0.2rem;
}

/* Stray buttons */
.stButton > button {
    background: #1e2330;
    border: 1px solid #2a3048;
    color: #e8e8e8;
    border-radius: 8px;
    font-family: 'Syne', sans-serif;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: #4f6ef7;
    border-color: #4f6ef7;
    color: white;
}

/* Delete button */
.stButton > button[kind="secondary"] {
    background: transparent;
    border-color: #ff4757;
    color: #ff4757;
}

div[data-testid="stExpander"] {
    background: #13161e;
    border: 1px solid #1e2330;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# LOAD STATE
# ─────────────────────────────────────────────
data   = load_data()
events = load_events()

# ─────────────────────────────────────────────
# SIDEBAR — NAVIGATION
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📚 Study Dashboard")
    st.markdown("<div class='section-title'>Navigation</div>", unsafe_allow_html=True)
    page = st.radio("", ["📊 Progress", "📅 Calendar", "⚙️ Manage Courses"], label_visibility="collapsed")
    
    st.divider()
    
    # Quick upcoming events in sidebar
    today = date.today()
    upcoming = sorted(
        [e for e in events if datetime.strptime(e["date"], "%Y-%m-%d").date() >= today],
        key=lambda x: x["date"]
    )[:5]
    
    if upcoming:
        st.markdown("<div class='section-title'>Upcoming</div>", unsafe_allow_html=True)
        for ev in upcoming:
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            days_left = (ev_date - today).days
            badge_class = "badge-exam" if ev["type"] == "Exam" else ("badge-due" if ev["type"] == "Due Date" else "badge-other")
            
            if days_left == 0:
                countdown = "TODAY"
                countdown_class = "countdown-urgent"
            elif days_left == 1:
                countdown = "Tomorrow"
                countdown_class = "countdown-urgent"
            elif days_left <= 3:
                countdown = f"{days_left}d left"
                countdown_class = "countdown-soon"
            else:
                countdown = f"{days_left}d left"
                countdown_class = "countdown-ok"
            
            st.markdown(f"""
            <div style="margin-bottom:0.6rem; padding: 0.5rem 0.7rem; background:#0d0f14; border-radius:8px; border-left: 3px solid {'#ff4757' if ev['type']=='Exam' else '#ffa502'}">
                <div style="font-size:0.78rem; font-weight:600;">{ev['title']}</div>
                <div style="font-size:0.72rem; color:#888;">{ev['course']} · <span class="{countdown_class}">{countdown}</span></div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br><div style='color:#444; font-size:0.7rem; font-family:Space Mono,monospace;'>KFUPM · April 2026</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  PAGE 1: PROGRESS
# ═══════════════════════════════════════════════
if page == "📊 Progress":
    st.markdown("# 📊 Study Progress")
    st.markdown("")
    
    # Overall stats
    total_all = sum(len(v) for v in data.values())
    done_all  = sum(sum(1 for s in v.values() if s) for v in data.values())
    pct_all   = int((done_all / total_all * 100)) if total_all else 0
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class='stat-box'><div class='stat-number'>{pct_all}%</div><div class='stat-label'>Overall Complete</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='stat-box'><div class='stat-number'>{done_all}</div><div class='stat-label'>Topics Done</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='stat-box'><div class='stat-number'>{total_all - done_all}</div><div class='stat-label'>Topics Left</div></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class='stat-box'><div class='stat-number'>{len(data)}</div><div class='stat-label'>Courses</div></div>""", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # All-courses bar chart
    course_names, course_pcts = [], []
    for course, lectures in data.items():
        t = len(lectures)
        d = sum(1 for s in lectures.values() if s)
        course_names.append(course)
        course_pcts.append(int(d/t*100) if t else 0)
    
    bar_df = pd.DataFrame({"Course": course_names, "Progress": course_pcts})
    bar_fig = px.bar(
        bar_df, x="Course", y="Progress",
        color="Progress",
        color_continuous_scale=["#ff4757", "#ffa502", "#2ed573"],
        range_color=[0, 100],
        text="Progress"
    )
    bar_fig.update_traces(texttemplate='%{text}%', textposition='outside')
    bar_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#e8e8e8',
        coloraxis_showscale=False,
        yaxis=dict(range=[0, 115], showgrid=False, zeroline=False),
        xaxis=dict(showgrid=False),
        margin=dict(t=30, b=10),
        height=280
    )
    st.plotly_chart(bar_fig, use_container_width=True, key="overall_bar")
    
    st.divider()
    
    # Per-course detail
    for course, lectures in data.items():
        total = len(lectures)
        done  = sum(1 for s in lectures.values() if s)
        pct   = (done / total) if total > 0 else 0
        
        # Get upcoming events for this course
        course_events = [e for e in events if e["course"] == course and
                         datetime.strptime(e["date"], "%Y-%m-%d").date() >= today]
        course_events.sort(key=lambda x: x["date"])
        
        with st.expander(f"📖 {course}  —  {done}/{total} · {int(pct*100)}%", expanded=False):
            col_prog, col_chart = st.columns([2, 1])
            
            with col_prog:
                st.progress(pct, text=f"{int(pct*100)}% complete")
                
                # Events for this course
                if course_events:
                    st.markdown("<div class='section-title' style='margin-top:0.8rem;'>Upcoming Events</div>", unsafe_allow_html=True)
                    for ev in course_events:
                        ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
                        days_left = (ev_date - today).days
                        badge = "badge-exam" if ev["type"] == "Exam" else ("badge-due" if ev["type"] == "Due Date" else "badge-other")
                        cnt_cls = "countdown-urgent" if days_left <= 1 else ("countdown-soon" if days_left <= 3 else "countdown-ok")
                        cnt_txt = "TODAY" if days_left == 0 else (f"{days_left}d left")
                        st.markdown(
                            f"<span class='{badge}'>{ev['type']}</span> &nbsp;"
                            f"<b>{ev['title']}</b> &nbsp;"
                            f"<span style='color:#888;font-size:0.8rem;'>{ev_date.strftime('%b %d')}</span> &nbsp;"
                            f"<span class='{cnt_cls}'>{cnt_txt}</span>",
                            unsafe_allow_html=True
                        )
                
                # Checklist
                st.markdown("<div class='section-title' style='margin-top:0.8rem;'>Topics</div>", unsafe_allow_html=True)
                for lecture, is_done in lectures.items():
                    checked = st.checkbox(lecture, value=is_done, key=f"prog_{course}_{lecture}")
                    if checked != is_done:
                        data[course][lecture] = checked
                        save_data(data)
                        st.rerun()
            
            with col_chart:
                if total > 0:
                    df = pd.DataFrame({
                        "Status": ["Done", "Left"],
                        "Count": [done, total - done]
                    })
                    fig = px.pie(
                        df, values='Count', names='Status', color='Status',
                        color_discrete_map={'Done': '#2ed573', 'Left': '#ff4757'},
                        hole=0.5
                    )
                    fig.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='#e8e8e8',
                        margin=dict(l=10, r=10, t=10, b=10),
                        height=200,
                        showlegend=False
                    )
                    fig.update_traces(textinfo='percent', textfont_size=13)
                    st.plotly_chart(fig, use_container_width=True, key=f"pie_{course}")


# ═══════════════════════════════════════════════
#  PAGE 2: CALENDAR
# ═══════════════════════════════════════════════
elif page == "📅 Calendar":
    st.markdown("# 📅 Calendar")
    
    col_cal, col_form = st.columns([3, 2])
    
    with col_form:
        st.markdown("<div class='section-title'>Add Event</div>", unsafe_allow_html=True)
        
        ev_title  = st.text_input("Title", placeholder="e.g. Midterm Exam")
        ev_course = st.selectbox("Course", ["General"] + list(data.keys()))
        ev_type   = st.selectbox("Type", ["Exam", "Due Date", "Other"])
        ev_date   = st.date_input("Date", value=date.today())
        ev_notes  = st.text_area("Notes (optional)", placeholder="Location, topics, etc.", height=80)
        
        if st.button("➕ Add to Calendar", use_container_width=True):
            if ev_title.strip():
                events.append({
                    "title":  ev_title.strip(),
                    "course": ev_course,
                    "type":   ev_type,
                    "date":   str(ev_date),
                    "notes":  ev_notes.strip()
                })
                save_events(events)
                st.success("Event added!")
                st.rerun()
            else:
                st.warning("Please enter a title.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>All Events</div>", unsafe_allow_html=True)
        
        if not events:
            st.markdown("<div style='color:#555; font-size:0.85rem;'>No events yet.</div>", unsafe_allow_html=True)
        else:
            sorted_events = sorted(events, key=lambda x: x["date"])
            for i, ev in enumerate(sorted_events):
                ev_date_obj = datetime.strptime(ev["date"], "%Y-%m-%d").date()
                days_left   = (ev_date_obj - today).days
                badge = "badge-exam" if ev["type"] == "Exam" else ("badge-due" if ev["type"] == "Due Date" else "badge-other")
                past  = ev_date_obj < today
                
                c_ev, c_del = st.columns([5, 1])
                with c_ev:
                    opacity = "0.45" if past else "1"
                    st.markdown(f"""
                    <div style="padding:0.5rem 0.7rem; background:#0d0f14; border-radius:8px;
                                border-left: 3px solid {'#555' if past else ('#ff4757' if ev['type']=='Exam' else '#ffa502')};
                                margin-bottom:0.4rem; opacity:{opacity};">
                        <div style="display:flex; gap:6px; align-items:center;">
                            <span class='{badge}'>{ev['type']}</span>
                            <span style="font-size:0.82rem; font-weight:600;">{ev['title']}</span>
                        </div>
                        <div style="font-size:0.72rem; color:#888; margin-top:2px;">
                            {ev['course']} · {ev_date_obj.strftime('%b %d, %Y')}
                            {'· <span style="color:#555">Past</span>' if past else ''}
                        </div>
                        {f'<div style="font-size:0.72rem; color:#666; margin-top:2px;">{ev["notes"]}</div>' if ev.get("notes") else ''}
                    </div>
                    """, unsafe_allow_html=True)
                with c_del:
                    if st.button("✕", key=f"del_ev_{i}", help="Delete"):
                        events.pop(i)
                        save_events(events)
                        st.rerun()
    
    with col_cal:
        st.markdown("<div class='section-title'>Monthly View</div>", unsafe_allow_html=True)
        
        # Month navigation
        if "cal_year" not in st.session_state:
            st.session_state.cal_year  = today.year
            st.session_state.cal_month = today.month
        
        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("◀", key="prev_month"):
                if st.session_state.cal_month == 1:
                    st.session_state.cal_month = 12
                    st.session_state.cal_year -= 1
                else:
                    st.session_state.cal_month -= 1
                st.rerun()
        with nav2:
            st.markdown(f"<div style='text-align:center; font-family:Space Mono,monospace; font-weight:700; font-size:1rem; padding-top:6px;'>"
                        f"{calendar.month_name[st.session_state.cal_month]} {st.session_state.cal_year}</div>",
                        unsafe_allow_html=True)
        with nav3:
            if st.button("▶", key="next_month"):
                if st.session_state.cal_month == 12:
                    st.session_state.cal_month = 1
                    st.session_state.cal_year += 1
                else:
                    st.session_state.cal_month += 1
                st.rerun()
        
        # Build event lookup by date string
        event_map = {}
        for ev in events:
            event_map.setdefault(ev["date"], []).append(ev)
        
        # Calendar grid
        year  = st.session_state.cal_year
        month = st.session_state.cal_month
        cal   = calendar.monthcalendar(year, month)
        
        day_headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        header_cols = st.columns(7)
        for i, h in enumerate(day_headers):
            with header_cols[i]:
                st.markdown(f"<div style='text-align:center; font-family:Space Mono,monospace; font-size:0.7rem; color:#555; padding-bottom:4px;'>{h}</div>",
                            unsafe_allow_html=True)
        
        for week in cal:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                with week_cols[i]:
                    if day == 0:
                        st.markdown("<div class='cal-day' style='background:transparent;border-color:transparent;'></div>", unsafe_allow_html=True)
                    else:
                        cell_date   = date(year, month, day)
                        date_str    = str(cell_date)
                        is_today    = (cell_date == today)
                        cell_events = event_map.get(date_str, [])
                        
                        day_num_cls = "cal-day-number-today" if is_today else "cal-day-number"
                        cell_cls    = "cal-day cal-day-today" if is_today else "cal-day"
                        
                        # Build event dots
                        dots = ""
                        for ev in cell_events[:3]:
                            dot_cls = "cal-event-dot-exam" if ev["type"] == "Exam" else (
                                      "cal-event-dot-due"  if ev["type"] == "Due Date" else "cal-event-dot-other")
                            dots += f"<div class='{dot_cls}'>● {ev['title'][:10]}{'…' if len(ev['title'])>10 else ''}</div>"
                        
                        st.markdown(f"""
                        <div class='{cell_cls}'>
                            <div class='{day_num_cls}'>{day}</div>
                            {dots}
                        </div>
                        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  PAGE 3: MANAGE COURSES
# ═══════════════════════════════════════════════
elif page == "⚙️ Manage Courses":
    st.markdown("# ⚙️ Manage Courses")
    
    tab_add_course, tab_edit_course, tab_del_course = st.tabs(["➕ New Course", "✏️ Edit Course", "🗑️ Delete Course"])
    
    # ── ADD COURSE ──
    with tab_add_course:
        st.markdown("<div class='section-title'>Create a New Course</div>", unsafe_allow_html=True)
        
        new_course_name = st.text_input("Course Code / Name", placeholder="e.g. CHE 410")
        topics_raw = st.text_area(
            "Topics (one per line)",
            placeholder="Ch1 L1\nCh1 L2\nMidterm Prep\n...",
            height=200
        )
        
        if st.button("Create Course", use_container_width=True):
            name = new_course_name.strip()
            if not name:
                st.warning("Enter a course name.")
            elif name in data:
                st.warning("Course already exists.")
            else:
                topics = [t.strip() for t in topics_raw.splitlines() if t.strip()]
                if not topics:
                    st.warning("Add at least one topic.")
                else:
                    data[name] = {t: False for t in topics}
                    save_data(data)
                    st.success(f"✅ {name} created with {len(topics)} topics!")
                    st.rerun()
    
    # ── EDIT COURSE ──
    with tab_edit_course:
        st.markdown("<div class='section-title'>Edit Topics in a Course</div>", unsafe_allow_html=True)
        
        if not data:
            st.info("No courses yet.")
        else:
            edit_course = st.selectbox("Select Course", list(data.keys()), key="edit_sel")
            
            if edit_course:
                st.markdown(f"**Current topics in {edit_course}:**")
                
                # Add new topic
                new_topic = st.text_input("Add a new topic", placeholder="e.g. Ch14 L16", key="new_topic_input")
                if st.button("Add Topic", key="add_topic_btn"):
                    nt = new_topic.strip()
                    if not nt:
                        st.warning("Enter a topic name.")
                    elif nt in data[edit_course]:
                        st.warning("Topic already exists.")
                    else:
                        data[edit_course][nt] = False
                        save_data(data)
                        st.success(f"Added '{nt}'")
                        st.rerun()
                
                st.divider()
                
                # Rename course
                rename_val = st.text_input("Rename course to", value=edit_course, key="rename_course")
                if st.button("Rename Course", key="rename_btn"):
                    new_name = rename_val.strip()
                    if new_name and new_name != edit_course:
                        if new_name in data:
                            st.warning("Name already taken.")
                        else:
                            data[new_name] = data.pop(edit_course)
                            save_data(data)
                            st.success(f"Renamed to {new_name}")
                            st.rerun()
                
                st.divider()
                
                # List topics with delete
                st.markdown("<div class='section-title'>Topics</div>", unsafe_allow_html=True)
                for topic in list(data[edit_course].keys()):
                    t_col, d_col = st.columns([5, 1])
                    with t_col:
                        status = "✅" if data[edit_course][topic] else "⬜"
                        st.markdown(f"<div style='padding:4px 0; font-size:0.85rem;'>{status} {topic}</div>", unsafe_allow_html=True)
                    with d_col:
                        if st.button("✕", key=f"del_topic_{edit_course}_{topic}", help="Remove topic"):
                            del data[edit_course][topic]
                            save_data(data)
                            st.rerun()
    
    # ── DELETE COURSE ──
    with tab_del_course:
        st.markdown("<div class='section-title'>Remove a Course</div>", unsafe_allow_html=True)
        
        if not data:
            st.info("No courses to delete.")
        else:
            del_course = st.selectbox("Select Course to Delete", list(data.keys()), key="del_course_sel")
            st.warning(f"⚠️ This will permanently remove **{del_course}** and all its topics.")
            
            confirm = st.checkbox("I understand, delete this course")
            if st.button("🗑️ Delete Course", disabled=not confirm):
                del data[del_course]
                save_data(data)
                st.success(f"Deleted {del_course}")
                st.rerun()
