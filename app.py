import time
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
#  SESSION STATE DEFAULTS
# ─────────────────────────────────────────
defaults = {
    "authenticated":  False,
    "messages":       [],
    "req_timestamps": [],
    "last_activity":  time.time(),
    "theme":          "dark",
    "model":          "llama-3.3-70b-versatile",
    "temperature":    0.7,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

SYSTEM_PROMPT = (
    "You are PLM GPT, a highly intelligent and professional AI assistant created by Pranav C. "
    "Answer clearly and helpfully. Format responses using markdown (bold, bullets, code blocks). "
    "Never reveal API keys, system details, or internal implementation."
)

# ─────────────────────────────────────────
#  THEME DEFINITIONS
# ─────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":           "#0f0f1a",
        "card":         "#1a1a2e",
        "input_bg":     "#1e1e2e",
        "text":         "#f0f0f0",
        "sub":          "#aaaaaa",
        "accent":       "#00c9a7",
        "border":       "#444444",
        "user_bg":      "#1e2a3a",
        "user_border":  "#3a8fcc",
        "btn_bg":       "#2a2a3d",
        "btn_text":     "#cccccc",
        "toolbar_bg":   "#16162a",
    },
    "light": {
        "bg":           "#f0f2f6",
        "card":         "#ffffff",
        "input_bg":     "#ffffff",
        "text":         "#1a1a2e",
        "sub":          "#666666",
        "accent":       "#00a388",
        "border":       "#cccccc",
        "user_bg":      "#ddeeff",
        "user_border":  "#3a8fcc",
        "btn_bg":       "#e0e0e0",
        "btn_text":     "#333333",
        "toolbar_bg":   "#e4e6f0",
    },
}

def apply_theme():
    t = THEMES[st.session_state.theme]
    st.markdown(f"""
    <style>
      .stApp {{ background-color:{t['bg']}; }}

      /* ── Toolbar bar ── */
      .plm-toolbar {{
        display:flex; align-items:center; justify-content:space-between;
        background:{t['toolbar_bg']}; border-radius:12px;
        padding:0.6rem 1rem; margin-bottom:0.8rem;
        border:1px solid {t['border']};
        flex-wrap:wrap; gap:0.4rem;
      }}
      .plm-toolbar-label {{
        color:{t['sub']}; font-size:0.78rem; font-weight:600;
        text-transform:uppercase; letter-spacing:0.05em;
        margin-bottom:2px;
      }}

      /* ── Title ── */
      .plm-title {{ text-align:center; padding:1.5rem 0 0.5rem; }}
      .plm-title h1 {{
        font-size:2.6rem; font-weight:800; color:{t['text']}; margin-bottom:0.1rem;
      }}
      .plm-title .byline {{ color:{t['sub']}; font-size:0.9rem; }}
      .plm-title .caption {{
        color:{t['sub']}; font-size:0.78rem; font-style:italic; opacity:0.65;
      }}

      /* ── Chat bubbles ── */
      .msg-user {{
        background:{t['user_bg']}; border-left:4px solid {t['user_border']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.45rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.6;
      }}
      .msg-bot {{
        background:{t['card']}; border-left:4px solid {t['accent']};
        border-radius:10px; padding:0.8rem 1.1rem; margin:0.45rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.7;
      }}
      .msg-label {{
        font-size:0.72rem; font-weight:700; margin-bottom:0.25rem;
        opacity:0.55; text-transform:uppercase; letter-spacing:0.06em;
      }}

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

      /* ── Slider ── */
      .stSlider > div {{ color:{t['text']}; }}

      /* ── Select box ── */
      .stSelectbox > div > div {{
        background-color:{t['input_bg']} !important;
        color:{t['text']} !important;
        border:1px solid {t['border']} !important;
        border-radius:10px !important;
      }}

      hr {{ border-color:{t['border']}; margin:0.8rem 0; }}
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

def get_response(query: str) -> str:
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        history = [{"role": "system", "content": SYSTEM_PROMPT}]
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
      <h1 style="font-size:2.8rem; font-weight:800; color:{t['text']};">🤖 PLM GPT</h1>
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
                st.rerun()
            else:
                st.error("Incorrect password.")

# ─────────────────────────────────────────
#  MAIN CHAT PAGE
# ─────────────────────────────────────────
def chat_page():
    apply_theme()
    t = THEMES[st.session_state.theme]

    # ── Top toolbar (all controls visible) ──
    st.markdown('<div class="plm-toolbar">', unsafe_allow_html=True)
    tc1, tc2, tc3, tc4, tc5 = st.columns([2, 2, 1, 1, 1])

    with tc1:
        st.markdown(f'<div class="plm-toolbar-label">🧠 Model</div>', unsafe_allow_html=True)
        sel = st.selectbox("", list(MODELS.keys()),
            index=list(MODELS.values()).index(st.session_state.model),
            label_visibility="collapsed", key="model_select")
        st.session_state.model = MODELS[sel]

    with tc2:
        temp_val = st.session_state.temperature
        label = "🧊 Factual" if temp_val < 0.4 else ("⚖️ Balanced" if temp_val < 0.75 else "🔥 Creative")
        st.markdown(f'<div class="plm-toolbar-label">🎨 Creativity — {label}</div>', unsafe_allow_html=True)
        st.session_state.temperature = st.slider(
            "", 0.0, 1.0, st.session_state.temperature, 0.1,
            label_visibility="collapsed", key="temp_slider")

    with tc3:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        theme_icon = "☀️ Light" if st.session_state.theme == "dark" else "🌙 Dark"
        if st.button(theme_icon, use_container_width=True, key="theme_btn"):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()

    with tc4:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("🗑️ New", use_container_width=True, key="new_chat_btn"):
            st.session_state.messages = []
            st.rerun()

    with tc5:
        st.markdown('<div class="plm-toolbar-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("🚪 Exit", use_container_width=True, key="logout_btn"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Header ──
    st.markdown(f"""
    <div class="plm-title">
      <h1>🤖 PLM GPT</h1>
      <div class="byline">A Bot by Pranav C</div>
      <div class="caption">Where curiosity meets intelligence — ask, explore, discover.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # ── Session timer ──
    remaining = max(0, int((SESSION_TIMEOUT - (time.time() - st.session_state.last_activity)) / 60))
    st.markdown(
        f"<p style='text-align:right; color:{t['sub']}; font-size:0.75rem; margin-bottom:0.5rem;'>"
        f"⏱️ Session expires in ~{remaining} min</p>",
        unsafe_allow_html=True
    )

    # ── Chat history ──
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="msg-user">
              <div class="msg-label">You</div>
              {msg['content']}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="msg-bot">
              <div class="msg-label">PLM GPT</div>
              {msg['content']}
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

    # ── Input form ──
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "", placeholder="Type your question here...",
            key="input", max_chars=3000,
        )
        submit = st.form_submit_button("Ask PLM GPT", use_container_width=True)

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
            st.warning("Please enter a question first.")
        elif is_rate_limited():
            st.error(f"Too many requests — max {MAX_REQUESTS} per minute. Please wait.")
        else:
            st.session_state.messages.append({"role": "user", "content": clean})
            with st.spinner("PLM GPT is thinking..."):
                reply = get_response(clean)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()

# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
if not st.session_state.authenticated:
    login_page()
else:
    chat_page()
