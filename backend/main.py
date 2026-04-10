"""FastAPI backend serving store availability data from DuckDB."""

import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db, query
from chat import router as chat_router
from observability import init_langfuse, shutdown_langfuse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_langfuse()
    yield
    shutdown_langfuse()


app = FastAPI(title="Rappi AI API", lifespan=lifespan)

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(chat_router)


@app.get("/api/data")
def get_data(
    start: str | None = None,
    end: str | None = None,
    resolution: int = Query(default=60, description="Downsample: take 1 point every N seconds"),
):
    """Time series data, optionally filtered and downsampled."""
    where = []
    params = []
    if start:
        where.append("timestamp >= ?")
        params.append(start)
    if end:
        where.append("timestamp <= ?")
        params.append(end)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    # Downsample by taking every Nth row (resolution in seconds, data is every 10s)
    step = max(1, resolution // 10)

    sql = f"""
        WITH numbered AS (
            SELECT *, ROW_NUMBER() OVER (ORDER BY timestamp) as rn
            FROM availability
            {where_clause}
        )
        SELECT timestamp, store_count, rolling_avg_30m, daily_pct, z_score, is_anomaly
        FROM numbered
        WHERE rn % {step} = 0
        ORDER BY timestamp
    """
    rows = query(sql, params)
    # Convert timestamps to ISO strings
    for r in rows:
        r["timestamp"] = r["timestamp"].isoformat()
    return rows


@app.get("/api/stats")
def get_stats():
    """Overall KPI stats."""
    result = query("""
        SELECT
            MAX(store_count) as peak,
            ROUND(AVG(store_count)) as avg,
            MIN(store_count) as min,
            COUNT(*) FILTER (WHERE is_anomaly) as anomaly_count,
            COUNT(*) as total_points,
            MIN(timestamp) as date_start,
            MAX(timestamp) as date_end,
            COUNT(DISTINCT date) as total_days
        FROM availability
    """)[0]
    result["date_start"] = result["date_start"].isoformat()
    result["date_end"] = result["date_end"].isoformat()

    # Uptime: percentage of points above 50% of daily peak (not in a "down" state)
    uptime = query("""
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE daily_pct > 50)
            / COUNT(*), 1
        ) as uptime_pct
        FROM availability
        WHERE hour BETWEEN 8 AND 22
    """)[0]
    result["uptime_pct"] = uptime["uptime_pct"]
    return result


@app.get("/api/heatmap")
def get_heatmap():
    """Average store_count by hour and day_of_week."""
    return query("""
        SELECT
            day_of_week,
            day_num,
            hour,
            ROUND(AVG(store_count)) as avg_count,
            ROUND(AVG(daily_pct), 1) as avg_daily_pct
        FROM availability
        GROUP BY day_of_week, day_num, hour
        ORDER BY day_num, hour
    """)


@app.get("/api/daily-comparison")
def get_daily_comparison(days: str | None = None):
    """Daily curves using daily_pct (0-100%) for comparison.
    days: comma-separated dates like '2026-02-01,2026-02-03'
    """
    if days:
        day_list = [d.strip() for d in days.split(",")]
        placeholders = ",".join("?" for _ in day_list)
        where = f"WHERE CAST(date AS VARCHAR) IN ({placeholders})"
    else:
        day_list = []
        where = ""

    rows = query(f"""
        SELECT
            CAST(date AS VARCHAR) as date,
            day_of_week,
            hour,
            minute,
            ROUND(AVG(store_count)) as avg_count,
            ROUND(AVG(daily_pct), 1) as avg_daily_pct
        FROM availability
        {where}
        GROUP BY date, day_of_week, hour, minute
        ORDER BY date, hour, minute
    """, day_list)
    return rows


@app.get("/api/anomalies")
def get_anomalies():
    """All flagged anomalies."""
    rows = query("""
        SELECT timestamp, store_count, z_score, daily_pct, hour, date, day_of_week
        FROM availability
        WHERE is_anomaly = true
        ORDER BY ABS(z_score) DESC
        LIMIT 500
    """)
    for r in rows:
        r["timestamp"] = r["timestamp"].isoformat()
        r["date"] = r["date"].isoformat()
    return rows


@app.get("/api/anomaly-density")
def get_anomaly_density():
    """Anomaly count and rate by hour of day."""
    return query("""
        SELECT
            hour,
            COUNT(*) FILTER (WHERE is_anomaly) as anomaly_count,
            COUNT(*) as total_count,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_anomaly) / COUNT(*), 2) as anomaly_pct
        FROM availability
        GROUP BY hour
        ORDER BY hour
    """)


@app.get("/api/hourly-stats")
def get_hourly_stats():
    """Store count distribution per hour (avg, min, max, percentiles)."""
    return query("""
        SELECT
            hour,
            ROUND(AVG(store_count)) as avg_count,
            MIN(store_count) as min_count,
            MAX(store_count) as max_count,
            ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY store_count)) as p25,
            ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY store_count)) as p75,
            ROUND(STDDEV(store_count)) as std_dev
        FROM availability
        GROUP BY hour
        ORDER BY hour
    """)
