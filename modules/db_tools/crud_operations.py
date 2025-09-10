"""Database CRUD operation utilities."""
import pandas as pd
import bcrypt
import streamlit as st

from .db_connection import get_engine


def _read_sql(query, params=None):
    """Helper to execute SQL queries and return a DataFrame."""
    return pd.read_sql(query, get_engine(), params=params)


def get_buildings(conn):
    """Return a DataFrame of all buildings."""
    query = "SELECT * FROM buildings;"
    return _read_sql(query)


def get_dashboard_counts(conn):
    """Return counts for dashboard metrics."""
    query = """
        SELECT
            (SELECT COUNT(*) FROM buildings) AS total_buildings,
            (SELECT COUNT(*) FROM apartments WHERE apartment_number NOT IN ('0', '00', '000')) AS total_apartments,
            (
                SELECT COUNT(*)
                FROM residents
                WHERE is_active = TRUE AND end_date IS NULL
            ) AS active_residents
    """
    return _read_sql(query)


def add_building(conn, name, city, street, home_number):
    """Insert a new building and return its ID."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO buildings (building_name, city, street, home_number)
            VALUES (%s, %s, %s, %s)
            RETURNING building_id;
        """, (name, city, street, home_number))
        building_id = cur.fetchone()[0]
        conn.commit()
    return building_id


def update_building(
    conn,
    building_id,
    name,
    city,
    street,
    home_number,
    postal_code,
    building_code,
    vaad_name,
    bank_name,
    bank_branch,
    bank_account,
    bank_number,
    vaad_representative,
    contact_phone,
    contact_email,
):
    """Update all building details."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE buildings
            SET building_name = %s,
                city = %s,
                street = %s,
                home_number = %s,
                postal_code = %s,
                building_code = %s,
                vaad_name = %s,
                bank_name = %s,
                bank_branch = %s,
                bank_account = %s,
                bank_number = %s,
                vaad_representative = %s,
                contact_phone = %s,
                contact_email = %s
            WHERE building_id = %s;
            """,
            (
                name,
                city,
                street,
                home_number,
                postal_code,
                building_code,
                vaad_name,
                bank_name,
                bank_branch,
                bank_account,
                bank_number,
                vaad_representative,
                contact_phone,
                contact_email,
                building_id,
            ),
        )
        conn.commit()


def log_invoice_send(conn, invoice_id, email):
    """Record that an invoice was emailed."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO invoice_log (invoice_id, sent_to_email)
            VALUES (%s, %s);
        """, (invoice_id, email))
        conn.commit()

def generate_expected_charges(conn, building_id, month):
    """Generate expected charges for a month."""
    with conn.cursor() as cur:
        cur.execute("SELECT generate_expected_charges(%s, %s);", (building_id, month))
        conn.commit()

def delete_building(conn, building_id):
    """Delete a building record."""
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM buildings WHERE building_id = %s;
        """, (building_id,))
        conn.commit()

def get_db_activity(conn):
    """
    Returns active and idle connections from pg_stat_activity for the current database.
    """
    query = """
        SELECT pid, usename, state, query_start, state_change, query
        FROM pg_stat_activity
        WHERE datname = current_database()
        ORDER BY state DESC, query_start DESC;
    """
    return _read_sql(query)

def terminate_connection(conn, pid):
    """
    Terminates a specific backend process by PID.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        conn.commit()


def upsert_bulk_apartment_fees(conn, building_id, monthly_fee):
    """Insert or update monthly fee settings for apartments."""
    with conn.cursor() as cur:
        # Insert missing rows
        cur.execute("""
            INSERT INTO apartment_charge_settings (apartment_id, building_id, monthly_fee, charge_type)
            SELECT a.apartment_id, a.building_id, %s, 'monthly fee'
            FROM apartments a
            WHERE a.building_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM apartment_charge_settings s
                  WHERE s.apartment_id = a.apartment_id
              );
        """, (monthly_fee, building_id))

        # Update all existing
        cur.execute("""
            UPDATE apartment_charge_settings s
            SET monthly_fee = %s
            FROM apartments a
            WHERE s.apartment_id = a.apartment_id AND a.building_id = %s;
        """, (monthly_fee, building_id))

        conn.commit()



def get_apartments_by_building(conn, building_id):
    """Get apartments belonging to a building."""
    query = """
        SELECT * FROM apartments
        WHERE building_id = %s
        ORDER BY floor, apartment_number;
    """
    return _read_sql(query, params=(building_id,))

