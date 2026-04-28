import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import calendar

# ─────────────────────────────────────────────
st.set_page_config(page_title="Study Dashboard · KFUPM", layout="wide", page_icon="◈")

DATA_FILE   = "study_data.json"
EVENTS_FILE = "events_data.json"

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
        "Lab Safety & Density": False,
        "Absorption Spectrum of Conjugated Dye": False,
        "Gas Viscosity": False,
        "Kinetics Using Spectroscopy": False,
        "Fluorescence Quenching of Rhodamine B": False,
        "Adsorption Isotherm of Acetic Acid": False
    }
}

COURSE_COLORS = ["#4361ee", "#e63946", "#7209b7", "#2d6a4f", "#e76f51", "#0077b6"]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_DATA

def save_data(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2)

def load_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    return []

def save_events(e):
    with open(EVENTS_FILE, "w") as f:
        json.dump(e, f, indent=2)

# ─────────────────────────────────────────────  CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Playfair+Display:wght@700;800&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, .stApp {
    background: #f5f3ef !important;
    color: #1a1814 !important;
    font-family: 'DM Sans', sans-serif !important;
}
#MainMenu, footer { visibility: hidden; }
.block-container { padding: 2rem 2.2rem 4rem !important; max-width: 100% !important; }

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1.5px solid #e2ddd6 !important;
}
section[data-testid="stSidebar"] .block-container { padding: 1.8rem 1.3rem !important; }

