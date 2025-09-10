import streamlit as st
import pandas as pd
from modules.db_tools.crud_operations import (
    get_user_id,
    get_user_building_ids,
    submit_ticket,
    get_support_tickets_by_buildings,
)
from modules.gpt_assistant import ask_gpt


def render(conn, T):
    st.header("🛠️ Support Assistant")

    # Close button to return to the main app
    if st.button(T("close_support_page"), use_container_width=True):
        st.session_state.support_open = False
        st.session_state.show_ticket_form = False
        st.rerun()

    # Get user and building info
    username = st.session_state.get("username")
    user_id = get_user_id(conn, username)
    building_ids = get_user_building_ids(conn, user_id)

    st.subheader("📋 " + T("support_tickets"))
    tickets = get_support_tickets_by_buildings(conn, building_ids)
    if tickets:
        df_tickets = pd.DataFrame(
            tickets,
            columns=["ticket_id", "building_name", "subject", "status", "created_at"],
        )
        rename_map = {
            "ticket_id": "ID",
            "building_name": T("building_name_label") if T("building_name_label") != "building_name_label" else "Building",
            "subject": T("subject_label") if T("subject_label") != "subject_label" else "Subject",
            "status": T("status_label") if T("status_label") != "status_label" else "Status",
            "created_at": T("created_at") if T("created_at") != "created_at" else "Created",
        }
        st.dataframe(df_tickets.rename(columns=rename_map))
    else:
        st.info(T("no_tickets") if T("no_tickets") != "no_tickets" else "No tickets found.")

    if "show_ticket_form" not in st.session_state:
        st.session_state.show_ticket_form = False

    # -------------- STEP 1: GPT ASSISTANT --------------
    with st.expander("🧠 " + T("gpt_assistant"), expanded=not st.session_state.show_ticket_form):
        query = st.text_input(T("ask_gpt"), key="support_gpt_input")
        if st.button(T("ask_gpt"), key="support_gpt_btn") and query:
            ctx = {"page": "support", "user": username, "buildings": str(building_ids)}
            with st.spinner(T("thinking")):
                answer = ask_gpt(query, ctx)
            st.write(answer)

        if st.button("❌ Still Need Help?", key="need_help_btn"):
            st.session_state.show_ticket_form = True
            st.rerun()

    # -------------- STEP 2: TICKET FORM --------------
    if st.session_state.show_ticket_form:
        st.markdown("## 📝 " + T("submit_ticket"))

        building_name_map = {}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT building_id, building_name FROM buildings WHERE building_id = ANY(%s)",
                (building_ids,),
            )
            for row in cur.fetchall():
                building_name_map[row[1]] = row[0]

        selected_building_name = st.selectbox("🏢 " + T("select_building"), list(building_name_map.keys()))
        building_id = building_name_map[selected_building_name]

        subject = st.text_input(T("subject_label"))
        message = st.text_area(T("message_body"))

        if st.button("📨 " + T("submit_ticket")):
            submit_ticket(conn, user_id, building_id, subject, message)
            st.success("✅ Your support ticket has been submitted.")
            st.session_state.show_ticket_form = False
            st.rerun()
