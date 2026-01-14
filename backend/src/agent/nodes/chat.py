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
- Fallback model: anthropic.claude-3-5-sonnet-20240620-v1:0
- Temperature: 0.7
- Max tokens: 4096

Usage:
    from src.agent.nodes.chat import chat_node

    # Use in LangGraph StateGraph
    graph.add_node("chat", chat_node)

Reference:
    - agent.mdc for node patterns
    - LangChain ChatBedrockConverse docs (Converse API)

LangChain Version Notes (langchain-aws~=0.2.0, langchain~=0.3.0):
    - Use ChatBedrockConverse for Converse API (recommended for Nova Pro)
    - AIMessageChunk does NOT have to_message() in 0.3.x
    - Combine chunks with + operator, then extract content directly
    - Nova Pro returns content as list: [{'type': 'text', 'text': '...'}]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence, cast

import structlog
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    AIMessageChunk,
    SystemMessage,
)

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

# System prompt that gives the AI context about its capabilities
SYSTEM_PROMPT = """You are an Enterprise Agentic AI Assistant with persistent conversation memory.

Key capabilities:
- You HAVE memory of this conversation. You can recall what the user said earlier in this conversation.
- You have access to tools for web search, market data, SQL queries, and document retrieval.
- You provide helpful, accurate, and contextual responses.

Important:
- DO NOT say you cannot remember past interactions - you CAN see the full conversation history.
- Reference previous messages naturally when relevant.
- Be concise and helpful.

When users share personal information (like their name or preferences), acknowledge it and use that context in future responses within this conversation."""


# =============================================================================
# Model Factory Functions
# =============================================================================


