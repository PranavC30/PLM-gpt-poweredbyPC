import time
import datetime
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
#  SESSION STATE DEFAULTS
# ─────────────────────────────────────────
defaults = {
    "authenticated":   False,
    "messages":        [],
    "req_timestamps":  [],
    "last_activity":   time.time(),
    "theme":           "dark",
    "model":           "llama-3.3-70b-versatile",
    "temperature":     0.7,
    "conv_mode":       "💼 Professional",
    "welcome_shown":   False,
    "starred":         [],       # pinned/starred messages
    "show_starred":    False,    # toggle starred panel
    "voice_text":      "",       # voice input result
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

def apply_theme():
    t = THEMES[st.session_state.theme]
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;1,500&family=Inter:wght@400;500;600;700;800&display=swap');

      /* ── Animated gradient background ── */
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

      /* ── Toolbar ── */
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

      /* ── Title ── */
      .plm-title {{ text-align:center; padding:1.2rem 0 0.4rem; }}
      .plm-title h1 {{
        font-size:2.6rem; font-weight:800; color:{t['text']};
        font-family:'Inter', sans-serif; margin-bottom:0.1rem;
      }}
      .plm-title .byline {{ color:{t['sub']}; font-size:0.88rem; font-weight:500; }}
      .plm-title .caption {{ color:{t['sub']}; font-size:0.76rem; font-style:italic; opacity:0.6; }}

      /* ── Welcome card ── */
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

      /* ── Prompt suggestion cards ── */
      .prompt-grid {{
        display: grid; grid-template-columns: 1fr 1fr;
        gap: 0.5rem; margin: 0.8rem 0 1rem 0;
      }}
      .prompt-card {{
        background: {t['card']}; border: 1px solid {t['border']};
        border-radius: 10px; padding: 0.65rem 0.9rem;
        font-size: 0.82rem; color: {t['text']}; cursor: pointer;
        transition: all 0.2s; line-height: 1.4;
        border-left: 3px solid {t['accent']};
      }}
      .prompt-card:hover {{
        border-color: {t['accent']}; background: {t['user_bg']};
        transform: translateY(-1px);
      }}

      /* ── Chat bubbles ── */
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

      /* ── Feedback buttons ── */
      .feedback-row {{
        display:flex; gap:0.4rem; margin-top:0.5rem; align-items:center;
      }}
      .feedback-btn {{
        background:transparent; border:1px solid {t['border']};
        border-radius:6px; padding:2px 8px; font-size:0.78rem;
        cursor:pointer; color:{t['sub']}; transition:all 0.15s;
      }}
      .feedback-btn:hover {{ background:{t['accent']}22; border-color:{t['accent']}; }}
      .feedback-liked {{ background:{t['accent']}22 !important; border-color:{t['accent']} !important; color:{t['accent']} !important; }}
      .feedback-disliked {{ background:#e0555522 !important; border-color:#e05555 !important; color:#e05555 !important; }}

      /* ── Starred panel ── */
      .starred-card {{
        background:{t['card']}; border:1px solid {t['accent']}66;
        border-radius:10px; padding:0.8rem 1rem; margin:0.4rem 0;
        color:{t['text']}; font-size:0.88rem; line-height:1.6;
        border-left:3px solid {t['accent']};
      }}

      /* ── Typing animation ── */
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

      /* ── Streaming box ── */
      .stream-box {{
        background:{t['card']}; border-left:4px solid {t['accent']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.7; min-height:2rem;
        white-space: pre-wrap;
      }}

      /* ── Char counter ── */
      .char-counter {{
        text-align:right; font-size:0.72rem; color:{t['sub']};
        margin-top:-0.5rem; margin-bottom:0.4rem; opacity:0.7;
      }}
      .char-warn  {{ color:#f0a500 !important; opacity:1 !important; }}
      .char-danger {{ color:#e05555 !important; opacity:1 !important; }}

      /* ── Input ── */
      .stTextInput > div > div > input {{
        background-color:{t['input_bg']} !important; color:{t['text']} !important;
        border:1px solid {t['border']} !important; border-radius:10px !important;
        font-size:1rem !important; box-shadow:none !important;
      }}
      .stTextInput > div > div > input:focus {{
        border:1px solid {t['accent']} !important;
        box-shadow:0 0 0 2px {t['accent']}33 !important;
      }}

      /* ── Buttons ── */
      .stFormSubmitButton > button, .stButton > button {{
        background-color:{t['btn_bg']}; color:{t['btn_text']};
        border:1px solid {t['border']}; border-radius:10px;
        padding:0.5rem 1.2rem; font-size:0.9rem; font-weight:600; transition:all 0.2s;
      }}
      .stFormSubmitButton > button:hover, .stButton > button:hover {{
        background-color:{t['accent']}; color:{t['bg']}; border-color:{t['accent']};
      }}

      /* ── Selectbox ── */
      .stSelectbox > div > div {{
        background-color:{t['input_bg']} !important; color:{t['text']} !important;
        border:1px solid {t['border']} !important; border-radius:10px !important;
      }}

      /* ── Summary box ── */
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

      hr {{ border-color:{t['border']}; margin:0.7rem 0; }}
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
#  VOICE INPUT (Web Speech API via JS)
# ─────────────────────────────────────────
VOICE_JS = """
<script>
function startVoice() {
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert("Voice input not supported in this browser. Please use Chrome.");
    return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new SR();
  rec.lang = 'en-US';
  rec.interimResults = false;
  rec.maxAlternatives = 1;

  const btn = document.getElementById('voice-btn');
  btn.innerHTML = '🔴 Listening...';
  btn.style.borderColor = '#e05555';
  btn.style.color = '#e05555';

  rec.onresult = function(e) {
    const txt = e.results[0][0].transcript;
    // write into the Streamlit text input
    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
    if (inputs.length > 0) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      nativeInputValueSetter.call(inputs[inputs.length-1], txt);
      inputs[inputs.length-1].dispatchEvent(new Event('input', { bubbles: true }));
    }
    btn.innerHTML = '🎙️ Voice';
    btn.style.borderColor = '';
    btn.style.color = '';
  };
  rec.onerror = function() {
    btn.innerHTML = '🎙️ Voice';
    btn.style.borderColor = '';
    btn.style.color = '';
  };
  rec.onend = function() {
    btn.innerHTML = '🎙️ Voice';
    btn.style.borderColor = '';
    btn.style.color = '';
  };
  rec.start();
}
</script>
<button id="voice-btn" onclick="startVoice()"
  style="background:transparent; border:1px solid #444; border-radius:8px;
         padding:6px 14px; font-size:0.88rem; font-weight:600; cursor:pointer;
         color:#aaa; transition:all 0.2s; margin-bottom:0.5rem;">
  🎙️ Voice
</button>
"""

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
    """Summarize the full conversation."""
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
#  LOGIN PAGE
# ─────────────────────────────────────────
def login_page():
    t = THEMES[st.session_state.theme]
    st.markdown(f"<style>.stApp{{background-color:{t['bg']};}}</style>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="text-align:center; padding:4rem 0 2rem;">
      <h1 style="font-size:2.8rem; font-weight:800; color:{t['text']}; font-family:'Inter',sans-serif;">
        🤖 PLM GPT
      </h1>
      <p style="color:{t['sub']}; font-size:0.95rem; margin-top:0.5rem;">Enter password to continue</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            pwd = st.text_input("Password", type="password", placeholder="Enter password...")
            btn = st.form_submit_button("🔓 Login", use_container_width=True)
        if btn:
            if pwd == st.secrets.get("APP_PASSWORD", ""):
                st.session_state.authenticated = True
                st.session_state.last_activity = time.time()
                st.session_state.welcome_shown = False
                st.rerun()
            else:
                st.error("Incorrect password.")

# ─────────────────────────────────────────
#  WELCOME CARD
# ─────────────────────────────────────────
def render_welcome():
    t = THEMES[st.session_state.theme]
    st.markdown(f"""
    <div class="welcome-card">
      <div class="welcome-greeting">Welcome to PLM GPT</div>
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

    # ── Prompt suggestion cards ──
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

    # ── Toolbar ──
    st.markdown('<div class="plm-toolbar">', unsafe_allow_html=True)
    tc1, tc2, tc3, tc4, tc5, tc6, tc7 = st.columns([2, 2, 2, 1, 1, 1, 1])

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
        star_label = f"⭐ {len(st.session_state.starred)}" if st.session_state.starred else "⭐"
        if st.button(star_label, use_container_width=True, key="starred_btn", help="Starred messages"):
            st.session_state.show_starred = not st.session_state.show_starred
            st.rerun()

    with tc6:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("🗑️", use_container_width=True, key="new_chat_btn", help="New Chat"):
            st.session_state.messages = []
            st.session_state.starred = []
            st.session_state.show_starred = False
            st.rerun()

    with tc7:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("🚪", use_container_width=True, key="logout_btn", help="Logout"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Title ──
    st.markdown("""
    <div class="plm-title">
      <h1>🤖 PLM GPT</h1>
      <div class="byline">Developed by Pranav Chakravorty</div>
      <div class="caption">Where curiosity meets intelligence — ask, explore, discover.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # ── Session info bar ──
    remaining = max(0, int((SESSION_TIMEOUT - (time.time() - st.session_state.last_activity)) / 60))
    msg_count = len(st.session_state.messages)
    st.markdown(
        f"<p style='text-align:right; color:{t['sub']}; font-size:0.72rem; margin-bottom:0.3rem;'>"
        f"⏱️ ~{remaining} min &nbsp;|&nbsp; 🎭 {st.session_state.conv_mode} &nbsp;|&nbsp; 💬 {msg_count} messages</p>",
        unsafe_allow_html=True
    )

    # ── Starred messages panel ──
    if st.session_state.show_starred:
        if st.session_state.starred:
            st.markdown(f"<div class='summary-title' style='margin-bottom:0.3rem;'>⭐ Starred Messages</div>", unsafe_allow_html=True)
            for s in st.session_state.starred:
                st.markdown(f"<div class='starred-card'>{s}</div>", unsafe_allow_html=True)
        else:
            st.info("No starred messages yet. Click ⭐ on any response to save it.")
        st.markdown("---")

    # ── Smart summary button (show if 6+ messages) ──
    if len(st.session_state.messages) >= 6:
        if st.button("📋 Summarize this conversation", use_container_width=False, key="summarize_btn"):
            with st.spinner("Generating summary..."):
                summary = get_summary()
            st.markdown(f"""
            <div class="summary-box">
              <div class="summary-title">📋 Conversation Summary</div>
              {summary}
            </div>""", unsafe_allow_html=True)

    # ── Welcome / Prompt suggestions ──
    if not st.session_state.messages:
        render_welcome()

    # ── Handle pending query from prompt suggestion ──
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

            # ── Feedback + Star row ──
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
                    st.rerun()

            if feedback == "liked":
                st.markdown(f"<p style='font-size:0.7rem; color:{t['accent']}; margin-top:-0.3rem;'>✓ Marked as helpful</p>", unsafe_allow_html=True)
            elif feedback == "disliked":
                st.markdown(f"<p style='font-size:0.7rem; color:#e05555; margin-top:-0.3rem;'>✗ Marked as not helpful</p>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

    # ── Voice input button ──
    st.markdown(VOICE_JS, unsafe_allow_html=True)

    # ── Input form ──
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "", placeholder="Type your message or use 🎙️ Voice above...",
            key="input", max_chars=3000,
        )
        submit = st.form_submit_button("Ask PLM GPT", use_container_width=True)

    # ── Character counter ──
    char_count = len(user_input) if user_input else 0
    words      = len(user_input.split()) if user_input and user_input.strip() else 0
    warn_class = "char-danger" if char_count > 2700 else ("char-warn" if char_count > 2000 else "")
    st.markdown(
        f"<div class='char-counter {warn_class}'>{words} words &nbsp;·&nbsp; {char_count} / 3000 chars</div>",
        unsafe_allow_html=True
    )

    # ── Handle submit ──
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

            # Typing indicator
            typing_ph = st.empty()
            typing_ph.markdown("""
            <div class="typing-indicator">
              <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
              <span class="typing-text">PLM GPT is thinking...</span>
            </div>""", unsafe_allow_html=True)

            # Word-by-word streaming
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
            st.rerun()

# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
if not st.session_state.authenticated:
    login_page()
else:
    chat_page()
