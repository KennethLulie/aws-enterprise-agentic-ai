"""
Aggregate agent tool instances for LangGraph binding.

Tools follow the LangChain @tool decorator pattern (no custom base class).
Import and re-export tool callables here so nodes/tests can use a single
registry.

IMPORTANT: Keep this in sync with REGISTERED_TOOLS in src/agent/graph.py.
When adding or removing tools here, update graph.py's REGISTERED_TOOLS tuple.
"""

from src.agent.tools.market_data import market_data_tool
from src.agent.tools.rag import rag_retrieval
from src.agent.tools.search import tavily_search
from src.agent.tools.sql import sql_query

# Canonical tool exports - these are registered in graph.py REGISTERED_TOOLS
__all__ = [
    "market_data_tool",
    "tavily_search",
    "sql_query",
    "rag_retrieval",
]