def get_residents_by_building(conn, building_id):
    """Get active residents for a building."""
    query = """
        SELECT r.*
        FROM residents r
        JOIN apartments a ON r.apartment_id = a.apartment_id
        WHERE a.building_id = %s
          AND r.is_active = TRUE
          AND r.end_date IS NULL
        ORDER BY a.floor, a.apartment_number;
    """
    return _read_sql(query, params=(building_id,))


def get_financial_summary_range(conn, start_date, end_date, building_id=None, exclude_apartment_0=False):
    """Summarize income and expenses for a date range."""
    query = """
        SELECT
            -- Total Expected Income
            (SELECT COALESCE(SUM(ec.expected_amount), 0)
             FROM expected_charges ec
             LEFT JOIN apartments ea ON ec.apartment_id = ea.apartment_id
             WHERE ec.charge_month BETWEEN %s AND %s
               AND (%s IS NULL OR ec.building_id = %s)
               AND (%s = FALSE OR (ec.apartment_id != 0 AND ea.apartment_number <> '0'))
            ) AS total_expected,

            -- Total Paid
            (SELECT COALESCE(SUM(t.amount_paid), 0)
             FROM transactions t
             LEFT JOIN apartments ta ON t.apartment_id = ta.apartment_id
             WHERE t.charge_month BETWEEN %s AND %s
               AND (%s IS NULL OR t.building_id = %s)
               AND (%s = FALSE OR (t.apartment_id != 0 AND ta.apartment_number <> '0'))
            ) AS total_paid,

            -- Total Expenses (only paid ones)
            (SELECT COALESCE(SUM(cost), 0)
             FROM payments p
             JOIN expenses e ON p.expense_id = e.expense_id
             WHERE p.charge_month BETWEEN %s AND %s
               AND (%s IS NULL OR e.building_id = %s)
               AND e.status = 'paid'
            ) AS total_expenses;
    """

    params = [
        start_date, end_date, building_id, building_id, exclude_apartment_0,       # expected
        start_date, end_date, building_id, building_id, exclude_apartment_0,       # paid
        start_date, end_date, building_id, building_id                             # expenses
    ]

    return _read_sql(query, params=params)



def get_expense_details_range(conn, start_date, end_date, building_id=None):
    """Retrieve detailed expenses for a date range.

    In addition to the monthly payment details used on the dashboard, this
    function now returns the original expense metadata so the expenses page can
    display the full set of columns.
    """
    query = """
        SELECT p.charge_year,
               p.charge_month_num,
               b.building_name,
               s.supplier_name,
               e.supplier_receipt_id,
               e.start_date,
               e.end_date,
               e.total_cost,
               e.monthly_cost,
               e.num_payments,
               p.cost,
               p.expense_type,
               e.status,
               e.notes,
               e.expense_id
        FROM payments p
        JOIN expenses e ON p.expense_id = e.expense_id
        JOIN suppliers s ON e.supplier_id = s.supplier_id
        JOIN buildings b ON e.building_id = b.building_id
        WHERE p.charge_month BETWEEN %s AND %s
    """
    params = [start_date, end_date]

    if building_id:
        query += " AND e.building_id = %s"
        params.append(building_id)

    return _read_sql(query, params=params)
