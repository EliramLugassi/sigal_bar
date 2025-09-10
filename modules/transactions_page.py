"""Page for viewing and adjusting payment transactions."""

import streamlit as st
import pandas as pd
from datetime import date
from modules.db_tools.crud_operations import (
    get_paid_transactions,
    get_apartments_by_building, get_expected_charge_years
)
from modules.db_tools.filters import get_allowed_building_df

def render(conn, T):
    """Display and edit payment transactions for a building."""
    st.header("💳 " + T("transactions_management"))

    # 🕽️ Top Filters
    buildings_df = get_allowed_building_df(conn)
    building_map = {row["building_name"]: row["building_id"] for _, row in buildings_df.iterrows()}
    selected_building_name = st.selectbox("🏢 " + T("select_building"), list(building_map.keys()))
    selected_building_id = building_map[selected_building_name]

    apartments_df = get_apartments_by_building(conn, selected_building_id)
    apartments_df = apartments_df.sort_values(by="apartment_number", key=lambda x: x.astype(str).str.zfill(4))
    apt_map = {str(row["apartment_number"]): row["apartment_id"] for _, row in apartments_df.iterrows()}
    selected_apt = st.selectbox("🏠 " + T("apartment"), ["All"] + list(apt_map.keys()))
    selected_apt_id = apt_map.get(selected_apt) if selected_apt != "All" else None

    col1, col2 = st.columns(2)
    year = col1.selectbox("📅 " + T("year"), list(range(2023, date.today().year + 1)), index=1)
    month = col2.selectbox("🗓 " + T("month"), list(range(1, 13)), index=date.today().month - 1)
    selected_month = date(year, month, 1)

    # 🧾 Transactions Table
    df = get_paid_transactions(conn, building_id=selected_building_id, selected_month=selected_month)
    if selected_apt_id:
        df = df[df["apartment_id"] == selected_apt_id]

    st.subheader("📄 " + T("transactions"))

    with st.expander(T("view_transactions_table"), expanded=False):
        if df.empty:
            st.info(T("no_paid_transactions"))
        else:
            df = df.drop(columns=["apartment_id", "resident_id"], errors="ignore")
            rename_map = {
                "building_name": T("building_name_label"),
                "apartment_number": T("apartment"),
                "resident_name": T("resident_name"),
                "email": T("email"),
                "charge_month": T("charge_month_label"),
                "payment_date": T("payment_date"),
                "amount_paid": T("amount_paid"),
                "method": T("payment_method"),
            }
            st.dataframe(df.rename(columns=rename_map))

    # 💰 Total Paid Card (filtered)
    total_paid = df["amount_paid"].sum()
    label = T("total_amount_paid") if T("total_amount_paid") != "total_amount_paid" else "Total Amount Paid"

    st.markdown(f"""
    <div style='
        background-color: #f0f9ff;
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
        💰 {label}: ₪ {total_paid:,.0f}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    with st.expander(T("edit_or_delete_transaction"), expanded=False):
        st.subheader(T("edit_or_delete_transaction"))

        tx_options = {
            f"#{row.transaction_id} — {T('apt_header')} {row.apartment_number} — {row.payment_date.strftime('%Y-%m-%d')} — ₪{row.amount_paid}":
                row.transaction_id
            for _, row in df.iterrows()
        }

        selected_tx_label = st.selectbox(T("select_transaction"), list(tx_options.keys()))

        if selected_tx_label:
            selected_tx_id = tx_options[selected_tx_label]
            tx_row = df[df["transaction_id"] == selected_tx_id].iloc[0]

            with st.form("edit_tx_form"):
                new_payment_date = st.date_input(T("payment_date"), value=tx_row["payment_date"])
                new_amount = st.number_input(T("amount_paid"), value=float(tx_row["amount_paid"]), step=10.0)

                methods = ["Cash", "Bank Transfer", "Check"]
                method_cap = tx_row["method"].strip().title()
                new_method = st.selectbox(
                    T("payment_method"),
                    methods,
                    index=methods.index(method_cap) if method_cap in methods else 0
                )

                col1, col2 = st.columns(2)
                update_clicked = col1.form_submit_button(T("update"))
                delete_clicked = col2.form_submit_button(T("delete"))

                if update_clicked:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE transactions
                            SET payment_date = %s, amount_paid = %s, method = %s
                            WHERE transaction_id = %s
                        """, (new_payment_date, new_amount, new_method, selected_tx_id))
                        conn.commit()
                    st.success(T("transaction_updated"))
                    st.rerun()

                elif delete_clicked:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM transactions WHERE transaction_id = %s", (selected_tx_id,))
                        conn.commit()
                    st.warning(T("transaction_deleted"))
                    st.rerun()
        else:
            st.info(T("select_transaction_prompt"))

    with st.expander(T("add_new_transaction"), expanded=False):
        st.subheader(T("add_new_transaction"))

        apt_options = {
            row["apartment_id"]: row["apartment_number"]
            for _, row in apartments_df.iterrows()
        }

        apt_id = st.selectbox(
            T("select_apartment"),
            options=list(apt_options.keys()),
            format_func=lambda x: f"{T('apt_header')} {apt_options[x]}"
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT resident_id, first_name, last_name
                FROM residents
                WHERE apartment_id = %s
                  AND is_active = TRUE
                  AND end_date IS NULL
                """,
                (apt_id,),
            )
            res = cur.fetchone()

        default_fee = 0.0
        with conn.cursor() as cur:
            cur.execute("""
                SELECT monthly_fee FROM apartment_charge_settings
                WHERE apartment_id = %s
            """, (apt_id,))
            fee_result = cur.fetchone()
            if fee_result:
                default_fee = float(fee_result[0])

        with st.form("add_tx_form"):
            charge_month = st.date_input(T("month_being_paid_for"), value=date.today().replace(day=1))
            payment_date = st.date_input(T("payment_date_made"), value=date.today())
            amount_paid = st.number_input(T("amount_paid"), min_value=0.0, value=default_fee, step=10.0)
            method = st.selectbox(T("payment_method"), ["Cash", "Bank Transfer", "Check"])

            submitted = st.form_submit_button(T("add_transaction_btn"))

            if submitted:
                if not res:
                    st.error(T("no_active_resident"))
                else:
                    resident_id, first_name, last_name = res
                    with conn.cursor() as cur:

                        cur.execute("""
                            INSERT INTO transactions (
                                building_id, apartment_id, resident_id,
                                charge_month, payment_date,
                                amount_paid, method
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """, (
                            selected_building_id, apt_id, resident_id,
                            charge_month, payment_date,
                            amount_paid, method
                        ))
                        conn.commit()
                        st.success(T("transaction_added_for").format(first_name=first_name, last_name=last_name))
                        st.rerun()
    from modules.db_tools.crud_operations import (
        get_unpaid_apartments_for_period,
        insert_bulk_transactions,
        has_expected_charges_for_period,
        import_transactions_from_df,
    )

    with st.expander(T("bulk_insert_transactions"), expanded=False):
        st.markdown(T("bulk_insert_hint"))

        col1, col2 = st.columns(2)
        valid_years = get_expected_charge_years(conn)
        if not valid_years:
            st.warning(T("no_charge_data"))
            st.stop()

        bulk_year = col1.selectbox(T("year_being_paid_for"), valid_years)

        bulk_months = col2.multiselect(
            T("months_being_paid_for"),
            options=list(range(1, 13)),
            format_func=lambda m: date(1900, m, 1).strftime('%B')
        )

        bulk_payment_date = st.date_input(T("payment_received_on"), value=date.today(), key="bulk_payment_date")
        bulk_method = st.selectbox(T("payment_method"), ["Cash", "Bank Transfer", "Check"], key="bulk_method")

        if bulk_months:
            df_unpaid_all = get_unpaid_apartments_for_period(conn, selected_building_id, bulk_year, bulk_months)

            if df_unpaid_all.empty:
                if not has_expected_charges_for_period(conn, selected_building_id, bulk_year, bulk_months):
                    st.warning(T("no_expected_charges_selected_months"))
                else:
                    st.info(T("all_apartments_paid_selected_months"))
            else:
                # 🔧 Ensure month_num is an integer (fixes float -> int issue)
                df_unpaid_all["month_num"] = df_unpaid_all["month_num"].astype(int)

                # Remove apartment 0 if present and get unique apartments
                # Apartment numbers sometimes come back as floats or strings
                # Normalize to integers so apartment 0 is reliably filtered out
                df_unpaid_all["apartment_number"] = (
                    pd.to_numeric(df_unpaid_all["apartment_number"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                )
                df_unpaid_all = df_unpaid_all[df_unpaid_all["apartment_number"] != 0]

                # Get unique apartments that have unpaid months in the selected period
                unique_apts = df_unpaid_all.drop_duplicates(subset="apartment_id")

                apt_options = {
                    f"{T('apt_header')} {row['apartment_number']}": row["apartment_id"]
                    for _, row in unique_apts.sort_values("apartment_number").iterrows()
                }

                # Remove apartments that were previously selected but are no longer available
                current_selected = st.session_state.get("bulk_selected_apartments", [])
                st.session_state.bulk_selected_apartments = [
                    label for label in current_selected if label in apt_options
                ]

                def update_bulk_apartment_selection():
                    """Toggle selection of all apartments for bulk insertion."""
                    if st.session_state.get("bulk_select_all"):
                        st.session_state.bulk_selected_apartments = list(apt_options.keys())
                    else:
                        st.session_state.bulk_selected_apartments = []

                select_all = st.checkbox(
                    T("select_all_apartments"),
                    key="bulk_select_all",
                    on_change=update_bulk_apartment_selection,
                )

                selected_labels = st.multiselect(
                    T("select_apartments"),
                    list(apt_options.keys()),
                    key="bulk_selected_apartments",
                )

                if st.button(T("insert_transactions")):
                    # Map apartment_id to apartment_number for clarity
                    apt_number_map = {
                        row["apartment_id"]: row["apartment_number"]
                        for _, row in df_unpaid_all.iterrows()
                    }

                    selected_apartment_ids = [apt_options[label] for label in selected_labels]

                    selected_pairs = []
                    for apt_id in selected_apartment_ids:
                        months_unpaid = df_unpaid_all[df_unpaid_all["apartment_id"] == apt_id]["month_num"].tolist()
                        for m in months_unpaid:
                            selected_pairs.append((apt_id, date(bulk_year, int(m), 1)))

                    inserted, skipped = insert_bulk_transactions(
                        conn, selected_building_id, selected_pairs, bulk_payment_date, bulk_method
                    )

                    if inserted > 0:
                        st.success(T("transactions_inserted").format(count=inserted))

                    if skipped:
                        st.warning(T("some_transactions_skipped"))
                        for apartment_id, charge_month, reason in skipped:
                            apt_number = apt_number_map.get(apartment_id, f"ID {apartment_id}")
                            st.markdown(
                                f"- **{T('apt_header')} {apt_number}** for **{charge_month.strftime('%B %Y')}**: {reason}"
                            )
                    else:
                        st.rerun()

        else:
            st.info(T("please_select_at_least_one_month"))

    with st.expander(T("import_transactions"), expanded=False):
        template = pd.DataFrame(
            [
                {
                    "building_id": selected_building_id,
                    "apartment_number": 1,
                    "charge_month": date.today().replace(day=1).strftime("%d/%m/%Y"),
                    "payment_date": date.today().strftime("%d/%m/%Y"),
                    "amount_paid": 100,
                    "method": "Cash",
                }
            ]
        )
        st.download_button(
            T("download_template"),
            template.to_csv(index=False).encode("utf-8-sig"),
            file_name="transactions_template.csv",
            mime="text/csv",
        )

        uploaded = st.file_uploader(T("upload_csv"), type=["csv"])
        if uploaded is not None:
            try:
                df_upload = pd.read_csv(uploaded)
            except Exception:
                st.error(T("invalid_csv"))
            else:
                required_cols = {
                    "building_id",
                    "apartment_number",
                    "charge_month",
                    "payment_date",
                    "amount_paid",
                    "method",
                }
                if not required_cols.issubset(df_upload.columns):
                    st.error(T("invalid_csv"))
                elif df_upload.empty:
                    st.warning(T("no_paid_transactions"))
                else:
                    rename_map = {
                        "building_id": T("building_label"),
                        "apartment_number": T("apartment"),
                        "charge_month": T("charge_month_label"),
                        "payment_date": T("payment_date"),
                        "amount_paid": T("amount_paid"),
                        "method": T("payment_method"),
                    }
                    st.dataframe(df_upload.rename(columns=rename_map))
                    if st.button(T("confirm_import")):
                        inserted, skipped = import_transactions_from_df(conn, df_upload)
                        if inserted:
                            st.success(T("import_success").format(count=inserted))
                        if skipped:
                            st.warning(T("some_transactions_skipped"))
                            for apt, charge_month, reason in skipped:
                                parsed = pd.to_datetime(charge_month, dayfirst=True, errors="coerce")
                                if pd.notna(parsed):
                                    display_month = parsed.strftime('%B %Y')
                                else:
                                    display_month = str(charge_month)
                                st.markdown(
                                    f"- **{T('apt_header')} {apt}** for **{display_month}**: {reason}"
                                )
                        st.rerun()



