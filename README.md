# Rappi AI - Store Availability Dashboard

Real-time analytics dashboard and AI-powered chatbot for monitoring Rappi store availability patterns, built with Next.js, FastAPI, DuckDB, and Claude.

**Stack:** Next.js 16 | FastAPI | DuckDB | Claude Sonnet 4.6 | Langfuse | Docker

---

## Overview

Rappi AI analyzes 67,141 observations of Rappi store visibility data (Feb 1-11, 2026, Colombia) and provides:

- **Interactive Dashboard** -- KPI cards, time series, heatmaps, anomaly density charts, hourly distributions, and day-over-day comparisons
- **AI Chatbot** -- Natural language interface powered by Claude with extended thinking, tool calling, and real-time streaming
- **Observability** -- Self-hosted Langfuse for tracing every AI interaction: token usage, costs, tool calls, and latency

---

## Architecture

```mermaid
graph TB
    subgraph Docker Compose
        subgraph Frontend["Frontend :3000"]
            Next["Next.js 16 + React 19"]
            Charts["Recharts + Tailwind"]
        end

        subgraph Backend["Backend :8000"]
            API["FastAPI"]
            Guards["Guardrails"]
            Tools["Tool Engine"]
            DB["DuckDB"]
        end

        subgraph Observability["Langfuse :3001"]
            LF["Langfuse Server"]
            PG["PostgreSQL 16"]
        end
    end

    User((User)) --> Next
    Next -->|REST API| API
    Next -->|SSE Stream| API
    API --> Guards
    Guards --> API
    API -->|SQL Queries| DB
    API -->|Tool Calls| Tools
    Tools -->|Parameterized SQL| DB
    Tools -->|Web Search| DDG["DuckDuckGo"]
    API <-->|Streaming| Claude["Claude Sonnet 4.6"]
    API -->|Traces| LF
    LF --> PG
    Claude -.->|Prompt Cache| Claude

    style Frontend fill:#0070f3,color:#fff
    style Backend fill:#009688,color:#fff
    style Observability fill:#7c3aed,color:#fff
    style Claude fill:#d97706,color:#fff
```

---

## AI Chatbot Flow

Every chat message goes through this pipeline, streamed back to the user in real time via Server-Sent Events:

```mermaid
graph LR
    A["User sends message"] --> B["Guardrails check"]
    B --> C["Claude receives message\n(system prompt cached)"]
    C --> D["Extended thinking"]
    D --> E{"Needs data?"}
    E -- Yes --> F["Tool calls\n(SQL, anomaly, compare, search)"]
    F --> G["Execute against DuckDB"]
    G --> C
    E -- No --> H["Stream final answer"]
    H --> I["Log trace to Langfuse\n(tokens, cost, latency)"]

    style A fill:#FC4C02,color:#fff
    style C fill:#d97706,color:#fff
    style D fill:#d97706,color:#fff
    style F fill:#009688,color:#fff
    style G fill:#009688,color:#fff
    style H fill:#0070f3,color:#fff
    style I fill:#7c3aed,color:#fff
```

### Tool Calling Loop

Claude has access to 4 tools and can chain up to 5 iterations per request:

| Tool | Purpose | Security |
|------|---------|----------|
| `query_database` | Execute read-only SQL against DuckDB | SELECT-only + keyword blocklist + read-only DB |
| `analyze_anomaly` | Deep-dive into anomalies by date/hour | Parameterized queries |
| `compare_periods` | Compare two time periods statistically | Structured filter schema (no raw SQL) |
| `web_search` | Search for domain knowledge via DuckDuckGo | Input sanitized |

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | Next.js 16, React 19, Tailwind, Recharts | Modern React with server components, fast charting |
| **Backend** | FastAPI, Python 3.12 | Async streaming, lightweight, great for APIs |
| **Database** | DuckDB | In-process analytics DB, zero config, fast on columnar data |
| **AI** | Anthropic SDK (direct) | Full control over streaming, tool calling, prompt caching, and extended thinking |
| **Model** | Claude Sonnet 4.6 | Extended thinking + tool use + streaming |
| **Observability** | Langfuse (self-hosted) | Full tracing, token/cost tracking, no external dependencies |
| **Containers** | Docker Compose | One-command setup for all 4 services |

---

## Key Design Decisions

**Direct Anthropic SDK** -- Using the Anthropic Python SDK directly gives full control over SSE streaming, extended thinking blocks, tool signature preservation, and prompt caching. The agentic tool-calling loop is a simple `while` loop with explicit message management, making it easy to debug and extend.

