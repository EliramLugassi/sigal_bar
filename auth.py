"""User authentication helpers."""
import bcrypt
import streamlit as st

from crud_operations import create_user, get_user_by_username
from localization import get_translation
import time

from modules import onboarding_wizard


def signup(conn):
    """Register a new user in the database."""
    T = get_translation(st.session_state.get("lang", "en"))

    st.subheader(T("signup_title"))

    username = st.text_input(T("new_username"))
    email = st.text_input(T("email"))
    password = st.text_input(T("new_password"), type="password")

    # 👀 Only admins can assign roles
    if st.session_state.get("logged_in") and st.session_state.get("role") == "admin":
        role = st.selectbox(T("assign_role"), ["user", "admin"])
    else:
        role = "user"

    if st.button(T("create_account_btn")):
        if username and password:
            create_user(conn, username, password, email, role)
            st.success(T("user_created").format(username=username, role=role))
        else:
            st.warning(T("fill_all_fields"))

def login(conn):
    """Authenticate a user and start a session."""
    T = get_translation(st.session_state.get("lang", "en"))
    st.subheader(T("login_title"))

    username = st.text_input(T("username"))
    password = st.text_input(T("password"), type="password")

    if st.button(T("login_btn")):
        user = get_user_by_username(conn, username)
        if user and bcrypt.checkpw(password.encode(), user[2].encode()):
            # If this is the first login, trigger onboarding wizard
            first_login_flag = False
            if user[7]is None:
                first_login_flag = True
                st.session_state.onboarding_step = 1

            # ✅ Extract user_id (assuming it's at index 0)
            user_id = user[0]
            # ✅ Set session
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.user_id = user_id  # ✅ Add this
            st.session_state.role = user[4]
            st.session_state.last_seen = time.time()

            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users
                    SET last_login = CURRENT_TIMESTAMP,
                        last_active = CURRENT_TIMESTAMP
                    WHERE username = %s
                """, (username,))

                cur.execute("""
                    INSERT INTO user_sessions (user_id)
                    VALUES (%s)
                """, (user_id,))

                conn.commit()

            st.success(T("welcome_user").format(username=username))
            if first_login_flag:
                onboarding_wizard.render(conn)
                st.rerun()
            st.rerun()
        else:
            st.error(T("invalid_credentials"))


# def login(conn):
#     T = get_translation(st.session_state.get("lang", "en"))
#     st.subheader(T("login_title"))
#
#     username = st.text_input(T("username"))
#     password = st.text_input(T("password"), type="password")
#
#     if st.button(T("login_btn")):
#         user = get_user_by_username(conn, username)
#         if user and bcrypt.checkpw(password.encode(), user[2].encode()):
#             # ✅ Set session
#             st.session_state.logged_in = True
#             st.session_state.username = username
#             st.session_state.role = user[4]
#             st.session_state.last_seen = time.time()
#
#             with conn.cursor() as cur:
#                 # ✅ Update login + activity
#                 cur.execute("""
#                     UPDATE users
#                     SET last_login = CURRENT_TIMESTAMP,
#                         last_active = CURRENT_TIMESTAMP
#                     WHERE username = %s
#                 """, (username,))
#
#                 # ✅ Insert session log
#                 cur.execute("""
#                     INSERT INTO user_sessions (user_id)
#                     SELECT user_id FROM users WHERE username = %s
#                 """, (username,))
#
#                 conn.commit()
#
#             st.success(T("welcome_user").format(username=username))
#             st.rerun()
#         else:
#             st.error(T("invalid_credentials"))


# import streamlit as st
# from localization import get_translation
# import time
# from supabase import create_client
# import os
# from dotenv import load_dotenv
# from crud_operations import get_user_role  # still used for fallback
#
# # 🔐 Supabase setup
# load_dotenv()
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
#
# def signup():
#     T = get_translation(st.session_state.get("lang", "en"))
#
#     st.subheader(T("signup_title"))
#
#     email = st.text_input(T("email"))
#     password = st.text_input(T("new_password"), type="password")
#     role = st.selectbox(T("assign_role"), ["user", "admin"]) if st.session_state.get("role") == "admin" else "user"
#
#     if st.button(T("create_account_btn")):
#         if email and password:
#             try:
#                 supabase.auth.sign_up({
#                     "email": email,
#                     "password": password,
#                     "options": {
#                         "data": {
#                             "role": role
#                         }
#                     }
#                 })
#                 st.success(f"✅ User created! Role: {role}. Check your email to confirm.")
#             except Exception as e:
#                 st.error(f"❌ Signup failed: {str(e)}")
#         else:
#             st.warning(T("fill_all_fields"))
#
# def login():
#     T = get_translation(st.session_state.get("lang", "en"))
#     st.subheader(T("login_title"))
#
#     email = st.text_input(T("email"))
#     password = st.text_input(T("password"), type="password")
#
#     if st.button(T("login_btn")):
#         try:
#             result = supabase.auth.sign_in_with_password({
#                 "email": email,
#                 "password": password
#             })
#
#             user = result.user
#             if user:
#                 # Try role from metadata
#                 metadata = user.user_metadata or {}
#                 role = metadata.get("role")
#
#                 # Fallback: try local DB
#                 if not role:
#                     conn = st.session_state.get("conn")
#                     if conn:
#                         role = get_user_role(conn, email)
#
#                 # Default if all fails
#                 role = role or "user"
#
#                 # ✅ Set session
#                 st.session_state.logged_in = True
#                 st.session_state.username = user.email
#                 st.session_state.role = role
#                 st.session_state.last_seen = time.time()
#
#                 st.success(T("welcome_user").format(username=user.email))
#                 st.rerun()
#             else:
#                 st.error(T("invalid_credentials"))
#
#         except Exception as e:
#             st.error("❌ Invalid credentials or Supabase error.")
