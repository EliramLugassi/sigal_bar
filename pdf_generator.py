"""Utilities for generating invoice PDFs."""
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import os
from bidi.algorithm import get_display
import arabic_reshaper
from localization import get_translation, translate_payment_method
import streamlit as st
import pandas as pd
from crud_operations import (
    get_financial_summary_range,
    get_expense_details_range,
    get_special_transactions_balance,
    has_expected_charges_for_period,
    generate_expected_charges,
)


def rtl(text):
    """Convert Hebrew text to proper RTL display."""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def contains_hebrew(text: str) -> bool:
    """Return True if the text contains any Hebrew characters."""
    for ch in str(text):
        if "\u0590" <= ch <= "\u05FF":
            return True
    return False


def maybe_rtl(text: str) -> str:
    """Apply RTL conversion if the text contains Hebrew characters."""
    return rtl(text) if contains_hebrew(text) else str(text)

"""Generate a PDF receipt for a given transaction."""
def generate_invoice_pdf(
    conn, invoice_id, resident_name, apartment, amount,
    payment_date, charge_month, building_id, payment_method,
    output_dir=None
):
    building_id = int(building_id)
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "invoices")
    # Language settings
    lang = st.session_state.get("lang", "he")
    T = get_translation(lang)
    is_hebrew = lang == "he"

    # Load building info
    with conn.cursor() as cur:
        cur.execute("""
            SELECT building_name, vaad_representative, contact_phone, contact_email
            FROM buildings WHERE building_id = %s
        """, (building_id,))
        result = cur.fetchone()

    if not result:
        raise ValueError("No building found with ID {}".format(building_id))
    building_name, rep, phone, email = result

    # Font setup
    font_path = os.path.join(os.path.dirname(__file__), "NotoSansHebrew-VariableFont_wdth,wght.ttf")
    if not os.path.exists(font_path):
        raise FileNotFoundError("Font not found at {}".format(font_path))
    # Register the Hebrew font so Unicode text renders correctly
    pdfmetrics.registerFont(TTFont('Hebrew', font_path))
    pdfmetrics.registerFontFamily('Hebrew', normal='Hebrew')

    # File path
    os.makedirs(output_dir, exist_ok=True)
    file_name = "{}_{}.pdf".format(T("receipt"), invoice_id)
    file_path = os.path.join(output_dir, file_name)

    # Start PDF canvas
    c = canvas.Canvas(file_path, pagesize=A4)
    w, h = A4
    y = h - 50
    spacing = 20

    def draw(label, value, size=14, offset=50, bold=False):
        """Draw text, applying RTL when Hebrew characters are present."""
        nonlocal y
        c.setFont("Hebrew", size)
        text = "{}: {}".format(label, value) if label else str(value)
        if contains_hebrew(text) or is_hebrew:
            c.drawRightString(w - offset, y, maybe_rtl(text))
        else:
            c.drawString(offset, y, text)
        y -= spacing

    # Header
    c.setFont("Hebrew", 18)
    draw("", building_name)
    draw(T("receipt"), str(invoice_id))
    draw(T("date"), payment_date)

    # Resident Info
    y -= spacing
    draw(T("resident_name"), resident_name)
    draw(T("apartment"), apartment)
    method_display = translate_payment_method(payment_method, lang)
    draw(T("payment_method"), method_display)
    draw(T("for_month"), charge_month.strftime('%B %Y'))
    draw(T("payment_date"), payment_date)

    # Line item header
    y -= spacing
    c.setFont("Hebrew", 14)
    draw(T("description"), "")
    draw(T("amount"), "")
    month_name = T("months")[charge_month.month - 1]
    draw(T("line_item"), month_name)
    draw("", "₪{:.0f}".format(amount))

    # Total
    y -= spacing
    draw(T("total_paid"), "₪{:.0f}".format(amount), size=16)

    # Footer
    y -= spacing
    draw("", T("thanks"), size=12)
    draw(T("contact"), "{} | {}".format(phone, email), size=12)

    c.showPage()
    c.save()
    return file_path


