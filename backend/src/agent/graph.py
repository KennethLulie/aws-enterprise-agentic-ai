"""
LangGraph tool registration stub for Phase 0.

This module exposes the tools list used by the agent. It currently registers
the Financial Modeling Prep market data tool in place of the previous weather
stub to satisfy MCP demonstrations.
"""

from typing import Sequence

from langchain_core.tools import BaseTool

from src.agent.tools.market_data import market_data_tool


def get_registered_tools() -> Sequence[BaseTool]:
    """Return the tools available to the agent."""

    return [market_data_tool]


__all__ = ["get_registered_tools"]

