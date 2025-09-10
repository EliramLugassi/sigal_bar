"""Reports page with KPIs and detailed financial tables."""
import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
from modules.utils.pdf_generator import generate_report_summary_pdf

from modules.db_tools.crud_operations import (
    get_financial_summary_range,
    get_expense_details_range,
    get_special_transactions_balance,
)
from modules.db_tools.filters import get_allowed_building_df


def render(conn, T):
    """Render the reports page."""
    st.header("\U0001F4C4 " + T("reports"))

    def reset_ready():
        st.session_state["report_ready"] = False

    buildings_df = get_allowed_building_df(conn)
    if buildings_df.empty:
        st.warning(T("no_buildings_assigned"))
        st.stop()

    building_map = {row["building_name"]: row["building_id"] for _, row in buildings_df.iterrows()}
    selected_building_name = st.selectbox(
        "\U0001F3E2 " + T("select_building"),
        list(building_map.keys()),
        key="report_building",
        on_change=reset_ready,
    )
    selected_building_id = building_map[selected_building_name]

    today = datetime.date.today()
    col1, col2, col3, col4 = st.columns(4)
    from_year = col1.selectbox(
        T("from_year"),
        list(range(2022, today.year + 1)),
        key="report_from_year",
        on_change=reset_ready,
    )
    from_month = col2.selectbox(
        T("from_month"),
        list(range(1, 13)),
        key="report_from_month",
        on_change=reset_ready,
    )
    to_year = col3.selectbox(
        T("to_year"),
        list(range(2022, today.year + 1)),
        index=today.year - 2022,
        key="report_to_year",
        on_change=reset_ready,
    )
    to_month = col4.selectbox(
        T("to_month"),
        list(range(1, 13)),
        index=today.month - 1,
        key="report_to_month",
        on_change=reset_ready,
    )

    report_type = st.radio(
        T("report_type"),
        [T("full_report"), T("transactions_only"), T("expenses_only")],
        key="report_type",
        on_change=reset_ready,
    )

    col5, col6 = st.columns(2)
    expense_status = col5.selectbox(
        T("filter_by_status"),
        ["All", "paid", "pending"],
        key="report_expense_status",
        on_change=reset_ready,
    )
    payment_method = col6.selectbox(
        T("payment_method"),
        ["All", "cash", "credit", "check", "bank transfer", "other"],
        key="report_payment_method",
        on_change=reset_ready,
    )

    if st.button("\U0001F3AF " + T("produce_report"), key="produce_report_btn"):
        st.session_state["report_filters"] = {
            "building_id": selected_building_id,
            "from_year": from_year,
            "from_month": from_month,
            "to_year": to_year,
            "to_month": to_month,
            "report_type": report_type,
            "expense_status": expense_status,
            "payment_method": payment_method,
        }
        st.session_state["report_ready"] = True
        st.session_state["download_counter"] = st.session_state.get("download_counter", 0) + 1
        st.rerun()

    if not st.session_state.get("report_ready"):
        return

    filters = st.session_state.get("report_filters", {})
    start_date = datetime.date(filters["from_year"], filters["from_month"], 1)
    end_temp = datetime.date(filters["to_year"], filters["to_month"], 28)
    end_date = (pd.to_datetime(end_temp) + pd.offsets.MonthEnd(0)).date()

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    summary = get_financial_summary_range(
        conn, start_dt, end_dt, selected_building_id, exclude_apartment_0=True
    )
    paid = summary.at[0, "total_paid"]
    expected = summary.at[0, "total_expected"]

    df_exp_full = get_expense_details_range(conn, start_dt, end_dt, selected_building_id)
    if expense_status != "All":
        df_exp_full = df_exp_full[df_exp_full["status"] == expense_status]
    expenses_paid = df_exp_full[df_exp_full["status"] == "paid"]["cost"].sum()
    expenses_pending = df_exp_full[df_exp_full["status"] == "pending"]["cost"].sum()

    outstanding = expected - paid
    special_balance = get_special_transactions_balance(conn, start_dt, end_dt, selected_building_id)
    net_balance = paid - expenses_paid - expenses_pending + special_balance
    expected_net = net_balance + outstanding

    st.markdown(
        f"""
        <div style='display:flex;flex-wrap:wrap;justify-content:space-between;gap:15px;margin-top:10px;margin-bottom:30px;'>
          <div style='background-color:#d0f8ce;flex:1 1 0;min-width:160px;max-width:220px;padding:20px;border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.08);text-align:center;'>
            <div style='font-size:20px;font-weight:500;margin-bottom:8px;'>{T('kpi_paid')}</div>
            <div style='font-size:22px;font-weight:bold;'>₪ {paid:,.0f} / ₪ {expected:,.0f}</div>
          </div>
          <div style='background-color:#fff3e0;flex:1 1 0;min-width:160px;max-width:220px;padding:20px;border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.08);text-align:center;'>
            <div style='font-size:20px;font-weight:500;margin-bottom:8px;'>{T('kpi_expenses')}</div>
            <div style='font-size:22px;font-weight:bold;'>₪ {expenses_paid:,.0f}</div>
          </div>
          <div style='background-color:#fffde7;flex:1 1 0;min-width:160px;max-width:220px;padding:20px;border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.08);text-align:center;'>
            <div style='font-size:20px;font-weight:500;margin-bottom:8px;'>{T('kpi_pending_expenses')}</div>
            <div style='font-size:22px;font-weight:bold;'>₪ {expenses_pending:,.0f}</div>
          </div>
          <div style='background-color:#ffcdd2;flex:1 1 0;min-width:160px;max-width:220px;padding:20px;border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.08);text-align:center;'>
            <div style='font-size:20px;font-weight:500;margin-bottom:8px;'>{T('kpi_left_to_collect')}</div>
            <div style='font-size:22px;font-weight:bold;'>₪ {outstanding:,.0f}</div>
          </div>
          <div style='background-color:#e0f7fa;flex:1 1 0;min-width:160px;max-width:220px;padding:20px;border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.08);text-align:center;'>
            <div style='font-size:20px;font-weight:500;margin-bottom:8px;'>{T('special_transactions')}</div>
            <div style='font-size:22px;font-weight:bold;'>₪ {special_balance:,.0f}</div>
          </div>
          <div style='background-color:#f5f5f5;flex:1 1 0;min-width:160px;max-width:220px;padding:20px;border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.08);text-align:center;'>
            <div style='font-size:20px;font-weight:500;margin-bottom:8px;'>{T('net_balance')}</div>
            <div style='font-size:22px;font-weight:bold;'>₪ {net_balance:,.0f}</div>
          </div>
          <div style='background-color:#f5f5f5;flex:1 1 0;min-width:160px;max-width:220px;padding:20px;border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.08);text-align:center;'>
            <div style='font-size:20px;font-weight:500;margin-bottom:8px;'>{T('expected_net')}</div>
            <div style='font-size:22px;font-weight:bold;'>₪ {expected_net:,.0f}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Half-Year Summary -----
    st.markdown("#### " + T("half_year_summary"))

    half_year_data = []
    cumulative_half = 0
    df_half = pd.DataFrame()
    for yr in range(start_date.year, end_date.year + 1):
        for half, months in enumerate([(1, 6), (7, 12)], start=1):
            start_h = datetime.date(yr, months[0], 1)
            end_h = datetime.date(yr, months[1], 1)
            end_h = (pd.to_datetime(end_h) + pd.offsets.MonthEnd(0)).date()

            seg_start = max(start_h, start_date)
            seg_end = min(end_h, end_date)
            if seg_start > seg_end:
                continue

            summ = get_financial_summary_range(
                conn,
                seg_start,
                seg_end,
                selected_building_id,
                exclude_apartment_0=True,
            )
            expected_h = float(summ.at[0, "total_expected"])
            paid_h = float(summ.at[0, "total_paid"])
            expenses_h = float(summ.at[0, "total_expenses"])
            special_h = get_special_transactions_balance(
                conn, seg_start, seg_end, selected_building_id
            )
            net_h = paid_h - expenses_h + special_h
            cumulative_half += net_h
            label = f"H{half} {yr}"
            half_year_data.append(
                {
                    T("half_year"): label,
                    T("expected_label"): expected_h,
                    T("kpi_paid"): paid_h,
                    T("kpi_expenses"): expenses_h,
                    T("special_transactions"): special_h,
                    T("net_balance"): net_h,
                    T("cumulative_value"): cumulative_half,
                }
            )

    if half_year_data:
        df_half = pd.DataFrame(half_year_data)
        st.dataframe(df_half)

    tabs = st.tabs([T("transactions"), T("expenses"), T("net_cash_flow_title")])

    df_trans = pd.DataFrame()
    df_expenses = pd.DataFrame()

    if report_type != T("expenses_only"):
        with tabs[0]:
            q = """
                SELECT a.apartment_number AS apt,
                       r.first_name || ' ' || r.last_name AS resident,
                       t.charge_month,
                       t.payment_date,
                       t.amount_paid,
                       t.method
                FROM transactions t
                LEFT JOIN apartments a ON t.apartment_id = a.apartment_id
                LEFT JOIN residents r ON t.resident_id = r.resident_id
                WHERE t.amount_paid > 0
                  AND t.charge_month BETWEEN %s AND %s
                  AND t.building_id = %s
            """
            params = [start_dt, end_dt, selected_building_id]
            if payment_method != "All":
                q += " AND t.method = %s"
                params.append(payment_method)
            q += " ORDER BY t.payment_date DESC"
            df_trans = pd.read_sql(q, conn, params=params)
            total_paid = 0
            if not df_trans.empty:
                df_trans["payment_date"] = pd.to_datetime(df_trans["payment_date"], errors="coerce")
                df_trans = df_trans.sort_values("payment_date")
                total_paid = df_trans["amount_paid"].sum()
                df_trans[T("cumulative_value")] = df_trans["amount_paid"].cumsum()
                rename_map = {
                    "apt": T("apartment"),
                    "resident": T("resident_name"),
                    "charge_month": T("charge_month_label"),
                    "payment_date": T("payment_date"),
                    "amount_paid": T("amount_paid"),
                    "method": T("payment_method"),
                }
                df_trans = df_trans.rename(columns=rename_map)
            st.dataframe(df_trans)
            st.markdown(f"**{T('total_paid')}: ₪ {total_paid:,.0f}**")

    if report_type != T("transactions_only"):
        with tabs[1]:
            q = """
                SELECT s.supplier_name AS supplier,
                       e.expense_type AS type,
                       e.start_date,
                       e.end_date,
                       e.status,
                       e.total_cost AS amount
                FROM expenses e
                JOIN suppliers s ON e.supplier_id = s.supplier_id
                WHERE e.start_date <= %s AND e.end_date >= %s
                  AND e.building_id = %s
            """
            params = [end_dt, start_dt, selected_building_id]
            if expense_status != "All":
                q += " AND e.status = %s"
                params.append(expense_status)
            q += " ORDER BY e.start_date DESC"
            df_expenses = pd.read_sql(q, conn, params=params)
            total_cost = 0
            if not df_expenses.empty:
                df_expenses["start_date"] = pd.to_datetime(df_expenses["start_date"], errors="coerce")
                df_expenses = df_expenses.sort_values("start_date")
                total_cost = df_expenses["amount"].sum()
                df_expenses[T("cumulative_value")] = df_expenses["amount"].cumsum()
                rename_map = {
                    "supplier": T("supplier_name"),
                    "type": T("expense_type"),
                    "start_date": T("start_date"),
                    "end_date": T("end_date"),
                    "status": T("status_label"),
                    "amount": T("amount"),
                }
                df_expenses = df_expenses.rename(columns=rename_map)
            st.dataframe(df_expenses)
            st.markdown(f"**{T('total_expense_amount')}: ₪ {total_cost:,.0f}**")

    with tabs[2]:
        months = pd.date_range(start_dt, end_dt, freq="MS")
        data = []
        cumulative = 0
        for m in months:
            m_start = m.date()
            m_end = (m + pd.offsets.MonthEnd(0)).date()
            summ = get_financial_summary_range(
                conn, m_start, m_end, selected_building_id, exclude_apartment_0=True
            )
            paid_m = summ.at[0, "total_paid"]
            expected_m = summ.at[0, "total_expected"]
            expenses_df = get_expense_details_range(
                conn, m_start, m_end, selected_building_id
            )
            exp_paid = expenses_df[expenses_df["status"] == "paid"]["cost"].sum()
            exp_pending = expenses_df[expenses_df["status"] == "pending"]["cost"].sum()
            special_m = get_special_transactions_balance(
                conn, m_start, m_end, selected_building_id
            )
            net = expected_m + special_m - exp_paid - exp_pending
            cumulative += net
            data.append(
                {
                    "Date": m,
                    "Month": m.strftime("%b %Y"),
                    "Paid In": expected_m,
                    "Paid Out": exp_paid,
                    T("special_transactions"): special_m,
                    "Net": net,
                    "Cumulative": cumulative,
                }
            )

        df_cf = pd.DataFrame(data).sort_values("Date")
        rename_map = {
            "Month": T("month"),
            "Paid In": T("paid_in_label"),
            "Paid Out": T("paid_out_label"),
            "Net": T("monthly_net_label").split()[0],
            "Cumulative": T("cumulative_net_label"),
        }
        st.dataframe(df_cf.drop(columns="Date").rename(columns=rename_map))

        # ----- Cash Flow Chart Matching Dashboard Behavior -----
        baseline_value = st.selectbox(
            T("baseline_threshold"), options=list(range(5000, 40001, 5000)), index=1
        )

        # Historical cumulative before selected range
        base_cumulative = 0
        for i in range(100):
            ref_date = start_dt - pd.DateOffset(months=i + 1)
            month_start = ref_date.date()
            month_end = (
                ref_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)
            ).date()
            summ = get_financial_summary_range(
                conn, month_start, month_end, selected_building_id, False
            )
            paid_hist = summ.at[0, "total_paid"]
            expected_hist = summ.at[0, "total_expected"]
            exp_df_hist = get_expense_details_range(
                conn, month_start, month_end, selected_building_id
            )
            exp_paid_hist = exp_df_hist[exp_df_hist["status"] == "paid"]["cost"].sum()
            exp_pending_hist = exp_df_hist[exp_df_hist["status"] == "pending"]["cost"].sum()
            special_hist = get_special_transactions_balance(
                conn, month_start, month_end, selected_building_id
            )
            if (
                expected_hist == 0
                and exp_paid_hist == 0
                and exp_pending_hist == 0
                and special_hist == 0
            ):
                break
            base_cumulative += expected_hist + special_hist - exp_paid_hist - exp_pending_hist

        chart_data = {
            "Month": [],
            "Net": [],
            "Paid": [],
            "Expenses": [],
            "Special": [],
        }
        for m in months:
            m_start = m.date()
            m_end = (m + pd.offsets.MonthEnd(0)).date()
            summ = get_financial_summary_range(
                conn, m_start, m_end, selected_building_id, False
            )
            paid = summ.at[0, "total_paid"]
            expected = summ.at[0, "total_expected"]
            exp_df = get_expense_details_range(
                conn, m_start, m_end, selected_building_id
            )
            exp_paid = exp_df[exp_df["status"] == "paid"]["cost"].sum()
            exp_pending = exp_df[exp_df["status"] == "pending"]["cost"].sum()
            special = get_special_transactions_balance(
                conn, m_start, m_end, selected_building_id
            )
            net = expected + special - exp_paid - exp_pending
            chart_data["Month"].append(m.strftime("%b %Y"))
            chart_data["Net"].append(net)
            chart_data["Paid"].append(expected)
            chart_data["Expenses"].append(exp_paid + exp_pending)
            chart_data["Special"].append(special)

        df_chart = pd.DataFrame(chart_data)
        df_chart["Cumulative Net"] = df_chart["Net"].cumsum() + base_cumulative

        # Forecast next 6 months
        forecast_months = [df_chart["Month"].iloc[-1]]
        forecast_values = [df_chart["Cumulative Net"].iloc[-1]]
        forecast_expenses = [0]
        cumulative_forecast = df_chart["Cumulative Net"].iloc[-1]
        last_month = end_dt
        for i in range(1, 7):
            ref_date = last_month + pd.DateOffset(months=i)
            month_start = ref_date.date()
            month_end = (
                ref_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)
            ).date()
            summary_future = get_financial_summary_range(
                conn, month_start, month_end, selected_building_id, False
            )
            expected_future = summary_future.at[0, "total_expected"]
            expenses_future = get_expense_details_range(
                conn, month_start, month_end, selected_building_id
            )
            pending_future = (
                expenses_future[expenses_future["status"] == "pending"]["cost"].sum()
            )
            forecast_expenses.append(pending_future)
            cumulative_forecast += expected_future - pending_future
            forecast_months.append(ref_date.strftime("%b %Y"))
            forecast_values.append(cumulative_forecast)

        df_forecast = pd.DataFrame(
            {"Month": forecast_months, "Forecast": forecast_values, "Expenses": forecast_expenses}
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_chart["Month"],
                y=df_chart["Cumulative Net"],
                customdata=df_chart[["Paid", "Expenses", "Special"]].values,
                mode="lines+markers+text",
                text=[f"₪{val:,.0f}" for val in df_chart["Cumulative Net"]],
                textposition="top center",
                name=T("cumulative_net_label"),
                line=dict(color="blue", width=3),
                hovertemplate=(
                    T("month")
                    + ": %{x}<br>"
                    + T("paid_in_label")
                    + ": ₪%{customdata[0]:,.0f}<br>"
                    + T("total_expenses_label")
                    + ": ₪%{customdata[1]:,.0f}<br>"
                    + T("special_transactions")
                    + ": ₪%{customdata[2]:,.0f}<br>"
                    + T("cumulative_net_label")
                    + ": ₪%{y:,.0f}<extra></extra>"
                ),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_chart["Month"],
                y=df_chart["Net"],
                customdata=df_chart[["Paid", "Expenses", "Special"]].values,
                mode="lines+markers+text",
                name=T("monthly_net_label"),
                line=dict(color="orange", width=2, dash="dash"),
                text=[f"₪{n:,.0f}" for n in df_chart["Net"]],
                textposition="bottom center",
                hovertemplate=(
                    T("month")
                    + ": %{x}<br>"
                    + T("paid_in_label")
                    + ": ₪%{customdata[0]:,.0f}<br>"
                    + T("total_expenses_label")
                    + ": ₪%{customdata[1]:,.0f}<br>"
                    + T("special_transactions")
                    + ": ₪%{customdata[2]:,.0f}<br>"
                    + T("monthly_net_label")
                    + ": ₪%{y:,.0f}<extra></extra>"
                ),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_forecast["Month"],
                y=df_forecast["Forecast"],
                customdata=df_forecast["Expenses"],
                mode="lines+markers+text",
                name=T("forecast_label"),
                text=[f"₪{val:,.0f}" for val in df_forecast["Forecast"]],
                textposition="top center",
                line=dict(color="green", width=2, dash="dot"),
                hovertemplate=(
                    "Forecast: ₪%{y:,.0f}<br>"
                    + T("total_expenses_label")
                    + ": ₪%{customdata:,.0f}<extra></extra>"
                ),
            )
        )
        fig.add_shape(
            type="line",
            x0=df_chart["Month"].iloc[0],
            x1=df_forecast["Month"].iloc[-1],
            y0=baseline_value,
            y1=baseline_value,
            xref="x",
            yref="y",
            line=dict(color="red", width=2, dash="dot"),
        )
        fig.add_annotation(
            x=df_chart["Month"].iloc[0],
            y=baseline_value,
            text=T("baseline_label").format(value=f"{baseline_value:,}"),
            showarrow=False,
            yshift=10,
            font=dict(color="red"),
            bgcolor="white",
            bordercolor="red",
            borderwidth=1,
        )
        y_min = min(
            min(df_chart["Net"].min(), df_chart["Cumulative Net"].min(), baseline_value)
            * 0.95,
            0,
        )
        y_max = (
            max(df_forecast["Forecast"].max(), df_chart["Cumulative Net"].max())
            if not df_forecast.empty
            else df_chart["Cumulative Net"].max()
        )
        y_max = max(y_max, df_chart["Net"].max(), baseline_value) * 1.05
        fig.update_layout(
            xaxis_title=T("month"),
            yaxis_title="₪",
            height=420,
            template="simple_white",
            yaxis=dict(range=[y_min, y_max]),
        )
        st.plotly_chart(fig, use_container_width=True)

    export_df = df_expenses if report_type == T("expenses_only") else df_trans
    if report_type == T("full_report"):
        export_df = pd.concat([df_trans, df_expenses], axis=0)
    st.download_button(
        T("download_csv"),
        export_df.to_csv(index=False).encode("utf-8-sig"),
        "report.csv",
        "text/csv",
    )

    dl_key = f"download_summary_pdf_{st.session_state.get('download_counter', 0)}"
    if st.button(T("download_summary_pdf"), key=f"{dl_key}_generate"):
        pdf_bytes = generate_report_summary_pdf(
            conn,
            selected_building_id,
            start_dt,
            end_dt,
            datetime.date.today(),
            {
                "paid": paid,
                "expenses_paid": expenses_paid,
                "expenses_pending": expenses_pending,
                "outstanding": outstanding,
                "special": special_balance,
                "net": net_balance,
                "expected_net": expected_net,
            },
            df_half if half_year_data else pd.DataFrame(),
        ).getvalue()
        st.download_button(
            T("download_summary_pdf"),
            data=pdf_bytes,
            file_name="report_summary.pdf",
            mime="application/pdf",
            key=dl_key,
        )
