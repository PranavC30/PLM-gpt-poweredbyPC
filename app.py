import streamlit as st
from groq import Groq

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def my_output(query):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": query}]
    )
    return response.choices[0].message.content

st.set_page_config(page_title="PLM Bot", page_icon="🤖", layout="centered")

st.markdown("""
    <style>
        .title-container { text-align: center; padding: 2rem 0 1rem 0; }
        .title-container h1 {
            font-size: 3rem; font-weight: 800;
            color: #f0f0f0;
        }
        .title-container .byline { color: #aaa; font-size: 0.95rem; font-weight: 500; }
        .title-container .caption { color: #666; font-size: 0.82rem; font-style: italic; margin-top: 0.2rem; }
        .response-box {
            background-color: #1a1a2e; border-left: 4px solid #00c9a7;
            border-radius: 10px; padding: 1.2rem 1.5rem;
            margin-top: 1.5rem; color: #e0e0e0; font-size: 1rem; line-height: 1.7;
        }
        .stTextInput > div > div > input {
            background-color: #1e1e2e !important; color: #ffffff !important;
            border: 1px solid #444 !important; border-radius: 10px !important;
            font-size: 1rem !important; box-shadow: none !important;
        }
        .stTextInput > div > div > input:hover {
            border: 1px solid #666 !important; box-shadow: none !important;
        }
        .stTextInput > div > div > input:focus {
            border: 1px solid #888 !important;
            box-shadow: 0 0 0 2px rgba(150,150,150,0.15) !important;
        }
        .stFormSubmitButton > button {
            background-color: #2a2a3d;
            color: #cccccc; border: 1px solid #444; border-radius: 10px;
            padding: 0.6rem 2rem; font-size: 1rem; font-weight: 600; width: 100%;
            transition: background-color 0.2s, color 0.2s;
        }
        .stFormSubmitButton > button:hover {
            background-color: #3a3a50; color: #ffffff; border-color: #666;
        }
        footer { visibility: hidden; } #MainMenu { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="title-container">
        <h1>🤖 PLM Bot</h1>
        <div class="byline">A Bot by Pranav C</div>
        <div class="caption">Where curiosity meets intelligence — ask, explore, discover.</div>
    </div>
""", unsafe_allow_html=True)

st.markdown("---")

with st.form(key="query_form"):
    user_input = st.text_input("", placeholder="Type your question here...", key="input")
    submit = st.form_submit_button("Ask PLM Bot")

if submit:
    if user_input.strip():
        with st.spinner("Thinking..."):
            response = my_output(user_input)
        st.markdown(f'<div class="response-box">{response}</div>', unsafe_allow_html=True)
    else:
        st.warning("Please enter a question first.")
