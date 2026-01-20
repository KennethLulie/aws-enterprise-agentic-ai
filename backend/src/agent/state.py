"""
Agent state schema for LangGraph graph execution.

This module defines the TypedDict state schema used by the LangGraph agent.
LangGraph requires TypedDict (not Pydantic) for state management to ensure
proper state updates and checkpointing behavior.

State Fields:
    messages: Conversation history with LangChain message format.
              Uses the add_messages reducer for proper message handling.
    conversation_id: Unique identifier for the conversation session.
    tools_used: List of tool names called during this graph execution.
    last_error: Most recent error message for error recovery.
    metadata: Extensible dictionary for additional context.

LangGraph Reducers:
    The `messages` field uses the `add_messages` reducer which:
    - Appends new messages to existing history
    - Handles message deduplication by ID
    - Properly merges tool call results

Usage:
    from src.agent.state import AgentState, create_initial_state

    # Create initial state for new conversation
    state = create_initial_state(conversation_id="conv-123")

    # Use in LangGraph node
    async def chat_node(state: AgentState) -> AgentState:
        # Process state...
        return {
            **state,
            "messages": state["messages"] + [new_message],
            "tools_used": state["tools_used"] + ["market_data"],
        }

Reference:
    - LangGraph StateGraph: https://langchain-ai.github.io/langgraph/
    - LangChain Messages: https://python.langchain.com/docs/concepts/messages/
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# =============================================================================
# State Schema
# =============================================================================


class AgentState(TypedDict, total=False):
    """
    TypedDict state schema for the LangGraph agent.

    This schema defines the structure of state passed between graph nodes.
    All fields except `messages` are optional (total=False) to allow
    incremental state updates in nodes.

    Attributes:
        messages: Conversation history as LangChain BaseMessage objects.
            Uses the add_messages reducer for proper append/merge behavior.
            This is the primary communication channel between nodes.

        conversation_id: Unique identifier for this conversation session.
            Used as the checkpoint key for state persistence.
            Format: UUID string (e.g., "550e8400-e29b-41d4-a716-446655440000")

        tools_used: List of tool names called during this graph execution.
            Populated by the tool execution node for observability.
            Example: ["market_data", "search", "sql"]

        last_error: Most recent error message encountered during execution.
            Used by the error recovery node to determine recovery strategy.
            Cleared after successful recovery.

        metadata: Extensible dictionary for additional context.
            Can include: user_id, session_start, request_id, etc.
            Preserved across state updates.

    Example:
        state: AgentState = {
            "messages": [HumanMessage(content="Hello")],
            "conversation_id": "conv-123",
            "tools_used": [],
            "last_error": None,
            "metadata": {"user_id": "user-456"},
        }
    """

    # Primary message history with reducer for proper handling
    messages: Annotated[list[BaseMessage], add_messages]

    # Conversation tracking
    conversation_id: str | None

    # Tool execution tracking
    tools_used: list[str]

    # Error handling
    last_error: str | None

    # Extensible metadata
    metadata: dict[str, Any]


# =============================================================================
# State Factory Functions
# =============================================================================


def create_initial_state(
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentState:
    """
    Create initial state for a new conversation.

    This factory function creates a properly initialized AgentState
    with all required fields set to appropriate defaults.

    Args:
        conversation_id: Optional conversation ID. If not provided,
            a new UUID will be generated.
        metadata: Optional metadata dictionary. If not provided,
            basic metadata with timestamp will be created.

    Returns:
        AgentState: Initialized state ready for graph execution.

    Example:
        # New conversation with auto-generated ID
        state = create_initial_state()

        # Existing conversation
        state = create_initial_state(
            conversation_id="existing-conv-id",
            metadata={"user_id": "user-123"}
        )
    """
    now = datetime.now(timezone.utc).isoformat()

    return AgentState(
        messages=[],
        conversation_id=conversation_id or str(uuid.uuid4()),
        tools_used=[],
        last_error=None,
        metadata={
            "created_at": now,
            "updated_at": now,
            **(metadata or {}),
        },
    )


def validate_state(state: AgentState) -> tuple[bool, list[str]]:
    """
    Validate agent state structure and contents.

    Checks that the state has all required fields with correct types.
    Use this for debugging and ensuring state integrity.

    Args:
        state: The AgentState to validate.

    Returns:
        Tuple of (is_valid, errors) where errors is a list of
        validation error messages.

    Example:
        is_valid, errors = validate_state(state)
        if not is_valid:
            for error in errors:
                logger.error(f"State validation error: {error}")
    """
    errors: list[str] = []

    # Check messages field
    if "messages" not in state:
        errors.append("Missing required field: messages")
    elif not isinstance(state.get("messages"), list):
        errors.append("Field 'messages' must be a list")

    # Check conversation_id (optional but should be string if present)
    conv_id = state.get("conversation_id")
    if conv_id is not None and not isinstance(conv_id, str):
        errors.append("Field 'conversation_id' must be a string or None")

    # Check tools_used
    if "tools_used" not in state:
        errors.append("Missing required field: tools_used")
    elif not isinstance(state.get("tools_used"), list):
        errors.append("Field 'tools_used' must be a list")

    # Check last_error (optional)
    last_error = state.get("last_error")
    if last_error is not None and not isinstance(last_error, str):
        errors.append("Field 'last_error' must be a string or None")

    # Check metadata
    if "metadata" not in state:
        errors.append("Missing required field: metadata")
    elif not isinstance(state.get("metadata"), dict):
        errors.append("Field 'metadata' must be a dict")

    return len(errors) == 0, errors


def update_state_metadata(
    state: AgentState,
    **kwargs: Any,
) -> AgentState:
    """
    Update state metadata with new values.

    Creates a new state with updated metadata, preserving immutability.
    Automatically updates the 'updated_at' timestamp.

    Args:
        state: The current AgentState.
        **kwargs: Key-value pairs to add/update in metadata.

    Returns:
        New AgentState with updated metadata.

    Example:
        state = update_state_metadata(
            state,
            user_id="user-123",
            request_id="req-456",
        )
    """
    current_metadata = state.get("metadata", {})
    new_state = AgentState(**state)
    new_state["metadata"] = {
        **current_metadata,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    return new_state


def add_tool_used(state: AgentState, tool_name: str) -> AgentState:
    """
    Add a tool name to the tools_used list.

    Creates a new state with the tool added, preserving immutability.
    Avoids duplicates in the same execution.

    Args:
        state: The current AgentState.
        tool_name: Name of the tool that was called.

    Returns:
        New AgentState with tool added to tools_used.

    Example:
        state = add_tool_used(state, "market_data")
    """
    current_tools = state.get("tools_used", [])
    if tool_name not in current_tools:
        new_state = AgentState(**state)
        new_state["tools_used"] = [*current_tools, tool_name]
        return new_state
    return state


def set_error(state: AgentState, error_message: str) -> AgentState:
    """
    Set the last_error field in state.

    Creates a new state with the error set, preserving immutability.

    Args:
        state: The current AgentState.
        error_message: The error message to record.

    Returns:
        New AgentState with last_error set.

    Example:
        state = set_error(state, "Tool execution failed: timeout")
    """
    new_state = AgentState(**state)
    new_state["last_error"] = error_message
    return new_state


def clear_error(state: AgentState) -> AgentState:
    """
    Clear the last_error field in state.

    Creates a new state with the error cleared, preserving immutability.
    Call this after successful error recovery.

    Args:
        state: The current AgentState.

    Returns:
        New AgentState with last_error set to None.

    Example:
        # After successful recovery
        state = clear_error(state)
    """
    new_state = AgentState(**state)
    new_state["last_error"] = None
    return new_state


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # State schema
    "AgentState",
    # Factory functions
    "create_initial_state",
    "validate_state",
    # State update helpers
    "update_state_metadata",
    "add_tool_used",
    "set_error",
    "clear_error",
]
