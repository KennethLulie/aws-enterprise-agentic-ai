"""Unit tests for LangGraph agent state helpers and tool registry."""

from typing import cast

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool

from src.agent.graph import get_registered_tools
from src.agent.nodes import chat as chat_node_module
from src.agent.state import (
    AgentState,
    add_tool_used,
    clear_error,
    create_initial_state,
    set_error,
    validate_state,
)
from src.agent.tools import market_data_tool, rag_retrieval, sql_query, tavily_search


@pytest.fixture
def initial_state() -> AgentState:
    """Return a fresh agent state for testing helpers."""

    return create_initial_state(
        conversation_id="test-conv",
        metadata={"user_id": "user-123"},
    )


@pytest.mark.asyncio
async def test_state_creation_sets_defaults() -> None:
    """Verify create_initial_state initializes required fields and metadata."""

    state = create_initial_state()

    assert state["messages"] == [], "Initial messages should be empty."
    assert isinstance(
        state["conversation_id"], str
    ), "conversation_id should default to a string UUID."
    assert state["tools_used"] == [], "tools_used should start empty."
    assert state["last_error"] is None, "last_error should default to None."

    metadata = state["metadata"]
    assert "created_at" in metadata, "metadata should include created_at."
    assert "updated_at" in metadata, "metadata should include updated_at."

    custom_state = create_initial_state(
        conversation_id="custom-id",
        metadata={"request_id": "req-1"},
    )
    assert (
        custom_state["metadata"]["request_id"] == "req-1"
    ), "metadata should merge custom values."
    assert (
        custom_state["conversation_id"] == "custom-id"
    ), "conversation_id should honor provided value."


@pytest.mark.asyncio
async def test_state_validation_flags_errors_and_accepts_valid_state() -> None:
    """Ensure validate_state catches missing/invalid fields and passes valid state."""

    missing_fields_state: AgentState = {}
    is_valid, missing_errors = validate_state(missing_fields_state)

    assert not is_valid, "State without required fields should be invalid."
    assert "Missing required field: messages" in missing_errors
    assert "Missing required field: tools_used" in missing_errors
    assert "Missing required field: metadata" in missing_errors

    type_errors_state: AgentState = cast(
        AgentState,
        {
            "messages": "not-a-list",
            "conversation_id": 123,
            "tools_used": {},
            "last_error": 42,
            "metadata": [],
        },
    )
    is_valid_types, type_errors = validate_state(type_errors_state)

    assert not is_valid_types, "State with invalid types should be rejected."
    assert "Field 'messages' must be a list" in type_errors
    assert "Field 'conversation_id' must be a string or None" in type_errors
    assert "Field 'tools_used' must be a list" in type_errors
    assert "Field 'last_error' must be a string or None" in type_errors
    assert "Field 'metadata' must be a dict" in type_errors

    valid_state = create_initial_state(
        conversation_id="valid-conv",
        metadata={"trace_id": "trace-123"},
    )
    valid_state["messages"].append(HumanMessage(content="Hello"))
    is_valid_final, final_errors = validate_state(valid_state)

    assert is_valid_final, f"Valid state should pass validation. Errors: {final_errors}"
    assert final_errors == [], "No validation errors expected for valid state."


@pytest.mark.asyncio
async def test_state_helpers_manage_tools_and_errors(initial_state: AgentState) -> None:
    """Check add_tool_used, set_error, and clear_error maintain state integrity."""

    state_with_tool = add_tool_used(initial_state, "search")
    assert (
        "search" in state_with_tool["tools_used"]
    ), "Tool should be added to tools_used."
    assert initial_state["tools_used"] == [], "Original state should remain unchanged."

    deduped_state = add_tool_used(state_with_tool, "search")
    assert (
        deduped_state["tools_used"] == state_with_tool["tools_used"]
    ), "Tools should not duplicate."

    state_with_error = set_error(state_with_tool, "failure")
    assert state_with_error["last_error"] == "failure", "Error message should be set."

    cleared_state = clear_error(state_with_error)
    assert cleared_state["last_error"] is None, "Error should be cleared."
    assert (
        cleared_state["conversation_id"] == initial_state["conversation_id"]
    ), "Conversation ID should be preserved."


@pytest.mark.asyncio
async def test_get_registered_tools_contains_expected_tools() -> None:
    """Verify get_registered_tools returns the configured LangChain tools."""

    tools = list(get_registered_tools())
    expected_tools = [
        tavily_search,
        sql_query,
        rag_retrieval,
        market_data_tool,
    ]

    assert len(tools) == len(expected_tools), "Unexpected tool count in registry."
    assert [tool.name for tool in tools] == [
        tool.name for tool in expected_tools
    ], "Registered tool names should match expected set and order."
    assert all(
        isinstance(tool, BaseTool) for tool in tools
    ), "All registered items must be LangChain tools."


@pytest.mark.asyncio
async def test_create_success_state_does_not_conflict_messages() -> None:
    """Ensure success state creation overwrites messages without duplicate kw errors."""

    state = create_initial_state(conversation_id="conv-123")
    state["messages"] = [HumanMessage(content="hi")]
    state["last_error"] = "previous"

    updated = chat_node_module._create_success_state(state, AIMessage(content="ok"))  # type: ignore[attr-defined]

    assert len(updated["messages"]) == 1
    assert isinstance(updated["messages"][0], AIMessage)
    assert updated["messages"][0].content == "ok"
    assert updated["last_error"] is None


@pytest.mark.asyncio
async def test_chat_node_returns_friendly_error_when_models_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """chat_node should surface a user-friendly error when both models fail."""

    call_count = {"n": 0}

    async def failing_invoke_model(*args: object, **kwargs: object) -> None:
        """Stub that fails on invocation to simulate model errors."""
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("primary boom")
        raise RuntimeError("fallback boom")

    monkeypatch.setattr(chat_node_module, "_invoke_model", failing_invoke_model)

    state = create_initial_state(conversation_id="conv-err")
    state["messages"] = [HumanMessage(content="hello")]

    result = await chat_node_module.chat_node(state)

    assert result["last_error"], "Expected a user-facing error message"
    assert "temporarily unavailable" in result["last_error"]
    assert "primary boom" not in result["last_error"]
    assert "fallback boom" not in result["last_error"]