def insert_bulk_transactions(conn, building_id, records, payment_date, method):
    """Bulk insert transaction records."""
    """
    Inserts transactions for (apartment_id, charge_month) pairs.
    Returns number of successful inserts and a list of skipped entries with reasons.
    """
    inserted = 0
    skipped = []

    with conn.cursor() as cur:
        for apartment_id, charge_month in records:
            # Check for active resident
            cur.execute(
                """
                SELECT resident_id FROM residents
                WHERE apartment_id = %s
                  AND is_active = TRUE
                  AND end_date IS NULL
                """,
                (apartment_id,),
            )
            res = cur.fetchone()
            if not res:
                skipped.append((apartment_id, charge_month, "No active resident"))
                continue
            resident_id = res[0]

            # Check for monthly fee
            cur.execute("""
                SELECT monthly_fee FROM apartment_charge_settings
                WHERE apartment_id = %s
            """, (apartment_id,))
            fee = cur.fetchone()
            if not fee:
                skipped.append((apartment_id, charge_month, "No monthly fee set"))
                continue
            amount_paid = fee[0]

            # Insert transaction
            cur.execute("""
                INSERT INTO transactions (
                    building_id, apartment_id, resident_id,
                    charge_month, payment_date, amount_paid, method
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                building_id, apartment_id, resident_id,
                charge_month, payment_date, amount_paid, method
            ))
            inserted += 1

    conn.commit()
    return inserted, skipped


def import_expenses_from_df(conn, df):
    """Import expenses from a DataFrame."""
    required_cols = {
        "building_id",
        "supplier_id",
        "supplier_receipt_id",
        "start_date",
        "num_payments",
        "total_cost",
        "status",
    }

    if not required_cols.issubset(df.columns):
        raise ValueError("missing_columns")

    inserted = 0
    skipped = []

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            try:
                building_id = int(row["building_id"])
                supplier_id = int(row["supplier_id"])
                receipt_id = str(row.get("supplier_receipt_id", ""))
                start_date = pd.to_datetime(
                    str(row["start_date"]).strip(),
                    format="%d/%m/%Y",
                    dayfirst=True,
                ).date()
                num_payments = int(row.get("num_payments", 1))
                total_cost = float(row.get("total_cost", 0))
                status = str(row.get("status", "pending"))
                notes = str(row.get("notes", ""))

                if num_payments <= 0:
                    raise ValueError("invalid_payments")
            except Exception:
                skipped.append((receipt_id, row.get("start_date"), "invalid_data"))
                continue

            end_date = (
                pd.to_datetime(start_date)
                + pd.DateOffset(months=num_payments - 1)
                + pd.offsets.MonthEnd(0)
            ).date()
            monthly_cost = total_cost / num_payments

            cur.execute(
                """
                INSERT INTO expenses (
                    building_id, supplier_id, supplier_receipt_id,
                    start_date, end_date, total_cost, monthly_cost,
                    num_payments, status, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    building_id,
                    supplier_id,
                    receipt_id,
                    start_date,
                    end_date,
                    total_cost,
                    monthly_cost,
                    num_payments,
                    status,
                    notes,
                ),
            )
            inserted += 1

    conn.commit()
    return inserted, skipped


