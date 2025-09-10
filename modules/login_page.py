"""User login page."""

import streamlit as st
from auth import login
from localization import get_translation
from language import setup_language_selector

def render(conn):
    """Render the login form for users."""
    setup_language_selector(key="language_selector_login")
    T = get_translation(st.session_state.get("lang", "en"))

    # 🏠 Centered App Title
    st.markdown("""
        <h1 style='text-align: center; font-size: 2.2em; margin-bottom: 1em;'>
            🏠 Vaad Management App
        </h1>
    """, unsafe_allow_html=True)

    login(conn)  # calls auth logic and handles success
