"""Admin interface for managing users and database activity.

This page exposes user management tools such as password resets,
building assignments and viewing active sessions. The ``render``
function is invoked from ``app.py`` to display the UI.
"""

import streamlit as st
import bcrypt
import pandas as pd
from io import BytesIO
from auth import signup
from crud_operations import (
    get_all_users, get_all_buildings, get_user_building_ids,
    update_user_buildings, create_user, update_user, delete_user,
    get_user_id, get_user_session_count, count_active_users,
    get_active_users, get_db_activity, terminate_connection,
    get_open_support_tickets, update_support_ticket_status,
    delete_support_ticket
)

# Optional: implement this in crud_operations.py
def get_last_logins(conn, user_id, limit=5):
    """Return recent login timestamps for the given user."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT login_time FROM user_sessions
            WHERE user_id = %s
            ORDER BY login_time DESC
            LIMIT %s;
        """,
            (user_id, limit),
        )
        return [r[0].strftime("%Y-%m-%d %H:%M") for r in cur.fetchall()]


def render(conn, T):
    """Render the admin panel using the provided translator."""
    st.header(T("admin_panel"))

    if st.button(T("back_to_app")):
        st.session_state.admin_mode = False
        st.rerun()

    users_df = get_all_users(conn)
    buildings_df = get_all_buildings(conn)

    # Convert datetime
    users_df["last_login"] = users_df["last_login"].apply(
        lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notnull(x) else "—"
    )

    # ─────────── 📊 USERS OVERVIEW ───────────
    with st.expander("📊 Database Activity (pg_stat_activity)"):
        df_activity = get_db_activity(conn)
        st.dataframe(df_activity)

        pid_to_kill = st.number_input("Enter PID to terminate", step=1)
        if st.button("🔪 Terminate Connection"):
            terminate_connection(conn, int(pid_to_kill))
            st.success(f"✅ Connection {pid_to_kill} terminated.")
            st.rerun()

    with st.expander("📊 " + T("user_overview")):
        st.metric(T("total_users"), len(users_df))

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button(T("download_csv")):
                csv = users_df.to_csv(index=False).encode("utf-8")
                st.download_button(T("download_users_csv"), csv, file_name="users.csv", mime="text/csv")

        with col2:
            st.dataframe(users_df)

    with st.expander("🟢 " + T("live_sessions")):
        live_count = count_active_users(conn, within_minutes=5)
        st.metric(T("live_users_metric"), live_count)

        live_users = get_active_users(conn, within_minutes=5)
        if live_users:
            df_live = pd.DataFrame(live_users, columns=["Username", "Role", "Last Active"])
            st.dataframe(df_live)
        else:
            st.info(T("no_active_users"))

    # ─────────── ✏️ MANAGE USERS ───────────
    with st.expander("✏️ " + T("edit_delete_reset_user")):
        selected_username = st.selectbox(T("select_user_to_manage"), users_df["username"])
        selected_user = users_df[users_df["username"] == selected_username].iloc[0]

        user_id = selected_user["user_id"]
        user_role = selected_user["role"]
        new_email = st.text_input("📧 " + T("email"), value=selected_user["email"])
        new_role = st.selectbox("🎭 " + T("role"), ["user", "admin"], index=["user", "admin"].index(user_role))
        new_password = st.text_input(T("new_password_optional"), type="password")

        # KPIs and session info
        session_count = get_user_session_count(conn, user_id)
        assigned_buildings = get_user_building_ids(conn, user_id)
        st.markdown(f"**👥 Sessions:** {session_count} | 🏢 Assigned Buildings: {len(assigned_buildings)}**")

        last_sessions = get_last_logins(conn, int(user_id))  # 👈 Force cast to native int
        if last_sessions:
            st.markdown("**🕓 Last Logins:**")
            for i, ts in enumerate(last_sessions, 1):
                st.markdown(f"- {i}. {ts}")

        col1, col2, col3 = st.columns(3)
        if col1.button(T("update_user")):
            update_user(conn, user_id, new_email, new_role)
            st.success(T("user_updated"))
            st.rerun()

        if col2.button(T("reset_password")) and new_password:
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password_hash = %s WHERE user_id = %s;",
                    (hashed, int(user_id))  # 👈 Cast to native int
                )
                conn.commit()

            st.success(T("password_reset"))

        if col3.button(T("delete_user")):
            if user_role == "admin":
                st.error(T("cannot_delete_admin"))
            elif user_id == get_user_id(conn, st.session_state.username):
                st.error(T("cannot_delete_self"))
            else:
                delete_user(conn, user_id)
                st.warning(T("user_deleted"))
                st.rerun()

    # ─────────── 🎫 SUPPORT TICKETS ───────────
    with st.expander("🎫 " + T("support_ticket_admin")):
        tickets = get_open_support_tickets(conn)
        st.metric(T("open_tickets"), len(tickets))

        if tickets:
            df_t = pd.DataFrame(
                tickets,
                columns=[
                    "ticket_id",
                    "username",
                    "building_name",
                    "subject",
                    "message",
                    "status",
                    "created_at",
                ],
            )
            st.dataframe(df_t.drop(columns=["message"]))

            selected_id = st.selectbox(T("select_ticket"), df_t["ticket_id"])
            new_status = st.selectbox(
                T("status_label"),
                ["open", "in_progress", "resolved", "closed"],
            )
            col1, col2 = st.columns(2)
            if col1.button(T("update_ticket_status")):
                update_support_ticket_status(conn, int(selected_id), new_status)
                st.success(T("ticket_status_updated"))
                st.rerun()
            if col2.button(T("delete_ticket")):
                delete_support_ticket(conn, int(selected_id))
                st.success(T("ticket_deleted"))
                st.rerun()
        else:
            st.info(T("no_open_tickets"))

    # ─────────── 🏢 ASSIGN BUILDINGS ───────────
    with st.expander("🏢 " + T("assign_buildings_to_user")):
        selected_user_row = users_df[users_df["username"] == st.selectbox("👤 " + T("select_user"), users_df["username"], key="assign_user")]
        user_id = int(selected_user_row["user_id"])
        current_ids = get_user_building_ids(conn, user_id)

        building_names = buildings_df.set_index("building_id")["building_name"].to_dict()
        building_id_options = list(building_names.keys())

        selected_buildings = st.multiselect(
            "🏗 " + T("select_buildings"),
            options=building_id_options,
            default=current_ids,
            format_func=lambda x: building_names[x]
        )

        if not selected_buildings:
            st.warning("⚠️ " + T("no_buildings_assigned_user"))

        if st.button(T("save_assignments")):
            update_user_buildings(conn, user_id, selected_buildings)
            st.success(T("assignments_updated"))
            st.rerun()

    # ─────────── ➕ CREATE NEW USER ───────────
    with st.expander(T("create_new_user")):
        signup(conn)

    st.markdown("### " + T("onboarding_wizard"))
    st.info(T("onboarding_info"))

    if st.button(T("start_onboarding_wizard")):
        st.session_state.onboarding_step = 1
        st.rerun()