def import_transactions_from_df(conn, df):
    """Import transactions from a DataFrame."""
    required_cols = {
        "building_id",
        "apartment_number",
        "charge_month",
        "payment_date",
        "amount_paid",
        "method",
    }

    if not required_cols.issubset(df.columns):
        raise ValueError("missing_columns")

    inserted = 0
    skipped = []

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            building_id = int(row["building_id"])
            apt_number = str(row["apartment_number"]).strip()

            try:
                charge_month = (
                    pd.to_datetime(str(row["charge_month"]).strip(), format="%d/%m/%Y", dayfirst=True)
                    .date()
                    .replace(day=1)
                )
                payment_date = pd.to_datetime(
                    str(row["payment_date"]).strip(), format="%d/%m/%Y", dayfirst=True
                ).date()
            except Exception:
                skipped.append((apt_number, row.get("charge_month"), "invalid_dates"))
                continue

            amount_paid = float(row.get("amount_paid", 0))
            method = str(row.get("method", "Cash"))

            cur.execute(
                "SELECT apartment_id FROM apartments WHERE building_id = %s AND apartment_number = %s",
                (building_id, apt_number),
            )
            apt_res = cur.fetchone()
            if not apt_res:
                skipped.append((apt_number, charge_month, "apartment_not_found"))
                continue
            apartment_id = apt_res[0]

            cur.execute(
                "SELECT resident_id FROM residents WHERE apartment_id = %s AND is_active = TRUE AND end_date IS NULL",
                (apartment_id,),
            )
            res = cur.fetchone()
            if not res:
                skipped.append((apt_number, charge_month, "no_active_resident"))
                continue
            resident_id = res[0]

            cur.execute(
                """
                INSERT INTO transactions (
                    building_id, apartment_id, resident_id,
                    charge_month, payment_date, amount_paid, method
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    building_id,
                    apartment_id,
                    resident_id,
                    charge_month,
                    payment_date,
                    amount_paid,
                    method,
                ),
            )
            inserted += 1

    conn.commit()
    return inserted, skipped
def sync_supabase_user(conn, email, role):
    """Create a local user record from Supabase data."""
    with conn.cursor() as cur:
        # Check if user exists
        cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        exists = cur.fetchone()
        if not exists:
            # Insert with username = email
            cur.execute("""
                INSERT INTO users (username, email, role)
                VALUES (%s, %s, %s)
            """, (email, email, role))
            conn.commit()



def get_unpaid_apartments_for_period(conn, building_id, year, months: list):
    """Return unpaid apartments for specified months."""
    """
    Returns all unpaid apartments in a building for the specified year and list of months.
    """
    query = """
        SELECT *, charge_month_num AS month_num
        FROM view_unpaid_apartments
        WHERE building_id = %s
          AND charge_year = %s
          AND charge_month_num = ANY(%s)
    """
    return _read_sql(query, params=(building_id, year, months))


def get_unpaid_apartments_range(conn, start_date, end_date, building_id):
    """Return unpaid apartments within a date range."""
    query = """
        SELECT ec.charge_month, b.building_name, a.apartment_number, ec.expected_amount
        FROM expected_charges ec
        JOIN apartments a ON ec.apartment_id = a.apartment_id
        JOIN buildings b ON ec.building_id = b.building_id
        LEFT JOIN transactions t
            ON ec.apartment_id = t.apartment_id
           AND ec.charge_month = t.charge_month
        WHERE ec.charge_month BETWEEN %s AND %s
          AND ec.building_id = %s
          AND t.transaction_id IS NULL
    """
    params = [start_date, end_date, building_id]

    return _read_sql(query, params=params)



def get_financial_summary(conn, year=None, month=None, building_id=None, exclude_apartment_0=False):
    """Summarize expected income, payments and expenses."""
    query = """
        SELECT
            -- Total Expected Income
            (SELECT COALESCE(SUM(ec.expected_amount), 0)
             FROM expected_charges ec
             LEFT JOIN apartments ea ON ec.apartment_id = ea.apartment_id
             WHERE (%s IS NULL OR EXTRACT(YEAR FROM ec.charge_month) = %s)
               AND (%s IS NULL OR EXTRACT(MONTH FROM ec.charge_month) = %s)
               AND (%s IS NULL OR ec.building_id = %s)
               AND (%s = FALSE OR (ec.apartment_id != 0 AND ea.apartment_number <> '0'))
            ) AS total_expected,

            -- Total Paid
            (SELECT COALESCE(SUM(t.amount_paid), 0)
             FROM transactions t
             LEFT JOIN apartments ta ON t.apartment_id = ta.apartment_id
             WHERE (%s IS NULL OR EXTRACT(YEAR FROM t.charge_month) = %s)
               AND (%s IS NULL OR EXTRACT(MONTH FROM t.charge_month) = %s)
               AND (%s IS NULL OR t.building_id = %s)
               AND (%s = FALSE OR (t.apartment_id != 0 AND ta.apartment_number <> '0'))
            ) AS total_paid,

            -- Total Expenses
            (SELECT COALESCE(SUM(cost), 0)
             FROM payments p
             JOIN expenses e ON p.expense_id = e.expense_id
             WHERE (%s IS NULL OR EXTRACT(YEAR FROM p.charge_month) = %s)
               AND (%s IS NULL OR EXTRACT(MONTH FROM p.charge_month) = %s)
               AND (%s IS NULL OR e.building_id = %s)
            ) AS total_expenses;
    """

    params = [
        year, year, month, month, building_id, building_id, exclude_apartment_0,   # expected
        year, year, month, month, building_id, building_id, exclude_apartment_0,   # paid
        year, year, month, month, building_id, building_id                         # expenses
    ]

    return _read_sql(query, params=params)


def get_residents_by_building_full(conn, building_id, active_only=False):
    """Return residents for a building.

    If ``active_only`` is ``True``, only residents that are active and have
    no end date are returned.
    """
    query = """
        SELECT r.resident_id, r.apartment_id, a.floor, a.apartment_number,
               r.first_name, r.last_name, r.phone, r.email, r.role,
               r.start_date, r.end_date, r.is_active
        FROM residents r
        JOIN apartments a ON r.apartment_id = a.apartment_id
        WHERE a.building_id = %s
    """
    params = [building_id]
    if active_only:
        query += " AND r.is_active = TRUE AND r.end_date IS NULL"
    query += " ORDER BY a.floor, a.apartment_number, r.role"

    return _read_sql(query, params=params)


def set_active_resident(conn, resident_id, apartment_id):
    """Set the active resident for an apartment."""
    with conn.cursor() as cur:
        cur.execute("UPDATE residents SET is_active = FALSE WHERE apartment_id = %s;", (apartment_id,))
        cur.execute("UPDATE residents SET is_active = TRUE WHERE resident_id = %s;", (resident_id,))
        conn.commit()


def deactivate_resident(conn, resident_id):
    """Soft delete a resident by marking them inactive."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE residents
            SET end_date = CURRENT_DATE,
                is_active = FALSE
            WHERE resident_id = %s
            """,
            (resident_id,),
        )
        conn.commit()


def get_unpaid_apartments(conn, building_id, year, month):
    """Return unpaid apartments for a specific month."""
    query = """
        SELECT *
        FROM view_unpaid_apartments
        WHERE building_id = %s
          AND charge_year = %s
          AND charge_month_num = %s
    """
    return _read_sql(query, params=(building_id, year, month))

def get_expected_charge_years(conn):
    """
    Returns a list of distinct years found in expected_charges.
    """
    query = """
        SELECT DISTINCT charge_year
        FROM expected_charges
        ORDER BY charge_year DESC
    """
    df = _read_sql(query)
    return df["charge_year"].tolist()


def has_expected_charges_for_period(conn, building_id, year, months: list):
    """Check if expected charges exist for given months in a building."""
    query = """
        SELECT 1
        FROM expected_charges
        WHERE building_id = %s
          AND charge_year = %s
          AND charge_month_num = ANY(%s)
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(query, (building_id, year, months))
        return cur.fetchone() is not None


def get_expected_income_details(conn, year, month=None, building_id=None):
    """Get detailed expected income records."""
    query = """
        SELECT ec.charge_year, ec.charge_month_num, b.building_name,
               a.apartment_number, ec.expected_amount, ec.charge_type
        FROM expected_charges ec
        JOIN apartments a ON ec.apartment_id = a.apartment_id
        JOIN buildings b ON ec.building_id = b.building_id
        WHERE ec.charge_year = %s
    """
    params = [year]

    if month:
        query += " AND ec.charge_month_num = %s"
        params.append(month)

    if building_id:
        query += " AND ec.building_id = %s"
        params.append(building_id)

    return _read_sql(query, params=params)


def get_expense_details(conn, year, month=None, building_id=None):
    """Get detailed expense payment records."""
    query = """
        SELECT p.charge_year, p.charge_month_num, b.building_name,
               s.supplier_name, p.cost, p.expense_type
        FROM payments p
        JOIN expenses e ON p.expense_id = e.expense_id
        JOIN suppliers s ON e.supplier_id = s.supplier_id
        JOIN buildings b ON e.building_id = b.building_id
        WHERE p.charge_year = %s
    """
    params = [year]

    if month:
        query += " AND p.charge_month_num = %s"
        params.append(month)

    if building_id:
        query += " AND e.building_id = %s"
        params.append(building_id)

    return _read_sql(query, params=params)

# --- SUPPLIERS ---
def get_suppliers_by_building(conn, building_id):
    """Get suppliers linked to a building."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.*
            FROM suppliers s
            JOIN building_suppliers bs ON s.supplier_id = bs.supplier_id
            WHERE bs.building_id = %s
        """, (building_id,))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=cols)


