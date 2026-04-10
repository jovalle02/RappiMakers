"""Tool definitions and execution for the chat assistant."""

import json
from database import query

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
            "'how does Monday compare to Saturday' or 'is morning better than evening'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_a": {
                    "type": "string",
                    "description": "SQL WHERE clause for period A, e.g. \"day_of_week = 'Monday'\" or \"hour BETWEEN 8 AND 12\"",
                },
                "period_b": {
                    "type": "string",
                    "description": "SQL WHERE clause for period B, e.g. \"day_of_week = 'Saturday'\" or \"hour BETWEEN 18 AND 22\"",
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
    if input.get("date"):
        conditions.append(f"CAST(date AS VARCHAR) = '{input['date']}'")
    if input.get("hour") is not None:
        conditions.append(f"hour = {int(input['hour'])}")

    where = " AND ".join(conditions)

    try:
        # Get anomaly points
        anomalies = query(f"""
            SELECT timestamp, store_count, z_score, daily_pct, hour, minute,
                   day_of_week, CAST(date AS VARCHAR) as date
            FROM availability
            WHERE {where}
            ORDER BY ABS(z_score) DESC
            LIMIT 20
        """)
        for r in anomalies:
            if hasattr(r.get("timestamp"), "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()

        # Get context: overall stats for the same time window (without anomaly filter)
        context_where = " AND ".join(c for c in conditions if "is_anomaly" not in c)
        if not context_where:
            context_where = "1=1"

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
        """)

        return json.dumps({
            "anomalies": anomalies,
            "context": context[0] if context else {},
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def _exec_compare_periods(input: dict) -> str:
    def stats_for(where: str) -> dict:
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
        """)
        return rows[0] if rows else {}

    try:
        a = stats_for(input["period_a"])
        b = stats_for(input["period_b"])
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
