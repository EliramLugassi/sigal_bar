"""Database connection management."""
import psycopg2
import streamlit as st
import os

from dotenv import load_dotenv


load_dotenv()


def _create_connection():
    """Create a new database connection."""
    return psycopg2.connect(
        dbname=os.getenv("SUPABASE_DB_NAME"),
        user=os.getenv("SUPABASE_DB_USER"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        host=os.getenv("SUPABASE_DB_HOST"),
        port=os.getenv("SUPABASE_DB_PORT"),
    )


def get_connection():
    """Return an active database connection, reconnecting if needed."""
    conn = st.session_state.get("db_conn")
    if conn is None or conn.closed:
        conn = _create_connection()
        st.session_state["db_conn"] = conn
    return conn
