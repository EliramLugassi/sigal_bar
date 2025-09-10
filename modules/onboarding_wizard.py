"""First-time setup wizard for populating demo data."""

import streamlit as st
import datetime
import pandas as pd
from modules.db_tools.crud_operations import (
    get_user_by_username,
    get_user_id,
    add_building,
    get_apartments_by_building,
    get_residents_by_building_full,
    set_active_resident,
    add_expense,
    get_buildings,
    get_suppliers,
    get_expenses,
    delete_expense,
    update_expense,
)
from modules.utils.localization import get_translation
from modules.utils.language import setup_language_selector


def render(conn):
    """Guide new users through populating initial data."""
    setup_language_selector(key="language_selector_wizard")
    T = get_translation(st.session_state.get("lang", "en"))
    st.title(T("first_time_setup_title"))
    username = st.session_state.get("username")
    user = get_user_by_username(conn, username)
    if not user:
        st.error(T("user_not_found"))
        return
    step = st.session_state.get("onboarding_step", 1)
    st.markdown(f"### Step {step} of 8")

    completed = st.session_state.get("wizard_completed", {})

    # ----------------- Step 1: Contact Info -----------------
    if step == 1:
        st.subheader(T("update_contact_info"))
        st.info(T("step1_instruction"))
        new_email = st.text_input(T("your_email_label"), value=user[3])
        new_password = st.text_input(T("new_password_label"), type="password")

        if st.button(T("save_contact_info_btn")):
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET email = %s WHERE user_id = %s", (new_email, user[0]))
                if new_password:
                    import bcrypt
                    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                    cur.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (hashed, user[0]))
                conn.commit()
            st.success(T("contact_info_updated"))
            completed[1] = True
            st.session_state.wizard_completed = completed

        if completed.get(1):
            st.info(T("contact_info_step_completed"))


    elif step == 2:

        st.subheader(T("add_first_building"))
        st.info(T("step2_instruction"))
        st.markdown("### " + T("your_buildings_header"))

        user_id = get_user_id(conn, st.session_state["username"])

        with conn.cursor() as cur:

            cur.execute("""

                SELECT b.building_name, b.city, b.street, b.home_number

                FROM buildings b

                JOIN user_buildings ub ON b.building_id = ub.building_id

                WHERE ub.user_id = %s

                ORDER BY b.building_name;

            """, (user_id,))

            rows = cur.fetchall()

        df = pd.DataFrame(rows, columns=["Name", "City", "Street", "Home Number"])

        st.dataframe(df, use_container_width=True)
        name = st.text_input(T("building_name_label"))

        city = st.text_input(T("city_label"))

        street = st.text_input(T("street_label"))

        home_number = st.text_input(T("home_number_label"))

        if st.button(T("add_building_btn")):
            building_id = add_building(conn, name, city, street, home_number)

            # Assign to current user

            user_id = get_user_id(conn, st.session_state["username"])

            with conn.cursor() as cur:
                cur.execute("""

                    INSERT INTO user_buildings (user_id, building_id)

                    VALUES (%s, %s)

                    ON CONFLICT DO NOTHING

                """, (user_id, building_id))

                conn.commit()

            st.success(T("building_added_assigned_you"))

            completed[2] = True

            st.session_state.wizard_completed = completed

            st.rerun()

        if completed.get(2):
            st.info(T("building_step_completed"))

        # 📋 Show summary table




    # ----------------- Step 3: Add Apartments -----------------
    elif step == 3:
        st.subheader(T("add_apartments_title"))
        st.info(T("step3_instruction"))
        df_buildings = get_buildings(conn)
        building_id = int(df_buildings.iloc[-1]["building_id"])
        start_apt = int(st.number_input(T("from_apartment_number"), min_value=1, value=1))
        end_apt = int(st.number_input(T("to_apartment_number"), min_value=start_apt, value=start_apt + 5))
        start_floor = int(st.number_input(T("starting_floor"), step=1, value=0))
        per_floor = int(st.number_input(T("apartments_per_floor"), min_value=1, value=3))

        if st.button(T("submit_bulk_apartments")):
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT apartment_id FROM apartments
                    WHERE building_id = %s AND apartment_number = '0'
                """, (building_id,))
                apt_0 = cur.fetchone()
                if not apt_0:
                    cur.execute("""
                        INSERT INTO apartments (building_id, floor, apartment_number)
                        VALUES (%s, %s, %s) RETURNING apartment_id
                    """, (building_id, 0, '0'))
                    apt_0_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO residents (
                            apartment_id, role, first_name, last_name, phone, email,
                            start_date, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                    """, (
                        apt_0_id, "owner", "System", "Resident", "00000", "system@vaad.com",
                        datetime.date.today()))
                for i, apt_num in enumerate(range(start_apt, end_apt + 1)):
                    floor = int(start_floor + (i // per_floor))
                    cur.execute("""
                        INSERT INTO apartments (building_id, floor, apartment_number)
                        VALUES (%s, %s, %s) RETURNING apartment_id
                    """, (building_id, floor, str(apt_num)))
                    apartment_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO residents (
                            apartment_id, role, first_name, last_name, phone, email,
                            start_date, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                    """, (
                        apartment_id, "owner", "System", "Resident", "00000", "system@vaad.com",
                        datetime.date.today()))
                conn.commit()
            st.success(T("apartments_added"))
            completed[3] = True
            st.session_state.wizard_completed = completed

        if completed.get(3):
            st.info(T("apartments_step_completed"))

    # # ----------------- Step 4: Add Residents -----------------
    # elif step == 4:
    #     st.subheader("👥 Add Residents")
    #     df_buildings = get_buildings(conn)
    #     building_id = int(df_buildings.iloc[-1]["building_id"])
    #     apartments = get_apartments_by_building(conn, building_id)
    #     apt_map = {f"Apt {row['apartment_number']}": row['apartment_id'] for _, row in apartments.iterrows() if row['apartment_number'] != '0'}
    #
    #     apt_label = st.selectbox("Select Apartment", list(apt_map.keys()))
    #     apartment_id = apt_map[apt_label]
    #
    #     first_name = st.text_input("First Name")
    #     last_name = st.text_input("Last Name")
    #     phone = st.text_input("Phone")
    #     email = st.text_input("Email")
    #     role = st.selectbox("Role", ["owner", "renter"])
    #
    #     if st.button("➕ Add Resident"):
    #         with conn.cursor() as cur:
    #             cur.execute("""
    #                 INSERT INTO residents (apartment_id, role, first_name, last_name, phone, email, start_date, is_active)
    #                 VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE)
    #             """, (apartment_id, role, first_name, last_name, phone, email, datetime.date.today()))
    #             conn.commit()
    #         st.success("Resident added.")
    #         completed[4] = True
    #         st.session_state.wizard_completed = completed
    #
    #     if completed.get(4):
    #         st.info("✅ Residents step completed.")

    # ----------------- Step 4: Add Residents -----------------
    elif step == 4:
        st.subheader(T("add_residents_title"))
        st.info(T("step4_instruction"))
        df_buildings = get_buildings(conn)
        building_id = int(df_buildings.iloc[-1]["building_id"])
        apartments = get_apartments_by_building(conn, building_id)
        apt_map = {
            f"{T('apt_header')} {row['apartment_number']}": row['apartment_id']
            for _, row in apartments.iterrows()
            if row['apartment_number'] != '0'
        }

        apt_options = list(apt_map.keys())

        if not apt_options:
            st.warning(T("no_apartments_step3_warning"))
            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                if st.button(T("back_btn")):
                    st.session_state.onboarding_step = step - 1
                    st.rerun()

            with col2:
                if st.button(T("next_btn")):
                    st.session_state.onboarding_step = step + 1
                    st.rerun()

            st.stop()

        apt_label = st.selectbox(T("select_apartment"), apt_options,key="select_apt_1")
        apartment_id = apt_map.get(apt_label)

        if apartment_id is None:
            st.error(T("apartment_select_error"))
            st.stop()

        if st.session_state.get(f"residents_done_{apartment_id}"):
            st.info(T("residents_already_added").format(apt_label=apt_label))
            if st.button(T("delete_residents_for_apartment")):
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE residents
                        SET end_date = CURRENT_DATE,
                            is_active = FALSE
                        WHERE apartment_id = %s
                        """,
                        (apartment_id,),
                    )
                    conn.commit()
                st.success(T("residents_deleted"))
                st.session_state[f"residents_done_{apartment_id}"] = False
                st.rerun()

        st.markdown("---")
        st.markdown("**" + T("renter_details") + "**")
        renter_first_name = st.text_input(T("renter_first_name"))
        renter_last_name = st.text_input(T("renter_last_name"))
        renter_phone = st.text_input(T("renter_phone"))
        renter_email = st.text_input(T("renter_email"))

        same_as_owner = st.checkbox(" " + T("owner_same_as_renter"))

        owner_first_name = owner_last_name = owner_phone = owner_email = ""
        if not same_as_owner:
            st.markdown("**" + T("owner_details") + "**")
            owner_first_name = st.text_input(T("owner_first_name"))
            owner_last_name = st.text_input(T("owner_last_name"))
            owner_phone = st.text_input(T("owner_phone"))
            owner_email = st.text_input(T("owner_email"))

        if st.button(T("add_residents_btn")):
            with conn.cursor() as cur:
                # cur.execute("DELETE FROM residents WHERE apartment_id = %s",
                #             (apartment_id,))  # Replace any existing residents

                cur.execute("""
                    INSERT INTO residents (apartment_id, role, first_name, last_name, phone, email, start_date, is_active)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE)
                """, (apartment_id, "renter", renter_first_name, renter_last_name, renter_phone, renter_email,
                      datetime.date.today()))

                if same_as_owner:
                    cur.execute("""
                        INSERT INTO residents (apartment_id, role, first_name, last_name, phone, email, start_date, is_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE)
                    """, (apartment_id, "owner", renter_first_name, renter_last_name, renter_phone, renter_email,
                          datetime.date.today()))
                else:
                    cur.execute("""
                        INSERT INTO residents (apartment_id, role, first_name, last_name, phone, email, start_date, is_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE)
                    """, (apartment_id, "owner", owner_first_name, owner_last_name, owner_phone, owner_email,
                          datetime.date.today()))

                conn.commit()
            st.success(T("residents_added_for").format(apt_label=apt_label))
            completed[4] = True
            st.session_state.wizard_completed = completed
            st.session_state[f"residents_done_{apartment_id}"] = True

        st.markdown("---")
        st.markdown("### " + T("summary_table_title"))
        summary_df = get_residents_by_building_full(conn, building_id)
        st.dataframe(summary_df[["apartment_number", "first_name", "last_name", "role", "is_active"]].sort_values(
            by="apartment_number"))

        if completed.get(4):
            st.info(T("residents_step_completed"))



    # # ----------------- Step 5: Set Active -----------------
    # elif step == 5:
    #     st.subheader("🟢 Set Active Residents")
    #     df_buildings = get_buildings(conn)
    #     building_id = int(df_buildings.iloc[-1]["building_id"])
    #     df_residents = get_residents_by_building_full(conn, building_id)
    #
    #     for _, row in df_residents.iterrows():
    #         if not row["is_active"]:
    #             btn_label = f"✅ Set {row['first_name']} {row['last_name']} active"
    #             btn_key = f"set_active_{row['resident_id']}"
    #             if st.button(btn_label, key=btn_key):
    #                 set_active_resident(conn, row["resident_id"], row["apartment_id"])
    #                 st.success(f"{row['first_name']} is now active")
    #                 st.rerun()
    #
    #     completed[5] = True
    #     st.session_state.wizard_completed = completed
    #
    #     if completed.get(5):
    #         st.info("✅ Active resident step completed.")
    # ----------------- Step 5: Set Active -----------------
    elif step == 5:
        st.subheader(T("set_active_residents_title"))
        st.info(T("step5_instruction"))
        df_buildings = get_buildings(conn)
        building_id = int(df_buildings.iloc[-1]["building_id"])
        df_residents = get_residents_by_building_full(conn, building_id)

        for _, row in df_residents.iterrows():
            if not row["is_active"]:
                apt_num = row.get("apartment_number", "?")
                name = f"{row['first_name']} {row['last_name']}"
                btn_label = T("set_active_resident_for_apartment").format(name=name, apt_num=apt_num)
                btn_key = f"set_active_{row['resident_id']}"
                if st.button(btn_label, key=btn_key):
                    set_active_resident(conn, row["resident_id"], row["apartment_id"])
                    st.success(T("resident_now_active_for_apartment").format(name=name, apt_num=apt_num))
                    st.rerun()

        completed[5] = True
        st.session_state.wizard_completed = completed

        if completed.get(5):
            st.info(T("active_resident_step_completed"))

    # ----------------- Step 6: Monthly Fees -----------------
    elif step == 6:
        st.subheader(T("set_monthly_fees_title"))
        st.info(T("step6_instruction"))
        df_buildings = get_buildings(conn)
        building_id = int(df_buildings.iloc[-1]["building_id"])
        new_fee = st.number_input(T("new_monthly_fee"), min_value=0.0, step=50.0)

        if st.button(T("apply_fee_btn")):
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE apartment_charge_settings
                    SET monthly_fee = %s
                    WHERE building_id = %s;
                """, (new_fee, building_id))
                conn.commit()
            st.success(T("fees_updated"))
            completed[6] = True
            st.session_state.wizard_completed = completed

        if completed.get(6):
            st.info(T("fees_step_completed"))

    # # ----------------- Step 7: Add Transactions -----------------
    # elif step == 7:
    #     st.subheader("💳 Add Transactions")
    #     st.info("This step can be skipped and completed later via the Transactions page.")
    #     completed[7] = True
    #     st.session_state.wizard_completed = completed
    #
    #     if completed.get(7):
    #         st.info("✅ Transactions step marked as complete.")
    #
    # # ----------------- Step 8: Add Expenses -----------------
    # elif step == 8:
    #     st.subheader("💸 Add First Expense")
    #     df_buildings = get_buildings(conn)
    #     df_suppliers = get_suppliers(conn)
    #
    #     if df_buildings.empty or df_suppliers.empty:
    #         st.warning("You must add at least one building and supplier before continuing.")
    #     else:
    #         b_id = int(df_buildings.iloc[-1]["building_id"])
    #         s_id = int(df_suppliers.iloc[0]["supplier_id"])
    #         receipt = st.text_input("Receipt ID")
    #         start_date = st.date_input("Start Date")
    #         end_date = st.date_input("End Date")
    #         total_cost = st.number_input("Total Cost", min_value=0.0, step=100.0)
    #         monthly_cost = st.number_input("Monthly Cost", min_value=0.0, step=100.0)
    #         payments = int(st.number_input("Number of Payments", min_value=1, step=1))
    #         ex_type = st.text_input("Expense Type")
    #         status = st.selectbox("Status", ["pending", "paid", "cancelled"])
    #         notes = st.text_area("Notes")
    #
    #         if st.button("💾 Save Expense"):
    #             add_expense(conn, b_id, s_id, receipt, start_date, end_date, total_cost, monthly_cost, payments, ex_type, status, notes)
    #             st.success("Expense added.")
    #             completed[8] = True
    #             st.session_state.wizard_completed = completed
    #
    #     if completed.get(8):
    #         st.info("✅ Expenses step completed.")

    # ----------------- Step 7: Add Transactions -----------------
    elif step == 7:
        st.subheader(T("add_transactions_title"))
        st.info(T("step7_instruction"))
        st.info(T("transactions_step_info"))
        df_buildings = get_buildings(conn)
        building_id = int(df_buildings.iloc[-1]["building_id"])
        df_residents = get_residents_by_building_full(conn, building_id)
        df_apartments = get_apartments_by_building(conn, building_id)

        apartment_id = st.selectbox(T("apartment_label"), df_apartments["apartment_number"], key="txn_apt")
        filtered = df_apartments[df_apartments["apartment_number"] == apartment_id]

        if filtered.empty:
            df_apartments = get_apartments_by_building(conn, building_id)

            if df_apartments.empty:
                st.warning(T("no_apartments_step3_warning"))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(T("back_btn")):
                        st.session_state.onboarding_step = step - 1
                        st.rerun()
                with col2:
                    if st.button(T("next_btn")):
                        st.session_state.onboarding_step = step + 1
                        st.rerun()

                return  # Don't continue with step 7 logic

            st.stop()

        apartment_row = filtered.iloc[0]

        apt_id = int(apartment_row["apartment_id"])

        resident_options = df_residents[df_residents["apartment_id"] == apt_id]
        resident_name = st.selectbox(T("resident"), resident_options["first_name"] + " " + resident_options["last_name"],
                                     key="txn_res")
        resident_id = int(
            resident_options[resident_options["first_name"] + " " + resident_options["last_name"] == resident_name][
                "resident_id"].values[0])

        charge_month = st.date_input(T("charge_month_label"))
        payment_date = st.date_input(T("payment_date"))
        amount_paid = st.number_input(T("amount_paid"), min_value=0.0)
        method = st.selectbox(T("payment_method"), ["cash", "credit", "bank transfer", "other"])

        if st.button(T("save_transaction_btn")):
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO transactions (apartment_id, resident_id, charge_month, payment_date, amount_paid, method)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (apt_id, resident_id, charge_month, payment_date, amount_paid, method))
                conn.commit()
            st.success(T("transaction_added"))
            completed[7] = True
            st.session_state.wizard_completed = completed

        # Optional: display transactions table
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.transaction_id, a.apartment_number, r.first_name || ' ' || r.last_name AS resident_name,
                       t.charge_month, t.payment_date, t.amount_paid, t.method
                FROM transactions t
                JOIN apartments a ON t.apartment_id = a.apartment_id
                JOIN residents r ON t.resident_id = r.resident_id
                WHERE a.building_id = %s
                ORDER BY t.payment_date DESC
            """, (building_id,))
            df_txns = pd.DataFrame(cur.fetchall(),
                                   columns=["ID", "Apartment", "Resident", "Charge Month", "Payment Date", "Amount",
                                            "Method"])
            st.markdown("### " + T("transactions_summary_title"))
            st.dataframe(df_txns)

        if completed.get(7):
            st.info(T("transactions_step_completed"))


    # ----------------- Step 8: Add Expenses -----------------
    elif step == 8:
        st.subheader(T("add_expenses_title"))
        st.info(T("step8_instruction"))
        st.info(T("expenses_step_info"))

        df_buildings = get_buildings(conn)
        df_suppliers = get_suppliers(conn)

        if df_buildings.empty or df_suppliers.empty:
            st.warning(T("building_supplier_warning"))
        else:
            b_id = int(df_buildings.iloc[-1]["building_id"])
            supplier_options = {s["supplier_name"]: s["supplier_id"] for _, s in df_suppliers.iterrows()}

            with st.form("add_expense_form", clear_on_submit=True):
                selected_supplier = st.selectbox(T("supplier_label"), list(supplier_options.keys()))
                s_id = supplier_options[selected_supplier]

                receipt = st.text_input(T("receipt_id"))
                start_date = st.date_input(T("start_date"))
                end_date = st.date_input(T("end_date"))
                total_cost = st.number_input(T("total_cost"), min_value=0.0, step=100.0)
                monthly_cost = st.number_input(T("monthly_cost"), min_value=0.0, step=100.0)
                payments = int(st.number_input(T("number_of_payments"), min_value=1, step=1))
                ex_type = st.text_input(T("expense_type"))
                status = st.selectbox(T("status_label"), ["pending", "paid", "cancelled"])
                notes = st.text_area(T("notes_label"))

                submitted = st.form_submit_button(T("save_expense_btn"))
                if submitted:
                    add_expense(
                        conn, b_id, s_id, receipt, start_date, end_date,
                        total_cost, monthly_cost, payments, ex_type, status, notes
                    )
                    st.success(T("expense_added"))
                    completed[8] = True
                    st.session_state.wizard_completed = completed

            st.markdown("### " + T("expense_summary_title"))
            df_expenses = get_expenses(conn)

            # Safely extract building name for current building
            building_name = df_buildings[df_buildings["building_id"] == b_id]["building_name"].values[0]
            df_expenses = df_expenses[df_expenses["building_name"] == building_name]

            for _, row in df_expenses.iterrows():
                with st.expander(f"🧾 {row['supplier_receipt_id']} – {row['supplier_name']}"):

                    # Ensure the supplier_id from row is an int and exists in the dropdown
                    supplier_ids = list(supplier_options.values())
                    try:
                        supplier_index = supplier_ids.index(int(row["supplier_id"]))
                    except (ValueError, KeyError):
                        supplier_index = 0  # fallback if supplier_id is not found

                    with st.form(f"edit_expense_{row['expense_id']}"):
                        new_supplier = st.selectbox(
                            "Supplier",
                            list(supplier_options.keys()),
                            index=supplier_index,
                            key=f"supp_{row['expense_id']}"
                        )
                        new_supplier_id = supplier_options[new_supplier]
                        new_receipt_id = st.text_input(T("supplier_receipt_id"), row["supplier_receipt_id"],
                                                       key=f"rcpt_{row['expense_id']}")
                        new_start = st.date_input(T("start_date"), row["start_date"], key=f"start_{row['expense_id']}")
                        new_end = st.date_input(T("end_date"), row["end_date"], key=f"end_{row['expense_id']}")
                        new_total = st.number_input(T("total_cost"), value=row["total_cost"],
                                                    key=f"ttl_{row['expense_id']}")
                        new_monthly = st.number_input(T("monthly_cost"), value=row["monthly_cost"],
                                                      key=f"mnt_{row['expense_id']}")
                        new_payments = st.number_input(T("number_of_payments"), value=row["num_payments"], step=1,
                                                       key=f"pmt_{row['expense_id']}")
                        new_type = st.text_input(T("expense_type"), row["expense_type"], key=f"type_{row['expense_id']}")
                        new_status = st.selectbox(
                            T("status_label"), ["pending", "paid", "cancelled"],
                            index=["pending", "paid", "cancelled"].index(row["status"]),
                            key=f"sts_{row['expense_id']}"
                        )
                        new_notes = st.text_area(T("notes_label"), row["notes"] or "", key=f"nts_{row['expense_id']}")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button(T("update")):
                                update_expense(
                                    conn,
                                    row["expense_id"],
                                    new_supplier_id,
                                    new_receipt_id,
                                    new_start,
                                    new_end,
                                    new_total,
                                    new_monthly,
                                    new_payments,
                                    new_type,
                                    new_status,
                                    new_notes
                                )
                                st.success(T("expense_updated"))
                                st.rerun()
                        with col2:
                            if st.form_submit_button(T("delete")):
                                delete_expense(conn, row["expense_id"])
                                st.warning(T("expense_deleted"))
                                st.rerun()

            st.markdown("---")
            if st.button(T("finish_setup_btn")):
                st.session_state.wizard_completed[8] = True
                st.success(T("setup_complete_redirecting"))
                st.experimental_set_query_params(page="Dashboard")
                st.rerun()

    # ----------------- Navigation -----------------
    col1, col2 = st.columns(2)
    with col1:
        if step > 1 and st.button(T("back_btn")):
            st.session_state.onboarding_step = step - 1
            st.rerun()
    with col2:
        if step < 8 and st.button(T("next_phase_btn")):
            st.session_state.onboarding_step = step + 1
            st.rerun()
        elif step == 8 and completed.get(8):
            st.success(T("setup_complete_redirecting"))
            st.session_state.pop("onboarding_step", None)
            st.rerun()
