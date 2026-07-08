import time
import datetime
import hashlib
import json
from pathlib import Path
import streamlit as st
from groq import Groq

# ─────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="PLM GPT",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Viewport meta for mobile
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<style>
  * { box-sizing: border-box; }
  img, canvas { max-width: 100%; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
#  HIDE STREAMLIT BRANDING
# ─────────────────────────────────────────
st.markdown("""
<style>
  #MainMenu, header, footer,
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  [data-testid="stSidebarNav"],
  [data-testid="collapsedControl"],
  .stDeployButton { display:none !important; visibility:hidden !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────
MAX_REQUESTS    = 10
WINDOW_SECONDS  = 60
SESSION_TIMEOUT = 30 * 60

MODELS = {
    "⚡ Fast  — Llama 3.1 8B":  "llama-3.1-8b-instant",
    "🧠 Smart — Llama 3.3 70B": "llama-3.3-70b-versatile",
}

CONVERSATION_MODES = {
    "💼 Professional": (
        "You are PLM GPT, a highly professional AI assistant created by Pranav Chakravorty. "
        "Respond formally, precisely, and concisely. Use structured markdown formatting."
    ),
    "👨‍💻 Code Helper": (
        "You are PLM GPT, an expert programming assistant created by Pranav Chakravorty. "
        "Focus on clean, efficient code in proper markdown code blocks with language specified."
    ),
    "✍️ Creative Writer": (
        "You are PLM GPT, a creative writing assistant created by Pranav Chakravorty. "
        "Be imaginative, expressive, and engaging. Use vivid language and creative structure."
    ),
    "📚 Study Buddy": (
        "You are PLM GPT, a friendly study assistant created by Pranav Chakravorty. "
        "Explain concepts simply with examples and analogies. Break down complex topics step by step."
    ),
}

PROMPT_SUGGESTIONS = [
    "✍️ Write a professional introduction email",
    "🧠 Explain machine learning in simple terms",
    "💡 Give me 5 unique startup ideas for 2025",
    "📝 Summarize the key principles of clean code",
    "🌍 What are the biggest trends in AI right now?",
    "🔥 Help me prepare for a technical interview",
]

# ─────────────────────────────────────────
#  PERSISTENT DATABASE  (JSON file)
# ─────────────────────────────────────────
# Streamlit Cloud pe /tmp writable hai (restart tak persist karta hai)
# Local machine pe same directory mein save hoga
DB_PATH = Path("/tmp/plmgpt_db.json")
if not DB_PATH.exists():
    try:
        _local = Path(__file__).parent / "plmgpt_db.json"
        DB_PATH = _local
    except NameError:
        # __file__ not defined (e.g. exec() context) — keep /tmp
        pass

def _load_db() -> dict:
    """Read the full database from disk. Returns empty structure if missing."""
    if DB_PATH.exists():
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}, "chats": {}}

def _save_db(db: dict):
    """Write the full database to disk atomically."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = DB_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        tmp.replace(DB_PATH)
    except Exception as e:
        st.toast(f"⚠️ Could not save data: {e}", icon="⚠️")

# ── helpers ──────────────────────────────
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _seed_admin(db: dict):
    """Ensure the default admin account always exists."""
    admin = st.secrets.get("ADMIN_USER", "admin")
    if admin not in db["users"]:
        db["users"][admin] = {
            "password_hash": _hash(st.secrets.get("APP_PASSWORD", "plmgpt2024")),
            "display_name":  "Admin",
            "created_at":    datetime.datetime.now().strftime("%d %b %Y"),
        }
        _save_db(db)

# ── load once per interpreter boot ───────
if "db" not in st.session_state:
    st.session_state.db = _load_db()
    _seed_admin(st.session_state.db)

# ── public API ───────────────────────────
def register_user(username: str, display_name: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    db = st.session_state.db
    if username in db["users"]:
        return False, "Username already taken. Choose another."
    db["users"][username] = {
        "password_hash": _hash(password),
        "display_name":  display_name.strip() or username,
        "created_at":    datetime.datetime.now().strftime("%d %b %Y"),
    }
    # init empty chat store for new user
    if username not in db["chats"]:
        db["chats"][username] = {}
    _save_db(db)
    return True, "Account created!"

def verify_login(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    db = st.session_state.db
    if username not in db["users"]:
        return False, "No account found with that username."
    user = db["users"][username]
    if user["password_hash"] != _hash(password):
        return False, "Incorrect password."
    return True, user["display_name"]

def save_user_chats(username: str, sessions_data: dict):
    """Persist all chat sessions for a user to disk."""
    if not username:
        return
    db = st.session_state.db
    if "chats" not in db:
        db["chats"] = {}
    db["chats"][username] = sessions_data
    _save_db(db)

def load_user_chats(username: str) -> dict:
    """Load saved chat sessions for a user from disk."""
    if not username:
        return {}
    db = st.session_state.db
    return db.get("chats", {}).get(username, {})

# ─────────────────────────────────────────
#  SESSION STATE DEFAULTS
# ─────────────────────────────────────────
defaults = {
    "authenticated":   False,
    "current_user":    None,       # username (key into user_db)
    "display_name":    "",         # shown in UI
    "auth_tab":        "login",    # "login" | "signup"
    "splash_done":     False,      # startup animation shown?
    "messages":        [],
    "req_timestamps":  [],
    "last_activity":   time.time(),
    "theme":           "dark",
    "model":           "llama-3.3-70b-versatile",
    "temperature":     0.7,
    "conv_mode":       "💼 Professional",
    "welcome_shown":   False,
    "starred":         [],
    "show_starred":    False,
    "sessions":        {},
    "active_session":  "default",
    "show_sessions":   False,
    "show_profile":    False,   # profile page toggle
    "confetti_shown":  False,  # confetti shown once
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────
#  THEMES
# ─────────────────────────────────────────
THEMES = {
    "dark": {
        # ── Carbon Red — Bold & Powerful ──────────
        "bg":          "#0a0000",
        "card":        "#1a0505",
        "input_bg":    "#200808",
        "text":        "#fef2f2",
        "sub":         "#7a3333",
        "accent":      "#ef4444",
        "border":      "#2a0808",
        "user_bg":     "#150505",
        "user_border": "#f87171",
        "btn_bg":      "#200808",
        "btn_text":    "#fef2f2",
        "toolbar_bg":  "#070000",
        "welcome_bg":  "#0a0000",
        "grad1":       "#0a0000",
        "grad2":       "#1a0505",
        "grad3":       "#070000",
        "aurora1":     "#ef4444",
        "aurora2":     "#f87171",
        "aurora3":     "#fca5a5",
        "aurora4":     "#dc2626",
    },
    "light": {
        # ── Carbon Red Light ──────────────────────
        "bg":          "#fff5f5",
        "card":        "#ffffff",
        "input_bg":    "#fee2e2",
        "text":        "#1a0000",
        "sub":         "#7a3333",
        "accent":      "#dc2626",
        "border":      "#fecaca",
        "user_bg":     "#fee2e2",
        "user_border": "#ef4444",
        "btn_bg":      "#fee2e2",
        "btn_text":    "#1a0000",
        "toolbar_bg":  "#fde8e8",
        "welcome_bg":  "#fee2e2",
        "grad1":       "#fff5f5",
        "grad2":       "#fee2e2",
        "grad3":       "#fde8e8",
        "aurora1":     "#ef4444",
        "aurora2":     "#f87171",
        "aurora3":     "#fca5a5",
        "aurora4":     "#dc2626",
    },
}

# ─────────────────────────────────────────
#  BACKGROUND ANIMATIONS (particles + orbs)
# ─────────────────────────────────────────
BG_ANIMATION = """
<style>
/* ── Cinematic Aurora Stripes ── */
@keyframes auroraShift {
  0%   { transform: translateX(-100%) skewX(-15deg); opacity: 0; }
  20%  { opacity: 0.06; }
  80%  { opacity: 0.04; }
  100% { transform: translateX(200%) skewX(-15deg); opacity: 0; }
}
@keyframes auroraPulse {
  0%, 100% { opacity: 0.03; transform: scaleY(1); }
  50%       { opacity: 0.07; transform: scaleY(1.1); }
}
@keyframes noiseMove {
  0%   { background-position: 0 0; }
  100% { background-position: 200px 200px; }
}

.aurora-wrap {
  position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden;
}
.aurora-stripe {
  position: absolute; left: -100%; width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, var(--clr) 40%, transparent);
  animation: auroraShift linear infinite;
  filter: blur(60px);
}
.aurora-stripe-1 { --clr: #dc262655; animation-duration: 14s; animation-delay: 0s;   top: 10%; }
.aurora-stripe-2 { --clr: #ef444444; animation-duration: 18s; animation-delay: -5s;  top: 40%; }
.aurora-stripe-3 { --clr: #f8717133; animation-duration: 22s; animation-delay: -10s; top: 70%; }
.aurora-stripe-4 { --clr: #b91c1c44; animation-duration: 16s; animation-delay: -7s;  top: 25%; }

.aurora-glow-1 {
  position: fixed; width: 70vw; height: 40vh; left: -20vw; top: -10vh;
  background: radial-gradient(ellipse, #dc262622 0%, transparent 70%);
  animation: auroraPulse 8s ease-in-out infinite; filter: blur(80px);
  pointer-events: none; z-index: 0;
}
.aurora-glow-2 {
  position: fixed; width: 60vw; height: 50vh; right: -15vw; bottom: -10vh;
  background: radial-gradient(ellipse, #ef44441a 0%, transparent 70%);
  animation: auroraPulse 11s ease-in-out infinite reverse; filter: blur(100px);
  pointer-events: none; z-index: 0;
}
.aurora-glow-3 {
  position: fixed; width: 40vw; height: 30vh; left: 30vw; top: 30vh;
  background: radial-gradient(ellipse, #f8717111 0%, transparent 70%);
  animation: auroraPulse 14s ease-in-out infinite 3s; filter: blur(90px);
  pointer-events: none; z-index: 0;
}
.noise-overlay {
  position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: 0.025;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 200px 200px;
}
[data-testid="stAppViewContainer"] > section,
[data-testid="stAppViewBlockContainer"],
.block-container {
  position: relative; z-index: 1;
  max-width: 900px !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
  margin: 0 auto !important;
}
</style>
<div class="aurora-wrap">
  <div class="aurora-stripe aurora-stripe-1"></div>
  <div class="aurora-stripe aurora-stripe-2"></div>
  <div class="aurora-stripe aurora-stripe-3"></div>
  <div class="aurora-stripe aurora-stripe-4"></div>
</div>
<div class="aurora-glow-1"></div>
<div class="aurora-glow-2"></div>
<div class="aurora-glow-3"></div>
<div class="noise-overlay"></div>
"""

def apply_theme():
    t = THEMES[st.session_state.theme]
    st.markdown(BG_ANIMATION, unsafe_allow_html=True)
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Playfair+Display:ital,wght@0,600;1,500&family=Inter:wght@400;500;600;700;800&display=swap');

      @keyframes gradientShift {{
        0%   {{ background-position: 0% 50%; }}
        50%  {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
      }}
      .stApp {{
        background: {t['bg']};
        font-family: 'Space Grotesk', 'Inter', sans-serif;
      }}

      .plm-toolbar {{
        display:flex; align-items:center; justify-content:space-between;
        background:{t['toolbar_bg']}cc; border-radius:12px;
        padding:0.6rem 1rem; margin-bottom:0.8rem;
        border:1px solid {t['border']}; flex-wrap:wrap; gap:0.4rem;
        backdrop-filter: blur(8px);
      }}
      .plm-toolbar-label {{
        color:{t['sub']}; font-size:0.75rem; font-weight:600;
        text-transform:uppercase; letter-spacing:0.06em; margin-bottom:3px;
      }}
      .plm-title {{ text-align:center; padding:1.2rem 0 0.4rem; }}
      .plm-title h1 {{
        font-size:2.6rem; font-weight:800; color:{t['text']};
        font-family:'Space Grotesk', 'Inter', sans-serif; margin-bottom:0.1rem;
      }}
      .plm-title .byline {{ color:{t['sub']}; font-size:0.88rem; font-weight:500; }}
      .plm-title .caption {{ color:{t['sub']}; font-size:0.76rem; font-style:italic; opacity:0.6; }}

      .welcome-card {{
        background: linear-gradient(135deg, {t['welcome_bg']} 0%, {t['card']} 100%);
        border: 1px solid {t['accent']}55; border-radius: 16px;
        padding: 2rem 2.2rem; margin: 1rem 0 1rem 0;
        text-align: center; box-shadow: 0 4px 24px {t['accent']}18;
      }}
      .welcome-greeting {{
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.9rem; font-weight: 600; color: {t['accent']};
        letter-spacing: 0.01em; margin-bottom: 0.6rem; line-height: 1.3;
      }}
      .welcome-sub {{
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1rem; font-style: italic; color: {t['text']};
        opacity: 0.85; line-height: 1.7; margin-bottom: 0.5rem;
      }}
      .welcome-dev {{
        font-family: 'Inter', sans-serif; font-size: 0.72rem; font-weight: 600;
        letter-spacing: 0.12em; text-transform: uppercase;
        color: {t['sub']}; opacity: 0.7; margin-top: 0.8rem;
      }}
      .welcome-dot {{
        display: inline-block; width: 6px; height: 6px;
        background: {t['accent']}; border-radius: 50%;
        margin: 0 6px; vertical-align: middle;
      }}
      .prompt-grid {{
        display: grid; grid-template-columns: 1fr 1fr;
        gap: 0.5rem; margin: 0.8rem 0 1rem 0;
      }}

      /* ── WhatsApp-style chat layout ── */
      .msg-row-user {{
        display: flex; justify-content: flex-end;
        margin: 0.5rem 0; animation: msgSlideInRight 0.35s cubic-bezier(0.16,1,0.3,1) forwards;
      }}
      .msg-row-bot {{
        display: flex; justify-content: flex-start;
        margin: 0.5rem 0; animation: msgSlideInLeft 0.35s cubic-bezier(0.16,1,0.3,1) forwards;
      }}
      @keyframes msgSlideInRight {{
        from {{ opacity:0; transform: translateX(20px) scale(0.97); }}
        to   {{ opacity:1; transform: translateX(0)    scale(1); }}
      }}
      @keyframes msgSlideInLeft {{
        from {{ opacity:0; transform: translateX(-20px) scale(0.97); }}
        to   {{ opacity:1; transform: translateX(0)     scale(1); }}
      }}
      .msg-user {{
        background: linear-gradient(135deg, {t['accent']}dd 0%, {t['accent']}99 100%);
        border: none;
        border-radius: 18px 4px 18px 18px;
        padding: 0.75rem 1.1rem;
        color: #ffffff;
        font-size: 0.93rem; line-height: 1.6;
        max-width: 75%;
        backdrop-filter: blur(20px);
        box-shadow: 0 2px 16px {t['accent']}44;
        position: relative;
      }}
      .msg-bot {{
        background: linear-gradient(135deg, {t['card']}f5 0%, {t['input_bg']}ee 100%);
        border: 1px solid {t['border']};
        border-radius: 4px 18px 18px 18px;
        padding: 0.75rem 1.1rem;
        color: {t['text']}; font-size: 0.93rem; line-height: 1.75;
        max-width: 80%;
        backdrop-filter: blur(20px);
        box-shadow: 0 2px 20px rgba(0,0,0,0.3);
        position: relative;
      }}        position: relative; overflow: hidden;
      }}
      .msg-bot::before {{
        content: '';
        position: absolute; top: 0; left: 0; right: 0; height: 1px;
        background: linear-gradient(90deg, transparent, {t['accent']}44, transparent);
      }}
      @keyframes msgSlideIn {{
        from {{ opacity: 0; transform: translateY(18px) scale(0.98); }}
        to   {{ opacity: 1; transform: translateY(0)    scale(1); }}
      }}
      .msg-header {{
        display:flex; justify-content:space-between; align-items:center;
        margin-bottom:0.3rem;
      }}
      .msg-label {{ font-size:0.72rem; font-weight:700; opacity:0.55; text-transform:uppercase; letter-spacing:0.07em; }}
      .msg-time {{ font-size:0.68rem; color:{t['sub']}; opacity:0.6; }}
      .starred-card {{
        background:{t['card']}; border:1px solid {t['accent']}66;
        border-radius:10px; padding:0.8rem 1rem; margin:0.4rem 0;
        color:{t['text']}; font-size:0.88rem; line-height:1.6;
        border-left:3px solid {t['accent']};
      }}
      .typing-indicator {{
        display:flex; align-items:center; gap:5px; padding:0.8rem 1.1rem;
        background:{t['card']}; border-left:4px solid {t['accent']};
        border-radius:10px; margin:0.5rem 0;
      }}
      .typing-dot {{
        width:8px; height:8px; border-radius:50%; background:{t['accent']};
        animation: typingBounce 1.2s infinite ease-in-out;
      }}
      .typing-dot:nth-child(2) {{ animation-delay:0.2s; }}
      .typing-dot:nth-child(3) {{ animation-delay:0.4s; }}
      @keyframes typingBounce {{
        0%,60%,100% {{ transform:translateY(0); opacity:0.4; }}
        30% {{ transform:translateY(-6px); opacity:1; }}
      }}
      .typing-text {{ font-size:0.8rem; color:{t['sub']}; margin-left:4px; font-style:italic; }}
      .stream-box {{
        background:{t['card']}; border-left:4px solid {t['accent']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.7; min-height:2rem;
        white-space: pre-wrap;
      }}
      .char-counter {{
        text-align:right; font-size:0.72rem; color:{t['sub']};
        margin-top:-0.5rem; margin-bottom:0.4rem; opacity:0.7;
      }}
      .char-warn  {{ color:#f0a500 !important; opacity:1 !important; }}
      .char-danger {{ color:#b91c1c !important; opacity:1 !important; }}
      .stTextInput > div > div > input {{
        background-color:{t['input_bg']} !important; color:{t['text']} !important;
        border:1px solid {t['border']} !important; border-radius:10px !important;
        font-size:1rem !important; box-shadow:none !important;
      }}
      .stTextInput > div > div > input:focus {{
        border:1px solid {t['accent']} !important;
        box-shadow:0 0 0 2px {t['accent']}33 !important;
      }}
      .stFormSubmitButton > button, .stButton > button {{
        background-color:{t['btn_bg']}; color:{t['btn_text']};
        border:1px solid {t['border']}; border-radius:10px;
        padding:0.5rem 1.2rem; font-size:0.9rem; font-weight:600; transition:all 0.2s;
      }}
      .stFormSubmitButton > button:hover, .stButton > button:hover {{
        background-color:{t['accent']}; color:{t['bg']}; border-color:{t['accent']};
      }}
      .stSelectbox > div > div {{
        background-color:{t['input_bg']} !important; color:{t['text']} !important;
        border:1px solid {t['border']} !important; border-radius:10px !important;
      }}
      .summary-box {{
        background: linear-gradient(135deg, {t['welcome_bg']}, {t['card']});
        border: 1px solid {t['accent']}44; border-radius:12px;
        padding:1.2rem 1.4rem; margin:0.8rem 0;
        color:{t['text']}; font-size:0.92rem; line-height:1.7;
      }}
      .summary-title {{
        font-family:'Playfair Display',serif; color:{t['accent']};
        font-size:1rem; font-weight:600; margin-bottom:0.5rem;
      }}
      .session-card {{
        background:{t['card']}; border:1px solid {t['border']};
        border-radius:10px; padding:0.6rem 1rem; margin:0.3rem 0;
        color:{t['text']}; font-size:0.88rem; cursor:pointer;
        transition:all 0.15s; display:flex; justify-content:space-between; align-items:center;
      }}
      .session-card:hover {{ border-color:{t['accent']}; background:{t['user_bg']}; }}
      .session-active {{ border-color:{t['accent']} !important; background:{t['user_bg']} !important; }}
      .session-name {{ font-weight:600; }}
      .session-meta {{ font-size:0.72rem; color:{t['sub']}; }}
      hr {{ border-color:{t['border']}; margin:0.7rem 0; }}

      /* ── Custom Scrollbar (Discord style) ── */
      ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
      ::-webkit-scrollbar-track {{ background: transparent; }}
      ::-webkit-scrollbar-thumb {{
        background: {t['border']}; border-radius: 100px;
        transition: background 0.2s;
      }}
      ::-webkit-scrollbar-thumb:hover {{ background: {t['accent']}88; }}
      * {{ scrollbar-width: thin; scrollbar-color: {t['border']} transparent; }}

      /* ── Page transition ── */
      @keyframes pageSlideIn {{
        from {{ opacity: 0; transform: translateY(12px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
      }}
      .block-container {{
        animation: pageSlideIn 0.5s cubic-bezier(0.16,1,0.3,1) forwards;
      }}

      /* ── Skeleton shimmer ── */
      @keyframes shimmer {{
        0%   {{ background-position: -600px 0; }}
        100% {{ background-position:  600px 0; }}
      }}
      .skeleton {{
        background: linear-gradient(90deg,
          {t['card']} 25%,
          {t['border']} 50%,
          {t['card']} 75%);
        background-size: 600px 100%;
        animation: shimmer 1.4s ease-in-out infinite;
        border-radius: 8px; height: 14px; margin: 6px 0;
      }}
      .skeleton-wide  {{ width: 85%; }}
      .skeleton-med   {{ width: 60%; }}
      .skeleton-short {{ width: 35%; }}
      .skeleton-wrap {{
        background: {t['card']}99;
        border-left: 4px solid {t['border']};
        border-radius: 12px; padding: 0.9rem 1.1rem;
        margin: 0.5rem 0;
        backdrop-filter: blur(12px);
      }}

      /* ── Avatar in messages ── */
      .msg-with-avatar {{
        display: flex; gap: 0.65rem; align-items: flex-start; margin: 0.5rem 0;
      }}
      .msg-avatar {{
        width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.78rem; font-weight: 800; margin-top: 2px;
      }}
      .msg-avatar-user {{
        background: linear-gradient(135deg, {t['user_border']}, {t['accent']});
        color: {t['bg']};
      }}
      .msg-avatar-bot {{
        background: linear-gradient(135deg, {t['accent']}, {t['user_border']});
        color: {t['bg']}; font-size: 0.65rem; letter-spacing: -0.5px;
      }}
      .msg-bubble {{ flex: 1; min-width: 0; }}
      .msg-user {{ border-radius: 4px 12px 12px 12px !important; }}
      .msg-bot  {{ border-radius: 12px 4px 12px 12px !important; border-left: none !important;
                   border-top: none !important;
                   border: 1px solid {t['accent']}44 !important; }}

      @media (max-width: 640px) {{
        .block-container {{ padding: 0.5rem 0.6rem 2rem 0.6rem !important; max-width: 100% !important; }}
        .plm-toolbar {{ flex-direction: column; align-items: stretch; gap: 0.5rem; padding: 0.6rem 0.7rem; border-radius: 10px; }}
        .plm-title h1 {{ font-size: 1.8rem !important; }}
        .msg-user, .msg-bot {{ padding: 0.65rem 0.8rem; font-size: 0.88rem; border-radius: 8px; }}
        .prompt-grid {{ grid-template-columns: 1fr !important; }}
        .plm-orb-1 {{ width:220px; height:220px; }}
        .plm-orb-2 {{ width:180px; height:180px; }}
        .plm-orb-3 {{ width:140px; height:140px; }}
        .plm-orb-4 {{ width:120px; height:120px; }}
        .msg-avatar {{ width:26px; height:26px; font-size:0.65rem; }}
      }}
      @media (min-width: 641px) and (max-width: 900px) {{
        .block-container {{ padding: 0.8rem 1rem 2rem 1rem !important; max-width: 100% !important; }}
        .plm-title h1 {{ font-size: 2.1rem !important; }}
        .msg-user, .msg-bot {{ font-size: 0.92rem; }}
      }}

      /* ── Floating sticky input ── */
      div[data-testid="stForm"] {{
        position: sticky !important;
        bottom: 0 !important;
        z-index: 100 !important;
        background: transparent !important;
        padding-bottom: 0.5rem;
      }}
      div[data-testid="stForm"]::before {{
        content: '';
        position: absolute;
        inset: -10px -20px 0;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        z-index: -1;
      }}
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def is_rate_limited() -> bool:
    now = time.time()
    ts = [x for x in st.session_state.req_timestamps if now - x < WINDOW_SECONDS]
    if len(ts) >= MAX_REQUESTS:
        return True
    ts.append(now)
    st.session_state.req_timestamps = ts
    return False

def is_session_expired() -> bool:
    return time.time() - st.session_state.last_activity > SESSION_TIMEOUT

def refresh_activity():
    st.session_state.last_activity = time.time()

def sanitize(text: str) -> str:
    import re as _re
    # Strip potential HTML/script tags from user input
    text = _re.sub(r'<[^>]+>', '', text)
    return text.strip()[:3000]

def now_str() -> str:
    return datetime.datetime.now().strftime("%I:%M %p")

def get_system_prompt() -> str:
    return CONVERSATION_MODES[st.session_state.conv_mode]

def stream_response(query: str):
    """Generator: yields text chunks from Groq streaming API."""
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        history = [{"role": "system", "content": get_system_prompt()}]
        for m in st.session_state.messages[-10:]:
            history.append({"role": m["role"], "content": m["content"]})
        history.append({"role": "user", "content": query})

        response = client.chat.completions.create(
            model=st.session_state.model,
            messages=history,
            max_tokens=1024,
            temperature=st.session_state.temperature,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:
        yield f"⚠️ Error: {type(e).__name__}. Please try again."

def get_summary() -> str:
    """Summarize the full conversation using Groq."""
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        convo = "\n".join(
            f"{'User' if m['role']=='user' else 'PLM GPT'}: {m['content']}"
            for m in st.session_state.messages
        )
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Summarize the following conversation in 5-7 concise bullet points. Be precise and professional."},
                {"role": "user", "content": convo},
            ],
            max_tokens=512,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception:
        return "⚠️ Could not generate summary."



# ─────────────────────────────────────────
#  MARKDOWN RENDERER
# ─────────────────────────────────────────
def render_markdown(text: str, t: dict) -> str:
    """Convert markdown text to styled HTML for chat bubbles."""
    import re as _re
    # Code blocks
    def replace_codeblock(m):
        lang = m.group(1).strip() if m.group(1) else ""
        code = m.group(2).replace('<','&lt;').replace('>','&gt;')
        return (
            f'<div style="background:#070710;border:1px solid {t["border"]};border-radius:8px;margin:0.6rem 0;overflow:hidden;">' +
            f'<div style="background:#0a0a0f;padding:0.3rem 0.8rem;font-size:0.72rem;color:{t["sub"]};">{lang if lang else "code"}</div>' +
            f'<pre style="margin:0;padding:0.8rem;overflow-x:auto;font-size:0.88rem;line-height:1.6;color:#e8eaed;font-family:monospace;"><code>' +
            code + '</code></pre></div>'
        )
    text = _re.sub(r'```(\w*)\n?([\s\S]*?)```', replace_codeblock, text)
    # Inline code
    text = _re.sub(r'`([^`]+)`',
        lambda m: f'<code style="background:#0a0a0f;padding:1px 5px;border-radius:4px;font-size:0.88em;color:#e8eaed;font-family:monospace;">{m.group(1)}</code>', text)
    # Bold
    text = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Headings
    text = _re.sub(r'^### (.+)$', lambda m: f'<h4 style="color:{t["accent"]};margin:0.5rem 0 0.2rem;">{m.group(1)}</h4>', text, flags=_re.MULTILINE)
    text = _re.sub(r'^## (.+)$',  lambda m: f'<h3 style="color:{t["accent"]};margin:0.6rem 0 0.3rem;">{m.group(1)}</h3>', text, flags=_re.MULTILINE)
    text = _re.sub(r'^# (.+)$',   lambda m: f'<h2 style="color:{t["accent"]};margin:0.7rem 0 0.3rem;">{m.group(1)}</h2>', text, flags=_re.MULTILINE)
    # Unordered list
    def replace_ul(m):
        items = _re.findall(r'^[-*] (.+)$', m.group(0), _re.MULTILINE)
        lis = ''.join(f'<li style="margin:0.15rem 0;">{i}</li>' for i in items)
        return f'<ul style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;">{lis}</ul>'
    text = _re.sub(r'(^[-*] .+$\n?)+', replace_ul, text, flags=_re.MULTILINE)
    # Numbered list
    def replace_ol(m):
        items = _re.findall(r'^\d+\. (.+)$', m.group(0), _re.MULTILINE)
        lis = ''.join(f'<li style="margin:0.15rem 0;">{i}</li>' for i in items)
        return f'<ol style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;">{lis}</ol>'
    text = _re.sub(r'(^\d+\. .+$\n?)+', replace_ol, text, flags=_re.MULTILINE)
    # HR
    text = _re.sub(r'^---+$', f'<hr style="border-color:{t["border"]};margin:0.5rem 0;">', text, flags=_re.MULTILINE)
    # Newlines
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append('<br>')
        elif stripped.startswith('<'):
            result.append(line)
        else:
            result.append(line + '<br>')
    return '\n'.join(result)


def get_auto_title(first_message: str) -> str:
    """Generate a short chat title from the first user message."""
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Generate a very short chat title (3-5 words max). Return ONLY the title, no quotes."},
                {"role": "user", "content": first_message[:200]},
            ],
            max_tokens=15,
            temperature=0.3,
        )
        title = response.choices[0].message.content.strip().strip('"\'\' ')
        return title[:40] if title else "New Chat"
    except Exception:
        words = first_message.strip().split()[:5]
        return " ".join(words) + ("…" if len(first_message.split()) > 5 else "")

# ─────────────────────────────────────────
#  SESSION MANAGEMENT HELPERS
# ─────────────────────────────────────────
def init_sessions():
    """Load sessions from DB if first time this login, else sync state."""
    if not st.session_state.sessions:
        # Try loading saved chats from disk for this user
        saved = load_user_chats(st.session_state.current_user)
        if saved:
            st.session_state.sessions = saved
            # restore last active session
            first_sid = list(saved.keys())[0]
            st.session_state.active_session = first_sid
        else:
            st.session_state.sessions["default"] = {
                "name": "Chat 1",
                "messages": [],
                "starred": [],
            }
    sid = st.session_state.active_session
    if sid not in st.session_state.sessions:
        sid = list(st.session_state.sessions.keys())[0]
        st.session_state.active_session = sid
    st.session_state.messages = st.session_state.sessions[sid]["messages"]
    st.session_state.starred  = st.session_state.sessions[sid]["starred"]

def save_active_session():
    """Push current messages/starred into sessions dict AND persist to disk."""
    sid = st.session_state.active_session
    if sid in st.session_state.sessions:
        st.session_state.sessions[sid]["messages"] = st.session_state.messages
        st.session_state.sessions[sid]["starred"]  = st.session_state.starred
    save_user_chats(st.session_state.current_user, st.session_state.sessions)

def switch_session(sid: str):
    save_active_session()
    st.session_state.active_session = sid
    st.session_state.messages = st.session_state.sessions[sid]["messages"]
    st.session_state.starred  = st.session_state.sessions[sid]["starred"]
    st.session_state.show_sessions = False

def new_session():
    save_active_session()
    import uuid
    sid  = str(uuid.uuid4())[:8]
    num  = len(st.session_state.sessions) + 1
    st.session_state.sessions[sid] = {
        "name": f"Chat {num}",
        "messages": [],
        "starred":  [],
    }
    switch_session(sid)

def delete_session(sid: str):
    if len(st.session_state.sessions) <= 1:
        return
    del st.session_state.sessions[sid]
    first = list(st.session_state.sessions.keys())[0]
    switch_session(first)

# ─────────────────────────────────────────
#  SPLASH SCREEN  (particle network)
# ─────────────────────────────────────────
def splash_screen():
    """Cinematic particle network startup animation."""
    import streamlit.components.v1 as components
    components.html("""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: #000000;
    overflow: hidden;
    font-family: 'Space Grotesk', 'Inter', sans-serif;
  }
  canvas { display:block; position:fixed; inset:0; z-index:0; }

  .center {
    position: fixed; inset:0;
    display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    z-index: 10; pointer-events:none;
  }

  .logo-ring {
    width: 100px; height: 100px;
    border-radius: 50%;
    border: 1.5px solid #ef444433;
    border-top-color: #ef4444;
    display:flex; align-items:center; justify-content:center;
    animation: spin 3s linear infinite;
    margin-bottom: 1.8rem;
    box-shadow: 0 0 30px #ef444430, inset 0 0 20px #ef444410;
    opacity: 0;
    animation: spin 3s linear infinite, fadeIn 0.8s ease 0.5s forwards;
  }
  .logo-ring-inner {
    width: 80px; height: 80px;
    border-radius: 50%;
    border: 1px solid #ef444422;
    border-bottom-color: #f87171;
    display:flex; align-items:center; justify-content:center;
    animation: spinRev 2s linear infinite;
  }
  .logo-text {
    font-size: 1.1rem; font-weight: 700;
    letter-spacing: 0.1em;
    background: linear-gradient(135deg, #fff, #f87171, #ef4444);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .title {
    font-size: 3.8rem; font-weight: 700;
    letter-spacing: -0.03em; line-height: 1;
    background: linear-gradient(135deg, #ffffff 0%, #f87171 50%, #ef4444 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    opacity: 0; transform: translateY(20px);
    animation: slideUp 0.9s cubic-bezier(0.16,1,0.3,1) 0.8s forwards;
    margin-bottom: 0.5rem;
  }
  .tagline {
    font-size: 0.68rem; letter-spacing: 0.3em;
    text-transform: uppercase; color: #ffffff44;
    opacity: 0;
    animation: fadeIn 0.8s ease 1.4s forwards;
    margin-bottom: 2.5rem;
  }
  .bar-track {
    width: 240px; height: 2px;
    background: #ffffff08; border-radius:100px;
    overflow:hidden; margin-bottom: 0.8rem;
    opacity:0; animation: fadeIn 0.5s ease 1.2s forwards;
  }
  .bar-fill {
    height:100%; width:0%; border-radius:100px;
    background: linear-gradient(90deg, #dc2626, #ef4444, #f87171, #ef4444);
    background-size: 200% auto;
    animation: barGrow 1.8s cubic-bezier(0.4,0,0.2,1) 1.3s forwards,
               barShine 1.2s linear infinite;
  }
  .status {
    font-size: 0.62rem; letter-spacing: 0.2em;
    text-transform: uppercase; color: #ef444466;
    height: 1rem; position:relative; width:200px; text-align:center;
    opacity:0; animation: fadeIn 0.5s ease 1.3s forwards;
  }
  .status span {
    position:absolute; left:50%; transform:translateX(-50%);
    opacity:0; white-space:nowrap;
    animation: statusCycle 0.6s ease both;
  }
  .status span:nth-child(1){ animation-delay:1.3s; }
  .status span:nth-child(2){ animation-delay:1.9s; }
  .status span:nth-child(3){ animation-delay:2.5s; }
  .status span:nth-child(4){ animation-delay:3.0s; }

  .dots {
    display:flex; gap:7px; margin-top:0.9rem;
    opacity:0; animation: fadeIn 0.5s ease 1.5s forwards;
  }
  .dot {
    width:5px; height:5px; border-radius:50%;
    animation: dotPulse 1.2s ease-in-out infinite;
  }
  .dot:nth-child(1){ background:#ef4444; animation-delay:0s; }
  .dot:nth-child(2){ background:#f87171; animation-delay:0.15s; }
  .dot:nth-child(3){ background:#fca5a5; animation-delay:0.3s; }
  .dot:nth-child(4){ background:#f87171; animation-delay:0.45s; }
  .dot:nth-child(5){ background:#ef4444; animation-delay:0.6s; }

  .byline {
    position:fixed; bottom:1.5rem; left:0; right:0;
    text-align:center; font-size:0.55rem;
    letter-spacing:0.2em; text-transform:uppercase;
    color:#ffffff0d;
    opacity:0; animation: fadeIn 1s ease 2s forwards;
  }

  @keyframes spin    { to{ transform:rotate(360deg); } }
  @keyframes spinRev { to{ transform:rotate(-360deg); } }
  @keyframes fadeIn  { to{ opacity:1; } }
  @keyframes slideUp {
    to{ opacity:1; transform:translateY(0); }
  }
  @keyframes barGrow { to{ width:100%; } }
  @keyframes barShine{
    0%  { background-position:-200% center; }
    100%{ background-position:200% center; }
  }
  @keyframes dotPulse{
    0%,100%{ transform:scale(0.7); opacity:0.3; }
    50%    { transform:scale(1.2); opacity:1; }
  }
  @keyframes statusCycle{
    0%  { opacity:0; transform:translateX(-50%) translateY(4px); }
    15% { opacity:1; transform:translateX(-50%) translateY(0); }
    70% { opacity:1; transform:translateX(-50%) translateY(0); }
    100%{ opacity:0; transform:translateX(-50%) translateY(-4px); }
  }
</style>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body>
<canvas id="c"></canvas>

<div class="center">
  <div class="logo-ring">
    <div class="logo-ring-inner">
      <span class="logo-text">PLM</span>
    </div>
  </div>
  <div class="title">PLM GPT</div>
  <div class="tagline">Where curiosity meets intelligence</div>
  <div class="bar-track"><div class="bar-fill"></div></div>
  <div class="status">
    <span>Initializing engine...</span>
    <span>Loading models...</span>
    <span>Preparing workspace...</span>
    <span>Almost ready...</span>
  </div>
  <div class="dots">
    <div class="dot"></div><div class="dot"></div><div class="dot"></div>
    <div class="dot"></div><div class="dot"></div>
  </div>
</div>
<div class="byline">Crafted by Pranav Chakravorty &nbsp;·&nbsp; PLM GPT</div>

<script>
const canvas = document.getElementById('c');
const ctx    = canvas.getContext('2d');

let W, H, particles = [], mouse = {x:0, y:0};
const COUNT   = 90;
const MAX_DIST = 140;
const RED     = '239,68,68';

function resize(){
  W = canvas.width  = window.innerWidth;
  H = canvas.height = window.innerHeight;
}
resize();
window.addEventListener('resize', resize);
window.addEventListener('mousemove', e => { mouse.x=e.clientX; mouse.y=e.clientY; });

// Create particles
for(let i=0;i<COUNT;i++){
  particles.push({
    x: Math.random()*1400,
    y: Math.random()*900,
    vx: (Math.random()-0.5)*0.5,
    vy: (Math.random()-0.5)*0.5,
    r: Math.random()*2+1,
    opacity: Math.random()*0.5+0.2
  });
}

function draw(){
  ctx.clearRect(0,0,W,H);

  // Subtle red vignette
  const vg = ctx.createRadialGradient(W/2,H/2,H*0.1, W/2,H/2,H*0.8);
  vg.addColorStop(0,'rgba(0,0,0,0)');
  vg.addColorStop(1,'rgba(10,0,0,0.6)');
  ctx.fillStyle = vg;
  ctx.fillRect(0,0,W,H);

  // Update + draw particles
  for(let i=0;i<particles.length;i++){
    const p = particles[i];
    p.x += p.vx; p.y += p.vy;
    if(p.x<0||p.x>W) p.vx*=-1;
    if(p.y<0||p.y>H) p.vy*=-1;

    // Mouse repel (subtle)
    const dx=p.x-mouse.x, dy=p.y-mouse.y;
    const md=Math.sqrt(dx*dx+dy*dy);
    if(md<100){ p.vx+=dx/md*0.05; p.vy+=dy/md*0.05; }

    // Draw dot
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
    ctx.fillStyle = `rgba(${RED},${p.opacity})`;
    ctx.fill();

    // Draw connections
    for(let j=i+1;j<particles.length;j++){
      const q=particles[j];
      const ex=p.x-q.x, ey=p.y-q.y;
      const dist=Math.sqrt(ex*ex+ey*ey);
      if(dist<MAX_DIST){
        const alpha = (1-dist/MAX_DIST)*0.25;
        ctx.beginPath();
        ctx.moveTo(p.x,p.y); ctx.lineTo(q.x,q.y);
        ctx.strokeStyle=`rgba(${RED},${alpha})`;
        ctx.lineWidth=0.8;
        ctx.stroke();
      }
    }
  }
  requestAnimationFrame(draw);
}

draw();
</script>
</body>
</html>
""", height=700, scrolling=False)

    import time
    time.sleep(3.5)
    st.session_state.splash_done = True
    st.rerun()

# ─────────────────────────────────────────
#  AUTH PAGE  (Login + Sign Up)
# ─────────────────────────────────────────
def auth_page():
    t = THEMES["dark"]   # auth page always uses dark theme for consistent look

    # Full-page background with orbs
    st.markdown(BG_ANIMATION, unsafe_allow_html=True)
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@1,500&display=swap');

      @keyframes gradientShift {{
        0%   {{ background-position: 0% 50%; }}
        50%  {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
      }}
      @keyframes cardSlideUp {{
        from {{ opacity: 0; transform: translateY(24px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
      }}
      @keyframes inputGlow {{
        0%, 100% {{ box-shadow: 0 0 0 0 #ef444400; }}
        50%       {{ box-shadow: 0 0 0 3px #ef444430; }}
      }}

      .stApp {{
        background: linear-gradient(-45deg, #0a0a0f, #12121a, #070710, #0a0a0f);
        background-size: 400% 400%;
        animation: gradientShift 12s ease infinite;
        font-family: 'Inter', sans-serif;
      }}

      /* ── Auth card ── */
      .auth-card {{
        background: linear-gradient(160deg, #12121add 0%, #070710dd 100%);
        border: 1px solid #ef444433;
        border-radius: 20px;
        padding: 2.4rem 2.8rem 2rem;
        margin: 0 auto;
        max-width: 420px;
        backdrop-filter: blur(16px);
        box-shadow: 0 8px 40px #0a000060, 0 0 60px #ef444410;
        animation: cardSlideUp 0.7s cubic-bezier(0.16,1,0.3,1) forwards;
      }}

      /* ── Logo area ── */
      .auth-logo-ring {{
        width: 72px; height: 72px; border-radius: 50%; margin: 0 auto 1rem;
        background: linear-gradient(135deg, #ef444418, #0a0a0f);
        border: 1.5px solid #ef444455;
        display: flex; align-items: center; justify-content: center;
        font-size: 2rem; line-height: 1;
        box-shadow: 0 0 24px #ef444430;
      }}
      .auth-title {{
        font-size: 2rem; font-weight: 800; letter-spacing: -0.02em;
        background: linear-gradient(135deg, #e8e0d0 30%, #ef4444 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; text-align: center; margin-bottom: 0.2rem;
      }}
      .auth-subtitle {{
        font-family: 'Playfair Display', serif; font-style: italic;
        font-size: 0.88rem; color: #888899; text-align: center; margin-bottom: 1.6rem;
      }}

      /* ── Tab switcher ── */
      .auth-tabs {{
        display: flex; gap: 0; border-radius: 10px; overflow: hidden;
        border: 1px solid #333355; margin-bottom: 1.5rem;
      }}
      .auth-tab {{
        flex: 1; text-align: center; padding: 0.55rem 0;
        font-size: 0.85rem; font-weight: 600; cursor: pointer;
        letter-spacing: 0.04em; transition: all 0.2s;
        color: #888899; background: transparent;
      }}
      .auth-tab-active {{
        background: linear-gradient(135deg, #ef444422, #dc262618);
        color: #ef4444;
        border-bottom: 2px solid #ef4444;
      }}

      /* ── Form field labels ── */
      .auth-label {{
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
        text-transform: uppercase; color: #888899; margin-bottom: 4px;
      }}

      /* ── Input override ── */
      .stTextInput > div > div > input {{
        background: #12122088 !important; color: #e8e0d8 !important;
        border: 1px solid #333355 !important; border-radius: 10px !important;
        font-size: 0.95rem !important; padding: 0.6rem 0.9rem !important;
        transition: all 0.2s;
      }}
      .stTextInput > div > div > input:focus {{
        border: 1px solid {t["accent"]} !important;
        box-shadow: 0 0 0 3px {t["accent"]}20 !important;
      }}

      /* ── Submit button ── */
      .stFormSubmitButton > button {{
        background: linear-gradient(135deg, #ef4444, #dc2626) !important;
        color: #0a0a0f !important; border: none !important;
        border-radius: 10px !important; font-weight: 700 !important;
        font-size: 0.95rem !important; letter-spacing: 0.04em !important;
        padding: 0.65rem 1rem !important;
        transition: all 0.25s !important;
        box-shadow: 0 4px 20px #ef444440 !important;
      }}
      .stFormSubmitButton > button:hover {{
        box-shadow: 0 6px 28px #ef444470 !important;
        transform: translateY(-1px) !important;
      }}

      /* ── Divider ── */
      .auth-divider {{
        display: flex; align-items: center; gap: 0.7rem;
        margin: 1rem 0 0.8rem; color: #444466; font-size: 0.75rem;
      }}
      .auth-divider::before, .auth-divider::after {{
        content: ""; flex: 1; height: 1px; background: #333355;
      }}

      /* ── Switch link ── */
      .auth-switch {{
        text-align: center; font-size: 0.82rem; color: #666688; margin-top: 0.6rem;
      }}

      /* ── Error / success ── */
      .auth-error {{
        background: #b91c1c18; border: 1px solid #b91c1c66;
        border-radius: 8px; padding: 0.55rem 0.8rem;
        color: #e08080; font-size: 0.83rem; margin-bottom: 0.6rem;
      }}
      .auth-success {{
        background: #ef444418; border: 1px solid #ef444466;
        border-radius: 8px; padding: 0.55rem 0.8rem;
        color: #ef4444; font-size: 0.83rem; margin-bottom: 0.6rem;
      }}

      /* ── Password strength bar ── */
      .pw-strength-wrap {{
        height: 3px; border-radius: 100px; background: #333355;
        margin-top: 4px; margin-bottom: 2px; overflow: hidden;
      }}
      .pw-strength-bar {{
        height: 100%; border-radius: 100px; transition: width 0.3s;
      }}

      /* ── Features strip ── */
      .auth-features {{
        display: flex; justify-content: center; gap: 1.2rem;
        flex-wrap: wrap; margin-top: 1.2rem;
      }}
      .auth-feature-pill {{
        font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase;
        color: #555577; display: flex; align-items: center; gap: 4px;
      }}

      /* ── Bottom byline ── */
      .auth-byline {{
        text-align: center; font-size: 0.65rem; letter-spacing: 0.1em;
        text-transform: uppercase; color: #333355; margin-top: 1.4rem;
      }}

      /* ── Hide Streamlit extras on auth page ── */
      #MainMenu, header, footer,
      [data-testid="stToolbar"] {{ display:none !important; }}
    </style>
    """, unsafe_allow_html=True)

    # ─── Header ───
    st.markdown("""
    <div style="text-align:center; padding: 2.5rem 0 0.5rem;">
      <div class="auth-logo-ring" style="width:72px;height:72px;border-radius:50%;margin:0 auto 1rem;
           background:linear-gradient(135deg,#ef444414,#0a0a0f);border:1.5px solid #ef444450;
           display:flex;align-items:center;justify-content:center;
           box-shadow:0 0 28px #ef444430, inset 0 0 16px #ef444408;">
        <svg width="46" height="46" viewBox="0 0 54 54" fill="none" xmlns="http://www.w3.org/2000/svg">
          <text x="3" y="38" font-family="'Inter',sans-serif" font-weight="800" font-size="22"
                fill="url(#authGrad)" letter-spacing="-1">PLM</text>
          <rect x="3" y="42" width="48" height="2.5" rx="1.25" fill="url(#authGrad)" opacity="0.6"/>
          <circle cx="48" cy="7" r="3" fill="#ef4444" opacity="0.9"/>
          <circle cx="48" cy="7" r="5.5" fill="#ef4444" opacity="0.2"/>
          <defs>
            <linearGradient id="authGrad" x1="0" y1="0" x2="54" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#e8e0d0"/>
              <stop offset="55%" stop-color="#ef4444"/>
              <stop offset="100%" stop-color="#dc2626"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
      <div class="auth-title">PLM GPT</div>
      <div class="auth-subtitle">Where curiosity meets intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    # ─── Tab buttons ───
    col_l, col_r = st.columns(2)
    with col_l:
        login_active = "auth-tab auth-tab-active" if st.session_state.auth_tab == "login" else "auth-tab"
        if st.button("🔐  Sign In", use_container_width=True, key="tab_login"):
            st.session_state.auth_tab = "login"
            st.rerun()
    with col_r:
        signup_active = "auth-tab auth-tab-active" if st.session_state.auth_tab == "signup" else "auth-tab"
        if st.button("✨  Sign Up", use_container_width=True, key="tab_signup"):
            st.session_state.auth_tab = "signup"
            st.rerun()

    st.markdown("<div style='height:0.2rem'></div>", unsafe_allow_html=True)

    # ─── Active indicator bar ───
    bar_left = "0%" if st.session_state.auth_tab == "login" else "50%"
    st.markdown(f"""
    <div style="position:relative;height:3px;background:#12121a;border-radius:100px;margin-bottom:1.4rem;">
      <div style="position:absolute;top:0;left:{bar_left};width:50%;height:100%;
                  background:linear-gradient(90deg,#ef4444,#dc2626);border-radius:100px;
                  transition:left 0.3s ease;"></div>
    </div>
    """, unsafe_allow_html=True)

    _, mid_col, _ = st.columns([0.5, 3, 0.5])
    with mid_col:
        # ══════════════════════════════
        #  LOGIN FORM
        # ══════════════════════════════
        if st.session_state.auth_tab == "login":
            with st.form("login_form", clear_on_submit=False):
                st.markdown('<div class="auth-label">Username</div>', unsafe_allow_html=True)
                username = st.text_input("", placeholder="Enter your username", key="login_user",
                                         label_visibility="collapsed")
                st.markdown('<div class="auth-label" style="margin-top:0.6rem;">Password</div>', unsafe_allow_html=True)
                password = st.text_input("", placeholder="Enter your password", type="password",
                                         key="login_pass", label_visibility="collapsed")
                st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("🔐  Sign In", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.markdown('<div class="auth-error">⚠️ Please fill in all fields.</div>', unsafe_allow_html=True)
                else:
                    ok, result = verify_login(username, password)
                    if ok:
                        st.session_state.authenticated  = True
                        st.session_state.current_user   = username.strip().lower()
                        st.session_state.display_name   = result
                        st.session_state.last_activity  = time.time()
                        st.session_state.welcome_shown  = False
                        # Clear sessions so init_sessions() loads from DB fresh
                        st.session_state.sessions       = {}
                        st.session_state.messages       = []
                        st.session_state.starred        = []
                        st.session_state.active_session = "default"
                        st.rerun()
                    else:
                        st.markdown(f'<div class="auth-error">⚠️ {result}</div>', unsafe_allow_html=True)

            st.markdown("""
            <div class="auth-divider">or</div>
            <div class="auth-switch">
              Don't have an account? Click <strong style="color:#ef4444">Sign Up</strong> above.
            </div>
            """, unsafe_allow_html=True)

        # ══════════════════════════════
        #  SIGNUP FORM
        # ══════════════════════════════
        else:
            with st.form("signup_form", clear_on_submit=False):
                st.markdown('<div class="auth-label">Display Name</div>', unsafe_allow_html=True)
                display_name = st.text_input("", placeholder="How should we call you?",
                                              key="signup_name", label_visibility="collapsed")
                st.markdown('<div class="auth-label" style="margin-top:0.6rem;">Username</div>', unsafe_allow_html=True)
                new_username = st.text_input("", placeholder="Choose a username (min 3 chars)",
                                              key="signup_user", label_visibility="collapsed")
                st.markdown('<div class="auth-label" style="margin-top:0.6rem;">Password</div>', unsafe_allow_html=True)
                new_password = st.text_input("", placeholder="Choose a strong password (min 6 chars)",
                                              type="password", key="signup_pass", label_visibility="collapsed")
                st.markdown('<div class="auth-label" style="margin-top:0.6rem;">Confirm Password</div>', unsafe_allow_html=True)
                confirm_pw   = st.text_input("", placeholder="Repeat your password",
                                              type="password", key="signup_confirm", label_visibility="collapsed")
                st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("✨  Create Account", use_container_width=True)

            if submitted:
                if not all([display_name, new_username, new_password, confirm_pw]):
                    st.markdown('<div class="auth-error">⚠️ Please fill in all fields.</div>', unsafe_allow_html=True)
                elif new_password != confirm_pw:
                    st.markdown('<div class="auth-error">⚠️ Passwords do not match.</div>', unsafe_allow_html=True)
                else:
                    ok, msg = register_user(new_username, display_name, new_password)
                    if ok:
                        st.markdown(f'<div class="auth-success">✅ Account created! You can now sign in.</div>', unsafe_allow_html=True)
                        time.sleep(1)
                        st.session_state.auth_tab = "login"
                        st.rerun()
                    else:
                        st.markdown(f'<div class="auth-error">⚠️ {msg}</div>', unsafe_allow_html=True)

            st.markdown("""
            <div class="auth-divider">or</div>
            <div class="auth-switch">
              Already have an account? Click <strong style="color:#ef4444">Sign In</strong> above.
            </div>
            """, unsafe_allow_html=True)

    # ─── Feature pills ───
    st.markdown("""
    <div class="auth-features">
      <div class="auth-feature-pill">⚡ Fast Streaming</div>
      <div class="auth-feature-pill">🧠 Llama 3.3 70B</div>
      <div class="auth-feature-pill">🎭 4 AI Modes</div>
      <div class="auth-feature-pill">💬 Multi-Session</div>
    </div>
    <div class="auth-byline">PLM GPT · Crafted by Pranav Chakravorty</div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
#  WELCOME CARD
# ─────────────────────────────────────────
def render_welcome():
    t = THEMES[st.session_state.theme]
    name = st.session_state.display_name or "there"
    st.markdown(f"""
    <div class="welcome-card">
      <div class="welcome-greeting">Welcome back, {name} 👋</div>
      <div class="welcome-sub">
        Your intelligent companion for thoughtful conversations,<br>
        creative exploration, and precise answers — whenever you need them.
      </div>
      <div style="margin:0.8rem 0; color:{t['accent']}; font-size:1.3rem;">✦ &nbsp; ✦ &nbsp; ✦</div>
      <div class="welcome-sub" style="font-size:0.88rem; opacity:0.75;">
        Choose a conversation mode, or pick a suggestion below to get started.
      </div>
      <div class="welcome-dev">
        <span class="welcome-dot"></span>
        Crafted with precision by &nbsp;<strong style="color:{t['text']}; letter-spacing:0.05em;">Pranav Chakravorty</strong>
        <span class="welcome-dot"></span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"<p style='text-align:center; color:{t['sub']}; font-size:0.8rem; margin-bottom:0.3rem;'>✨ Try one of these</p>", unsafe_allow_html=True)
    cols = st.columns(2)
    for i, suggestion in enumerate(PROMPT_SUGGESTIONS):
        with cols[i % 2]:
            if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                clean = suggestion.split(" ", 1)[1] if suggestion[0] in "✍🧠💡📝🌍🔥" else suggestion
                st.session_state.messages.append({
                    "role": "user", "content": clean, "time": now_str(),
                    "feedback": None, "starred": False,
                })
                st.session_state["_pending_query"] = clean
                st.rerun()

# ─────────────────────────────────────────
#  CHAT PAGE
# ─────────────────────────────────────────
def chat_page():
    apply_theme()
    t = THEMES[st.session_state.theme]
    init_sessions()

    # ── Toolbar — compact 2-row design ──
    # Row 1: selectors
    r1c1, r1c2, r1c3 = st.columns([3, 3, 3])
    with r1c1:
        sel = st.selectbox("🧠 Model", list(MODELS.keys()),
            index=list(MODELS.values()).index(st.session_state.model),
            key="model_select")
        st.session_state.model = MODELS[sel]
    with r1c2:
        mode_sel = st.selectbox("🎭 Mode", list(CONVERSATION_MODES.keys()),
            index=list(CONVERSATION_MODES.keys()).index(st.session_state.conv_mode),
            key="mode_select")
        st.session_state.conv_mode = mode_sel
    with r1c3:
        temp_val = st.session_state.temperature
        lbl = "🧊 Factual" if temp_val < 0.4 else ("⚖️ Balanced" if temp_val < 0.75 else "🔥 Creative")
        st.session_state.temperature = st.slider(
            f"🎨 {lbl}", 0.0, 1.0, temp_val, 0.1, key="temp_slider")

    # Row 2: action buttons
    b1, b2, b3, b4, b5, b6, bsp = st.columns([1, 1, 1, 1, 1, 1, 3])
    with b1:
        theme_icon = "☀️" if st.session_state.theme == "dark" else "🌙"
        if st.button(theme_icon, use_container_width=True, key="theme_btn", help="Toggle theme"):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()
    with b2:
        star_label = f"⭐ {len(st.session_state.starred)}" if st.session_state.starred else "⭐"
        if st.button(star_label, use_container_width=True, key="starred_btn", help="Starred messages"):
            st.session_state.show_starred = not st.session_state.show_starred
            st.session_state.show_sessions = False
            st.rerun()
    with b3:
        sess_count = len(st.session_state.sessions)
        if st.button(f"💬 {sess_count}", use_container_width=True, key="sessions_btn", help="Chat sessions"):
            st.session_state.show_sessions = not st.session_state.show_sessions
            st.session_state.show_starred = False
            st.rerun()
    with b4:
        if st.button("➕", use_container_width=True, key="new_session_btn", help="New chat"):
            new_session()
            st.rerun()
    with b5:
        user_initial = (st.session_state.display_name or "U")[0].upper()
        if st.button(f"👤 {user_initial}", use_container_width=True, key="profile_btn", help="Profile"):
            st.session_state.show_profile = not st.session_state.get("show_profile", False)
            st.rerun()
    with b6:
        if st.button("🚪", use_container_width=True, key="logout_btn", help="Logout"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()
    st.markdown("<div style='margin-bottom:0.3rem'></div>", unsafe_allow_html=True)

    # ── Title ──
    active_chat = st.session_state.sessions.get(st.session_state.active_session, {}).get("name", "Chat")
    st.markdown(f"""
    <div class="plm-title">
      <h1>🤖 PLM GPT</h1>
      <div class="byline" style="color:{t['sub']};font-size:0.8rem;">
        {active_chat} &nbsp;·&nbsp; {st.session_state.conv_mode}
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")



    # ── Profile panel ──
    if st.session_state.get("show_profile", False):
        t = THEMES[st.session_state.theme]
        db = st.session_state.db
        uname = st.session_state.current_user
        udata = db["users"].get(uname, {})
        total_msgs = sum(len(s.get("messages", [])) for s in st.session_state.sessions.values())
        total_sessions = len(st.session_state.sessions)

        st.markdown(f"""
        <div style="background:{t['card']};border:1px solid {t['accent']}44;border-radius:14px;
                    padding:1.4rem 1.6rem;margin-bottom:1rem;">
          <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;">
            <div style="width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,{t['accent']},{t['user_border']});
                        display:flex;align-items:center;justify-content:center;font-size:1.4rem;
                        font-weight:800;color:{t['bg']};flex-shrink:0;">
              {(st.session_state.display_name or 'U')[0].upper()}
            </div>
            <div>
              <div style="font-size:1.1rem;font-weight:700;color:{t['text']};">{st.session_state.display_name}</div>
              <div style="font-size:0.78rem;color:{t['sub']};">@{uname} · Member since {udata.get('created_at','—')}</div>
            </div>
          </div>
          <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:0.4rem;">
            <div style="text-align:center;">
              <div style="font-size:1.4rem;font-weight:800;color:{t['accent']};">{total_sessions}</div>
              <div style="font-size:0.72rem;color:{t['sub']};">Chats</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.4rem;font-weight:800;color:{t['accent']};">{total_msgs}</div>
              <div style="font-size:0.72rem;color:{t['sub']};">Messages</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.4rem;font-weight:800;color:{t['accent']};">{len(st.session_state.starred)}</div>
              <div style="font-size:0.72rem;color:{t['sub']};">Starred</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["✏️ Edit Profile", "🔒 Change Password"])

        with tab1:
            with st.form("edit_profile_form"):
                new_display = st.text_input("Display Name", value=st.session_state.display_name, placeholder="Your name")
                if st.form_submit_button("💾 Save Changes", use_container_width=True):
                    if new_display.strip():
                        db["users"][uname]["display_name"] = new_display.strip()
                        st.session_state.display_name = new_display.strip()
                        _save_db(db)
                        st.success("✅ Display name updated!")
                    else:
                        st.error("Name cannot be empty.")

        with tab2:
            with st.form("change_pw_form"):
                old_pw  = st.text_input("Current Password", type="password")
                new_pw  = st.text_input("New Password", type="password", placeholder="Min 6 characters")
                conf_pw = st.text_input("Confirm New Password", type="password")
                if st.form_submit_button("🔒 Update Password", use_container_width=True):
                    if db["users"][uname]["password_hash"] != _hash(old_pw):
                        st.error("❌ Current password is incorrect.")
                    elif len(new_pw) < 6:
                        st.error("❌ New password must be at least 6 characters.")
                    elif new_pw != conf_pw:
                        st.error("❌ Passwords do not match.")
                    else:
                        db["users"][uname]["password_hash"] = _hash(new_pw)
                        _save_db(db)
                        st.success("✅ Password updated successfully!")

        st.markdown("---")

    # ── Sessions panel ──
    if st.session_state.show_sessions:
        st.markdown(f"<div class='summary-title'>💬 Chat Sessions</div>", unsafe_allow_html=True)
        for sid, sdata in list(st.session_state.sessions.items()):
            is_active = sid == st.session_state.active_session
            msg_n = len(sdata["messages"])
            sc1, sc2, sc3, sc4 = st.columns([4, 1, 1, 1])
            with sc1:
                card_class = "session-card session-active" if is_active else "session-card"
                # Show first message preview if exists
                preview = ""
                if sdata["messages"]:
                    first_user = next((m for m in sdata["messages"] if m["role"] == "user"), None)
                    if first_user:
                        preview = first_user["content"][:50] + ("…" if len(first_user["content"]) > 50 else "")
                st.markdown(f"""
                <div class="{card_class}">
                  <div>
                    <span class="session-name">{'▶ ' if is_active else ''}{sdata['name']}</span>
                    <span class="session-meta" style="margin-left:6px;">{msg_n} msgs</span>
                  </div>
                  {f'<div style="font-size:0.72rem;color:#888;margin-top:2px;font-style:italic;">{preview}</div>' if preview else ''}
                </div>""", unsafe_allow_html=True)
            with sc2:
                if not is_active:
                    if st.button("Open", key=f"open_{sid}"):
                        switch_session(sid)
                        st.rerun()
                else:
                    st.markdown(f"<span style='font-size:0.7rem;color:{t['accent']}'>active</span>", unsafe_allow_html=True)
            with sc3:
                # Rename button
                if st.button("✏️", key=f"rename_{sid}", help="Rename"):
                    st.session_state[f"renaming_{sid}"] = True
            with sc4:
                if len(st.session_state.sessions) > 1 and not is_active:
                    if st.button("🗑", key=f"del_{sid}"):
                        delete_session(sid)
                        st.rerun()

            # Inline rename input
            if st.session_state.get(f"renaming_{sid}"):
                new_name = st.text_input("New name", value=sdata["name"], key=f"newname_{sid}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Save", key=f"savename_{sid}"):
                        st.session_state.sessions[sid]["name"] = new_name.strip() or sdata["name"]
                        save_active_session()
                        st.session_state[f"renaming_{sid}"] = False
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"cancelname_{sid}"):
                        st.session_state[f"renaming_{sid}"] = False
                        st.rerun()
        st.markdown("---")

    # ── Starred messages panel ──
    if st.session_state.show_starred:
        if st.session_state.starred:
            st.markdown(f"<div class='summary-title' style='margin-bottom:0.3rem;'>⭐ Starred Messages</div>", unsafe_allow_html=True)
            for s in st.session_state.starred:
                st.markdown(f"<div class='starred-card'>{s}</div>", unsafe_allow_html=True)
        else:
            st.info("No starred messages yet. Click ⭐ on any response to save it.")
        st.markdown("---")

    # ── Summary + Export ──
    if len(st.session_state.messages) >= 6:
        ex_col1, ex_col2 = st.columns([1, 1])
        with ex_col1:
            if st.button("📋 Summarize this conversation", use_container_width=True, key="summarize_btn"):
                with st.spinner("Generating summary..."):
                    summary = get_summary()
                st.markdown(f"""
                <div class="summary-box">
                  <div class="summary-title">📋 Conversation Summary</div>
                  {summary}
                </div>""", unsafe_allow_html=True)
        with ex_col2:
            active_name = st.session_state.sessions.get(
                st.session_state.active_session, {}
            ).get("name", "Chat")
            export_lines = [
                "=" * 50,
                f"  PLM GPT — Conversation Export",
                f"  Session : {active_name}",
                f"  Mode    : {st.session_state.conv_mode}",
                f"  User    : {st.session_state.display_name}",
                f"  Exported: {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}",
                "=" * 50, "",
            ]
            for msg in st.session_state.messages:
                role = "You" if msg["role"] == "user" else "PLM GPT"
                ts   = msg.get("time", "")
                export_lines.append(f"[{ts}]  {role}")
                export_lines.append(msg["content"])
                export_lines.append("")
            export_lines += ["=" * 50, "  Developed by Pranav Chakravorty", "=" * 50]
            export_text = "\n".join(export_lines)
            filename = f"plmgpt_{active_name.replace(' ', '_').lower()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            st.download_button(
                label="⬇️ Export Chat",
                data=export_text, file_name=filename, mime="text/plain",
                use_container_width=True, key="export_btn",
            )

    # ── Welcome ──
    if not st.session_state.messages:
        render_welcome()

    # ── Pending query ──
    pending = st.session_state.pop("_pending_query", None)
    if pending:
        placeholder = st.empty()
        placeholder.markdown(f"""
        <div class="msg-with-avatar">
          <div class="msg-avatar msg-avatar-bot">PLM</div>
          <div class="msg-bubble">
            <div class="skeleton-wrap">
              <div class="skeleton skeleton-wide"></div>
              <div class="skeleton skeleton-med"></div>
              <div class="skeleton skeleton-short"></div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
        full_reply = ""
        stream_placeholder = st.empty()
        for chunk in stream_response(pending):
            full_reply += chunk
            stream_placeholder.markdown(
                f'<div class="stream-box"><span class="msg-label" style="display:block;margin-bottom:0.3rem;opacity:0.5;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;">PLM GPT</span>{full_reply}▌</div>',
                unsafe_allow_html=True
            )
        placeholder.empty()
        stream_placeholder.empty()
        st.session_state.messages.append({
            "role": "assistant", "content": full_reply,
            "time": now_str(), "feedback": None, "starred": False,
        })
        # ── Auto-title for prompt suggestion queries ──
        sid = st.session_state.active_session
        cur_name = st.session_state.sessions.get(sid, {}).get("name", "")
        if len(st.session_state.messages) == 2 and cur_name.startswith("Chat "):
            new_title = get_auto_title(pending)
            st.session_state.sessions[sid]["name"] = new_title
        save_active_session()
        st.rerun()

    # ── Chat history ──
    for i, msg in enumerate(st.session_state.messages):
        ts = msg.get("time", "")
        is_starred = msg.get("starred", False)
        user_initial = (st.session_state.display_name or "U")[0].upper()

        if msg["role"] == "user":
            st.markdown(f"""
            <div class="msg-row-user">
              <div>
                <div class="msg-user">
                  {msg['content']}
                  <div style="font-size:0.62rem;opacity:0.6;margin-top:4px;text-align:right;">{ts}</div>
                </div>
              </div>
              <div class="msg-avatar msg-avatar-user" style="margin-left:8px;margin-top:4px;flex-shrink:0;">{user_initial}</div>
            </div>""", unsafe_allow_html=True)
        else:
            rendered = render_markdown(msg['content'], t)
            st.markdown(f"""
            <div class="msg-row-bot">
              <div class="msg-avatar msg-avatar-bot" style="margin-right:8px;margin-top:4px;flex-shrink:0;">PLM</div>
              <div>
                <div class="msg-bot">
                  <div class="msg-body">{rendered}</div>
                  <div style="font-size:0.62rem;opacity:0.5;margin-top:4px;">{ts}</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)
            fb_col1, fb_col2, fb_col3, fb_col4, fb_col5 = st.columns([1, 1, 1, 1, 5])
            feedback = msg.get("feedback")
            star_icon = "⭐" if is_starred else "☆"
            with fb_col1:
                if st.button("👍", key=f"like_{i}", help="Good response"):
                    st.session_state.messages[i]["feedback"] = "liked"
                    st.rerun()
            with fb_col2:
                if st.button("👎", key=f"dislike_{i}", help="Bad response"):
                    st.session_state.messages[i]["feedback"] = "disliked"
                    st.rerun()
            with fb_col3:
                if st.button(star_icon, key=f"star_{i}", help="Star this response"):
                    if not is_starred:
                        st.session_state.messages[i]["starred"] = True
                        st.session_state.starred.append(msg["content"])
                    else:
                        st.session_state.messages[i]["starred"] = False
                        if msg["content"] in st.session_state.starred:
                            st.session_state.starred.remove(msg["content"])
                    save_active_session()
                    st.rerun()
            with fb_col4:
                safe_content = msg['content'].replace('`','\\`').replace('\n','\\n').replace('\r','')
                st.markdown(f"""
                <button onclick="navigator.clipboard.writeText(`{safe_content}`).then(()=>{{
                  this.innerText='✅'; setTimeout(()=>this.innerText='📋',1500);
                }})" title="Copy"
                style="background:transparent;border:1px solid {t['border']};border-radius:6px;
                       padding:3px 8px;font-size:0.8rem;cursor:pointer;color:{t['sub']};
                       transition:all 0.15s;">📋</button>
                """, unsafe_allow_html=True)
            if feedback == "liked":
                st.markdown(f"<p style='font-size:0.7rem;color:{t['accent']};margin-top:-0.3rem;'>✓ Marked as helpful</p>", unsafe_allow_html=True)
            elif feedback == "disliked":
                st.markdown(f"<p style='font-size:0.7rem;color:#e05555;margin-top:-0.3rem;'>✗ Marked as not helpful</p>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

    # ── Input form ──
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "", placeholder="Type your message here...",
            key="input", max_chars=3000,
        )
        submit = st.form_submit_button("Ask PLM GPT", use_container_width=True)

    char_count = len(user_input) if user_input else 0
    words      = len(user_input.split()) if user_input and user_input.strip() else 0
    warn_class = "char-danger" if char_count > 2700 else ("char-warn" if char_count > 2000 else "")
    st.markdown(
        f"<div class='char-counter {warn_class}'>{words} words &nbsp;·&nbsp; {char_count} / 3000 chars</div>",
        unsafe_allow_html=True
    )

    if submit:
        if is_session_expired():
            st.error("Session expired. Please login again.")
            st.session_state.authenticated = False
            time.sleep(1)
            st.rerun()
            return
        refresh_activity()
        clean = sanitize(user_input)
        if not clean:
            st.warning("Please enter a message first.")
        elif is_rate_limited():
            st.error(f"Too many requests — max {MAX_REQUESTS} per minute. Please wait.")
        else:
            st.session_state.messages.append({
                "role": "user", "content": clean,
                "time": now_str(), "feedback": None, "starred": False,
            })
            # ── Confetti on very first message ever ──
            if len(st.session_state.messages) == 1 and not st.session_state.get("confetti_shown"):
                st.session_state.confetti_shown = True
                st.markdown("""
                <script>
                (function(){
                  const colors=['#ef4444','#dc2626','#faf8f5','#b91c1c','#99aab5'];
                  const count = 120;
                  for(let i=0;i<count;i++){
                    const el=document.createElement('div');
                    el.style.cssText=`position:fixed;top:-10px;left:${Math.random()*100}vw;
                      width:${4+Math.random()*6}px;height:${8+Math.random()*8}px;
                      background:${colors[Math.floor(Math.random()*colors.length)]};
                      border-radius:2px;z-index:99999;pointer-events:none;
                      animation:confettiFall ${1.5+Math.random()*2}s ease-in forwards;
                      transform:rotate(${Math.random()*360}deg);
                      animation-delay:${Math.random()*0.8}s`;
                    document.body.appendChild(el);
                    setTimeout(()=>el.remove(), 4000);
                  }
                  const style=document.createElement('style');
                  style.textContent=`@keyframes confettiFall{
                    to{top:110vh;transform:rotate(${Math.random()*720}deg);opacity:0;}}`;
                  document.head.appendChild(style);
                })();
                </script>
                """, unsafe_allow_html=True)

            typing_ph = st.empty()
            # ── Skeleton loading ──
            typing_ph.markdown(f"""
            <div class="msg-with-avatar">
              <div class="msg-avatar msg-avatar-bot">PLM</div>
              <div class="msg-bubble">
                <div class="skeleton-wrap">
                  <div class="skeleton skeleton-wide"></div>
                  <div class="skeleton skeleton-med"></div>
                  <div class="skeleton skeleton-short"></div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)
            full_reply = ""
            stream_ph = st.empty()
            for chunk in stream_response(clean):
                full_reply += chunk
                stream_ph.markdown(
                    f'<div class="stream-box"><span class="msg-label" style="display:block;margin-bottom:0.3rem;opacity:0.5;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;">PLM GPT</span>{full_reply}▌</div>',
                    unsafe_allow_html=True
                )
            typing_ph.empty()
            stream_ph.empty()
            st.session_state.messages.append({
                "role": "assistant", "content": full_reply,
                "time": now_str(), "feedback": None, "starred": False,
            })
            # ── Auto-title: set chat name from first exchange ──
            sid = st.session_state.active_session
            current_name = st.session_state.sessions.get(sid, {}).get("name", "")
            if len(st.session_state.messages) == 2 and current_name.startswith("Chat "):
                new_title = get_auto_title(clean)
                st.session_state.sessions[sid]["name"] = new_title
            save_active_session()
            st.rerun()

    st.markdown("""
    <script>
    (function() {
      function scrollToBottom() {
        const doc = window.parent.document;
        const scrollable = doc.querySelector('[data-testid="stAppViewBlockContainer"]')
                        || doc.querySelector('section.main')
                        || doc.documentElement;
        if (scrollable) scrollable.scrollTop = scrollable.scrollHeight;
        window.parent.scrollTo(0, window.parent.document.body.scrollHeight);
      }
      setTimeout(scrollToBottom, 200);
    })();
    </script>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
#  ENTRY POINT  — Splash → Auth → Chat
# ─────────────────────────────────────────
if not st.session_state.splash_done:
    splash_screen()
elif not st.session_state.authenticated:
    auth_page()
else:
    chat_page()