def get_suppliers(conn, user_id=None):
    """Get suppliers accessible to the current user."""
    with conn.cursor() as cur:
        if user_id is None or st.session_state.get("role") == "admin":
            cur.execute("SELECT * FROM suppliers")
        else:
            cur.execute("""
                SELECT DISTINCT s.*
                FROM suppliers s
                JOIN building_suppliers bs ON s.supplier_id = bs.supplier_id
                JOIN user_buildings ub ON bs.building_id = ub.building_id
                WHERE ub.user_id = %s
            """, (user_id,))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=cols)

def add_supplier(conn, name, expense_type, segment, building_ids):
    """Add a supplier and link it to buildings.

    If a supplier with the given name already exists, it will simply be linked
    to the provided buildings instead of inserting a duplicate record.
    """
    with conn.cursor() as cur:
        # Check if supplier already exists
        cur.execute(
            "SELECT supplier_id FROM suppliers WHERE supplier_name = %s;",
            (name,)
        )
        row = cur.fetchone()

        if row:
            supplier_id = row[0]
        else:
            # Insert new supplier
            cur.execute(
                """
                INSERT INTO suppliers (supplier_name, expense_type, segment)
                VALUES (%s, %s, %s)
                RETURNING supplier_id;
                """,
                (name, expense_type, segment),
            )
            supplier_id = cur.fetchone()[0]

        # Link supplier to selected buildings
        for b_id in building_ids:
            cur.execute(
                """
                INSERT INTO building_suppliers (building_id, supplier_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (b_id, supplier_id),
            )

        conn.commit()




def update_supplier(conn, supplier_id, name, expense_type, segment):
    """Update supplier information."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE suppliers
            SET supplier_name = %s,
                expense_type = %s,
                segment = %s
            WHERE supplier_id = %s;
        """, (name, expense_type, segment, supplier_id))
        conn.commit()

def delete_supplier(conn, supplier_id):
    """Remove a supplier from the system."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM suppliers WHERE supplier_id = %s;", (supplier_id,))
        conn.commit()


# --- EXPENSES ---

def get_expenses(conn):
    """Retrieve all expenses."""
    query = """
        SELECT e.expense_id, b.building_name,b.building_id, s.supplier_name,
               e.supplier_id,  -- ✅ add this
               e.supplier_receipt_id, e.start_date, e.end_date,
               e.total_cost, e.monthly_cost, e.num_payments,
               e.expense_type, e.status, e.notes
        FROM expenses e
        JOIN suppliers s ON e.supplier_id = s.supplier_id
        JOIN buildings b ON e.building_id = b.building_id
        ORDER BY e.start_date DESC;
    """
    return _read_sql(query)


