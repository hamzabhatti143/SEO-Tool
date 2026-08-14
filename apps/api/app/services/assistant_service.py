"""AI SEO Assistant service — streams an Agents SDK run over SSE.

Runs the assistant agent with the project scoped via run context, and
translates the SDK's streamed events into SSE frames: `token` (assistant
text deltas), `tool` (a data-lookup tool was called — for UI transparency),
`done`, and `error`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from agents import Runner

from app.agents.assistant_agent import AssistantContext, assistant_agent
from app.schemas.assistant import ChatRequest


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Human-friendly labels for the tool-usage indicator in the UI.
_TOOL_LABELS = {
    "get_project_overview": "Reading project overview",
    "get_latest_audit": "Checking the latest audit",
    "get_tracked_rankings": "Looking at rank history",
    "get_keywords": "Reviewing keyword research",
    "get_content": "Reviewing content",
}


async def stream_chat(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Yield SSE frames for one assistant turn."""
    try:
        # Pass the full conversation so the agent has context.
        input_items = [
            {"role": m.role, "content": m.content} for m in request.messages
        ]
        context = AssistantContext(project_id=request.project_id)
        result = Runner.run_streamed(
            assistant_agent, input=input_items, context=context
        )

        async for event in result.stream_events():
            if event.type == "raw_response_event":
                # Token deltas arrive as ResponseTextDeltaEvent — duck-type it
                # so we don't couple to a specific openai import path.
                data = event.data
                delta = getattr(data, "delta", None)
                if delta and type(data).__name__ == "ResponseTextDeltaEvent":
                    yield _sse("token", {"text": delta})
            elif event.type == "run_item_stream_event":
                if getattr(event, "name", "") == "tool_called":
                    raw = getattr(event.item, "raw_item", None)
                    name = getattr(raw, "name", None) or "tool"
                    yield _sse(
                        "tool",
                        {"name": name, "label": _TOOL_LABELS.get(name, name)},
                    )

        yield _sse("done", {})
    except Exception as exc:  # noqa: BLE001 - surface errors over the stream
        yield _sse("error", {"detail": str(exc)})
