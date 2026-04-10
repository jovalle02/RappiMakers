"""Chat endpoint: streams Claude responses via SSE with tool calling and thinking."""

import json
import os
import time
import traceback
import uuid

from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from anthropic import AsyncAnthropic

from prompts import SYSTEM_PROMPT
from tools import TOOL_DEFINITIONS, execute_tool
from observability import create_chat_trace, log_llm_generation, log_tool_call, finalize_trace
from guards import validate_user_input

load_dotenv()

router = APIRouter()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


@router.post("/api/chat")
async def chat(request: Request):
    """Stream a Claude response as Server-Sent Events, with tool call + thinking support."""
    body = await request.json()
    messages = body.get("messages", [])

    # --- Guardrails ---
    ok, error = validate_user_input(messages)
    if not ok:
        if error == "off_topic":
            async def redirect():
                yield f"data: {json.dumps({'type': 'text', 'content': 'I can only help with Rappi store availability data analysis. Please ask a question about the dashboard data.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return StreamingResponse(redirect(), media_type="text/event-stream")
        return JSONResponse(status_code=400, content={"error": error})

    async def generate():
        conversation_id = uuid.uuid4().hex[:12]
        last_user_msg = messages[-1].get("content", "") if messages else ""
        trace = create_chat_trace(conversation_id, last_user_msg)
        request_start = time.monotonic()
        total_input_tokens = 0
        total_output_tokens = 0
        iteration = 0

        try:
            while iteration < 5:
                iteration += 1
                tool_calls = []
                current_block_type = None
                current_tool = None
                iter_start = time.monotonic()

                async with client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=16000,
                    system=[{
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                    thinking={
                        "type": "enabled",
                        "budget_tokens": 4000,
                    },
                ) as stream:
                    async for event in stream:
                        if event.type == "content_block_start":
                            current_block_type = event.content_block.type
                            if current_block_type == "thinking":
                                yield f"data: {json.dumps({'type': 'thinking_start'})}\n\n"
                            elif current_block_type == "tool_use":
                                current_tool = {
                                    "id": event.content_block.id,
                                    "name": event.content_block.name,
                                    "input_json": "",
                                }

                        elif event.type == "content_block_delta":
                            if event.delta.type == "thinking_delta":
                                yield f"data: {json.dumps({'type': 'thinking', 'content': event.delta.thinking})}\n\n"
                            elif event.delta.type == "text_delta":
                                yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"
                            elif event.delta.type == "input_json_delta" and current_tool:
                                current_tool["input_json"] += event.delta.partial_json

                        elif event.type == "content_block_stop":
                            if current_block_type == "thinking":
                                yield f"data: {json.dumps({'type': 'thinking_end'})}\n\n"
                            elif current_block_type == "tool_use" and current_tool:
                                try:
                                    tool_input = json.loads(current_tool["input_json"])
                                except json.JSONDecodeError:
                                    tool_input = {}

                                yield f"data: {json.dumps({'type': 'tool_start', 'name': current_tool['name'], 'input': tool_input})}\n\n"
                                tool_start = time.monotonic()
                                result = execute_tool(current_tool["name"], tool_input)
                                tool_latency = (time.monotonic() - tool_start) * 1000
                                log_tool_call(
                                    trace,
                                    tool_name=current_tool["name"],
                                    tool_input=tool_input,
                                    tool_output=result,
                                    latency_ms=tool_latency,
                                )
                                yield f"data: {json.dumps({'type': 'tool_result', 'name': current_tool['name'], 'result': json.loads(result)})}\n\n"

                                tool_calls.append({
                                    "id": current_tool["id"],
                                    "name": current_tool["name"],
                                    "input": tool_input,
                                    "result": result,
                                })
                                current_tool = None
                            current_block_type = None

                    # Get the final message (has thinking blocks with signatures intact)
                    final_message = await stream.get_final_message()

                # Track token usage
                usage = final_message.usage
                total_input_tokens += usage.input_tokens
                total_output_tokens += usage.output_tokens
                iter_latency = (time.monotonic() - iter_start) * 1000

                log_llm_generation(
                    trace,
                    name=f"claude_iter_{iteration}",
                    model="claude-sonnet-4-6",
                    usage={
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
                        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
                    },
                    latency_ms=iter_latency,
                    iteration=iteration,
                )

                # If Claude called tools, rebuild from the final message (preserves signatures)
                if tool_calls:
                    # Use the actual content blocks from the final message
                    # This preserves thinking signatures required by the API
                    assistant_content = []
                    for block in final_message.content:
                        if block.type == "thinking":
                            assistant_content.append({
                                "type": "thinking",
                                "thinking": block.thinking,
                                "signature": block.signature,
                            })
                        elif block.type == "text":
                            assistant_content.append({
                                "type": "text",
                                "text": block.text,
                            })
                        elif block.type == "tool_use":
                            assistant_content.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })

                    tool_results = []
                    for tc in tool_calls:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": tc["result"],
                        })

                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({"role": "user", "content": tool_results})
                    continue

                break

        except Exception as e:
            traceback.print_exc()
            finalize_trace(
                trace,
                total_tokens={"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
                total_latency_ms=(time.monotonic() - request_start) * 1000,
                iterations=iteration,
                status=f"error: {e}",
            )
            yield f"data: {json.dumps({'type': 'error', 'content': 'An internal error occurred. Please try again.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        finalize_trace(
            trace,
            total_tokens={"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            total_latency_ms=(time.monotonic() - request_start) * 1000,
            iterations=iteration,
            status="ok",
        )
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
