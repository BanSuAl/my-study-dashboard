"""
Study Dashboard — KFUPM
Single-file Streamlit application backed by Supabase (PostgREST).

Credentials are read from st.secrets (see SECRETS_HELP below) or environment
variables. Nothing sensitive is hardcoded in this file.
"""

import os
import html
import json
import uuid
import time
import hashlib
import calendar
from datetime import datetime, date, timedelta, timezone

import requests
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

st.set_page_config(page_title="Study Dashboard · KFUPM", layout="wide", page_icon="◈")

# ══════════════════════════════════════════════════════════════════════
#  TIMEZONE — all "today" logic is anchored to Asia/Riyadh, never the
#  server's local time. This keeps streaks, the daily goal and the
#  Pomodoro log on the correct day when deployed to a UTC host.
# ══════════════════════════════════════════════════════════════════════
try:
    from zoneinfo import ZoneInfo
    RIYADH = ZoneInfo("Asia/Riyadh")
except Exception:                                   # tzdata missing
    RIYADH = timezone(timedelta(hours=3))


def now_local() -> datetime:
    return datetime.now(RIYADH)


TODAY = now_local().date()
TODAY_STR = str(TODAY)

# ══════════════════════════════════════════════════════════════════════
#  CONFIG / SECRETS
# ══════════════════════════════════════════════════════════════════════
SECRETS_HELP = """
**Supabase credentials are not configured.**

Create `.streamlit/secrets.toml` next to this file (and add `.streamlit/` to
your `.gitignore`):

```toml
[supabase]
url = "https://YOUR-PROJECT.supabase.co"
key = "YOUR-ANON-KEY"
```

On Streamlit Community Cloud: **Manage app → Settings → Secrets**, paste the
same block. Environment variables `SUPABASE_URL` / `SUPABASE_KEY` also work.
"""


def _secret(*path, default=None):
    """Read a nested value from st.secrets without raising."""
    try:
        node = st.secrets
        for part in path:
            node = node[part]
        return node
    except Exception:
        return default


SUPABASE_URL = (
    _secret("supabase", "url")
    or _secret("SUPABASE_URL")
    or os.environ.get("SUPABASE_URL")
    or ""
).rstrip("/")

