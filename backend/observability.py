"""Langfuse observability helpers for tracing chat requests."""

import os
import time
import logging
from langfuse import Langfuse

logger = logging.getLogger("rappi")

_client: Langfuse | None = None

# Claude Sonnet 4.6 pricing (USD per token)
MODEL_PRICING = {
    "claude-sonnet-4-6": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
        "cache_write": 3.75 / 1_000_000,   # 25% more than input
        "cache_read": 0.3 / 1_000_000,     # 90% less than input
    },
}


def init_langfuse():
    """Initialize the Langfuse client. Safe to call if env vars are missing (disables tracing)."""
    global _client
    if os.environ.get("LANGFUSE_PUBLIC_KEY"):
        _client = Langfuse()
        logger.info("Langfuse tracing enabled")
    else:
        logger.info("Langfuse tracing disabled (no LANGFUSE_PUBLIC_KEY set)")


def shutdown_langfuse():
    """Flush and shutdown the Langfuse client."""
    if _client:
        _client.flush()
        _client.shutdown()


def create_chat_trace(conversation_id: str, user_message: str):
    """Create a new trace for a chat request. Returns trace or None."""
    if not _client:
        return None
    return _client.trace(
        id=conversation_id,
        name="chat_request",
        input={"message": user_message[:500]},
    )


def log_llm_generation(trace, *, name: str, model: str, usage: dict, latency_ms: float, iteration: int):
    """Log an LLM generation span to a trace."""
    if not trace:
        return
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)

    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0})
    # Non-cached input tokens = total input - cache_read (cache_write tokens are also charged)
    regular_input = max(0, input_tokens - cache_read)
    input_cost = regular_input * pricing["input"]
    output_cost = output_tokens * pricing["output"]
    cache_write_cost = cache_write * pricing.get("cache_write", 0)
    cache_read_cost = cache_read * pricing.get("cache_read", 0)
    total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

    trace.generation(
        name=name,
        model=model,
        usage={
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
            "input_cost": input_cost + cache_write_cost + cache_read_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
        },
        metadata={
            "iteration": iteration,
            "latency_ms": round(latency_ms),
            "cache_write_tokens": cache_write,
            "cache_read_tokens": cache_read,
        },
    )


def log_tool_call(trace, *, tool_name: str, tool_input: dict, tool_output: str, latency_ms: float):
    """Log a tool execution span to a trace."""
    if not trace:
        return
    trace.span(
        name=f"tool:{tool_name}",
        input=tool_input,
        output=tool_output[:2000],
        metadata={"latency_ms": round(latency_ms)},
    )


def finalize_trace(trace, *, total_tokens: dict, total_latency_ms: float, iterations: int, status: str = "ok"):
    """Finalize a trace with summary metadata."""
    if not trace:
        return
    trace.update(
        output={"status": status, "iterations": iterations},
        metadata={
            "total_input_tokens": total_tokens.get("input_tokens", 0),
            "total_output_tokens": total_tokens.get("output_tokens", 0),
            "total_tokens": total_tokens.get("input_tokens", 0) + total_tokens.get("output_tokens", 0),
            "total_latency_ms": round(total_latency_ms),
        },
    )
