"""
Chat node for LangGraph agent - LLM invocation with tool binding.

This module implements the main chat node that processes user messages
using AWS Bedrock models (Nova Pro with Claude fallback). It handles:
- LLM invocation with message history
- Tool binding for agent tool use
- Fallback to alternative model if primary fails
- Structured error handling and logging

Configuration is loaded from settings:
- Primary model: amazon.nova-pro-v1:0
- Fallback model: anthropic.claude-3-5-sonnet-20241022-v2:0
- Temperature: 0.7
- Max tokens: 4096

Usage:
    from src.agent.nodes.chat import chat_node

    # Use in LangGraph StateGraph
    graph.add_node("chat", chat_node)

Reference:
    - agentic-ai.mdc for node patterns
    - LangChain ChatBedrock docs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

import structlog
from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, BaseMessage

from src.agent.state import AgentState, set_error
from src.config.settings import get_settings

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

# Configure structured logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# LLM Configuration
DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_MAX_TOKENS: int = 4096


# =============================================================================
# Model Factory Functions
# =============================================================================


def _create_chat_model(
    model_id: str,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> ChatBedrock:
    """
    Create a ChatBedrock model instance.

    Args:
        model_id: The Bedrock model ID to use.
        temperature: Sampling temperature (0.0-1.0).
        max_tokens: Maximum tokens in response.

    Returns:
        Configured ChatBedrock instance.
    """
    settings = get_settings()

    # NOTE: langchain-aws stubs may lag runtime; allow region/model kwargs explicitly.
    return ChatBedrock(  # type: ignore[call-arg]
        model_id=model_id,
        region_name=settings.aws_region,
        model_kwargs={
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )


def _bind_tools_to_model(
    model: ChatBedrock,
    tools: Sequence[BaseTool] | None = None,
) -> Any:
    """
    Bind tools to a ChatBedrock model for tool calling.

    Args:
        model: The ChatBedrock model instance.
        tools: Optional sequence of tools to bind.

    Returns:
        Model with tools bound (or original model if no tools).
    """
    if tools:
        return model.bind_tools(tools)
    return model


# =============================================================================
# Chat Node Implementation
# =============================================================================


async def chat_node(
    state: AgentState,
    tools: Sequence[BaseTool] | None = None,
) -> AgentState:
    """
    Main LLM invocation node for processing user messages.

    This node:
    1. Takes the current conversation state with message history
    2. Creates a ChatBedrock model with tool binding
    3. Invokes the LLM with the message history
    4. Falls back to alternative model if primary fails
    5. Returns updated state with LLM response

    The node implements a fallback strategy:
    - Primary: Nova Pro (amazon.nova-pro-v1:0)
    - Fallback: Claude 3.5 Sonnet (anthropic.claude-3-5-sonnet-20241022-v2:0)

    Args:
        state: Current agent state with messages and context.
        tools: Optional sequence of tools for the model to use.
            If provided, tools will be bound to the model.

    Returns:
        Updated AgentState with LLM response added to messages.
        On error, last_error is set with error details.

    Example:
        state = await chat_node(state)
        # state["messages"] now contains LLM response

        # With tools
        from src.agent.tools import market_data_tool
        state = await chat_node(state, tools=[market_data_tool])
    """
    settings = get_settings()
    messages: list[BaseMessage] = state.get("messages", [])
    conversation_id = state.get("conversation_id", "unknown")

    log = logger.bind(
        conversation_id=conversation_id,
        message_count=len(messages),
    )

    if not messages:
        log.warning("chat_node called with empty messages")
        return state

    log.info("chat_node: Processing messages with primary model")

    # Try primary model first
    try:
        response = await _invoke_model(
            model_id=settings.bedrock_model_id,
            messages=messages,
            tools=tools,
            log=log,
        )
        log.info(
            "chat_node: Primary model response received",
            model_id=settings.bedrock_model_id,
        )
        return _create_success_state(state, response)

    except Exception as primary_error:
        log.warning(
            "chat_node: Primary model failed, trying fallback",
            model_id=settings.bedrock_model_id,
            error=str(primary_error),
        )

        # Try fallback model
        try:
            response = await _invoke_model(
                model_id=settings.bedrock_fallback_model_id,
                messages=messages,
                tools=tools,
                log=log,
            )
            log.info(
                "chat_node: Fallback model response received",
                model_id=settings.bedrock_fallback_model_id,
            )
            return _create_success_state(state, response)

        except Exception as fallback_error:
            error_msg = (
                f"Both primary and fallback models failed. "
                f"Primary ({settings.bedrock_model_id}): {primary_error}. "
                f"Fallback ({settings.bedrock_fallback_model_id}): {fallback_error}."
            )
            log.error(
                "chat_node: All models failed",
                primary_error=str(primary_error),
                fallback_error=str(fallback_error),
            )
            return set_error(state, error_msg)


async def _invoke_model(
    model_id: str,
    messages: list[BaseMessage],
    tools: Sequence[BaseTool] | None,
    log: structlog.BoundLogger,
) -> BaseMessage:
    """
    Invoke a Bedrock model with messages and optional tools.

    Args:
        model_id: The Bedrock model ID to use.
        messages: Message history to send to the model.
        tools: Optional tools to bind to the model.
        log: Bound logger for contextual logging.

    Returns:
        AIMessage response from the model.

    Raises:
        Exception: If model invocation fails.
    """
    log.debug(
        "Invoking model", model_id=model_id, tool_count=len(tools) if tools else 0
    )

    model = _create_chat_model(model_id)
    model_with_tools = _bind_tools_to_model(model, tools)

    # Use ainvoke for async invocation
    response = await model_with_tools.ainvoke(messages)

    # Preserve structured responses (tool_calls, etc.); coerce only if unexpected
    if isinstance(response, BaseMessage):
        return response

    response = AIMessage(content=str(response))

    return response


def _create_success_state(state: AgentState, response: BaseMessage) -> AgentState:
    """
    Create updated state with successful LLM response.

    The messages field uses the add_messages reducer, so we just need
    to return the new messages and they'll be properly appended.

    Args:
        state: Current agent state.
        response: AIMessage response from the model.

    Returns:
        Updated AgentState with response added to messages.
    """
    # Return only the new message - the add_messages reducer handles appending
    return AgentState(
        **state,
        messages=[response],
        last_error=None,  # Clear any previous error on success
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "chat_node",
]