SUPABASE_KEY = (
    _secret("supabase", "key")
    or _secret("SUPABASE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Configuration required")
    st.markdown(SECRETS_HELP)
    st.stop()

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

CACHE_TTL = 60          # seconds; caches are also cleared explicitly on write
MAX_ROWS = 10000        # explicit cap so PostgREST never truncates silently
POMO_TICK = 2.0         # seconds between server ticks while a timer runs

COURSE_COLORS = ["#4361ee", "#e63946", "#7209b7", "#2d6a4f", "#e76f51", "#0077b6"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TODOS_KEY = "__todos__"
GOAL_KEY = "__daily_goal__"

PAGE_LABELS = {
    "Progress":        "📊  Progress",
    "Pomodoro":        "⏱️  Pomodoro",
    "Calendar":        "📅  Calendar",
    "Weekly Plan":     "📆  Weekly Plan",
    "Manage Courses":  "⚙️  Manage Courses",
}
LABEL_TO_PAGE = {v: k for k, v in PAGE_LABELS.items()}


# ══════════════════════════════════════════════════════════════════════
#  SMALL HELPERS
# ══════════════════════════════════════════════════════════════════════
def esc(value) -> str:
    """Escape user-supplied text before it goes into raw HTML."""
    return html.escape(str(value if value is not None else ""), quote=True)


def parse_date(value):
    """Return a date, or None if the value cannot be parsed. Never guesses."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


FAR_FUTURE = date(9999, 12, 31)


def sort_key_date(value):
    """Sort helper that pushes unparseable dates to the end instead of crashing."""
    return parse_date(value) or FAR_FUTURE


def wkey(*parts) -> str:
    """Collision-free Streamlit widget key from arbitrary user text."""
    raw = "\x1f".join(str(p) for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def prio_key(course, topic) -> str:
    return f"{course}::{topic}"


# ══════════════════════════════════════════════════════════════════════
#  DATABASE LAYER
#
#  Every call either succeeds or raises DBError. Nothing returns an empty
#  list on failure, which is what previously made a dropped request look
#  like "the table is empty" and triggered re-seeding.
# ══════════════════════════════════════════════════════════════════════
class DBError(Exception):
    pass


@st.cache_resource(show_spinner=False)
def _http():
    """Pooled session — reuses the TLS connection across requests."""
    sess = requests.Session()
    sess.headers.update(HEADERS)
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=4, pool_maxsize=8, max_retries=2
    )
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def _req(method, table, *, params=None, body=None, prefer=None, timeout=12):
    headers = {"Prefer": prefer} if prefer else None
    try:
        resp = _http().request(
            method, f"{BASE}/{table}",
            params=params, json=body, headers=headers, timeout=timeout,
        )
    except requests.RequestException as exc:
        raise DBError(f"could not reach the database ({exc.__class__.__name__})") from exc

    if not resp.ok:
        detail = (resp.text or "").strip()[:180]
        raise DBError(f"HTTP {resp.status_code} — {detail or 'no details'}")
    return resp


def db_select(table, select="*", filters=None, order=None, limit=MAX_ROWS):
    params = {"select": select, "limit": str(limit)}
    if order:
        params["order"] = order
    if filters:
        params.update(filters)
    resp = _req("GET", table, params=params)
    try:
        rows = resp.json()
    except ValueError as exc:
        raise DBError("database returned a malformed response") from exc
    return rows if isinstance(rows, list) else []


def db_insert(table, rows):
    payload = rows if isinstance(rows, list) else [rows]
    if not payload:
        return
    _req("POST", table, body=payload, prefer="return=minimal")


def db_upsert(table, rows, on_conflict=None):
    payload = rows if isinstance(rows, list) else [rows]
    if not payload:
        return
    params = {"on_conflict": on_conflict} if on_conflict else None
    _req("POST", table, params=params, body=payload,
         prefer="resolution=merge-duplicates,return=minimal")


def db_update(table, filters, data):
    if not filters:
        raise DBError("refusing to update every row (no filter supplied)")
    _req("PATCH", table, params=dict(filters), body=data, prefer="return=minimal")


def db_delete(table, filters):
    if not filters:
        raise DBError("refusing to delete every row (no filter supplied)")
    _req("DELETE", table, params=dict(filters), prefer="return=minimal")


def eq(value) -> str:
    """PostgREST equality filter value. requests percent-encodes it for us."""
    return f"eq.{value}"


def db_action(label, fn, *args, **kwargs):
    """Run a write. Returns True on success; surfaces the real error on failure.

    Callers must only st.rerun() when this returns True, otherwise the error
    message is wiped off the screen before it can be read.
    """
    try:
        fn(*args, **kwargs)
        return True
    except DBError as exc:
        st.error(f"{label} failed — {exc}")
        return False
    except Exception as exc:                        # noqa: BLE001 - last resort
        st.error(f"{label} failed — unexpected error: {exc}")
        return False


# ══════════════════════════════════════════════════════════════════════
#  LOADERS
#
#  Cached functions raise on failure (Streamlit does not cache exceptions,
#  so a transient outage is not remembered for the whole TTL). The thin
#  wrappers below turn that into a (value, error) pair for the UI.
# ══════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_topics():
    return db_select("topics", "id,course,topic,done", order="id.asc")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_events():
    return db_select("events", "id,title,date,type,course,notes", order="date.asc")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_meta():
    return {
        "streak":       db_select("streak", "id,last_date,count", order="id.asc", limit=5),
        "priorities":   db_select("priorities", "id,key,level"),
        "weekly_plan":  db_select("weekly_plan", "id,day,course"),
        "pomodoro_log": db_select("pomodoro_log", "id,date,course,minutes"),
    }


def safe_load(loader, fallback):
    try:
        return loader(), None
    except DBError as exc:
        return fallback, str(exc)
    except Exception as exc:                        # noqa: BLE001
        return fallback, f"unexpected error: {exc}"


def refresh(topics=False, events=False, meta=False):
    if topics:
        fetch_topics.clear()
    if events:
        fetch_events.clear()
    if meta:
        fetch_meta.clear()


def build_topics(rows):
    """rows -> {course: {topic: done}} preserving insertion order."""
    out = {}
    for row in rows:
        course, topic = row.get("course"), row.get("topic")
        if course and topic:
            out.setdefault(course, {})[topic] = bool(row.get("done"))
    return out


def build_events(rows):
    out = []
    for row in rows:
        out.append({
            "id":     row.get("id"),
            "title":  row.get("title") or "",
            "date":   row.get("date") or "",
            "type":   row.get("type") or "Other",
            "course": row.get("course") or "General",
            "notes":  row.get("notes") or "",
        })
    return out


def build_meta(raw):
    streak_rows = raw.get("streak") or []
    first = streak_rows[0] if streak_rows else {}
    try:
        streak_count = int(first.get("count") or 0)
    except (TypeError, ValueError):
        streak_count = 0

    priorities = {}
    for row in raw.get("priorities") or []:
        if row.get("key"):
            priorities[row["key"]] = row.get("level") or ""

    plan = {}
    for row in raw.get("weekly_plan") or []:
        day, course = row.get("day"), row.get("course")
        if day and course and course not in plan.get(day, []):
            plan.setdefault(day, []).append(course)

    plog = {}
    for row in raw.get("pomodoro_log") or []:
        day, course = row.get("date"), row.get("course")
        try:
            minutes = int(row.get("minutes") or 0)
        except (TypeError, ValueError):
            minutes = 0
        if day and course:
            plog.setdefault(day, {})[course] = plog.get(day, {}).get(course, 0) + minutes

    return {
        "streak_id":      first.get("id"),
        "streak_last":    first.get("last_date"),
        "streak_count":   streak_count,
        "priorities":     priorities,
        "priority_rows":  raw.get("priorities") or [],
        "weekly_plan":    plan,
        "pomodoro_log":   plog,
        "pomodoro_rows":  raw.get("pomodoro_log") or [],
    }


def read_todos(meta):
    raw = meta["priorities"].get(TODOS_KEY)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    clean = []
    for item in parsed:
        if isinstance(item, dict) and item.get("text"):
            clean.append({
                "id":   str(item.get("id") or uuid.uuid4()),
                "text": str(item["text"]),
                "done": bool(item.get("done")),
            })
    return clean


def read_goal(meta):
    try:
        value = int(meta["priorities"].get(GOAL_KEY) or 120)
    except (TypeError, ValueError):
        value = 120
    return max(1, value)


# ══════════════════════════════════════════════════════════════════════
#  MUTATIONS — every write is targeted. No delete-everything-then-insert.
# ══════════════════════════════════════════════════════════════════════
def set_kv(meta, key, value):
    """Upsert one row in `priorities`, or delete it when value is empty."""
    if value in (None, ""):
        db_delete("priorities", {"key": eq(key)})
        return
    row = next((r for r in meta["priority_rows"] if r.get("key") == key), None)
    if row and row.get("id") is not None:
        db_update("priorities", {"id": eq(row["id"])}, {"level": str(value)})
    else:
        try:
            db_upsert("priorities", {"key": key, "level": str(value)}, on_conflict="key")
        except DBError:
            db_insert("priorities", {"key": key, "level": str(value)})


def set_topic_done(course, topic, done):
    db_update("topics", {"course": eq(course), "topic": eq(topic)}, {"done": bool(done)})


def record_activity(meta):
    """Advance the streak for today. Idempotent within a single day."""
    if meta["streak_last"] == TODAY_STR:
        return
    last = parse_date(meta["streak_last"])
    count = meta["streak_count"] + 1 if last == TODAY - timedelta(days=1) else 1
    payload = {"last_date": TODAY_STR, "count": count}
    if meta["streak_id"] is not None:
        db_update("streak", {"id": eq(meta["streak_id"])}, payload)
    else:
        db_insert("streak", payload)
    meta["streak_last"] = TODAY_STR
    meta["streak_count"] = count


def display_streak(meta):
    """The stored count is only a live streak if it touches today or yesterday."""
    last = parse_date(meta["streak_last"])
    if last and (TODAY - last).days <= 1:
        return meta["streak_count"]
    return 0


def add_minutes(meta, day_str, course, minutes):
    """Add minutes to one (date, course) cell without rewriting the whole log."""
    minutes = int(minutes)
    if minutes <= 0:
        return
    row = next(
        (r for r in meta["pomodoro_rows"]
         if r.get("date") == day_str and r.get("course") == course),
        None,
    )
    if row and row.get("id") is not None:
        try:
            current = int(row.get("minutes") or 0)
        except (TypeError, ValueError):
            current = 0
        db_update("pomodoro_log", {"id": eq(row["id"])}, {"minutes": current + minutes})
    else:
        db_insert("pomodoro_log", {"date": day_str, "course": course, "minutes": minutes})
    record_activity(meta)


def save_todos(meta, todos):
    set_kv(meta, TODOS_KEY, json.dumps(todos, ensure_ascii=False))


def delete_topic(meta, course, topic):
    db_delete("topics", {"course": eq(course), "topic": eq(topic)})
    key = prio_key(course, topic)
    if key in meta["priorities"]:
        db_delete("priorities", {"key": eq(key)})


def delete_course(meta, course):
    """Remove the course and everything keyed to it. Pomodoro history and
    calendar events are deliberately kept — they are a record of work done."""
    db_delete("topics", {"course": eq(course)})
    db_delete("weekly_plan", {"course": eq(course)})
    prefix = f"{course}::"
    for row in meta["priority_rows"]:
        key = row.get("key") or ""
        if key.startswith(prefix) and row.get("id") is not None:
            db_delete("priorities", {"id": eq(row["id"])})


def rename_course(meta, old, new):
    """Rename in place across every table that references the course name."""
    db_update("topics", {"course": eq(old)}, {"course": new})
    db_update("weekly_plan", {"course": eq(old)}, {"course": new})
    db_update("events", {"course": eq(old)}, {"course": new})
    db_update("pomodoro_log", {"course": eq(old)}, {"course": new})
    prefix = f"{old}::"
    for row in meta["priority_rows"]:
        key = row.get("key") or ""
        if key.startswith(prefix) and row.get("id") is not None:
            db_update("priorities", {"id": eq(row["id"])},
                      {"key": f"{new}::{key[len(prefix):]}"})


# ══════════════════════════════════════════════════════════════════════
#  THEME
# ══════════════════════════════════════════════════════════════════════
def get_css(dark: bool) -> str:
    if dark:
        BG, WHITE, SURF, SURF2 = "#0f1117", "#161b27", "#1c2333", "#232b3e"
        BORDER, BORDER2        = "#2a3248", "#3a4560"
        TEXT, TEXTM, TEXTD     = "#e8eaf0", "#9aa0b8", "#5a6080"
        ACCENT, ACBL           = "#52b788", "#1a3a2a"
        INP_BG                 = "#1c2333"
        HR                     = "#2a3248"
        CARD_SHADOW            = "0 2px 12px rgba(0,0,0,0.3)"
    else:
        BG, WHITE, SURF, SURF2 = "#f5f3ef", "#ffffff", "#ffffff", "#f0ede8"
        BORDER, BORDER2        = "#e2ddd6", "#ccc7be"
        TEXT, TEXTM, TEXTD     = "#1a1814", "#4a4640", "#9a948c"
        ACCENT, ACBL           = "#2d6a4f", "#d8f3dc"
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


# ══════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════
_DEFAULT_STATE = {
    "dark": False,
    "pomo_running": False,
    "pomo_wall_start": None,     # time.time() when the timer last started
    "pomo_elapsed": 0.0,         # seconds accumulated before the last pause
    "pomo_total": 1500.0,
    "pomo_course": None,
    "pomo_is_work": True,
    "pomo_finished": False,
    "pomo_token": None,          # identifies one run, so it can only log once
    "pomo_logged": set(),
    "cal_year": TODAY.year,
    "cal_month": TODAY.month,
}
for _k, _v in _DEFAULT_STATE.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ══════════════════════════════════════════════════════════════════════
#  LOAD STATE
# ══════════════════════════════════════════════════════════════════════
topic_rows, topics_err = safe_load(fetch_topics, [])
event_rows, events_err = safe_load(fetch_events, [])
meta_raw, meta_err     = safe_load(fetch_meta,
                                   {"streak": [], "priorities": [],
                                    "weekly_plan": [], "pomodoro_log": []})

st.markdown(get_css(st.session_state.dark), unsafe_allow_html=True)

for _label, _err in (("Courses", topics_err), ("Events", events_err), ("Settings", meta_err)):
    if _err:
        st.error(f"{_label} could not be loaded — {_err}")

if topics_err or events_err or meta_err:
    st.info("Showing whatever loaded successfully. Saving is disabled for the "
            "failed sections until the connection recovers.")
    if st.button("↻  Retry"):
        refresh(topics=True, events=True, meta=True)
        st.rerun()

data   = build_topics(topic_rows)
events = build_events(event_rows)
meta   = build_meta(meta_raw)
todos  = read_todos(meta)
today  = TODAY

# No auto-seeding: an empty `topics` table just means an empty dashboard.
# The user adds their first course from the "Manage Courses" page.
course_list = list(data.keys())
color_map = {c: COURSE_COLORS[i % len(COURSE_COLORS)] for i, c in enumerate(course_list)}
can_write = topics_err is None and meta_err is None

dark = st.session_state.dark
TEXT   = "#e8eaf0" if dark else "#1a1814"
TEXTM  = "#9aa0b8" if dark else "#4a4640"
TEXTD  = "#5a6080" if dark else "#9a948c"
WHITE  = "#161b27" if dark else "#ffffff"
SURF2  = "#232b3e" if dark else "#f0ede8"
BORDER = "#2a3248" if dark else "#e2ddd6"
ACCENT = "#52b788" if dark else "#2d6a4f"
BG     = "#0f1117" if dark else "#f5f3ef"
HR_CLR = "#2a3248" if dark else "#f0ede8"


def tint(color, light_bg):
    """Badge background: keep the light pastel, use a translucent tint in dark."""
    return f"{color}26" if dark else light_bg


def prio_icon(p):
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(p, "")


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
                    font-weight:800;color:{TEXT};letter-spacing:-.02em;line-height:1.1;">{esc(text)}</div>
        {"" if not sub else f'<div style="{label_style()}margin-top:5px;">{esc(sub)}</div>'}
    </div>""", unsafe_allow_html=True)


def upcoming_events(kind=None, course=None):
    """Events dated today or later, sorted by real parsed date."""
    out = []
    for ev in events:
        day = parse_date(ev["date"])
        if day is None or day < today:
            continue
        if kind and ev["type"] != kind:
            continue
        if course and ev["course"] != course:
            continue
        out.append(ev)
    return sorted(out, key=lambda e: sort_key_date(e["date"]))


def next_exam():
    exams = upcoming_events(kind="Exam")
    return exams[0] if exams else None


# ══════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════
with st.sidebar:
    c_logo, c_toggle = st.columns([3, 1])
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

    page_label = st.radio("nav", list(PAGE_LABELS.values()), label_visibility="collapsed")
    page = LABEL_TO_PAGE[page_label]

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    total_all = sum(len(v) for v in data.values())
    done_all = sum(sum(1 for s in v.values() if s) for v in data.values())
    streak = display_streak(meta)

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
                            font-weight:700;color:{TEXT};">{int(done_all / total_all * 100) if total_all else 0}%</div>
                <div style="{label_style()}">overall</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    ne = next_exam()
    if ne:
        ne_d = parse_date(ne["date"])
        diff = (ne_d - today).days
        urgency_clr = "#e63946" if diff <= 3 else ("#e76f51" if diff <= 7 else ACCENT)
        st.markdown(f"""
        <div style="background:{WHITE};border:1.5px solid {urgency_clr}44;
                    border-left:4px solid {urgency_clr};border-radius:10px;
                    padding:.8rem 1rem;margin-bottom:1rem;">
            <div style="{label_style()}margin-bottom:3px;">Next Exam</div>
            <div style="font-size:.88rem;font-weight:600;color:{TEXT};">{esc(ne['title'])}</div>
            <div style="font-size:.75rem;color:{TEXTD};margin-top:2px;">{esc(ne['course'])}</div>
            <div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                        font-weight:800;color:{urgency_clr};line-height:1.1;margin-top:4px;">
                {"TODAY" if diff == 0 else f"{diff}d"}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f'<div style="{label_style()}margin-bottom:.6rem;">Upcoming</div>',
                unsafe_allow_html=True)
    upcoming = upcoming_events()[:5]
    if upcoming:
        for ev in upcoming:
            diff = (parse_date(ev["date"]) - today).days
            tag = "TODAY" if diff == 0 else ("Tomorrow" if diff == 1 else f"{diff}d")
            tc = "#e63946" if diff <= 1 else ("#e76f51" if diff <= 4 else ACCENT)
            dc = "#e63946" if ev["type"] == "Exam" else ("#e76f51" if ev["type"] == "Due Date" else "#4361ee")
            st.markdown(f"""
            <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;
                        border-bottom:1px solid {HR_CLR};">
                <div style="width:8px;height:8px;border-radius:50%;background:{dc};
                            margin-top:4px;flex-shrink:0;"></div>
                <div style="flex:1;min-width:0;">
                    <div style="font-size:.8rem;font-weight:600;color:{TEXT};
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{esc(ev['title'])}</div>
                    <div style="font-size:.7rem;color:{TEXTD};margin-top:1px;">
                        {esc(ev['course'])} · <span style="color:{tc};font-weight:600;">{tag}</span></div>
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='font-size:.82rem;color:{TEXTD};'>No upcoming events</div>",
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  PAGE 1 — PROGRESS
# ══════════════════════════════════════════════════════════════════════
if page == "Progress":
    main_col, todo_col = st.columns([3, 1], gap="large")

    with main_col:
        ne = next_exam()
        if ne:
            ne_d = parse_date(ne["date"])
            diff = (ne_d - today).days
            if diff <= 7:
                uc = "#e63946" if diff <= 2 else "#e76f51"
                ubg = "#fde8ea44" if dark else ("#fde8ea" if diff <= 2 else "#fdeee9")
                st.markdown(f"""
                <div style="background:{ubg};border:1.5px solid {uc}55;border-left:4px solid {uc};
                            border-radius:10px;padding:.9rem 1.2rem;margin-bottom:1.5rem;
                            display:flex;align-items:center;gap:1rem;">
                    <div style="font-size:1.6rem;">🚨</div>
                    <div>
                        <div style="font-size:.84rem;font-weight:700;color:{uc};">
                            {"TODAY" if diff == 0 else f"In {diff} day{'s' if diff != 1 else ''}"} — {esc(ne['title'])}</div>
                        <div style="font-size:.76rem;color:{TEXTD};margin-top:2px;">{esc(ne['course'])} · {ne_d.strftime('%A, %b %d')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        heading("Study Progress", f"Spring 2026 — {len(data)} courses tracked")

        # ── Upcoming exams ────────────────────────────────────────────
        # ── Upcoming exams ────────────────────────────────────────────
        exam_events = upcoming_events(kind="Exam")
        
        if exam_events:
            st.markdown(f"""
            <div style="background:{WHITE};border:1.5px solid {BORDER};
                        border-radius:14px;padding:1.2rem 1.4rem;
                        margin-bottom:0.5rem;">
                <div style="font-family:'Playfair Display',serif;font-size:1.1rem;
                            font-weight:800;color:{TEXT};margin-bottom:1rem;">
                    📋 Upcoming Exams
                </div>
            </div>
            """, unsafe_allow_html=True)
        
            for e in exam_events:
                ex_date = parse_date(e["date"])
                diff = (ex_date - today).days
        
                if diff == 0:
                    bc, blb = "#e63946", "TODAY 🚨"
                elif diff <= 3:
                    bc, blb = "#e63946", f"{diff}d left 🔴"
                elif diff <= 7:
                    bc, blb = "#e76f51", f"{diff}d left 🟠"
                else:
                    bc, blb = "#2d6a4f", f"{diff}d left 🟢"
        
                bbg = tint(
                    bc,
                    {
                        "#e63946": "#fde8ea",
                        "#e76f51": "#fdeee9",
                        "#2d6a4f": "#d8f3dc"
                    }[bc]
                )
        
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;
                            align-items:center;padding:.6rem .8rem;
                            margin-bottom:.4rem;background:{SURF2};
                            border-radius:8px;border-left:3px solid {bc};">
        
                    <div>
                        <div style="font-weight:700;font-size:.9rem;color:{TEXT};">
                            {esc(e['title'])}
                        </div>
        
                        <div style="font-size:.75rem;color:{TEXTD};margin-top:2px;">
                            {esc(e['course'])} ·
                            {ex_date.strftime('%A, %b %d %Y')}
                        </div>
                    </div>
        
                    <div style="background:{bbg};color:{bc};
                                font-family:'DM Mono',monospace;
                                font-size:.75rem;font-weight:700;
                                padding:4px 10px;border-radius:6px;
                                white-space:nowrap;">
                        {blb}
                    </div>
        
                </div>
                """, unsafe_allow_html=True)


        # ── Achievements ──────────────────────────────────────────────
        pomo_log = meta["pomodoro_log"]
        pomo_days = len(pomo_log)
        total_mins = sum(sum(v.values()) for v in pomo_log.values())
        courses_done = sum(1 for c in data.values() if len(c) > 0 and all(c.values()))

        badges = []
        if streak >= 1:    badges.append(("🔥", f"{streak} Day Streak", "#e63946", "#fde8ea"))
        if streak >= 7:    badges.append(("🏆", "Week Warrior", "#e76f51", "#fdeee9"))
        if streak >= 30:   badges.append(("👑", "Month Master", "#7209b7", "#f0e6ff"))
        if done_all >= 10: badges.append(("✅", "10 Topics Done", "#2d6a4f", "#d8f3dc"))
        if done_all >= 25: badges.append(("🎯", "25 Topics Done", "#0077b6", "#e0f0ff"))
        if total_mins >= 60:  badges.append(("⏱️", "1hr Studied", "#4361ee", "#eef0ff"))
        if total_mins >= 300: badges.append(("💪", "5hrs Studied", "#7209b7", "#f0e6ff"))
        if courses_done >= 1: badges.append(("🎓", "Course Complete!", "#2d6a4f", "#d8f3dc"))
        if pomo_days >= 3:    badges.append(("📅", "3-Day Grind", "#e76f51", "#fdeee9"))

        if badges:
            badge_html = "".join(
                f'<div style="display:inline-flex;align-items:center;gap:6px;'
                f'background:{tint(clr, bg)};color:{clr};border-radius:20px;padding:5px 12px;'
                f'margin:3px;font-size:.78rem;font-weight:600;">{icon} {esc(lbl)}</div>'
                for icon, lbl, clr, bg in badges
            )
            st.markdown(f"""
            <div style="background:{WHITE};border:1.5px solid {BORDER};border-radius:14px;
                        padding:1rem 1.4rem;margin-bottom:1.5rem;">
                <div style="font-family:'Playfair Display',serif;font-size:1.1rem;
                            font-weight:800;color:{TEXT};margin-bottom:.8rem;">🏅 Achievements</div>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">{badge_html}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Daily study goal ──────────────────────────────────────────
        today_mins = sum(pomo_log.get(TODAY_STR, {}).values())
        goal_mins = read_goal(meta)
        goal_pct = min(100, int(today_mins / goal_mins * 100))
        goal_clr = "#e63946" if goal_pct < 33 else ("#e76f51" if goal_pct < 66 else "#2d6a4f")
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
                {"Goal reached! Great work today! 🎉" if goal_pct >= 100
                 else f"{max(0, goal_mins - today_mins)} min remaining to reach your daily goal"}</div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("⚙️ Set Daily Study Goal"):
            with st.form("goal_form"):
                new_goal = st.slider("Daily goal (minutes)", 30, 480,
                                     min(480, max(30, goal_mins)), 30)
                if st.form_submit_button("💾 Save Goal", disabled=not can_write):
                    if db_action("Saving your goal", set_kv, meta, GOAL_KEY, int(new_goal)):
                        refresh(meta=True)
                        st.rerun()

        # ── Stats row ─────────────────────────────────────────────────
        pct_all = int(done_all / total_all * 100) if total_all else 0
        s1, s2, s3, s4 = st.columns(4)
        for col, val, lbl in [(s1, f"{pct_all}%", "Overall"),
                              (s2, done_all, "Topics Done"),
                              (s3, total_all - done_all, "Remaining"),
                              (s4, streak, "Day Streak 🔥")]:
            with col:
                st.markdown(f"""
                <div style="background:{WHITE};border:1.5px solid {BORDER};border-radius:12px;
                            padding:1rem;text-align:center;margin-bottom:1rem;">
                    <div style="font-family:'Playfair Display',serif;font-size:2rem;
                                font-weight:800;color:{ACCENT};line-height:1;">{val}</div>
                    <div style="{label_style()}margin-top:4px;">{lbl}</div>
                </div>""", unsafe_allow_html=True)

        # ── Bar chart ─────────────────────────────────────────────────
        if course_list:
            names, pcts, clrs = [], [], []
            for c in course_list:
                t = len(data[c])
                d = sum(1 for s in data[c].values() if s)
                names.append(c)
                pcts.append(int(d / t * 100) if t else 0)
                clrs.append(color_map[c])
            fig = go.Figure(go.Bar(x=names, y=pcts, marker_color=clrs,
                                   text=[f"{p}%" for p in pcts], textposition="outside",
                                   textfont=dict(family="DM Mono", size=11, color=TEXTM)))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font=dict(family="DM Sans", color=TEXTM),
                              yaxis=dict(range=[0, 130], showgrid=False, zeroline=False, showticklabels=False),
                              xaxis=dict(showgrid=False, tickfont=dict(family="DM Mono", size=11, color=TEXTM)),
                              margin=dict(t=30, b=5, l=0, r=0), height=210, showlegend=False, bargap=0.4)
            st.plotly_chart(fig, use_container_width=True, key="bar")
        st.markdown("<hr>", unsafe_allow_html=True)

        # ── Course cards ──────────────────────────────────────────────
        PRIO_OPTIONS = ["", "high", "medium", "low"]
        course_items = list(data.items())
        for i in range(0, len(course_items), 2):
            col_a, col_b = st.columns(2, gap="medium")
            for col, idx in [(col_a, i), (col_b, i + 1)]:
                if idx >= len(course_items):
                    break
                course, lectures = course_items[idx]
                total = len(lectures)
                done = sum(1 for s in lectures.values() if s)
                pct = done / total if total else 0
                clr = color_map[course]

                pills = ""
                for ev in upcoming_events(course=course)[:2]:
                    diff = (parse_date(ev["date"]) - today).days
                    pc = "#e63946" if ev["type"] == "Exam" else "#e76f51"
                    pbg = tint(pc, "#fde8ea" if ev["type"] == "Exam" else "#fdeee9")
                    lbl = "TODAY" if diff == 0 else f"{diff}d"
                    pills += (f'<span style="background:{pbg};color:{pc};font-family:DM Mono,monospace;'
                              f'font-size:.61rem;font-weight:600;padding:2px 8px;border-radius:4px;">'
                              f'{esc(ev["type"])} · {lbl}</span> ')

                with col:
                    st.markdown(f"""
                    <div style="{card_style(clr)}">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1rem;">
                            <div>
                                <div style="{label_style()}margin-bottom:3px;">Course</div>
                                <div style="font-family:'Playfair Display',serif;font-size:1.4rem;
                                            font-weight:800;color:{TEXT};line-height:1.1;">{esc(course)}</div>
                            </div>
                            <div style="text-align:right;">
                                <div style="font-family:'Playfair Display',serif;font-size:1.7rem;
                                            font-weight:800;color:{clr};line-height:1;">{int(pct * 100)}%</div>
                                <div style="font-family:'DM Mono',monospace;font-size:.65rem;color:{TEXTD};">{done}/{total}</div>
                            </div>
                        </div>
                        <div style="background:{SURF2};border-radius:99px;height:5px;margin-bottom:.9rem;overflow:hidden;">
                            <div style="background:{clr};width:{int(pct * 100)}%;height:100%;border-radius:99px;"></div>
                        </div>
                        <div style="display:flex;gap:5px;flex-wrap:wrap;min-height:1.3rem;">
                            {pills if pills else f'<span style="font-size:.72rem;color:{TEXTD};font-family:DM Mono,monospace;">No upcoming events</span>'}
                        </div>
                    </div>""", unsafe_allow_html=True)

                    with st.expander(f"Topics — {course}"):
                        for lec, is_done in list(lectures.items()):
                            pkey = prio_key(course, lec)
                            prio = meta["priorities"].get(pkey, "")
                            if prio not in PRIO_OPTIONS:
                                prio = ""
                            base = wkey(course, lec)
                            tc, tb = st.columns([5, 1])
                            with tc:
                                # Stable key: after the first render Streamlit uses
                                # session_state, which always mirrors what the user
                                # last clicked, and `is_done` mirrors the database.
                                # Comparing the two is what detects a real change.
                                checked = st.checkbox(
                                    f"{prio_icon(prio)} {lec}" if prio else lec,
                                    value=is_done,
                                    key=f"chk_{base}",
                                    disabled=not can_write)
                                if checked != is_done:
                                    # One PATCH for the one topic that changed.
                                    if db_action("Saving this topic", set_topic_done,
                                                 course, lec, checked):
                                        db_action("Updating your streak", record_activity, meta)
                                        refresh(topics=True, meta=True)
                                        st.rerun()
                            with tb:
                                new_prio = st.selectbox(
                                    "Priority", PRIO_OPTIONS,
                                    index=PRIO_OPTIONS.index(prio),
                                    key=f"prio_{base}",
                                    label_visibility="collapsed",
                                    disabled=not can_write)
                                if new_prio != prio:
                                    # Clearing a priority now deletes the row instead
                                    # of being silently skipped.
                                    if db_action("Saving priority", set_kv, meta, pkey, new_prio):
                                        refresh(meta=True)
                                        st.rerun()
            st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)


    # ── TO-DO PANEL ───────────────────────────────────────────────────
    with todo_col:
        done_count = sum(1 for t in todos if t["done"])
        total_count = len(todos)
        pct_td = int(done_count / total_count * 100) if total_count else 0
        ring_clr = "#52b788" if pct_td == 100 else ACCENT
        track_clr = "#2a3248" if dark else "#f0ede8"
        bg_clr = "#161b27" if dark else "#ffffff"
        text_clr = "#e8eaf0" if dark else "#1a1814"
        sub_clr = "#5a6080" if dark else "#9a948c"
        CIRC = 2 * 3.14159 * 28
        offset = CIRC * (1 - pct_td / 100)

        components.html(f"""
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@800&family=DM+Mono:wght@400&family=DM+Sans:wght@500&display=swap');
          body{{margin:0;padding:1.2rem 1rem 1rem;background:{bg_clr};font-family:'DM Sans',sans-serif;}}
          .header{{display:flex;align-items:center;gap:14px;}}
          .title{{font-family:'Playfair Display',serif;font-size:1.3rem;font-weight:800;
                  color:{text_clr};line-height:1.15;}}
          .subtitle{{font-family:'DM Mono',monospace;font-size:.6rem;color:{sub_clr};
                     letter-spacing:.1em;text-transform:uppercase;margin-top:3px;}}
          .ring{{position:relative;width:70px;height:70px;flex-shrink:0;}}
          .ring svg{{transform:rotate(-90deg);}}
          .ring-center{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;}}
          .ring-pct{{font-family:'DM Mono',monospace;font-size:.8rem;font-weight:700;
                     color:{ring_clr};line-height:1;}}
          .ring-lbl{{font-family:'DM Mono',monospace;font-size:.42rem;color:{sub_clr};
                     letter-spacing:.06em;text-transform:uppercase;}}
        </style>
        <div class="header">
          <div class="ring">
            <svg width="70" height="70" viewBox="0 0 70 70">
              <circle cx="35" cy="35" r="28" fill="none" stroke="{track_clr}" stroke-width="7"/>
              <circle cx="35" cy="35" r="28" fill="none" stroke="{ring_clr}" stroke-width="7"
                      stroke-linecap="round"
                      stroke-dasharray="{CIRC:.2f}" stroke-dashoffset="{offset:.2f}"/>
            </svg>
            <div class="ring-center">
              <div class="ring-pct">{pct_td}%</div>
              <div class="ring-lbl">done</div>
            </div>
          </div>
          <div>
            <div class="title">To-Do</div>
            <div class="subtitle">{done_count} of {total_count} done</div>
          </div>
        </div>
        """, height=110)

        with st.form("todo_add_form", clear_on_submit=True):
            new_task = st.text_input("New task", placeholder="e.g. Review Ch7 notes…",
                                     label_visibility="collapsed")
            if st.form_submit_button("+  Add Task", use_container_width=True,
                                     disabled=not can_write):
                if new_task.strip():
                    updated = todos + [{"id": str(uuid.uuid4()),
                                        "text": new_task.strip(), "done": False}]
                    if db_action("Adding the task", save_todos, meta, updated):
                        refresh(meta=True)
                        st.rerun()

        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)

        def _write_todos(updated, label):
            if db_action(label, save_todos, meta, updated):
                refresh(meta=True)
                st.rerun()

        if not todos:
            st.markdown(
                f"<div style='font-size:.82rem;color:{TEXTD};text-align:center;"
                f"padding:1.5rem 0;'>No tasks yet.<br>Add one above! ✨</div>",
                unsafe_allow_html=True)
        else:
            open_tasks = [t for t in todos if not t["done"]]
            closed_tasks = [t for t in todos if t["done"]]

            for task in open_tasks:
                tc, dc = st.columns([5, 1])
                with tc:
                    # One stable key per task, used by both the open and completed
                    # branches. The old code hardcoded value=False here, which fought
                    # with the persisted widget state.
                    if st.checkbox(task["text"], value=False,
                                   key=f"todo_{task['id']}", disabled=not can_write):
                        _write_todos([dict(t, done=True) if t["id"] == task["id"] else t
                                      for t in todos], "Updating the task")
                with dc:
                    if st.button("×", key=f"todo_del_{task['id']}", help="Delete",
                                 disabled=not can_write):
                        _write_todos([t for t in todos if t["id"] != task["id"]],
                                     "Deleting the task")

            if closed_tasks:
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:.6rem;"
                    f"color:{TEXTD};letter-spacing:.1em;text-transform:uppercase;"
                    f"margin:.8rem 0 .4rem;'>Completed</div>",
                    unsafe_allow_html=True)
                for task in closed_tasks:
                    tc2, dc2 = st.columns([5, 1])
                    with tc2:
                        if not st.checkbox(task["text"], value=True,
                                           key=f"todo_{task['id']}",
                                           help="Uncheck to restore",
                                           disabled=not can_write):
                            _write_todos([dict(t, done=False) if t["id"] == task["id"] else t
                                          for t in todos], "Restoring the task")
                    with dc2:
                        if st.button("×", key=f"todo_del_{task['id']}", help="Delete",
                                     disabled=not can_write):
                            _write_todos([t for t in todos if t["id"] != task["id"]],
                                         "Deleting the task")

                if st.button("🗑️  Clear completed", use_container_width=True,
                             key="clear_done_todos", disabled=not can_write):
                    _write_todos([t for t in todos if not t["done"]],
                                 "Clearing completed tasks")


# ══════════════════════════════════════════════════════════════════════
#  PAGE 2 — POMODORO
# ══════════════════════════════════════════════════════════════════════
elif page == "Pomodoro":
    heading("Pomodoro Timer", "Focus sessions · 25 min work / 5 min break")

    ss = st.session_state
    now_wall = time.time()
    if ss.pomo_running and ss.pomo_wall_start is not None:
        elapsed_now = ss.pomo_elapsed + (now_wall - ss.pomo_wall_start)
    else:
        elapsed_now = ss.pomo_elapsed
    secs_left_now = max(0.0, ss.pomo_total - elapsed_now)

    # Auto-finish. `pomo_token` identifies this specific run; once its minutes
    # are logged the token is remembered, so a rerun (or a failed save that is
    # retried) can never log the same session twice.
    if ss.pomo_running and secs_left_now <= 0 and not ss.pomo_finished:
        ss.pomo_running = False
        ss.pomo_finished = True
        ss.pomo_elapsed = float(ss.pomo_total)
        token = ss.pomo_token
        should_log = (ss.pomo_is_work and ss.pomo_course
                      and token and token not in ss.pomo_logged)
        if should_log:
            mins_done = max(1, round(ss.pomo_total / 60))
            if db_action("Logging your session", add_minutes,
                         meta, TODAY_STR, ss.pomo_course, mins_done):
                ss.pomo_logged.add(token)
                refresh(meta=True)
        st.rerun()

    if not course_list:
        st.info("Add a course first — go to **Manage Courses**.")
    else:
        col_timer, col_log = st.columns([2, 3], gap="large")

        with col_timer:
            disabled = ss.pomo_running or ss.pomo_finished

            default_idx = course_list.index(ss.pomo_course) if ss.pomo_course in course_list else 0
            pomo_course_sel = st.selectbox("Studying for", course_list,
                                           index=default_idx, disabled=disabled,
                                           key="pomo_course_sel")

            pomo_type = st.radio("Session type", ["🍅 Work (25 min)", "☕ Break (5 min)"],
                                 horizontal=True, disabled=disabled, key="pomo_type")

            minutes = 25 if "Work" in pomo_type else 5
            seconds_total = minutes * 60

            if st.checkbox("Custom duration", disabled=disabled, key="pomo_custom"):
                minutes = st.number_input("Minutes", min_value=1, max_value=180,
                                          value=minutes, step=1, disabled=disabled,
                                          key="pomo_custom_mins")
                seconds_total = minutes * 60

            b1, b2 = st.columns(2)
            with b1:
                if not ss.pomo_running and not ss.pomo_finished:
                    if st.button("▶  Start", use_container_width=True, key="pomo_btn_start"):
                        ss.pomo_course = pomo_course_sel
                        ss.pomo_is_work = "Work" in pomo_type
                        ss.pomo_total = float(seconds_total)
                        ss.pomo_elapsed = 0.0
                        ss.pomo_wall_start = time.time()
                        ss.pomo_running = True
                        ss.pomo_finished = False
                        ss.pomo_token = uuid.uuid4().hex
                        st.rerun()
                elif ss.pomo_running:
                    if st.button("⏸  Pause", use_container_width=True, key="pomo_btn_pause"):
                        ss.pomo_elapsed = elapsed_now
                        ss.pomo_running = False
                        ss.pomo_wall_start = None
                        st.rerun()
                else:
                    st.button("▶  Start", use_container_width=True, disabled=True,
                              key="pomo_btn_done")
            with b2:
                if st.button("↺  Reset", use_container_width=True, key="pomo_btn_reset"):
                    ss.pomo_running = False
                    ss.pomo_finished = False
                    ss.pomo_elapsed = 0.0
                    ss.pomo_wall_start = None
                    ss.pomo_token = None
                    st.rerun()

            if not ss.pomo_running and not ss.pomo_finished and ss.pomo_elapsed > 0:
                if st.button("▶  Resume", use_container_width=True, key="pomo_btn_resume"):
                    ss.pomo_wall_start = time.time()
                    ss.pomo_running = True
                    st.rerun()

            total_f = float(ss.pomo_total) if ss.pomo_total else float(seconds_total)
            CIRC = 565.49
            ring_color = "#52b788" if ss.pomo_finished else ACCENT
            track_color = "#2a3248" if dark else "#f0ede8"
            bg_color = "#161b27" if dark else "#ffffff"
            lbl_color = "#5a6080" if dark else "#9a948c"
            status_text = ("Session complete! ✅ Logged automatically." if ss.pomo_finished
                           else ("⏸ Paused — press Resume to continue"
                                 if (not ss.pomo_running and ss.pomo_elapsed > 0)
                                 else ("🍅 Focus! Stay on task." if ss.pomo_running
                                       else "Ready — press Start")))
            status_clr = ("#52b788" if ss.pomo_finished
                          else (TEXTD if not ss.pomo_running else ACCENT))
            course_lbl = ss.pomo_course or pomo_course_sel
            lbl_txt = "FOCUS" if ss.pomo_is_work else "BREAK"

            # The countdown ticks in the browser, so the server no longer has to
            # rerun the whole script once per second just to redraw the clock.
            components.html(f"""<style>
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
  <circle id="prog" cx="100" cy="100" r="90" fill="none" stroke="{ring_color}" stroke-width="10"
          stroke-linecap="round" stroke-dasharray="{CIRC:.2f}" stroke-dashoffset="0"/>
</svg>
<div id="center"><div id="td">00:00</div><div id="lbl">{lbl_txt}</div></div>
</div>
<div id="status">{esc(status_text)}</div>
<div id="clbl">{esc(course_lbl)}</div>
<script>
(function(){{
  var left = {secs_left_now:.1f};
  var total = {total_f:.1f};
  var running = {str(bool(ss.pomo_running)).lower()};
  var CIRC = {CIRC:.2f};
  function fmt(s){{
    s = Math.max(0, Math.round(s));
    var m = Math.floor(s / 60), r = s % 60;
    return String(m).padStart(2, '0') + ':' + String(r).padStart(2, '0');
  }}
  function draw(){{
    document.getElementById('td').textContent = fmt(left);
    var pct = total > 0 ? (total - left) / total : 0;
    pct = Math.min(1, Math.max(0, pct));
    document.getElementById('prog').setAttribute('stroke-dashoffset', (CIRC * (1 - pct)).toFixed(2));
  }}
  draw();
  if (running) {{
    var iv = setInterval(function(){{
      left -= 1;
      if (left <= 0) {{ left = 0; draw(); clearInterval(iv); return; }}
      draw();
    }}, 1000);
  }}
}})();
</script>""", height=290)

            # Server tick: only needed to notice completion and log it. The
            # visible clock is driven by the script above, so this can be much
            # slower than the old once-per-second rerun.
            if ss.pomo_running:
                time.sleep(min(max(secs_left_now, 0.5), POMO_TICK))
                st.rerun()


            st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
            st.markdown(f'<div style="{label_style()}margin-bottom:.5rem;">Log Study Time Manually</div>',
                        unsafe_allow_html=True)
            log_course = st.selectbox("Course", course_list, key="log_course")
            log_min = st.number_input("Minutes studied (type any amount)", min_value=1,
                                      max_value=600, value=25, step=5, key="log_min")
            if st.button("✅  Add to Today's Log", use_container_width=True,
                         disabled=not can_write):
                if db_action("Logging your minutes", add_minutes,
                             meta, TODAY_STR, log_course, int(log_min)):
                    refresh(meta=True)
                    st.success(f"Logged {int(log_min)} min for {log_course}!")
                    st.rerun()

        with col_log:
            st.markdown(f'<div style="{label_style()}margin-bottom:.8rem;">Study Log — Last 7 Days</div>',
                        unsafe_allow_html=True)

            plog = meta["pomodoro_log"]
            last7 = [today - timedelta(days=i) for i in range(6, -1, -1)]
            last7_str = [str(d) for d in last7]

            chart_data = {c: [plog.get(ds, {}).get(c, 0) for ds in last7_str]
                          for c in course_list}
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
                           zeroline=False, tickfont=dict(family="DM Mono", size=10, color=TEXTD)),
                xaxis=dict(showgrid=False, tickfont=dict(family="DM Mono", size=10, color=TEXTD)),
                margin=dict(t=10, b=5, l=0, r=0), height=280,
                legend=dict(font=dict(family="DM Sans", size=11, color=TEXTM), bgcolor="rgba(0,0,0,0)")
            )
            st.plotly_chart(fig2, use_container_width=True, key="pomo_chart")

            st.markdown(f'<div style="{label_style()}margin-bottom:.6rem;margin-top:.4rem;">All-Time Totals</div>',
                        unsafe_allow_html=True)
            totals = {}
            for day_data in plog.values():
                for c, m in day_data.items():
                    totals[c] = totals.get(c, 0) + m
            if totals:
                peak = max(totals.values()) or 1
                for c, mins in sorted(totals.items(), key=lambda x: -x[1]):
                    hrs, rem = mins // 60, mins % 60
                    time_str = f"{hrs}h {rem}m" if hrs else f"{rem}m"
                    clr = color_map.get(c, "#888")
                    pct_bar = min(100, int(mins / peak * 100))
                    st.markdown(f"""
                    <div style="margin-bottom:.5rem;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                            <span style="font-size:.82rem;font-weight:600;color:{TEXT};">{esc(c)}</span>
                            <span style="font-family:'DM Mono',monospace;font-size:.76rem;color:{TEXTD};">{time_str}</span>
                        </div>
                        <div style="background:{SURF2};border-radius:99px;height:4px;overflow:hidden;">
                            <div style="background:{clr};width:{pct_bar}%;height:100%;border-radius:99px;"></div>
                        </div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='font-size:.84rem;color:{TEXTD};'>No sessions logged yet.</div>",
                            unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  PAGE 3 — CALENDAR
# ══════════════════════════════════════════════════════════════════════
elif page == "Calendar":
    heading("Calendar", "Exams · Due Dates · Reminders")
    col_cal, col_side = st.columns([3, 2], gap="large")

    with col_cal:
        n1, n2, n3 = st.columns([1, 5, 1])
        with n1:
            if st.button("←", key="prev_m"):
                if st.session_state.cal_month == 1:
                    st.session_state.cal_month = 12
                    st.session_state.cal_year -= 1
                else:
                    st.session_state.cal_month -= 1
                st.rerun()
        with n2:
            st.markdown(f"""<div style="text-align:center;font-family:'Playfair Display',serif;
                font-size:1.1rem;font-weight:700;color:{TEXT};padding-top:5px;">
                {calendar.month_name[st.session_state.cal_month]} {st.session_state.cal_year}
                </div>""", unsafe_allow_html=True)
        with n3:
            if st.button("→", key="next_m"):
                if st.session_state.cal_month == 12:
                    st.session_state.cal_month = 1
                    st.session_state.cal_year += 1
                else:
                    st.session_state.cal_month += 1
                st.rerun()

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        ev_map = {}
        for ev in events:
            day = parse_date(ev["date"])
            if day:
                ev_map.setdefault(str(day), []).append(ev)

        yr, mo = st.session_state.cal_year, st.session_state.cal_month
        hcols = st.columns(7)
        for i, h in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            with hcols[i]:
                st.markdown(f"""<div style="text-align:center;font-family:'DM Mono',monospace;
                    font-size:.63rem;color:{TEXTD};letter-spacing:.08em;text-transform:uppercase;
                    padding-bottom:6px;">{h}</div>""", unsafe_allow_html=True)

        for week in calendar.monthcalendar(yr, mo):
            wcols = st.columns(7)
            for i, day in enumerate(week):
                with wcols[i]:
                    if day == 0:
                        st.markdown("<div style='min-height:60px'></div>", unsafe_allow_html=True)
                        continue
                    cd = date(yr, mo, day)
                    isd = (cd == today)
                    cevs = ev_map.get(str(cd), [])
                    bg = ("#1a3a2a" if dark else "#edf6f0") if isd else WHITE
                    bdr = f"2px solid {ACCENT}" if isd else f"1.5px solid {BORDER}"
                    dnc = ACCENT if isd else TEXT
                    dots = ""
                    for ev in cevs[:3]:
                        dc = "#e63946" if ev["type"] == "Exam" else ("#e76f51" if ev["type"] == "Due Date" else "#4361ee")
                        sh = ev["title"][:9] + ("…" if len(ev["title"]) > 9 else "")
                        dots += (f'<div style="font-size:.57rem;color:{dc};font-family:DM Mono,monospace;'
                                 f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4;">'
                                 f'● {esc(sh)}</div>')
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
        ev_title = st.text_input("Title", placeholder="e.g. Midterm Exam", key="ev_t")
        ev_course = st.selectbox("Course", ["General"] + course_list, key="ev_c")
        ev_type = st.selectbox("Type", ["Exam", "Due Date", "Other"], key="ev_typ")
        ev_date_v = st.date_input("Date", value=today, key="ev_d")
        ev_notes = st.text_input("Notes (optional)", placeholder="Room, topics…", key="ev_n")
        if st.button("＋  Add Event", use_container_width=True, key="add_ev",
                     disabled=events_err is not None):
            if ev_title.strip():
                # A single INSERT. The old code rewrote the entire table.
                if db_action("Adding the event", db_insert, "events", {
                    "title": ev_title.strip(), "course": ev_course,
                    "type": ev_type, "date": str(ev_date_v),
                    "notes": ev_notes.strip(),
                }):
                    refresh(events=True)
                    st.success("Added!")
                    st.rerun()
            else:
                st.warning("Enter a title.")

        st.markdown(f'<div style="{label_style()}margin-top:1.3rem;margin-bottom:.7rem;">All Events</div>',
                    unsafe_allow_html=True)
        if not events:
            st.markdown(f"<div style='font-size:.84rem;color:{TEXTD};'>No events yet.</div>",
                        unsafe_allow_html=True)
        else:
            for ev in sorted(events, key=lambda x: sort_key_date(x["date"])):
                ev_d = parse_date(ev["date"])
                if ev_d is None:
                    lbl, lc, op = "Invalid date", TEXTD, "0.5"
                    date_txt = esc(ev["date"])
                else:
                    diff = (ev_d - today).days
                    past = ev_d < today
                    lbl = "Past" if past else ("TODAY" if diff == 0 else f"{diff}d left")
                    lc = TEXTD if past else ("#e63946" if diff <= 1 else ("#e76f51" if diff <= 4 else ACCENT))
                    op = "0.4" if past else "1"
                    date_txt = ev_d.strftime('%b %d')
                dc = "#e63946" if ev["type"] == "Exam" else ("#e76f51" if ev["type"] == "Due Date" else "#4361ee")

                c1, c2 = st.columns([6, 1])
                with c1:
                    notes_html = (f'<div style="font-size:.72rem;color:{TEXTD};margin-top:2px;">'
                                  f'{esc(ev["notes"])}</div>') if ev["notes"] else ""
                    st.markdown(f"""
                    <div style="opacity:{op};padding:8px 0;border-bottom:1px solid {HR_CLR};
                                display:flex;align-items:flex-start;gap:9px;">
                        <div style="width:9px;height:9px;border-radius:50%;background:{dc};
                                    margin-top:4px;flex-shrink:0;"></div>
                        <div>
                            <div style="font-size:.84rem;font-weight:600;color:{TEXT};">{esc(ev['title'])}</div>
                            <div style="font-size:.72rem;color:{TEXTD};margin-top:1px;">
                                {esc(ev['course'])} · {date_txt} ·
                                <span style="color:{lc};font-weight:600;">{lbl}</span></div>
                            {notes_html}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    # Delete by primary key, so the row removed is always the row
                    # clicked — the old code used a sorted-list index against the
                    # unsorted list and deleted the wrong event.
                    if ev["id"] is None:
                        st.button("✕", key=f"ev_del_missing_{wkey(ev['title'], ev['date'])}",
                                  disabled=True, help="This row has no id and cannot be deleted")
                    elif st.button("✕", key=f"ev_del_{ev['id']}",
                                   disabled=events_err is not None):
                        if db_action("Deleting the event", db_delete, "events",
                                     {"id": eq(ev["id"])}):
                            refresh(events=True)
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  PAGE 4 — WEEKLY PLAN
# ══════════════════════════════════════════════════════════════════════
elif page == "Weekly Plan":
    heading("Weekly Study Plan", "Assign courses to days — plan your week")

    plan = {d: [c for c in meta["weekly_plan"].get(d, []) if c in data] for d in DAYS}

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

    # The grid shows the CURRENT calendar week, Monday to Sunday. The old
    # modulo arithmetic made days earlier in the week show next week's date.
    week_start = today - timedelta(days=today.weekday())
    day_cols = st.columns(7, gap="small")

    for i, (day, col) in enumerate(zip(DAYS, day_cols)):
        day_date = week_start + timedelta(days=i)
        is_today = (day_date == today)
        with col:
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
                    {day_date.day}
                </div>
            </div>
            """, unsafe_allow_html=True)

            for c in plan.get(day, []):
                clr = color_map.get(c, "#888")
                t = len(data.get(c, {}))
                d2 = sum(1 for s in data.get(c, {}).values() if s)
                p = int(d2 / t * 100) if t else 0
                st.markdown(f"""
                <div style="background:{clr}18;border:1.5px solid {clr}55;
                            border-left:3px solid {clr};border-radius:6px;
                            padding:.4rem .5rem;margin-bottom:4px;">
                    <div style="font-size:.72rem;font-weight:700;color:{clr};
                                font-family:'DM Mono',monospace;">{esc(c)}</div>
                    <div style="font-size:.65rem;color:{TEXTD};">{p}% done</div>
                </div>""", unsafe_allow_html=True)

            for ev in [e for e in events if parse_date(e["date"]) == day_date]:
                ec = "#e63946" if ev["type"] == "Exam" else ("#e76f51" if ev["type"] == "Due Date" else "#4361ee")
                st.markdown(f"""
                <div style="background:{ec}15;border:1px solid {ec}44;border-radius:5px;
                            padding:3px 6px;margin-bottom:3px;">
                    <div style="font-size:.65rem;color:{ec};font-weight:600;
                                font-family:'DM Mono',monospace;white-space:nowrap;
                                overflow:hidden;text-overflow:ellipsis;">📌 {esc(ev['title'][:12])}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f'<div style="{label_style()}margin:1rem 0 .8rem;">Edit Weekly Plan</div>',
                unsafe_allow_html=True)

    edit_cols = st.columns(7, gap="small")
    for day, col in zip(DAYS, edit_cols):
        with col:
            assigned = plan.get(day, [])
            st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:.65rem;"
                        f"color:{TEXTD};margin-bottom:3px;'>{day[:3].upper()}</div>",
                        unsafe_allow_html=True)
            options = ["—"] + [c for c in course_list if c not in assigned]
            to_add = st.selectbox("Add", options, key=f"plan_add_{day}",
                                  label_visibility="collapsed", disabled=not can_write)
            if to_add != "—" and to_add not in assigned:
                # A single INSERT rather than wiping and rebuilding the table.
                if db_action("Adding to your plan", db_insert, "weekly_plan",
                             {"day": day, "course": to_add}):
                    refresh(meta=True)
                    st.rerun()
            for c in list(assigned):
                if st.button(f"✕ {c}", key=f"plan_del_{wkey(day, c)}", disabled=not can_write):
                    if db_action("Removing from your plan", db_delete, "weekly_plan",
                                 {"day": eq(day), "course": eq(c)}):
                        refresh(meta=True)
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  PAGE 5 — MANAGE COURSES
# ══════════════════════════════════════════════════════════════════════
elif page == "Manage Courses":
    heading("Manage Courses", "Add · Edit · Delete")
    tab1, tab2, tab3 = st.tabs(["➕  New Course", "✏️  Edit Course", "🗑️  Delete"])

    with tab1:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        new_name = st.text_input("Course code / name", placeholder="e.g. CHE 410")
        topics_raw = st.text_area("Topics — one per line",
                                  placeholder="Ch1 L1\nCh1 L2\nMidterm Prep", height=180)
        if st.button("Create Course", use_container_width=True, disabled=not can_write):
            name = new_name.strip()
            if not name:
                st.warning("Enter a course name.")
            elif name in data:
                st.warning("Already exists.")
            else:
                seen, topics = set(), []
                for line in topics_raw.splitlines():
                    line = line.strip()
                    if line and line not in seen:
                        seen.add(line)
                        topics.append(line)
                if not topics:
                    st.warning("Add at least one topic.")
                elif db_action("Creating the course", db_insert, "topics",
                               [{"course": name, "topic": t, "done": False} for t in topics]):
                    refresh(topics=True)
                    st.success(f"✅ {name} created with {len(topics)} topics!")
                    st.rerun()

    with tab2:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        if not data:
            st.info("No courses yet.")
        else:
            sel = st.selectbox("Select course", course_list, key="edit_sel")
            if sel:
                c1e, c2e = st.columns(2)
                with c1e:
                    nt = st.text_input("Add new topic", key="new_t_inp")
                    if st.button("Add Topic", disabled=not can_write):
                        nt = nt.strip()
                        if not nt:
                            st.warning("Enter a name.")
                        elif nt in data[sel]:
                            st.warning("Already exists.")
                        elif db_action("Adding the topic", db_insert, "topics",
                                       {"course": sel, "topic": nt, "done": False}):
                            refresh(topics=True)
                            st.success(f"Added '{nt}'")
                            st.rerun()
                with c2e:
                    new_nm = st.text_input("Rename course to", value=sel, key="ren_c")
                    if st.button("Rename", disabled=not can_write):
                        nn = new_nm.strip()
                        if not nn or nn == sel:
                            st.warning("Enter a different name.")
                        elif nn in data:
                            st.warning("Name taken.")
                        # Renames the rows in place across every table instead of
                        # inserting a copy and orphaning the original.
                        elif db_action("Renaming the course", rename_course, meta, sel, nn):
                            refresh(topics=True, events=True, meta=True)
                            st.success(f"Renamed to {nn}")
                            st.rerun()

                st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
                st.markdown(f'<div style="{label_style()}margin-bottom:.5rem;">Topics</div>',
                            unsafe_allow_html=True)
                for topic in list(data[sel].keys()):
                    tc2, dc2 = st.columns([7, 1])
                    with tc2:
                        done_t = data[sel][topic]
                        prio = meta["priorities"].get(prio_key(sel, topic), "")
                        st.markdown(
                            f"<div style='padding:5px 0;font-size:.84rem;"
                            f"color:{ACCENT if done_t else TEXTM};"
                            f"border-bottom:1px solid {HR_CLR};'>"
                            f"{'✓' if done_t else '○'} {prio_icon(prio)} {esc(topic)}</div>",
                            unsafe_allow_html=True)
                    with dc2:
                        if st.button("✕", key=f"del_t_{wkey(sel, topic)}", disabled=not can_write):
                            # Actually issues a DELETE now, so the topic stays gone.
                            if db_action("Deleting the topic", delete_topic, meta, sel, topic):
                                refresh(topics=True, meta=True)
                                st.rerun()

    with tab3:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        if not data:
            st.info("No courses to delete.")
        else:
            dc_sel = st.selectbox("Course to delete", course_list, key="del_c_sel")
            st.warning(f"⚠️ This permanently removes **{dc_sel}** and all its topics. "
                       "Your logged study time and calendar events are kept.")
            confirm = st.checkbox("I understand, delete this course")
            if st.button("Delete Course", disabled=not confirm or not can_write):
                if db_action("Deleting the course", delete_course, meta, dc_sel):
                    refresh(topics=True, meta=True)
                    st.success(f"Deleted {dc_sel}")
                    st.rerun()
