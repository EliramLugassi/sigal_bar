"""Page for updating a user's personal profile."""

import streamlit as st
import bcrypt
from modules.db_tools.crud_operations import get_user_by_username


def render(conn, T):
    """Allow a user to update their email and password."""
    st.header("👤 " + T("my_profile"))

    username = st.session_state.username
    user = get_user_by_username(conn, username)

    if not user:
        st.error(T("user_not_found"))
        return

    from modules.db_tools.crud_operations import get_user_building_ids

    ...

    user_id = user[0]
    current_email = user[3]
    assigned_building_ids = get_user_building_ids(conn, user_id)

    # We'll let the rep edit contact info for all assigned buildings
    with conn.cursor() as cur:
        cur.execute("""
            SELECT building_id, building_name, contact_phone, contact_email
            FROM buildings WHERE building_id = ANY(%s)
        """, (assigned_building_ids,))
        buildings_info = cur.fetchall()

    if not buildings_info:
        st.info(T("no_buildings_assigned"))
        return

    new_email = st.text_input(T("your_email_label"), value=current_email)
    new_password = st.text_input(T("new_password_optional"), type="password")

    # Collect phone updates
    updated_contacts = []
    st.subheader(T("building_contact_info_title"))
    for building_id, name, phone, email in buildings_info:
        st.markdown(f"**🏢 {name}**")
        new_phone = st.text_input(T("phone_for_building").format(name=name), value=phone or "", key=f"phone_{building_id}")
        new_contact_email = st.text_input(T("contact_email_for_building").format(name=name), value=email or "", key=f"email_{building_id}")
        updated_contacts.append((building_id, new_phone, new_contact_email))

    if st.button(T("save_changes_btn")):
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET email = %s WHERE user_id = %s", (new_email, user_id))

                if new_password:
                    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                    cur.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (hashed, user_id))

                for building_id, phone, email in updated_contacts:
                    cur.execute("""
                        UPDATE buildings
                        SET contact_phone = %s,
                            contact_email = %s
                        WHERE building_id = %s
                    """, (phone, email, building_id))

                conn.commit()
            st.success(T("profile_updated"))
        except Exception as e:
            st.error(T("failed_to_update").format(error=e))

    st.markdown("---")
    st.subheader(T("invoice_footer_preview"))

    for building_id, phone, email in updated_contacts:
        with conn.cursor() as cur:
            cur.execute("SELECT building_name FROM buildings WHERE building_id = %s", (building_id,))
            name = cur.fetchone()[0] if cur.rowcount else T("unknown_building")

        contact_display = f"{phone} | {email}" if phone or email else "—"

        st.markdown(f"""
        <div style='
            background-color: #f0f8ff;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid #d0e6f7;
            font-size: 16px;
        '>
            🏢 <strong>{T('in_building_footer_preview').format(name=name)}</strong><br>
            📇 {contact_display}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(T("download_my_data_csv"))
    building_map = {b_id: name for b_id, name, *_ in buildings_info}
    selected_b_id = st.selectbox(
        T("select_building"),
        options=list(building_map.keys()),
        format_func=lambda x: building_map[x],
    )

    if st.button(T("download_csv")):
        from modules.db_tools.crud_operations import export_building_data

        zip_buffer = export_building_data(conn, selected_b_id)
        st.download_button(
            T("download_my_data_csv"),
            zip_buffer.getvalue(),
            file_name=f"building_{selected_b_id}_data.zip",
            mime="application/zip",
        )