**Prompt Caching** -- The system prompt is cached across tool-calling iterations using Anthropic's ephemeral cache. When Claude calls tools and needs a second API call, the cached system prompt is reused at 90% discount instead of being reprocessed. This reduces both cost and latency on multi-tool requests.

**DuckDB** -- An in-process columnar analytics database that runs embedded inside the backend with zero configuration. It supports full SQL including window functions, percentiles, and filtered aggregations out of the box, which is ideal for this read-only analytical workload. No separate database server needed.

**Self-Hosted Langfuse** -- Observability runs locally inside the Docker Compose stack with auto-seeded credentials. No external accounts needed. Every request is traced with token counts, costs, tool call latency, and cache hit rates.

**Custom Guardrails** -- Input validation uses regex-based prompt injection detection and topic restriction. The guards fail-open to avoid blocking legitimate users on edge cases.

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/jovalle02/RappiMakers.git
cd RappiMakers

# 2. Create your environment file
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Start all services
docker compose up --build
```

### Access

| Service | URL | Description |
|---------|-----|-------------|
| **Dashboard + Chat** | [http://localhost:3000](http://localhost:3000) | Main application |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | FastAPI endpoints |
| **Langfuse** | [http://localhost:3001](http://localhost:3001) | Observability dashboard |

---

## Langfuse Dashboard

Langfuse is pre-configured with auto-seeded credentials. No registration needed.

**Login:** `admin@rappimakers.local` / `rappimakers`

Once logged in, you can explore:

- **Traces** -- Every chat request with full breakdown (thinking, tool calls, response)
- **Generations** -- Token usage per Claude API call, with input/output/cache breakdown
- **Cost** -- Per-request and aggregate cost tracking (Claude Sonnet 4.6 pricing)
- **Latency** -- End-to-end and per-tool response times

---

## Project Structure

```
RappiMakers/
|-- backend/
|   |-- main.py              # FastAPI app + 7 REST endpoints
|   |-- chat.py              # SSE streaming chat with Claude (tool loop, caching)
|   |-- tools.py             # 4 tool definitions + safe execution
|   |-- prompts.py           # System prompt (data analyst persona + source attribution)
|   |-- database.py          # DuckDB initialization + parameterized query helper
|   |-- guards.py            # Input guardrails (injection, topic, length)
|   |-- observability.py     # Langfuse tracing helpers (traces, generations, spans)
|   |-- requirements.txt     # Python dependencies
|   |-- Dockerfile
|-- frontend/
|   |-- src/
|   |   |-- app/page.tsx     # Main page layout (dashboard + chat)
|   |   |-- components/
|   |   |   |-- chat/        # AI chatbot panel with SSE streaming
|   |   |   |-- dashboard/   # 6 chart components (timeline, heatmap, etc.)
|   |   |   |-- ui/          # Shared UI components (shadcn/ui)
|   |   |-- lib/api.ts       # API client + TypeScript interfaces
|   |-- package.json
|   |-- Dockerfile
|-- processing_data/
|   |-- data/
|   |   |-- availability.csv # Processed dataset (67,141 rows)
|   |-- Archivo/             # Raw source CSV files
|-- transform_data.py        # Data processing pipeline
|-- docker-compose.yml       # 4 services: frontend, backend, langfuse, postgres
|-- .env.example             # Environment variable template
|-- README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats` | Overall KPI statistics (peak, avg, min, anomaly count, uptime) |
| `GET` | `/api/data` | Time series data with optional filtering and downsampling |
| `GET` | `/api/heatmap` | Average store count by hour and day of week |
| `GET` | `/api/daily-comparison` | Daily curves using daily percentage for comparison |
| `GET` | `/api/anomalies` | All flagged anomaly points (z-score > 2) |
| `GET` | `/api/anomaly-density` | Anomaly count and rate by hour of day |
| `GET` | `/api/hourly-stats` | Store count distribution per hour (avg, min, max, percentiles) |
| `POST` | `/api/chat` | AI chatbot endpoint (SSE streaming response) |

---

## Dataset

67,141 observations of visible Rappi store counts, recorded every 10 seconds from February 1-11, 2026 in Colombia.

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | TIMESTAMP | Precise observation timestamp |
| `store_count` | INT | Number of visible stores (range: 37 to 39,000) |
| `rolling_avg_30m` | FLOAT | 30-minute rolling average |
| `daily_pct` | FLOAT | Store count as percentage of that day's peak (0-100%) |
| `z_score` | FLOAT | Statistical deviation from hourly mean |
| `is_anomaly` | BOOL | Flagged when the absolute z_score is greater than 2 |
| `hour`, `minute`, `day_of_week`, `day_num` | Various | Time decomposition fields |