/* Radio */
div[data-testid="stRadio"] > label { display: none; }
div[data-testid="stRadio"] > div { flex-direction: column; gap: 3px; }
div[data-testid="stRadio"] > div > label {
    background: transparent !important;
    border: 1.5px solid transparent !important;
    border-radius: 8px !important;
    padding: 9px 13px !important;
    color: #6b6560 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.86rem !important;
    font-weight: 500 !important;
    cursor: pointer;
    transition: all 0.15s;
}
div[data-testid="stRadio"] > div > label:hover {
    background: #f0ede8 !important;
    color: #1a1814 !important;
}
div[data-testid="stRadio"] > div > label[data-checked="true"] {
    background: #d8f3dc !important;
    border-color: #b7dfc4 !important;
    color: #2d6a4f !important;
    font-weight: 600 !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea {
    background: #ffffff !important;
    border: 1.5px solid #ddd8d2 !important;
    border-radius: 8px !important;
    color: #1a1814 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #2d6a4f !important;
    box-shadow: 0 0 0 3px rgba(45,106,79,0.1) !important;
    outline: none !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label, .stDateInput label {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.67rem !important;
    color: #9a948c !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
div[data-baseweb="select"] > div {
    background: #ffffff !important;
    border: 1.5px solid #ddd8d2 !important;
    border-radius: 8px !important;
    color: #1a1814 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
}

/* Buttons */
.stButton > button {
    background: #ffffff !important;
    border: 1.5px solid #ccc7be !important;
    color: #4a4640 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    transition: all 0.15s !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}
.stButton > button:hover {
    border-color: #2d6a4f !important;
    color: #2d6a4f !important;
    background: #edf6f0 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 2px solid #e2ddd6 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #9a948c !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.86rem !important;
    font-weight: 500 !important;
    padding: 9px 20px !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -2px !important;
}
.stTabs [aria-selected="true"] {
    color: #2d6a4f !important;
    border-bottom-color: #2d6a4f !important;
    font-weight: 600 !important;
}

/* Expander */
details {
    background: #ffffff !important;
    border: 1.5px solid #e2ddd6 !important;
    border-radius: 10px !important;
    overflow: hidden;
}
details summary {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.84rem !important;
    padding: 10px 14px !important;
    color: #4a4640 !important;
    font-weight: 500 !important;
}
details[open] { border-color: #ccc7be !important; }

/* Checkbox */
.stCheckbox label {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.84rem !important;
    color: #4a4640 !important;
}

/* Progress bar */
div[data-testid="stProgressBar"] > div {
    background: #e8e4df !important;
    border-radius: 99px !important;
    height: 6px !important;
}
div[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #2d6a4f, #52b788) !important;
    border-radius: 99px !important;
}

hr { border-color: #e2ddd6 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
data        = load_data()
events      = load_events()
today       = date.today()
course_list = list(data.keys())
color_map   = {c: COURSE_COLORS[i % len(COURSE_COLORS)] for i, c in enumerate(course_list)}

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="margin-bottom:1.8rem;">
        <div style="font-family:'Playfair Display',serif;font-size:1.4rem;font-weight:800;
                    color:#1a1814;line-height:1.15;letter-spacing:-0.01em;">
            Study<br>Dashboard</div>
        <div style="font-family:'DM Mono',monospace;font-size:0.63rem;color:#9a948c;
                    letter-spacing:0.12em;text-transform:uppercase;margin-top:5px;">
            KFUPM · Spring 2026</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("nav", ["📊  Progress", "📅  Calendar", "⚙️  Manage Courses"],
                    label_visibility="collapsed")

    st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)
    st.markdown("""<div style="font-family:'DM Mono',monospace;font-size:0.63rem;
                    color:#9a948c;letter-spacing:0.1em;text-transform:uppercase;
                    margin-bottom:0.7rem;">Upcoming</div>""", unsafe_allow_html=True)

    upcoming = sorted(
        [e for e in events if datetime.strptime(e["date"], "%Y-%m-%d").date() >= today],
        key=lambda x: x["date"]
    )[:6]

    if upcoming:
        for ev in upcoming:
            ev_d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            diff = (ev_d - today).days
            if diff == 0:   tag, tc = "TODAY",     "#e63946"
            elif diff == 1: tag, tc = "Tomorrow",  "#e76f51"
            elif diff <= 4: tag, tc = f"{diff}d",  "#e76f51"
            else:           tag, tc = f"{diff}d",  "#2d6a4f"
            dc = "#e63946" if ev["type"]=="Exam" else ("#e76f51" if ev["type"]=="Due Date" else "#4361ee")
            st.markdown(f"""
            <div style="display:flex;align-items:flex-start;gap:8px;padding:7px 0;
                        border-bottom:1px solid #f0ede8;">
                <div style="width:8px;height:8px;border-radius:50%;background:{dc};
                            margin-top:4px;flex-shrink:0;"></div>
                <div style="flex:1;min-width:0;">
                    <div style="font-size:0.81rem;font-weight:600;color:#1a1814;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        {ev['title']}</div>
                    <div style="font-size:0.71rem;color:#9a948c;margin-top:1px;">
                        {ev['course']} · <span style="color:{tc};font-weight:600;">{tag}</span></div>
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("<div style='font-size:0.82rem;color:#9a948c;'>No upcoming events</div>",
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE 1 — PROGRESS
# ══════════════════════════════════════════════
if page == "📊  Progress":
    total_all = sum(len(v) for v in data.values())
    done_all  = sum(sum(1 for s in v.values() if s) for v in data.values())
    pct_all   = int(done_all / total_all * 100) if total_all else 0

    # ── Page header ──
    st.markdown(f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;
                margin-bottom:1.8rem;flex-wrap:wrap;gap:1rem;">
        <div>
            <div style="font-family:'Playfair Display',serif;font-size:2.1rem;
                        font-weight:800;color:#1a1814;letter-spacing:-0.02em;
                        line-height:1.1;">Study Progress</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.68rem;color:#9a948c;
                        letter-spacing:0.1em;text-transform:uppercase;margin-top:5px;">
                Spring 2026 — {len(data)} courses tracked</div>
        </div>
        <div style="text-align:right;">
            <div style="font-family:'Playfair Display',serif;font-size:3.2rem;
                        font-weight:800;color:#2d6a4f;line-height:1;">{pct_all}%</div>
            <div style="font-family:'DM Sans',sans-serif;font-size:0.78rem;color:#9a948c;">
                {done_all} of {total_all} topics complete</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── All-courses bar chart ──
    names, pcts, clrs = [], [], []
    for c in course_list:
        t = len(data[c]); d = sum(1 for s in data[c].values() if s)
        names.append(c); pcts.append(int(d/t*100) if t else 0)
        clrs.append(color_map[c])

    fig = go.Figure(go.Bar(
        x=names, y=pcts, marker_color=clrs,
        text=[f"{p}%" for p in pcts], textposition="outside",
        textfont=dict(family="DM Mono", size=11, color="#4a4640"),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#4a4640"),
        yaxis=dict(range=[0,125], showgrid=False, zeroline=False, showticklabels=False),
        xaxis=dict(showgrid=False, tickfont=dict(family="DM Mono", size=11, color="#4a4640")),
        margin=dict(t=30, b=5, l=0, r=0), height=210,
        showlegend=False, bargap=0.4,
    )
    st.plotly_chart(fig, use_container_width=True, key="bar_summary")

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)

    # ── 2-column course cards ──
    course_items = list(data.items())

    for i in range(0, len(course_items), 2):
        col_a, col_b = st.columns(2, gap="medium")

        for col, idx in [(col_a, i), (col_b, i+1)]:
            if idx >= len(course_items):
                break
            course, lectures = course_items[idx]
            total = len(lectures)
            done  = sum(1 for s in lectures.values() if s)
            pct   = done / total if total else 0
            clr   = color_map[course]

            c_evs = sorted(
                [e for e in events if e["course"] == course
                 and datetime.strptime(e["date"], "%Y-%m-%d").date() >= today],
                key=lambda x: x["date"]
            )[:2]

            pills = ""
            for ev in c_evs:
                ev_d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
                diff = (ev_d - today).days
                pc  = "#e63946" if ev["type"]=="Exam" else "#e76f51"
                pbg = "#fde8ea" if ev["type"]=="Exam" else "#fdeee9"
                lbl = "TODAY" if diff==0 else f"{diff}d"
                pills += (f'<span style="background:{pbg};color:{pc};'
                          f'font-family:DM Mono,monospace;font-size:0.61rem;font-weight:600;'
                          f'padding:2px 8px;border-radius:4px;letter-spacing:0.05em;">'
                          f'{ev["type"]} · {lbl}</span> ')

            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;
                            padding:1.3rem 1.4rem 1.1rem;
                            box-shadow:0 2px 10px rgba(0,0,0,0.05);margin-bottom:6px;
                            border-top: 4px solid {clr};">
                    <div style="display:flex;justify-content:space-between;
                                align-items:flex-start;margin-bottom:1rem;">
                        <div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.61rem;
                                        color:#9a948c;letter-spacing:0.1em;
                                        text-transform:uppercase;margin-bottom:3px;">Course</div>
                            <div style="font-family:'Playfair Display',serif;font-size:1.4rem;
                                        font-weight:800;color:#1a1814;letter-spacing:-0.01em;
                                        line-height:1.1;">{course}</div>
                        </div>
                        <div style="text-align:right;padding-top:2px;">
                            <div style="font-family:'Playfair Display',serif;font-size:1.7rem;
                                        font-weight:800;color:{clr};line-height:1;">{int(pct*100)}%</div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.65rem;
                                        color:#9a948c;">{done} / {total}</div>
                        </div>
                    </div>
                    <div style="background:#ede9e4;border-radius:99px;height:5px;
                                margin-bottom:0.9rem;overflow:hidden;">
                        <div style="background:{clr};width:{int(pct*100)}%;height:100%;
                                    border-radius:99px;"></div>
                    </div>
                    <div style="display:flex;gap:5px;flex-wrap:wrap;min-height:1.3rem;">
                        {pills if pills else
                         '<span style="font-size:0.72rem;color:#ccc7be;'
                         'font-family:DM Mono,monospace;">No upcoming events</span>'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander(f"Topics — {course}"):
                    for lec, is_done in lectures.items():
                        checked = st.checkbox(lec, value=is_done, key=f"chk_{course}_{lec}")
                        if checked != is_done:
                            data[course][lec] = checked
                            save_data(data)
                            st.rerun()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE 2 — CALENDAR
# ══════════════════════════════════════════════
elif page == "📅  Calendar":
    st.markdown("""
    <div style="margin-bottom:1.8rem;">
        <div style="font-family:'Playfair Display',serif;font-size:2.1rem;
                    font-weight:800;color:#1a1814;letter-spacing:-0.02em;">Calendar</div>
        <div style="font-family:'DM Mono',monospace;font-size:0.68rem;color:#9a948c;
                    letter-spacing:0.1em;text-transform:uppercase;margin-top:5px;">
            Exams · Due Dates · Reminders</div>
    </div>""", unsafe_allow_html=True)

    col_cal, col_side = st.columns([3, 2], gap="large")

    # ── Calendar grid ──
    with col_cal:
        if "cal_year"  not in st.session_state: st.session_state.cal_year  = today.year
        if "cal_month" not in st.session_state: st.session_state.cal_month = today.month

        n1, n2, n3 = st.columns([1, 5, 1])
        with n1:
            if st.button("←", key="prev_m"):
                if st.session_state.cal_month == 1:
                    st.session_state.cal_month = 12; st.session_state.cal_year -= 1
                else: st.session_state.cal_month -= 1
                st.rerun()
        with n2:
            st.markdown(f"""<div style="text-align:center;font-family:'Playfair Display',serif;
                font-size:1.1rem;font-weight:700;color:#1a1814;padding-top:5px;">
                {calendar.month_name[st.session_state.cal_month]} {st.session_state.cal_year}
                </div>""", unsafe_allow_html=True)
        with n3:
            if st.button("→", key="next_m"):
                if st.session_state.cal_month == 12:
                    st.session_state.cal_month = 1; st.session_state.cal_year += 1
                else: st.session_state.cal_month += 1
                st.rerun()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        ev_map = {}
        for ev in events: ev_map.setdefault(ev["date"], []).append(ev)

        yr, mo = st.session_state.cal_year, st.session_state.cal_month
        cal_m  = calendar.monthcalendar(yr, mo)

        hcols = st.columns(7)
        for i, h in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
            with hcols[i]:
                st.markdown(f"""<div style="text-align:center;font-family:'DM Mono',monospace;
                    font-size:0.63rem;color:#9a948c;letter-spacing:0.08em;
                    text-transform:uppercase;padding-bottom:6px;">{h}</div>""",
                    unsafe_allow_html=True)

        for week in cal_m:
            wcols = st.columns(7)
            for i, day in enumerate(week):
                with wcols[i]:
                    if day == 0:
                        st.markdown("<div style='min-height:60px'></div>", unsafe_allow_html=True)
                        continue
                    cd   = date(yr, mo, day)
                    ds   = str(cd)
                    isd  = (cd == today)
                    cevs = ev_map.get(ds, [])
                    bg   = "#edf6f0" if isd else "#ffffff"
                    bdr  = "2px solid #2d6a4f" if isd else "1.5px solid #e2ddd6"
                    dnc  = "#2d6a4f" if isd else "#1a1814"
                    dots = ""
                    for ev in cevs[:3]:
                        dc = "#e63946" if ev["type"]=="Exam" else ("#e76f51" if ev["type"]=="Due Date" else "#4361ee")
                        sh = ev["title"][:9]+("…" if len(ev["title"])>9 else "")
                        dots += (f'<div style="font-size:0.57rem;color:{dc};'
                                 f'font-family:DM Mono,monospace;white-space:nowrap;'
                                 f'overflow:hidden;text-overflow:ellipsis;line-height:1.4;">'
                                 f'● {sh}</div>')
                    st.markdown(f"""
                    <div style="background:{bg};border:{bdr};border-radius:8px;
                                min-height:60px;padding:5px 6px;">
                        <div style="font-family:'DM Mono',monospace;font-size:0.7rem;
                                    font-weight:{'700' if isd else '400'};color:{dnc};
                                    margin-bottom:2px;">{day}</div>
                        {dots}
                    </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style="display:flex;gap:1.2rem;margin-top:0.9rem;flex-wrap:wrap;">
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#e63946;"></div>
                <span style="font-family:'DM Mono',monospace;font-size:0.67rem;color:#9a948c;">Exam</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#e76f51;"></div>
                <span style="font-family:'DM Mono',monospace;font-size:0.67rem;color:#9a948c;">Due Date</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#4361ee;"></div>
                <span style="font-family:'DM Mono',monospace;font-size:0.67rem;color:#9a948c;">Other</span>
            </div>
        </div>""", unsafe_allow_html=True)

    # ── Right side ──
    with col_side:
        st.markdown("""<div style="font-family:'DM Mono',monospace;font-size:0.67rem;
                        color:#9a948c;letter-spacing:0.1em;text-transform:uppercase;
                        margin-bottom:0.9rem;">Add Event</div>""", unsafe_allow_html=True)

        ev_title  = st.text_input("Title", placeholder="e.g. Midterm Exam", key="ev_t")
        ev_course = st.selectbox("Course", ["General"] + list(data.keys()), key="ev_c")
        ev_type   = st.selectbox("Type", ["Exam", "Due Date", "Other"], key="ev_typ")
        ev_date_v = st.date_input("Date", value=today, key="ev_d")
        ev_notes  = st.text_input("Notes (optional)", placeholder="Room, topics…", key="ev_n")

        if st.button("＋  Add Event", use_container_width=True, key="add_ev"):
            if ev_title.strip():
                events.append({"title": ev_title.strip(), "course": ev_course,
                               "type": ev_type, "date": str(ev_date_v),
                               "notes": ev_notes.strip()})
                save_events(events)
                st.success("Event added!")
                st.rerun()
            else:
                st.warning("Enter a title.")

        st.markdown("""<div style="font-family:'DM Mono',monospace;font-size:0.67rem;
                        color:#9a948c;letter-spacing:0.1em;text-transform:uppercase;
                        margin-top:1.4rem;margin-bottom:0.7rem;">All Events</div>""",
                    unsafe_allow_html=True)

        if not events:
            st.markdown("<div style='font-size:0.84rem;color:#9a948c;'>No events yet.</div>",
                        unsafe_allow_html=True)
        else:
            for i, ev in enumerate(sorted(events, key=lambda x: x["date"])):
                ev_d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
                diff = (ev_d - today).days
                past = ev_d < today
                dc   = "#e63946" if ev["type"]=="Exam" else ("#e76f51" if ev["type"]=="Due Date" else "#4361ee")
                lbl  = "Past" if past else ("TODAY" if diff==0 else f"{diff}d left")
                lc   = "#ccc7be" if past else ("#e63946" if diff<=1 else ("#e76f51" if diff<=4 else "#2d6a4f"))
                op   = "0.45" if past else "1"
                c1, c2 = st.columns([6,1])
                with c1:
                    st.markdown(f"""
                    <div style="opacity:{op};padding:8px 0;border-bottom:1px solid #f0ede8;
                                display:flex;align-items:flex-start;gap:9px;">
                        <div style="width:9px;height:9px;border-radius:50%;background:{dc};
                                    margin-top:4px;flex-shrink:0;"></div>
                        <div>
                            <div style="font-size:0.84rem;font-weight:600;color:#1a1814;">{ev['title']}</div>
                            <div style="font-size:0.72rem;color:#9a948c;margin-top:1px;">
                                {ev['course']} · {ev_d.strftime('%b %d')} ·
                                <span style="color:{lc};font-weight:600;">{lbl}</span></div>
                            {f'<div style="font-size:0.72rem;color:#b0a99e;margin-top:2px;">{ev["notes"]}</div>' if ev.get("notes") else ''}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    if st.button("✕", key=f"del_{i}"):
                        events.pop(i); save_events(events); st.rerun()


# ══════════════════════════════════════════════
#  PAGE 3 — MANAGE COURSES
# ══════════════════════════════════════════════
elif page == "⚙️  Manage Courses":
    st.markdown("""
    <div style="margin-bottom:1.8rem;">
        <div style="font-family:'Playfair Display',serif;font-size:2.1rem;
                    font-weight:800;color:#1a1814;letter-spacing:-0.02em;">Manage Courses</div>
        <div style="font-family:'DM Mono',monospace;font-size:0.68rem;color:#9a948c;
                    letter-spacing:0.1em;text-transform:uppercase;margin-top:5px;">
            Add · Edit · Delete</div>
    </div>""", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["➕  New Course", "✏️  Edit Course", "🗑️  Delete"])

    with tab1:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        new_name   = st.text_input("Course code / name", placeholder="e.g. CHE 410")
        topics_raw = st.text_area("Topics — one per line",
                                   placeholder="Ch1 L1\nCh1 L2\nMidterm Prep", height=180)
        if st.button("Create Course", use_container_width=True):
            n = new_name.strip()
            if not n: st.warning("Enter a course name.")
            elif n in data: st.warning("Already exists.")
            else:
                topics = [t.strip() for t in topics_raw.splitlines() if t.strip()]
                if not topics: st.warning("Add at least one topic.")
                else:
                    data[n] = {t: False for t in topics}
                    save_data(data)
                    st.success(f"✅ {n} created with {len(topics)} topics!")
                    st.rerun()

    with tab2:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if not data: st.info("No courses yet.")
        else:
            sel = st.selectbox("Select course", list(data.keys()), key="edit_sel")
            if sel:
                c1e, c2e = st.columns(2)
                with c1e:
                    nt = st.text_input("Add new topic", key="new_t_inp")
                    if st.button("Add Topic"):
                        nt = nt.strip()
                        if not nt: st.warning("Enter a name.")
                        elif nt in data[sel]: st.warning("Already exists.")
                        else:
                            data[sel][nt] = False; save_data(data)
                            st.success(f"Added '{nt}'"); st.rerun()
                with c2e:
                    new_nm = st.text_input("Rename course to", value=sel, key="ren_c")
                    if st.button("Rename"):
                        nn = new_nm.strip()
                        if nn and nn != sel:
                            if nn in data: st.warning("Name taken.")
                            else:
                                data[nn] = data.pop(sel); save_data(data)
                                st.success(f"Renamed to {nn}"); st.rerun()

                st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
                st.markdown("""<div style="font-family:'DM Mono',monospace;font-size:0.67rem;
                    color:#9a948c;letter-spacing:0.1em;text-transform:uppercase;
                    margin-bottom:0.5rem;">Topics</div>""", unsafe_allow_html=True)

                for topic in list(data[sel].keys()):
                    tc2, dc2 = st.columns([7,1])
                    with tc2:
                        done_t = data[sel][topic]
                        st.markdown(
                            f"<div style='padding:5px 0;font-size:0.84rem;"
                            f"color:{'#2d6a4f' if done_t else '#4a4640'};"
                            f"border-bottom:1px solid #f0ede8;'>"
                            f"{'✓' if done_t else '○'}  {topic}</div>",
                            unsafe_allow_html=True)
                    with dc2:
                        if st.button("✕", key=f"del_t_{sel}_{topic}"):
                            del data[sel][topic]; save_data(data); st.rerun()

    with tab3:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if not data: st.info("No courses to delete.")
        else:
            dc_sel = st.selectbox("Course to delete", list(data.keys()), key="del_c_sel")
            st.warning(f"⚠️ This permanently removes **{dc_sel}** and all its topics.")
            confirm = st.checkbox("I understand, delete this course")
            if st.button("Delete Course", disabled=not confirm):
                del data[dc_sel]; save_data(data)
                st.success(f"Deleted {dc_sel}"); st.rerun()
