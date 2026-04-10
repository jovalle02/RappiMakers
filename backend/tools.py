"""Tool definitions and execution for the chat assistant."""

import json
import re
from database import query

_DANGEROUS_SQL = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|EXEC|GRANT)\b|;",
    re.IGNORECASE,
)

# --- Tool schemas (sent to Claude so it knows what it can call) ---

TOOL_DEFINITIONS = [
    {
        "name": "query_database",
        "description": (
            "Execute a read-only SQL query against the DuckDB 'availability' table. "
            "Use this to answer questions about store availability data. "
            "The table has columns: timestamp (TIMESTAMP), store_count (INT), "
            "date (DATE), hour (INT), minute (INT), day_of_week (VARCHAR), "
            "day_num (INT), pct_change (FLOAT), rolling_avg_30m (FLOAT), "
            "daily_pct (FLOAT), z_score (FLOAT), is_anomaly (BOOL). "
            "Date range: Feb 1-11, 2026. Use DuckDB SQL syntax. "
            "Always LIMIT results to avoid huge outputs (max 50 rows)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to execute. Must be a SELECT statement. Always include a LIMIT clause.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why you're running this query.",
                },
            },
            "required": ["sql", "reasoning"],
        },
    },
    {
        "name": "analyze_anomaly",
        "description": (
            "Deep-dive into anomalies at a specific hour or date. "
            "Returns the anomaly points with surrounding context (before/after data) "
            "to help understand what happened. Use this when the user asks about "
            "specific anomalies, drops, or unusual behavior."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to analyze (YYYY-MM-DD format). Optional if only hour is given.",
                },
                "hour": {
                    "type": "integer",
                    "description": "Hour of day to focus on (0-23). Optional if only date is given.",
                },
            },
        },
    },
    {
        "name": "compare_periods",
        "description": (
            "Compare two time periods statistically. Returns avg, min, max, "
            "std_dev, anomaly count for each period. Useful for questions like "
            "'how does Monday compare to Saturday' or 'is morning better than evening'. "
            "Each period is defined by structured filters (day_of_week, hour_start, hour_end, date)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_a": {
                    "type": "object",
                    "description": "Filters for period A.",
                    "properties": {
                        "day_of_week": {"type": "string", "description": "Day name, e.g. 'Monday'"},
                        "hour_start": {"type": "integer", "description": "Start hour inclusive (0-23)"},
                        "hour_end": {"type": "integer", "description": "End hour inclusive (0-23)"},
                        "date": {"type": "string", "description": "Specific date YYYY-MM-DD"},
                    },
                },
                "period_b": {
                    "type": "object",
                    "description": "Filters for period B.",
                    "properties": {
                        "day_of_week": {"type": "string", "description": "Day name, e.g. 'Saturday'"},
                        "hour_start": {"type": "integer", "description": "Start hour inclusive (0-23)"},
                        "hour_end": {"type": "integer", "description": "End hour inclusive (0-23)"},
                        "date": {"type": "string", "description": "Specific date YYYY-MM-DD"},
                    },
                },
                "label_a": {
                    "type": "string",
                    "description": "Human-readable label for period A, e.g. 'Monday' or 'Morning'",
                },
                "label_b": {
                    "type": "string",
                    "description": "Human-readable label for period B, e.g. 'Saturday' or 'Evening'",
                },
            },
            "required": ["period_a", "period_b", "label_a", "label_b"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for general domain knowledge to help explain data patterns. "
            "Use this to research topics like: why food delivery platforms show certain "
            "availability patterns, common causes of store visibility drops, marketplace "
            "infrastructure patterns, etc. Do NOT search for specific Rappi incidents — "
            "the data is synthetic. Instead search for general knowledge that helps "
            "form hypotheses about the patterns observed in the data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Focus on general domain knowledge, not specific incidents.",
                },
            },
            "required": ["query"],
        },
    },
]


# --- Tool execution (actually runs the tool and returns results) ---

