import streamlit as st
import json, os, calendar
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from pathlib import Path
import requests

st.set_page_config(page_title="Study Dashboard · KFUPM", layout="wide", page_icon="◈")

# ── Supabase config ───────────────────────────
SUPABASE_URL = "https://bbtumvmmhqghhhggexkw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJidHVtdm1taHFnaGhoZ2dleGt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzczODI0OTksImV4cCI6MjA5Mjk1ODQ5OX0.mhBofxDw9_TsVUMgj74v6C6aTEmbjQ-FwBtsjtuTLwA"
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

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
    "CHE 309": {"HT part": False, "MT Part": False, "FM Part": False, "Final Lab Prep": False},
    "CHE 360": {"unit 6": False, "unit 8": False, "unit 9": False, "Project": False},
    "GS 495":  {"week 8 & 9": False, "week 10": False, "week 11": False, "week 12": False, "Project": False},
    "CHEM 312": {
        "Lab Safety & Density": False,
        "Absorption Spectrum of Conjugated Dye": False,
        "Gas Viscosity": False,
        "Kinetics Using Spectroscopy": False,
        "Fluorescence Quenching of Rhodamine B": False,
        "Adsorption Isotherm of Acetic Acid": False
    }
}

COURSE_COLORS = ["#4361ee","#e63946","#7209b7","#2d6a4f","#e76f51","#0077b6"]
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

# ── Supabase helpers ──────────────────────────
def db_get(table, params=""):
    try:
        r = requests.get(f"{BASE}/{table}?{params}", headers=HEADERS, timeout=10)
        return r.json() if r.ok else []
    except Exception:
        return []

def db_upsert(table, rows):
    """Insert or update — safe, no data loss."""
    if not rows: return True
    h = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    try:
        r = requests.post(f"{BASE}/{table}", headers=h,
                         json=rows if isinstance(rows, list) else [rows], timeout=10)
        return r.ok
    except Exception:
        return False

def db_insert(table, rows):
    if not rows: return True
    try:
        r = requests.post(f"{BASE}/{table}", headers=HEADERS,
                         json=rows if isinstance(rows, list) else [rows], timeout=10)
        return r.ok
    except Exception:
        return False

def db_update(table, data, row_id):
    try:
        r = requests.patch(f"{BASE}/{table}?id=eq.{row_id}", headers=HEADERS,
                          json=data, timeout=10)
        return r.ok
    except Exception:
        return False

def db_delete_all(table):
    """Delete all rows safely."""
    try:
        rows = db_get(table, "select=id")
        if not rows: return True
        ids = [str(r["id"]) for r in rows if "id" in r]
        if not ids: return True
        r = requests.delete(f"{BASE}/{table}?id=in.({','.join(ids)})",
                           headers=HEADERS, timeout=10)
        return r.ok
    except Exception:
        return False

def db_batch_upsert(table, rows):
    """Safer than delete+insert — updates existing, inserts new."""
    if not rows: return True
    h = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    try:
        r = requests.post(f"{BASE}/{table}", headers=h,
                         json=rows if isinstance(rows, list) else [rows], timeout=10)
        return r.ok
    except Exception:
        return False

def safe_date(date_str):
    """Safe date parsing — no crashes on bad data."""
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()

# ── Load functions ────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    rows = db_get("topics")
    if not rows:
        # First run only — seed default data
        seed = [{"course": c, "topic": t, "done": False}
                for c, ts in DEFAULT_DATA.items() for t in ts]
        db_insert("topics", seed)
        return {c: dict(ts) for c, ts in DEFAULT_DATA.items()}
    # Build from database only — no auto re-seeding deleted topics
    merged = {}
    for r in rows:
        c, t = r.get("course",""), r.get("topic","")
        if c and t:
            merged.setdefault(c, {})[t] = bool(r.get("done", False))
    return merged

@st.cache_data(ttl=30)
def load_events():
    rows = db_get("events")
    result = []
    for r in rows:
        result.append({
            "title":  r.get("title",""),
            "date":   r.get("date",""),
            "type":   r.get("type","Other"),
            "course": r.get("course","General"),
            "notes":  r.get("notes","")
        })
    return result

@st.cache_data(ttl=30)
def load_meta():
    meta = {"streak_last": None, "streak_count": 0,
            "priorities": {}, "weekly_plan": {}, "pomodoro_log": {}}
    try:
        sr = db_get("streak", "limit=1")
        if sr:
            meta["streak_last"]  = sr[0].get("last_date")
            meta["streak_count"] = int(sr[0].get("count", 0) or 0)
        for r in db_get("priorities"):
            if r.get("key"):
                meta["priorities"][r["key"]] = r.get("level","")
        for r in db_get("weekly_plan"):
            day, c = r.get("day",""), r.get("course","")
            if day and c:
                meta["weekly_plan"].setdefault(day, []).append(c)
        for r in db_get("pomodoro_log"):
            d, c = r.get("date",""), r.get("course","")
            m = int(r.get("minutes", 0) or 0)
            if d and c:
                meta["pomodoro_log"].setdefault(d, {})[c] = (
                    meta["pomodoro_log"].get(d, {}).get(c, 0) + m)
    except Exception:
        pass
    return meta

# ── Save functions ────────────────────────────
def save_data(data, changed_only=None):
    """Save topics — if changed_only dict provided, only saves those."""
    try:
        # Only fetch and update what changed for speed
        target = changed_only if changed_only else data
        rows = db_get("topics", "select=id,course,topic")
        existing = {(r["course"], r["topic"]): r["id"] for r in rows}
        updates = []
        inserts = []
        for c, ts in target.items():
            for t, done in ts.items():
                if (c, t) in existing:
                    updates.append((existing[(c,t)], done))
                else:
                    inserts.append({"course": c, "topic": t, "done": done})
        # Batch updates
        for row_id, done in updates:
            db_update("topics", {"done": done}, row_id)
        if inserts:
            db_insert("topics", inserts)
        load_data.clear()
        return True
    except Exception as e:
        st.warning(f"⚠️ Could not save topic data: {e}")
        return False

def save_events(events):
    """Safe replace — delete then insert with error handling."""
    db_delete_all("events")
    if events:
        db_insert("events", [{"title": e.get("title",""), "date": e.get("date",""),
            "type": e.get("type","Other"), "course": e.get("course","General"),
            "notes": e.get("notes","")} for e in events])
    load_events.clear()

def save_meta(meta):
    """Use batch upsert where possible to prevent data loss."""
    try:
        # Streak
        db_delete_all("streak")
        db_insert("streak", {"last_date": meta.get("streak_last",""),
                              "count": meta.get("streak_count", 0)})
        # Priorities — use upsert (has unique key column)
        if meta.get("priorities"):
            db_batch_upsert("priorities", [{"key": k, "level": v}
                for k, v in meta["priorities"].items() if v])
        # Weekly plan — delete+insert (day+course combo has no unique key)
        db_delete_all("weekly_plan")
        if meta.get("weekly_plan"):
            db_insert("weekly_plan", [{"day": d, "course": c}
                for d, cs in meta["weekly_plan"].items() for c in cs])
        # Pomodoro log — use upsert to prevent data loss on network failure
        if meta.get("pomodoro_log"):
            log_rows = [{"date": d, "course": c, "minutes": m}
                for d, cs in meta["pomodoro_log"].items() for c, m in cs.items()]
            db_batch_upsert("pomodoro_log", log_rows)
        load_meta.clear()
        return True
    except Exception as e:
        st.warning(f"⚠️ Could not save some data: {e}")
        return False

