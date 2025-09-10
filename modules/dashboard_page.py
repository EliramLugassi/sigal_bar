"""Dashboard showing KPIs and cash flow charts for buildings."""

import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go
from modules.gpt_assistant import ask_gpt
from modules.db_tools.crud_operations import (
    get_buildings,
    get_financial_summary_range,
    get_expense_details_range,
    get_unpaid_apartments_range,
    get_expenses,get_special_transactions_balance
)
from modules.db_tools.filters import (
    get_allowed_building_df
)
def abbreviate_currency(value):
    """Format numeric currency values with K/M shorthand."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M ₪"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K ₪"
    else:
        return f"{value:.0f} ₪"

def render(conn, T):
    """Render the main dashboard with KPIs and charts."""
    username = st.session_state.get("username", "User")

    # 🎯 Centered greeting and title
    st.markdown(
        f"""
           <div style='text-align: center; margin-top: 1em; margin-bottom: 2em;'>
               <h1 style='font-size: 2em;'>{T('app_title')}</h1>
               <h5 style='margin-bottom: 0.2em;'> {T('app_subtitle')}</h5>
           </div>
       """,
        unsafe_allow_html=True,
    )

    # You can continue rendering dashboard content here...
    # ------------------ 🔍 FILTERS ------------------
    today = datetime.date.today()
    col_filters = st.columns([2.5, 1, 1, 1, 1])

    df_buildings = get_allowed_building_df(conn)

    if df_buildings.empty:
        st.warning(T("no_buildings_assigned"))
        st.stop()

    building_options = {
        row["building_name"]: row["building_id"]
        for _, row in df_buildings.iterrows()
    }

    with col_filters[0]:
        selected_building_name = st.selectbox("🏢 " + T("filter_by_building"), list(building_options.keys()))
        selected_building_id = building_options[selected_building_name]

    # 📅 From Year + Month
    with col_filters[1]:
        from_year = st.selectbox(T("from_year"), list(range(2022, today.year + 1)), index=today.year - 2022)
    with col_filters[2]:
        from_month = st.selectbox(T("from_month"), list(range(1, 13)), index=max(today.month - 6, 0))

    # 📅 To Year + Month
    with col_filters[3]:
        to_year = st.selectbox(T("to_year"), list(range(2022, today.year + 1)), index=today.year - 2022)
    with col_filters[4]:
        to_month = st.selectbox(T("to_month"), list(range(1, 13)), index=today.month - 1)

    # 🗓 Final parsed date range (month-level precision)
    start_date = datetime.date(from_year, from_month, 1)

    end_temp = datetime.date(to_year, to_month, 28)
    end_date = (pd.to_datetime(end_temp) + pd.offsets.MonthEnd(0)).date()

    # ------------------ 🤖 GPT Assistant ------------------
    with st.expander("💬 " + T("gpt_assistant")):
        user_q = st.text_input(T("ask_gpt"), key="dash_gpt_input")
        if st.button(T("ask_gpt"), key="dash_gpt_btn") and user_q:
            ctx = {
                "page": "dashboard",
                "building_id": selected_building_id,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "user": username,
                "role": st.session_state.get("role"),
            }
            with st.spinner(T("thinking")):
                answer = ask_gpt(user_q, ctx)
            st.write(answer)

    # Checkbox for special transactions
    st.divider()

    # ------------------ 📊 KPI CARDS ------------------
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    # 1. Paid and Expected (EXCLUDING apartment 0)
    df_summary_main = get_financial_summary_range(
        conn, start_dt, end_dt, selected_building_id, exclude_apartment_0=True
    )
    paid = df_summary_main.at[0, 'total_paid']
    expected = df_summary_main.at[0, 'total_expected']

    # 2. Expenses and Special Transactions (INCLUDES apartment 0)
    df_expenses = get_expense_details_range(conn, start_dt, end_dt, selected_building_id)
    expenses_paid = df_expenses[df_expenses["status"] == "paid"]["cost"].sum()
    expenses_pending = df_expenses[df_expenses["status"] == "pending"]["cost"].sum()

    outstanding = expected - paid

    special_balance = get_special_transactions_balance(conn, start_dt, end_dt, selected_building_id)

    # 3. Final balances
    final_balance = paid - expenses_paid + special_balance
    full_balance = final_balance + outstanding - expenses_pending

    label = T("your_balance") if T("your_balance") != "your_balance" else "Your Balance"

    # ------------------ 💳 KPI CARDS UI ------------------
    st.markdown(f"""
    <div style='display: flex; flex-wrap: wrap; justify-content: space-between; gap: 15px; margin-top: 10px; margin-bottom: 30px;'>

      <div style='background-color: #d0f8ce; flex: 1 1 0; min-width: 160px; max-width: 220px; padding: 20px; border-radius: 12px;
                  box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;'>
        <div style='font-size: 20px; font-weight: 500; margin-bottom: 8px;'>{T("kpi_paid")}</div>
        <div style='font-size: 22px; font-weight: bold;'>₪ {paid:,.0f} / ₪ {expected:,.0f}</div>
      </div>

      <div style='background-color: #fff3e0; flex: 1 1 0; min-width: 160px; max-width: 220px; padding: 20px; border-radius: 12px;
                  box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;'>
        <div style='font-size: 20px; font-weight: 500; margin-bottom: 8px;'>{T("kpi_expenses")}</div>
        <div style='font-size: 22px; font-weight: bold;'>₪ {expenses_paid:,.0f}</div>
      </div>

      <div style='background-color: #fffde7; flex: 1 1 0; min-width: 160px; max-width: 220px; padding: 20px; border-radius: 12px;
                  box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;'>
        <div style='font-size: 20px; font-weight: 500; margin-bottom: 8px;'>{T("kpi_pending_expenses")}</div>
        <div style='font-size: 22px; font-weight: bold;'>₪ {expenses_pending:,.0f}</div>
      </div>

      <div style='background-color: #ffcdd2; flex: 1 1 0; min-width: 160px; max-width: 220px; padding: 20px; border-radius: 12px;
                  box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;'>
        <div style='font-size: 20px; font-weight: 500; margin-bottom: 8px;'>{T("kpi_left_to_collect")}</div>
        <div style='font-size: 22px; font-weight: bold;'>₪ {outstanding:,.0f}</div>
      </div>

    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style='
        background-color: #e0f7fa;
        border-radius: 16px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        text-align: center;
        font-size: 22px;
        font-weight: bold;
        color: #333;
    '>
        {T("special_transactions")}: ₪ {special_balance:,.0f}
    </div>
    """, unsafe_allow_html=True)

    # ------------------ 🧮 Final Balance UI ------------------
    st.markdown(f"""
    <div style='
        background-color: #f5f5f5;
        border-radius: 16px;
        padding: 25px;
        margin-bottom: 30px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        text-align: center;
        font-size: 22px;
        font-weight: bold;
        color: #333;
    '>
        💼 {label}: ₪ {final_balance:,.0f} / ₪ {full_balance:,.0f}
    </div>
    """, unsafe_allow_html=True)
    # -------------Manual Bank fixing ------------------
    with st.expander(T("manual_bank_reconciliation")):
        st.markdown(T("manual_bank_reconciliation_desc"))

        # ✅ Reuse filters already selected above
        recon_building_id = selected_building_id
        recon_start_dt = start_dt
        recon_end_dt = end_dt

        # if recon_building_id is None:
        #     st.warning("⚠️ Please select a specific building to perform reconciliation.")
        #     st.stop()
        if recon_building_id is None:
            building_name = "None"
        else:
            df_buildings = get_buildings(conn)
            building_row = df_buildings[df_buildings["building_id"] == recon_building_id]
            building_name = building_row["building_name"].values[0] if not building_row.empty else "Unknown"

        if recon_building_id is None:
            st.warning(T("select_building_reconciliation"))
            st.stop()
        else:
            st.info(
                T("performing_reconciliation").format(
                    building_name=building_name, building_id=recon_building_id
                )
            )

        bank_balance = st.number_input(T("bank_balance_statement"), step=10.0)

        # 🔄 Recalculate system balance using same logic as KPI
        df_summary_main_recon = get_financial_summary_range(
            conn, recon_start_dt, recon_end_dt, recon_building_id, exclude_apartment_0=True
        )
        paid_recon = df_summary_main_recon.at[0, 'total_paid']

        df_exp_recon = get_expense_details_range(conn, recon_start_dt, recon_end_dt, recon_building_id)
        expenses_paid_recon = df_exp_recon[df_exp_recon["status"] == "paid"]["cost"].sum()

        special_balance_recon = get_special_transactions_balance(conn, recon_start_dt, recon_end_dt, recon_building_id)

        system_balance = paid_recon - expenses_paid_recon + special_balance_recon

        st.markdown(f"{T('system_net_balance')} ₪ {system_balance:,.0f}")

        difference = bank_balance - system_balance
        st.markdown(f"{T('adjustment_needed')} ₪ {difference:,.0f}")

        note = st.text_input(T("note_for_adjustment"), value="Manual bank reconciliation")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(T("submit_adjustment")):
                today = datetime.date.today()

                # ✅ Get default resident from apartment 0
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT r.resident_id
                        FROM residents r
                        JOIN apartments a ON r.apartment_id = a.apartment_id
                        WHERE a.building_id = %s AND a.apartment_number = '0'
                        LIMIT 1
                    """, (int(recon_building_id),))
                    result = cur.fetchone()
                    default_resident_id = result[0] if result else None

                # ✅ Insert transaction
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO transactions (
                            building_id, apartment_id, resident_id,
                            charge_month, payment_date,
                            amount_paid, method, reference
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        int(recon_building_id),
                        0,
                        default_resident_id,
                        today.replace(day=1),
                        today,
                        float(difference),
                        "manual_reconciliation",
                        note
                    ))
                    conn.commit()

                st.success(T("adjustment_recorded"))
                st.rerun()
            from modules.db_tools.crud_operations import delete_last_reconciliation

            with col2:
                if st.button(T("undo_last_reconciliation")):
                    deleted = delete_last_reconciliation(conn, int(recon_building_id))
                    if deleted:
                        st.success(T("last_reconciliation_removed"))
                    else:
                        st.info(T("no_reconciliation_entry"))
                    st.rerun()



    # ------------------ 📊 CASH FLOW CHART ------------------
    st.markdown("#### " + T("net_cash_flow_title"))

    # 📉 User-selected baseline
    baseline_value = st.selectbox(
        T("baseline_threshold"),
        options=list(range(5000, 40001, 5000)),
        index=1  # Default to 10,000
    )

    today = datetime.date.today().replace(day=1)
    months_back = 6
    chart_data = {
        "Month": [],
        "Net": [],
        "Paid": [],
        "Expenses_Paid": [],
        "Expenses_Pending": [],
        "Special": [],
    }
    base_cumulative = 0

    # 🧮 Base cumulative before the last 6 months
    for i in range(100):
        ref_date = today - pd.DateOffset(months=months_back + i)
        month_start = ref_date.date()
        month_end = (ref_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)).date()
        summary = get_financial_summary_range(
            conn, month_start, month_end, selected_building_id, False
        )
        paid = summary.at[0, "total_paid"]
        expected = summary.at[0, "total_expected"]
        expenses_df = get_expense_details_range(
            conn, month_start, month_end, selected_building_id
        )
        expenses_paid = expenses_df[expenses_df["status"] == "paid"]["cost"].sum()
        expenses_pending = expenses_df[
            expenses_df["status"] == "pending"
        ]["cost"].sum()
        special = get_special_transactions_balance(
            conn, month_start, month_end, selected_building_id
        )
        if (
            expected == 0
            and expenses_paid == 0
            and expenses_pending == 0
            and special == 0
        ):
            break
        base_cumulative += expected + special - expenses_paid - expenses_pending

    # 🧾 Last 6 months data
    for i in range(months_back):
        ref_date = today - pd.DateOffset(months=i)
        month_start = ref_date.date()
        month_end = (ref_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)).date()
        summary = get_financial_summary_range(
            conn,
            month_start,
            month_end,
            selected_building_id,
            exclude_apartment_0=False,
        )

        paid = summary.at[0, "total_paid"]
        expected = summary.at[0, "total_expected"]
        expenses_df = get_expense_details_range(
            conn, month_start, month_end, selected_building_id
        )
        expenses_paid = expenses_df[expenses_df["status"] == "paid"]["cost"].sum()
        expenses_pending = expenses_df[
            expenses_df["status"] == "pending"
        ]["cost"].sum()
        special = get_special_transactions_balance(
            conn, month_start, month_end, selected_building_id
        )
        net = expected + special - expenses_paid - expenses_pending

        chart_data["Month"].append(ref_date.strftime("%b %Y"))
        chart_data["Net"].append(net)
        chart_data["Paid"].append(expected)
        chart_data["Expenses_Paid"].append(expenses_paid)
        chart_data["Expenses_Pending"].append(expenses_pending)
        chart_data["Special"].append(special)

    # 🧮 Create DataFrame
    df_chart = pd.DataFrame(chart_data).iloc[::-1]
    df_chart["Total Expenses"] = (
        df_chart["Expenses_Paid"] + df_chart["Expenses_Pending"]
    )
    df_chart["Cumulative Net"] = df_chart["Net"].cumsum() + base_cumulative

    # ------------------ 📈 Forecast Next 6 Months ------------------
    forecast_months = []
    forecast_values = []
    forecast_pending = []
    forecast_paid = []
    forecast_total_expenses = []
    cumulative_forecast = df_chart["Cumulative Net"].iloc[-1]

    for i in range(1, 7):
        ref_date = today + pd.DateOffset(months=i)
        month_start = ref_date.date()
        month_end = (ref_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)).date()

        # Income expected for the month
        summary_future = get_financial_summary_range(
            conn, month_start, month_end, selected_building_id, exclude_apartment_0=False
        )
        expected_future = summary_future.at[0, "total_expected"]

        # Expenses for the month
        expenses_future = get_expense_details_range(
            conn, month_start, month_end, selected_building_id
        )
        pending_future = (
            expenses_future[expenses_future["status"] == "pending"]["monthly_cost"].sum()
        )
        paid_future = (
            expenses_future[expenses_future["status"] == "paid"]["monthly_cost"].sum()
        )
        total_future_expenses = pending_future + paid_future

        forecast_pending.append(pending_future)
        forecast_paid.append(paid_future)
        forecast_total_expenses.append(total_future_expenses)

        cumulative_forecast += expected_future - pending_future - paid_future
        forecast_months.append(ref_date.strftime("%b %Y"))
        forecast_values.append(cumulative_forecast)

    df_forecast = pd.DataFrame({
        "Month": forecast_months,
        "Forecast": forecast_values,
        "Pending": forecast_pending,
        "Paid": forecast_paid,
        "Total Expenses": forecast_total_expenses,
    })

    # 📈 Plotly Chart
    fig = go.Figure()

    # 🔵 Cumulative Net
    fig.add_trace(
        go.Scatter(
            x=df_chart["Month"],
            y=df_chart["Cumulative Net"],
            customdata=df_chart[["Paid", "Total Expenses", "Special"]].values,
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

    # 🟠 Monthly Net with tooltip
    fig.add_trace(
        go.Scatter(
            x=df_chart["Month"],
            y=df_chart["Net"],
            customdata=df_chart[["Paid", "Total Expenses", "Special"]].values,
            mode="lines+markers+text",
            name=T("monthly_net_label"),
            line=dict(color="orange", width=2, dash="dash"),
            text=[f"₪{net:,.0f}" for net in df_chart["Net"]],
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

    # 🟢 Forecast Cumulative Line
    fig.add_trace(
        go.Scatter(
            x=df_forecast["Month"],
            y=df_forecast["Forecast"],
            customdata=df_forecast[["Paid", "Total Expenses"]].values,
            mode="lines+markers+text",
            name=T("forecast_label"),
            text=[f"₪{val:,.0f}" for val in df_forecast["Forecast"]],
            textposition="top center",
            line=dict(color="green", width=2, dash="dot"),
            hovertemplate=(
                T("month")
                + ": %{x}<br>"
                + T("paid_in_label")
                + ": ₪%{customdata[0]:,.0f}<br>"
                + T("total_expenses_label")
                + ": ₪%{customdata[1]:,.0f}<br>"
                + T("forecast_label")
                + ": ₪%{y:,.0f}<extra></extra>"
            ),
        )
    )

    # 🔴 Baseline Line using shape
    fig.add_shape(
        type="line",
        x0=df_chart["Month"].iloc[0],
        x1=df_forecast["Month"].iloc[-1],
        y0=baseline_value,
        y1=baseline_value,
        xref="x",
        yref="y",
        line=dict(color="red", width=2, dash="dot")
    )

    # 🔴 Annotation for the baseline
    fig.add_annotation(
        x=df_chart["Month"].iloc[0],
        y=baseline_value,
        text=T("baseline_label").format(value=f"{baseline_value:,}"),
        showarrow=False,
        yshift=10,
        font=dict(color="red"),
        bgcolor="white",
        bordercolor="red",
        borderwidth=1
    )

    # ✏️ Y-axis range fix to ensure baseline is visible
    y_min = min(
        min(df_chart["Net"].min(), df_chart["Cumulative Net"].min(), baseline_value) * 0.95,
        0,
    )
    y_max = max(
        max(df_forecast["Forecast"].max(), df_chart["Cumulative Net"].max()),
        df_chart["Net"].max(),
        baseline_value,
    ) * 1.05

    fig.update_layout(
        xaxis_title=T("month"),
        yaxis_title="₪",
        height=420,
        template="simple_white",
        yaxis=dict(range=[y_min, y_max])
    )

    st.plotly_chart(fig, use_container_width=True)

    # ------------------ 📋 Unpaid Expenses ------------------
    with st.expander(T("view_unpaid_expenses"), expanded=False):
        df_expenses = get_expenses(conn)
        df_expenses["start_date"] = pd.to_datetime(df_expenses["start_date"], errors="coerce")

        filtered = df_expenses.copy()
        if selected_building_id:
            building_name = df_buildings[df_buildings["building_id"] == selected_building_id]["building_name"].values[0]
            filtered = filtered[filtered["building_name"] == building_name]
        filtered = filtered[(filtered["start_date"] >= start_dt) & (filtered["start_date"] <= end_dt)]
        filtered = filtered[filtered["status"] != "paid"]

        if filtered.empty:
            st.success(T("no_unpaid_expenses"))
        else:
            rename_map = {
                "building_name": T("building_name_label"),
                "expense_id": T("expense_id_label"),
                "building_id": T("building_id_label"),
                "apartment_number": T("apartment_label"),
                "supplier_id": T("supplier_id_label"),
                "supplier_receipt_id": T("supplier_receipt_label"),
                "supplier_name": T("supplier_name"),
                "start_date": T("start_date"),
                "end_date": T("end_date"),
                "Num_payments": T("Num_payments_label"),
                "total_cost": T("total_cost"),
                "expense_type": T("expense_type"),
                "status": T("status_label"),
                "notes": T("notes_label"),
            }
            st.dataframe(filtered.rename(columns=rename_map))

    # ------------------ 📅 Unpaid Apartments ------------------
    with st.expander(T("view_unpaid_apartments"), expanded=False):
        if selected_building_id:
            df_unpaid = get_unpaid_apartments_range(conn, start_dt, end_dt, selected_building_id)
            if df_unpaid.empty:
                st.success(T("all_apartments_paid"))
            else:
                rename_map = {
                    "charge_month": T("charge_month_label"),
                    "building_name": T("building_name_label"),
                    "apartment_number": T("apartment_label"),
                    "expected_amount": T("expected_amount_label"),
                }
                st.dataframe(df_unpaid.rename(columns=rename_map))

    # ------------------ 💸 Expense Breakdown ------------------
    with st.expander(T("expense_breakdown"), expanded=False):
        df_expense = get_expense_details_range(conn, start_dt, end_dt, selected_building_id)
        if df_expense.empty:
            st.info(T("no_expenses_found"))
        else:
            rename_map = {
                "charge_year": T("year"),
                "charge_month_num": T("month"),
                "building_name": T("building_name_label"),
                "supplier_name": T("supplier_name"),
                "cost": T("amount"),
                "expense_type": T("expense_type"),
                "status": T("status_label"),
            }
            st.dataframe(df_expense.rename(columns=rename_map))
