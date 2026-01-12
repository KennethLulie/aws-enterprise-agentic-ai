"""
V1 Chat endpoints providing POST and SSE streaming.

This module provides versioned chat endpoints at /api/v1/chat. The functionality
is identical to the legacy /api/chat endpoints but mounted under the v1 namespace
for API versioning support.

Phase 0 defaults to a lightweight mock streaming path. When Bedrock credentials
are configured, the endpoints stream real LangGraph responses (LLM + tools).
This keeps the API surface stable while enabling incremental bring-up:
verify UI first with mocks, then switch to real agent behavior without
changing the routes.

Rate Limiting:
    Both endpoints are rate limited to 10 requests per minute per IP address
    using slowapi. This prevents abuse and ensures fair usage across clients.
    The rate limit can be configured via settings.rate_limit_per_minute.

Streaming Implementation:
    Uses LangGraph's astream() with stream_mode="values" to receive the full
    AgentState after each graph step. This allows extracting messages and errors
    from the complete state rather than handling per-node updates.

Thinking Content:
    Nova Pro and other models may include <thinking>...</thinking> tags for
    chain-of-thought reasoning. This module parses these out and sends them
    as separate "thinking" events so the frontend can display them appropriately
    (e.g., in a collapsible section). The main message content is sent without
    the thinking tags.

Note:
    The /api/v1 prefix is applied in main.py when including the v1 router.
    Routes in this module are defined relative to that prefix.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, AsyncIterator, Dict, Sequence

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from src.agent.graph import graph
from src.agent.state import AgentState, create_initial_state
from src.api.middleware.rate_limit import DEFAULT_RATE_LIMIT, limiter
from src.api.routes.auth import SessionPayload, require_session
from src.config import Settings

# Configure module logger
logger = structlog.get_logger(__name__)

# Regex pattern to extract <thinking>...</thinking> content
# Supports multiline thinking blocks
THINKING_PATTERN = re.compile(
    r"<thinking>(.*?)</thinking>",
    re.DOTALL | re.IGNORECASE,
)


def _parse_thinking_content(content: str) -> tuple[str, str | None]:
    """
    Parse thinking content from model response.

    Some models (like Nova Pro) include <thinking>...</thinking> tags
    for chain-of-thought reasoning. This function extracts the thinking
    content and returns the cleaned message.

    Args:
        content: Raw content string that may contain thinking tags.

    Returns:
        Tuple of (cleaned_content, thinking_content).
        thinking_content is None if no thinking tags found.
    """
    thinking_match = THINKING_PATTERN.search(content)
    if thinking_match:
        thinking_content = thinking_match.group(1).strip()
        # Remove all thinking blocks from the content
        cleaned_content = THINKING_PATTERN.sub("", content).strip()
        return cleaned_content, thinking_content
    return content, None


# V1 chat router - no prefix here, /api/v1 is applied in main.py
router = APIRouter(prefix="/chat", tags=["v1", "Chat"])

# In-memory queues keyed by conversation_id. This is sufficient for Phase 0 demos.
# Note: Using separate namespace from legacy routes to avoid conflicts
_V1_STREAM_QUEUES: Dict[str, asyncio.Queue[dict[str, Any]]] = {}
_KEEPALIVE_SECONDS = 15


def _get_queue(conversation_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Return (or create) the queue for a conversation."""
    if conversation_id not in _V1_STREAM_QUEUES:
        _V1_STREAM_QUEUES[conversation_id] = asyncio.Queue()
    return _V1_STREAM_QUEUES[conversation_id]


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
            "content": f'I heard: "{user_message}". ',
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
    """Use real LangGraph only when AWS credentials are configured.

    Returns True when:
    1. Running in AWS environment (credentials come from IAM role), OR
    2. Explicit AWS credentials are set (for local development)
    """
    # In AWS environment, IAM role provides credentials via instance metadata
    if settings.is_aws():
        return True

    # For local development, require explicit credentials
    return bool(settings.aws_access_key_id and settings.aws_secret_access_key)


