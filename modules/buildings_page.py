"""Buildings management page.

Allows admins to view buildings and manage apartments, residents and
fees. The ``render`` function displays the building dashboard within
the Streamlit application.
"""

import streamlit as st
import datetime
import pandas as pd
from crud_operations import (
    get_user_id,
    get_user_role,
    get_buildings_by_user,
    get_residents_by_building_full,
    get_apartments_by_building,
    set_active_resident,
    add_building,
    update_building,
    delete_building,
    generate_expected_charges,
    upsert_bulk_apartment_fees,
    deactivate_resident,
)
from email_utils import send_invoice_email

def render(conn, T):
    """Display the buildings dashboard and related management tools."""
    st.header(T("buildings"))

    user_id = get_user_id(conn, st.session_state.username)
    user_role = get_user_role(conn, st.session_state.username)
    df_buildings = get_buildings_by_user(conn, user_id, user_role)

    if df_buildings.empty:
        st.warning(T("not_assigned_building_admin"))
        st.stop()

    with st.expander(T("view_assigned_buildings")):
        rename_map = {
            "building_name": T("building_name_label"),
            "city": T("city_label"),
            "street": T("street_label"),
            "home_number": T("home_number_label"),
        }
        display_cols = list(rename_map.keys())
        st.dataframe(
            df_buildings[display_cols].rename(columns=rename_map)
        )

    building_options = df_buildings.set_index('building_id')['building_name'].to_dict()
    selected_building_id = st.selectbox(
        T("select_building_manage"),
        options=list(building_options.keys()),
        format_func=lambda x: building_options[x],
        key="details_building"
    )

    # Only show currently active residents
    df_residents_full = get_residents_by_building_full(
        conn,
        selected_building_id,
        active_only=True,
    )
    apartments_df = get_apartments_by_building(conn, selected_building_id)
    apt_map = {
        f"Floor {row['floor']} – {T('apt_header')} {row['apartment_number']}": row["apartment_id"]
        for _, row in apartments_df.iterrows()
    }

    with st.expander(T("view_set_active_residents"), expanded=True):
        st.markdown(f"### {T('residents_in_building').format(building=building_options[selected_building_id])}")
        if df_residents_full.empty:
            st.info(T("no_residents_found"))
        else:
            st.markdown(T("click_set_active_hint"))

            # 🧩 7 columns: apt, floor, name, role, phone, email, button
            header_cols = st.columns([1, 1, 2, 1, 2, 2, 1])
            headers = [
                T("apt_header"), T("floor_header"), T("name_header"),
                T("role"), T("phone_label"), T("email"), ""
            ]
            for col, text in zip(header_cols, headers):
                col.markdown(f"**{text}**")

            for _, row in df_residents_full.iterrows():
                cols = st.columns([1, 1, 2, 1, 2, 2, 1])
                cols[0].write(row["apartment_number"])
                cols[1].write(f"{int(row['floor'])}" if pd.notna(row["floor"]) else "")
                cols[2].write(f"{row['first_name']} {row['last_name']}")
                cols[3].write(row["role"])
                cols[4].write(row["phone"])
                cols[5].write(row["email"])

                if not row["is_active"]:
                    if cols[6].button("✅ " + T("set_active"), key=f"set_active_{row['resident_id']}"):
                        set_active_resident(conn, row["resident_id"], row["apartment_id"])
                        st.success(
                            T("resident_now_active").format(first_name=row['first_name'], last_name=row['last_name']))
                        st.rerun()
                else:
                    cols[6].write("🟢 " + T("active_status"))

    with st.expander(T("update_monthly_fees_title")):
        st.markdown(T("update_monthly_fees_desc"))

        # Select year to apply
        selected_year = st.selectbox("📆 " + T("select_year"), list(range(2023, datetime.date.today().year + 6)),
                                     index=2)

        # Choose update mode
        update_mode = st.radio(T("choose_update_mode"), [T("bulk_update"), T("individual_update")])

        # BULK UPDATE
        if update_mode == T("bulk_update"):
            st.markdown("### " + T("bulk_update_all_fees"))
            new_fee = st.number_input("💰 " + T("new_monthly_fee"), min_value=0.0, step=50.0, key="bulk_fee")

            if st.button(T("apply_bulk_update")):
                upsert_bulk_apartment_fees(conn, selected_building_id, new_fee)
                st.success(T("bulk_update_success").format(fee=f"{new_fee:.0f}"))

        # INDIVIDUAL UPDATE
        else:
            st.markdown("### " + T("individual_fee_updates"))
            apts_df = get_apartments_by_building(conn, selected_building_id)

            for _, row in apts_df.iterrows():
                col1, col2, col3 = st.columns([1, 1, 2])
                col1.write(f"{T('apt_header')} {row['apartment_number']}")
                fee_input = col2.number_input(
                    T("fee_label"),
                    min_value=0.0,
                    step=50.0,
                    key=f"apt_fee_{row['apartment_id']}"
                )

                if col3.button(T("update"), key=f"update_fee_{row['apartment_id']}"):
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO apartment_charge_settings (apartment_id, building_id, monthly_fee, charge_type)
                            VALUES (%s, %s, %s, 'monthly fee')
                            ON CONFLICT (apartment_id) DO UPDATE
                            SET monthly_fee = EXCLUDED.monthly_fee;
                        """, (row['apartment_id'], selected_building_id, fee_input))
                        conn.commit()
                    st.success(T("update_fee_success").format(apartment=row['apartment_number']))

        # CHARGE GENERATION BUTTON
        if st.button(T("generate_expected_charges_for_year").format(year=selected_year)):
            for month in range(1, 13):
                target_month = datetime.date(selected_year, month, 1)
                generate_expected_charges(conn, selected_building_id, target_month)
            conn.commit()
            st.success(T("expected_charges_generated").format(year=selected_year))
    with st.expander(T("add_resident_expander")):
        if not apt_map:
            st.info(T("no_apartments_found"))
        else:
            selected_apt = st.selectbox(T("select_apartment"), list(apt_map.keys()), key="add_resident_apt")
            apartment_id = apt_map[selected_apt]

            first_name = st.text_input(T("first_name_label"), key="add_resident_first_name")
            last_name = st.text_input(T("last_name_label"), key="add_resident_last_name")
            phone = st.text_input(T("phone_label"), key="add_resident_phone")
            email = st.text_input(T("email"), key="add_resident_email")
            role = st.selectbox(T("role"), ["owner", "renter"], key="add_resident_role")
            start_date = st.date_input(T("start_date"), value=datetime.date.today(), key="add_resident_start")

            if st.button(T("add_resident_btn"), key="add_resident_btn"):
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO residents (apartment_id, role, first_name, last_name, phone, email, start_date, is_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,False)
                    """, (apartment_id, role, first_name, last_name, phone, email, start_date))
                    conn.commit()
                st.success(T("resident_added"))
                st.rerun()

    with st.expander(T("edit_resident_expander")):
        if df_residents_full.empty:
            st.info(T("no_residents_available"))
        else:
            resident_map = {
                f"{T('apt_header')} {row['apartment_number']} – {row['first_name']} {row['last_name']}": row["resident_id"]
                for _, row in df_residents_full.iterrows()
            }
            selected_resident = st.selectbox(T("select_resident"), list(resident_map.keys()), key="edit_resident_select")
            resident_id = resident_map[selected_resident]
            resident_row = df_residents_full[df_residents_full["resident_id"] == resident_id].iloc[0]

            new_first_name = st.text_input(T("first_name_label"), resident_row["first_name"], key="edit_first_name")
            new_last_name = st.text_input(T("last_name_label"), resident_row["last_name"], key="edit_last_name")
            new_phone = st.text_input(T("phone_label"), resident_row["phone"], key="edit_phone")
            new_email = st.text_input(T("email"), resident_row["email"], key="edit_email")
            new_role = st.selectbox(
                T("role"), ["owner", "renter"], index=0 if resident_row["role"] == "owner" else 1, key="edit_role"
            )
            new_start = st.date_input(T("start_date"), value=resident_row["start_date"], key="edit_start_date")
            new_end = (
                st.date_input(T("end_date"), value=resident_row["end_date"])
                if resident_row["end_date"]
                else None
            )

            if st.button(T("update_resident_btn"), key="update_resident_btn"):
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE residents
                        SET first_name = %s,
                            last_name = %s,
                            phone = %s,
                            email = %s,
                            role = %s,
                            start_date = %s,
                            end_date = %s
                        WHERE resident_id = %s
                        """,
                        (
                            new_first_name,
                            new_last_name,
                            new_phone,
                            new_email,
                            new_role,
                            new_start,
                            new_end,
                            resident_id,
                        ),
                    )
                    conn.commit()
                st.success(T("resident_updated"))
                st.rerun()

    with st.expander(T("delete_resident_expander")):
        if df_residents_full.empty:
            st.info(T("no_residents_to_delete"))
        else:
            delete_map = {
                f"{T('apt_header')} {row['apartment_number']} – {row['first_name']} {row['last_name']}": row["resident_id"]
                for _, row in df_residents_full.iterrows()
            }
            selected_to_delete = st.selectbox(T("select_resident_to_delete"), list(delete_map.keys()), key="delete_resident_select")
            if st.button(T("delete_resident_btn"), key="delete_resident_btn"):
                deactivate_resident(conn, delete_map[selected_to_delete])
                st.warning(T("resident_deleted"))
                st.rerun()

    with st.expander(T("send_message_residents_expander")):
        emails = df_residents_full["email"].dropna().tolist()
        subject = st.text_input(T("subject_label"), key="email_subject")
        body = st.text_area(T("message_body"), key="email_body")
        if st.button(T("send_email_all_residents"), key="send_emails_btn"):
            for email in emails:
                send_invoice_email(email, subject, body)
            st.success(T("emails_sent_residents"))

    with st.expander(T("edit_building_expander")):
        edit_building_id = st.selectbox(
            T("select_building_edit"),
            options=list(building_options.keys()),
            format_func=lambda x: building_options[x],
            key="edit_building_select",
        )
        row = df_buildings[df_buildings["building_id"] == edit_building_id].iloc[0]

        new_name = st.text_input(T("building_name_label"), row["building_name"], key="edit_building_name")
        new_city = st.text_input(T("city_label"), row["city"], key="edit_building_city")
        new_street = st.text_input(T("street_label"), row["street"], key="edit_building_street")
        new_home = st.text_input(T("home_number_label"), row["home_number"], key="edit_building_home")
        new_postal = st.text_input(T("postal_code_label"), row.get("postal_code", ""), key="edit_postal")
        new_code = st.text_input(T("building_code_label"), row.get("building_code", ""), key="edit_building_code")
        new_vaad_name = st.text_input(T("vaad_name_label"), row.get("vaad_name", ""), key="edit_vaad_name")
        new_bank_name = st.text_input(T("bank_name_label"), row.get("bank_name", ""), key="edit_bank_name")
        new_bank_branch = st.text_input(T("bank_branch_label"), row.get("bank_branch", ""), key="edit_bank_branch")
        new_bank_account = st.text_input(T("bank_account_label"), row.get("bank_account", ""), key="edit_bank_account")
        new_bank_number = st.text_input(T("bank_number_label"), row.get("bank_number", ""), key="edit_bank_number")
        new_vaad_rep = st.text_input(T("vaad_representative_label"), row.get("vaad_representative", ""), key="edit_vaad_rep")
        new_contact_phone = st.text_input(T("contact_phone_label"), row.get("contact_phone", ""), key="edit_contact_phone")
        new_contact_email = st.text_input(T("contact_email_label"), row.get("contact_email", ""), key="edit_contact_email")

        if st.button(T("update_building_btn"), key="update_building_btn"):
            update_building(
                conn,
                edit_building_id,
                new_name,
                new_city,
                new_street,
                new_home,
                new_postal,
                new_code,
                new_vaad_name,
                new_bank_name,
                new_bank_branch,
                new_bank_account,
                new_bank_number,
                new_vaad_rep,
                new_contact_phone,
                new_contact_email,
            )
            st.success(T("building_updated"))
            st.rerun()

    with st.expander(T("add_new_building_expander")):
        with st.form("Add Building"):
            name = st.text_input(T("building_name_label"), key="building_name")
            city = st.text_input(T("city_label"), key="building_city")
            street = st.text_input(T("street_label"), key="building_street")
            home_number = st.text_input(T("home_number_label"), key="building_home_number")
            submitted = st.form_submit_button(T("add_building_btn"))

            if submitted:
                add_building(conn, name, city, street, home_number)
                st.success(T("building_added"))
                st.rerun()

    with st.expander(T("bulk_add_apartments_expander"), expanded=False):
        st.markdown(T("bulk_add_apartments_desc"))

        start_apt = st.number_input(T("from_apartment_number"), min_value=1, value=1)
        end_apt = st.number_input(T("to_apartment_number"), min_value=start_apt, value=start_apt + 5)
        start_floor = st.number_input(T("starting_floor"), step=1, value=0)
        per_floor = st.number_input(T("apartments_per_floor"), min_value=1, value=3)

        if st.button(T("submit_bulk_apartments")):
            with conn.cursor() as cur:
                # 🔒 Ensure apartment 0 exists (only once per building)
                cur.execute("""
                    SELECT apartment_id FROM apartments
                    WHERE building_id = %s AND apartment_number = '0'
                """, (selected_building_id,))
                apt_0 = cur.fetchone()

                if not apt_0:
                    cur.execute("""
                        INSERT INTO apartments (building_id, floor, apartment_number)
                        VALUES (%s, %s, %s)
                        RETURNING apartment_id
                    """, (selected_building_id, 0, '0'))
                    apt_0_id = cur.fetchone()[0]

                    cur.execute("""
                        INSERT INTO residents (
                            apartment_id, role, first_name, last_name, phone, email,
                            start_date, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        apt_0_id,
                        "owner",
                        "System",
                        "Resident",
                        "00000",
                        "system@vaad.com",
                        datetime.date.today(),
                        True
                    ))

                # 🚀 Bulk add apartments and system residents
                for i, apt_num in enumerate(range(start_apt, end_apt + 1)):
                    floor = start_floor + (i // per_floor)

                    cur.execute("""
                        INSERT INTO apartments (building_id, floor, apartment_number)
                        VALUES (%s, %s, %s)
                        RETURNING apartment_id
                    """, (selected_building_id, floor, str(apt_num)))
                    apartment_id = cur.fetchone()[0]

                    cur.execute("""
                        INSERT INTO residents (
                            apartment_id, role, first_name, last_name, phone, email,
                            start_date, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        apartment_id,
                        "owner",
                        "System",
                        "Resident",
                        "00000",
                        "system@vaad.com",
                        datetime.date.today(),
                        True
                    ))

                conn.commit()

            st.success(T("apartments_added_success").format(start=start_apt, end=end_apt))
            st.rerun()

    with st.expander(T("delete_building_expander")):
        building_id = st.selectbox(
            T("select_building_delete"),
            options=list(building_options.keys()),
            format_func=lambda x: building_options[x],
            key="delete_building_select"
        )
        if st.button(T("delete_building_btn"), key="delete_building_btn"):
            delete_building(conn, building_id)
            st.success(T('building_deleted').format(building=building_options[building_id]))
            st.rerun()
