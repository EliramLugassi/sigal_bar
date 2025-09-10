"""UI filter helpers for Streamlit."""
# # filters.py
# import streamlit as st
# import pandas as pd
# from datetime import date
# from crud_operations import (
#     get_all_buildings,
#     get_user_building_ids,
#     get_apartments_by_building,
#     get_expected_charge_years, get_buildings
# )
#
# # ─────────────────────────────────────────
# # 🎛 BUILDING FILTERS
# # ─────────────────────────────────────────
# def get_user_buildings(conn):
#     user_id = st.session_state.get("user_id")
#     role = st.session_state.get("role")
#
#     if role == "admin":
#         return get_all_buildings(conn)  # ⬅️ This line is correct
#
#     if not user_id:
#         return pd.DataFrame()  # ⛔ Safeguard
#
#     building_ids = get_user_building_ids(conn, user_id)
#     df = get_all_buildings(conn)
#     return df[df["building_id"].isin(building_ids)]
#
#
# def get_allowed_building_df(conn):
#     """Returns a DataFrame of buildings the user is allowed to access."""
#     role = st.session_state.get("role")
#     if role == "admin":
#         return get_buildings(conn)
#
#     user_id = st.session_state.get("user_id")
#     allowed_ids = get_user_building_ids(conn, user_id)
#
#     df_all = get_buildings(conn)
#     return df_all[df_all["building_id"].isin(allowed_ids)]
#
# def building_filter(conn, label="🏢 Select Building", key="building_filter"):
#     buildings_df = get_user_buildings(conn)
#     if buildings_df.empty:
#         st.warning("⚠️ No buildings available.")
#         return None
#     return st.selectbox(
#         label,
#         buildings_df["building_id"],
#         format_func=lambda b_id: buildings_df.loc[buildings_df["building_id"] == b_id, "building_name"].values[0],
#         key=key
#     )
#
# # ─────────────────────────────────────────
# # 🏠 APARTMENT FILTER
# # ─────────────────────────────────────────
# def apartment_filter(conn, building_id, label="🏠 Apartment", key="apartment_filter"):
#     df = get_apartments_by_building(conn, building_id)
#     if df.empty:
#         return None
#     df = df.sort_values(by="apartment_number", key=lambda x: x.astype(str).str.zfill(4))
#     apt_map = {f"{row['apartment_number']}": row["apartment_id"] for _, row in df.iterrows()}
#     selected = st.selectbox(label, ["All"] + list(apt_map.keys()), key=key)
#     return apt_map.get(selected) if selected != "All" else None
#
# # ─────────────────────────────────────────
# # 🗕 YEAR FILTERS
# # ─────────────────────────────────────────
# def static_year_filter(label="🗕 Year", key="year_filter", start=2023):
#     current_year = date.today().year
#     return st.selectbox(label, list(range(start, current_year + 1)), key=key)
#
# def db_year_filter(conn, label="🗕 Year", key="db_year_filter"):
#     years = get_expected_charge_years(conn)
#     if not years:
#         st.warning("⚠️ No year data available.")
#         return None
#     return st.selectbox(label, years, key=key)
#
# def static_year_range_filter(label_from="From Year", label_to="To Year", key_prefix="year_range", start=2022):
#     current_year = date.today().year
#     col1, col2 = st.columns(2)
#     year_from = col1.selectbox(label_from, list(range(start, current_year + 1)), key=f"{key_prefix}_from")
#     year_to = col2.selectbox(label_to, list(range(start, current_year + 1)), index=(current_year - start), key=f"{key_prefix}_to")
#     return year_from, year_to
#
# # ─────────────────────────────────────────
# # 🗓 MONTH FILTERS
# # ─────────────────────────────────────────
# def month_filter(label="🗓 Month", key="month_filter"):
#     return st.selectbox(label, list(range(1, 13)), format_func=lambda m: f"{m:02d}", key=key)
#
# def multi_month_filter(label="🗓 Months", key="multi_month_filter"):
#     return st.multiselect(
#         label,
#         options=list(range(1, 13)),
#         format_func=lambda m: date(1900, m, 1).strftime('%B'),
#         key=key
#     )
#
# def month_range_filter(label_from="From Month", label_to="To Month", key_prefix="month_range"):
#     col1, col2 = st.columns(2)
#     month_from = col1.selectbox(label_from, list(range(1, 13)), format_func=lambda m: f"{m:02d}", key=f"{key_prefix}_from")
#     month_to = col2.selectbox(label_to, list(range(1, 13)), format_func=lambda m: f"{m:02d}", key=f"{key_prefix}_to")
#     return month_from, month_to
#
# # ─────────────────────────────────────────
# # 🏠 APARTMENT NUMBER FILTER (NO DB)
# # ─────────────────────────────────────────
# def apartment_number_filter(df_apartments, label="🏠 Apartment", key="apt_num_filter"):
#     options = df_apartments["apartment_number"].tolist()
#     selected = st.selectbox(label, options, key=key)
#     return selected
#
# def building_id_and_name_filter(conn, label="🏢 Select Building", key="building_id_name_filter"):
#     buildings_df = get_user_buildings(conn)
#     if buildings_df.empty:
#         st.warning("⚠️ No buildings available.")
#         return None, None
#
#     options = {
#         row["building_name"]: row["building_id"]
#         for _, row in buildings_df.iterrows()
#     }
#
#     selected_name = st.selectbox(label, list(options.keys()), key=key)
#     return options[selected_name], selected_name
#
# def multiselect_buildings(buildings_df, current_ids=None, key="multi_building_select"):
#     """Multiselect filter for assigning buildings to a user."""
#     building_names = buildings_df.set_index("building_id")["building_name"].to_dict()
#     return st.multiselect(
#         "🎗 Select Buildings",
#         options=list(building_names.keys()),
#         default=current_ids or [],
#         format_func=lambda x: building_names[x],
#         key=key
#     )


