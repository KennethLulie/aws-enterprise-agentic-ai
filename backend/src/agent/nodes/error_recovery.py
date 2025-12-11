"""
Error recovery node for LangGraph agent executions.

This node converts internal errors into user-friendly responses while
clearing error state for the next graph step. It logs full technical
details with structlog and keeps user-facing messages actionable and
non-technical.
"""

from __future__ import annotations

import structlog
from langchain_core.messages import AIMessage

from src.agent.state import AgentState, clear_error

# Configure structured logger
logger = structlog.get_logger(__name__)


async def error_recovery_node(state: AgentState) -> AgentState:
    """
    Handle errors recorded in the agent state and return a safe response.

    Workflow:
    1. Check for last_error; if absent, return state unchanged.
    2. Log technical error details with conversation context.
    3. Generate a user-friendly, actionable AIMessage (no stack traces).
    4. Clear last_error and append the error response to messages.
    """
    error_text = state.get("last_error")
    conversation_id = state.get("conversation_id", "unknown")
    metadata = state.get("metadata", {}) or {}

    log = logger.bind(
        conversation_id=conversation_id,
        request_id=metadata.get("request_id"),
        user_id=metadata.get("user_id"),
    )

    if not error_text:
        log.debug("error_recovery_node: No error to recover from")
        return state

    log.error(
        "error_recovery_node: Handling error",
        last_error=error_text,
    )

    user_message = _friendly_error_message(error_text)

    error_response = AIMessage(content=user_message)
    cleared_state = clear_error(state)

    return AgentState(
        **cleared_state,
        messages=[error_response],
    )


def _friendly_error_message(error_text: str) -> str:
    """
    Map internal error text to a user-facing, actionable message.
    """
    lowered = error_text.lower()

    if "rate limit" in lowered or "429" in lowered:
        return (
            "I'm being rate limited right now. Please wait a few seconds and try "
            "again, or simplify the request."
        )

    if "timeout" in lowered or "timed out" in lowered:
        return (
            "That took too long to complete. Please try again with a smaller or "
            "more specific request."
        )

    if "tool" in lowered or "execute" in lowered:
        return (
            "A tool I rely on had an issue. Please rephrase what you need or try a "
            "narrower request."
        )

    if "model" in lowered or "fallback" in lowered:
        return (
            "The model had trouble completing that. Please try again, and I'll "
            "retry with a safer approach."
        )

    return (
        "I ran into an issue while processing that request. Please try again in a "
        "moment or rephrase what you need. If it keeps happening, tell me the task "
        "and I will adjust."
    )


__all__ = [
    "error_recovery_node",
]
