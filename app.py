import time
import datetime
import hashlib
import streamlit as st
from groq import Groq

# ─────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="PLM GPT",
    page_icon="🤖",
    layout="centered",
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
#  USER ACCOUNTS  (in-memory store)
# ─────────────────────────────────────────
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# Seed a default admin account from secrets so existing users aren't locked out
_DEFAULT_ADMIN = st.secrets.get("ADMIN_USER", "admin")
_DEFAULT_PASS  = st.secrets.get("APP_PASSWORD", "plmgpt2024")

if "user_db" not in st.session_state:
    st.session_state.user_db = {
        _DEFAULT_ADMIN: {
            "password_hash": _hash(_DEFAULT_PASS),
            "display_name":  "Admin",
            "created_at":    datetime.datetime.now().strftime("%d %b %Y"),
        }
    }

def register_user(username: str, display_name: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if username in st.session_state.user_db:
        return False, "Username already taken. Choose another."
    st.session_state.user_db[username] = {
        "password_hash": _hash(password),
        "display_name":  display_name.strip() or username,
        "created_at":    datetime.datetime.now().strftime("%d %b %Y"),
    }
    return True, "Account created!"

def verify_login(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if username not in st.session_state.user_db:
        return False, "No account found with that username."
    user = st.session_state.user_db[username]
    if user["password_hash"] != _hash(password):
        return False, "Incorrect password."
    return True, user["display_name"]

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
    "voice_text":      "",
    "sessions":        {},
    "active_session":  "default",
    "show_sessions":   False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────
#  THEMES
# ─────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":          "#0f0f1a",
        "card":        "#1a1a2e",
        "input_bg":    "#1e1e2e",
        "text":        "#f0f0f0",
        "sub":         "#aaaaaa",
        "accent":      "#00c9a7",
        "border":      "#444444",
        "user_bg":     "#1e2a3a",
        "user_border": "#3a8fcc",
        "btn_bg":      "#2a2a3d",
        "btn_text":    "#cccccc",
        "toolbar_bg":  "#16162a",
        "welcome_bg":  "#0d1f2d",
        "grad1":       "#0f0f1a",
        "grad2":       "#1a1a2e",
        "grad3":       "#0d1a2a",
    },
    "light": {
        "bg":          "#f0f2f6",
        "card":        "#ffffff",
        "input_bg":    "#ffffff",
        "text":        "#1a1a2e",
        "sub":         "#666666",
        "accent":      "#00a388",
        "border":      "#cccccc",
        "user_bg":     "#ddeeff",
        "user_border": "#3a8fcc",
        "btn_bg":      "#e0e0e0",
        "btn_text":    "#333333",
        "toolbar_bg":  "#e4e6f0",
        "welcome_bg":  "#e8f4f8",
        "grad1":       "#f0f2f6",
        "grad2":       "#e8f4f0",
        "grad3":       "#eaf0ff",
    },
}

