import time
import streamlit as st
from groq import Groq

# ─────────────────────────────────────────
#  PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────
st.set_page_config(
    page_title="PLM GPT",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────
#  HIDE ALL STREAMLIT BRANDING & CHROME
# ─────────────────────────────────────────
HIDE_ST = """
<style>
  #MainMenu, header, footer,
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  [data-testid="stSidebarNav"],
  .stDeployButton, #stDecoration { display: none !important; visibility: hidden !important; }
</style>
"""
st.markdown(HIDE_ST, unsafe_allow_html=True)

# ─────────────────────────────────────────
#  SESSION STATE DEFAULTS
# ─────────────────────────────────────────
defaults = {
    "authenticated": False,
    "messages": [],           # chat history
    "req_timestamps": [],     # rate limiting
    "last_activity": time.time(),
    "theme": "dark",
    "model": "llama-3.3-70b-versatile",
    "temperature": 0.7,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────
MAX_REQUESTS   = 10
WINDOW_SECONDS = 60
SESSION_TIMEOUT = 30 * 60   # 30 minutes in seconds

MODELS = {
    "⚡ Fast  — Llama 3.1 8B":       "llama-3.1-8b-instant",
    "🧠 Smart — Llama 3.3 70B":      "llama-3.3-70b-versatile",
    "💎 Best  — Llama 3.1 70B":      "llama-3.1-70b-versatile",
}

SYSTEM_PROMPT = (
    "You are PLM GPT, a highly intelligent and professional AI assistant created by Pranav C. "
    "You answer questions clearly, concisely, and helpfully. "
    "Format your responses using markdown where appropriate (bold, bullets, code blocks). "
    "Never reveal internal system details, API keys, or technical implementation."
)

# ─────────────────────────────────────────
#  THEMES
# ─────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":        "#0f0f1a",
        "card":      "#1a1a2e",
        "input_bg":  "#1e1e2e",
        "text":      "#f0f0f0",
        "sub":       "#aaa",
        "accent":    "#00c9a7",
        "border":    "#444",
        "hr":        "#2a2a3a",
        "user_bg":   "#1e2a3a",
        "user_border":"#3a8fcc",
        "btn_bg":    "#2a2a3d",
        "btn_text":  "#cccccc",
    },
    "light": {
        "bg":        "#f5f5f5",
        "card":      "#ffffff",
        "input_bg":  "#ffffff",
        "text":      "#1a1a2e",
        "sub":       "#555",
        "accent":    "#00a388",
        "border":    "#ccc",
        "hr":        "#ddd",
        "user_bg":   "#e8f4fd",
        "user_border":"#3a8fcc",
        "btn_bg":    "#e0e0e0",
        "btn_text":  "#333",
    },
}