def add_expense(
    conn,
    building_id,
    supplier_id,
    receipt_id,
    start_date,
    end_date,
    total_cost,
    monthly_cost,
    num_payments,
    status,
    notes,
):
    """Add a new expense entry and return its ID."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO expenses (
                building_id, supplier_id, supplier_receipt_id,
                start_date, end_date, total_cost, monthly_cost,
                num_payments, status, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING expense_id;
        """,
            (
                building_id,
                supplier_id,
                receipt_id,
                start_date,
                end_date,
                total_cost,
                monthly_cost,
                num_payments,
                status,
                notes,
            ),
        )
        expense_id = cur.fetchone()[0]
        conn.commit()
        return expense_id

def update_expense(conn, expense_id, supplier_id, receipt_id, start_date, end_date, total_cost, monthly_cost, num_payments, expense_type, status, notes):
    """Update an existing expense entry."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE expenses
            SET supplier_id = %s,
                supplier_receipt_id = %s,
                start_date = %s,
                end_date = %s,
                total_cost = %s,
                monthly_cost = %s,
                num_payments = %s,
                expense_type = %s,
                status = %s,
                notes = %s
            WHERE expense_id = %s;
        """, (
            supplier_id, receipt_id, start_date, end_date,
            total_cost, monthly_cost, num_payments,
            expense_type, status, notes, expense_id
        ))
        conn.commit()


def delete_expense(conn, expense_id):
    """Delete an expense entry."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM expenses WHERE expense_id = %s;", (expense_id,))
        conn.commit()


def add_expense_document(conn, building_id, expense_id, file_name, file_url):
    """Insert a document record for an expense."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO expense_documents (building_id, expense_id, file_name, file_url)
            VALUES (%s, %s, %s, %s)
            RETURNING doc_id;
        """,
            (building_id, expense_id, file_name, file_url),
        )
        doc_id = cur.fetchone()[0]
        conn.commit()
        return doc_id


def get_expense_documents(conn, expense_id):
    """Retrieve documents linked to an expense."""
    query = "SELECT * FROM expense_documents WHERE expense_id = %s ORDER BY doc_id;"
    return _read_sql(query, params=(expense_id,))


def delete_expense_document(conn, doc_id):
    """Delete a document record."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM expense_documents WHERE doc_id = %s;", (doc_id,))
        conn.commit()


def get_expense_document_counts(conn):
    """Return a dataframe of document counts per expense."""
    query = "SELECT expense_id, COUNT(*) AS doc_count FROM expense_documents GROUP BY expense_id;"
    return _read_sql(query)




def create_user(conn, username, password, email, role='user'):
    """Create a new user account."""
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO users (username, password_hash, email, role)
            VALUES (%s, %s, %s, %s)
        """, (username, hashed, email, role))
        conn.commit()

def get_user_by_username(conn, username):
    """Fetch a user record by username."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchone()


def get_user_id(conn, username):
    """Get a user's ID from their username."""
    with conn.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE username = %s;", (username,))
        result = cur.fetchone()
        return result[0] if result else None

def get_user_role(conn, username):
    """Get the role for a user."""
    with conn.cursor() as cur:
        cur.execute("SELECT role FROM users WHERE username = %s;", (username,))
        result = cur.fetchone()
        return result[0] if result else "user"

def get_buildings_by_user(conn, user_id, role):
    """List buildings accessible to a user."""
    if role == "admin":
        return get_buildings(conn)
    else:
        query = """
            SELECT b.*
            FROM buildings b
            JOIN user_buildings ub ON b.building_id = ub.building_id
            WHERE ub.user_id = %s;
        """
        return _read_sql(query, params=(user_id,))


def get_all_users(conn):
    """Return all users."""
    query = """
        SELECT user_id, username, email, role, last_login
        FROM users
        ORDER BY username;
    """
    return _read_sql(query)


def get_all_buildings(conn):
    """Return basic building info for all buildings."""
    return _read_sql(
        "SELECT building_id, building_name FROM buildings ORDER BY building_name;"
    )

def get_user_building_ids(conn, user_id):
    """Get building IDs linked to a user."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT building_id FROM user_buildings WHERE user_id = %s;
        """, (int(user_id),))  # 👈 Cast here to native int
        return [row[0] for row in cur.fetchall()]