# ── streak helper ─────────────────────────────
def update_streak(meta):
    today_str = str(date.today())
    last = meta.get("streak_last")
    if last == today_str:
        return meta
    yesterday = str(date.today() - timedelta(days=1))
    if last == yesterday:
        meta["streak_count"] = meta.get("streak_count", 0) + 1
    elif last != today_str:
        meta["streak_count"] = 1
    meta["streak_last"] = today_str
    return meta

# ── dark / light theme CSS ────────────────────
def get_css(dark: bool) -> str:
    if dark:
        BG, WHITE, SURF, SURF2 = "#0f1117","#161b27","#1c2333","#232b3e"
        BORDER, BORDER2        = "#2a3248","#3a4560"
        TEXT, TEXTM, TEXTD     = "#e8eaf0","#9aa0b8","#5a6080"
        ACCENT, ACBL           = "#52b788","#1a3a2a"
        INP_BG                 = "#1c2333"
        HR                     = "#2a3248"
        CARD_SHADOW            = "0 2px 12px rgba(0,0,0,0.3)"
    else:
        BG, WHITE, SURF, SURF2 = "#f5f3ef","#ffffff","#ffffff","#f0ede8"
        BORDER, BORDER2        = "#e2ddd6","#ccc7be"
        TEXT, TEXTM, TEXTD     = "#1a1814","#4a4640","#9a948c"
        ACCENT, ACBL           = "#2d6a4f","#d8f3dc"
        INP_BG                 = "#ffffff"
        HR                     = "#e2ddd6"
        CARD_SHADOW            = "0 2px 10px rgba(0,0,0,0.05)"

    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Playfair+Display:wght@700;800&family=DM+Sans:wght@300;400;500;600&display=swap');
