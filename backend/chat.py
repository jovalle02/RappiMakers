"""Chat endpoint — streams Claude responses via SSE with tool calling + thinking."""

import json
import os
import traceback

from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from anthropic import AsyncAnthropic

from prompts import SYSTEM_PROMPT
from tools import TOOL_DEFINITIONS, execute_tool

load_dotenv()

router = APIRouter()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


@router.post("/api/chat")
async def chat(request: Request):
    """Stream a Claude response as Server-Sent Events, with tool call + thinking support."""
    body = await request.json()
    messages = body.get("messages", [])

    async def generate():
        try:
            iteration = 0
            while iteration < 5:
                iteration += 1
                tool_calls = []
                current_block_type = None
                current_tool = None

                async with client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=16000,
                    system=SYSTEM_PROMPT,
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
                                result = execute_tool(current_tool["name"], tool_input)
                                yield f"data: {json.dumps({'type': 'tool_result', 'name': current_tool['name'], 'result': json.loads(result)})}\n\n"

                                tool_calls.append({
                                    "id": current_tool["id"],
                                    "name": current_tool["name"],
                                    "input": tool_input,
                                    "result": result,
                                })
                                current_tool = None
                            current_block_type = None

                    # Get the final message — this has thinking blocks with signatures intact
                    final_message = await stream.get_final_message()

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
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