# ─────────────────────────────────────────
#  BACKGROUND ANIMATIONS (particles + orbs)
# ─────────────────────────────────────────
BG_ANIMATION = """
<style>
.plm-orb {
  position: fixed;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
}
.plm-orb-1 {
  width: 500px; height: 500px;
  background: radial-gradient(circle at center, #00c9a740 0%, #00c9a715 40%, transparent 70%);
  top: -150px; left: -150px;
  animation: orbMove1 20s ease-in-out infinite;
  filter: blur(40px);
}
.plm-orb-2 {
  width: 400px; height: 400px;
  background: radial-gradient(circle at center, #3a8fcc35 0%, #3a8fcc10 40%, transparent 70%);
  bottom: -100px; right: -100px;
  animation: orbMove2 25s ease-in-out infinite;
  filter: blur(50px);
}
.plm-orb-3 {
  width: 300px; height: 300px;
  background: radial-gradient(circle at center, #7b4ccc30 0%, #7b4ccc0d 40%, transparent 70%);
  top: 35%; left: 5%;
  animation: orbMove3 30s ease-in-out infinite;
  filter: blur(45px);
}
.plm-orb-4 {
  width: 250px; height: 250px;
  background: radial-gradient(circle at center, #00c9a725 0%, transparent 70%);
  top: 60%; right: 10%;
  animation: orbMove4 22s ease-in-out infinite;
  filter: blur(35px);
}
@keyframes orbMove1 {
  0%,100% { transform: translate(0px, 0px) scale(1); }
  33%      { transform: translate(60px, 40px) scale(1.08); }
  66%      { transform: translate(20px, 80px) scale(0.95); }
}
@keyframes orbMove2 {
  0%,100% { transform: translate(0px, 0px) scale(1); }
  33%      { transform: translate(-50px, -40px) scale(1.1); }
  66%      { transform: translate(-20px, -70px) scale(0.92); }
}
@keyframes orbMove3 {
  0%,100% { transform: translate(0px, 0px) scale(1); }
  50%      { transform: translate(40px, -50px) scale(1.12); }
}
@keyframes orbMove4 {
  0%,100% { transform: translate(0px, 0px) scale(1); }
  40%      { transform: translate(-30px, 40px) scale(1.06); }
  80%      { transform: translate(20px, -20px) scale(0.94); }
}
.plm-dot {
  position: fixed;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
  animation: dotFloat linear infinite;
}
.plm-dot-1  { width:3px;  height:3px;  background:#00c9a7; top:10%; left:15%; opacity:0.4; animation-duration:8s;  animation-delay:0s;   }
.plm-dot-2  { width:2px;  height:2px;  background:#3a8fcc; top:25%; left:80%; opacity:0.3; animation-duration:12s; animation-delay:-3s;  }
.plm-dot-3  { width:4px;  height:4px;  background:#7b4ccc; top:60%; left:25%; opacity:0.25;animation-duration:10s; animation-delay:-5s;  }
.plm-dot-4  { width:2px;  height:2px;  background:#00c9a7; top:75%; left:65%; opacity:0.35;animation-duration:15s; animation-delay:-7s;  }
.plm-dot-5  { width:3px;  height:3px;  background:#3a8fcc; top:40%; left:45%; opacity:0.3; animation-duration:9s;  animation-delay:-2s;  }
.plm-dot-6  { width:2px;  height:2px;  background:#00c9a7; top:85%; left:10%; opacity:0.4; animation-duration:11s; animation-delay:-4s;  }
.plm-dot-7  { width:4px;  height:4px;  background:#7b4ccc; top:15%; left:55%; opacity:0.2; animation-duration:14s; animation-delay:-9s;  }
.plm-dot-8  { width:2px;  height:2px;  background:#3a8fcc; top:50%; left:90%; opacity:0.3; animation-duration:7s;  animation-delay:-1s;  }
.plm-dot-9  { width:3px;  height:3px;  background:#00c9a7; top:70%; left:40%; opacity:0.35;animation-duration:13s; animation-delay:-6s;  }
.plm-dot-10 { width:2px;  height:2px;  background:#7b4ccc; top:30%; left:5%;  opacity:0.25;animation-duration:16s; animation-delay:-11s; }
.plm-dot-11 { width:3px;  height:3px;  background:#00c9a7; top:5%;  left:70%; opacity:0.3; animation-duration:10s; animation-delay:-8s;  }
.plm-dot-12 { width:2px;  height:2px;  background:#3a8fcc; top:90%; left:50%; opacity:0.4; animation-duration:18s; animation-delay:-13s; }
@keyframes dotFloat {
  0%   { transform: translateY(0px)   translateX(0px);   opacity: 0.4; }
  25%  { transform: translateY(-20px) translateX(10px);  opacity: 0.7; }
  50%  { transform: translateY(-35px) translateX(-8px);  opacity: 0.3; }
  75%  { transform: translateY(-15px) translateX(15px);  opacity: 0.6; }
  100% { transform: translateY(0px)   translateX(0px);   opacity: 0.4; }
}
[data-testid="stAppViewContainer"] > section,
[data-testid="stAppViewBlockContainer"],
.block-container { position: relative; z-index: 1; }
</style>
<div class="plm-orb plm-orb-1"></div>
<div class="plm-orb plm-orb-2"></div>
<div class="plm-orb plm-orb-3"></div>
<div class="plm-orb plm-orb-4"></div>
<div class="plm-dot plm-dot-1"></div>
<div class="plm-dot plm-dot-2"></div>
<div class="plm-dot plm-dot-3"></div>
<div class="plm-dot plm-dot-4"></div>
<div class="plm-dot plm-dot-5"></div>
<div class="plm-dot plm-dot-6"></div>
<div class="plm-dot plm-dot-7"></div>
<div class="plm-dot plm-dot-8"></div>
<div class="plm-dot plm-dot-9"></div>
<div class="plm-dot plm-dot-10"></div>
<div class="plm-dot plm-dot-11"></div>
<div class="plm-dot plm-dot-12"></div>
"""