def update_user_buildings(conn, user_id, building_ids):
    """Update building assignments for a user."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_buildings WHERE user_id = %s;", (user_id,))
        for b_id in building_ids:
            cur.execute("INSERT INTO user_buildings (user_id, building_id) VALUES (%s, %s);", (user_id, b_id))
        conn.commit()

def get_allowed_suppliers(conn, user_id):
    """List suppliers a user can access."""
    """Returns a DataFrame of suppliers that the user has access to (via expenses -> buildings)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT s.*
            FROM suppliers s
            JOIN expenses e ON s.supplier_id = e.supplier_id
            JOIN user_buildings ub ON e.building_id = ub.building_id
            WHERE ub.user_id = %s
        """, (user_id,))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=cols)


def get_paid_transactions(conn, building_id=None, selected_month=None):
    """Retrieve paid transactions with optional filters."""
    query = """
        SELECT
            t.transaction_id,
            t.apartment_id,
            t.resident_id,
            t.building_id,
            b.building_name,
            a.apartment_number,
            r.first_name || ' ' || r.last_name AS resident_name,
            r.email,
            t.charge_month,
            t.payment_date,
            t.amount_paid,
            t.method,
            EXISTS (
                SELECT 1
                FROM invoices i
                JOIN invoice_log il ON i.invoice_id = il.invoice_id
                WHERE i.building_id = t.building_id
                  AND i.apartment_id = t.apartment_id
                  AND i.resident_id = t.resident_id
                  AND i.invoice_date = t.payment_date
                  AND i.total_paid = t.amount_paid
                  AND i.payment_method = t.method
            ) AS invoice_sent
        FROM transactions t
        LEFT JOIN apartments a ON t.apartment_id = a.apartment_id
        LEFT JOIN residents r ON t.resident_id = r.resident_id
        LEFT JOIN buildings b ON t.building_id = b.building_id
        WHERE t.amount_paid > 0
    """

    params = []

    if building_id is not None:
        query += " AND t.building_id = %s"
        params.append(building_id)

    if selected_month is not None:
        query += " AND DATE_TRUNC('month', t.charge_month) = DATE_TRUNC('month', %s)"
        params.append(selected_month)

    query += " ORDER BY t.payment_date DESC"

    return _read_sql(query, params=params)





def create_invoice(conn, transaction_row):
    """Create an invoice based on a transaction."""
    import datetime

    building_id = int(transaction_row["building_id"])
    apartment_id = int(transaction_row["apartment_id"])
    resident_id = int(transaction_row["resident_id"])
    amount_paid = float(transaction_row["amount_paid"])
    payment_method = str(transaction_row["method"])

    # Normalize payment_date
    payment_date = transaction_row["payment_date"]
    if hasattr(payment_date, "to_pydatetime"):
        payment_date = payment_date.to_pydatetime().date()
    elif isinstance(payment_date, datetime.datetime):
        payment_date = payment_date.date()

    today = datetime.date.today()

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO invoices (
                building_id,
                apartment_id,
                resident_id,
                invoice_date,
                issue_date,
                total_due,
                total_paid,
                status,
                notes,
                invoice_year,
                invoice_month_num,
                invoice_day,
                issue_year,
                issue_month,
                issue_day,
                payment_method
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING invoice_id;
        """, (
            building_id,
            apartment_id,
            resident_id,
            payment_date,
            today,
            amount_paid,
            amount_paid,
            'issued',  # 🟢 was missing from placeholders
            'Generated from transaction',
            payment_date.year,
            payment_date.month,
            payment_date.day,
            today.year,
            today.month,
            today.day,
            payment_method,
        ))

        invoice_id = cur.fetchone()[0]
        conn.commit()
        return invoice_id



def update_user(conn, user_id, email, role):
    """Update user email and role."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET email = %s, role = %s WHERE user_id = %s;",
            (email, role, int(user_id))  # 👈 Cast to native int
        )
        conn.commit()


def delete_user(conn, user_id):
    """Remove a user from the database."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE user_id = %s;", (user_id,))
        conn.commit()


def get_last_logins(conn, user_id, limit=5):
    """Get recent login timestamps for a user."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT login_time FROM user_sessions
            WHERE user_id = %s
            ORDER BY login_time DESC
            LIMIT %s;
        """, (user_id, limit))  # 👈 already cast above
        return [r[0].strftime("%Y-%m-%d %H:%M") for r in cur.fetchall()]



