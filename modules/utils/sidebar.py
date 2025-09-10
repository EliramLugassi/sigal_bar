"""Sidebar rendering utilities."""
import streamlit as st
from language import setup_language_selector, get_translator

def render_sidebar(username, user_role, actual_role):
    """Render the common sidebar and return selected menu."""
    setup_language_selector(key="language_selector_sidebar")
    T = get_translator()

    st.sidebar.title("🏠 Apartment Management App")
    st.sidebar.markdown(f"{T('logged_in_as')}: {username} ({user_role})")

    menu = st.sidebar.selectbox("", [
        T("dashboard"), T("buildings"), T("invoices"),
        T("suppliers"), T("expenses"), T("reports")
    ], key="main_menu")

    # Admin toggle
    if actual_role == "admin":
        if st.sidebar.button(T("admin_panel")):
            st.session_state.admin_mode = True

        toggle_label = T("view_as_admin") if st.session_state.get("simulate_user") else T("view_as_user")
        if st.sidebar.button(toggle_label):
            st.session_state.simulate_user = not st.session_state.get("simulate_user", False)
            st.rerun()

    # Stop server + logout
    st.sidebar.markdown("---")
    if actual_role == "admin":
        if st.sidebar.button(T("stop_server")):
            import os, signal
            os.kill(os.getpid(), signal.SIGINT)

    if st.sidebar.button(T("logout")):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.admin_mode = False
        st.session_state.simulate_user = False
        st.rerun()

    return menu
