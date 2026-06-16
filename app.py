import time
import streamlit as st
from groq import Groq

# ── Groq client (key lives only on the server, never sent to browser) ──
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ── Rate limiting: max 10 requests per session per minute ──
MAX_REQUESTS = 10
WINDOW_SECONDS = 60

def is_rate_limited() -> bool:
    now = time.time()
    timestamps = st.session_state.get("req_timestamps", [])
    # keep only timestamps within the window
    timestamps = [t for t in timestamps if now - t < WINDOW_SECONDS]
    if len(timestamps) >= MAX_REQUESTS:
        return True
    timestamps.append(now)
    st.session_state["req_timestamps"] = timestamps
    return False

# ── Input sanitization ──
def sanitize(text: str) -> str:
    return text.strip()[:2000]  # trim whitespace, cap at 2000 chars

# ── Core API call with error handling ──
def get_response(query: str) -> str:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": query}],
            max_tokens=1024,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception:
        return "Something went wrong. Please try again in a moment."

# ── Page config ──
st.set_page_config(
    page_title="PLM GPT",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Hide all Streamlit branding, menu, toolbar, and dev info ──
st.markdown("""
    <style>
        /* Hide Streamlit chrome */
        #MainMenu { visibility: hidden; }
        header { visibility: hidden; }
        footer { visibility: hidden; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="stDecoration"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
        [data-testid="stSidebarNav"] { display: none !important; }
        .stDeployButton { display: none !important; }
        #stDecoration { display: none !important; }

        /* Page background */
        .stApp { background-color: #0f0f1a; }

        /* Title area */
        .title-container { text-align: center; padding: 2.5rem 0 1.2rem 0; }
        .title-container h1 {
            font-size: 3rem; font-weight: 800; color: #f0f0f0; margin-bottom: 0.2rem;
        }
        .title-container .byline {
            color: #aaa; font-size: 0.95rem; font-weight: 500;
        }
        .title-container .caption {
            color: #555; font-size: 0.82rem; font-style: italic; margin-top: 0.3rem;
        }

        /* Response box */
        .response-box {
            background-color: #1a1a2e;
            border-left: 4px solid #00c9a7;
            border-radius: 10px;
            padding: 1.2rem 1.5rem;
            margin-top: 1.5rem;
            color: #e0e0e0;
            font-size: 1rem;
            line-height: 1.7;
            white-space: pre-wrap;
        }

        /* Input field */
        .stTextInput > div > div > input {
            background-color: #1e1e2e !important;
            color: #ffffff !important;
            border: 1px solid #444 !important;
            border-radius: 10px !important;
            font-size: 1rem !important;
            box-shadow: none !important;
        }
        .stTextInput > div > div > input:hover {
            border: 1px solid #666 !important;
        }
        .stTextInput > div > div > input:focus {
            border: 1px solid #00c9a7 !important;
            box-shadow: 0 0 0 2px rgba(0,201,167,0.15) !important;
        }

        /* Submit button */
        .stFormSubmitButton > button {
            background-color: #2a2a3d;
            color: #cccccc;
            border: 1px solid #444;
            border-radius: 10px;
            padding: 0.6rem 2rem;
            font-size: 1rem;
            font-weight: 600;
            width: 100%;
            transition: background-color 0.2s, color 0.2s, border-color 0.2s;
        }
        .stFormSubmitButton > button:hover {
            background-color: #00c9a7;
            color: #0f0f1a;
            border-color: #00c9a7;
        }

        /* Divider */
        hr { border-color: #2a2a3a; }
    </style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("""
    <div class="title-container">
        <h1>🤖 PLM GPT</h1>
        <div class="byline">A Bot by Pranav C</div>
        <div class="caption">Where curiosity meets intelligence — ask, explore, discover.</div>
    </div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── Input form ──
with st.form(key="query_form", clear_on_submit=True):
    user_input = st.text_input(
        "",
        placeholder="Type your question here...",
        key="input",
        max_chars=2000,
    )
    submit = st.form_submit_button("Ask PLM GPT")

# ── Handle submission ──
if submit:
    clean_input = sanitize(user_input)
    if not clean_input:
        st.warning("Please enter a question first.")
    elif is_rate_limited():
        st.error("Too many requests. Please wait a moment before asking again.")
    else:
        with st.spinner("Thinking..."):
            response = get_response(clean_input)
        st.markdown(
            f'<div class="response-box">{response}</div>',
            unsafe_allow_html=True,
        )
