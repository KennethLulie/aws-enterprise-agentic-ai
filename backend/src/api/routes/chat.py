"""
Chat endpoints providing POST and SSE streaming.

Phase 0 defaults to a lightweight mock streaming path. When Bedrock credentials
are configured, the endpoints stream real LangGraph responses (LLM + tools).
This keeps the API surface stable while enabling incremental bring-up:
verify UI first with mocks, then switch to real agent behavior without
changing the routes.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncIterator, Dict, Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from src.agent.graph import graph
from src.agent.state import AgentState, create_initial_state
from src.api.routes.auth import SessionPayload, require_session
from src.config import Settings

router = APIRouter(prefix="/api", tags=["Chat"])

# In-memory queues keyed by conversation_id. This is sufficient for Phase 0 demos.
_STREAM_QUEUES: Dict[str, asyncio.Queue[dict[str, Any]]] = {}
_KEEPALIVE_SECONDS = 15


def _get_queue(conversation_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Return (or create) the queue for a conversation."""

    if conversation_id not in _STREAM_QUEUES:
        _STREAM_QUEUES[conversation_id] = asyncio.Queue()
    return _STREAM_QUEUES[conversation_id]


class SendMessageRequest(BaseModel):
    """Incoming chat message payload."""

    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = Field(
        default=None,
        description="Conversation identifier. A new one is issued if omitted.",
    )


class SendMessageResponse(BaseModel):
    """Response indicating the accepted conversation id."""

    conversation_id: str = Field(..., alias="conversationId")
    message: str | None = Field(
        default=None, description="Optional status message for the client."
    )

    class Config:
        """Pydantic configuration for alias handling."""

        populate_by_name = True


async def _mock_stream_response(conversation_id: str, user_message: str) -> None:
    """Simulate a short streaming response for Phase 0."""

    queue = _get_queue(conversation_id)
    # Simulate incremental chunks
    queue.put_nowait(
        {
            "type": "message",
            "content": "Thanks for trying the demo. ",
            "conversationId": conversation_id,
        }
    )
    await asyncio.sleep(0.3)
    queue.put_nowait(
        {
            "type": "message",
            "content": f"I heard: “{user_message}”. ",
            "conversationId": conversation_id,
        }
    )
    await asyncio.sleep(0.3)
    queue.put_nowait(
        {
            "type": "message",
            "content": "Tooling is mocked in Phase 0.",
            "conversationId": conversation_id,
        }
    )
    queue.put_nowait({"type": "complete", "conversationId": conversation_id})


def _should_use_real_agent(settings: Settings) -> bool:
    """Use real LangGraph only when AWS credentials are configured."""

    return bool(settings.aws_access_key_id and settings.aws_secret_access_key)


async def _stream_langgraph_events(
    conversation_id: str, user_message: str, settings: Settings
) -> None:
    """
    Run the LangGraph agent and push streaming events into the SSE queue.

    This keeps the API surface the same while allowing real tool execution when
    Bedrock credentials are present.
    """

    queue = _get_queue(conversation_id)

    state: AgentState = create_initial_state(conversation_id=conversation_id)
    state["messages"] = [HumanMessage(content=user_message)]

    try:
        async for event in graph.astream(
            state,
            config={"configurable": {"thread_id": conversation_id}},
        ):
            messages: Sequence[BaseMessage] = event.get("messages", [])  # type: ignore[arg-type]
            last_error = event.get("last_error")

            for message in messages:
                if isinstance(message, AIMessage):
                    queue.put_nowait(
                        {
                            "type": "message",
                            "content": message.content,
                            "conversationId": conversation_id,
                        }
                    )
                elif isinstance(message, ToolMessage):
                    queue.put_nowait(
                        {
                            "type": "tool_result",
                            "content": message.content,
                            "tool": message.name,
                            "conversationId": conversation_id,
                        }
                    )

            if last_error:
                queue.put_nowait(
                    {
                        "type": "error",
                        "content": last_error,
                        "conversationId": conversation_id,
                    }
                )
                return

        queue.put_nowait({"type": "complete", "conversationId": conversation_id})

    except Exception as exc:  # pragma: no cover - defensive guard
        queue.put_nowait(
            {
                "type": "error",
                "content": f"Agent error: {exc!s}",
                "conversationId": conversation_id,
            }
        )


async def _event_stream(
    conversation_id: str,
) -> AsyncIterator[str]:
    """Yield server-sent events for the given conversation."""

    queue = _get_queue(conversation_id)
    # Send an initial open event so the client captures the ID
    yield f"data: {json.dumps({'type': 'open', 'conversationId': conversation_id})}\n\n"

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                # Keep-alive comment to prevent intermediaries from closing the stream
                yield ": keep-alive\n\n"
                continue

            yield f"data: {json.dumps(item)}\n\n"

            if item.get("type") in {"complete", "error"}:
                break
    finally:
        # Clean up queue to avoid unbounded growth for completed conversations
        _STREAM_QUEUES.pop(conversation_id, None)


@router.post(
    "/chat",
    response_model=SendMessageResponse,
    response_model_by_alias=True,
    summary="Submit a chat message",
    description="Accepts a chat message and enqueues a streaming response (mock or real).",
)
async def post_chat(
    request: SendMessageRequest,
    _: SessionPayload = Depends(require_session),
) -> SendMessageResponse:
    """Accept a chat message and start a streaming response (mock or real)."""

    conversation_id = request.conversation_id or str(uuid.uuid4())
    queue = _get_queue(conversation_id)

    # Avoid unbounded queues if the client disconnects without consuming.
    if queue.qsize() > 100:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Conversation queue is full. Please reconnect.",
        )

    message_text = request.message.strip()

    settings = Settings()
    use_real_agent = _should_use_real_agent(settings)

    if use_real_agent:
        asyncio.create_task(
            _stream_langgraph_events(conversation_id, message_text, settings)
        )
    else:
        asyncio.create_task(_mock_stream_response(conversation_id, message_text))

    return SendMessageResponse(
        conversationId=conversation_id,
        message="Message accepted; streaming will continue over SSE.",
    )


@router.get(
    "/chat",
    summary="Stream chat updates",
    description="Server-Sent Events stream for chat responses.",
)
async def stream_chat(
    conversation_id: str | None = None,
    _: SessionPayload = Depends(require_session),
) -> StreamingResponse:
    """Stream chat responses for the provided conversation."""

    active_conversation_id = conversation_id or str(uuid.uuid4())
    generator = _event_stream(active_conversation_id)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


__all__ = ["router"]
