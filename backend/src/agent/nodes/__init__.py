"""
LangGraph node functions for agent graph execution.

This package contains the node implementations for the LangGraph agent.
Each node is an async function that takes AgentState and returns AgentState,
following the LangGraph node function signature pattern.

Node Architecture:
    User Message → chat_node → [tools_node] → error_recovery_node → Response
                      ↓              ↓
                 LLM Decision   Tool Execution
                      ↓              ↓
                  Tool Calls    External APIs

Nodes:
    chat_node: Main LLM invocation node. Processes user messages,
        decides whether to use tools, and generates responses.

    tools_node: Tool execution node. Executes tools based on LLM
        tool calls and returns results to the graph.

    error_recovery_node: Error handling node. Handles errors from
        other nodes and implements recovery strategies.

Node Function Signature:
    All node functions follow this signature:

    async def node_name(state: AgentState) -> AgentState:
        '''Process state and return updated state.'''
        # Implementation
        return updated_state

State Updates:
    - Nodes return new state (don't mutate in place)
    - Use state spread: {**state, "field": new_value}
    - The messages field uses add_messages reducer for proper handling

Phase 0 Implementation:
    Nodes provide working behavior for local development.
    tools_node executes registered tools (see tools.py).
    Error recovery remains minimal and will expand in Phase 1b+.

Usage:
    from src.agent.nodes import chat_node, tools_node, error_recovery_node

    # Use in LangGraph StateGraph
    graph.add_node("chat", chat_node)
    graph.add_node("tools", tools_node)
    graph.add_node("error_recovery", error_recovery_node)

Reference:
    - agentic-ai.mdc for node patterns
    - LangGraph docs: https://langchain-ai.github.io/langgraph/
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.agent.state import AgentState

# Import nodes from dedicated modules
from src.agent.nodes.chat import chat_node
from src.agent.nodes.error_recovery import error_recovery_node
from src.agent.nodes.tools import tool_execution_node

if TYPE_CHECKING:
    pass

# Configure module logger
logger = logging.getLogger(__name__)


# Alias tool_execution_node as tools_node for backward compatibility with graph
# The full implementation is in src.agent.nodes.tools
tools_node = tool_execution_node


# =============================================================================
# Conditional Edge Functions
# =============================================================================


def should_use_tools(state: AgentState) -> str:
    """
    Determine if the agent should use tools based on LLM response.

    This function is used as a conditional edge in the LangGraph graph
    to route execution to the tools node or directly to output.

    Args:
        state: Current agent state with LLM response.

    Returns:
        "tools" if tools should be called, "end" otherwise.

    Phase 0: Always returns "end" (no tool execution).
    Phase 1b+: Inspects LLM response for tool_calls.

    Example:
        graph.add_conditional_edges(
            "chat",
            should_use_tools,
            {"tools": "tools", "end": END}
        )
    """
    # Phase 0: No tool execution
    # Phase 1b+ will check: state["messages"][-1].tool_calls
    return "end"


def has_error(state: AgentState) -> str:
    """
    Check if the state contains an error that needs recovery.

    Args:
        state: Current agent state.

    Returns:
        "error" if last_error is set, "continue" otherwise.

    Example:
        graph.add_conditional_edges(
            "tools",
            has_error,
            {"error": "error_recovery", "continue": "chat"}
        )
    """
    if state.get("last_error"):
        return "error"
    return "continue"


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Node functions
    "chat_node",
    "tool_execution_node",
    "tools_node",  # Alias for tool_execution_node
    "error_recovery_node",
    # Conditional edge functions
    "should_use_tools",
    "has_error",
]