def apply_theme():
    t = THEMES[st.session_state.theme]
    st.markdown(BG_ANIMATION, unsafe_allow_html=True)
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;1,500&family=Inter:wght@400;500;600;700;800&display=swap');

      @keyframes gradientShift {{
        0%   {{ background-position: 0% 50%; }}
        50%  {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
      }}
      .stApp {{
        background: linear-gradient(-45deg, {t['grad1']}, {t['grad2']}, {t['grad3']}, {t['bg']});
        background-size: 400% 400%;
        animation: gradientShift 12s ease infinite;
        font-family: 'Inter', sans-serif;
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
        font-family:'Inter', sans-serif; margin-bottom:0.1rem;
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
      .msg-user {{
        background:{t['user_bg']}; border-left:4px solid {t['user_border']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.6;
      }}
      .msg-bot {{
        background:{t['card']}cc; border-left:4px solid {t['accent']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.7;
        backdrop-filter: blur(4px);
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
      .char-danger {{ color:#e05555 !important; opacity:1 !important; }}
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
      }}
      @media (min-width: 641px) and (max-width: 900px) {{
        .block-container {{ padding: 0.8rem 1rem 2rem 1rem !important; max-width: 100% !important; }}
        .plm-title h1 {{ font-size: 2.1rem !important; }}
        .msg-user, .msg-bot {{ font-size: 0.92rem; }}
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
    except Exception:
        yield "⚠️ Something went wrong. Please try again in a moment."

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
#  SESSION MANAGEMENT HELPERS
# ─────────────────────────────────────────
def init_sessions():
    if not st.session_state.sessions:
        st.session_state.sessions["default"] = {
            "name": "Chat 1",
            "messages": [],
            "starred": [],
        }
    sid = st.session_state.active_session
    if sid in st.session_state.sessions:
        st.session_state.messages = st.session_state.sessions[sid]["messages"]
        st.session_state.starred  = st.session_state.sessions[sid]["starred"]

def save_active_session():
    sid = st.session_state.active_session
    if sid in st.session_state.sessions:
        st.session_state.sessions[sid]["messages"] = st.session_state.messages
        st.session_state.sessions[sid]["starred"]  = st.session_state.starred

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
#  SPLASH SCREEN  (startup animation)
# ─────────────────────────────────────────
def splash_screen():
    """Full-screen startup animation. Runs once per browser session."""
    st.markdown("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;800&family=Playfair+Display:ital,wght@1,500&display=swap');

      @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }
      @keyframes splashFadeIn {
        from { opacity: 0; transform: translateY(30px) scale(0.97); }
        to   { opacity: 1; transform: translateY(0px) scale(1); }
      }
      @keyframes logoGlow {
        0%, 100% { text-shadow: 0 0 20px #00c9a780, 0 0 40px #00c9a740; }
        50%       { text-shadow: 0 0 40px #00c9a7cc, 0 0 80px #00c9a760, 0 0 120px #00c9a730; }
      }
      @keyframes barFill {
        0%   { width: 0%; }
        15%  { width: 18%; }
        35%  { width: 42%; }
        55%  { width: 63%; }
        75%  { width: 80%; }
        90%  { width: 92%; }
        100% { width: 100%; }
      }
      @keyframes barShimmer {
        0%   { background-position: -200% center; }
        100% { background-position: 200% center; }
      }
      @keyframes dotPulse {
        0%, 80%, 100% { transform: scale(0.6); opacity: 0.3; }
        40%            { transform: scale(1.2); opacity: 1; }
      }
      @keyframes taglineFade {
        0%   { opacity: 0; transform: translateY(10px); }
        100% { opacity: 1; transform: translateY(0); }
      }
      @keyframes orbSplash1 {
        0%,100% { transform: translate(0,0) scale(1); }
        50%      { transform: translate(40px,-30px) scale(1.1); }
      }
      @keyframes orbSplash2 {
        0%,100% { transform: translate(0,0) scale(1); }
        50%      { transform: translate(-30px,40px) scale(1.08); }
      }
      @keyframes statusCycle {
        0%   { opacity: 0; }
        10%  { opacity: 1; }
        30%  { opacity: 1; }
        40%  { opacity: 0; }
        100% { opacity: 0; }
      }

      .splash-wrap {
        position: fixed; inset: 0;
        background: linear-gradient(-45deg, #0f0f1a, #1a1a2e, #0d1a2a, #0f0f1a);
        background-size: 400% 400%;
        animation: gradientShift 8s ease infinite;
        display: flex; align-items: center; justify-content: center;
        z-index: 9999;
        font-family: 'Inter', sans-serif;
      }
      .splash-orb-1 {
        position: fixed; width: 600px; height: 600px; border-radius: 50%;
        background: radial-gradient(circle, #00c9a740 0%, transparent 65%);
        top: -200px; left: -200px; filter: blur(50px);
        animation: orbSplash1 6s ease-in-out infinite;
        pointer-events: none;
      }
      .splash-orb-2 {
        position: fixed; width: 500px; height: 500px; border-radius: 50%;
        background: radial-gradient(circle, #3a8fcc35 0%, transparent 65%);
        bottom: -150px; right: -150px; filter: blur(60px);
        animation: orbSplash2 8s ease-in-out infinite;
        pointer-events: none;
      }
      .splash-orb-3 {
        position: fixed; width: 300px; height: 300px; border-radius: 50%;
        background: radial-gradient(circle, #7b4ccc30 0%, transparent 65%);
        top: 50%; left: 60%; filter: blur(40px);
        animation: orbSplash1 10s ease-in-out infinite reverse;
        pointer-events: none;
      }
      .splash-card {
        animation: splashFadeIn 0.9s cubic-bezier(0.16,1,0.3,1) forwards;
        text-align: center; padding: 3rem 3.5rem; max-width: 440px; width: 90%;
        position: relative; z-index: 1;
      }
      .splash-logo-ring {
        width: 96px; height: 96px; border-radius: 50%; margin: 0 auto 1.4rem;
        background: linear-gradient(135deg, #00c9a718, #1a1a2e);
        border: 2px solid #00c9a755;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 0 40px #00c9a730, inset 0 0 20px #00c9a710;
        animation: logoGlow 3s ease-in-out infinite;
        padding: 4px;
      }
      .splash-title {
        font-size: 3.2rem; font-weight: 800; letter-spacing: -0.02em;
        background: linear-gradient(135deg, #ffffff 30%, #00c9a7 70%, #3a8fcc 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; margin-bottom: 0.4rem;
        animation: logoGlow 3s ease-in-out infinite;
      }
      .splash-tagline {
        font-family: 'Playfair Display', Georgia, serif;
        font-style: italic; font-size: 1rem; color: #aaaaaa;
        line-height: 1.6; margin-bottom: 2.2rem;
        animation: taglineFade 1s 0.5s ease forwards; opacity: 0;
      }
      .splash-bar-wrap {
        width: 100%; background: #ffffff12; border-radius: 100px;
        height: 4px; overflow: hidden; margin-bottom: 1rem;
        box-shadow: 0 0 10px #00000040;
      }
      .splash-bar {
        height: 100%; border-radius: 100px;
        background: linear-gradient(90deg, #00c9a7, #3a8fcc, #7b4ccc, #00c9a7);
        background-size: 200% auto;
        animation: barFill 2.8s cubic-bezier(0.4,0,0.2,1) forwards,
                   barShimmer 1.5s linear infinite;
      }
      .splash-status {
        font-size: 0.75rem; font-weight: 500; letter-spacing: 0.08em;
        text-transform: uppercase; color: #666688; margin-bottom: 0.6rem;
        min-height: 1.1rem;
      }
      .splash-status span {
        position: absolute;
        animation: statusCycle 2.8s linear forwards;
      }
      .splash-status span:nth-child(1) { animation-delay: 0s; }
      .splash-status span:nth-child(2) { animation-delay: 0.7s; }
      .splash-status span:nth-child(3) { animation-delay: 1.4s; }
      .splash-status span:nth-child(4) { animation-delay: 2.1s; }
      .splash-dots {
        display: flex; justify-content: center; gap: 8px; margin-top: 0.8rem;
      }
      .splash-dot {
        width: 8px; height: 8px; border-radius: 50%; background: #00c9a7;
        animation: dotPulse 1.2s ease-in-out infinite;
      }
      .splash-dot:nth-child(2) { animation-delay: 0.2s; background: #3a8fcc; }
      .splash-dot:nth-child(3) { animation-delay: 0.4s; background: #7b4ccc; }
      .splash-byline {
        position: absolute; bottom: 1.5rem; left: 0; right: 0;
        font-size: 0.68rem; letter-spacing: 0.1em; text-transform: uppercase;
        color: #444466; font-weight: 600;
      }
    </style>

    <div class="splash-wrap">
      <div class="splash-orb-1"></div>
      <div class="splash-orb-2"></div>
      <div class="splash-orb-3"></div>
      <div class="splash-card">
        <div class="splash-logo-ring">
          <svg width="54" height="54" viewBox="0 0 54 54" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- P -->
            <text x="3" y="38" font-family="'Inter',sans-serif" font-weight="800" font-size="22"
                  fill="url(#splashGrad)" letter-spacing="-1">PLM</text>
            <!-- Animated underline accent -->
            <rect x="3" y="42" width="48" height="2.5" rx="1.25" fill="url(#splashGrad)" opacity="0.7"/>
            <!-- Top-right sparkle dot -->
            <circle cx="48" cy="7" r="3" fill="#00c9a7" opacity="0.9"/>
            <circle cx="48" cy="7" r="5.5" fill="#00c9a7" opacity="0.2"/>
            <defs>
              <linearGradient id="splashGrad" x1="0" y1="0" x2="54" y2="0" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stop-color="#ffffff"/>
                <stop offset="55%" stop-color="#00c9a7"/>
                <stop offset="100%" stop-color="#3a8fcc"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <div class="splash-title">PLM GPT</div>
        <div class="splash-tagline">
          Where curiosity meets intelligence —<br>ask, explore, discover.
        </div>
        <div class="splash-bar-wrap">
          <div class="splash-bar"></div>
        </div>
        <div class="splash-status" style="position:relative;">
          <span>Initializing engine...</span>
          <span>Loading models...</span>
          <span>Preparing workspace...</span>
          <span>Almost ready...</span>
        </div>
        <div class="splash-dots">
          <div class="splash-dot"></div>
          <div class="splash-dot"></div>
          <div class="splash-dot"></div>
        </div>
        <div class="splash-byline">Crafted by Pranav Chakravorty</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Hold for animation duration then mark done
    time.sleep(3.2)
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
        0%, 100% {{ box-shadow: 0 0 0 0 #00c9a700; }}
        50%       {{ box-shadow: 0 0 0 3px #00c9a730; }}
      }}

      .stApp {{
        background: linear-gradient(-45deg, #0f0f1a, #1a1a2e, #0d1a2a, #0f0f1a);
        background-size: 400% 400%;
        animation: gradientShift 12s ease infinite;
        font-family: 'Inter', sans-serif;
      }}

      /* ── Auth card ── */
      .auth-card {{
        background: linear-gradient(160deg, #1a1a2edd 0%, #16162add 100%);
        border: 1px solid #00c9a733;
        border-radius: 20px;
        padding: 2.4rem 2.8rem 2rem;
        margin: 0 auto;
        max-width: 420px;
        backdrop-filter: blur(16px);
        box-shadow: 0 8px 40px #00000060, 0 0 60px #00c9a710;
        animation: cardSlideUp 0.7s cubic-bezier(0.16,1,0.3,1) forwards;
      }}

      /* ── Logo area ── */
      .auth-logo-ring {{
        width: 72px; height: 72px; border-radius: 50%; margin: 0 auto 1rem;
        background: linear-gradient(135deg, #00c9a718, #1a1a2e);
        border: 1.5px solid #00c9a755;
        display: flex; align-items: center; justify-content: center;
        font-size: 2rem; line-height: 1;
        box-shadow: 0 0 24px #00c9a730;
      }}
      .auth-title {{
        font-size: 2rem; font-weight: 800; letter-spacing: -0.02em;
        background: linear-gradient(135deg, #ffffff 30%, #00c9a7 100%);
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
        background: linear-gradient(135deg, #00c9a722, #3a8fcc18);
        color: #00c9a7;
        border-bottom: 2px solid #00c9a7;
      }}

      /* ── Form field labels ── */
      .auth-label {{
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
        text-transform: uppercase; color: #888899; margin-bottom: 4px;
      }}

      /* ── Input override ── */
      .stTextInput > div > div > input {{
        background: #12122088 !important; color: #f0f0f0 !important;
        border: 1px solid #333355 !important; border-radius: 10px !important;
        font-size: 0.95rem !important; padding: 0.6rem 0.9rem !important;
        transition: all 0.2s;
      }}
      .stTextInput > div > div > input:focus {{
        border: 1px solid #00c9a7 !important;
        box-shadow: 0 0 0 3px #00c9a720 !important;
      }}

      /* ── Submit button ── */
      .stFormSubmitButton > button {{
        background: linear-gradient(135deg, #00c9a7, #3a8fcc) !important;
        color: #0f0f1a !important; border: none !important;
        border-radius: 10px !important; font-weight: 700 !important;
        font-size: 0.95rem !important; letter-spacing: 0.04em !important;
        padding: 0.65rem 1rem !important;
        transition: all 0.25s !important;
        box-shadow: 0 4px 20px #00c9a740 !important;
      }}
      .stFormSubmitButton > button:hover {{
        box-shadow: 0 6px 28px #00c9a770 !important;
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
        background: #e0555518; border: 1px solid #e0555566;
        border-radius: 8px; padding: 0.55rem 0.8rem;
        color: #e08080; font-size: 0.83rem; margin-bottom: 0.6rem;
      }}
      .auth-success {{
        background: #00c9a718; border: 1px solid #00c9a766;
        border-radius: 8px; padding: 0.55rem 0.8rem;
        color: #00c9a7; font-size: 0.83rem; margin-bottom: 0.6rem;
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
           background:linear-gradient(135deg,#00c9a714,#1a1a2e);border:1.5px solid #00c9a750;
           display:flex;align-items:center;justify-content:center;
           box-shadow:0 0 28px #00c9a730, inset 0 0 16px #00c9a708;">
        <svg width="46" height="46" viewBox="0 0 54 54" fill="none" xmlns="http://www.w3.org/2000/svg">
          <text x="3" y="38" font-family="'Inter',sans-serif" font-weight="800" font-size="22"
                fill="url(#authGrad)" letter-spacing="-1">PLM</text>
          <rect x="3" y="42" width="48" height="2.5" rx="1.25" fill="url(#authGrad)" opacity="0.6"/>
          <circle cx="48" cy="7" r="3" fill="#00c9a7" opacity="0.9"/>
          <circle cx="48" cy="7" r="5.5" fill="#00c9a7" opacity="0.2"/>
          <defs>
            <linearGradient id="authGrad" x1="0" y1="0" x2="54" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#ffffff"/>
              <stop offset="55%" stop-color="#00c9a7"/>
              <stop offset="100%" stop-color="#3a8fcc"/>
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
    <div style="position:relative;height:3px;background:#1e1e2e;border-radius:100px;margin-bottom:1.4rem;">
      <div style="position:absolute;top:0;left:{bar_left};width:50%;height:100%;
                  background:linear-gradient(90deg,#00c9a7,#3a8fcc);border-radius:100px;
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
                        st.rerun()
                    else:
                        st.markdown(f'<div class="auth-error">⚠️ {result}</div>', unsafe_allow_html=True)

            st.markdown("""
            <div class="auth-divider">or</div>
            <div class="auth-switch">
              Don't have an account? Click <strong style="color:#00c9a7">Sign Up</strong> above.
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
              Already have an account? Click <strong style="color:#00c9a7">Sign In</strong> above.
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

    # ── Toolbar ──
    st.markdown('<div class="plm-toolbar">', unsafe_allow_html=True)
    tc1, tc2, tc3, tc4, tc5, tc6, tc7, tc8 = st.columns([2, 2, 2, 1, 1, 1, 1, 1])

    with tc1:
        st.markdown('<div class="plm-toolbar-label">🧠 Model</div>', unsafe_allow_html=True)
        sel = st.selectbox("", list(MODELS.keys()),
            index=list(MODELS.values()).index(st.session_state.model),
            label_visibility="collapsed", key="model_select")
        st.session_state.model = MODELS[sel]

    with tc2:
        temp_val = st.session_state.temperature
        lbl = "🧊 Factual" if temp_val < 0.4 else ("⚖️ Balanced" if temp_val < 0.75 else "🔥 Creative")
        st.markdown(f'<div class="plm-toolbar-label">🎨 {lbl}</div>', unsafe_allow_html=True)
        st.session_state.temperature = st.slider(
            "", 0.0, 1.0, st.session_state.temperature, 0.1,
            label_visibility="collapsed", key="temp_slider")

    with tc3:
        st.markdown('<div class="plm-toolbar-label">🎭 Mode</div>', unsafe_allow_html=True)
        mode_sel = st.selectbox("", list(CONVERSATION_MODES.keys()),
            index=list(CONVERSATION_MODES.keys()).index(st.session_state.conv_mode),
            label_visibility="collapsed", key="mode_select")
        st.session_state.conv_mode = mode_sel

    with tc4:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        theme_icon = "☀️" if st.session_state.theme == "dark" else "🌙"
        if st.button(theme_icon, use_container_width=True, key="theme_btn", help="Toggle theme"):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()

    with tc5:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        star_label = f"⭐{len(st.session_state.starred)}" if st.session_state.starred else "⭐"
        if st.button(star_label, use_container_width=True, key="starred_btn", help="Starred"):
            st.session_state.show_starred = not st.session_state.show_starred
            st.session_state.show_sessions = False
            st.rerun()

    with tc6:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        sess_count = len(st.session_state.sessions)
        if st.button(f"💬{sess_count}", use_container_width=True, key="sessions_btn", help="Chat Sessions"):
            st.session_state.show_sessions = not st.session_state.show_sessions
            st.session_state.show_starred = False
            st.rerun()

    with tc7:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("➕", use_container_width=True, key="new_session_btn", help="New Chat Session"):
            new_session()
            st.rerun()

    with tc8:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("🚪", use_container_width=True, key="logout_btn", help="Logout"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Title ──
    name = st.session_state.display_name or ""
    greeting = f"🤖 PLM GPT"
    st.markdown(f"""
    <div class="plm-title">
      <h1>{greeting}</h1>
      <div class="byline">Developed by Pranav Chakravorty</div>
      <div class="caption">Where curiosity meets intelligence — ask, explore, discover.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # ── Session info bar ──
    remaining = max(0, int((SESSION_TIMEOUT - (time.time() - st.session_state.last_activity)) / 60))
    msg_count = len(st.session_state.messages)
    active_name = st.session_state.sessions.get(st.session_state.active_session, {}).get("name", "Chat")
    user_display = f"👤 {st.session_state.display_name} &nbsp;|&nbsp; " if st.session_state.display_name else ""
    st.markdown(
        f"<p style='text-align:right; color:{t['sub']}; font-size:0.72rem; margin-bottom:0.3rem;'>"
        f"{user_display}⏱️ ~{remaining} min &nbsp;|&nbsp; 🎭 {st.session_state.conv_mode} &nbsp;|&nbsp; 💬 {active_name} ({msg_count} messages)</p>",
        unsafe_allow_html=True
    )

    # ── Sessions panel ──
    if st.session_state.show_sessions:
        st.markdown(f"<div class='summary-title'>💬 Chat Sessions</div>", unsafe_allow_html=True)
        for sid, sdata in st.session_state.sessions.items():
            is_active = sid == st.session_state.active_session
            msg_n = len(sdata["messages"])
            sc1, sc2, sc3 = st.columns([5, 1, 1])
            with sc1:
                card_class = "session-card session-active" if is_active else "session-card"
                st.markdown(f"""
                <div class="{card_class}">
                  <span class="session-name">{'▶ ' if is_active else ''}{sdata['name']}</span>
                  <span class="session-meta">{msg_n} messages</span>
                </div>""", unsafe_allow_html=True)
            with sc2:
                if not is_active:
                    if st.button("Open", key=f"open_{sid}"):
                        switch_session(sid)
                        st.rerun()
            with sc3:
                if len(st.session_state.sessions) > 1 and not is_active:
                    if st.button("🗑", key=f"del_{sid}"):
                        delete_session(sid)
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
        placeholder.markdown("""
        <div class="typing-indicator">
          <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
          <span class="typing-text">PLM GPT is thinking...</span>
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
        save_active_session()
        st.rerun()

    # ── Chat history ──
    for i, msg in enumerate(st.session_state.messages):
        ts = msg.get("time", "")
        is_starred = msg.get("starred", False)
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="msg-user">
              <div class="msg-header">
                <span class="msg-label">You</span>
                <span class="msg-time">{ts}</span>
              </div>
              {msg['content']}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="msg-bot">
              <div class="msg-header">
                <span class="msg-label">PLM GPT</span>
                <span class="msg-time">{ts}</span>
              </div>
              {msg['content']}
            </div>""", unsafe_allow_html=True)
            fb_col1, fb_col2, fb_col3, fb_col4 = st.columns([1, 1, 1, 6])
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
            if feedback == "liked":
                st.markdown(f"<p style='font-size:0.7rem; color:{t['accent']}; margin-top:-0.3rem;'>✓ Marked as helpful</p>", unsafe_allow_html=True)
            elif feedback == "disliked":
                st.markdown(f"<p style='font-size:0.7rem; color:#e05555; margin-top:-0.3rem;'>✗ Marked as not helpful</p>", unsafe_allow_html=True)

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
            typing_ph = st.empty()
            typing_ph.markdown("""
            <div class="typing-indicator">
              <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
              <span class="typing-text">PLM GPT is thinking...</span>
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