# filters.py
import streamlit as st
import pandas as pd
from datetime import date
from modules.db_tools.crud_operations import (
    get_user_building_ids,
    get_apartments_by_building,
    get_expected_charge_years,
    get_buildings
)

# ────────────────────────────────────────────────
# 🏢 BUILDING FILTERS
# ────────────────────────────────────────────────

def get_allowed_building_df(conn):
    """Returns a DataFrame of buildings the user is allowed to access."""
    role = st.session_state.get("role")
    user_id = st.session_state.get("user_id")

    if role == "admin":
        return get_buildings(conn)

    if not user_id:
        return pd.DataFrame()

    allowed_ids = get_user_building_ids(conn, user_id)
    df = get_buildings(conn)
    return df[df["building_id"].isin(allowed_ids)]

def building_filter(conn, label="🏢 Select Building", key="building_filter"):
    """Returns selected building_id or None if 'All' is selected."""
    buildings_df = get_allowed_building_df(conn)

    if buildings_df.empty:
        st.warning("⚠️ No buildings available.")
        return None

    building_options = {
        "All": None,
        **{row["building_name"]: row["building_id"] for _, row in buildings_df.iterrows()}
    }

    selected_name = st.selectbox(label, list(building_options.keys()), key=key)
    return building_options[selected_name]

def building_id_and_name_filter(conn, label="🏢 Select Building", key="building_id_name_filter"):
    """Return building id and name selected by the user."""
    buildings_df = get_allowed_building_df(conn)

    if buildings_df.empty:
        st.warning("⚠️ No buildings available.")
        return None, None

    options = {
        row["building_name"]: row["building_id"]
        for _, row in buildings_df.iterrows()
    }

    selected_name = st.selectbox(label, list(options.keys()), key=key)
    return options[selected_name], selected_name

