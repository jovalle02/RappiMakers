"""DuckDB database layer. Loads the clean CSV and exposes query helpers."""

import os
import threading
import duckdb

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "processing_data", "data", "availability.csv")

_db_path = os.path.join(os.path.dirname(__file__), "..", "processing_data", "data", "availability.duckdb")
_lock = threading.Lock()
_initialized = False


def init_db():
    """Load the clean CSV into a persistent DuckDB database."""
    global _initialized
    # Remove stale db file to force fresh load
    if os.path.exists(_db_path):
        os.remove(_db_path)
    con = duckdb.connect(_db_path)
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS availability AS
        SELECT
            CAST(timestamp AS TIMESTAMP) as timestamp,
            store_count,
            CAST(date AS DATE) as date,
            hour,
            minute,
            day_of_week,
            day_num,
            pct_change,
            rolling_avg_30m,
            daily_pct,
            z_score,
            is_anomaly
        FROM read_csv('{DATA_PATH.replace(os.sep, "/")}', auto_detect=true)
    """)
    count = con.execute("SELECT COUNT(*) FROM availability").fetchone()[0]
    print(f"Loaded {count:,} rows into DuckDB")
    con.close()
    _initialized = True


def query(sql: str, params: list | None = None) -> list[dict]:
    """Execute SQL using a fresh connection per query (thread-safe)."""
    con = duckdb.connect(_db_path, read_only=True)
    try:
        result = con.execute(sql, params or [])
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        con.close()