async def _stream_langgraph_events(
    conversation_id: str, user_message: str, settings: Settings
) -> None:
    """
    Run the LangGraph agent and push streaming events into the SSE queue.

    This keeps the API surface the same while allowing real tool execution when
    Bedrock credentials are present.

    Uses stream_mode="values" to receive the full AgentState after each graph
    step, allowing proper extraction of messages and error state.

    Args:
        conversation_id: Unique identifier for this conversation.
        user_message: The user's chat message to process.
        settings: Application settings (used for configuration).
    """
    queue = _get_queue(conversation_id)
    log = logger.bind(conversation_id=conversation_id)

    state: AgentState = create_initial_state(conversation_id=conversation_id)
    state["messages"] = [HumanMessage(content=user_message)]

    log.info("Starting LangGraph agent stream", user_message_length=len(user_message))

    # Track the position of the user's new message in the conversation.
    # With checkpointing, the graph state includes ALL previous messages.
    # We only want to stream NEW responses (after the user's current input).
    user_message_index: int | None = None
    last_processed_index: int = 0

    try:
        # Use stream_mode="values" to get full state after each step.
        # Default "updates" mode returns per-node dicts, not the full state.
        async for graph_state in graph.astream(
            state,
            config={"configurable": {"thread_id": conversation_id}},
            stream_mode="values",
        ):
            messages: Sequence[BaseMessage] = graph_state.get("messages", [])
            last_error = graph_state.get("last_error")

            # On first iteration, find the user's new message (last HumanMessage)
            # and set our baseline to only stream messages AFTER it
            if user_message_index is None:
                for i, msg in enumerate(messages):
                    if isinstance(msg, HumanMessage) and msg.content == user_message:
                        user_message_index = i
                # If we found the user's message, start processing AFTER it
                if user_message_index is not None:
                    last_processed_index = user_message_index + 1
                    log.debug(
                        "Found user message position",
                        user_message_index=user_message_index,
                        starting_from=last_processed_index,
                        total_messages=len(messages),
                    )

            log.debug(
                "Received graph state",
                message_count=len(messages),
                has_error=bool(last_error),
                last_processed_index=last_processed_index,
            )

            # Only process NEW messages (those after the user's input)
            # This prevents re-sending messages from previous turns
            for i, message in enumerate(messages):
                if i < last_processed_index:
                    continue

                if isinstance(message, AIMessage):
                    raw_content = message.content
                    tool_calls = getattr(message, "tool_calls", None)
                    additional_kwargs = getattr(message, "additional_kwargs", {})

                    # Debug: log the full AI message structure
                    log.debug(
                        "AI message structure",
                        raw_content_type=type(raw_content).__name__,
                        raw_content_repr=repr(raw_content)[:500],
                        has_tool_calls=bool(tool_calls),
                        tool_calls_count=len(tool_calls) if tool_calls else 0,
                        additional_kwargs_keys=(
                            list(additional_kwargs.keys()) if additional_kwargs else []
                        ),
                    )

                    # Handle content that can be string or list of content blocks
                    if isinstance(raw_content, str):
                        content = raw_content
                    elif isinstance(raw_content, list):
                        # Extract text from content blocks (various formats)
                        text_parts = []
                        for block in raw_content:
                            if isinstance(block, str):
                                text_parts.append(block)
                            elif isinstance(block, dict):
                                # Try different key names used by various providers
                                text = (
                                    block.get("text")
                                    or block.get("content")
                                    or block.get("value")
                                    or ""
                                )
                                if text:
                                    text_parts.append(str(text))
                            elif hasattr(block, "text"):
                                # Handle object with .text attribute
                                text_parts.append(str(block.text))
                        content = "".join(text_parts)
                    else:
                        # Fallback: convert to string
                        content = str(raw_content) if raw_content else ""

                    # Parse out <thinking> content if present
                    # Nova Pro uses this for chain-of-thought reasoning
                    cleaned_content, thinking_content = _parse_thinking_content(content)

                    # Send thinking content as separate event (if present)
                    if thinking_content:
                        log.debug(
                            "Streaming thinking content to client",
                            thinking_preview=thinking_content[:100],
                        )
                        queue.put_nowait(
                            {
                                "type": "thinking",
                                "content": thinking_content,
                                "conversationId": conversation_id,
                            }
                        )

                    log.debug(
                        "Extracted AI message content",
                        content_length=len(cleaned_content) if cleaned_content else 0,
                        has_thinking=bool(thinking_content),
                        content_preview=(
                            cleaned_content[:100] if cleaned_content else "empty"
                        ),
                    )

                    # Skip empty AI messages (can occur before tool calls)
                    if cleaned_content:
                        log.info(
                            "Streaming AI message to client",
                            content_preview=cleaned_content[:100],
                        )
                        queue.put_nowait(
                            {
                                "type": "message",
                                "content": cleaned_content,
                                "conversationId": conversation_id,
                            }
                        )
                elif isinstance(message, ToolMessage):
                    # Don't send raw tool results to the frontend - they're intermediate
                    # results that the AI will process. The user should only see the
                    # AI's final response that incorporates the tool results.
                    log.debug(
                        "Tool result received (not streaming to client)",
                        tool_name=message.name,
                        result_length=(
                            len(str(message.content)) if message.content else 0
                        ),
                    )
                    # Optionally notify frontend that a tool was used (without raw content)
                    queue.put_nowait(
                        {
                            "type": "tool_used",
                            "tool": message.name,
                            "conversationId": conversation_id,
                        }
                    )
                elif isinstance(message, HumanMessage):
                    # Skip human messages (we don't need to stream these back)
                    log.debug("Skipping HumanMessage (already sent by user)")
                else:
                    log.debug(
                        "Skipping unknown message type",
                        message_type=type(message).__name__,
                    )

            # Update our tracking index to the current message count
            last_processed_index = len(messages)

            # Check for errors in the graph state
            if last_error:
                log.warning("Agent encountered error", error=last_error)
                queue.put_nowait(
                    {
                        "type": "error",
                        "content": last_error,
                        "conversationId": conversation_id,
                    }
                )
                return

        log.info("LangGraph agent stream completed successfully")
        queue.put_nowait({"type": "complete", "conversationId": conversation_id})

    except Exception as exc:
        log.exception("LangGraph agent stream failed", error=str(exc))
        queue.put_nowait(
            {
                "type": "error",
                "content": "I'm having trouble processing that request. Please try again.",
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
        _V1_STREAM_QUEUES.pop(conversation_id, None)


@router.post(
    "",
    response_model=SendMessageResponse,
    response_model_by_alias=True,
    summary="Submit a chat message (v1)",
    description="Accepts a chat message and enqueues a streaming response (mock or real).",
)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def post_chat(
    request: Request,
    body: SendMessageRequest,
    _: SessionPayload = Depends(require_session),
) -> SendMessageResponse:
    """Accept a chat message and start a streaming response (mock or real)."""
    conversation_id = body.conversation_id or str(uuid.uuid4())
    queue = _get_queue(conversation_id)

    # Avoid unbounded queues if the client disconnects without consuming.
    if queue.qsize() > 100:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Conversation queue is full. Please reconnect.",
        )

    message_text = body.message.strip()

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
    "",
    summary="Stream chat updates (v1)",
    description="Server-Sent Events stream for chat responses.",
)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def stream_chat(
    request: Request,
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