def _create_chat_model(
    model_id: str,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> ChatBedrockConverse:
    """
    Create a ChatBedrockConverse model instance.

    Uses the Converse API which is the recommended approach for
    Amazon Nova and newer Bedrock models. Provides better tool calling
    support and standardized message handling.

    Args:
        model_id: The Bedrock model ID to use.
        temperature: Sampling temperature (0.0-1.0).
        max_tokens: Maximum tokens in response.

    Returns:
        Configured ChatBedrockConverse instance.
    """
    settings = get_settings()

    # ChatBedrockConverse uses the Converse API (recommended for Nova Pro)
    # Note: temperature and max_tokens are direct kwargs, not in model_kwargs
    return ChatBedrockConverse(  # type: ignore[call-arg]
        model=model_id,
        region_name=settings.aws_region,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _bind_tools_to_model(
    model: ChatBedrockConverse,
    tools: Sequence[BaseTool] | None = None,
) -> Any:
    """
    Bind tools to a ChatBedrockConverse model for tool calling.

    Args:
        model: The ChatBedrockConverse model instance.
        tools: Optional sequence of tools to bind.

    Returns:
        Model with tools bound (or original model if no tools).
    """
    if tools:
        return model.bind_tools(tools)
    return model


# =============================================================================
# Message Sanitization for Bedrock
# =============================================================================


def _sanitize_messages_for_bedrock(
    messages: list[BaseMessage],
    log: structlog.BoundLogger,
) -> list[BaseMessage]:
    """
    Sanitize messages for Bedrock API compatibility.

    Bedrock rejects messages with empty content fields. This commonly occurs
    with AIMessages that have tool_calls but no text content. This function
    ensures all messages have valid content.

    Args:
        messages: List of messages to sanitize.
        log: Bound logger for contextual logging.

    Returns:
        List of sanitized messages safe for Bedrock API.
    """
    sanitized: list[BaseMessage] = []

    for msg in messages:
        if isinstance(msg, AIMessage):
            content = msg.content
            tool_calls = getattr(msg, "tool_calls", None)

            # Check if content is empty (string or list)
            is_empty = (
                content == ""
                or content is None
                or (isinstance(content, list) and len(content) == 0)
            )

            if is_empty and tool_calls:
                # AIMessage with tool calls but no content - add placeholder
                log.debug(
                    "Sanitizing empty AIMessage with tool calls",
                    tool_count=len(tool_calls),
                )
                # Create a new AIMessage with placeholder content
                sanitized.append(
                    AIMessage(
                        content="(calling tools)",
                        tool_calls=tool_calls,
                        id=msg.id,
                    )
                )
            elif is_empty:
                # Empty AIMessage with no tool calls - skip it
                log.debug("Skipping empty AIMessage with no tool calls")
                continue
            else:
                # Normal message - keep as is
                sanitized.append(msg)
        else:
            # Non-AI messages (Human, Tool, System) - keep as is
            sanitized.append(msg)

    return sanitized


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
    2. Creates a ChatBedrockConverse model with tool binding
    3. Invokes the LLM with the message history
    4. Falls back to alternative model if primary fails
    5. Returns updated state with LLM response

    The node implements a fallback strategy:
    - Primary: Nova Pro (amazon.nova-pro-v1:0)
    - Fallback: Claude 3.5 Sonnet (anthropic.claude-3-5-sonnet-20240620-v1:0)

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

    log.info(
        "chat_node: Processing messages with primary model",
        model_id=settings.bedrock_model_id,
    )

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
            fallback_model_id=settings.bedrock_fallback_model_id,
            error=str(primary_error),
        )

        # Try fallback model
        try:
            log.info(
                "chat_node: Processing messages with fallback model",
                model_id=settings.bedrock_fallback_model_id,
            )
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
                "The model is temporarily unavailable. Please try again in a moment."
            )
            log.error(
                "chat_node: All models failed",
                primary_error=str(primary_error),
                fallback_error=str(fallback_error),
                primary_model=settings.bedrock_model_id,
                fallback_model=settings.bedrock_fallback_model_id,
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
    # Prepend system message if not already present
    # This gives the AI context about its capabilities and memory
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    # Sanitize messages to ensure Bedrock compatibility
    # (handles empty content in AIMessages with tool calls)
    sanitized_messages = _sanitize_messages_for_bedrock(messages, log)

    log.debug(
        "Invoking model",
        model_id=model_id,
        tool_count=len(tools) if tools else 0,
        original_message_count=len(messages),
        sanitized_message_count=len(sanitized_messages),
    )

    model = _create_chat_model(model_id)
    model_with_tools = _bind_tools_to_model(model, tools)

    response = await _stream_response(model_with_tools, sanitized_messages, log)
    log.debug("Model stream completed", model_id=model_id)

    return response


async def _stream_response(
    model: ChatBedrockConverse,
    messages: list[BaseMessage],
    log: structlog.BoundLogger,
) -> BaseMessage:
    """
    Stream model responses and combine chunks into a full message.

    Uses LangChain's astream to support UI streaming while still returning
    a complete BaseMessage (including tool_calls) back to the graph.

    LangChain 0.3.x + langchain-aws 0.2.x Notes:
    - AIMessageChunk does NOT have to_message() method
    - Accumulate chunks with + operator, then extract content directly
    - Nova Pro via Converse API returns content as list of blocks:
      [{'type': 'text', 'text': '...', 'index': 0}, ...]
    - We convert this to a plain string for the final AIMessage
    """
    combined_chunk: AIMessageChunk | None = None
    chunk_count = 0

    async for chunk in model.astream(messages):
        chunk_count += 1

        # Log first few chunks in detail to understand structure
        if chunk_count <= 3:
            log.debug(
                "Stream chunk detail",
                chunk_num=chunk_count,
                chunk_type=type(chunk).__name__,
                chunk_content=repr(getattr(chunk, "content", "NO_CONTENT"))[:200],
            )
        else:
            log.debug("Received stream chunk", chunk_num=chunk_count)

        # Accumulate chunks - AIMessageChunk supports + operator for combining
        if isinstance(chunk, AIMessageChunk):
            if combined_chunk is None:
                combined_chunk = chunk
            else:
                combined_chunk = cast(AIMessageChunk, combined_chunk + chunk)

    log.debug(
        "Stream completed",
        total_chunks=chunk_count,
        has_combined_chunk=combined_chunk is not None,
    )

    if combined_chunk:
        # Extract content from the accumulated chunk
        # ChatBedrockConverse returns content as list: [{'type': 'text', 'text': '...'}]
        raw_content = combined_chunk.content

        # Convert list-format content to string
        if isinstance(raw_content, list):
            text_parts = []
            for block in raw_content:
                if isinstance(block, dict):
                    # Nova Pro format: {'type': 'text', 'text': '...', 'index': 0}
                    text = block.get("text", "")
                    if text:
                        text_parts.append(text)
                elif isinstance(block, str):
                    text_parts.append(block)
            combined_text = "".join(text_parts)
        elif isinstance(raw_content, str):
            combined_text = raw_content
        else:
            combined_text = str(raw_content) if raw_content else ""

        # Extract tool_calls from the accumulated chunk
        # In LangChain 0.3.x, tool_calls is a list of ToolCall objects
        tool_calls = getattr(combined_chunk, "tool_calls", None) or []

        # Create AIMessage with string content (LangChain 0.3.x compatible)
        result = AIMessage(
            content=combined_text,
            tool_calls=tool_calls,
            additional_kwargs=getattr(combined_chunk, "additional_kwargs", {}) or {},
            response_metadata=getattr(combined_chunk, "response_metadata", {}) or {},
        )

        log.info(
            "Model response assembled",
            content_length=len(result.content),
            content_preview=result.content[:100] if result.content else "(empty)",
            has_tool_calls=bool(result.tool_calls),
            tool_call_count=len(result.tool_calls) if result.tool_calls else 0,
        )
        return result

    raise ValueError("No response received from model stream")


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
    # Copy to avoid duplicate keyword collisions (messages is already in state)
    new_state = AgentState(**state)
    new_state["messages"] = [response]
    new_state["last_error"] = None  # Clear any previous error on success
    return new_state


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "chat_node",
]