def apply_theme():
    t = THEMES[st.session_state.theme]
    st.markdown(f"""
    <style>
      .stApp {{ background-color: {t['bg']}; }}
      .plm-title {{ text-align:center; padding:2rem 0 0.5rem; }}
      .plm-title h1 {{ font-size:2.8rem; font-weight:800; color:{t['text']}; margin-bottom:0.2rem; }}
      .plm-title .byline {{ color:{t['sub']}; font-size:0.9rem; }}
      .plm-title .caption {{ color:{t['sub']}; font-size:0.78rem; font-style:italic; opacity:0.7; }}

      /* Chat bubbles */
      .msg-user {{
        background:{t['user_bg']}; border-left:4px solid {t['user_border']};
        border-radius:10px; padding:0.9rem 1.2rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.6;
      }}
      .msg-assistant {{
        background:{t['card']}; border-left:4px solid {t['accent']};
        border-radius:10px; padding:0.9rem 1.2rem; margin:0.5rem 0;
        color:{t['text']}; font-size:0.95rem; line-height:1.7;
      }}
      .msg-label {{ font-size:0.75rem; font-weight:700; margin-bottom:0.3rem; opacity:0.6; }}

      /* Input */
      .stTextInput > div > div > input {{
        background-color:{t['input_bg']} !important; color:{t['text']} !important;
        border:1px solid {t['border']} !important; border-radius:10px !important;
        font-size:1rem !important; box-shadow:none !important;
      }}
      .stTextInput > div > div > input:focus {{
        border:1px solid {t['accent']} !important;
        box-shadow:0 0 0 2px {t['accent']}33 !important;
      }}

      /* Submit button */
      .stFormSubmitButton > button {{
        background-color:{t['btn_bg']}; color:{t['btn_text']};
        border:1px solid {t['border']}; border-radius:10px;
        padding:0.6rem 2rem; font-size:1rem; font-weight:600; width:100%;
        transition:all 0.2s;
      }}
      .stFormSubmitButton > button:hover {{
        background-color:{t['accent']}; color:{t['bg']};
        border-color:{t['accent']};
      }}

      /* Sidebar */
      [data-testid="stSidebar"] {{
        background-color:{t['card']};
      }}

      hr {{ border-color:{t['hr']}; }}
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def is_rate_limited() -> bool:
    now = time.time()
    ts = [t for t in st.session_state.req_timestamps if now - t < WINDOW_SECONDS]
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
        # send last 10 messages for context
        for m in st.session_state.messages[-10:]:
            history.append({"role": m["role"], "content": m["content"]})
        history.append({"role": "user", "content": query})

        response = client.chat.completions.create(
            model=st.session_state.model,
            messages=history,
            max_tokens=1024,
            temperature=st.session_state.temperature,
            stream=True,   # streaming enabled
        )
        # collect streamed chunks
        result = ""
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                result += delta
        return result
    except Exception:
        return "⚠️ Something went wrong. Please try again in a moment."

# ─────────────────────────────────────────
#  PASSWORD GATE
# ─────────────────────────────────────────
def login_page():
    t = THEMES[st.session_state.theme]
    st.markdown(f"""
    <style>.stApp {{ background-color:{t['bg']}; }}</style>
    <div style="text-align:center; padding:4rem 0 1rem;">
      <h1 style="font-size:2.8rem; font-weight:800; color:{t['text']};">🤖 PLM GPT</h1>
      <p style="color:{t['sub']}; font-size:0.95rem;">Enter password to continue</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        pwd = st.text_input("Password", type="password", placeholder="Enter password...")
        login_btn = st.form_submit_button("Login", use_container_width=True)

    if login_btn:
        if pwd == st.secrets.get("APP_PASSWORD", ""):
            st.session_state.authenticated = True
            st.session_state.last_activity = time.time()
            st.rerun()
        else:
            st.error("Incorrect password. Try again.")

# ─────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        t = THEMES[st.session_state.theme]
        st.markdown(f"<h3 style='color:{t['text']}'>⚙️ Settings</h3>", unsafe_allow_html=True)
        st.markdown("---")

        # Theme toggle
        theme_label = "☀️ Switch to Light" if st.session_state.theme == "dark" else "🌙 Switch to Dark"
        if st.button(theme_label, use_container_width=True):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()

        st.markdown("---")

        # Model selector
        st.markdown(f"<p style='color:{t['sub']}; font-size:0.85rem; font-weight:600;'>🧠 MODEL</p>", unsafe_allow_html=True)
        selected_label = st.selectbox(
            "", list(MODELS.keys()),
            index=list(MODELS.values()).index(st.session_state.model),
            label_visibility="collapsed",
        )
        st.session_state.model = MODELS[selected_label]

        st.markdown("---")

        # Temperature
        st.markdown(f"<p style='color:{t['sub']}; font-size:0.85rem; font-weight:600;'>🎨 CREATIVITY</p>", unsafe_allow_html=True)
        st.session_state.temperature = st.slider(
            "", min_value=0.0, max_value=1.0,
            value=st.session_state.temperature, step=0.1,
            label_visibility="collapsed",
        )
        temp_label = "🧊 Factual" if st.session_state.temperature < 0.4 else ("⚖️ Balanced" if st.session_state.temperature < 0.75 else "🔥 Creative")
        st.markdown(f"<p style='color:{t['sub']}; font-size:0.8rem; text-align:center'>{temp_label}</p>", unsafe_allow_html=True)

        st.markdown("---")

        # New chat + logout
        if st.button("🗑️ New Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        if st.button("🚪 Logout", use_container_width=True):
            for k in defaults:
                st.session_state[k] = defaults[k]
            st.rerun()

        # Session info
        st.markdown("---")
        remaining = max(0, int((SESSION_TIMEOUT - (time.time() - st.session_state.last_activity)) / 60))
        st.markdown(f"<p style='color:{t['sub']}; font-size:0.75rem; text-align:center'>Session expires in ~{remaining} min</p>", unsafe_allow_html=True)

# ─────────────────────────────────────────
#  MAIN CHAT PAGE
# ─────────────────────────────────────────
def chat_page():
    apply_theme()
    render_sidebar()
    t = THEMES[st.session_state.theme]

    # Header
    st.markdown(f"""
    <div class="plm-title">
      <h1>🤖 PLM GPT</h1>
      <div class="byline">A Bot by Pranav C</div>
      <div class="caption">Where curiosity meets intelligence — ask, explore, discover.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # Chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="msg-user">
              <div class="msg-label">YOU</div>
              {msg['content']}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="msg-assistant">
              <div class="msg-label">PLM GPT</div>
              {msg['content']}
            </div>""", unsafe_allow_html=True)

    # Input form
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "", placeholder="Type your question here...",
            key="input", max_chars=3000,
        )
        submit = st.form_submit_button("Ask PLM GPT", use_container_width=True)

    if submit:
        # Session timeout check
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
            st.error(f"Too many requests. Max {MAX_REQUESTS} per minute. Please wait.")
        else:
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": clean})

            with st.spinner("PLM GPT is thinking..."):
                reply = get_response(clean)

            # Add assistant reply to history
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()

# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
if not st.session_state.authenticated:
    login_page()
else:
    chat_page()