def generate_report_summary_pdf(
    conn,
    building_id,
    start_date,
    end_date,
    issue_date,
    kpis,
    df_half,
):
    """Create a PDF summary report with KPIs and tables."""
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO

    building_id = int(building_id)

    # Ensure expected charge rows exist for the report and forecast months
    months_needed = pd.date_range(
        start_date, end_date + pd.DateOffset(months=6), freq="MS"
    )
    for m in months_needed:
        if not has_expected_charges_for_period(conn, building_id, m.year, [m.month]):
            generate_expected_charges(conn, building_id, m.date())

    lang = st.session_state.get("lang", "he")
    T = get_translation(lang)
    is_hebrew = lang == "he"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT building_name, city, street, home_number,
                   vaad_representative, contact_phone, contact_email
            FROM buildings WHERE building_id = %s
            """,
            (building_id,),
        )
        result = cur.fetchone()

    (
        building_name,
        city,
        street,
        home_number,
        rep,
        phone,
        email,
    ) = result if result else ("", "", "", "", "", "", "")

    font_path = os.path.join(
        os.path.dirname(__file__), "NotoSansHebrew-VariableFont_wdth,wght.ttf"
    )
    # Register the Hebrew font without a subfont index to ensure
    # full Unicode support in the generated PDF
    pdfmetrics.registerFont(TTFont("Hebrew", font_path))
    pdfmetrics.registerFontFamily("Hebrew", normal="Hebrew")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
    )
    styles = getSampleStyleSheet()
    # Use the Hebrew font for all text so that Hebrew names render correctly
    for s in styles.byName.values():
        s.fontName = "Hebrew"

    elements = []

    header = f"{building_name} - {rep}"
    address = f"{street} {home_number}, {city}"
    date_range = f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"
    issue = f"{T('issue_date')}: {issue_date.strftime('%Y-%m-%d')}"

    elements.append(Paragraph(maybe_rtl(header), styles["Title"]))
    elements.append(Paragraph(maybe_rtl(address), styles["Normal"]))
    elements.append(Paragraph(maybe_rtl(f"{phone} | {email}"), styles["Normal"]))
    elements.append(Paragraph(maybe_rtl(date_range), styles["Normal"]))
    elements.append(Paragraph(maybe_rtl(issue), styles["Normal"]))
    elements.append(Spacer(1, 12))

    kpi_rows = [
        [T("kpi_paid"), f"₪ {kpis['paid']:,.0f}"],
        [T("kpi_expenses"), f"₪ {kpis['expenses_paid']:,.0f}"],
        [T("kpi_pending_expenses"), f"₪ {kpis['expenses_pending']:,.0f}"],
        [T("kpi_left_to_collect"), f"₪ {kpis['outstanding']:,.0f}"],
        [T("special_transactions"), f"₪ {kpis['special']:,.0f}"],
        [T("net_balance"), f"₪ {kpis['net']:,.0f}"],
        [T("expected_net"), f"₪ {kpis['expected_net']:,.0f}"],
    ]
    kpi_rows = [[maybe_rtl(str(c)) for c in row] for row in kpi_rows]
    kpi_table = Table(kpi_rows, hAlign="LEFT")
    tbl_style = [("GRID", (0, 0), (-1, -1), 1, colors.black),
                 ("FONTNAME", (0, 0), (-1, -1), "Hebrew")]
    if is_hebrew:
        tbl_style.append(("ALIGN", (0, 0), (-1, -1), "RIGHT"))
    kpi_table.setStyle(TableStyle(tbl_style))
    elements.append(kpi_table)
    elements.append(Spacer(1, 12))

    def add_df(title, df):
        if df.empty:
            return
        elements.append(Paragraph(maybe_rtl(title), styles["Heading2"]))
        fmt_df = df.applymap(lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) else x)
        data = [list(fmt_df.columns)] + fmt_df.astype(str).values.tolist()
        data = [[maybe_rtl(str(c)) for c in row] for row in data]
        col_width = doc.width / len(fmt_df.columns)
        tbl = Table(data, colWidths=[col_width] * len(fmt_df.columns), hAlign="LEFT")
        tbl_style = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Hebrew"),
        ]
        if is_hebrew:
            tbl_style.append(("ALIGN", (0, 0), (-1, -1), "RIGHT"))
        tbl.setStyle(TableStyle(tbl_style))
        elements.append(tbl)
        elements.append(Spacer(1, 12))

    add_df(T("half_year_summary"), df_half)

    months_actual = pd.date_range(start_date, end_date, freq="MS")
    payments = []
    expenses = []
    cumulative_paid = 0
    cumulative_expense = 0
    cf_rows = []
    cumulative = 0
    cumulative_forecast = 0
    for m in months_actual:
        m_start = m.date()
        m_end = (m + pd.offsets.MonthEnd(0)).date()
        summ = get_financial_summary_range(
            conn, m_start, m_end, building_id, exclude_apartment_0=True
        )
        expected_m = float(summ.at[0, "total_expected"])
        paid_m = float(summ.at[0, "total_paid"])
        exp_m = float(summ.at[0, "total_expenses"])
        exp_details = get_expense_details_range(conn, m_start, m_end, building_id)
        pending_exp = (
            exp_details[exp_details["status"] == "pending"]["cost"].sum()
            if not exp_details.empty
            else 0
        )
        cumulative_paid += paid_m
        cumulative_expense += exp_m
        special_m = get_special_transactions_balance(conn, m_start, m_end, building_id)
        net = paid_m - exp_m + special_m
        cumulative += net
        month_label = m.strftime("%b %Y")
        payments.append(
            {
                T("month"): month_label,
                T("total_paid"): paid_m,
                T("cumulative_value"): cumulative_paid,
            }
        )
        expenses.append(
            {
                T("month"): month_label,
                T("total_expense_amount"): exp_m,
                T("cumulative_value"): cumulative_expense,
            }
        )
        forecast_net = net + (expected_m - paid_m) - pending_exp
        cumulative_forecast += forecast_net
        cf_rows.append(
            {
                T("month"): month_label,
                T("expected_label"): expected_m,
                "Paid In": paid_m,
                "Paid Out": exp_m,
                T("special_transactions"): special_m,
                "Net": net,
                T("forecast_net_label"): forecast_net,
                T("cumulative_value"): cumulative,
                T("cumulative_forecast_label"): cumulative_forecast,
            }
        )

    last_cumulative = cumulative
    last_forecast = cumulative_forecast
    last_month_dt = pd.to_datetime(end_date)
    for i in range(1, 7):
        ref_date = last_month_dt + pd.DateOffset(months=i)
        m_start = ref_date.date()
        m_end = (ref_date + pd.offsets.MonthEnd(0)).date()
        future_summary = get_financial_summary_range(
            conn, m_start, m_end, building_id, False
        )
        expected_future = float(future_summary.at[0, "total_expected"])
        paid_future = float(future_summary.at[0, "total_paid"])
        exp_paid_future = float(future_summary.at[0, "total_expenses"])
        expenses_future = get_expense_details_range(conn, m_start, m_end, building_id)
        pending_future = (
            expenses_future[expenses_future["status"] == "pending"]["cost"].sum()
            if not expenses_future.empty
            else 0
        )
        special_future = get_special_transactions_balance(conn, m_start, m_end, building_id)
        net_future = paid_future - exp_paid_future + special_future
        forecast_future = expected_future - exp_paid_future - pending_future + special_future
        last_cumulative += net_future
        last_forecast += forecast_future
        cf_rows.append(
            {
                T("month"): ref_date.strftime("%b %Y"),
                T("expected_label"): expected_future,
                "Paid In": paid_future,
                "Paid Out": exp_paid_future,
                T("special_transactions"): special_future,
                "Net": net_future,
                T("forecast_net_label"): forecast_future,
                T("cumulative_value"): last_cumulative,
                T("cumulative_forecast_label"): last_forecast,
            }
        )

    df_payments = pd.DataFrame(payments)
    df_exp_by_month = pd.DataFrame(expenses)
    df_cf = pd.DataFrame(cf_rows)

    add_df(T("payments_by_month"), df_payments)
    add_df(T("expenses_by_month"), df_exp_by_month)
    add_df(T("net_cash_flow_title"), df_cf)

    summary_text = f"{T('expected_end_period_net')}: ₪ {last_forecast:,.0f}"
    elements.append(Paragraph(maybe_rtl(summary_text), styles["Heading3"]))
    elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return buffer
