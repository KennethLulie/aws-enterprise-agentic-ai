"""
LangGraph graph definition for the Phase 0 agent.

This module wires together the LangGraph StateGraph with chat, tool execution,
and error recovery nodes. It also exposes the registered tool list for binding
to the chat node and tool execution node. Phase 0 uses an in-memory
MemorySaver checkpointer to keep state lightweight for local development.
"""

from __future__ import annotations

from typing import Sequence

from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agent.tools import market_data_tool, rag_retrieval, sql_query, tavily_search

REGISTERED_TOOLS: tuple[BaseTool, ...] = (
    tavily_search,
    sql_query,
    rag_retrieval,
    market_data_tool,
)


def get_registered_tools() -> Sequence[BaseTool]:
    """
    Return the tools available to the agent for LangGraph binding.

    Tools are kept in a single registry to ensure consistent binding between
    the chat node (for tool calls) and the tool execution node.
    """

    return REGISTERED_TOOLS


# Late imports to avoid circular dependency with tool_execution_node which
# imports get_registered_tools from this module.
from src.agent.nodes.chat import chat_node  # noqa: E402
from src.agent.nodes.error_recovery import error_recovery_node  # noqa: E402
from src.agent.nodes.tools import tool_execution_node  # noqa: E402
from src.agent.state import AgentState  # noqa: E402


# =============================================================================
# Routing helpers
# =============================================================================


async def _chat_with_tools(state: AgentState) -> AgentState:
    """Invoke the chat node with all registered tools bound."""

    return await chat_node(state, tools=get_registered_tools())


def _route_from_chat(state: AgentState) -> str:
    """
    Decide next step after the chat node.

    Returns:
        - "error" when last_error is populated (route to error recovery)
        - "tools" when the last AI message contains tool_calls
        - "end" when no tool calls are present
    """

    if state.get("last_error"):
        return "error"

    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "tools" if tool_calls else "end"


def _route_from_tools(state: AgentState) -> str:
    """
    Decide next step after tool execution.

    Routes errors to the error recovery node, otherwise loops back to chat.
    """

    return "error" if state.get("last_error") else "continue"


# =============================================================================
# Graph construction
# =============================================================================

# In-memory checkpointing for Phase 0 (no DB dependency)
checkpointer = MemorySaver()

_graph_builder = StateGraph(AgentState)
_graph_builder.add_node("chat", _chat_with_tools)
_graph_builder.add_node("tools", tool_execution_node)
_graph_builder.add_node("error_recovery", error_recovery_node)

_graph_builder.add_edge(START, "chat")
_graph_builder.add_conditional_edges(
    "chat",
    _route_from_chat,
    {
        "tools": "tools",
        "end": END,
        "error": "error_recovery",
    },
)
_graph_builder.add_conditional_edges(
    "tools",
    _route_from_tools,
    {
        "continue": "chat",
        "error": "error_recovery",
    },
)
_graph_builder.add_edge("error_recovery", END)

graph = _graph_builder.compile(checkpointer=checkpointer)


__all__ = ["graph", "get_registered_tools", "checkpointer"]
