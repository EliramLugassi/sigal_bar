"""Database connection management."""
import os

import psycopg2
import streamlit as st
from sqlalchemy import create_engine

from dotenv import load_dotenv


load_dotenv()


def _create_engine():
    """Create a new SQLAlchemy engine for the database."""
    return create_engine(
        "postgresql+psycopg2://{}:{}@{}:{}/{}".format(
            os.getenv("SUPABASE_DB_USER"),
            os.getenv("SUPABASE_DB_PASSWORD"),
            os.getenv("SUPABASE_DB_HOST"),
            os.getenv("SUPABASE_DB_PORT"),
            os.getenv("SUPABASE_DB_NAME"),
        )
    )


def _create_connection():
    """Create a new database connection."""
    return psycopg2.connect(
        dbname=os.getenv("SUPABASE_DB_NAME"),
        user=os.getenv("SUPABASE_DB_USER"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        host=os.getenv("SUPABASE_DB_HOST"),
        port=os.getenv("SUPABASE_DB_PORT"),
    )


def get_engine():
    """Return a SQLAlchemy engine, creating it if necessary."""
    engine = st.session_state.get("db_engine")
    if engine is None:
        engine = _create_engine()
        st.session_state["db_engine"] = engine
    return engine


def get_connection():
    """Return an active database connection, reconnecting if needed."""
    conn = st.session_state.get("db_conn")
    if conn is None or conn.closed:
        conn = _create_connection()
        st.session_state["db_conn"] = conn
    return conn
