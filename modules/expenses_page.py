"""Page for recording expenses and uploading receipt images."""

import datetime
import os
import streamlit as st
import pandas as pd
import tempfile
from google.api_core.exceptions import GoogleAPIError
from modules.db_tools.crud_operations import (
    get_expenses,
    add_expense,
    update_expense,
    delete_expense,
    get_suppliers_by_building,
    import_expenses_from_df,
    add_expense_document,
    get_expense_documents,
    delete_expense_document,
    get_expense_document_counts,
    get_expense_details_range,
)
from modules.db_tools.filters import get_allowed_building_df
from modules.google_tools.gcs_utils import (
    upload_document,
    delete_document_by_url,
    get_document_url_from_file,
)
import unicodedata
import re


def sanitize_filename(filename):
    """Clean a filename by removing special characters and accents."""
    name = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\-_.]', '_', name)
    return name


def render(conn, T):
    """Render the expenses management page with upload options."""
    st.header("💸 " + T("expenses"))

    # Load data
    buildings_df = get_allowed_building_df(conn)
    user_id = st.session_state.get("user_id")
    all_expenses = get_expenses(conn)
    current_year = datetime.datetime.now().year
    allowed_ids = buildings_df["building_id"].tolist()
    filtered_expenses = all_expenses[all_expenses["building_id"].isin(allowed_ids)]
    all_expenses = filtered_expenses

    # ───────────── FILTERS ─────────────
    col1, col2 = st.columns(2)
    building_filter = col1.selectbox(
        "🏢 " + T("filter_by_building"),
        options= buildings_df["building_name"].tolist(),
        key="building_filter_expenses"
    )
    building_map = {
        row["building_name"]: row["building_id"]
        for _, row in buildings_df.iterrows()
    }
    selected_building_id = building_map[building_filter]

    building_expense_types = (
        all_expenses[all_expenses["building_id"] == selected_building_id]
        ["expense_type"]
        .dropna()
        .unique()
    )
    expense_type_filter = col2.selectbox(
        "📂 " + T("filter_by_expense_type"),
        options=["All"] + sorted(building_expense_types),
        key="expense_type_filter_expenses"
    )

    col3, col4 = st.columns(2)
    status_filter = col3.selectbox(
        "📌 " + T("filter_by_status"),
        options=["All"] + sorted(all_expenses["status"].dropna().unique()),
        key="status_filter_expenses"
    )
    year_filter = col4.selectbox(
        "📅 " + T("year"),
        options=["All"] + list(range(2023, current_year + 2)),
        key="year_filter_expenses"
    )

    col5, col6 = st.columns(2)
    month_filter = col5.selectbox(
        "🗓 " + T("month"),
        options=["All"] + list(range(1, 13)),
        key="month_filter_expenses"
    )
    receipt_id_filter = col6.text_input(T("filter_by_receipt_id"), key="receipt_id_filter_expenses")


    suppliers_df = get_suppliers_by_building(conn, selected_building_id)

    # ───────────── APPLY FILTERS ─────────────
    df_expenses = all_expenses.copy()
    df_expenses["start_date"] = pd.to_datetime(df_expenses["start_date"], errors="coerce")
    doc_counts = get_expense_document_counts(conn)
    df_expenses = df_expenses.merge(doc_counts, on="expense_id", how="left")
    df_expenses["doc_count"] = df_expenses["doc_count"].fillna(0).astype(int)

    if building_filter != "All":
        df_expenses = df_expenses[df_expenses["building_name"] == building_filter]
    if expense_type_filter != "All":
        df_expenses = df_expenses[df_expenses["expense_type"] == expense_type_filter]
    if status_filter != "All":
        df_expenses = df_expenses[df_expenses["status"] == status_filter]
    if isinstance(year_filter, int):
        df_expenses = df_expenses[df_expenses["start_date"].dt.year == year_filter]
    if isinstance(month_filter, int):
        df_expenses = df_expenses[df_expenses["start_date"].dt.month == month_filter]

    if receipt_id_filter.strip():
        df_expenses = df_expenses[
            df_expenses["supplier_receipt_id"].str.contains(receipt_id_filter.strip(), case=False, na=False)]

    # ───────────── FETCH DETAILS FOR TABLE (MATCH DASHBOARD) ─────────────
    detail_start = datetime.date(2020, 1, 1)
    detail_end = datetime.date(current_year + 1, 12, 31)
    df_table = get_expense_details_range(conn, detail_start, detail_end, selected_building_id)

    if expense_type_filter != "All":
        df_table = df_table[df_table["expense_type"] == expense_type_filter]
    if status_filter != "All":
        df_table = df_table[df_table["status"] == status_filter]
    if isinstance(year_filter, int):
        df_table = df_table[df_table["charge_year"] == year_filter]
    if isinstance(month_filter, int):
        df_table = df_table[df_table["charge_month_num"] == month_filter]

    # calculate total before dropping unused columns so the "cost" field is
    # still available
    total_cost = df_table["cost"].sum()

    # ───────────── SHOW TABLE ─────────────
    with st.expander(T("view_expenses_table"), expanded=False):
        # drop building name (filtered to one building) and order columns
        df_table = df_table.drop(columns=["building_name"], errors="ignore")
        ordered_cols = [
            "expense_id",
            "status",
            "expense_type",
            "supplier_name",
            "notes",
            "supplier_receipt_id",
            "total_cost",
            "num_payments",
            "monthly_cost",
            "start_date",
            "end_date",
            "charge_year",
            "charge_month_num",
        ]
        df_table = df_table[ordered_cols]

        rename_map = {
            "expense_id": T("expense_id_label"),
            "status": T("status_label"),
            "expense_type": T("expense_type"),
            "supplier_name": T("supplier_name"),
            "notes": T("notes_label"),
            "supplier_receipt_id": T("supplier_receipt_id"),
            "total_cost": T("total_cost"),
            "num_payments": T("number_of_payments"),
            "monthly_cost": T("monthly_cost"),
            "start_date": T("start_date"),
            "end_date": T("end_date"),
            "charge_year": T("year"),
            "charge_month_num": T("month"),
        }
        st.dataframe(df_table.rename(columns=rename_map))

    # 💰 Total Expense Summary

    label = T("total_expense_amount") if T("total_expense_amount") != "total_expense_amount" else "Total Expense Amount"

    st.markdown("""
    <div style='
        background-color: #fff8e1;
        border-radius: 16px;
        padding: 25px;
        margin-top: 20px;
        margin-bottom: 30px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        text-align: center;
        font-size: 22px;
        font-weight: bold;
        color: #333;
    '>
        💰 {}: ₪ {:,.0f}
    </div>
    """.format(label, total_cost), unsafe_allow_html=True)

    with st.expander("➕ " + T("add_expense")):
        b_id = st.selectbox(T("building_label"), buildings_df["building_id"], format_func=lambda x: buildings_df[buildings_df["building_id"] == x]["building_name"].values[0])
        s_id = st.selectbox(T("supplier_label"), suppliers_df["supplier_id"], format_func=lambda x: suppliers_df[suppliers_df["supplier_id"] == x]["supplier_name"].values[0])
        receipt = st.text_input(T("receipt_id"))
        col1, col2 = st.columns(2)
        start_date = col1.date_input(T("start_date"), key="add_expense_start")
        payments = col2.number_input(T("number_of_payments"), min_value=1, step=1, key="add_expense_payments")

        # ⏱ automatically derive the end date based on the start date and number of payments
        calc_end_date = (
            pd.to_datetime(start_date)
            + pd.DateOffset(months=int(payments) - 1)
            + pd.offsets.MonthEnd(0)
        ).date()

        col3, col4 = st.columns(2)
        total_cost = col3.number_input(T("total_cost"), min_value=0.0, step=100.0)
        col4.date_input(T("end_date"), value=calc_end_date, disabled=True, key="add_expense_end")
        # monthly_cost = col4.number_input("Monthly Cost", min_value=0.0, step=100.0)
        # payments = st.number_input("Number of Payments", min_value=1, step=1)
        status = st.selectbox(T("status_label"), ["pending", "paid", "cancelled"], index=0)
        notes = st.text_area(T("notes_label"), key="add_expense_notes")
        uploaded_docs = st.file_uploader("📎 " + T("attach_documents"), accept_multiple_files=True)

        if st.button(T("add_expense")):
            new_id = add_expense(
                conn,
                b_id,
                s_id,
                receipt,
                start_date,
                calc_end_date,
                total_cost,
                total_cost / payments,
                payments,
                status,
                notes,
            )
            if uploaded_docs:
                # resolve the building name from the selected id so the path is
                # consistent regardless of any active filter
                b_name = buildings_df[buildings_df["building_id"] == b_id][
                    "building_name"
                ].values[0]
                for doc in uploaded_docs:
                    tmp = tempfile.NamedTemporaryFile(delete=False)
                    tmp.write(doc.getbuffer())
                    tmp.close()
                    safe_name = sanitize_filename(doc.name)
                    try:
                        url = upload_document(
                            tmp.name,
                            safe_name,
                            b_id,
                            b_name,
                            start_date,
                        )
                        add_expense_document(conn, b_id, new_id, safe_name, url)
                    except GoogleAPIError as e:
                        st.toast(
                            T("storage_action_failed").format(error=e), icon="⚠️"
                        )
                    finally:
                        os.remove(tmp.name)
            st.success(T("expense_added"))
            st.rerun()

    with st.expander("✏️ " + T("edit_expense")):
        if df_expenses.empty:
            st.info(T("no_expenses_match"))
        else:
            expense_labels = {
                f"{row.expense_id} - {row.supplier_receipt_id} - {row.notes[:30]} ({row.doc_count})": row.expense_id
                for _, row in df_expenses.iterrows()
            }
            selected_label = st.selectbox(T("select_expense"), list(expense_labels.keys()))
            e_id = expense_labels[selected_label]
            e_row = df_expenses[df_expenses["expense_id"] == e_id].iloc[0]

            col_start, col_end = st.columns(2)
            start_date = col_start.date_input(T("start_date"), value=e_row["start_date"])
            end_date = col_end.date_input(T("end_date"), value=e_row["end_date"])

            supplier_options = {row["supplier_name"]: row["supplier_id"] for _, row in suppliers_df.iterrows()}
            reverse_supplier_lookup = {v: k for k, v in supplier_options.items()}

            current_supplier_name = e_row["supplier_name"]
            current_supplier_id = supplier_options.get(current_supplier_name)

            supplier_ids = list(supplier_options.values())
            if current_supplier_id in supplier_ids:
                selected_index = supplier_ids.index(current_supplier_id)
            else:
                selected_index = 0  # fallback if missing

            supplier_id = st.selectbox(
                T("supplier_label"),
                options=supplier_ids,
                format_func=lambda x: reverse_supplier_lookup.get(x, "Unknown"),
                index=selected_index,
                key=f"edit_supplier_{e_id}"
            )

            receipt = st.text_input(
                T("receipt_id"),
                e_row["supplier_receipt_id"],
                key=f"receipt_{e_row['expense_id']}"
            )
            total_cost = st.number_input(T("total_cost"), value=float(e_row["total_cost"]))
            monthly_cost = st.number_input(T("monthly_cost"), value=float(e_row["monthly_cost"]))
            payments = st.number_input(T("number_of_payments"), value=int(e_row["num_payments"]))
            ex_type = st.text_input(T("expense_type"), e_row["expense_type"])

            status_options = ["pending", "paid", "cancelled", "מתוכננת"]
            current_status = e_row["status"]
            status = st.selectbox(T("status_label"), status_options,
                                  index=status_options.index(current_status) if current_status in status_options else 0)
            notes = st.text_area(
                T("notes_label"), e_row["notes"] or "", key=f"edit_notes_{e_id}"
            )

            st.markdown("#### " + T("documents"))
            docs_df = get_expense_documents(conn, e_id)
            if docs_df.empty:
                st.info(T("no_documents"))
            else:
                for _, doc in docs_df.iterrows():
                    dcol1, dcol2, dcol3 = st.columns([5, 1, 1])
                    dcol1.write(doc["file_name"])
                    url = get_document_url_from_file(doc["file_url"]) 
                    dcol2.markdown(f"[View]({url})")
                    if dcol3.button("🗑", key=f"del_doc_{doc['doc_id']}"):
                        try:
                            delete_document_by_url(doc["file_url"])
                            delete_expense_document(conn, doc["doc_id"])
                            st.success(T("document_deleted"))
                        except GoogleAPIError as e:
                            st.toast(
                                T("storage_action_failed").format(error=e), icon="⚠️"
                            )
                        st.rerun()

            new_docs = st.file_uploader(
                "📎 " + T("attach_documents"),
                accept_multiple_files=True,
                key=f"edit_upload_{e_id}",
            )
            if new_docs:
                if st.button(T("upload_documents"), key=f"btn_up_{e_id}"):
                    for doc in new_docs:
                        tmp = tempfile.NamedTemporaryFile(delete=False)
                        tmp.write(doc.getbuffer())
                        tmp.close()
                        safe_name = sanitize_filename(doc.name)
                        try:
                            url = upload_document(
                                tmp.name,
                                safe_name,
                                int(e_row["building_id"]),
                                e_row["building_name"],
                                e_row["start_date"],
                            )
                            add_expense_document(
                                conn,
                                int(e_row["building_id"]),
                                e_id,
                                safe_name,
                                url,
                            )
                        except GoogleAPIError as e:
                            st.toast(
                                T("storage_action_failed").format(error=e), icon="⚠️"
                            )
                        finally:
                            os.remove(tmp.name)
                    st.success(T("documents_uploaded"))
                    st.rerun()

            col_update, col_delete = st.columns(2)

            with col_update:
                if st.button("🔄 " + T("edit_expense")):
                    update_expense(conn, e_id, supplier_id, receipt, start_date, end_date, total_cost, monthly_cost,
                                   payments, ex_type, status, notes)
                    st.success(T("expense_updated"))
                    st.rerun()

            with col_delete:
                del_id = e_id
                if st.button("❌ " + T("delete_expense")):
                    delete_expense(conn, del_id)
                    st.warning(T("expense_deleted"))
                    st.rerun()

    # with st.expander("🗑 Delete Expense"):
    #     if df_expenses.empty:
    #         st.info("No expenses to delete for these filters.")
    #     else:
    #         del_id = st.selectbox("Select Expense to Delete", df_expenses["expense_id"], key="delete_expense")
    #         if st.button("Delete Expense"):
    #             delete_expense(conn, del_id)
    #             st.warning("Expense deleted.")
    #             st.rerun()

    with st.expander(T("import_expenses"), expanded=False):
        template = pd.DataFrame([
            {
                "building_id": selected_building_id,
                "supplier_id": suppliers_df["supplier_id"].iloc[0]
                if not suppliers_df.empty
                else 0,
                "supplier_receipt_id": "R-001",
                "start_date": datetime.date.today().strftime("%d/%m/%Y"),
                "num_payments": 1,
                "total_cost": 100,
                "status": "pending",
                "notes": "",
            }
        ])
        st.download_button(
            T("download_template"),
            template.to_csv(index=False).encode("utf-8-sig"),
            file_name="expenses_template.csv",
            mime="text/csv",
        )

        uploaded = st.file_uploader(T("upload_csv"), type=["csv"], key="exp_csv")
        if uploaded is not None:
            try:
                df_upload = pd.read_csv(uploaded)
            except Exception:
                st.error(T("invalid_csv"))
            else:
                required_cols = {
                    "building_id",
                    "supplier_id",
                    "supplier_receipt_id",
                    "start_date",
                    "num_payments",
                    "total_cost",
                    "status",
                }
                if not required_cols.issubset(df_upload.columns):
                    st.error(T("invalid_csv"))
                elif df_upload.empty:
                    st.warning(T("no_expenses_found"))
                else:
                    rename_map = {
                        "building_id": T("building_label"),
                        "supplier_id": T("supplier_label"),
                        "supplier_receipt_id": T("supplier_receipt_id"),
                        "start_date": T("start_date"),
                        "num_payments": T("number_of_payments"),
                        "total_cost": T("total_cost"),
                        "status": T("status_label"),
                    }
                    st.dataframe(df_upload.rename(columns=rename_map))
                    if st.button(T("confirm_import"), key="imp_exp_btn"):
                        inserted, skipped = import_expenses_from_df(conn, df_upload)
                        if inserted:
                            st.success(
                                T("import_expenses_success").format(count=inserted)
                            )
                        if skipped:
                            st.warning(T("some_expenses_skipped"))
                            for receipt, s_date, reason in skipped:
                                st.markdown(f"- **{receipt}** ({s_date}): {reason}")
                        st.rerun()
