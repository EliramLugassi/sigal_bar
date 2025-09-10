"""Page for managing suppliers linked to each building."""

import streamlit as st
from modules.db_tools.crud_operations import add_supplier, update_supplier, delete_supplier, get_suppliers_by_building
from modules.db_tools.filters import get_allowed_building_df

def render(conn, T):
    """Render supplier management for the selected building."""
    st.header("📦 " + T("supplier_management"))

    user_id = st.session_state.get("user_id")
    df_buildings = get_allowed_building_df(conn)

    if df_buildings.empty:
        st.warning(T("no_buildings_assigned"))
        st.stop()

    building_map = {row["building_name"]: row["building_id"] for _, row in df_buildings.iterrows()}
    selected_building_name = st.selectbox("🏢 " + T("select_building"), list(building_map.keys()))
    selected_building_id = building_map[selected_building_name]
    df_suppliers = get_suppliers_by_building(conn, selected_building_id)

    rename_map = {
        "supplier_name": T("supplier_name"),
        "expense_type": T("expense_type"),
        "segment": T("segment_label"),
    }
    st.dataframe(df_suppliers.rename(columns=rename_map))

    with st.expander(T("add_supplier_expander")):
        name = st.text_input(T("supplier_name"))
        expense_type = st.text_input(T("expense_type"))
        segment = st.text_input(T("segment_label"))
        if st.button(T("add_supplier")):
            add_supplier(conn, name, expense_type, segment, [selected_building_id])
            st.success(T("supplier_added"))
            st.rerun()

    with st.expander(T("edit_supplier_expander")):
        if not df_suppliers.empty:
            selected_id = st.selectbox(
                T("select_supplier"),
                df_suppliers['supplier_id'],
                format_func=lambda x: df_suppliers[df_suppliers['supplier_id'] == x]['supplier_name'].values[0]
            )
            selected_row = df_suppliers[df_suppliers['supplier_id'] == selected_id].iloc[0]

            new_name = st.text_input(T("new_name"), selected_row['supplier_name'])
            new_type = st.text_input(T("new_expense_type"), selected_row['expense_type'])
            new_segment = st.text_input(T("new_segment"), selected_row['segment'])

            if st.button(T("update_supplier_btn")):
                update_supplier(conn, selected_id, new_name, new_type, new_segment)
                st.success(T("supplier_updated"))
                st.rerun()
        else:
            st.info(T("no_suppliers_to_edit"))

    with st.expander(T("delete_supplier_expander")):
        if not df_suppliers.empty:
            delete_id = st.selectbox(
                T("select_supplier_to_delete"),
                df_suppliers['supplier_id'],
                format_func=lambda x: df_suppliers[df_suppliers['supplier_id'] == x]['supplier_name'].values[0],
                key="delete_supplier"
            )
            if st.button(T("delete_supplier")):
                delete_supplier(conn, delete_id)
                st.warning(T("supplier_deleted"))
                st.rerun()
        else:
            st.info(T("no_suppliers_to_delete"))
