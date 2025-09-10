"""Streamlit app entrypoint for apartment management UI."""
import streamlit as st
from modules.db_tools.db_connection import get_connection
from modules.utils.language import setup_language_selector, get_translator
from modules import (
    dashboard_page, buildings_page, invoices_page,
    suppliers_page, expenses_page, admin_panel, transactions_page,
    reports_page, my_profile, login_page, onboarding_wizard, support_page
)


# 📦 Initialize database and language
conn = get_connection()
T = get_translator()

# 🔐 Session control

import time
from datetime import datetime

SESSION_TIMEOUT = 10 * 60  # 15 minutes
now = time.time()

# 🔐 Initialize session flags
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# 🔐 If not logged in — show login/signup
if not st.session_state.logged_in:
    with st.spinner("🔐 Loading login screen..."):
        time.sleep(0.8)
    # Refresh connection in case it expired while idle
    conn = get_connection()
    login_page.render(conn)
    st.stop()

# 🕒 Session timeout check (after login)
if "last_seen" not in st.session_state:
    st.session_state.last_seen = now
elif now - st.session_state.last_seen > SESSION_TIMEOUT:
    # Expire session and clean up
    conn.close()
    st.session_state.pop("db_conn", None)
    for key in ["logged_in", "username", "role", "admin_mode", "simulate_user", "last_seen"]:
        st.session_state.pop(key, None)
    st.warning("Session expired due to inactivity.")
    st.rerun()
else:
    st.session_state.last_seen = now

# 📌 Update last_active in DB only if logged in and username is available
if st.session_state.get("logged_in") and st.session_state.get("username"):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE users
            SET last_active = %s
            WHERE username = %s
        """, (datetime.now(), st.session_state.username))
        conn.commit()

# 🚀 Onboarding wizard check
if st.session_state.get("onboarding_step"):
    onboarding_wizard.render(conn)
    st.stop()

# 👤 User info
actual_role = st.session_state.get("role", "user")
simulate_user = st.session_state.get("simulate_user", False)
user_role = "user" if simulate_user else actual_role
username = st.session_state.get("username", "unknown")

if "support_open" not in st.session_state:
    st.session_state.support_open = False

# 🧨 Stop server callback
def stop_server():
    """Stop the running Streamlit server."""
    import os, signal
    os.kill(os.getpid(), signal.SIGINT)

# 🧭 Sidebar layout
with st.sidebar:
    # 🏠 App title
    st.markdown("## 🏠 Apartment Management App")

    # 🌐 Language selector
    setup_language_selector(key="language_selector_app_sidebar")

    # 📂 Page navigation (moved directly under language)
    pages = {
        T("dashboard"): "dashboard",
        T("buildings"): "buildings",
        T("invoices"): "invoices",
        T("suppliers"): "suppliers",
        T("expenses"): "expenses",
        T("reports"): "reports",
        T("transactions"): "transactions",
        T("my_profile"): "my_profile",
    }
    menu_label = st.sidebar.selectbox("", list(pages.keys()))
    menu = pages[menu_label]

    # 🔐 Admin-only controls
    if actual_role == "admin":
        if st.button(T("admin_panel")):
            st.session_state.admin_mode = True

        is_sim_user = st.session_state.get("simulate_user", False)
        btn_label = T("view_as_admin") if is_sim_user else T("view_as_user")
        if st.button(btn_label):
            st.session_state.simulate_user = not is_sim_user
            st.rerun()

    # ───────── Divider ─────────
    st.markdown("---")

    # 👤 User info
    st.markdown(f"👤 {T('logged_in_as')}: **{username} ({user_role})**")

    if st.button(T("support")):
        st.session_state.support_open = True

    # 🚪 Logout
    if st.button(T("logout")):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.admin_mode = False
        st.session_state.simulate_user = False
        st.session_state.support_open = False

        # Close connection explicitly
        conn.close()
        st.session_state.pop("db_conn", None)

        st.rerun()

    # 🛑 Stop Server for admins only
    if actual_role == "admin":
        st.button(T("stop_server"), on_click=stop_server)

# 🛠 Admin panel rendering
if st.session_state.get("admin_mode") and actual_role == "admin":
    admin_panel.render(conn, T)
    st.stop()

# 🔀 Page routing
if st.session_state.get("support_open"):
    support_page.render(conn, T)
elif menu == "dashboard":
    dashboard_page.render(conn, T)
elif menu == "buildings":
    buildings_page.render(conn, T)
elif menu == "invoices":
    invoices_page.render(conn, T)
elif menu == "suppliers":
    suppliers_page.render(conn, T)
elif menu == "expenses":
    expenses_page.render(conn, T)
elif menu == "reports":
    reports_page.render(conn, T)
elif menu == "transactions":
    transactions_page.render(conn, T)
elif menu == "my_profile":
    my_profile.render(conn, T)

