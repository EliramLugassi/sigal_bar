"""Generate invoices for residents and send them via email."""

import streamlit as st
import datetime
from modules.db_tools.crud_operations import get_paid_transactions, create_invoice, log_invoice_send
from modules.utils.pdf_generator import generate_invoice_pdf
from modules.utils.localization import translate_payment_method
from modules.utils.email_utils import send_invoice_email
import base64
import os
from modules.db_tools.filters import get_allowed_building_df

def render(conn, T):
    """Display invoice generation options for a selected building."""
    st.header("📩 " + T("send_invoices_title"))

    buildings_df = get_allowed_building_df(conn)
    building_options = {
        row["building_name"]: row["building_id"] for _, row in buildings_df.iterrows()
    }

    selected_building_name = st.selectbox("🏢 " + T("select_building"), list(building_options.keys()))
    selected_building_id = building_options[selected_building_name]

    if selected_building_id is None:
        st.warning(T("please_select_building"))
        st.stop()

    today = datetime.date.today()
    col1, col2 = st.columns(2)
    year = col1.selectbox("📅 " + T("year"), list(range(2023, today.year + 2)), index=1)
    month = col2.selectbox("🗓 " + T("month"), list(range(1, 13)), index=today.month - 1)
    selected_month = datetime.date(year, month, 1)

    df_paid = get_paid_transactions(conn, selected_building_id, selected_month)

    with st.expander("📤 " + T("send_selected_invoices")):
        selected_rows = st.multiselect(
            T("select_apartments_send"),
            options=df_paid.index,
            format_func=lambda i: (
                f"{T('apt_header')} {df_paid.loc[i, 'apartment_number']}"
                f" — {df_paid.loc[i, 'resident_name']}"
                f" — ₪{df_paid.loc[i, 'amount_paid']}"
            ),
        )

        if st.button("🚀 " + T("send_selected_invoices")):
            if not selected_rows:
                st.warning(T("please_select_apartment"))
            else:
                sent_count = 0
                for i in selected_rows:
                    row = df_paid.loc[i]
                    invoice_id = create_invoice(conn, row)

                    pdf_path = generate_invoice_pdf(
                        conn=conn,
                        invoice_id=invoice_id,
                        resident_name=row['resident_name'],
                        apartment=row['apartment_number'],
                        amount=row['amount_paid'],
                        payment_date=row['payment_date'].strftime('%Y-%m-%d'),
                        charge_month=row['charge_month'],
                        building_id=row['building_id'],
                        payment_method=row['method']
                    )

                    send_invoice_email(
                        receiver_email=row['email'],
                        subject=T("invoice_email_subject").format(invoice_id=invoice_id),
                        body=T("invoice_email_body").format(resident_name=row['resident_name']),
                        attachment_path=pdf_path
                    )

                    log_invoice_send(conn, invoice_id, row['email'])
                    sent_count += 1

                st.success(T("invoices_sent_success").format(count=sent_count))

    if df_paid.empty:
        st.info(T("no_paid_transactions"))
    else:
        st.subheader("✅ " + T("paid_transactions"))

        for idx, row in df_paid.iterrows():
            indicator = T("invoice_sent_short") if row.get("invoice_sent") else ""
            header = (
                f"🏠 {T('apt_header')} {row['apartment_number']} — {row['resident_name']} — ₪{row['amount_paid']}"
            )
            if indicator:
                header = f"{indicator} " + header

            with st.expander(header):
                st.markdown(f"**{T('building_label')}:** {row['building_name']}")
                st.markdown(f"**{T('resident')}:** {row['resident_name']}")
                st.markdown(f"**{T('email')}:** {row['email']}")
                st.markdown(f"**{T('for_month')}:** {row['charge_month'].strftime('%B %Y')}")
                st.markdown(f"**{T('payment_date')}:** {row['payment_date'].strftime('%Y-%m-%d')}")
                lang = st.session_state.get('lang', 'en')
                method_display = translate_payment_method(row['method'], lang)
                st.markdown(f"**{T('payment_method')}:** {method_display}")

                col1, col2, col3 = st.columns([1, 1, 1])

                with col1:
                    if st.button("👁️ " + T("view_invoice"), key=f"view_{row['transaction_id']}"):
                        pdf_path = generate_invoice_pdf(
                            conn=conn,
                            invoice_id=row['transaction_id'],
                            resident_name=row['resident_name'],
                            apartment=row['apartment_number'],
                            amount=row['amount_paid'],
                            payment_date=row['payment_date'].strftime('%Y-%m-%d'),
                            charge_month=row['charge_month'],
                            building_id=row['building_id'],
                            payment_method=row['method']
                        )

                        with open(pdf_path, "rb") as f:
                            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600px" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)

                with col2:
                    if st.button("📤 " + T("send_invoice"), key=f"send_{row['transaction_id']}"):
                        invoice_id = create_invoice(conn, row)

                        pdf_path = generate_invoice_pdf(
                            conn=conn,
                            invoice_id=invoice_id,
                            resident_name=row['resident_name'],
                            apartment=row['apartment_number'],
                            amount=row['amount_paid'],
                            payment_date=row['payment_date'].strftime('%Y-%m-%d'),
                            charge_month=row['charge_month'],
                            building_id=row['building_id'],
                            payment_method=row['method']
                        )

                        send_invoice_email(
                            receiver_email=row['email'],
                            subject=T("invoice_email_subject").format(invoice_id=invoice_id),
                            body=T("invoice_email_body").format(resident_name=row['resident_name']),
                            attachment_path=pdf_path
                        )

                        log_invoice_send(conn, invoice_id, row['email'])
                        st.success(T("invoice_sent_to").format(invoice_id=invoice_id, email=row['email']))

                with col3:
                    btn_key = f"download_{row['transaction_id']}_generate"
                    if st.button("⬇️ " + T("download_invoice"), key=btn_key):
                        pdf_path = generate_invoice_pdf(
                            conn=conn,
                            invoice_id=row['transaction_id'],
                            resident_name=row['resident_name'],
                            apartment=row['apartment_number'],
                            amount=row['amount_paid'],
                            payment_date=row['payment_date'].strftime('%Y-%m-%d'),
                            charge_month=row['charge_month'],
                            building_id=row['building_id'],
                            payment_method=row['method']
                        )

                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "⬇️ " + T("download_invoice"),
                                data=f.read(),
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf",
                                key=f"download_{row['transaction_id']}"
                            )