def get_user_session_count(conn, user_id):
    """Count sessions recorded for a user."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM user_sessions WHERE user_id = %s;",
            (int(user_id),)  # 👈 Fix: cast to native Python int
        )
        result = cur.fetchone()
        return result[0] if result else 0


def get_special_transactions_balance(conn, start_date, end_date, building_id=None):
    """Sum special transactions over a period.

    Special transactions are recorded under the "apartment 0" placeholder for
    each building.  Older data may have used an explicit ``apartment_id`` of
    ``0`` while newer entries rely on an apartment record with
    ``apartment_number = '0'``.  To support both approaches we include
    transactions matching either style for the requested building.
    """

    query = """
        SELECT COALESCE(SUM(t.amount_paid), 0) AS special_balance
        FROM transactions t
        LEFT JOIN apartments a ON t.apartment_id = a.apartment_id
        WHERE t.charge_month BETWEEN %s AND %s
          AND (%s IS NULL OR t.building_id = %s)
          AND (t.apartment_id = 0 OR a.apartment_number = '0')
    """

    params = [start_date, end_date, building_id, building_id]
    result = _read_sql(query, params=params)
    return result.at[0, "special_balance"]


def count_active_users(conn, within_minutes=5):
    """Count active users within a timeframe."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM users
            WHERE last_active > NOW() - INTERVAL '%s minutes'
        """, (within_minutes,))
        return cur.fetchone()[0]

def get_active_users(conn, within_minutes=5):
    """Get active user details."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT username, role, last_active
            FROM users
            WHERE last_active > NOW() - INTERVAL '%s minutes'
            ORDER BY last_active DESC
        """, (within_minutes,))
        return cur.fetchall()


def export_building_data(conn, building_id):
    """Return a zip archive with building related data as CSV files."""
    import io
    import zipfile

    dataframes = {
        "buildings": _read_sql(
            "SELECT * FROM buildings WHERE building_id = %s", params=(building_id,),
        ),
        "apartments": get_apartments_by_building(conn, building_id),
        "residents": get_residents_by_building_full(conn, building_id),
        "expenses": _read_sql(
            "SELECT * FROM expenses WHERE building_id = %s", params=(building_id,),
        ),
        "transactions": _read_sql(
            "SELECT * FROM transactions WHERE building_id = %s", params=(building_id,),
        ),
        "invoices": _read_sql(
            "SELECT * FROM invoices WHERE building_id = %s", params=(building_id,),
        ),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for name, df in dataframes.items():
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            zipf.writestr(f"{name}.csv", csv_bytes)

    buffer.seek(0)
    return buffer


def delete_last_reconciliation(conn, building_id):
    """Delete the most recent manual reconciliation."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT transaction_id
            FROM transactions
            WHERE building_id = %s
              AND apartment_id = 0
              AND method = 'manual_reconciliation'
            ORDER BY payment_date DESC, transaction_id DESC
            LIMIT 1
        """, (building_id,))
        result = cur.fetchone()

        if result:
            transaction_id = result[0]
            cur.execute("DELETE FROM transactions WHERE transaction_id = %s", (transaction_id,))
            conn.commit()
            return True
        else:
            return False


def is_first_login(conn, user_id):
    """Check whether a user has never logged in."""
    with conn.cursor() as cur:
        cur.execute("""
        SELECT last_active 
        FROM users
        WHERE user_id = %s
        """, (user_id,))
        result = cur.fetchone()

        # Check if record exists and if last_active is null
        if result is None:
            # User doesn't exist
            return False

        # result[0] is the last_active value
        return result[0] is None


def submit_ticket(conn, user_id, building_id, subject, message):
    """Insert a new support ticket."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO support_tickets (user_id, building_id, subject, message)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, building_id, subject, message),
        )
        conn.commit()


def get_support_tickets_by_buildings(conn, building_ids):
    """Return support tickets for the given building IDs."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT st.ticket_id, b.building_name, st.subject, st.status, st.created_at
            FROM support_tickets st
            JOIN buildings b ON st.building_id = b.building_id
            WHERE st.building_id = ANY(%s)
            ORDER BY st.created_at DESC
            """,
            (building_ids,),
        )
        return cur.fetchall()


def get_open_support_tickets(conn):
    """Return all open support tickets with user and building info."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT st.ticket_id, u.username, b.building_name, st.subject, st.message, st.status, st.created_at
            FROM support_tickets st
            JOIN users u ON st.user_id = u.user_id
            JOIN buildings b ON st.building_id = b.building_id
            WHERE st.status = 'open'
            ORDER BY st.created_at DESC
            """
        )
        return cur.fetchall()


def update_support_ticket_status(conn, ticket_id, status):
    """Update the status for a support ticket."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE support_tickets SET status = %s WHERE ticket_id = %s",
            (status, ticket_id),
        )
        conn.commit()


def delete_support_ticket(conn, ticket_id):
    """Delete a support ticket by ID."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM support_tickets WHERE ticket_id = %s", (ticket_id,))
        conn.commit()
