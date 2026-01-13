"""
Agent package for LangGraph-based agentic AI orchestration.

This package provides the core agent implementation using LangGraph for
multi-step reasoning, tool orchestration, and conversation management.
Powered by AWS Bedrock (Nova Pro/Lite) with Claude fallback.

Usage:
    from src.agent import AgentState, create_initial_state, get_registered_tools

    # Create initial state for a conversation
    state = create_initial_state(conversation_id="conv-123")

    # Get all registered tools for LangGraph binding
    tools = get_registered_tools()

    # Validate agent configuration
    from src.agent import validate_agent_config
    validation = validate_agent_config()

    # Get default agent (MemorySaver)
    from src.agent import get_agent
    agent = get_agent()

Checkpointing:
    The agent supports two checkpointing modes:

    1. MemorySaver (default, local development):
       from src.agent import get_agent
       agent = get_agent()  # Uses MemorySaver by default

    2. PostgresSaver (production, requires database):
       from src.agent import get_checkpointer, build_graph

       # Use context manager for proper connection lifecycle
       with get_checkpointer(database_url) as checkpointer:
           agent = build_graph(checkpointer)
           # Use agent within this context...

       # Or in FastAPI lifespan:
       @asynccontextmanager
       async def lifespan(app: FastAPI):
           with get_checkpointer(settings.database_url) as checkpointer:
               app.state.agent = build_graph(checkpointer)
               yield

Package Structure:
    - graph.py: LangGraph graph definition and tool registration
    - state.py: Agent state schema (TypedDict)
    - nodes/: Graph node implementations
        - chat.py: LLM invocation node
        - tools.py: Tool execution node
        - error_recovery.py: Error handling node
    - tools/: Tool implementations
        - market_data.py: Financial market data (FMP API)
        - search.py: Web search (Tavily) - Phase 2
        - sql.py: Database queries - Phase 2
        - rag.py: RAG retrieval - Phase 2

Architecture:
    User Message → Chat Node → [Tool Node] → Error Recovery → Response
                      ↓              ↓
                 Tool Decision   Tool Execution
                      ↓              ↓
                   LLM Call    External APIs

Phase 0-1a:
    - Tool registration with market_data_tool
    - MemorySaver for in-memory checkpointing
    - Mock data fallback when API keys unavailable

Phase 1b+:
    - Full LangGraph StateGraph with streaming
    - PostgresSaver for persistent checkpointing (Neon PostgreSQL)
    - Multi-tool orchestration and coordination
    - Error recovery with fallback strategies

Example - Tool Registration:
    from src.agent import get_registered_tools
    from langchain_aws import ChatBedrockConverse

    # Get tools for LLM binding
    tools = get_registered_tools()

    # Bind to LLM (uses Converse API, recommended for Nova Pro)
    llm = ChatBedrockConverse(model="amazon.nova-pro-v1:0")
    llm_with_tools = llm.bind_tools(tools)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.agent.graph import (
    POSTGRES_AVAILABLE,
    build_graph,
    get_checkpointer,
    get_registered_tools,
    graph,
)
from src.agent.state import (
    AgentState,
    add_tool_used,
    clear_error,
    create_initial_state,
    set_error,
    update_state_metadata,
    validate_state,
)
from src.agent.tools import market_data_tool

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langgraph.graph.state import CompiledStateGraph

# Version tracking for the agent package
__version__ = "0.1.0"

# Configure module logger (structlog for Phase 1b+)
logger = structlog.get_logger(__name__)


# =============================================================================
# Agent Factory
# =============================================================================


def get_agent() -> "CompiledStateGraph":
    """
    Get a pre-configured agent instance with in-memory checkpointing.

    This is a convenience function for local development and testing.
    Returns the default graph with MemorySaver (in-memory checkpointing).

    For production use with PostgresSaver (persistent checkpointing),
    use the context manager pattern in your application lifespan:

        from src.agent import get_checkpointer, build_graph

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            with get_checkpointer(settings.database_url) as checkpointer:
                app.state.graph = build_graph(checkpointer)
                yield

    Returns:
        A compiled LangGraph agent ready for invocation.

    Example:
        # Simple usage (MemorySaver - for local dev/testing)
        agent = get_agent()

        # With conversation thread
        config = {"configurable": {"thread_id": "conv-123"}}
        async for chunk in agent.astream(state, config=config):
            print(chunk)

    See Also:
        - get_checkpointer: Context manager for PostgresSaver support
        - build_graph: Build agent with a specific checkpointer
    """
    logger.info(
        "agent_initialized",
        checkpointer_type="MemorySaver",
        message="Using MemorySaver for in-memory checkpointing",
    )
    # Return the pre-built graph with MemorySaver (from graph.py)
    return graph


# =============================================================================
# Validation Utilities
# =============================================================================


def validate_agent_config() -> dict[str, Any]:
    """
    Validate agent configuration and tool availability.

    This function checks that all required components are properly configured
    and tools are available. Call during application startup.

    Returns:
        dict: Validation result with status, available tools, and any warnings.

    Raises:
        ValueError: If critical agent configuration is invalid.

    Example:
        from src.agent import validate_agent_config

        result = validate_agent_config()
        if result["warnings"]:
            for warning in result["warnings"]:
                logger.warning(warning)
    """
    warnings: list[str] = []
    errors: list[str] = []

    try:
        tools = get_registered_tools()
        tool_names = [tool.name for tool in tools]

        if not tools:
            warnings.append(
                "No tools registered. Agent will operate in chat-only mode."
            )

        logger.info(
            "agent_configuration_validated",
            tools_available=tool_names,
            tool_count=len(tool_names),
        )

    except Exception as e:
        errors.append(f"Failed to load agent tools: {e}")
        logger.error(
            "agent_configuration_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise ValueError(f"Agent configuration validation failed: {errors}") from e

    return {
        "status": "ok",
        "version": __version__,
        "tools_available": tool_names if tools else [],
        "tool_count": len(tools) if tools else 0,
        "warnings": warnings,
    }


def get_tool_by_name(name: str) -> BaseTool | None:
    """
    Get a specific tool by name.

    Args:
        name: The name of the tool to retrieve.

    Returns:
        The tool if found, None otherwise.

    Example:
        from src.agent import get_tool_by_name

        tool = get_tool_by_name("market_data")
        if tool:
            result = await tool.ainvoke({"tickers": ["AAPL"]})
    """
    tools = get_registered_tools()
    for tool in tools:
        if tool.name == name:
            return tool
    return None


def list_available_tools() -> list[dict[str, str]]:
    """
    List all available tools with their descriptions.

    Returns:
        List of dicts with tool name and description.

    Example:
        from src.agent import list_available_tools

        for tool_info in list_available_tools():
            print(f"{tool_info['name']}: {tool_info['description']}")
    """
    tools = get_registered_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description or "No description available",
        }
        for tool in tools
    ]


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Version
    "__version__",
    # State schema and utilities
    "AgentState",
    "create_initial_state",
    "validate_state",
    "update_state_metadata",
    "add_tool_used",
    "set_error",
    "clear_error",
    # Agent factory and graph
    "get_agent",
    "build_graph",
    "get_checkpointer",
    "graph",
    "POSTGRES_AVAILABLE",
    # Tool functions
    "get_registered_tools",
    "validate_agent_config",
    "get_tool_by_name",
    "list_available_tools",
    # Tools (re-exported for convenience)
    "market_data_tool",
]