def multiselect_buildings(buildings_df, current_ids=None, key="multi_building_select"):
    """Multiselect widget for assigning buildings."""
    building_names = buildings_df.set_index("building_id")["building_name"].to_dict()
    return st.multiselect(
        "🎗 Select Buildings",
        options=list(building_names.keys()),
        default=current_ids or [],
        format_func=lambda x: building_names[x],
        key=key
    )

# ────────────────────────────────────────────────
# 🏠 APARTMENT FILTERS
# ────────────────────────────────────────────────

def apartment_filter(conn, building_id, label="🏠 Apartment", key="apartment_filter"):
    """Select an apartment within a building."""
    df = get_apartments_by_building(conn, building_id)
    if df.empty:
        return None
    df = df.sort_values(by="apartment_number", key=lambda x: x.astype(str).str.zfill(4))
    apt_map = {f"{row['apartment_number']}": row["apartment_id"] for _, row in df.iterrows()}
    selected = st.selectbox(label, ["All"] + list(apt_map.keys()), key=key)
    return apt_map.get(selected) if selected != "All" else None

def apartment_number_filter(df_apartments, label="🏠 Apartment", key="apt_num_filter"):
    """Select an apartment number from a DataFrame."""
    options = df_apartments["apartment_number"].tolist()
    selected = st.selectbox(label, options, key=key)
    return selected

# ────────────────────────────────────────────────
# 📅 YEAR FILTERS
# ────────────────────────────────────────────────

def static_year_filter(label="🗕 Year", key="year_filter", start=2023):
    """Select a year from a static range."""
    current_year = date.today().year
    return st.selectbox(label, list(range(start, current_year + 1)), key=key)

def db_year_filter(conn, label="🗕 Year", key="db_year_filter"):
    """Select a year from years present in the DB."""
    years = get_expected_charge_years(conn)
    if not years:
        st.warning("⚠️ No year data available.")
        return None
    return st.selectbox(label, years, key=key)

def static_year_range_filter(label_from="From Year", label_to="To Year", key_prefix="year_range", start=2022):
    """Select a range of years."""
    current_year = date.today().year
    col1, col2 = st.columns(2)
    year_from = col1.selectbox(label_from, list(range(start, current_year + 1)), key=f"{key_prefix}_from")
    year_to = col2.selectbox(label_to, list(range(start, current_year + 1)), index=(current_year - start), key=f"{key_prefix}_to")
    return year_from, year_to

# ────────────────────────────────────────────────
# 📆 MONTH FILTERS
# ────────────────────────────────────────────────

def month_filter(label="🗓 Month", key="month_filter"):
    """Select a single month."""
    return st.selectbox(label, list(range(1, 13)), format_func=lambda m: f"{m:02d}", key=key)

def multi_month_filter(label="🗓 Months", key="multi_month_filter"):
    """Select multiple months."""
    return st.multiselect(
        label,
        options=list(range(1, 13)),
        format_func=lambda m: date(1900, m, 1).strftime('%B'),
        key=key
    )

def month_range_filter(label_from="From Month", label_to="To Month", key_prefix="month_range"):
    """Select a start and end month."""
    col1, col2 = st.columns(2)
    month_from = col1.selectbox(label_from, list(range(1, 13)), format_func=lambda m: f"{m:02d}", key=f"{key_prefix}_from")
    month_to = col2.selectbox(label_to, list(range(1, 13)), format_func=lambda m: f"{m:02d}", key=f"{key_prefix}_to")
    return month_from, month_to

# ────────────────────────────────────────────────
# 🔐 DATA ACCESS GUARDRAIL
# ────────────────────────────────────────────────

def filter_df_by_allowed_buildings(df):
    """
    Filters any DataFrame with a 'building_id' column to only include buildings
    the current user is allowed to access.
    """
    role = st.session_state.get("role")
    user_id = st.session_state.get("user_id")

    if role == "admin":
        return df

    if "building_id" not in df.columns:
        return df  # ⛔ Can't filter — column not present

    allowed_ids = get_user_building_ids(None, user_id)
    return df[df["building_id"].isin(allowed_ids)]
