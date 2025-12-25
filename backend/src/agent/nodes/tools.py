"""
Tool execution node for LangGraph agent.

This module implements the tool execution node that runs tools based on
LLM tool call decisions. It handles:
- Parsing tool calls from AIMessage responses
- Executing registered tools with provided arguments
- Formatting results as ToolMessage objects
- Tracking which tools were used for observability
- Graceful error handling for individual tool failures

The node executes between the chat node (which decides to use tools)
and returns results to the graph for further processing.

Usage:
    from src.agent.nodes.tools import tool_execution_node

    # Use in LangGraph StateGraph
    graph.add_node("tools", tool_execution_node)

Reference:
    - agent.mdc for tool execution patterns
    - LangChain ToolMessage docs
"""

from __future__ import annotations

import json
import inspect
from typing import Any

import structlog
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from src.agent.graph import get_registered_tools
from src.agent.state import AgentState, add_tool_used, set_error
from typing import cast

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Tool Execution Node
# =============================================================================


async def tool_execution_node(state: AgentState) -> AgentState:
    """
    Execute tools based on LLM tool call decisions.

    This node:
    1. Checks if the last message is an AIMessage with tool_calls
    2. Retrieves registered tools via get_registered_tools()
    3. Executes each requested tool with provided arguments
    4. Formats results as ToolMessage objects
    5. Tracks tools used via add_tool_used() helper
    6. Handles errors gracefully, setting last_error on failure

    Args:
        state: Current agent state containing messages with potential tool calls.

    Returns:
        Updated AgentState with:
        - Tool results appended to messages as ToolMessage objects
        - tools_used updated with names of executed tools
        - last_error set if any tool execution fails

    Example:
        # State with AIMessage containing tool_calls
        state = await tool_execution_node(state)
        # state["messages"] now includes ToolMessage results
        # state["tools_used"] tracks which tools ran
    """
    messages = state.get("messages", [])
    conversation_id = state.get("conversation_id", "unknown")

    log = logger.bind(
        conversation_id=conversation_id,
        message_count=len(messages),
    )

    # Check if we have messages to process
    if not messages:
        log.debug("tool_execution_node: No messages to process")
        return state

    last_message = messages[-1]

    # Check if it's an AIMessage with tool_calls
    if not isinstance(last_message, AIMessage):
        log.debug(
            "tool_execution_node: Last message is not an AIMessage",
            message_type=type(last_message).__name__,
        )
        return state

    tool_calls = getattr(last_message, "tool_calls", None)
    if not tool_calls:
        log.debug("tool_execution_node: No tool calls in last message")
        return state

    log.info(
        "tool_execution_node: Processing tool calls",
        tool_call_count=len(tool_calls),
    )

    # Get registered tools and build lookup map
    registered_tools = get_registered_tools()
    tool_map = {tool.name: tool for tool in registered_tools}

    log.debug(
        "tool_execution_node: Available tools",
        available_tools=list(tool_map.keys()),
    )

    # Execute each tool call and collect results
    tool_messages: list[ToolMessage] = []
    current_state = state

    for idx, tool_call in enumerate(tool_calls):
        normalized, reason = _normalize_tool_call(tool_call)
        if normalized is None:
            tool_call_id = f"unknown-{idx}"
            log.warning(
                "tool_execution_node: Unable to parse tool call payload",
                tool_call_type=type(tool_call).__name__,
                reason=reason,
            )
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Unable to parse tool call payload ({reason or 'unknown reason'}).",
                    tool_call_id=tool_call_id,
                    name="unknown",
                )
            )
            current_state = set_error(
                current_state,
                f"Unable to parse tool call payload ({reason or 'unknown reason'}).",
            )
            continue

        tool_name, tool_call_id, tool_args = normalized

        log.info(
            "tool_execution_node: Executing tool",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )

        # Check if tool is registered
        if tool_name not in tool_map:
            error_msg = f"Tool '{tool_name}' is not registered"
            log.warning(
                "tool_execution_node: Unknown tool requested",
                tool_name=tool_name,
                available_tools=list(tool_map.keys()),
            )
            tool_messages.append(
                ToolMessage(
                    content=f"Error: {error_msg}",
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )
            current_state = set_error(current_state, error_msg)
            continue

        # Execute the tool
        tool = tool_map[tool_name]
        try:
            result = await _execute_tool(tool, tool_args, log)

            log.info(
                "tool_execution_node: Tool executed successfully",
                tool_name=tool_name,
                result_type=type(result).__name__,
            )

            # Format result as string if needed
            result_str = _format_tool_result(result)

            tool_messages.append(
                ToolMessage(
                    content=result_str,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )

            # Track that this tool was used
            current_state = add_tool_used(current_state, tool_name)

        except Exception as e:
            error_msg = f"Tool execution failed: {e!s}"
            log.error(
                "tool_execution_node: Tool execution error",
                tool_name=tool_name,
                error=str(e),
            )

            # Add error as tool result (allows LLM to handle gracefully)
            tool_messages.append(
                ToolMessage(
                    content=f"Error executing {tool_name}: {e!s}",
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )

            # Set error in state
            current_state = set_error(current_state, error_msg)

    log.info(
        "tool_execution_node: Completed tool execution",
        tools_executed=len(tool_messages),
        tools_used=current_state.get("tools_used", []),
    )

    # Return updated state with tool messages
    # The add_messages reducer will handle appending properly
    return AgentState(
        messages=cast(list[BaseMessage], tool_messages),
        conversation_id=current_state.get("conversation_id"),
        tools_used=current_state.get("tools_used", []),
        last_error=current_state.get("last_error"),
        metadata=current_state.get("metadata", {}),
    )


async def _execute_tool(
    tool: Any,
    args: dict[str, Any],
    log: structlog.BoundLogger,
) -> Any:
    """
    Execute a single tool with the provided arguments.

    Handles both sync and async tool invocation patterns.

    Args:
        tool: The LangChain tool to execute.
        args: Arguments to pass to the tool.
        log: Bound logger for contextual logging.

    Returns:
        The tool execution result.

    Raises:
        Exception: If tool execution fails.
    """
    log.debug(
        "Executing tool",
        tool_name=tool.name,
        arg_keys=list(args.keys()) if isinstance(args, dict) else "non-dict",
    )

    # Use ainvoke for async execution (preferred for LangChain tools)
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)
    if hasattr(tool, "invoke"):
        return tool.invoke(args)
    # Fallback: call directly if it's a callable
    if callable(tool):
        if inspect.iscoroutinefunction(tool):
            return await tool(**args)
        result = tool(**args)
        if inspect.isawaitable(result):
            return await result
        return result

    raise TypeError(f"Tool {tool.name} is not invocable")


def _format_tool_result(result: Any) -> str:
    """
    Format tool result as a string for ToolMessage content.

    Handles various result types including dicts, lists, and primitives.

    Args:
        result: The raw tool execution result.

    Returns:
        String representation suitable for ToolMessage content.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, default=str)
    return str(result)


def _normalize_tool_call(
    tool_call: Any,
) -> tuple[tuple[str, str, dict[str, Any]] | None, str | None]:
    """
    Normalize tool call payloads to a common tuple of (name, id, args).

    Supports LangChain ToolCall objects and dict-like payloads and
    tolerates args provided as JSON strings (common in Bedrock).
    """
    name = getattr(tool_call, "name", None)
    call_id = getattr(tool_call, "id", None)
    args: Any = getattr(tool_call, "args", None) or getattr(
        tool_call, "arguments", None
    )

    if isinstance(tool_call, dict):
        name = name or tool_call.get("name")
        call_id = call_id or tool_call.get("id")
        args = args or tool_call.get("args") or tool_call.get("arguments")

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}

    if not isinstance(args, dict):
        args = {}

    if not name or not call_id:
        return None, "missing tool name or id"

    return (name, call_id, args), None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "tool_execution_node",
]