:root {{
    --bg:{BG};--white:{WHITE};--surf:{SURF};--surf2:{SURF2};
    --border:{BORDER};--border2:{BORDER2};
    --text:{TEXT};--textm:{TEXTM};--textd:{TEXTD};
    --accent:{ACCENT};--acbl:{ACBL};
    --inp-bg:{INP_BG};--hr:{HR};--card-shadow:{CARD_SHADOW};
}}
html,body,.stApp{{background:var(--bg)!important;color:var(--text)!important;font-family:'DM Sans',sans-serif!important;}}
#MainMenu,footer{{visibility:hidden;}}
.block-container{{padding:2rem 2.2rem 4rem!important;max-width:100%!important;}}
section[data-testid="stSidebar"]{{background:var(--white)!important;border-right:1.5px solid var(--border)!important;}}
section[data-testid="stSidebar"] .block-container{{padding:1.8rem 1.3rem!important;}}
div[data-testid="stRadio"]>label{{display:none;}}
div[data-testid="stRadio"]>div{{flex-direction:column;gap:3px;}}
div[data-testid="stRadio"]>div>label{{background:transparent!important;border:1.5px solid transparent!important;border-radius:8px!important;padding:9px 13px!important;color:var(--textm)!important;font-family:'DM Sans',sans-serif!important;font-size:0.86rem!important;font-weight:500!important;cursor:pointer;transition:all .15s;}}
div[data-testid="stRadio"]>div>label:hover{{background:var(--surf2)!important;color:var(--text)!important;}}
div[data-testid="stRadio"]>div>label[data-checked="true"]{{background:var(--acbl)!important;border-color:var(--accent)!important;color:var(--accent)!important;font-weight:600!important;}}
.stTextInput input,.stTextArea textarea{{background:var(--inp-bg)!important;border:1.5px solid var(--border)!important;border-radius:8px!important;color:var(--text)!important;font-family:'DM Sans',sans-serif!important;font-size:0.88rem!important;}}
.stTextInput input:focus,.stTextArea textarea:focus{{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(45,106,79,.1)!important;outline:none!important;}}
.stTextInput label,.stTextArea label,.stSelectbox label,.stDateInput label{{font-family:'DM Mono',monospace!important;font-size:0.67rem!important;color:var(--textd)!important;letter-spacing:.1em!important;text-transform:uppercase!important;}}
div[data-baseweb="select"]>div{{background:var(--inp-bg)!important;border:1.5px solid var(--border)!important;border-radius:8px!important;color:var(--text)!important;font-family:'DM Sans',sans-serif!important;font-size:0.88rem!important;}}
.stButton>button{{background:var(--white)!important;border:1.5px solid var(--border2)!important;color:var(--textm)!important;font-family:'DM Sans',sans-serif!important;font-size:.84rem!important;font-weight:500!important;border-radius:8px!important;transition:all .15s!important;}}
.stButton>button:hover{{border-color:var(--accent)!important;color:var(--accent)!important;background:var(--acbl)!important;}}
.stTabs [data-baseweb="tab-list"]{{background:transparent!important;border-bottom:2px solid var(--border)!important;gap:0!important;}}
.stTabs [data-baseweb="tab"]{{background:transparent!important;color:var(--textd)!important;font-family:'DM Sans',sans-serif!important;font-size:.86rem!important;font-weight:500!important;padding:9px 20px!important;border-bottom:2px solid transparent!important;margin-bottom:-2px!important;}}
.stTabs [aria-selected="true"]{{color:var(--accent)!important;border-bottom-color:var(--accent)!important;font-weight:600!important;}}
details{{background:var(--white)!important;border:1.5px solid var(--border)!important;border-radius:10px!important;overflow:hidden;}}
details summary{{font-family:'DM Sans',sans-serif!important;font-size:.84rem!important;padding:10px 14px!important;color:var(--textm)!important;font-weight:500!important;}}
details[open]{{border-color:var(--border2)!important;}}
.stCheckbox label{{font-family:'DM Sans',sans-serif!important;font-size:.84rem!important;color:var(--textm)!important;}}
div[data-testid="stProgressBar"]>div{{background:var(--surf2)!important;border-radius:99px!important;height:6px!important;}}
div[data-testid="stProgressBar"]>div>div{{background:linear-gradient(90deg,var(--accent),#52b788)!important;border-radius:99px!important;}}
hr{{border-color:var(--hr)!important;}}
</style>"""

# ── session state defaults ────────────────────
if "dark"          not in st.session_state: st.session_state.dark          = False
if "pomo_running"  not in st.session_state: st.session_state.pomo_running  = False
if "pomo_wall_start" not in st.session_state: st.session_state.pomo_wall_start = None  # time.time() when timer started
if "pomo_elapsed"  not in st.session_state: st.session_state.pomo_elapsed  = 0.0       # seconds elapsed before last pause
if "pomo_total"    not in st.session_state: st.session_state.pomo_total    = 1500
if "pomo_course"   not in st.session_state: st.session_state.pomo_course   = None
if "pomo_is_work"  not in st.session_state: st.session_state.pomo_is_work  = True
if "pomo_finished" not in st.session_state: st.session_state.pomo_finished = False
if "cal_year"  not in st.session_state: st.session_state.cal_year  = date.today().year
if "cal_month" not in st.session_state: st.session_state.cal_month = date.today().month

# ── load all state ────────────────────────────
data   = load_data()
events = load_events()
meta   = load_meta()
today  = date.today()
course_list = list(data.keys())
color_map   = {c: COURSE_COLORS[i % len(COURSE_COLORS)] for i, c in enumerate(course_list)}

# ── inject CSS ────────────────────────────────
st.markdown(get_css(st.session_state.dark), unsafe_allow_html=True)

dark = st.session_state.dark
TEXT    = "#e8eaf0" if dark else "#1a1814"
TEXTM   = "#9aa0b8" if dark else "#4a4640"
TEXTD   = "#5a6080" if dark else "#9a948c"
WHITE   = "#161b27" if dark else "#ffffff"
SURF2   = "#232b3e" if dark else "#f0ede8"
BORDER  = "#2a3248" if dark else "#e2ddd6"
ACCENT  = "#52b788" if dark else "#2d6a4f"
BG      = "#0f1117" if dark else "#f5f3ef"
HR_CLR  = "#2a3248" if dark else "#f0ede8"

# ── helpers ───────────────────────────────────
def prio_icon(p):
    return {"high":"🔴","medium":"🟡","low":"🟢"}.get(p,"")

def card_style(clr):
    return (f"background:{WHITE};border:1.5px solid {BORDER};"
            f"border-radius:14px;padding:1.3rem 1.4rem 1.1rem;"
            f"border-top:4px solid {clr};margin-bottom:6px;"
            f"box-shadow:{'0 2px 12px rgba(0,0,0,0.25)' if dark else '0 2px 10px rgba(0,0,0,0.05)'};")

def label_style():
    return (f"font-family:'DM Mono',monospace;font-size:0.67rem;"
            f"color:{TEXTD};letter-spacing:.1em;text-transform:uppercase;")

def heading(text, sub=""):
    st.markdown(f"""
    <div style="margin-bottom:1.8rem;">
        <div style="font-family:'Playfair Display',serif;font-size:2.1rem;
                    font-weight:800;color:{TEXT};letter-spacing:-.02em;line-height:1.1;">{text}</div>
        {"" if not sub else f'<div style="{label_style()}margin-top:5px;">{sub}</div>'}
    </div>""", unsafe_allow_html=True)

# ── next exam helper ──────────────────────────
def next_exam():
    exams = [e for e in events if e["type"]=="Exam"
             and safe_date(e["date"]) >= today]
    if not exams: return None
    return min(exams, key=lambda x: x["date"])

# ════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════
with st.sidebar:
    # Logo + dark mode toggle
    c_logo, c_toggle = st.columns([3,1])
    with c_logo:
        st.markdown(f"""
        <div style="font-family:'Playfair Display',serif;font-size:1.3rem;
                    font-weight:800;color:{TEXT};line-height:1.15;letter-spacing:-.01em;">
            Study<br>Dashboard</div>
        <div style="{label_style()}margin-top:5px;">KFUPM · Spring 2026</div>
        """, unsafe_allow_html=True)
    with c_toggle:
        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
        if st.button("🌙" if not dark else "☀️", key="toggle_dark", help="Toggle dark/light mode"):
            st.session_state.dark = not st.session_state.dark
            st.rerun()

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    page = st.radio("nav", [
        "📊  Progress",
        "⏱️  Pomodoro",
        "📅  Calendar",
        "📆  Weekly Plan",
        "⚙️  Manage Courses"
    ], label_visibility="collapsed")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # ── Streak ──
    total_all = sum(len(v) for v in data.values())
    done_all  = sum(sum(1 for s in v.values() if s) for v in data.values())

    streak = meta.get("streak_count", 0)
    st.markdown(f"""
    <div style="background:{'#1a3a2a' if dark else '#edf6f0'};border:1.5px solid {'#2d6a4f44' if dark else '#b7dfc4'};
                border-radius:10px;padding:.8rem 1rem;margin-bottom:1rem;">
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="font-size:1.4rem;">🔥</div>
            <div>
                <div style="font-family:'Playfair Display',serif;font-size:1.3rem;
                            font-weight:800;color:{ACCENT};line-height:1;">{streak}</div>
                <div style="{label_style()}">day streak</div>
            </div>
            <div style="margin-left:auto;text-align:right;">
                <div style="font-family:'DM Mono',monospace;font-size:1rem;
                            font-weight:700;color:{TEXT};">{int(done_all/total_all*100) if total_all else 0}%</div>
                <div style="{label_style()}">overall</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Next exam countdown ──
    ne = next_exam()
    if ne:
        ne_d  = safe_date(ne["date"])
        diff  = (ne_d - today).days
        urgency_clr = "#e63946" if diff <= 3 else ("#e76f51" if diff <= 7 else ACCENT)
        st.markdown(f"""
        <div style="background:{WHITE};border:1.5px solid {urgency_clr}44;
                    border-left:4px solid {urgency_clr};border-radius:10px;
                    padding:.8rem 1rem;margin-bottom:1rem;">
            <div style="{label_style()}margin-bottom:3px;">Next Exam</div>
            <div style="font-size:.88rem;font-weight:600;color:{TEXT};">{ne['title']}</div>
            <div style="font-size:.75rem;color:{TEXTD};margin-top:2px;">{ne['course']}</div>
            <div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                        font-weight:800;color:{urgency_clr};line-height:1.1;margin-top:4px;">
                {"TODAY" if diff==0 else f"{diff}d"}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Upcoming events ──
    st.markdown(f'<div style="{label_style()}margin-bottom:.6rem;">Upcoming</div>',
                unsafe_allow_html=True)
    upcoming = sorted([e for e in events
                       if safe_date(e["date"]) >= today],
                      key=lambda x: x["date"])[:5]
    if upcoming:
        for ev in upcoming:
            ev_d = safe_date(ev["date"])
            diff = (ev_d - today).days
            tag  = "TODAY" if diff==0 else ("Tomorrow" if diff==1 else f"{diff}d")
            tc   = "#e63946" if diff<=1 else ("#e76f51" if diff<=4 else ACCENT)
            dc   = "#e63946" if ev["type"]=="Exam" else ("#e76f51" if ev["type"]=="Due Date" else "#4361ee")
            st.markdown(f"""
            <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;
                        border-bottom:1px solid {HR_CLR};">
                <div style="width:8px;height:8px;border-radius:50%;background:{dc};
                            margin-top:4px;flex-shrink:0;"></div>
                <div style="flex:1;min-width:0;">
                    <div style="font-size:.8rem;font-weight:600;color:{TEXT};
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{ev['title']}</div>
                    <div style="font-size:.7rem;color:{TEXTD};margin-top:1px;">
                        {ev['course']} · <span style="color:{tc};font-weight:600;">{tag}</span></div>
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='font-size:.82rem;color:{TEXTD};'>No upcoming events</div>",
                    unsafe_allow_html=True)


# ════════════════════════════════════════════════
#  PAGE 1 — PROGRESS
# ════════════════════════════════════════════════
if page == "📊  Progress":

    # Exam countdown banner
    ne = next_exam()
    if ne:
        ne_d = safe_date(ne["date"])
        diff = (ne_d - today).days
        if diff <= 7:
            uc = "#e63946" if diff<=2 else "#e76f51"
            ubg = "#fde8ea44" if dark else ("#fde8ea" if diff<=2 else "#fdeee9")
            st.markdown(f"""
            <div style="background:{ubg};border:1.5px solid {uc}55;border-left:4px solid {uc};
                        border-radius:10px;padding:.9rem 1.2rem;margin-bottom:1.5rem;
                        display:flex;align-items:center;gap:1rem;">
                <div style="font-size:1.6rem;">🚨</div>
                <div>
                    <div style="font-size:.84rem;font-weight:700;color:{uc};">
                        {"TODAY" if diff==0 else f"In {diff} day{'s' if diff!=1 else ''}"} — {ne['title']}</div>
                    <div style="font-size:.76rem;color:{TEXTD};margin-top:2px;">{ne['course']} · {ne_d.strftime('%A, %b %d')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    heading("Study Progress", f"Spring 2026 — {len(data)} courses tracked")

    # ── EXAM DATES TABLE ──────────────────────────────────────────
    exam_events = sorted(
        [e for e in events if e.get("type") == "Exam" and safe_date(e["date"]) >= today],
        key=lambda x: x["date"]
    )
    if exam_events:
        st.markdown(f"""
        <div style="background:{WHITE};border:1.5px solid {BORDER};border-radius:14px;
                    padding:1.2rem 1.4rem;margin-bottom:1.5rem;">
            <div style="font-family:'Playfair Display',serif;font-size:1.1rem;
                        font-weight:800;color:{TEXT};margin-bottom:1rem;">📋 Upcoming Exams</div>
        """, unsafe_allow_html=True)
        for e in exam_events:
            ex_date = safe_date(e["date"])
            diff = (ex_date - today).days
            if diff == 0:
                badge_color = "#e63946"; badge_bg = "#fde8ea"; badge_txt = "TODAY 🚨"
            elif diff <= 3:
                badge_color = "#e63946"; badge_bg = "#fde8ea"; badge_txt = f"{diff}d left 🔴"
            elif diff <= 7:
                badge_color = "#e76f51"; badge_bg = "#fdeee9"; badge_txt = f"{diff}d left 🟠"
            else:
                badge_color = "#2d6a4f"; badge_bg = "#d8f3dc"; badge_txt = f"{diff}d left 🟢"
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        padding:.6rem .8rem;margin-bottom:.4rem;background:{SURF2};
                        border-radius:8px;border-left:3px solid {badge_color};">
                <div>
                    <div style="font-weight:700;font-size:.9rem;color:{TEXT};">{e['title']}</div>
                    <div style="font-size:.75rem;color:{TEXTD};margin-top:2px;">
                        {e.get('course','General')} · {ex_date.strftime('%A, %b %d %Y')}
                    </div>
                </div>
                <div style="background:{badge_bg};color:{badge_color};font-family:'DM Mono',monospace;
                            font-size:.75rem;font-weight:700;padding:4px 10px;border-radius:6px;
                            white-space:nowrap;">{badge_txt}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── ACHIEVEMENT BADGES ────────────────────────────────────────
    # Pre-calculate stats once to avoid re-summing on every UI interaction
    streak        = meta.get("streak_count", 0)
    pomo_log      = meta.get("pomodoro_log", {})
    pomo_days     = len(pomo_log)
    total_mins    = sum(sum(v.values()) for v in pomo_log.values()) if pomo_log else 0
    done_all_badges = sum(sum(1 for s in v.values() if s) for v in data.values())
    courses_done  = sum(1 for c in data.values() if len(c) > 0 and all(c.values()))

    badges = []
    if streak >= 1:   badges.append(("🔥", f"{streak} Day Streak", "#e63946", "#fde8ea"))
    if streak >= 7:   badges.append(("🏆", "Week Warrior", "#e76f51", "#fdeee9"))
    if streak >= 30:  badges.append(("👑", "Month Master", "#7209b7", "#f0e6ff"))
    if done_all_badges >= 10: badges.append(("✅", "10 Topics Done", "#2d6a4f", "#d8f3dc"))
    if done_all_badges >= 25: badges.append(("🎯", "25 Topics Done", "#0077b6", "#e0f0ff"))
    if total_mins >= 60:  badges.append(("⏱️", "1hr Studied", "#4361ee", "#eef0ff"))
    if total_mins >= 300: badges.append(("💪", "5hrs Studied", "#7209b7", "#f0e6ff"))
    if courses_done >= 1: badges.append(("🎓", "Course Complete!", "#2d6a4f", "#d8f3dc"))
    if pomo_days >= 3:    badges.append(("📅", "3-Day Grind", "#e76f51", "#fdeee9"))

    if badges:
        badge_html = "".join([
            f'<div style="display:inline-flex;align-items:center;gap:6px;background:{bg};'
            f'color:{clr};border-radius:20px;padding:5px 12px;margin:3px;font-size:.78rem;font-weight:600;">'
            f'{icon} {label}</div>'
            for icon, label, clr, bg in badges
        ])
        st.markdown(f"""
        <div style="background:{WHITE};border:1.5px solid {BORDER};border-radius:14px;
                    padding:1rem 1.4rem;margin-bottom:1.5rem;">
            <div style="font-family:'Playfair Display',serif;font-size:1.1rem;
                        font-weight:800;color:{TEXT};margin-bottom:.8rem;">🏅 Achievements</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;">{badge_html}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── DAILY STUDY GOAL ─────────────────────────────────────────
    today_str = str(today)
    today_mins = sum(meta.get("pomodoro_log", {}).get(today_str, {}).values())
    goal_mins = int(meta.get("priorities", {}).get("__daily_goal__", 120) or 120)
    goal_pct  = min(100, int(today_mins / goal_mins * 100))
    goal_clr  = "#e63946" if goal_pct < 33 else ("#e76f51" if goal_pct < 66 else "#2d6a4f")
    goal_emoji = "🔴" if goal_pct < 33 else ("🟠" if goal_pct < 66 else "🟢")
    st.markdown(f"""
    <div style="background:{WHITE};border:1.5px solid {BORDER};border-radius:14px;
                padding:1rem 1.4rem;margin-bottom:1.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">
            <div style="font-family:'Playfair Display',serif;font-size:1.1rem;
                        font-weight:800;color:{TEXT};">⏰ Daily Study Goal {goal_emoji}</div>
            <div style="font-family:'DM Mono',monospace;font-size:.85rem;color:{goal_clr};font-weight:700;">
                {today_mins}min / {goal_mins}min</div>
        </div>
        <div style="background:{SURF2};border-radius:99px;height:8px;overflow:hidden;">
            <div style="background:{goal_clr};width:{goal_pct}%;height:100%;
                        border-radius:99px;transition:width .3s;"></div>
        </div>
        <div style="font-size:.74rem;color:{TEXTD};margin-top:.4rem;">
            {"🎉 Goal reached! Great work today!" if goal_pct >= 100
             else f"{goal_mins - today_mins} min remaining to reach your daily goal"}</div>
    </div>
    """, unsafe_allow_html=True)

    # Daily goal setter
    with st.expander("⚙️ Set Daily Study Goal"):
        current_goal = int(meta.get("priorities", {}).get("__daily_goal__", 120) or 120)
        with st.form("goal_form"):
            new_goal = st.slider("Daily goal (minutes)", 30, 480, current_goal, 30)
            if st.form_submit_button("💾 Save Goal"):
                meta.setdefault("priorities", {})["__daily_goal__"] = new_goal
                if save_meta(meta):
                    st.success("Goal saved!")
                    st.rerun()

    # Stats row
    pct_all = int(done_all/total_all*100) if total_all else 0
    s1,s2,s3,s4 = st.columns(4)
    for col, val, lbl in [(s1,f"{pct_all}%","Overall"),
                           (s2,done_all,"Topics Done"),
                           (s3,total_all-done_all,"Remaining"),
                           (s4,meta.get("streak_count",0),"Day Streak 🔥")]:
        with col:
            st.markdown(f"""
            <div style="background:{WHITE};border:1.5px solid {BORDER};border-radius:12px;
                        padding:1rem;text-align:center;margin-bottom:1rem;">
                <div style="font-family:'Playfair Display',serif;font-size:2rem;
                            font-weight:800;color:{ACCENT};line-height:1;">{val}</div>
                <div style="{label_style()}margin-top:4px;">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    # Bar chart
    names,pcts,clrs = [],[],[]
    for c in course_list:
        t=len(data[c]); d=sum(1 for s in data[c].values() if s)
        names.append(c); pcts.append(int(d/t*100) if t else 0); clrs.append(color_map[c])
    fig = go.Figure(go.Bar(x=names, y=pcts, marker_color=clrs,
                           text=[f"{p}%" for p in pcts], textposition="outside",
                           textfont=dict(family="DM Mono",size=11,color=TEXTM)))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="DM Sans",color=TEXTM),
                      yaxis=dict(range=[0,130],showgrid=False,zeroline=False,showticklabels=False),
                      xaxis=dict(showgrid=False,tickfont=dict(family="DM Mono",size=11,color=TEXTM)),
                      margin=dict(t=30,b=5,l=0,r=0),height=210,showlegend=False,bargap=0.4)
    st.plotly_chart(fig, use_container_width=True, key="bar")
    st.markdown("<hr>", unsafe_allow_html=True)

    # 2-column course cards
    course_items = list(data.items())
    for i in range(0, len(course_items), 2):
        col_a, col_b = st.columns(2, gap="medium")
        for col, idx in [(col_a,i),(col_b,i+1)]:
            if idx >= len(course_items): break
            course, lectures = course_items[idx]
            total = len(lectures)
            done  = sum(1 for s in lectures.values() if s)
            pct   = done/total if total else 0
            clr   = color_map[course]

            c_evs = sorted([e for e in events if e["course"]==course
                            and safe_date(e["date"]) >= today],
                           key=lambda x: x["date"])[:2]
            pills = ""
            for ev in c_evs:
                ev_d = safe_date(ev["date"])
                diff = (ev_d - today).days
                pc = "#e63946" if ev["type"]=="Exam" else "#e76f51"
                pbg= "#fde8ea" if ev["type"]=="Exam" else "#fdeee9"
                lbl= "TODAY" if diff==0 else f"{diff}d"
                pills += (f'<span style="background:{pbg};color:{pc};font-family:DM Mono,monospace;'
                          f'font-size:.61rem;font-weight:600;padding:2px 8px;border-radius:4px;">'
                          f'{ev["type"]} · {lbl}</span> ')

            with col:
                st.markdown(f"""
                <div style="{card_style(clr)}">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1rem;">
                        <div>
                            <div style="{label_style()}margin-bottom:3px;">Course</div>
                            <div style="font-family:'Playfair Display',serif;font-size:1.4rem;
                                        font-weight:800;color:{TEXT};line-height:1.1;">{course}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-family:'Playfair Display',serif;font-size:1.7rem;
                                        font-weight:800;color:{clr};line-height:1;">{int(pct*100)}%</div>
                            <div style="font-family:'DM Mono',monospace;font-size:.65rem;color:{TEXTD};">{done}/{total}</div>
                        </div>
                    </div>
                    <div style="background:{SURF2};border-radius:99px;height:5px;margin-bottom:.9rem;overflow:hidden;">
                        <div style="background:{clr};width:{int(pct*100)}%;height:100%;border-radius:99px;"></div>
                    </div>
                    <div style="display:flex;gap:5px;flex-wrap:wrap;min-height:1.3rem;">
                        {pills if pills else f'<span style="font-size:.72rem;color:{TEXTD};font-family:DM Mono,monospace;">No upcoming events</span>'}
                    </div>
                </div>""", unsafe_allow_html=True)

                with st.expander(f"Topics — {course}"):
                    changed = False
                    prio_changed = False
                    for lec, is_done in lectures.items():
                        prio_key = f"{course}::{lec}"
                        prio = meta.get("priorities",{}).get(prio_key,"")
                        tc, tb = st.columns([5,1])
                        with tc:
                            checked = st.checkbox(
                                f"{prio_icon(prio)} {lec}" if prio else lec,
                                value=is_done, key=f"chk_{course}_{lec}")
                            if checked != is_done:
                                data[course][lec] = checked
                                changed = True
                        with tb:
                            new_prio = st.selectbox("Priority",["","high","medium","low"],
                                                    index=["","high","medium","low"].index(prio),
                                                    key=f"prio_{course}_{lec}",
                                                    label_visibility="collapsed")
                            if new_prio != prio:
                                meta.setdefault("priorities",{})[prio_key] = new_prio
                                prio_changed = True
                    # Save ONCE after all checkboxes processed
                    if changed:
                        save_data(data)
                        meta = update_streak(meta)
                        save_meta(meta)
                        st.rerun()
                    elif prio_changed:
                        save_meta(meta)
                        st.rerun()
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════
#  PAGE 2 — POMODORO
# ════════════════════════════════════════════════
elif page == "\u23f1\ufe0f  Pomodoro":
    import time as _time
    import streamlit.components.v1 as components
    heading("Pomodoro Timer", "Focus sessions \u00b7 25 min work / 5 min break")

    # ---- Server-side persistent timer -----------------------------------------
    ss = st.session_state
    now_wall = _time.time()
    if ss.pomo_running and ss.pomo_wall_start is not None:
        elapsed_now = ss.pomo_elapsed + (now_wall - ss.pomo_wall_start)
    else:
        elapsed_now = ss.pomo_elapsed
    secs_left_now = max(0.0, ss.pomo_total - elapsed_now)

    # Auto-finish if timer ran out while user navigated away
    if ss.pomo_running and secs_left_now <= 0 and not ss.pomo_finished:
        ss.pomo_running   = False
        ss.pomo_finished  = True
        ss.pomo_elapsed   = float(ss.pomo_total)
        if ss.pomo_is_work and ss.pomo_course:
            today_str = str(today)
            mins_done = round(ss.pomo_total / 60)
            meta.setdefault("pomodoro_log", {}).setdefault(today_str, {})
            meta["pomodoro_log"][today_str][ss.pomo_course] = (
                meta["pomodoro_log"][today_str].get(ss.pomo_course, 0) + mins_done)
            meta = update_streak(meta)
            save_meta(meta)
        st.rerun()

    col_timer, col_log = st.columns([2, 3], gap="large")

    with col_timer:
        disabled = ss.pomo_running or ss.pomo_finished

        course_keys = list(data.keys())
        default_idx = course_keys.index(ss.pomo_course) if ss.pomo_course in course_keys else 0
        pomo_course_sel = st.selectbox("Studying for", course_keys,
                                       index=default_idx, disabled=disabled,
                                       key="pomo_course_sel")

        pomo_type = st.radio("Session type", ["\U0001f345 Work (25 min)", "\u2615 Break (5 min)"],
                             horizontal=True, disabled=disabled, key="pomo_type")

        minutes       = 25 if "Work" in pomo_type else 5
        seconds_total = minutes * 60

        use_custom = st.checkbox("Custom duration", disabled=disabled, key="pomo_custom")
        if use_custom:
            custom_mins   = st.number_input("Minutes", min_value=1, max_value=180,
                                            value=minutes, step=1, disabled=disabled,
                                            key="pomo_custom_mins")
            minutes       = custom_mins
            seconds_total = minutes * 60

        # Control buttons
        b1, b2 = st.columns(2)
        with b1:
            if not ss.pomo_running and not ss.pomo_finished:
                if st.button("\u25b6  Start", use_container_width=True, key="pomo_btn_start"):
                    ss.pomo_course     = pomo_course_sel
                    ss.pomo_is_work    = "Work" in pomo_type
                    ss.pomo_total      = float(seconds_total)
                    ss.pomo_elapsed    = 0.0
                    ss.pomo_wall_start = _time.time()
                    ss.pomo_running    = True
                    ss.pomo_finished   = False
                    st.rerun()
            elif ss.pomo_running:
                if st.button("\u23f8  Pause", use_container_width=True, key="pomo_btn_pause"):
                    ss.pomo_elapsed    = elapsed_now
                    ss.pomo_running    = False
                    ss.pomo_wall_start = None
                    st.rerun()
            else:
                st.button("\u25b6  Start", use_container_width=True, disabled=True,
                          key="pomo_btn_done")
        with b2:
            if st.button("\u21ba  Reset", use_container_width=True, key="pomo_btn_reset"):
                ss.pomo_running    = False
                ss.pomo_finished   = False
                ss.pomo_elapsed    = 0.0
                ss.pomo_wall_start = None
                st.rerun()

        if not ss.pomo_running and not ss.pomo_finished and ss.pomo_elapsed > 0:
            if st.button("\u25b6  Resume", use_container_width=True, key="pomo_btn_resume"):
                ss.pomo_wall_start = _time.time()
                ss.pomo_running    = True
                st.rerun()

        # Ring display (static SVG re-rendered each tick)
        secs_show   = int(secs_left_now)
        mins_disp   = secs_show // 60
        secs_disp   = secs_show % 60
        total_f     = float(ss.pomo_total) if ss.pomo_total else float(seconds_total)
        pct_done    = min(1.0, elapsed_now / total_f) if total_f > 0 else 0.0
        CIRC        = 565.49
        ring_offset = CIRC * (1.0 - pct_done)
        ring_color  = "#52b788" if ss.pomo_finished else ACCENT
        track_color = "#2a3248" if dark else "#f0ede8"
        bg_color    = "#161b27" if dark else "#ffffff"
        lbl_color   = "#5a6080" if dark else "#9a948c"
        status_text = ("Session complete! \u2705 Logged automatically." if ss.pomo_finished
                       else ("\u23f8 Paused \u2014 press Resume to continue"
                             if (not ss.pomo_running and ss.pomo_elapsed > 0)
                             else ("\U0001f345 Focus! Stay on task." if ss.pomo_running
                                   else "Ready \u2014 press Start")))
        status_clr  = ("#52b788" if ss.pomo_finished
                       else (TEXTD if not ss.pomo_running else ACCENT))
        course_lbl  = ss.pomo_course or pomo_course_sel
        lbl_txt     = "FOCUS" if ss.pomo_is_work else "BREAK"

        components.html(
            f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@800&family=DM+Mono:wght@400&family=DM+Sans:wght@500&display=swap');
body{{margin:0;padding:1.2rem 1rem;background:{bg_color};display:flex;flex-direction:column;align-items:center;font-family:'DM Sans',sans-serif;}}
#ring{{position:relative;width:200px;height:200px;margin-bottom:.7rem;}}
svg{{transform:rotate(-90deg);}}
#center{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;}}
#td{{font-family:'Playfair Display',serif;font-size:2.6rem;font-weight:800;color:{ring_color};line-height:1;}}
#lbl{{font-family:'DM Mono',monospace;font-size:.62rem;color:{lbl_color};letter-spacing:.1em;text-transform:uppercase;margin-top:3px;}}
#status{{font-size:.82rem;font-weight:600;color:{status_clr};margin-top:.6rem;text-align:center;max-width:220px;}}
#clbl{{font-family:'DM Mono',monospace;font-size:.72rem;color:{lbl_color};margin-top:.3rem;letter-spacing:.05em;}}
</style>
<div id="ring">
<svg width="200" height="200" viewBox="0 0 200 200">
  <circle cx="100" cy="100" r="90" fill="none" stroke="{track_color}" stroke-width="10"/>
  <circle cx="100" cy="100" r="90" fill="none" stroke="{ring_color}" stroke-width="10"
          stroke-linecap="round" stroke-dasharray="{CIRC:.2f}" stroke-dashoffset="{ring_offset:.2f}"/>
</svg>
<div id="center"><div id="td">{mins_disp:02d}:{secs_disp:02d}</div><div id="lbl">{lbl_txt}</div></div>
</div>
<div id="status">{status_text}</div>
<div id="clbl">{course_lbl}</div>""",
            height=290)

        # Tick every second while running
        if ss.pomo_running:
            _time.sleep(1)
            st.rerun()

        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        st.markdown(f'<div style="{label_style()}margin-bottom:.5rem;">Log Study Time Manually</div>',
                    unsafe_allow_html=True)
        log_course = st.selectbox("Course", list(data.keys()), key="log_course")
        log_min    = st.number_input("Minutes studied (type any amount)", min_value=1,
                                     max_value=600, value=25, step=5, key="log_min")
        if st.button("\u2705  Add to Today's Log", use_container_width=True):
            today_str = str(today)
            meta.setdefault("pomodoro_log", {}).setdefault(today_str, {})
            meta["pomodoro_log"][today_str][log_course] = (
                meta["pomodoro_log"][today_str].get(log_course, 0) + log_min)
            meta = update_streak(meta)
            save_meta(meta)
            st.success(f"Logged {log_min} min for {log_course}!")
            st.rerun()

    with col_log:
        st.markdown(f'<div style="{label_style()}margin-bottom:.8rem;">Study Log — Last 7 Days</div>',
                    unsafe_allow_html=True)

        plog = meta.get("pomodoro_log", {})
        last7     = [(today - timedelta(days=i)) for i in range(6,-1,-1)]
        last7_str = [str(d) for d in last7]

        chart_data = {c: [] for c in course_list}
        for ds in last7_str:
            day_log = plog.get(ds, {})
            for c in course_list:
                chart_data[c].append(day_log.get(c, 0))

        day_labels = [d.strftime("%a %d") for d in last7]
        fig2 = go.Figure()
        for c in course_list:
            if sum(chart_data[c]) > 0:
                fig2.add_trace(go.Bar(name=c, x=day_labels, y=chart_data[c],
                                      marker_color=color_map[c]))
        fig2.update_layout(
            barmode="stack",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color=TEXTM),
            yaxis=dict(title="Minutes", showgrid=True,
                       gridcolor="rgba(42,50,72,0.19)" if dark else "rgba(226,221,214,0.5)",
                       zeroline=False, tickfont=dict(family="DM Mono",size=10,color=TEXTD)),
            xaxis=dict(showgrid=False, tickfont=dict(family="DM Mono",size=10,color=TEXTD)),
            margin=dict(t=10,b=5,l=0,r=0), height=280,
            legend=dict(font=dict(family="DM Sans",size=11,color=TEXTM), bgcolor="rgba(0,0,0,0)")
        )
        st.plotly_chart(fig2, use_container_width=True, key="pomo_chart")

        st.markdown(f'<div style="{label_style()}margin-bottom:.6rem;margin-top:.4rem;">All-Time Totals</div>',
                    unsafe_allow_html=True)
        totals = {}
        for day_data in plog.values():
            for c, m in day_data.items():
                totals[c] = totals.get(c, 0) + m
        if totals:
            for c, mins in sorted(totals.items(), key=lambda x: -x[1]):
                hrs = mins // 60; rem = mins % 60
                time_str = f"{hrs}h {rem}m" if hrs else f"{rem}m"
                clr     = color_map.get(c, "#888")
                pct_bar = min(100, int(mins / max(totals.values()) * 100))
                st.markdown(f"""
                <div style="margin-bottom:.5rem;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                        <span style="font-size:.82rem;font-weight:600;color:{TEXT};">{c}</span>
                        <span style="font-family:'DM Mono',monospace;font-size:.76rem;color:{TEXTD};">{time_str}</span>
                    </div>
                    <div style="background:{SURF2};border-radius:99px;height:4px;overflow:hidden;">
                        <div style="background:{clr};width:{pct_bar}%;height:100%;border-radius:99px;"></div>
                    </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-size:.84rem;color:{TEXTD};'>No sessions logged yet.</div>",
                        unsafe_allow_html=True)

# ════════════════════════════════════════════════
#  PAGE 3 — CALENDAR
# ════════════════════════════════════════════════
elif page == "📅  Calendar":
    heading("Calendar", "Exams · Due Dates · Reminders")
    col_cal, col_side = st.columns([3,2], gap="large")

    with col_cal:
        n1,n2,n3 = st.columns([1,5,1])
        with n1:
            if st.button("←", key="prev_m"):
                if st.session_state.cal_month==1:
                    st.session_state.cal_month=12; st.session_state.cal_year-=1
                else: st.session_state.cal_month-=1
                st.rerun()
        with n2:
            st.markdown(f"""<div style="text-align:center;font-family:'Playfair Display',serif;
                font-size:1.1rem;font-weight:700;color:{TEXT};padding-top:5px;">
                {calendar.month_name[st.session_state.cal_month]} {st.session_state.cal_year}
                </div>""", unsafe_allow_html=True)
        with n3:
            if st.button("→", key="next_m"):
                if st.session_state.cal_month==12:
                    st.session_state.cal_month=1; st.session_state.cal_year+=1
                else: st.session_state.cal_month+=1
                st.rerun()

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        ev_map = {}
        for ev in events: ev_map.setdefault(ev["date"],[]).append(ev)
        yr,mo = st.session_state.cal_year, st.session_state.cal_month
        cal_m = calendar.monthcalendar(yr, mo)
        hcols = st.columns(7)
        for i,h in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
            with hcols[i]:
                st.markdown(f"""<div style="text-align:center;font-family:'DM Mono',monospace;
                    font-size:.63rem;color:{TEXTD};letter-spacing:.08em;text-transform:uppercase;
                    padding-bottom:6px;">{h}</div>""", unsafe_allow_html=True)

        for week in cal_m:
            wcols = st.columns(7)
            for i, day in enumerate(week):
                with wcols[i]:
                    if day==0:
                        st.markdown("<div style='min-height:60px'></div>", unsafe_allow_html=True)
                        continue
                    cd = date(yr,mo,day); ds = str(cd)
                    isd = (cd==today); cevs = ev_map.get(ds,[])
                    bg  = ("#1a3a2a" if dark else "#edf6f0") if isd else WHITE
                    bdr = f"2px solid {ACCENT}" if isd else f"1.5px solid {BORDER}"
                    dnc = ACCENT if isd else TEXT
                    dots = ""
                    for ev in cevs[:3]:
                        dc = "#e63946" if ev["type"]=="Exam" else ("#e76f51" if ev["type"]=="Due Date" else "#4361ee")
                        sh = ev["title"][:9]+("…" if len(ev["title"])>9 else "")
                        dots += (f'<div style="font-size:.57rem;color:{dc};font-family:DM Mono,monospace;'
                                 f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4;">'
                                 f'● {sh}</div>')
                    st.markdown(f"""
                    <div style="background:{bg};border:{bdr};border-radius:8px;
                                min-height:60px;padding:5px 6px;">
                        <div style="font-family:'DM Mono',monospace;font-size:.7rem;
                                    font-weight:{'700' if isd else '400'};color:{dnc};margin-bottom:2px;">{day}</div>
                        {dots}
                    </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="display:flex;gap:1.2rem;margin-top:.9rem;flex-wrap:wrap;">
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#e63946;"></div>
                <span style="font-family:'DM Mono',monospace;font-size:.67rem;color:{TEXTD};">Exam</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#e76f51;"></div>
                <span style="font-family:'DM Mono',monospace;font-size:.67rem;color:{TEXTD};">Due Date</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#4361ee;"></div>
                <span style="font-family:'DM Mono',monospace;font-size:.67rem;color:{TEXTD};">Other</span>
            </div>
        </div>""", unsafe_allow_html=True)

    with col_side:
        st.markdown(f'<div style="{label_style()}margin-bottom:.9rem;">Add Event</div>',
                    unsafe_allow_html=True)
        ev_title  = st.text_input("Title", placeholder="e.g. Midterm Exam", key="ev_t")
        ev_course = st.selectbox("Course", ["General"]+list(data.keys()), key="ev_c")
        ev_type   = st.selectbox("Type", ["Exam","Due Date","Other"], key="ev_typ")
        ev_date_v = st.date_input("Date", value=today, key="ev_d")
        ev_notes  = st.text_input("Notes (optional)", placeholder="Room, topics…", key="ev_n")
        if st.button("＋  Add Event", use_container_width=True, key="add_ev"):
            if ev_title.strip():
                events.append({"title":ev_title.strip(),"course":ev_course,
                               "type":ev_type,"date":str(ev_date_v),"notes":ev_notes.strip()})
                save_events(events); st.success("Added!"); st.rerun()
            else: st.warning("Enter a title.")

        st.markdown(f'<div style="{label_style()}margin-top:1.3rem;margin-bottom:.7rem;">All Events</div>',
                    unsafe_allow_html=True)
        if not events:
            st.markdown(f"<div style='font-size:.84rem;color:{TEXTD};'>No events yet.</div>",
                        unsafe_allow_html=True)
        else:
            for i,ev in enumerate(sorted(events, key=lambda x: x["date"])):
                ev_d = safe_date(ev["date"])
                diff = (ev_d-today).days; past = ev_d<today
                dc  = "#e63946" if ev["type"]=="Exam" else ("#e76f51" if ev["type"]=="Due Date" else "#4361ee")
                lbl = "Past" if past else ("TODAY" if diff==0 else f"{diff}d left")
                lc  = TEXTD if past else ("#e63946" if diff<=1 else ("#e76f51" if diff<=4 else ACCENT))
                op  = "0.4" if past else "1"
                c1,c2 = st.columns([6,1])
                with c1:
                    st.markdown(f"""
                    <div style="opacity:{op};padding:8px 0;border-bottom:1px solid {HR_CLR};
                                display:flex;align-items:flex-start;gap:9px;">
                        <div style="width:9px;height:9px;border-radius:50%;background:{dc};
                                    margin-top:4px;flex-shrink:0;"></div>
                        <div>
                            <div style="font-size:.84rem;font-weight:600;color:{TEXT};">{ev['title']}</div>
                            <div style="font-size:.72rem;color:{TEXTD};margin-top:1px;">
                                {ev['course']} · {ev_d.strftime('%b %d')} ·
                                <span style="color:{lc};font-weight:600;">{lbl}</span></div>
                            {f'<div style="font-size:.72rem;color:{TEXTD};margin-top:2px;">{ev["notes"]}</div>' if ev.get("notes") else ''}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    if st.button("✕", key=f"del_{i}"):
                        events.pop(i); save_events(events); st.rerun()


# ════════════════════════════════════════════════
#  PAGE 4 — WEEKLY PLAN
# ════════════════════════════════════════════════
elif page == "📆  Weekly Plan":
    heading("Weekly Study Plan", "Assign courses to days — plan your week")

    plan = meta.get("weekly_plan", {d:[] for d in DAYS})
    # Clean up any deleted courses from the plan
    plan = {d: [c for c in cs if c in data] for d, cs in plan.items()}

    # PDF export button (generates printable HTML → triggers browser print)
    st.markdown(f"""
    <div style="display:flex;justify-content:flex-end;margin-bottom:1rem;">
        <button onclick="window.print()"
            style="background:{ACCENT};color:white;border:none;border-radius:8px;
                   padding:.5rem 1.3rem;font-family:'DM Sans',sans-serif;
                   font-size:.84rem;font-weight:600;cursor:pointer;
                   box-shadow:0 2px 8px rgba(45,106,79,.3);">
            🖨️  Print / Save as PDF
        </button>
    </div>
    <style>
    @media print {{
        section[data-testid="stSidebar"], .stButton {{ display: none !important; }}
        .block-container {{ padding: 0 !important; }}
    }}
    </style>
    """, unsafe_allow_html=True)

    # Week grid — 7 columns
    day_cols = st.columns(7, gap="small")
    today_name = today.strftime("%A")

    for i, (day, col) in enumerate(zip(DAYS, day_cols)):
        with col:
            is_today = (day == today_name)
            # Day header
            st.markdown(f"""
            <div style="background:{'#1a3a2a' if (dark and is_today) else (ACCENT if is_today else WHITE)};
                        border:1.5px solid {ACCENT if is_today else BORDER};
                        border-radius:10px 10px 0 0;padding:.6rem .7rem;text-align:center;
                        margin-bottom:2px;">
                <div style="font-family:'DM Mono',monospace;font-size:.63rem;
                            color:{'white' if is_today else TEXTD};
                            letter-spacing:.08em;text-transform:uppercase;">{day[:3]}</div>
                <div style="font-family:'Playfair Display',serif;font-size:1rem;
                            font-weight:700;color:{'white' if is_today else TEXT};">
                    {(today + timedelta(days=(i - today.weekday()) % 7)).day}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Assigned courses as chips
            assigned = plan.get(day, [])
            for c in assigned:
                clr = color_map.get(c, "#888")
                t   = len(data.get(c,{}))
                d2  = sum(1 for s in data.get(c,{}).values() if s)
                p   = int(d2/t*100) if t else 0
                st.markdown(f"""
                <div style="background:{clr}18;border:1.5px solid {clr}55;
                            border-left:3px solid {clr};border-radius:6px;
                            padding:.4rem .5rem;margin-bottom:4px;">
                    <div style="font-size:.72rem;font-weight:700;color:{clr};
                                font-family:'DM Mono',monospace;">{c}</div>
                    <div style="font-size:.65rem;color:{TEXTD};">{p}% done</div>
                </div>""", unsafe_allow_html=True)

            # Events on this day
            day_date = today + timedelta(days=(i - today.weekday()) % 7)
            day_evs  = [e for e in events if e["date"] == str(day_date)]
            for ev in day_evs:
                ec = "#e63946" if ev["type"]=="Exam" else ("#e76f51" if ev["type"]=="Due Date" else "#4361ee")
                st.markdown(f"""
                <div style="background:{ec}15;border:1px solid {ec}44;border-radius:5px;
                            padding:3px 6px;margin-bottom:3px;">
                    <div style="font-size:.65rem;color:{ec};font-weight:600;
                                font-family:'DM Mono',monospace;white-space:nowrap;
                                overflow:hidden;text-overflow:ellipsis;">📌 {ev['title'][:12]}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f'<div style="{label_style()}margin:1rem 0 .8rem;">Edit Weekly Plan</div>',
                unsafe_allow_html=True)

    edit_cols = st.columns(7, gap="small")
    for day, col in zip(DAYS, edit_cols):
        with col:
            assigned = plan.get(day, [])
            st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:.65rem;color:{TEXTD};margin-bottom:3px;'>{day[:3].upper()}</div>", unsafe_allow_html=True)
            to_add = st.selectbox("Add", ["—"]+[c for c in course_list if c not in assigned],
                                  key=f"plan_add_{day}", label_visibility="collapsed")
            if to_add != "—":
                plan.setdefault(day,[]).append(to_add)
                meta["weekly_plan"] = plan; save_meta(meta); st.rerun()
            for c in list(assigned):
                if st.button(f"✕ {c}", key=f"plan_del_{day}_{c}"):
                    plan[day].remove(c)
                    meta["weekly_plan"] = plan; save_meta(meta); st.rerun()


# ════════════════════════════════════════════════
#  PAGE 5 — MANAGE COURSES
# ════════════════════════════════════════════════
elif page == "⚙️  Manage Courses":
    heading("Manage Courses", "Add · Edit · Delete")
    tab1,tab2,tab3 = st.tabs(["➕  New Course","✏️  Edit Course","🗑️  Delete"])

    with tab1:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
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
                    data[n]={t:False for t in topics}; save_data(data)
                    st.success(f"✅ {n} created with {len(topics)} topics!"); st.rerun()

    with tab2:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        if not data: st.info("No courses yet.")
        else:
            sel = st.selectbox("Select course", list(data.keys()), key="edit_sel")
            if sel:
                c1e,c2e = st.columns(2)
                with c1e:
                    nt = st.text_input("Add new topic", key="new_t_inp")
                    if st.button("Add Topic"):
                        nt=nt.strip()
                        if not nt: st.warning("Enter a name.")
                        elif nt in data[sel]: st.warning("Already exists.")
                        else:
                            data[sel][nt]=False; save_data(data)
                            st.success(f"Added '{nt}'"); st.rerun()
                with c2e:
                    new_nm = st.text_input("Rename course to", value=sel, key="ren_c")
                    if st.button("Rename"):
                        nn=new_nm.strip()
                        if nn and nn!=sel:
                            if nn in data: st.warning("Name taken.")
                            else:
                                data[nn]=data.pop(sel); save_data(data)
                                st.success(f"Renamed to {nn}"); st.rerun()
                st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
                st.markdown(f'<div style="{label_style()}margin-bottom:.5rem;">Topics</div>',
                            unsafe_allow_html=True)
                for topic in list(data[sel].keys()):
                    tc2,dc2 = st.columns([7,1])
                    with tc2:
                        done_t = data[sel][topic]
                        pkey   = f"{sel}::{topic}"
                        prio   = meta.get("priorities",{}).get(pkey,"")
                        st.markdown(
                            f"<div style='padding:5px 0;font-size:.84rem;"
                            f"color:{ACCENT if done_t else TEXTM};"
                            f"border-bottom:1px solid {HR_CLR};'>"
                            f"{'✓' if done_t else '○'} {prio_icon(prio)} {topic}</div>",
                            unsafe_allow_html=True)
                    with dc2:
                        if st.button("✕", key=f"del_t_{sel}_{topic}"):
                            del data[sel][topic]; save_data(data); st.rerun()

    with tab3:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        if not data: st.info("No courses to delete.")
        else:
            dc_sel = st.selectbox("Course to delete", list(data.keys()), key="del_c_sel")
            st.warning(f"⚠️ This permanently removes **{dc_sel}** and all its topics.")
            confirm = st.checkbox("I understand, delete this course")
            if st.button("Delete Course", disabled=not confirm):
                del data[dc_sel]; save_data(data)
                st.success(f"Deleted {dc_sel}"); st.rerun()