def execute_tool(name: str, input: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "query_database":
        return _exec_query_database(input)
    elif name == "analyze_anomaly":
        return _exec_analyze_anomaly(input)
    elif name == "compare_periods":
        return _exec_compare_periods(input)
    elif name == "web_search":
        return _exec_web_search(input)
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


def _exec_query_database(input: dict) -> str:
    sql = input.get("sql", "").strip()

    # Safety: only allow SELECT statements
    if not sql.upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT statements are allowed."})

    # Block dangerous keywords (defense-in-depth)
    if _DANGEROUS_SQL.search(sql):
        return json.dumps({"error": "Query contains disallowed keywords."})

    try:
        rows = query(sql)
        # Serialize dates/timestamps
        for r in rows:
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat()
        return json.dumps({"row_count": len(rows), "rows": rows[:50]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _exec_analyze_anomaly(input: dict) -> str:
    conditions = ["is_anomaly = true"]
    params = []
    context_conditions = []
    context_params = []

    if input.get("date"):
        conditions.append("CAST(date AS VARCHAR) = ?")
        params.append(input["date"])
        context_conditions.append("CAST(date AS VARCHAR) = ?")
        context_params.append(input["date"])
    if input.get("hour") is not None:
        conditions.append("hour = ?")
        params.append(int(input["hour"]))
        context_conditions.append("hour = ?")
        context_params.append(int(input["hour"]))

    where = " AND ".join(conditions)
    context_where = " AND ".join(context_conditions) if context_conditions else "1=1"

    try:
        # Get anomaly points
        anomalies = query(f"""
            SELECT timestamp, store_count, z_score, daily_pct, hour, minute,
                   day_of_week, CAST(date AS VARCHAR) as date
            FROM availability
            WHERE {where}
            ORDER BY ABS(z_score) DESC
            LIMIT 20
        """, params)
        for r in anomalies:
            if hasattr(r.get("timestamp"), "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()

        # Get context: overall stats for the same time window (without anomaly filter)
        context = query(f"""
            SELECT
                COUNT(*) as total_points,
                COUNT(*) FILTER (WHERE is_anomaly) as anomaly_count,
                ROUND(AVG(store_count)) as avg_count,
                MIN(store_count) as min_count,
                MAX(store_count) as max_count,
                ROUND(STDDEV(store_count)) as std_dev
            FROM availability
            WHERE {context_where}
        """, context_params)

        return json.dumps({
            "anomalies": anomalies,
            "context": context[0] if context else {},
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def _build_period_filter(period: dict) -> tuple[str, list]:
    """Build a safe WHERE clause + params from a structured period filter."""
    conditions = []
    params = []
    if period.get("day_of_week"):
        conditions.append("day_of_week = ?")
        params.append(period["day_of_week"])
    if period.get("hour_start") is not None and period.get("hour_end") is not None:
        conditions.append("hour BETWEEN ? AND ?")
        params.extend([int(period["hour_start"]), int(period["hour_end"])])
    elif period.get("hour_start") is not None:
        conditions.append("hour >= ?")
        params.append(int(period["hour_start"]))
    elif period.get("hour_end") is not None:
        conditions.append("hour <= ?")
        params.append(int(period["hour_end"]))
    if period.get("date"):
        conditions.append("CAST(date AS VARCHAR) = ?")
        params.append(period["date"])
    return " AND ".join(conditions) if conditions else "1=1", params


def _exec_compare_periods(input: dict) -> str:
    def stats_for(where: str, params: list) -> dict:
        rows = query(f"""
            SELECT
                COUNT(*) as total_points,
                ROUND(AVG(store_count)) as avg_count,
                MIN(store_count) as min_count,
                MAX(store_count) as max_count,
                ROUND(STDDEV(store_count)) as std_dev,
                COUNT(*) FILTER (WHERE is_anomaly) as anomaly_count,
                ROUND(AVG(daily_pct), 1) as avg_daily_pct
            FROM availability
            WHERE {where}
        """, params)
        return rows[0] if rows else {}

    try:
        where_a, params_a = _build_period_filter(input.get("period_a", {}))
        where_b, params_b = _build_period_filter(input.get("period_b", {}))
        a = stats_for(where_a, params_a)
        b = stats_for(where_b, params_b)
        return json.dumps({
            input.get("label_a", "Period A"): a,
            input.get("label_b", "Period B"): b,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def _exec_web_search(input: dict) -> str:
    search_query = input.get("query", "")
    try:
        from ddgs import DDGS
        results = DDGS().text(search_query, max_results=5)
        return json.dumps({
            "query": search_query,
            "results": [
                {"title": r["title"], "snippet": r["body"], "url": r["href"]}
                for r in results
            ],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "query": search_query})
