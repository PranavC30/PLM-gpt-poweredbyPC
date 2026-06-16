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
#  HIDE ALL STREAMLIT BRANDING
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
        "Respond formally, precisely, and concisely. Use structured formatting with markdown."
    ),
    "👨‍💻 Code Helper": (
        "You are PLM GPT, an expert programming assistant created by Pranav Chakravorty. "
        "Focus on clean, efficient code. Always provide code in proper markdown code blocks with language specified. "
        "Explain your code clearly."
    ),
    "✍️ Creative Writer": (
        "You are PLM GPT, a creative writing assistant created by Pranav Chakravorty. "
        "Be imaginative, expressive, and engaging. Use vivid language and creative structure."
    ),
    "📚 Study Buddy": (
        "You are PLM GPT, a friendly study assistant created by Pranav Chakravorty. "
        "Explain concepts simply and clearly, use examples and analogies. Break down complex topics step by step."
    ),
}

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
    },
}

# ─────────────────────────────────────────
#  APPLY THEME
# ─────────────────────────────────────────
def apply_theme():
    t = THEMES[st.session_state.theme]
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;1,500&family=Inter:wght@400;500;600;700;800&display=swap');

      .stApp {{ background-color:{t['bg']}; font-family:'Inter', sans-serif; }}

      /* ── Toolbar ── */
      .plm-toolbar {{
        display:flex; align-items:center; justify-content:space-between;
        background:{t['toolbar_bg']}; border-radius:12px;
        padding:0.6rem 1rem; margin-bottom:0.8rem;
        border:1px solid {t['border']}; flex-wrap:wrap; gap:0.4rem;
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
      .plm-title .caption {{
        color:{t['sub']}; font-size:0.76rem; font-style:italic; opacity:0.6;
      }}

      /* ── Welcome card ── */
      .welcome-card {{
        background: linear-gradient(135deg, {t['welcome_bg']} 0%, {t['card']} 100%);
        border: 1px solid {t['accent']}55;
        border-radius: 16px;
        padding: 2rem 2.2rem;
        margin: 1rem 0 1.5rem 0;
        text-align: center;
        box-shadow: 0 4px 24px {t['accent']}18;
      }}
      .welcome-greeting {{
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.9rem;
        font-weight: 600;
        color: {t['accent']};
        letter-spacing: 0.01em;
        margin-bottom: 0.6rem;
        line-height: 1.3;
      }}
      .welcome-sub {{
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1rem;
        font-style: italic;
        color: {t['text']};
        opacity: 0.85;
        line-height: 1.7;
        margin-bottom: 1rem;
      }}
      .welcome-dev {{
        font-family: 'Inter', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: {t['sub']};
        opacity: 0.7;
        margin-top: 0.8rem;
      }}
      .welcome-dot {{
        display: inline-block;
        width: 6px; height: 6px;
        background: {t['accent']};
        border-radius: 50%;
        margin: 0 6px;
        vertical-align: middle;
      }}

      /* ── Chat bubbles ── */
      .msg-user {{
        background:{t['user_bg']}; border-left:4px solid {t['user_border']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.6;
      }}
      .msg-bot {{
        background:{t['card']}; border-left:4px solid {t['accent']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.7;
      }}
      .msg-header {{
        display:flex; justify-content:space-between; align-items:center;
        margin-bottom:0.3rem;
      }}
      .msg-label {{
        font-size:0.72rem; font-weight:700;
        opacity:0.55; text-transform:uppercase; letter-spacing:0.07em;
      }}
      .msg-time {{
        font-size:0.68rem; color:{t['sub']}; opacity:0.6;
      }}

      /* ── Typing animation ── */
      .typing-indicator {{
        display:flex; align-items:center; gap:5px;
        padding:0.8rem 1.1rem;
        background:{t['card']}; border-left:4px solid {t['accent']};
        border-radius:10px; margin:0.5rem 0;
      }}
      .typing-dot {{
        width:8px; height:8px; border-radius:50%;
        background:{t['accent']};
        animation: typingBounce 1.2s infinite ease-in-out;
      }}
      .typing-dot:nth-child(2) {{ animation-delay:0.2s; }}
      .typing-dot:nth-child(3) {{ animation-delay:0.4s; }}
      @keyframes typingBounce {{
        0%,60%,100% {{ transform:translateY(0); opacity:0.4; }}
        30% {{ transform:translateY(-6px); opacity:1; }}
      }}
      .typing-text {{
        font-size:0.8rem; color:{t['sub']}; margin-left:4px; font-style:italic;
      }}

      /* ── Char counter ── */
      .char-counter {{
        text-align:right; font-size:0.72rem;
        color:{t['sub']}; margin-top:-0.6rem; margin-bottom:0.5rem; opacity:0.7;
      }}
      .char-warn {{ color:#f0a500 !important; opacity:1 !important; }}
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
        padding:0.5rem 1.2rem; font-size:0.9rem; font-weight:600;
        transition:all 0.2s;
      }}
      .stFormSubmitButton > button:hover, .stButton > button:hover {{
        background-color:{t['accent']}; color:{t['bg']};
        border-color:{t['accent']};
      }}

      /* ── Selectbox ── */
      .stSelectbox > div > div {{
        background-color:{t['input_bg']} !important; color:{t['text']} !important;
        border:1px solid {t['border']} !important; border-radius:10px !important;
      }}

      hr {{ border-color:{t['border']}; margin:0.7rem 0; }}
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

def get_response(query: str) -> str:
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        system_prompt = CONVERSATION_MODES[st.session_state.conv_mode]
        history = [{"role": "system", "content": system_prompt}]
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
        result = ""
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                result += delta
        return result
    except Exception:
        return "⚠️ Something went wrong. Please try again in a moment."

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
      <p style="color:{t['sub']}; font-size:0.95rem; margin-top:0.5rem;">
        Enter password to continue
      </p>
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
      <div style="margin: 0.8rem 0; color:{t['accent']}; font-size:1.4rem;">✦ &nbsp; ✦ &nbsp; ✦</div>
      <div class="welcome-sub" style="font-size:0.88rem; opacity:0.75;">
        Select a conversation mode from the toolbar above,<br>
        then type your first message to begin.
      </div>
      <div class="welcome-dev">
        <span class="welcome-dot"></span>
        Crafted with precision by &nbsp;<strong style="color:{t['text']}; letter-spacing:0.05em;">Pranav Chakravorty</strong>
        <span class="welcome-dot"></span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
#  CHAT PAGE
# ─────────────────────────────────────────
def chat_page():
    apply_theme()
    t = THEMES[st.session_state.theme]

    # ── Toolbar ──
    st.markdown('<div class="plm-toolbar">', unsafe_allow_html=True)
    tc1, tc2, tc3, tc4, tc5, tc6 = st.columns([2, 2, 2, 1, 1, 1])

    with tc1:
        st.markdown('<div class="plm-toolbar-label">🧠 Model</div>', unsafe_allow_html=True)
        sel = st.selectbox("", list(MODELS.keys()),
            index=list(MODELS.values()).index(st.session_state.model),
            label_visibility="collapsed", key="model_select")
        st.session_state.model = MODELS[sel]

    with tc2:
        temp_val = st.session_state.temperature
        lbl = "🧊 Factual" if temp_val < 0.4 else ("⚖️ Balanced" if temp_val < 0.75 else "🔥 Creative")
        st.markdown(f'<div class="plm-toolbar-label">🎨 Creativity — {lbl}</div>', unsafe_allow_html=True)
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
        if st.button(theme_icon, use_container_width=True, key="theme_btn"):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()

    with tc5:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("🗑️", use_container_width=True, key="new_chat_btn", help="New Chat"):
            st.session_state.messages = []
            st.session_state.welcome_shown = False
            st.rerun()

    with tc6:
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

    # ── Session timer ──
    remaining = max(0, int((SESSION_TIMEOUT - (time.time() - st.session_state.last_activity)) / 60))
    st.markdown(
        f"<p style='text-align:right; color:{t['sub']}; font-size:0.72rem; margin-bottom:0.3rem;'>"
        f"⏱️ Session expires in ~{remaining} min &nbsp;|&nbsp; 🎭 {st.session_state.conv_mode}</p>",
        unsafe_allow_html=True
    )

    # ── Welcome card (shown when no messages) ──
    if not st.session_state.messages:
        render_welcome()

    # ── Chat history ──
    for msg in st.session_state.messages:
        ts = msg.get("time", "")
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

    st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

    # ── Input form ──
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "", placeholder="Type your message here...",
            key="input", max_chars=3000,
        )
        submit = st.form_submit_button("Ask PLM GPT", use_container_width=True)

    # ── Character counter ──
    char_count = len(user_input) if user_input else 0
    max_chars  = 3000
    words      = len(user_input.split()) if user_input and user_input.strip() else 0
    warn_class = "char-danger" if char_count > 2700 else ("char-warn" if char_count > 2000 else "")
    st.markdown(
        f"<div class='char-counter {warn_class}'>"
        f"{words} words &nbsp;·&nbsp; {char_count} / {max_chars} characters"
        f"</div>",
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
            # Save user message with timestamp
            st.session_state.messages.append({
                "role":    "user",
                "content": clean,
                "time":    now_str(),
            })

            # Show typing animation while fetching
            typing_placeholder = st.empty()
            typing_placeholder.markdown(f"""
            <div class="typing-indicator">
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
              <span class="typing-text">PLM GPT is thinking...</span>
            </div>""", unsafe_allow_html=True)

            reply = get_response(clean)
            typing_placeholder.empty()

            # Save bot reply with timestamp
            st.session_state.messages.append({
                "role":    "assistant",
                "content": reply,
                "time":    now_str(),
            })
            st.rerun()

# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
if not st.session_state.authenticated:
    login_page()
else:
    chat_page()
