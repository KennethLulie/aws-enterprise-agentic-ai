"""
LangGraph graph definition for the agent.

This module wires together the LangGraph StateGraph with chat, tool execution,
and error recovery nodes. It also exposes the registered tool list for binding
to the chat node and tool execution node.

Checkpointing:
    - Local development: MemorySaver (in-memory, no DB dependency)
    - AWS production: AsyncPostgresSaver (persistent, requires Neon PostgreSQL)

The graph can be built with a custom checkpointer using build_graph(), or
use the default MemorySaver via the pre-built `graph` instance.

IMPORTANT: When using async operations (astream, ainvoke), you MUST use
AsyncPostgresSaver, not the sync PostgresSaver. The sync version will raise
NotImplementedError when used with async methods.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, Sequence

import structlog
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agent.tools import market_data_tool, rag_retrieval, sql_query, tavily_search

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

# Module logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Conditional AsyncPostgresSaver Import
# =============================================================================

# AsyncPostgresSaver requires langgraph-checkpoint-postgres package
# MUST use async version for astream()/ainvoke() operations
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    AsyncPostgresSaver = None  # type: ignore[misc, assignment]
    AsyncConnectionPool = None  # type: ignore[misc, assignment]
    dict_row = None  # type: ignore[misc, assignment]

# =============================================================================
# Tool Registry
# =============================================================================

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


# =============================================================================
# Checkpointer Factory
# =============================================================================


@asynccontextmanager
async def get_checkpointer(
    database_url: str | None = None,
) -> AsyncIterator["BaseCheckpointSaver"]:
    """
    Async context manager that provides the appropriate checkpointer based on environment.

    Creates an AsyncPostgresSaver for persistent state when a database URL is provided
    and the package is available. Falls back to MemorySaver for local development
    or when PostgreSQL is unavailable.

    IMPORTANT: This is an ASYNC context manager because AsyncPostgresSaver requires
    async setup. When using graph.astream() or graph.ainvoke(), you MUST use the
    async checkpointer, not the sync PostgresSaver.

    Args:
        database_url: PostgreSQL connection string (e.g., from settings.database_url).
            If provided and valid, uses AsyncPostgresSaver. Otherwise falls back to
            MemorySaver.

    Yields:
        A LangGraph checkpointer instance (AsyncPostgresSaver or MemorySaver).

    Example:
        # In FastAPI lifespan (main.py):
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with get_checkpointer(settings.database_url) as checkpointer:
                app.state.checkpointer = checkpointer
                app.state.graph = build_graph(checkpointer)
                yield

        # For quick scripts or testing:
        async with get_checkpointer() as checkpointer:
            agent = build_graph(checkpointer)
            # use agent with astream/ainvoke...
    """
    if database_url and POSTGRES_AVAILABLE:
        try:
            # AsyncConnectionPool manages connection lifecycle
            # IMPORTANT: row_factory=dict_row is required for AsyncPostgresSaver
            # (it expects dict rows, not tuples)
            async with AsyncConnectionPool(
                conninfo=database_url,
                max_size=20,
                kwargs={"autocommit": True, "row_factory": dict_row},
            ) as pool:
                checkpointer = AsyncPostgresSaver(pool)
                # setup() creates checkpoint tables if they don't exist
                await checkpointer.setup()
                logger.info(
                    "postgres_checkpointer_created",
                    message="Using AsyncPostgresSaver for persistent checkpointing",
                )
                yield checkpointer
                return
        except Exception as e:
            logger.warning(
                "postgres_checkpointer_failed",
                error=str(e),
                error_type=type(e).__name__,
                message="Falling back to MemorySaver",
            )

    if database_url and not POSTGRES_AVAILABLE:
        logger.warning(
            "postgres_not_available",
            message="langgraph-checkpoint-postgres not installed, using MemorySaver",
        )

    # MemorySaver doesn't need context management and works with both sync/async
    logger.info(
        "memory_checkpointer_created",
        message="Using MemorySaver for in-memory checkpointing",
    )
    yield MemorySaver()


# =============================================================================
# Late imports (avoid circular dependency)
# =============================================================================

# These must come after get_registered_tools() definition since they import it
from src.agent.nodes.chat import chat_node  # noqa: E402
from src.agent.nodes.error_recovery import error_recovery_node  # noqa: E402
from src.agent.nodes.tools import tool_execution_node  # noqa: E402
from src.agent.state import AgentState  # noqa: E402


# =============================================================================
# Routing Helpers
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
# Graph Builder
# =============================================================================

# Create the graph builder (shared across all graph instances)
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


def build_graph(checkpointer: "BaseCheckpointSaver | None" = None):
    """
    Build the agent graph with the specified checkpointer.

    Creates a compiled LangGraph agent with the specified checkpointer for
    state persistence. If no checkpointer is provided, uses the default
    MemorySaver for in-memory state.

    Args:
        checkpointer: A LangGraph checkpointer instance (MemorySaver or
            PostgresSaver). If None, uses the default MemorySaver.

    Returns:
        A compiled LangGraph agent ready for invocation.

    Example:
        # Default (MemorySaver)
        agent = build_graph()

        # With PostgresSaver (use context manager)
        with get_checkpointer(settings.database_url) as checkpointer:
            agent = build_graph(checkpointer)
            # agent is valid within this context

        # Run the agent
        async for chunk in agent.astream(state, config={"configurable": {"thread_id": "123"}}):
            print(chunk)
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    return _graph_builder.compile(checkpointer=checkpointer)


# =============================================================================
# Default Graph Instance (Backward Compatibility)
# =============================================================================

# Default checkpointer for local development
_default_checkpointer = MemorySaver()

# Pre-built graph for backward compatibility with existing code
# This uses MemorySaver by default; use build_graph() for PostgresSaver
graph = build_graph(_default_checkpointer)


__all__ = [
    "graph",
    "build_graph",
    "get_registered_tools",
    "get_checkpointer",
    "POSTGRES_AVAILABLE",
]
